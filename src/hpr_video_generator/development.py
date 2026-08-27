from __future__ import annotations

from dataclasses import dataclass
import hashlib
import io
import json
import math
from pathlib import Path
import random
import subprocess
from typing import Any

try:
    from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps, ImageStat
except ImportError as error:  # pragma: no cover - exercised only without render extra
    raise SystemExit(
        "Pillow is required for portrait-development rendering. "
        "Install hpr-video-generator[render]."
    ) from error

from .config import Config
from .color_pipeline import (
    png_bit_depth,
    read_tiff_rgb16,
    srgb_profile_bytes,
    transform_rgb16,
    under_resolved_rgb16,
    write_rgb16_png,
)
from .generator import find_ffmpeg


MODES = {"static_reference", "global_development", "activation_field", "soft_sweep"}


@dataclass(frozen=True)
class DevelopmentRecipe:
    id: str
    name: str
    mode: str
    base_final_mix: float
    patch_count: int
    patch_size_min: float
    patch_size_max: float
    feather: float
    neighbor_coupling: float
    speed: float
    direction: tuple[float, float]
    finished_hold: float = 0.0
    ease_power: float = 1.0


@dataclass(frozen=True)
class DevelopmentConfig:
    version: str
    experiment_id: str
    mask: dict[str, Any]
    surrogate: dict[str, Any]
    recipes: dict[str, DevelopmentRecipe]


@dataclass(frozen=True)
class DevelopmentCandidate:
    portrait_id: str
    revision_id: str
    portrait: Path
    recipe: DevelopmentRecipe
    seed: int
    duration_sec: int
    output: Path


@dataclass(frozen=True)
class FieldPatch:
    x: float
    y: float
    radius: float
    aspect: float
    phase: float
    drift_x: float
    drift_y: float
    neighbor_angle: float


def load_development_config(path: Path) -> DevelopmentConfig:
    payload = json.loads(path.read_text(encoding="utf-8"))
    recipes: dict[str, DevelopmentRecipe] = {}
    for raw in payload.get("recipes", []):
        recipe = DevelopmentRecipe(
            id=raw["id"],
            name=raw["name"],
            mode=raw["mode"],
            base_final_mix=float(raw["baseFinalMix"]),
            patch_count=int(raw["patchCount"]),
            patch_size_min=float(raw["patchSizeMin"]),
            patch_size_max=float(raw["patchSizeMax"]),
            feather=float(raw["feather"]),
            neighbor_coupling=float(raw["neighborCoupling"]),
            speed=float(raw["speed"]),
            direction=tuple(float(value) for value in raw["direction"]),
            finished_hold=float(raw.get("finishedHold", 0.0)),
            ease_power=float(raw.get("easePower", 1.0)),
        )
        validate_development_recipe(recipe)
        if recipe.id in recipes:
            raise ValueError(f"Duplicate development recipe: {recipe.id}")
        recipes[recipe.id] = recipe
    if not recipes:
        raise ValueError("Portrait-development configuration requires recipes")
    mask = payload["mask"]
    if int(mask["width"]) < 16 or int(mask["height"]) < 16:
        raise ValueError("Development mask dimensions are too small")
    return DevelopmentConfig(
        version=payload["version"],
        experiment_id=payload["experimentId"],
        mask=mask,
        surrogate=payload["surrogate"],
        recipes=recipes,
    )


