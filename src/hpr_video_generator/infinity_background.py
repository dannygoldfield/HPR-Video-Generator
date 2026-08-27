from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache
from io import BytesIO
import hashlib
import json
import math
from pathlib import Path
import subprocess
from typing import Any

from PIL import Image, ImageCms, ImageDraw, ImageFilter, ImageFont

from .color_pipeline import (
    srgb_profile_bytes,
    transform_rgb16,
    under_resolved_rgb16,
    write_rgb16_png,
)
from .config import Config
from .development import DevelopmentConfig, DevelopmentRecipe, development_mask_frames


EFFECTS = {
    "momentum_wake",
    "emulsion_bloom",
    "floating_print",
    "negative_space_aperture",
    "residual_gesture",
    "incomplete_geometry",
    "borrowed_color_field",
    "number_depth_field",
    "number_side_streams",
    "number_evasive_corridor",
    "gradient_curtain",
    "sliding_panel",
    "hinged_door",
    "number_doorway",
    "flat_number_drift",
    "flat_number_grid",
    "flat_number_blobs",
    "flat_number_separation",
    "gradient_curtain_2d",
    "sliding_panel_full",
    "hinged_door_one_way",
    "flat_number_wipe",
}


def _numpy():
    try:
        import numpy as np
    except ImportError as error:  # pragma: no cover - environment-specific
        raise RuntimeError("NumPy is required for Infinity background generation") from error
    return np


@dataclass(frozen=True)
class InfinityBackgroundRecipe:
    id: str
    name: str
    effect: str
    strength: float
    speed: float
    visibility_boost: float
    perceptual_floor: dict[str, float]
    loop_behavior: str
    parameters: dict[str, Any]
    description: str


@dataclass(frozen=True)
class InfinityBackgroundConfig:
    version: str
    experiment_id: str
    working_width: int
    working_height: int
    base_portrait_treatment: dict[str, Any]
    font: dict[str, str]
    principle: str
    recipes: dict[str, InfinityBackgroundRecipe]


@dataclass(frozen=True)
class LayeredWorkingSources:
    layered_tiff: Path
    subject_png: Path
    background_png: Path
    subject_finished: Path
    subject_under_resolved: Path
    background_srgb: Path
    background_pixels: Any
    subject_pixels: Any
    subject_alpha: Any
    provenance: dict[str, Any]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_infinity_background_config(path: Path) -> InfinityBackgroundConfig:
    payload = json.loads(path.read_text(encoding="utf-8"))
    recipes: dict[str, InfinityBackgroundRecipe] = {}
    for item in payload["recipes"]:
        recipe = InfinityBackgroundRecipe(
            id=item["id"],
            name=item["name"],
            effect=item["effect"],
            strength=float(item["strength"]),
            speed=float(item["speed"]),
            visibility_boost=float(item.get("visibilityBoost", 1.0)),
            perceptual_floor={
                "meanDelta8Bit": float(
                    item.get("perceptualFloor", {}).get("meanDelta8Bit", 0.0)
                ),
                "p95Delta8Bit": float(
                    item.get("perceptualFloor", {}).get("p95Delta8Bit", 0.0)
                ),
                "activePixelsAbove3Percent": float(
                    item.get("perceptualFloor", {}).get(
                        "activePixelsAbove3Percent", 0.0
                    )
                ),
            },
            loop_behavior=item.get("loopBehavior", "continuous"),
            parameters=dict(item.get("parameters", {})),
            description=item["description"],
        )
        if recipe.effect not in EFFECTS:
            raise ValueError(f"{recipe.id} has an unsupported effect: {recipe.effect}")
        if not 0 < recipe.strength <= 0.45:
            raise ValueError(f"{recipe.id} strength must be greater than 0 and at most 0.45")
        static_number_field = (
            recipe.effect == "flat_number_grid"
            and recipe.parameters.get("numberMotion") == "static"
        )
        if recipe.speed < 0 or (recipe.speed == 0 and not static_number_field):
            raise ValueError(
                f"{recipe.id} speed must be greater than zero unless its "
                "numberMotion is static"
            )
        if not 1.0 <= recipe.visibility_boost <= 3.0:
            raise ValueError(
                f"{recipe.id} visibilityBoost must be between 1.0 and 3.0"
            )
        if any(value < 0 for value in recipe.perceptual_floor.values()):
            raise ValueError(f"{recipe.id} perceptual floors cannot be negative")
        if recipe.loop_behavior not in {"continuous", "intentional_hard_reset"}:
            raise ValueError(f"{recipe.id} has an unsupported loopBehavior")
        if recipe.id in recipes:
            raise ValueError(f"Duplicate Infinity background recipe: {recipe.id}")
        recipes[recipe.id] = recipe
    if not recipes:
        raise ValueError("An Infinity background comparison requires at least one recipe")
    return InfinityBackgroundConfig(
        version=payload["version"],
        experiment_id=payload["experimentId"],
        working_width=int(payload["workingWidth"]),
        working_height=int(payload["workingHeight"]),
        base_portrait_treatment=payload["basePortraitTreatment"],
        font=dict(payload.get("font", {})),
        principle=payload["principle"],
        recipes=recipes,
    )


def personalize_infinity_background_recipe(
    recipe: InfinityBackgroundRecipe,
    portrait_id: str,
) -> InfinityBackgroundRecipe:
    """Resolve a reproducible portrait-specific digit arrangement when requested."""
    if not recipe.parameters.get("portraitUniqueLayout", False):
        return recipe
    parameters = dict(recipe.parameters)
    parameters["numberSeed"] = f"{recipe.id}:{portrait_id}"
    parameters.pop("phaseOffset", None)
    return replace(recipe, parameters=parameters)


def resolve_font_file(
    family: str,
    style: str,
    search_roots: list[Path] | None = None,
) -> Path:
    """Resolve a locally licensed font by its internal family and style names."""
    roots = search_roots or [
        Path.home() / "Library/Fonts",
        Path("/Library/Fonts"),
        Path("/System/Library/Fonts"),
        Path.home()
        / "Library/Application Support/Adobe/CoreSync/plugins/livetype/.r",
    ]
    wanted_family = family.casefold().strip()
    wanted_style = style.casefold().strip()
    matches: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.casefold() not in {".otf", ".ttf", ".ttc"}:
                continue
            try:
                found_family, found_style = ImageFont.truetype(str(path), 12).getname()
            except (OSError, ValueError):
                continue
            if found_family.casefold().strip() != wanted_family:
                continue
            if found_style.casefold().strip() == wanted_style:
                return path
            matches.append(path)
    if matches:
        return matches[0]
    raise FileNotFoundError(f"Could not resolve local font: {family} {style}")


def _profile_description(profile: bytes) -> str:
    return ImageCms.getProfileDescription(
        ImageCms.ImageCmsProfile(BytesIO(profile))
    ).strip()


def _decode_png_rgba16(
    path: Path,
    ffmpeg: str,
    fallback_profile: bytes | None = None,
) -> tuple[Any, Any, bytes, str]:
    np = _numpy()
    with Image.open(path) as image:
        if image.mode != "RGBA":
            raise ValueError(f"{path.name} must be RGBA; found {image.mode}")
        width, height = image.size
        profile = image.info.get("icc_profile") or fallback_profile
        if not profile:
            raise ValueError(f"{path.name} requires an embedded ICC profile")
        description = _profile_description(profile)
    raw = subprocess.check_output(
        [
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
            "rgba64le",
            "pipe:1",
        ]
    )
    expected = width * height * 4 * 2
    if len(raw) != expected:
        raise RuntimeError(f"Decoded {len(raw)} subject bytes; expected {expected}")
    rgba = np.frombuffer(raw, dtype="<u2").reshape(height, width, 4).copy()
    return rgba[:, :, :3], rgba[:, :, 3], profile, description


