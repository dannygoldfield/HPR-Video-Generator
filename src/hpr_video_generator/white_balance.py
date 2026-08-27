from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import subprocess
from typing import Any

from .config import Config
from .generator import find_ffmpeg
from .rhythm import EASINGS, _ease


TEMP_RED_GAIN_PER_DELTA = 0.0015
TEMP_BLUE_GAIN_PER_DELTA = -0.0015
TINT_RED_BLUE_GAIN_PER_DELTA = 0.0006
TINT_GREEN_GAIN_PER_DELTA = -0.0012


@dataclass(frozen=True)
class WhiteBalanceKeyframe:
    time: float
    temperature: float
    tint: float
    easing_to_next: str


@dataclass(frozen=True)
class WhiteBalanceRecipe:
    id: str
    name: str
    adjustment_type: str
    keyframes: tuple[WhiteBalanceKeyframe, ...]


@dataclass(frozen=True)
class WhiteBalanceConfig:
    version: str
    experiment_id: str
    value_system: dict[str, Any]
    recipes: dict[str, WhiteBalanceRecipe]


@dataclass(frozen=True)
class WhiteBalanceState:
    temperature: float
    tint: float


@dataclass(frozen=True)
class WhiteBalanceCandidate:
    portrait_id: str
    revision_id: str
    portrait: Path
    recipe: WhiteBalanceRecipe
    seed: int
    duration_sec: int
    output: Path


def load_white_balance_config(path: Path) -> WhiteBalanceConfig:
    payload = json.loads(path.read_text(encoding="utf-8"))
    value_system = payload["valueSystem"]
    minimum = float(value_system["minimum"])
    maximum = float(value_system["maximum"])
    if minimum >= maximum or not minimum <= 0 <= maximum:
        raise ValueError("White-balance value range must contain neutral 0")
    recipes: dict[str, WhiteBalanceRecipe] = {}
    for raw in payload.get("recipes", []):
        recipe = WhiteBalanceRecipe(
            id=raw["id"],
            name=raw["name"],
            adjustment_type=raw["adjustmentType"],
            keyframes=tuple(
                WhiteBalanceKeyframe(
                    time=float(item["time"]),
                    temperature=float(item["temperature"]),
                    tint=float(item["tint"]),
                    easing_to_next=item["easingToNext"],
                )
                for item in raw["keyframes"]
            ),
        )
        validate_white_balance_recipe(recipe, minimum=minimum, maximum=maximum)
        if recipe.id in recipes:
            raise ValueError(f"Duplicate white-balance recipe: {recipe.id}")
        recipes[recipe.id] = recipe
    if not recipes:
        raise ValueError("White-balance configuration requires recipes")
    return WhiteBalanceConfig(
        payload["version"], payload["experimentId"], value_system, recipes
    )


def validate_white_balance_recipe(
    recipe: WhiteBalanceRecipe, *, minimum: float = -10, maximum: float = 10
) -> None:
    if len(recipe.keyframes) < 2:
        raise ValueError(f"{recipe.id} requires at least two keyframes")
    times = [keyframe.time for keyframe in recipe.keyframes]
    if not math.isclose(times[0], 0.0) or not math.isclose(times[-1], 1.0):
        raise ValueError(f"{recipe.id} must begin at 0 and end at 1")
    if any(later <= earlier for earlier, later in zip(times, times[1:])):
        raise ValueError(f"{recipe.id} keyframe times must increase")
    if any(keyframe.easing_to_next not in EASINGS for keyframe in recipe.keyframes):
        raise ValueError(f"{recipe.id} uses an unsupported easing")
    if any(
        value < minimum or value > maximum
        for keyframe in recipe.keyframes
        for value in (keyframe.temperature, keyframe.tint)
    ):
        raise ValueError(f"{recipe.id} exceeds the diagnostic delta range")
    first, last = recipe.keyframes[0], recipe.keyframes[-1]
    if not (
        math.isclose(first.temperature, last.temperature, abs_tol=1e-12)
        and math.isclose(first.tint, last.tint, abs_tol=1e-12)
    ):
        raise ValueError(f"{recipe.id} must return to its starting white balance")


def sample_white_balance(
    recipe: WhiteBalanceRecipe, time_fraction: float
) -> WhiteBalanceState:
    if not 0.0 <= time_fraction <= 1.0:
        raise ValueError("time_fraction must be between 0 and 1")
    if math.isclose(time_fraction, 1.0):
        last = recipe.keyframes[-1]
        return WhiteBalanceState(last.temperature, last.tint)
    for first, second in zip(recipe.keyframes, recipe.keyframes[1:]):
        if first.time <= time_fraction <= second.time:
            local = (time_fraction - first.time) / (second.time - first.time)
            amount = _ease(first.easing_to_next, local)
            return WhiteBalanceState(
                temperature=first.temperature
                + (second.temperature - first.temperature) * amount,
                tint=first.tint + (second.tint - first.tint) * amount,
            )
    raise AssertionError("Validated recipe did not cover requested time")


def channel_gains(state: WhiteBalanceState) -> tuple[float, float, float]:
    red = (
        1.0
        + state.temperature * TEMP_RED_GAIN_PER_DELTA
        + state.tint * TINT_RED_BLUE_GAIN_PER_DELTA
    )
    green = 1.0 + state.tint * TINT_GREEN_GAIN_PER_DELTA
    blue = (
        1.0
        + state.temperature * TEMP_BLUE_GAIN_PER_DELTA
        + state.tint * TINT_RED_BLUE_GAIN_PER_DELTA
    )
    return red, green, blue