def validate_development_recipe(recipe: DevelopmentRecipe) -> None:
    if recipe.mode not in MODES:
        raise ValueError(f"{recipe.id} has an unsupported mode: {recipe.mode}")
    if not 0 <= recipe.base_final_mix <= 1:
        raise ValueError(f"{recipe.id} base final mix must be between 0 and 1")
    if recipe.patch_count < 0:
        raise ValueError(f"{recipe.id} patch count cannot be negative")
    if not 0 <= recipe.patch_size_min <= recipe.patch_size_max <= 1:
        raise ValueError(f"{recipe.id} patch-size range is invalid")
    if not 0 <= recipe.feather <= 2:
        raise ValueError(f"{recipe.id} feather is invalid")
    if not 0 <= recipe.neighbor_coupling <= 1:
        raise ValueError(f"{recipe.id} neighbor coupling is invalid")
    if recipe.speed < 0:
        raise ValueError(f"{recipe.id} speed cannot be negative")
    if len(recipe.direction) != 2:
        raise ValueError(f"{recipe.id} requires a two-value direction")
    if not 0 <= recipe.finished_hold < 1:
        raise ValueError(f"{recipe.id} finished hold must be between 0 and 1")
    if not 0.25 <= recipe.ease_power <= 4:
        raise ValueError(f"{recipe.id} ease power is invalid")
    if recipe.mode == "activation_field" and recipe.patch_count < 1:
        raise ValueError(f"{recipe.id} activation field requires patches")
    if recipe.mode == "static_reference" and not math.isclose(
        recipe.base_final_mix, 1.0
    ):
        raise ValueError(f"{recipe.id} static reference must be the finished portrait")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalized_portrait(path: Path) -> tuple[Image.Image, bytes | None]:
    with Image.open(path) as opened:
        icc_profile = opened.info.get("icc_profile")
        return ImageOps.exif_transpose(opened).convert("RGB"), icc_profile


def _tone_lut(settings: dict[str, Any]) -> list[int]:
    values = []
    for channel_value in range(256):
        value = channel_value / 255.0
        black = float(settings["blackLift"]) * ((1.0 - value) ** 10)
        shadows = float(settings["shadowSuppression"]) * math.exp(
            -((value - float(settings["shadowCenter"])) / float(settings["shadowWidth"]))
            ** 2
        )
        highlights = float(settings["highlightVeil"]) * math.exp(
            -(
                (value - float(settings["highlightCenter"]))
                / float(settings["highlightWidth"])
            )
            ** 2
        )
        transformed = max(0.0, min(1.0, value + black - shadows + highlights))
        values.append(round(transformed * 255))
    return values


def prepare_source_pair(
    portrait: Path,
    normalized_final: Path,
    surrogate: Path,
    settings: dict[str, Any],
    *,
    ffmpeg: str | None = None,
) -> dict[str, Any]:
    if portrait.suffix.lower() in {".tif", ".tiff"}:
        encoder = ffmpeg or find_ffmpeg()
        source_pixels, source_profile, source_info = read_tiff_rgb16(
            portrait, encoder
        )
        working_profile = srgb_profile_bytes()
        final_pixels = transform_rgb16(
            source_pixels, source_profile, working_profile
        )
        surrogate_pixels = under_resolved_rgb16(final_pixels, settings)
        write_rgb16_png(final_pixels, normalized_final, encoder, working_profile)
        write_rgb16_png(surrogate_pixels, surrogate, encoder, working_profile)
        if png_bit_depth(normalized_final) != 16 or png_bit_depth(surrogate) != 16:
            raise AssertionError("TIFF source pair was not preserved as 16-bit PNG")
        return {
            "sourceWidth": int(source_pixels.shape[1]),
            "sourceHeight": int(source_pixels.shape[0]),
            **source_info,
            "workingIccProfileDescription": "sRGB IEC61966-2.1",
            "workingBitsPerSample": [16, 16, 16],
            "colorTransform": (
                "embedded source ICC to sRGB, LittleCMS 16-bit, "
                "relative colorimetric with black-point compensation"
            ),
            "precisionPolicy": "16-bit through source preparation and compositing; 8-bit only at H.264 delivery encode",
            "normalizedFinal": str(normalized_final.resolve()),
            "normalizedFinalSha256": _sha256(normalized_final),
            "underResolvedSurrogate": str(surrogate.resolve()),
            "underResolvedSurrogateSha256": _sha256(surrogate),
        }
    image, icc_profile = _normalized_portrait(portrait)
    normalized_final.parent.mkdir(parents=True, exist_ok=True)
    save_options = {"icc_profile": icc_profile} if icc_profile else {}
    image.save(normalized_final, **save_options)

    red, green, blue = image.split()
    gains = (
        float(settings["temperatureRedGain"]),
        float(settings["temperatureGreenGain"]),
        float(settings["temperatureBlueGain"]),
    )
    shifted = Image.merge(
        "RGB",
        tuple(
            band.point([min(255, round(index * gain)) for index in range(256)])
            for band, gain in zip((red, green, blue), gains)
        ),
    )
    toned = shifted.point(_tone_lut(settings) * 3)
    blur_radius = float(settings["textureBlurRadiusAt1080"]) * max(
        image.width / 1080.0, image.height / 1920.0
    )
    softened = toned.filter(ImageFilter.GaussianBlur(radius=blur_radius))
    under_resolved = Image.blend(
        toned, softened, float(settings["textureSoftening"])
    )
    under_resolved.save(surrogate, **save_options)
    return {
        "sourceWidth": image.width,
        "sourceHeight": image.height,
        "sourceIccProfilePresent": bool(icc_profile),
        "normalizedFinal": str(normalized_final.resolve()),
        "normalizedFinalSha256": _sha256(normalized_final),
        "underResolvedSurrogate": str(surrogate.resolve()),
        "underResolvedSurrogateSha256": _sha256(surrogate),
    }