def _decode_png_rgb16(
    path: Path,
    ffmpeg: str,
    fallback_profile: bytes | None = None,
) -> tuple[Any, bytes, str]:
    np = _numpy()
    with Image.open(path) as image:
        if image.mode != "RGB":
            raise ValueError(f"{path.name} must be RGB; found {image.mode}")
        width, height = image.size
        profile = image.info.get("icc_profile") or fallback_profile
        if not profile:
            raise ValueError(f"{path.name} requires an embedded ICC profile")
        description = _profile_description(profile)
    raw = subprocess.check_output(
        [
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
    )
    expected = width * height * 3 * 2
    if len(raw) != expected:
        raise RuntimeError(f"Decoded {len(raw)} background bytes; expected {expected}")
    pixels = np.frombuffer(raw, dtype="<u2").reshape(height, width, 3).copy()
    return pixels, profile, description


def _scaled_rgb16(path: Path, width: int, height: int, ffmpeg: str) -> Any:
    np = _numpy()
    raw = subprocess.check_output(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(path),
            "-vf",
            f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}",
            "-frames:v",
            "1",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb48le",
            "pipe:1",
        ]
    )
    expected = width * height * 3 * 2
    if len(raw) != expected:
        raise RuntimeError(f"Scaled RGB byte count was {len(raw)}; expected {expected}")
    return np.frombuffer(raw, dtype="<u2").reshape(height, width, 3).copy()


def _scaled_alpha16(path: Path, width: int, height: int, ffmpeg: str) -> Any:
    np = _numpy()
    raw = subprocess.check_output(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(path),
            "-vf",
            f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},"
            "format=rgba64le,alphaextract,format=gray16le",
            "-frames:v",
            "1",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "gray16le",
            "pipe:1",
        ]
    )
    expected = width * height * 2
    if len(raw) != expected:
        raise RuntimeError(f"Scaled alpha byte count was {len(raw)}; expected {expected}")
    return np.frombuffer(raw, dtype="<u2").reshape(height, width).copy()


def prepare_layered_working_sources(
    *,
    layered_tiff: Path,
    subject_png: Path,
    background_png: Path,
    output_root: Path,
    working_width: int,
    working_height: int,
    surrogate_settings: dict[str, Any],
    ffmpeg: str,
) -> LayeredWorkingSources:
    np = _numpy()
    output_root.mkdir(parents=True, exist_ok=True)
    with Image.open(layered_tiff) as layered_image:
        layered_profile = layered_image.info.get("icc_profile")
        if not layered_profile:
            raise ValueError(f"{layered_tiff.name} requires an embedded ICC profile")
        layered_profile_name = _profile_description(layered_profile)
    subject_rgb, subject_alpha, subject_profile, subject_profile_name = _decode_png_rgba16(
        subject_png, ffmpeg, layered_profile
    )
    background_rgb, background_profile, background_profile_name = _decode_png_rgb16(
        background_png, ffmpeg, layered_profile
    )
    if subject_rgb.shape[:2] != background_rgb.shape[:2]:
        raise ValueError("Subject and background layers must share dimensions")
    if subject_profile_name != background_profile_name:
        raise ValueError("Subject and background layers must share an ICC profile")
    if int(subject_alpha.min()) != 0 or int(subject_alpha.max()) != 65535:
        raise ValueError("Subject layer must contain both transparent and opaque pixels")

    working_profile = srgb_profile_bytes()
    subject_srgb = transform_rgb16(subject_rgb, subject_profile, working_profile)
    background_srgb_pixels = transform_rgb16(
        background_rgb, background_profile, working_profile
    )
    subject_under = under_resolved_rgb16(subject_srgb, surrogate_settings)

    subject_finished_path = output_root / "infinity-subject-finished-srgb-16bit.png"
    subject_under_path = output_root / "infinity-subject-under-resolved-srgb-16bit.png"
    background_srgb_path = output_root / "infinity-background-srgb-16bit.png"
    write_rgb16_png(subject_srgb, subject_finished_path, ffmpeg, working_profile)
    write_rgb16_png(subject_under, subject_under_path, ffmpeg, working_profile)
    write_rgb16_png(background_srgb_pixels, background_srgb_path, ffmpeg, working_profile)

    background_working = _scaled_rgb16(
        background_srgb_path, working_width, working_height, ffmpeg
    )
    subject_working = _scaled_rgb16(
        subject_finished_path, working_width, working_height, ffmpeg
    )
    alpha_working = _scaled_alpha16(subject_png, working_width, working_height, ffmpeg)

    return LayeredWorkingSources(
        layered_tiff=layered_tiff,
        subject_png=subject_png,
        background_png=background_png,
        subject_finished=subject_finished_path,
        subject_under_resolved=subject_under_path,
        background_srgb=background_srgb_path,
        background_pixels=background_working,
        subject_pixels=subject_working,
        subject_alpha=alpha_working,
        provenance={
            "layeredTiff": str(layered_tiff.resolve()),
            "layeredTiffSha256": _sha256(layered_tiff),
            "layeredTiffBitsPerChannel": 16,
            "layeredTiffProfile": subject_profile_name,
            "workingLayerProfileSource": (
                "The Photoshop PNG working copies contain the unconverted layer pixels; "
                f"their {layered_profile_name} profile is inherited from the authoritative layered TIFF."
            ),
            "layerNames": ["Subject", "Background"],
            "sourceWidth": int(subject_rgb.shape[1]),
            "sourceHeight": int(subject_rgb.shape[0]),
            "subjectLayer": str(subject_png.resolve()),
            "subjectLayerSha256": _sha256(subject_png),
            "backgroundLayer": str(background_png.resolve()),
            "backgroundLayerSha256": _sha256(background_png),
            "subjectAlphaMinimum": int(subject_alpha.min()),
            "subjectAlphaMaximum": int(subject_alpha.max()),
            "workingProfile": "sRGB IEC61966-2.1",
            "precisionPolicy": "16-bit layer extraction, ICC conversion, effect generation, development compositing, and background compositing; 8-bit only at H.264 delivery encode",
        },
    )


def _blur_mask(mask: Any, radius: float) -> Any:
    np = _numpy()
    image = Image.fromarray(np.rint(np.clip(mask, 0, 1) * 255).astype("uint8"), "L")
    blurred = image.filter(ImageFilter.GaussianBlur(radius=radius))
    return np.asarray(blurred, dtype=np.float32) / 255.0


def _shift_mask(mask: Any, dx: int, dy: int) -> Any:
    np = _numpy()
    output = np.zeros_like(mask)
    source_x0 = max(0, -dx)
    source_x1 = mask.shape[1] - max(0, dx)
    source_y0 = max(0, -dy)
    source_y1 = mask.shape[0] - max(0, dy)
    target_x0 = max(0, dx)
    target_x1 = target_x0 + max(0, source_x1 - source_x0)
    target_y0 = max(0, dy)
    target_y1 = target_y0 + max(0, source_y1 - source_y0)
    if source_x1 > source_x0 and source_y1 > source_y0:
        output[target_y0:target_y1, target_x0:target_x1] = mask[
            source_y0:source_y1, source_x0:source_x1
        ]
    return output