def frame_timeline(
    recipe: WhiteBalanceRecipe, duration_sec: int, fps: int
) -> list[dict[str, Any]]:
    frames = duration_sec * fps
    timeline = []
    for frame in range(frames):
        fraction = frame / max(frames - 1, 1)
        state = sample_white_balance(recipe, fraction)
        red, green, blue = channel_gains(state)
        timeline.append(
            {
                "frame": frame,
                "timeSec": frame / fps,
                "temperatureDelta": round(state.temperature, 6),
                "tintDelta": round(state.tint, 6),
                "redGain": round(red, 9),
                "greenGain": round(green, 9),
                "blueGain": round(blue, 9),
            }
        )
    return timeline


def write_command_file(path: Path, timeline: list[dict[str, Any]]) -> None:
    lines = []
    for state in timeline:
        lines.append(
            f"{state['timeSec']:.6f} "
            f"colorchannelmixer@hprwb rr {state['redGain']:.9f}, "
            f"colorchannelmixer@hprwb gg {state['greenGain']:.9f}, "
            f"colorchannelmixer@hprwb bb {state['blueGain']:.9f};"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _filter_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def build_white_balance_filter(
    config: Config,
    command_path: Path,
    initial_state: WhiteBalanceState,
) -> str:
    render_width = config.width * 2
    render_height = config.height * 2
    red, green, blue = channel_gains(initial_state)
    return (
        f"[0:v]scale={render_width}:{render_height}:force_original_aspect_ratio=increase,"
        f"crop={render_width}:{render_height},fps={config.fps},"
        f"sendcmd=f='{_filter_path(command_path)}',"
        f"colorchannelmixer@hprwb=rr={red:.9f}:gg={green:.9f}:bb={blue:.9f},"
        f"scale={config.width}:{config.height}:flags=lanczos,"
        f"format={config.pixel_format}[out]"
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def generate_white_balance_candidate(
    config: Config,
    white_balance_config: WhiteBalanceConfig,
    candidate: WhiteBalanceCandidate,
    *,
    ffmpeg: str | None = None,
) -> Path:
    if not candidate.portrait.is_file():
        raise FileNotFoundError(candidate.portrait)
    candidate.output.parent.mkdir(parents=True, exist_ok=True)
    frames = candidate.duration_sec * config.fps
    timeline = frame_timeline(candidate.recipe, candidate.duration_sec, config.fps)
    command_path = candidate.output.with_suffix(".commands.txt")
    write_command_file(command_path, timeline)
    filter_graph = build_white_balance_filter(
        config,
        command_path,
        sample_white_balance(candidate.recipe, 0.0),
    )
    command = [
        ffmpeg or find_ffmpeg(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-loop",
        "1",
        "-i",
        str(candidate.portrait),
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
        "-movflags",
        "+faststart",
        str(candidate.output),
    ]
    subprocess.run(command, check=True)
    manifest = {
        "schemaVersion": "1.0",
        "candidateType": "visual_white_balance_calibration",
        "experimentId": white_balance_config.experiment_id,
        "portraitId": candidate.portrait_id,
        "portraitRevisionId": candidate.revision_id,
        "portrait": str(candidate.portrait.resolve()),
        "portraitSha256": _sha256(candidate.portrait),
        "whiteBalanceRecipeId": candidate.recipe.id,
        "whiteBalanceRecipeName": candidate.recipe.name,
        "adjustmentType": candidate.recipe.adjustment_type,
        "whiteBalanceConfigVersion": white_balance_config.version,
        "generatorVersion": config.version,
        "durationSec": candidate.duration_sec,
        "fps": config.fps,
        "frames": frames,
        "seed": candidate.seed,
        "randomization": "none",
        "loopSafe": True,
        "imageOnly": True,
        "visualMovement": "none",
        "diagnosticSliders": {
            "visibleInVideo": False,
            "visibleInReviewInterface": True,
            "valueSystem": white_balance_config.value_system,
            "temperature": {
                "minimum": white_balance_config.value_system["minimum"],
                "maximum": white_balance_config.value_system["maximum"],
                "neutral": white_balance_config.value_system["neutral"],
            },
            "tint": {
                "minimum": white_balance_config.value_system["minimum"],
                "maximum": white_balance_config.value_system["maximum"],
                "neutral": white_balance_config.value_system["neutral"],
            },
            "keyframes": [
                {
                    "timeFraction": keyframe.time,
                    "temperatureDelta": keyframe.temperature,
                    "tintDelta": keyframe.tint,
                    "easingToNext": keyframe.easing_to_next,
                }
                for keyframe in candidate.recipe.keyframes
            ],
            "frameTimeline": timeline,
        },
        "channelGainMapping": {
            "temperatureRedGainPerDelta": TEMP_RED_GAIN_PER_DELTA,
            "temperatureBlueGainPerDelta": TEMP_BLUE_GAIN_PER_DELTA,
            "tintRedBlueGainPerDelta": TINT_RED_BLUE_GAIN_PER_DELTA,
            "tintGreenGainPerDelta": TINT_GREEN_GAIN_PER_DELTA,
        },
        "commandFile": str(command_path.resolve()),
        "commandFileSha256": _sha256(command_path),
        "grainTreatment": {"mode": "none", "reason": "Color-calibration pilot"},
        "filterGraph": filter_graph,
        "output": str(candidate.output.resolve()),
    }
    candidate.output.with_suffix(".json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return candidate.output
