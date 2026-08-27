from __future__ import annotations

import binascii
import ctypes
import ctypes.util
from functools import lru_cache
from io import BytesIO
from pathlib import Path
import struct
import subprocess
from typing import Any
import zlib

from PIL import Image, ImageCms


TYPE_RGB_16 = (4 << 16) | (3 << 3) | 2
INTENT_RELATIVE_COLORIMETRIC = 1
CMS_FLAGS_BLACK_POINT_COMPENSATION = 0x2000
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _numpy():
    try:
        import numpy as np
    except ImportError as error:  # pragma: no cover - environment-specific
        raise RuntimeError(
            "NumPy is required for 16-bit TIFF portrait development"
        ) from error
    return np


@lru_cache(maxsize=1)
def _lcms_library() -> ctypes.CDLL:
    candidates: list[Path | str] = []
    discovered = ctypes.util.find_library("lcms2")
    if discovered:
        candidates.append(discovered)
    try:
        from PIL import _imagingcms

        imaging_root = Path(_imagingcms.__file__).resolve().parent
        candidates.extend(
            sorted((imaging_root / ".dylibs").glob("liblcms2*.dylib"))
        )
        candidates.extend(sorted((imaging_root / ".libs").glob("liblcms2*")))
    except ImportError:
        pass
    for candidate in candidates:
        try:
            library = ctypes.CDLL(str(candidate))
            break
        except OSError:
            continue
    else:  # pragma: no cover - depends on installation
        raise RuntimeError("LittleCMS 2 is required for 16-bit ICC conversion")

    library.cmsOpenProfileFromMem.restype = ctypes.c_void_p
    library.cmsOpenProfileFromMem.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    library.cmsCreateTransform.restype = ctypes.c_void_p
    library.cmsCreateTransform.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_uint32,
    ]
    library.cmsDoTransform.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_uint32,
    ]
    library.cmsDeleteTransform.argtypes = [ctypes.c_void_p]
    library.cmsCloseProfile.argtypes = [ctypes.c_void_p]
    return library


@lru_cache(maxsize=1)
def srgb_profile_bytes() -> bytes:
    return ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()


def transform_rgb16(
    pixels: Any,
    source_profile: bytes,
    destination_profile: bytes | None = None,
) -> Any:
    """Apply an embedded ICC transform to an interleaved uint16 RGB array."""
    np = _numpy()
    source = np.ascontiguousarray(pixels, dtype="<u2")
    if source.ndim != 3 or source.shape[2] != 3:
        raise ValueError("16-bit color transform requires an HxWx3 RGB array")
    destination_profile = destination_profile or srgb_profile_bytes()
    library = _lcms_library()
    source_buffer = ctypes.create_string_buffer(source_profile)
    destination_buffer = ctypes.create_string_buffer(destination_profile)
    source_handle = library.cmsOpenProfileFromMem(
        source_buffer, len(source_profile)
    )
    destination_handle = library.cmsOpenProfileFromMem(
        destination_buffer, len(destination_profile)
    )
    if not source_handle or not destination_handle:
        if source_handle:
            library.cmsCloseProfile(source_handle)
        if destination_handle:
            library.cmsCloseProfile(destination_handle)
        raise RuntimeError("Unable to open ICC profile")
    transform = library.cmsCreateTransform(
        source_handle,
        TYPE_RGB_16,
        destination_handle,
        TYPE_RGB_16,
        INTENT_RELATIVE_COLORIMETRIC,
        CMS_FLAGS_BLACK_POINT_COMPENSATION,
    )
    if not transform:
        library.cmsCloseProfile(source_handle)
        library.cmsCloseProfile(destination_handle)
        raise RuntimeError("Unable to create 16-bit ICC transform")
    output = np.empty_like(source)
    try:
        library.cmsDoTransform(
            transform,
            ctypes.c_void_p(source.ctypes.data),
            ctypes.c_void_p(output.ctypes.data),
            source.shape[0] * source.shape[1],
        )
    finally:
        library.cmsDeleteTransform(transform)
        library.cmsCloseProfile(source_handle)
        library.cmsCloseProfile(destination_handle)
    return output


def read_tiff_rgb16(path: Path, ffmpeg: str) -> tuple[Any, bytes, dict[str, Any]]:
    np = _numpy()
    with Image.open(path) as image:
        if image.format != "TIFF":
            raise ValueError(f"Expected TIFF source: {path}")
        width, height = image.size
        bits = tuple(image.tag_v2.get(258) or ())
        profile = image.info.get("icc_profile")
        orientation = int(image.getexif().get(274, 1))
        if bits != (16, 16, 16):
            raise ValueError(f"{path.name} must contain 16-bit RGB channels; found {bits}")
        if not profile:
            raise ValueError(f"{path.name} requires an embedded ICC profile")
        if orientation != 1:
            raise ValueError(f"{path.name} must be exported with normalized orientation")
        profile_description = ImageCms.getProfileDescription(
            ImageCms.ImageCmsProfile(BytesIO(profile))
        ).strip()
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(path),
        "-frames:v",
        "1",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb48le",
        "pipe:1",
    ]
    raw = subprocess.check_output(command)
    expected_bytes = width * height * 3 * 2
    if len(raw) != expected_bytes:
        raise RuntimeError(
            f"Decoded byte count for {path.name} was {len(raw)}; expected {expected_bytes}"
        )
    pixels = np.frombuffer(raw, dtype="<u2").reshape(height, width, 3).copy()
    return pixels, profile, {
        "sourceBitsPerSample": list(bits),
        "sourceIccProfilePresent": True,
        "sourceIccProfileDescription": profile_description,
        "sourceOrientation": orientation,
    }