def estimate_focal_point(path: Path, width: int, height: int) -> tuple[float, float]:
    image, _ = _normalized_portrait(path)
    fitted = ImageOps.fit(
        image.convert("L"), (width, height), method=Image.Resampling.LANCZOS
    )
    edges = fitted.filter(ImageFilter.FIND_EDGES).filter(
        ImageFilter.GaussianBlur(radius=1.6)
    )
    pixels = edges.load()
    left, right = round(width * 0.08), round(width * 0.92)
    top, bottom = round(height * 0.06), round(height * 0.94)
    total = weighted_x = weighted_y = 0.0
    for y in range(top, bottom):
        for x in range(left, right):
            weight = max(0, pixels[x, y] - 8) ** 1.35
            total += weight
            weighted_x += x * weight
            weighted_y += y * weight
    if total <= 0:
        return 0.5, 0.45
    return weighted_x / total / width, weighted_y / total / height


def _focal_matte(
    width: int,
    height: int,
    focal_point: tuple[float, float],
    settings: dict[str, Any],
) -> Image.Image:
    background = float(settings["backgroundInfluence"])
    radius_x = float(settings["focalRadiusX"])
    radius_y = float(settings["focalRadiusY"])
    center_x, center_y = focal_point
    values = bytearray(width * height)
    for y in range(height):
        for x in range(width):
            dx = (x / max(width - 1, 1) - center_x) / radius_x
            dy = (y / max(height - 1, 1) - center_y) / radius_y
            emphasis = math.exp(-1.65 * (dx * dx + dy * dy))
            values[y * width + x] = round(
                255 * (background + (1.0 - background) * emphasis)
            )
    return Image.frombytes("L", (width, height), bytes(values))


def _patches(
    recipe: DevelopmentRecipe,
    seed: int,
    focal_point: tuple[float, float],
) -> tuple[FieldPatch, ...]:
    rng = random.Random(seed)
    result = []
    for index in range(recipe.patch_count):
        random_x, random_y = rng.uniform(0.1, 0.9), rng.uniform(0.08, 0.92)
        x = focal_point[0] * 0.64 + random_x * 0.36
        y = focal_point[1] * 0.64 + random_y * 0.36
        result.append(
            FieldPatch(
                x=x,
                y=y,
                radius=rng.uniform(recipe.patch_size_min, recipe.patch_size_max),
                aspect=rng.uniform(0.7, 1.35),
                phase=(2.0 * math.pi * index / max(recipe.patch_count, 1))
                + rng.uniform(-0.45, 0.45),
                drift_x=rng.uniform(0.025, 0.075),
                drift_y=rng.uniform(0.02, 0.06),
                neighbor_angle=rng.uniform(0.0, 2.0 * math.pi),
            )
        )
    return tuple(result)


