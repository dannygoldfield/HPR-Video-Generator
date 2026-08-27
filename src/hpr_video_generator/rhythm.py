from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
import math
from pathlib import Path
import subprocess
from typing import Any

from .config import Config
from .generator import find_ffmpeg


EASINGS = {
    "linear",
    "ease_in_sine",
    "ease_out_sine",
    "ease_in_out_sine",
}


@dataclass(frozen=True)
class MotionKeyframe:
    time: float
    scale: float
    x: float
    y: float
    easing_to_next: str


@dataclass(frozen=True)
class MotionHold:
    start: float
    end: float


@dataclass(frozen=True)
class MotionRecipe:
    id: str
    name: str
    rhythm_type: str
    loop_safe: bool
    holds: tuple[MotionHold, ...]
    keyframes: tuple[MotionKeyframe, ...]


@dataclass(frozen=True)
class MotionRhythmConfig:
    version: str
    recipes: dict[str, MotionRecipe]


@dataclass(frozen=True)
class MotionState:
    scale: float
    x: float
    y: float


@dataclass(frozen=True)
class RhythmCandidate:
    portrait_id: str
    revision_id: str
    portrait: Path
    recipe: MotionRecipe
    seed: int
    duration_sec: int
    output: Path
    experiment_id: str = "motion-rhythm-pilot-v1"
    parent_visual_id: str | None = None
    experiment_variables: dict[str, Any] = field(default_factory=dict)


def _same_state(first: MotionKeyframe, last: MotionKeyframe) -> bool:
    return all(
        math.isclose(a, b, abs_tol=1e-12)
        for a, b in ((first.scale, last.scale), (first.x, last.x), (first.y, last.y))
    )


def load_rhythm_config(path: Path) -> MotionRhythmConfig:
    payload = json.loads(path.read_text(encoding="utf-8"))
    recipes: dict[str, MotionRecipe] = {}
    for raw in payload.get("recipes", []):
        keyframes = tuple(
            MotionKeyframe(
                time=float(item["time"]),
                scale=float(item["scale"]),
                x=float(item["x"]),
                y=float(item["y"]),
                easing_to_next=item["easingToNext"],
            )
            for item in raw["keyframes"]
        )
        holds = tuple(
            MotionHold(float(item["start"]), float(item["end"]))
            for item in raw.get("holds", [])
        )
        recipe = MotionRecipe(
            id=raw["id"],
            name=raw["name"],
            rhythm_type=raw["rhythmType"],
            loop_safe=bool(raw["loopSafe"]),
            holds=holds,
            keyframes=keyframes,
        )
        validate_recipe(recipe)
        if recipe.id in recipes:
            raise ValueError(f"Duplicate motion recipe: {recipe.id}")
        recipes[recipe.id] = recipe
    if not recipes:
        raise ValueError("Motion rhythm configuration requires recipes")
    return MotionRhythmConfig(version=payload["version"], recipes=recipes)


def validate_recipe(recipe: MotionRecipe) -> None:
    if len(recipe.keyframes) < 2:
        raise ValueError(f"{recipe.id} requires at least two keyframes")
    times = [keyframe.time for keyframe in recipe.keyframes]
    if not math.isclose(times[0], 0.0) or not math.isclose(times[-1], 1.0):
        raise ValueError(f"{recipe.id} must begin at 0 and end at 1")
    if any(later <= earlier for earlier, later in zip(times, times[1:])):
        raise ValueError(f"{recipe.id} keyframe times must increase")
    if any(keyframe.scale < 1.0 for keyframe in recipe.keyframes):
        raise ValueError(f"{recipe.id} scale cannot be smaller than 1")
    if any(keyframe.easing_to_next not in EASINGS for keyframe in recipe.keyframes):
        raise ValueError(f"{recipe.id} uses an unsupported easing")
    if recipe.loop_safe and not _same_state(recipe.keyframes[0], recipe.keyframes[-1]):
        raise ValueError(f"{recipe.id} loop-safe start and end states must match")
    for hold in recipe.holds:
        if not 0 <= hold.start < hold.end <= 1:
            raise ValueError(f"{recipe.id} has an invalid hold interval")


def _ease(name: str, value: float) -> float:
    if name == "linear":
        return value
    if name == "ease_in_sine":
        return 1.0 - math.cos((value * math.pi) / 2.0)
    if name == "ease_out_sine":
        return math.sin((value * math.pi) / 2.0)
    if name == "ease_in_out_sine":
        return -(math.cos(math.pi * value) - 1.0) / 2.0
    raise ValueError(f"Unsupported easing: {name}")


def sample_recipe(recipe: MotionRecipe, time_fraction: float) -> MotionState:
    if not 0.0 <= time_fraction <= 1.0:
        raise ValueError("time_fraction must be between 0 and 1")
    if math.isclose(time_fraction, 1.0):
        last = recipe.keyframes[-1]
        return MotionState(last.scale, last.x, last.y)
    for first, second in zip(recipe.keyframes, recipe.keyframes[1:]):
        if first.time <= time_fraction <= second.time:
            local = (time_fraction - first.time) / (second.time - first.time)
            amount = _ease(first.easing_to_next, local)
            return MotionState(
                scale=first.scale + (second.scale - first.scale) * amount,
                x=first.x + (second.x - first.x) * amount,
                y=first.y + (second.y - first.y) * amount,
            )
    raise AssertionError("Validated recipe did not cover requested time")