def _gaussian_kernel(sigma: float) -> Any:
    np = _numpy()
    radius = max(1, int(round(3.0 * sigma)))
    positions = np.arange(-radius, radius + 1, dtype=np.float32)
    kernel = np.exp(-(positions * positions) / (2.0 * sigma * sigma))
    return kernel / kernel.sum()


def _convolve_channel(channel: Any, kernel: Any, axis: int) -> Any:
    np = _numpy()
    radius = len(kernel) // 2
    padding = [(0, 0), (0, 0)]
    padding[axis] = (radius, radius)
    padded = np.pad(channel, padding, mode="edge")
    output = np.zeros_like(channel, dtype=np.float32)
    for index, weight in enumerate(kernel):
        if axis == 0:
            output += padded[index : index + channel.shape[0], :] * weight
        else:
            output += padded[:, index : index + channel.shape[1]] * weight
    return output


def gaussian_blur_rgb(pixels: Any, sigma: float) -> Any:
    np = _numpy()
    if sigma <= 0:
        return np.asarray(pixels, dtype=np.float32).copy()
    kernel = _gaussian_kernel(sigma)
    output = np.empty_like(pixels, dtype=np.float32)
    for channel_index in range(3):
        horizontal = _convolve_channel(
            np.asarray(pixels[:, :, channel_index], dtype=np.float32), kernel, 1
        )
        output[:, :, channel_index] = _convolve_channel(horizontal, kernel, 0)
    return output


def under_resolved_rgb16(pixels: Any, settings: dict[str, Any]) -> Any:
    np = _numpy()
    values = np.asarray(pixels, dtype=np.float32) / 65535.0
    gains = np.asarray(
        [
            float(settings["temperatureRedGain"]),
            float(settings["temperatureGreenGain"]),
            float(settings["temperatureBlueGain"]),
        ],
        dtype=np.float32,
    )
    shifted = np.clip(values * gains, 0.0, 1.0)
    black = float(settings["blackLift"]) * ((1.0 - shifted) ** 10)
    shadows = float(settings["shadowSuppression"]) * np.exp(
        -(
            (shifted - float(settings["shadowCenter"]))
            / float(settings["shadowWidth"])
        )
        ** 2
    )
    highlights = float(settings["highlightVeil"]) * np.exp(
        -(
            (shifted - float(settings["highlightCenter"]))
            / float(settings["highlightWidth"])
        )
        ** 2
    )
    toned = np.clip(shifted + black - shadows + highlights, 0.0, 1.0)
    radius = float(settings["textureBlurRadiusAt1080"]) * max(
        pixels.shape[1] / 1080.0, pixels.shape[0] / 1920.0
    )
    softened = gaussian_blur_rgb(toned, radius)
    texture_mix = float(settings["textureSoftening"])
    result = toned * (1.0 - texture_mix) + softened * texture_mix
    return np.rint(np.clip(result, 0.0, 1.0) * 65535.0).astype("<u2")


def _png_chunk(chunk_type: bytes, payload: bytes) -> bytes:
    checksum = binascii.crc32(chunk_type)
    checksum = binascii.crc32(payload, checksum) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + chunk_type + payload + struct.pack(">I", checksum)


def embed_png_icc(path: Path, profile: bytes, name: str = "sRGB") -> None:
    source = path.read_bytes()
    if not source.startswith(PNG_SIGNATURE):
        raise ValueError(f"Not a PNG file: {path}")
    output = bytearray(PNG_SIGNATURE)
    position = len(PNG_SIGNATURE)
    inserted = False
    while position < len(source):
        length = struct.unpack(">I", source[position : position + 4])[0]
        chunk_end = position + 12 + length
        chunk_type = source[position + 4 : position + 8]
        chunk = source[position:chunk_end]
        output.extend(chunk)
        position = chunk_end
        if chunk_type == b"IHDR" and not inserted:
            payload = name.encode("latin-1") + b"\x00\x00" + zlib.compress(profile)
            output.extend(_png_chunk(b"iCCP", payload))
            inserted = True
    if not inserted:
        raise ValueError(f"PNG lacks IHDR chunk: {path}")
    path.write_bytes(bytes(output))


def write_rgb16_png(pixels: Any, path: Path, ffmpeg: str, profile: bytes) -> None:
    np = _numpy()
    array = np.ascontiguousarray(pixels, dtype="<u2")
    height, width, channels = array.shape
    if channels != 3:
        raise ValueError("PNG output requires HxWx3 RGB data")
    path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "rawvideo",
        "-pixel_format",
        "rgb48le",
        "-video_size",
        f"{width}x{height}",
        "-i",
        "pipe:0",
        "-frames:v",
        "1",
        "-c:v",
        "png",
        "-pred",
        "mixed",
        "-pix_fmt",
        "rgb48be",
        str(path),
    ]
    subprocess.run(command, input=array.tobytes(), check=True)
    embed_png_icc(path, profile)


def png_bit_depth(path: Path) -> int:
    data = path.read_bytes()[:25]
    if not data.startswith(PNG_SIGNATURE) or data[12:16] != b"IHDR":
        raise ValueError(f"Invalid PNG: {path}")
    return data[24]