def _oriented_gaussian(
    x: Any,
    y: Any,
    *,
    center_x: float,
    center_y: float,
    radius_x: float,
    radius_y: float,
    angle: float = 0.0,
) -> Any:
    cosine = math.cos(angle)
    sine = math.sin(angle)
    translated_x = x - center_x
    translated_y = y - center_y
    rotated_x = translated_x * cosine + translated_y * sine
    rotated_y = -translated_x * sine + translated_y * cosine
    return _numpy().exp(
        -0.5 * ((rotated_x / radius_x) ** 2 + (rotated_y / radius_y) ** 2)
    )


def _geometry_masks(
    width: int,
    height: int,
    *,
    line_scale: float = 1.0,
) -> list[Any]:
    np = _numpy()
    scale = 2
    masks = []
    for group in range(3):
        image = Image.new("L", (width * scale, height * scale), 0)
        draw = ImageDraw.Draw(image)
        line_width = max(2, round(width * 0.004 * scale * line_scale))
        if group == 0:
            draw.arc(
                (
                    int(width * 0.03 * scale),
                    int(height * 0.23 * scale),
                    int(width * 0.48 * scale),
                    int(height * 0.53 * scale),
                ),
                198,
                494,
                fill=255,
                width=line_width,
            )
        elif group == 1:
            draw.arc(
                (
                    int(width * 0.26 * scale),
                    int(height * 0.02 * scale),
                    int(width * 0.96 * scale),
                    int(height * 0.43 * scale),
                ),
                205,
                338,
                fill=255,
                width=line_width,
            )
            draw.line(
                (
                    int(width * 0.08 * scale),
                    int(height * 0.16 * scale),
                    int(width * 0.88 * scale),
                    int(height * 0.09 * scale),
                ),
                fill=170,
                width=max(1, line_width // 2),
            )
        else:
            for point_x, point_y, radius in (
                (0.07, 0.08, 0.012),
                (0.52, 0.055, 0.009),
                (0.92, 0.29, 0.014),
                (0.18, 0.61, 0.009),
                (0.88, 0.68, 0.011),
            ):
                x = int(point_x * width * scale)
                y = int(point_y * height * scale)
                r = max(2, int(radius * width * scale * line_scale**0.65))
                draw.ellipse((x - r, y - r, x + r, y + r), fill=255)
        image = image.resize((width, height), Image.Resampling.LANCZOS)
        image = image.filter(
            ImageFilter.GaussianBlur(radius=0.35 * min(line_scale, 2.0))
        )
        masks.append(np.asarray(image, dtype=np.float32) / 255.0)
    return masks


def build_background_context(
    background_pixels: Any,
    subject_pixels: Any,
    subject_alpha: Any,
) -> dict[str, Any]:
    np = _numpy()
    background = np.asarray(background_pixels, dtype=np.float32) / 65535.0
    subject = np.asarray(subject_pixels, dtype=np.float32) / 65535.0
    alpha = np.asarray(subject_alpha, dtype=np.float32) / 65535.0
    height, width = alpha.shape
    y, x = np.mgrid[0:height, 0:width].astype(np.float32)
    x /= max(width - 1, 1)
    y /= max(height - 1, 1)
    luminance = subject.mean(axis=2)
    skin_candidates = (
        (alpha > 0.65)
        & (subject[:, :, 0] > subject[:, :, 1] * 1.04)
        & (subject[:, :, 1] > subject[:, :, 2] * 1.02)
        & (luminance > 0.30)
    )
    dark_candidates = (alpha > 0.65) & (luminance < 0.26)
    skin_color = (
        np.median(subject[skin_candidates], axis=0)
        if skin_candidates.any()
        else np.asarray([0.72, 0.56, 0.46], dtype=np.float32)
    )
    dark_color = (
        np.median(subject[dark_candidates], axis=0)
        if dark_candidates.any()
        else np.asarray([0.10, 0.10, 0.12], dtype=np.float32)
    )
    return {
        "background": background,
        "alpha": alpha,
        "alphaSoft": _blur_mask(alpha, max(2.0, width * 0.028)),
        "alphaGhost": _blur_mask(alpha, max(1.0, width * 0.012)),
        "alphaShadowBold": _blur_mask(alpha, max(3.0, width * 0.050)),
        "alphaGhostBold": _blur_mask(alpha, max(2.0, width * 0.026)),
        "x": x,
        "y": y,
        "skinColor": np.asarray(skin_color, dtype=np.float32),
        "darkColor": np.asarray(dark_color, dtype=np.float32),
        "geometryMasks": _geometry_masks(width, height),
        "geometryMasksBold": _geometry_masks(width, height, line_scale=6.5),
    }


def _mix_color(
    base: Any,
    color: Any,
    amount: Any,
    maximum_opacity: float = 0.50,
) -> Any:
    np = _numpy()
    maximum = max(0.0, min(1.0, float(maximum_opacity)))
    opacity = np.clip(amount, 0.0, maximum)[:, :, None]
    return base * (1.0 - opacity) + np.asarray(color, dtype=np.float32) * opacity


@lru_cache(maxsize=128)
def _font(font_path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(font_path, max(1, size))


def _stable_fraction(key: str) -> float:
    value = int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:8], 16)
    return value / 0xFFFFFFFF


def _polygon_mask(width: int, height: int, points: list[tuple[float, float]], feather: float = 0.0) -> Any:
    np = _numpy()
    scale = 4
    image = Image.new("L", (width * scale, height * scale), 0)
    draw = ImageDraw.Draw(image)
    draw.polygon(
        [(round(px * width * scale), round(py * height * scale)) for px, py in points],
        fill=255,
    )
    image = image.resize((width, height), Image.Resampling.LANCZOS)
    if feather > 0:
        image = image.filter(ImageFilter.GaussianBlur(radius=feather))
    return np.asarray(image, dtype=np.float32) / 255.0


def _number_field_mask(
    recipe: InfinityBackgroundRecipe,
    fraction: float,
    context: dict[str, Any],
    *,
    mode: str,
) -> Any:
    """Draw a deterministic, loop-safe field of individual single digits."""
    np = _numpy()
    height, width = context["alpha"].shape
    scale = 3
    image = Image.new("L", (width * scale, height * scale), 0)
    draw = ImageDraw.Draw(image)
    parameters = recipe.parameters
    count = int(parameters.get("digitCount", 24))
    minimum_size = float(parameters.get("minimumSize", 16.0))
    maximum_size = float(parameters.get("maximumSize", 92.0))
    vanish_x = float(parameters.get("vanishingX", 0.52))
    vanish_y = float(parameters.get("vanishingY", 0.48))
    font_path = str(context.get("fontPath", ""))
    if not font_path:
        raise ValueError(f"{recipe.id} requires a resolved fontPath in the background context")
    digits = "1234567890"
    for index in range(count):
        prefix = f"{recipe.id}:{index}"
        phase_offset = _stable_fraction(prefix + ":phase")
        travel = (fraction * recipe.speed + phase_offset) % 1.0
        depth = 0.5 - 0.5 * math.cos(2.0 * math.pi * travel)
        side = -1.0 if index % 2 == 0 else 1.0
        row = _stable_fraction(prefix + ":row")
        if mode == "depth":
            near_x = 0.05 + 0.90 * _stable_fraction(prefix + ":x")
            near_y = 0.04 + 0.92 * row
        elif mode == "sides":
            near_x = -0.10 if side < 0 else 1.10
            near_y = 0.02 + 0.96 * row
        else:
            # A curved corridor leaves breathing room around the central pose.
            near_x = 0.02 if side < 0 else 0.98
            near_y = 0.05 + 0.90 * row
            corridor = math.sin(math.pi * depth) * (0.09 + 0.05 * _stable_fraction(prefix + ":curve"))
            near_x += -corridor if side < 0 else corridor
        x = vanish_x * (1.0 - depth) + near_x * depth
        y = vanish_y * (1.0 - depth) + near_y * depth
        size = minimum_size + (maximum_size - minimum_size) * (depth ** 1.18)
        opacity = 40 + round(200 * (0.18 + 0.82 * depth) ** 1.25)
        digit = digits[index % len(digits)]
        typeface = _font(font_path, round(size * scale))
        bbox = draw.textbbox((0, 0), digit, font=typeface)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        draw.text(
            (round(x * width * scale - text_width / 2), round(y * height * scale - text_height / 2 - bbox[1])),
            digit,
            font=typeface,
            fill=max(0, min(255, opacity)),
        )
    image = image.resize((width, height), Image.Resampling.LANCZOS)
    return np.asarray(image, dtype=np.float32) / 255.0