def _ffmpeg_ease(name: str, variable: str) -> str:
    if name == "linear":
        return variable
    if name == "ease_in_sine":
        return f"1-cos(({variable})*PI/2)"
    if name == "ease_out_sine":
        return f"sin(({variable})*PI/2)"
    if name == "ease_in_out_sine":
        return f"(1-cos(PI*({variable})))/2"
    raise ValueError(f"Unsupported easing: {name}")


def _frame_index(time_fraction: float, frames: int) -> int:
    return round(time_fraction * max(frames - 1, 1))


def _value_expression(recipe: MotionRecipe, attribute: str, frames: int) -> str:
    expressions = []
    for first, second in zip(recipe.keyframes, recipe.keyframes[1:]):
        start = _frame_index(first.time, frames)
        end = _frame_index(second.time, frames)
        span = max(end - start, 1)
        local = f"(on-{start})/{span}"
        eased = _ffmpeg_ease(first.easing_to_next, local)
        first_value = getattr(first, attribute)
        difference = getattr(second, attribute) - first_value
        value = f"{first_value:.10f}+({difference:.10f})*({eased})"
        expressions.append((end, value))
    result = f"{getattr(recipe.keyframes[-1], attribute):.10f}"
    for end, value in reversed(expressions):
        result = f"if(lte(on,{end}),{value},{result})"
    return result


def build_rhythm_filter(config: Config, recipe: MotionRecipe, frames: int) -> str:
    render_width = config.width * 2
    render_height = config.height * 2
    zoom = _value_expression(recipe, "scale", frames)
    x_fraction = _value_expression(recipe, "x", frames)
    y_fraction = _value_expression(recipe, "y", frames)
    x = f"iw/2-(iw/zoom/2)+({x_fraction})*iw"
    y = f"ih/2-(ih/zoom/2)+({y_fraction})*ih"
    return (
        f"[0:v]scale={render_width}:{render_height}:force_original_aspect_ratio=increase,"
        f"crop={render_width}:{render_height},"
        f"zoompan=z='{zoom}':x='{x}':y='{y}':d={frames}:"
        f"s={render_width}x{render_height}:fps={config.fps},"
        f"scale={config.width}:{config.height}:flags=lanczos,"
        f"format={config.pixel_format}[out]"
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def exact_timeline(recipe: MotionRecipe, duration_sec: int, fps: int) -> dict[str, Any]:
    frames = duration_sec * fps
    keyframes = []
    for keyframe in recipe.keyframes:
        frame = _frame_index(keyframe.time, frames)
        keyframes.append(
            {
                "declaredTimeFraction": keyframe.time,
                "frame": frame,
                "timeSec": frame / fps,
                "scale": keyframe.scale,
                "xFraction": keyframe.x,
                "yFraction": keyframe.y,
                "easingToNext": keyframe.easing_to_next,
            }
        )
    holds = []
    for hold in recipe.holds:
        start_frame = _frame_index(hold.start, frames)
        end_frame = _frame_index(hold.end, frames)
        holds.append(
            {
                "startFrame": start_frame,
                "endFrame": end_frame,
                "startSec": start_frame / fps,
                "endSec": end_frame / fps,
                "durationSec": (end_frame - start_frame) / fps,
            }
        )
    return {"keyframes": keyframes, "holds": holds}


def generate_rhythm_candidate(
    config: Config,
    rhythm_config: MotionRhythmConfig,
    candidate: RhythmCandidate,
    *,
    ffmpeg: str | None = None,
) -> Path:
    if not candidate.portrait.is_file():
        raise FileNotFoundError(candidate.portrait)
    candidate.output.parent.mkdir(parents=True, exist_ok=True)
    frames = candidate.duration_sec * config.fps
    filter_graph = build_rhythm_filter(config, candidate.recipe, frames)
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
        "candidateType": "visual_motion_rhythm",
        "portraitId": candidate.portrait_id,
        "portraitRevisionId": candidate.revision_id,
        "portrait": str(candidate.portrait.resolve()),
        "portraitSha256": _sha256(candidate.portrait),
        "motionRecipeId": candidate.recipe.id,
        "motionRecipeName": candidate.recipe.name,
        "rhythmType": candidate.recipe.rhythm_type,
        "experimentId": candidate.experiment_id,
        "parentVisualId": candidate.parent_visual_id,
        "experimentVariables": candidate.experiment_variables,
        "motionRhythmConfigVersion": rhythm_config.version,
        "generatorVersion": config.version,
        "durationSec": candidate.duration_sec,
        "fps": config.fps,
        "frames": frames,
        "seed": candidate.seed,
        "randomization": "none",
        "loopSafe": candidate.recipe.loop_safe,
        "timeline": exact_timeline(candidate.recipe, candidate.duration_sec, config.fps),
        "grainTreatment": {
            "mode": "none",
            "reason": "Motion-rhythm pilot isolates movement timing",
        },
        "filterGraph": filter_graph,
        "output": str(candidate.output.resolve()),
    }
    candidate.output.with_suffix(".json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return candidate.output