def _finished_rest_weight(
    fraction: float, finished_hold: float, ease_power: float
) -> float:
    """Return a periodic full-final rest centered on the loop boundary."""
    if finished_hold <= 0:
        return 0.0
    phase = fraction % 1.0
    distance_from_boundary = min(phase, 1.0 - phase)
    half_hold = finished_hold / 2.0
    if distance_from_boundary <= half_hold:
        return 1.0
    travel = (distance_from_boundary - half_hold) / max(0.5 - half_hold, 1e-9)
    eased = 0.5 + 0.5 * math.cos(math.pi * min(1.0, max(0.0, travel)))
    return eased ** ease_power


def _mix_mask(
    recipe: DevelopmentRecipe,
    fraction: float,
    width: int,
    height: int,
    focal: Image.Image,
    patches: tuple[FieldPatch, ...],
) -> Image.Image:
    base_value = math.ceil(255 * recipe.base_final_mix)
    if recipe.mode == "static_reference":
        return Image.new("L", (width, height), 255)
    if recipe.mode == "global_development":
        if recipe.finished_hold > 0:
            activation = _finished_rest_weight(
                fraction, recipe.finished_hold, recipe.ease_power
            )
        else:
            activation = 0.5 - 0.5 * math.cos(
                2.0 * math.pi * fraction * recipe.speed
            )
        value = math.ceil(
            255 * (recipe.base_final_mix + (1 - recipe.base_final_mix) * activation)
        )
        return Image.new("L", (width, height), value)

    field = Image.new("L", (width, height), 0)
    if recipe.mode == "activation_field":
        theta = 2.0 * math.pi * fraction * recipe.speed
        for patch in patches:
            activation = (0.5 + 0.5 * math.cos(theta + patch.phase)) ** 1.35
            center_x = (patch.x + patch.drift_x * math.sin(theta + patch.phase)) * width
            center_y = (patch.y + patch.drift_y * math.cos(theta + patch.phase)) * height
            radius_y = patch.radius * height
            radius_x = radius_y * patch.aspect
            layer = Image.new("L", (width, height), 0)
            draw = ImageDraw.Draw(layer)
            draw.ellipse(
                (
                    center_x - radius_x,
                    center_y - radius_y,
                    center_x + radius_x,
                    center_y + radius_y,
                ),
                fill=round(255 * activation),
            )
            neighbor_distance = radius_y * 0.72
            neighbor_x = center_x + math.cos(patch.neighbor_angle) * neighbor_distance
            neighbor_y = center_y + math.sin(patch.neighbor_angle) * neighbor_distance
            draw.ellipse(
                (
                    neighbor_x - radius_x * 0.72,
                    neighbor_y - radius_y * 0.72,
                    neighbor_x + radius_x * 0.72,
                    neighbor_y + radius_y * 0.72,
                ),
                fill=round(255 * activation * recipe.neighbor_coupling),
            )
            blur_radius = max(1.0, radius_y * recipe.feather)
            field = ImageChops.lighter(
                field, layer.filter(ImageFilter.GaussianBlur(radius=blur_radius))
            )
    elif recipe.mode == "soft_sweep":
        direction_x, direction_y = recipe.direction
        norm = max(abs(direction_x) + abs(direction_y), 1e-9)
        direction_x, direction_y = direction_x / norm, direction_y / norm
        phase = 2.0 * math.pi * fraction * recipe.speed
        values = bytearray(width * height)
        for y in range(height):
            for x in range(width):
                projection = direction_x * x / max(width - 1, 1) + direction_y * y / max(height - 1, 1)
                wave = 0.5 + 0.5 * math.cos(2.0 * math.pi * projection - phase)
                wave = wave * wave * (3.0 - 2.0 * wave)
                values[y * width + x] = round(255 * wave)
        field = Image.frombytes("L", (width, height), bytes(values)).filter(
            ImageFilter.GaussianBlur(radius=max(1.0, height * 0.04 * recipe.feather))
        )
    else:  # pragma: no cover - validated configuration prevents this
        raise AssertionError(recipe.mode)

    focused = ImageChops.multiply(field, focal)
    scale = 1.0 - recipe.base_final_mix
    mixed = focused.point(
        [min(255, round(base_value + value * scale)) for value in range(256)]
    )
    rest = _finished_rest_weight(
        fraction, recipe.finished_hold, recipe.ease_power
    )
    if rest > 0:
        mixed = Image.blend(mixed, Image.new("L", mixed.size, 255), rest)
    return mixed