def _flat_number_field_mask(
    recipe: InfinityBackgroundRecipe,
    fraction: float,
    context: dict[str, Any],
    *,
    mode: str,
) -> Any:
    """Draw a dense 2D field whose digit sizes never imply depth."""
    np = _numpy()
    height, width = context["alpha"].shape
    scale = 3
    image = Image.new("L", (width * scale, height * scale), 0)
    draw = ImageDraw.Draw(image)
    parameters = recipe.parameters
    number_seed = str(parameters.get("numberSeed", recipe.id))
    columns = int(parameters.get("columns", 9))
    rows = int(parameters.get("rows", 15))
    minimum_size = float(parameters.get("minimumSize", 24.0))
    maximum_size = float(parameters.get("maximumSize", minimum_size))
    opacity = int(parameters.get("opacity", 150))
    font_path = str(context.get("fontPath", ""))
    if not font_path:
        raise ValueError(f"{recipe.id} requires a resolved fontPath in the background context")
    digits = "1234567890"
    # A complete cycle is always closed inside the fixed 11-second duration.
    # ``speed`` scales the shared travel distance rather than allowing a
    # fractional cycle that would jump at the loop boundary.
    # Production may give each portrait a different deterministic starting
    # phase. The field keeps the selected speed and closed path, but a grid of
    # videos will not make every number field move in lockstep.
    phase_offset = float(parameters.get("phaseOffset", 0.0)) % 1.0
    cycle = 2.0 * math.pi * ((fraction + phase_offset) % 1.0)
    jitter_x = float(parameters.get("jitterX", 0.0))
    jitter_y = float(parameters.get("jitterY", 0.0))
    coordinated_motion = bool(parameters.get("coordinatedMotion", False))
    balanced_random_digits = bool(parameters.get("balancedRandomDigits", False))
    position_layout = str(parameters.get("positionLayout", "grid"))
    if position_layout not in {"grid", "random"}:
        raise ValueError(f"{recipe.id} has an unsupported positionLayout")
    bleed_edges = bool(parameters.get("bleedEdges", False))
    travel_x = float(parameters.get("travelX", 0.12)) * recipe.speed
    travel_y = float(parameters.get("travelY", 0.045)) * recipe.speed
    linear_travel = float(parameters.get("linearTravel", 0.22)) * recipe.speed
    for row in range(rows):
        for column in range(columns):
            index = row * columns + column
            prefix = f"{number_seed}:{index}"
            if position_layout == "random":
                base_x = _stable_fraction(prefix + ":random-x")
                base_y = _stable_fraction(prefix + ":random-y")
            elif bleed_edges:
                base_x = column / max(columns - 1, 1)
                base_y = row / max(rows - 1, 1)
            else:
                base_x = (column + 0.5) / columns
                base_y = (row + 0.5) / rows
            base_x += (_stable_fraction(prefix + ":jx") - 0.5) * jitter_x / columns
            base_y += (_stable_fraction(prefix + ":jy") - 0.5) * jitter_y / rows
            if mode == "varied":
                if jitter_x == 0.0:
                    base_x += (_stable_fraction(prefix + ":jx") - 0.5) * 0.55 / columns
                if jitter_y == 0.0:
                    base_y += (_stable_fraction(prefix + ":jy") - 0.5) * 0.55 / rows
                if coordinated_motion:
                    x = base_x + travel_x * math.sin(cycle)
                    y = base_y + travel_y * math.cos(cycle)
                else:
                    x = base_x + 0.075 * math.sin(
                        cycle + _stable_fraction(prefix + ":px") * 2.0 * math.pi
                    )
                    y = base_y + 0.035 * math.cos(
                        cycle + _stable_fraction(prefix + ":py") * 2.0 * math.pi
                    )
                size = minimum_size + (maximum_size - minimum_size) * _stable_fraction(prefix + ":size")
            elif mode == "uniform":
                x = base_x + travel_x * math.sin(cycle)
                y = base_y + travel_y * math.cos(cycle)
                size = minimum_size
            elif mode == "static":
                x = base_x
                y = base_y
                size = minimum_size
            elif mode in {"linear_left", "linear_right"}:
                direction = -1.0 if mode == "linear_left" else 1.0
                x = (base_x + direction * linear_travel * fraction) % 1.0
                y = base_y
                size = minimum_size
            else:
                separation = 0.18 * (0.5 - 0.5 * math.cos(cycle))
                x = base_x + (-separation if base_x < 0.5 else separation)
                y = base_y + 0.018 * math.sin(cycle)
                size = minimum_size + (maximum_size - minimum_size) * (
                    (row + column) % 5
                ) / 4.0
            if balanced_random_digits:
                block = index // len(digits)
                balanced_block = sorted(
                    digits,
                    key=lambda digit: _stable_fraction(
                        f"{number_seed}:digit-block:{block}:{digit}"
                    ),
                )
                digit = balanced_block[index % len(digits)]
            else:
                digit = digits[
                    (index + int(parameters.get("digitOffset", 0))) % len(digits)
                ]
            typeface = _font(font_path, round(size * scale))
            bbox = draw.textbbox((0, 0), digit, font=typeface)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            draw.text(
                (
                    round(x * width * scale - text_width / 2),
                    round(y * height * scale - text_height / 2 - bbox[1]),
                ),
                digit,
                font=typeface,
                fill=max(0, min(255, opacity)),
            )
    image = image.resize((width, height), Image.Resampling.LANCZOS)
    return np.asarray(image, dtype=np.float32) / 255.0


def _looping_blob_field_mask(
    recipe: InfinityBackgroundRecipe,
    fraction: float,
    context: dict[str, Any],
) -> Any:
    """Build deterministic organic blobs whose paths and shapes close exactly."""
    np = _numpy()
    parameters = recipe.parameters
    blob_count = int(parameters.get("blobCount", 1))
    if not 1 <= blob_count <= 3:
        raise ValueError(f"{recipe.id} blobCount must be between 1 and 3")
    blob_seed = str(parameters.get("blobSeed", recipe.id))
    feather = max(0.04, float(parameters.get("blobFeather", 0.18)))
    x = context["x"]
    y = context["y"]
    cycle = 2.0 * math.pi * (fraction % 1.0)
    combined = np.zeros_like(x, dtype=np.float32)
    for index in range(blob_count):
        prefix = f"{blob_seed}:{index}"
        radius_x = 0.14 + 0.07 * _stable_fraction(prefix + ":radius-x")
        radius_y = 0.12 + 0.08 * _stable_fraction(prefix + ":radius-y")
        amplitude_x = 0.07 + 0.07 * _stable_fraction(prefix + ":amplitude-x")
        amplitude_y = 0.05 + 0.07 * _stable_fraction(prefix + ":amplitude-y")
        base_x = 0.30 + 0.40 * _stable_fraction(prefix + ":base-x")
        base_y = 0.25 + 0.50 * _stable_fraction(prefix + ":base-y")
        phase_x = 2.0 * math.pi * _stable_fraction(prefix + ":phase-x")
        phase_y = 2.0 * math.pi * _stable_fraction(prefix + ":phase-y")
        frequency_x = 1 + int(_stable_fraction(prefix + ":frequency-x") * 2)
        frequency_y = 1 + int(_stable_fraction(prefix + ":frequency-y") * 2)
        center_x = base_x + amplitude_x * math.sin(frequency_x * cycle + phase_x)
        center_y = base_y + amplitude_y * math.cos(frequency_y * cycle + phase_y)
        rotation = (
            2.0 * math.pi * _stable_fraction(prefix + ":rotation")
            + 0.24 * math.sin(cycle + phase_y)
        )
        cosine = math.cos(rotation)
        sine = math.sin(rotation)
        delta_x = x - center_x
        delta_y = y - center_y
        rotated_x = delta_x * cosine + delta_y * sine
        rotated_y = -delta_x * sine + delta_y * cosine
        normalized_x = rotated_x / radius_x
        normalized_y = rotated_y / radius_y
        radius = np.sqrt(normalized_x**2 + normalized_y**2)
        angle = np.arctan2(normalized_y, normalized_x)
        shape_phase = 2.0 * math.pi * _stable_fraction(prefix + ":shape")
        boundary = (
            1.0
            + 0.13 * np.sin(3.0 * angle + shape_phase + cycle)
            + 0.07 * np.sin(5.0 * angle - shape_phase - 2.0 * cycle)
        )
        distance = radius / np.maximum(boundary, 0.72)
        exponent = np.clip((distance - 1.0) / feather, -60.0, 60.0)
        blob = 1.0 / (1.0 + np.exp(exponent))
        combined = 1.0 - (1.0 - combined) * (1.0 - blob)
    return np.asarray(np.clip(combined, 0.0, 1.0), dtype=np.float32)


def background_visibility_metrics(pixels: Any, base: Any) -> dict[str, float]:
    """Measure effect visibility in familiar 8-bit display-code distances."""
    np = _numpy()
    delta = np.abs(
        np.asarray(pixels, dtype=np.float32) - np.asarray(base, dtype=np.float32)
    ) / 257.0
    pixel_delta = delta.mean(axis=2)
    return {
        "meanDelta8Bit": round(float(delta.mean()), 3),
        "p95Delta8Bit": round(float(np.percentile(delta, 95)), 3),
        "activePixelsAbove3Percent": round(
            float(np.mean(pixel_delta > 3.0) * 100.0), 3
        ),
    }


def require_perceptual_visibility(
    recipe: InfinityBackgroundRecipe,
    metrics: dict[str, float],
) -> None:
    failures = [
        f"{key} {metrics[key]:.3f} < {minimum:.3f}"
        for key, minimum in recipe.perceptual_floor.items()
        if metrics[key] < minimum
    ]
    if failures:
        raise ValueError(
            f"{recipe.id} failed perceptual visibility: " + "; ".join(failures)
        )