def development_mask_frames(
    recipe: DevelopmentRecipe,
    *,
    seed: int,
    frames: int,
    width: int,
    height: int,
    focal_point: tuple[float, float],
    mask_settings: dict[str, Any],
) -> tuple[list[bytes], list[dict[str, Any]]]:
    focal = _focal_matte(width, height, focal_point, mask_settings)
    patches = _patches(recipe, seed, focal_point)
    masks: list[bytes] = []
    timeline: list[dict[str, Any]] = []
    for frame in range(frames):
        fraction = frame / max(frames - 1, 1)
        if frame == frames - 1 and masks:
            mask = Image.frombytes("L", (width, height), masks[0])
        else:
            mask = _mix_mask(recipe, fraction, width, height, focal, patches)
        masks.append(mask.tobytes())
        minimum, maximum = mask.getextrema()
        mean = ImageStat.Stat(mask).mean[0]
        timeline.append(
            {
                "frame": frame,
                "timeFraction": fraction,
                "meanFinalMix": round(mean / 255.0, 6),
                "minimumFinalMix": round(minimum / 255.0, 6),
                "maximumFinalMix": round(maximum / 255.0, 6),
            }
        )
    if masks[0] != masks[-1]:
        raise AssertionError(f"{recipe.id} mask does not close exactly")
    return masks, timeline


def build_development_filter(config: Config, mask_width: int, mask_height: int) -> str:
    render_width = config.width * 2
    render_height = config.height * 2
    return (
        f"[0:v]scale={render_width}:{render_height}:force_original_aspect_ratio=increase,"
        f"crop={render_width}:{render_height},format=gbrp16le[final];"
        f"[1:v]scale={render_width}:{render_height}:force_original_aspect_ratio=increase,"
        f"crop={render_width}:{render_height},format=gbrp16le[under];"
        f"[2:v]scale={render_width}:{render_height}:flags=bicubic,format=gray16le[mask];"
        f"[under][final][mask]maskedmerge,"
        f"scale={config.width}:{config.height}:flags=lanczos,"
        f"fps={config.fps},"
        f"format={config.pixel_format},"
        f"setparams=range=limited:color_primaries=bt709:color_trc=bt709:colorspace=bt709[out]"
    )


def _render_with_mask_stream(
    command: list[str], masks: list[bytes]
) -> None:
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    if process.stdin is None:  # pragma: no cover - defensive
        process.kill()
        raise RuntimeError("FFmpeg mask pipe was unavailable")
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