def background_effect_frame(
    recipe: InfinityBackgroundRecipe,
    fraction: float,
    context: dict[str, Any],
) -> Any:
    np = _numpy()
    base = context["background"]
    x = context["x"]
    y = context["y"]
    envelope = math.sin(math.pi * max(0.0, min(1.0, fraction))) ** 2
    phase = 2.0 * math.pi * fraction * recipe.speed
    strength = recipe.strength * envelope
    boost = recipe.visibility_boost
    emphasis = min(1.0, max(0.0, boost - 1.0))
    restrained_warm = context["skinColor"] * 0.42 + np.asarray(
        [0.88, 0.86, 0.82], dtype=np.float32
    ) * 0.58
    assertive_warm = context["skinColor"] * 0.52 + np.asarray(
        [0.72, 0.66, 0.58], dtype=np.float32
    ) * 0.48
    warm_neutral = restrained_warm * (1.0 - emphasis) + assertive_warm * emphasis
    restrained_dark = context["darkColor"] * 0.30 + np.asarray(
        [0.50, 0.49, 0.47], dtype=np.float32
    ) * 0.70
    assertive_dark = context["darkColor"] * 0.48 + np.asarray(
        [0.24, 0.24, 0.26], dtype=np.float32
    ) * 0.52
    quiet_dark = restrained_dark * (1.0 - emphasis) + assertive_dark * emphasis

    if recipe.effect == "momentum_wake":
        field = _oriented_gaussian(
            x,
            y,
            center_x=0.34 + 0.035 * boost * math.sin(phase),
            center_y=0.50 + 0.025 * boost * math.cos(phase),
            radius_x=0.48 * min(boost, 1.40),
            radius_y=0.17 * min(boost, 1.75),
            angle=-0.42,
        )
        frame = _mix_color(base, warm_neutral, field * strength)
    elif recipe.effect == "emulsion_bloom":
        field = np.zeros_like(x)
        for center_x, center_y, radius_x, radius_y, offset, weight in (
            (0.18, 0.20, 0.28, 0.18, 0.0, 0.80),
            (0.72, 0.35, 0.34, 0.23, 1.7, 0.62),
            (0.36, 0.72, 0.38, 0.25, 3.2, 0.58),
            (0.86, 0.82, 0.25, 0.20, 4.6, 0.48),
        ):
            field += weight * _oriented_gaussian(
                x,
                y,
                center_x=center_x + 0.025 * boost * math.sin(phase + offset),
                center_y=center_y + 0.020 * boost * math.cos(phase * 0.9 + offset),
                radius_x=radius_x * min(boost, 1.35),
                radius_y=radius_y * min(boost, 1.35),
                angle=0.2 * math.sin(offset),
            )
        field /= max(float(field.max()), 1e-6)
        frame = _mix_color(base, warm_neutral * 0.92, field * strength)
    elif recipe.effect == "floating_print":
        dx = int(round((7 + 3 * math.sin(phase)) * boost))
        dy = int(round((10 + 2 * math.cos(phase)) * boost))
        shadow_source = (
            context["alphaShadowBold"] if boost > 1.2 else context["alphaSoft"]
        )
        shadow = _shift_mask(shadow_source, dx, dy)
        frame = _mix_color(base, quiet_dark, shadow * strength)
    elif recipe.effect == "negative_space_aperture":
        aperture = _oriented_gaussian(
            x,
            y,
            center_x=0.64 + 0.08 * math.sin(phase),
            center_y=0.27 + 0.05 * math.cos(phase),
            radius_x=0.42,
            radius_y=0.30,
            angle=-0.18,
        )
        outer_density = np.clip(1.0 - aperture, 0.0, 1.0)
        frame = _mix_color(base, quiet_dark * 0.82 + warm_neutral * 0.18, outer_density * strength)
    elif recipe.effect == "residual_gesture":
        ghost_source = (
            context["alphaGhostBold"] if boost > 1.2 else context["alphaGhost"]
        )
        ghost_a = _shift_mask(
            ghost_source,
            int(round((-15 - 3 * math.sin(phase)) * boost)),
            int(round((3 + 2 * math.cos(phase)) * boost)),
        )
        ghost_b = _shift_mask(
            ghost_source,
            int(round((12 + 2 * math.cos(phase)) * boost)),
            int(round((-5 + 2 * math.sin(phase)) * boost)),
        )
        ghost = np.clip(ghost_a * 0.70 + ghost_b * 0.35, 0.0, 1.0)
        frame = _mix_color(base, warm_neutral * 0.72 + quiet_dark * 0.28, ghost * strength)
    elif recipe.effect == "incomplete_geometry":
        masks = (
            context["geometryMasksBold"]
            if boost > 1.2
            else context["geometryMasks"]
        )
        weights = [
            max(0.0, math.sin(math.pi * fraction + offset)) ** 2
            for offset in (0.0, 0.65, 1.25)
        ]
        geometry = np.clip(
            masks[0] * weights[0] + masks[1] * weights[1] + masks[2] * weights[2],
            0.0,
            1.0,
        )
        frame = _mix_color(base, quiet_dark, geometry * strength)
    elif recipe.effect == "borrowed_color_field":
        skin_field = _oriented_gaussian(
            x,
            y,
            center_x=0.27 + 0.04 * math.sin(phase),
            center_y=0.30 + 0.03 * math.cos(phase),
            radius_x=0.42 * min(boost, 1.30),
            radius_y=0.27 * min(boost, 1.30),
            angle=0.28,
        )
        dark_field = _oriented_gaussian(
            x,
            y,
            center_x=0.72 + 0.035 * math.cos(phase),
            center_y=0.73 + 0.025 * math.sin(phase),
            radius_x=0.46 * min(boost, 1.30),
            radius_y=0.30 * min(boost, 1.30),
            angle=-0.22,
        )
        frame = _mix_color(base, context["skinColor"], skin_field * strength * 0.72)
        frame = _mix_color(frame, context["darkColor"] * 0.55 + base.mean(axis=(0, 1)) * 0.45, dark_field * strength * 0.48)
    elif recipe.effect in {
        "number_depth_field",
        "number_side_streams",
        "number_evasive_corridor",
    }:
        number_mode = {
            "number_depth_field": "depth",
            "number_side_streams": "sides",
            "number_evasive_corridor": "corridor",
        }[recipe.effect]
        numbers = _number_field_mask(recipe, fraction, context, mode=number_mode)
        number_color = np.asarray(recipe.parameters.get("color", [0.46, 0.45, 0.43]), dtype=np.float32)
        frame = _mix_color(base, number_color, numbers * recipe.strength * recipe.visibility_boost)
    elif recipe.effect == "gradient_curtain":
        center = -0.20 + 1.40 * (0.5 - 0.5 * math.cos(2.0 * math.pi * fraction))
        width_scale = float(recipe.parameters.get("bandWidth", 0.34))
        leading = np.exp(-0.5 * ((x - center) / width_scale) ** 2)
        trailing = np.exp(-0.5 * ((x - (center - 0.32)) / (width_scale * 1.4)) ** 2)
        curtain = np.clip(leading * 0.9 + trailing * 0.42, 0.0, 1.0)
        curtain_color = np.asarray(recipe.parameters.get("color", [0.73, 0.70, 0.65]), dtype=np.float32)
        frame = _mix_color(base, curtain_color, curtain * recipe.strength * recipe.visibility_boost)
    elif recipe.effect == "sliding_panel":
        travel = 0.5 - 0.5 * math.cos(2.0 * math.pi * fraction)
        edge = -0.08 + 0.86 * travel
        feather = float(recipe.parameters.get("feather", 0.015))
        exponent = np.clip((x - edge) / max(feather, 0.003), -60.0, 60.0)
        panel = 1.0 / (1.0 + np.exp(exponent))
        panel_color = np.asarray(recipe.parameters.get("color", [0.78, 0.76, 0.72]), dtype=np.float32)
        frame = _mix_color(base, panel_color, panel * recipe.strength * recipe.visibility_boost)
    elif recipe.effect == "hinged_door":
        openness = 0.5 - 0.5 * math.cos(2.0 * math.pi * fraction)
        far_x = 1.04 - 0.56 * openness
        inset = 0.42 * openness
        door = _polygon_mask(
            base.shape[1],
            base.shape[0],
            [(0.0, 0.0), (far_x, inset), (far_x, 1.0 - inset), (0.0, 1.0)],
            feather=float(recipe.parameters.get("featherPixels", 0.7)),
        )
        door_color = np.asarray(recipe.parameters.get("color", [0.76, 0.74, 0.70]), dtype=np.float32)
        frame = _mix_color(base, door_color, door * recipe.strength * recipe.visibility_boost)
    elif recipe.effect == "number_doorway":
        openness = 0.5 - 0.5 * math.cos(2.0 * math.pi * fraction)
        numbers = _number_field_mask(recipe, fraction, context, mode="depth")
        number_color = np.asarray(recipe.parameters.get("numberColor", [0.43, 0.42, 0.40]), dtype=np.float32)
        frame = _mix_color(base, number_color, numbers * recipe.strength * 1.15)
        left_edge = 0.50 - 0.40 * openness
        right_edge = 0.50 + 0.40 * openness
        inset = 0.18 * openness
        left = _polygon_mask(
            base.shape[1], base.shape[0],
            [(0.0, 0.0), (left_edge, inset), (left_edge, 1.0 - inset), (0.0, 1.0)],
            feather=0.6,
        )
        right = _polygon_mask(
            base.shape[1], base.shape[0],
            [(right_edge, inset), (1.0, 0.0), (1.0, 1.0), (right_edge, 1.0 - inset)],
            feather=0.6,
        )
        doors = np.clip(left + right, 0.0, 1.0)
        door_color = np.asarray(recipe.parameters.get("doorColor", [0.82, 0.80, 0.76]), dtype=np.float32)
        frame = _mix_color(frame, door_color, doors * recipe.strength * recipe.visibility_boost)
    elif recipe.effect in {
        "flat_number_drift",
        "flat_number_grid",
        "flat_number_separation",
    }:
        flat_mode = str(recipe.parameters.get("numberMotion") or {
            "flat_number_drift": "varied",
            "flat_number_grid": "uniform",
            "flat_number_separation": "separation",
        }[recipe.effect])
        if flat_mode not in {"varied", "uniform", "static", "separation"}:
            raise ValueError(f"{recipe.id} has an unsupported numberMotion")
        numbers = _flat_number_field_mask(recipe, fraction, context, mode=flat_mode)
        number_color = np.asarray(
            recipe.parameters.get("color", [0.48, 0.47, 0.45]),
            dtype=np.float32,
        )
        number_base = base
        if "backgroundColor" in recipe.parameters:
            background_color = np.asarray(
                recipe.parameters["backgroundColor"], dtype=np.float32
            )
            number_base = np.broadcast_to(background_color, base.shape).copy()
        frame = _mix_color(
            number_base,
            number_color,
            numbers * recipe.strength * recipe.visibility_boost,
            maximum_opacity=float(recipe.parameters.get("maximumMix", 0.50)),
        )
    elif recipe.effect == "flat_number_blobs":
        number_motion = str(recipe.parameters.get("numberMotion", "uniform"))
        if number_motion not in {"uniform", "static"}:
            raise ValueError(f"{recipe.id} has an unsupported numberMotion")
        numbers = _flat_number_field_mask(
            recipe,
            fraction,
            context,
            mode=number_motion,
        )
        blobs = _looping_blob_field_mask(recipe, fraction, context)
        background_color = np.asarray(
            recipe.parameters.get("backgroundColor", [0.97, 0.96, 0.94]),
            dtype=np.float32,
        )
        number_color = np.asarray(
            recipe.parameters.get("numberColor", [0.93, 0.92, 0.89]),
            dtype=np.float32,
        )
        blob_color = np.asarray(
            recipe.parameters.get("blobColor", number_color),
            dtype=np.float32,
        )
        frame = np.broadcast_to(background_color, base.shape).copy()
        frame = _mix_color(
            frame,
            blob_color,
            blobs * float(recipe.parameters.get("blobOpacity", 0.72)),
            maximum_opacity=float(recipe.parameters.get("blobMaximumMix", 0.72)),
        )
        frame = _mix_color(
            frame,
            number_color,
            numbers * recipe.strength * recipe.visibility_boost,
            maximum_opacity=float(recipe.parameters.get("maximumMix", 1.0)),
        )
    elif recipe.effect == "gradient_curtain_2d":
        travel = 0.5 - 0.5 * math.cos(2.0 * math.pi * fraction)
        angle = math.radians(float(recipe.parameters.get("angleDegrees", 0.0)))
        direction_x = math.cos(angle)
        direction_y = math.sin(angle)
        projected = x * direction_x + y * direction_y
        corner_values = (
            0.0,
            direction_x,
            direction_y,
            direction_x + direction_y,
        )
        minimum_projection = min(corner_values)
        projection_range = max(corner_values) - minimum_projection
        coordinate = (projected - minimum_projection) / max(projection_range, 1e-6)
        if bool(recipe.parameters.get("reverseTravel", False)):
            center = -0.18 + 1.36 * travel
        else:
            center = 1.18 - 1.36 * travel
        band_width = float(recipe.parameters.get("bandWidth", 0.24))
        band = np.exp(-0.5 * ((coordinate - center) / band_width) ** 2)
        shoulder = np.exp(
            -0.5 * ((coordinate - (center + 0.30)) / (band_width * 1.7)) ** 2
        )
        color_a = np.asarray(
            recipe.parameters.get("colorA", [0.69, 0.67, 0.63]),
            dtype=np.float32,
        )
        color_b = np.asarray(
            recipe.parameters.get("colorB", [0.86, 0.83, 0.78]),
            dtype=np.float32,
        )
        curtain_base = base
        if "backgroundColor" in recipe.parameters:
            background_color = np.asarray(
                recipe.parameters["backgroundColor"], dtype=np.float32
            )
            curtain_base = np.broadcast_to(background_color, base.shape).copy()
        frame = _mix_color(
            curtain_base,
            color_b,
            shoulder * recipe.strength * recipe.visibility_boost * 0.72,
        )
        frame = _mix_color(
            frame,
            color_a,
            band * recipe.strength * recipe.visibility_boost,
        )
    elif recipe.effect == "sliding_panel_full":
        if bool(recipe.parameters.get("oneWay", False)):
            easing_exponent = float(recipe.parameters.get("easingExponent", 1.0))
            travel = max(0.0, min(1.0, fraction)) ** easing_exponent
        else:
            travel = math.sin(math.pi * fraction) ** 2
        edge = 1.08 - 1.16 * travel
        feather = float(recipe.parameters.get("feather", 0.010))
        exponent = np.clip((edge - x) / max(feather, 0.003), -60.0, 60.0)
        panel = 1.0 / (1.0 + np.exp(exponent))
        panel_color = np.asarray(
            recipe.parameters.get("color", [0.77, 0.75, 0.71]),
            dtype=np.float32,
        )
        panel_base = base
        if "backgroundColor" in recipe.parameters:
            background_color = np.asarray(
                recipe.parameters["backgroundColor"], dtype=np.float32
            )
            panel_base = np.broadcast_to(background_color, base.shape).copy()
        frame = _mix_color(
            panel_base,
            panel_color,
            panel * recipe.strength * recipe.visibility_boost,
            maximum_opacity=float(recipe.parameters.get("maximumMix", 0.50)),
        )
    elif recipe.effect == "hinged_door_one_way":
        easing_exponent = float(recipe.parameters.get("easingExponent", 1.0))
        openness = min(1.0, max(0.0, fraction * recipe.speed)) ** easing_exponent
        far_x = 1.04 - 1.01 * openness
        inset = 0.485 * openness
        door = _polygon_mask(
            base.shape[1],
            base.shape[0],
            [(0.0, 0.0), (far_x, inset), (far_x, 1.0 - inset), (0.0, 1.0)],
            feather=float(recipe.parameters.get("featherPixels", 0.6)),
        )
        door_color = np.asarray(
            recipe.parameters.get("color", [0.75, 0.73, 0.69]),
            dtype=np.float32,
        )
        door_base = base
        if "backgroundColor" in recipe.parameters:
            background_color = np.asarray(
                recipe.parameters["backgroundColor"], dtype=np.float32
            )
            door_base = np.broadcast_to(background_color, base.shape).copy()
        frame = _mix_color(
            door_base,
            door_color,
            door * recipe.strength * recipe.visibility_boost,
        )
    elif recipe.effect == "flat_number_wipe":
        number_motion = str(recipe.parameters.get("numberMotion", "varied"))
        if number_motion not in {"varied", "uniform", "static", "linear_left", "linear_right"}:
            raise ValueError(f"{recipe.id} has an unsupported numberMotion")
        numbers = _flat_number_field_mask(
            recipe, fraction, context, mode=number_motion
        )
        number_color = np.asarray(
            recipe.parameters.get("numberColor", [0.55, 0.54, 0.52]),
            dtype=np.float32,
        )
        wipe_base = base
        if "backgroundColor" in recipe.parameters:
            background_color = np.asarray(
                recipe.parameters["backgroundColor"], dtype=np.float32
            )
            wipe_base = np.broadcast_to(background_color, base.shape).copy()
        frame = _mix_color(
            wipe_base,
            number_color,
            numbers * recipe.strength * recipe.visibility_boost,
        )
        wipe_easing_exponent = float(
            recipe.parameters.get("wipeEasingExponent", 1.0)
        )
        wipe_progress = max(0.0, min(1.0, fraction)) ** wipe_easing_exponent
        edge = 1.06 - 1.12 * wipe_progress
        feather = float(recipe.parameters.get("feather", 0.010))
        exponent = np.clip((edge - x) / max(feather, 0.003), -60.0, 60.0)
        panel = 1.0 / (1.0 + np.exp(exponent))
        panel_color = np.asarray(
            recipe.parameters.get("panelColor", [0.55, 0.54, 0.52]),
            dtype=np.float32,
        )
        frame = frame * (1.0 - panel[:, :, None]) + panel_color * panel[:, :, None]
    else:  # pragma: no cover - configuration validation prevents this
        raise ValueError(recipe.effect)

    return np.rint(np.clip(frame, 0.0, 1.0) * 65535.0).astype("<u2")


def render_background_intermediate(
    *,
    recipe: InfinityBackgroundRecipe,
    context: dict[str, Any],
    frames: int,
    fps: int,
    output: Path,
    ffmpeg: str,
) -> dict[str, Any]:
    np = _numpy()
    output.parent.mkdir(parents=True, exist_ok=True)
    height, width = context["alpha"].shape
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
        "-framerate",
        str(fps),
        "-i",
        "pipe:0",
        "-frames:v",
        str(frames),
        "-an",
        "-c:v",
        "ffv1",
        "-level",
        "3",
        "-pix_fmt",
        "gbrp16le",
        "-color_primaries",
        "bt709",
        "-color_trc",
        "bt709",
        "-colorspace",
        "bt709",
        str(output),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    if process.stdin is None:  # pragma: no cover - defensive
        process.kill()
        raise RuntimeError("Background frame pipe was unavailable")
    first_bytes: bytes | None = None
    last_bytes: bytes | None = None
    timeline = []
    base = np.asarray(context["background"] * 65535.0, dtype=np.float32)
    base_u16 = np.rint(base).astype("<u2")
    peak_pixels = base_u16
    peak_mean_delta = -1.0
    try:
        for frame_index in range(frames):
            fraction = frame_index / max(frames - 1, 1)
            pixels = background_effect_frame(recipe, fraction, context)
            if (
                recipe.loop_behavior == "continuous"
                and frame_index == frames - 1
                and first_bytes is not None
            ):
                frame_bytes = first_bytes
                pixels = np.frombuffer(frame_bytes, dtype="<u2").reshape(height, width, 3)
            else:
                frame_bytes = pixels.tobytes()
            if first_bytes is None:
                first_bytes = frame_bytes
            last_bytes = frame_bytes
            process.stdin.write(frame_bytes)
            mean_delta = float(
                np.abs(pixels.astype(np.float32) - base).mean() / 65535.0
            )
            if mean_delta > peak_mean_delta:
                peak_mean_delta = mean_delta
                peak_pixels = pixels.copy()
            timeline.append(
                {
                    "frame": frame_index,
                    "timeFraction": round(fraction, 6),
                    "meanAbsoluteBackgroundDelta": round(mean_delta, 6),
                }
            )
        process.stdin.close()
        return_code = process.wait()
    except BaseException:
        process.kill()
        process.wait()
        raise
    if return_code:
        raise subprocess.CalledProcessError(return_code, command)
    first_last_identical = first_bytes == last_bytes
    if recipe.loop_behavior == "continuous" and not first_last_identical:
        raise AssertionError(f"{recipe.id} background does not close exactly")
    perceptual_visibility = background_visibility_metrics(peak_pixels, base_u16)
    require_perceptual_visibility(recipe, perceptual_visibility)
    return {
        "firstLastBackgroundIdentical": first_last_identical,
        "loopBehavior": recipe.loop_behavior,
        "backgroundFrameSha256": hashlib.sha256(first_bytes or b"").hexdigest(),
        "perceptualVisibility": perceptual_visibility,
        "perceptualMinimums": recipe.perceptual_floor,
        "frameTimeline": timeline,
    }