def generate_development_candidate(
    config: Config,
    development_config: DevelopmentConfig,
    candidate: DevelopmentCandidate,
    *,
    ffmpeg: str | None = None,
) -> Path:
    if not candidate.portrait.is_file():
        raise FileNotFoundError(candidate.portrait)
    candidate.output.parent.mkdir(parents=True, exist_ok=True)
    stem = candidate.output.parent / candidate.portrait.stem
    normalized_final = stem.with_name(f"{stem.name}__finished-source.png")
    surrogate = stem.with_name(f"{stem.name}__under-resolved.png")
    source_artifacts = prepare_source_pair(
        candidate.portrait,
        normalized_final,
        surrogate,
        development_config.surrogate,
        ffmpeg=ffmpeg,
    )
    mask_width = int(development_config.mask["width"])
    mask_height = int(development_config.mask["height"])
    frames = candidate.duration_sec * config.fps
    focal_point = estimate_focal_point(normalized_final, mask_width, mask_height)
    masks, timeline = development_mask_frames(
        candidate.recipe,
        seed=candidate.seed,
        frames=frames,
        width=mask_width,
        height=mask_height,
        focal_point=focal_point,
        mask_settings=development_config.mask,
    )
    mask_digest = hashlib.sha256()
    for mask in masks:
        mask_digest.update(mask)
    filter_graph = build_development_filter(config, mask_width, mask_height)
    command = [
        ffmpeg or find_ffmpeg(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-framerate",
        str(config.fps),
        "-loop",
        "1",
        "-i",
        str(normalized_final),
        "-framerate",
        str(config.fps),
        "-loop",
        "1",
        "-i",
        str(surrogate),
        "-f",
        "rawvideo",
        "-pixel_format",
        "gray",
        "-video_size",
        f"{mask_width}x{mask_height}",
        "-framerate",
        str(config.fps),
        "-i",
        "pipe:0",
        "-filter_complex",
        filter_graph,
        "-map",
        "[out]",
        "-frames:v",
        str(frames),
        "-an",
        "-c:v",
        config.codec,
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
        str(candidate.output),
    ]
    _render_with_mask_stream(command, masks)
    manifest = {
        "schemaVersion": "1.0",
        "candidateType": "visual_portrait_development",
        "experimentId": development_config.experiment_id,
        "portraitId": candidate.portrait_id,
        "portraitRevisionId": candidate.revision_id,
        "portrait": str(candidate.portrait.resolve()),
        "portraitSha256": _sha256(candidate.portrait),
        "sourceModel": "single finished source, one-direction reveal",
        "authoritativeState": "finished source portrait",
        "overshootAllowed": False,
        "developmentRecipeId": candidate.recipe.id,
        "developmentRecipeName": candidate.recipe.name,
        "developmentMode": candidate.recipe.mode,
        "developmentConfigVersion": development_config.version,
        "generatorVersion": config.version,
        "durationSec": candidate.duration_sec,
        "fps": config.fps,
        "frames": frames,
        "seed": candidate.seed,
        "loopSafe": True,
        "imageOnly": True,
        "geometry": {
            "fixed": True,
            "scaleChange": 0,
            "positionChange": 0,
            "rotationChange": 0,
            "displacement": "none",
        },
        "sourceArtifacts": source_artifacts,
        "underResolvedSurrogateModel": development_config.surrogate,
        "field": {
            "maskWidth": mask_width,
            "maskHeight": mask_height,
            "focalPoint": {"x": round(focal_point[0], 6), "y": round(focal_point[1], 6)},
            "backgroundInfluence": development_config.mask["backgroundInfluence"],
            "baseFinalMix": candidate.recipe.base_final_mix,
            "patchCount": candidate.recipe.patch_count,
            "patchSizeRange": [
                candidate.recipe.patch_size_min,
                candidate.recipe.patch_size_max,
            ],
            "feather": candidate.recipe.feather,
            "neighborCoupling": candidate.recipe.neighbor_coupling,
            "speed": candidate.recipe.speed,
            "direction": candidate.recipe.direction,
            "finishedHold": candidate.recipe.finished_hold,
            "easePower": candidate.recipe.ease_power,
            "algorithm": "seeded periodic broad field",
            "maskStreamSha256": mask_digest.hexdigest(),
            "firstLastMaskIdentical": masks[0] == masks[-1],
        },
        "developmentTelemetry": {
            "visibleInVideo": False,
            "visibleInReviewInterface": True,
            "valueSystem": "percentage of untouched finished portrait revealed",
            "frameTimeline": timeline,
        },
        "grainTreatment": {
            "mode": "none",
            "reason": "Development pilot isolates surface behavior",
        },
        "audio": "none",
        "text": "none",
        "filterGraph": filter_graph,
        "output": str(candidate.output.resolve()),
    }
    candidate.output.with_suffix(".json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return candidate.output