def build_infinity_background_filter(
    video_config: Config,
    mask_width: int,
    mask_height: int,
) -> str:
    render_width = video_config.width * 2
    render_height = video_config.height * 2
    return (
        f"[0:v]scale={render_width}:{render_height}:force_original_aspect_ratio=increase,"
        f"crop={render_width}:{render_height},format=gbrp16le[subjectFinal];"
        f"[1:v]scale={render_width}:{render_height}:force_original_aspect_ratio=increase,"
        f"crop={render_width}:{render_height},format=gbrp16le[subjectUnder];"
        f"[2:v]scale={render_width}:{render_height}:flags=bicubic,format=gray16le[developmentMask];"
        f"[subjectUnder][subjectFinal][developmentMask]maskedmerge[developedSubject];"
        f"[3:v]scale={render_width}:{render_height}:flags=lanczos,format=gbrp16le[animatedBackground];"
        f"[4:v]scale={render_width}:{render_height}:force_original_aspect_ratio=increase,"
        f"crop={render_width}:{render_height},format=rgba64le,alphaextract,"
        f"format=gray16le[subjectAlpha];"
        f"[animatedBackground][developedSubject][subjectAlpha]maskedmerge,"
        f"scale={video_config.width}:{video_config.height}:flags=lanczos,"
        f"fps={video_config.fps},format={video_config.pixel_format},"
        f"setparams=range=limited:color_primaries=bt709:color_trc=bt709:colorspace=bt709[out]"
    )


def render_composite_candidate(
    *,
    video_config: Config,
    subject_finished: Path,
    subject_under_resolved: Path,
    subject_rgba: Path,
    background_intermediate: Path,
    masks: list[bytes],
    mask_width: int,
    mask_height: int,
    output: Path,
    ffmpeg: str,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    frames = len(masks)
    filter_graph = build_infinity_background_filter(
        video_config, mask_width, mask_height
    )
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-framerate",
        str(video_config.fps),
        "-loop",
        "1",
        "-i",
        str(subject_finished),
        "-framerate",
        str(video_config.fps),
        "-loop",
        "1",
        "-i",
        str(subject_under_resolved),
        "-f",
        "rawvideo",
        "-pixel_format",
        "gray",
        "-video_size",
        f"{mask_width}x{mask_height}",
        "-framerate",
        str(video_config.fps),
        "-i",
        "pipe:0",
        "-i",
        str(background_intermediate),
        "-framerate",
        str(video_config.fps),
        "-loop",
        "1",
        "-i",
        str(subject_rgba),
        "-filter_complex",
        filter_graph,
        "-map",
        "[out]",
        "-frames:v",
        str(frames),
        "-an",
        "-c:v",
        video_config.codec,
        "-crf",
        "18",
        "-preset",
        "medium",
        "-color_primaries",
        "bt709",
        "-color_trc",
        "bt709",
        "-colorspace",
        "bt709",
        "-color_range",
        "tv",
        "-movflags",
        "+faststart",
        str(output),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    if process.stdin is None:  # pragma: no cover - defensive
        process.kill()
        raise RuntimeError("Development mask pipe was unavailable")
    try:
        for mask in masks:
            process.stdin.write(mask)
        process.stdin.close()
        return_code = process.wait()
    except BaseException:
        process.kill()
        process.wait()
        raise
    if return_code:
        raise subprocess.CalledProcessError(return_code, command)


def development_state(
    *,
    recipe: DevelopmentRecipe,
    development_config: DevelopmentConfig,
    seed: int,
    frames: int,
    focal_point: tuple[float, float],
) -> tuple[list[bytes], list[dict[str, Any]], dict[str, Any]]:
    mask_width = int(development_config.mask["width"])
    mask_height = int(development_config.mask["height"])
    masks, timeline = development_mask_frames(
        recipe,
        seed=seed,
        frames=frames,
        width=mask_width,
        height=mask_height,
        focal_point=focal_point,
        mask_settings=development_config.mask,
    )
    digest = hashlib.sha256()
    for mask in masks:
        digest.update(mask)
    field = {
        "maskWidth": mask_width,
        "maskHeight": mask_height,
        "focalPoint": {"x": round(focal_point[0], 6), "y": round(focal_point[1], 6)},
        "backgroundInfluence": development_config.mask["backgroundInfluence"],
        "baseFinalMix": recipe.base_final_mix,
        "patchCount": recipe.patch_count,
        "patchSizeRange": [recipe.patch_size_min, recipe.patch_size_max],
        "feather": recipe.feather,
        "neighborCoupling": recipe.neighbor_coupling,
        "speed": recipe.speed,
        "direction": recipe.direction,
        "finishedHold": recipe.finished_hold,
        "easePower": recipe.ease_power,
        "algorithm": "seeded periodic broad field",
        "maskStreamSha256": digest.hexdigest(),
        "firstLastMaskIdentical": masks[0] == masks[-1],
    }
    return masks, timeline, field
