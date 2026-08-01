from dataclasses import dataclass
from pathlib import Path
import json
import math
import shutil
import subprocess

from .config import Config, Preset


@dataclass(frozen=True)
class Candidate:
    portrait: Path
    grain: Path
    preset: Preset
    seed: int
    duration_sec: int
    output: Path


def loop_phase(frame: int, total_frames: int) -> float:
    if total_frames < 2:
        return 0.0
    return 2.0 * math.pi * frame / (total_frames - 1)


def motion_state(preset: Preset, frame: int, total_frames: int) -> tuple[float, float, float, float]:
    phase = loop_phase(frame, total_frames)
    wave = (1.0 - math.cos(phase)) / 2.0
    direction = -1.0 if preset.motion.endswith("reverse") else 1.0
    scale = preset.scale
    x = y = rotation = 0.0
    if preset.motion in {"breathing", "scale_in_out", "scale_drift", "orbit"}:
        scale = 1.025 + (preset.scale - 1.025) * wave
    elif preset.motion == "scale_out_in":
        scale = preset.scale - (preset.scale - 1.025) * wave
    if preset.motion in {"drift_x", "drift_x_reverse", "scale_drift"}:
        x = direction * preset.x * math.sin(phase)
    if preset.motion in {"drift_y", "drift_y_reverse", "scale_drift"}:
        y = direction * preset.y * math.sin(phase)
    if preset.motion == "orbit":
        x, y = preset.x * math.sin(phase), preset.y * (1.0 - math.cos(phase))
    if preset.motion == "tilt":
        rotation = math.radians(preset.rotation_deg) * math.sin(phase)
    return scale, x, y, rotation


def find_ffmpeg() -> str:
    direct = shutil.which("ffmpeg")
    if direct:
        return direct
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError as exc:
        raise RuntimeError("FFmpeg is required. Install the render extra: pip install -e '.[render]'") from exc


def build_filter(config: Config, preset: Preset, frames: int) -> str:
    n = max(frames - 1, 1)
    phase = f"2*PI*on/{n}"
    wave = f"(1-cos({phase}))/2"
    base = 1.025
    if preset.motion in {"breathing", "scale_in_out", "scale_drift", "orbit"}:
        zoom = f"{base}+{preset.scale-base}*{wave}"
    elif preset.motion == "scale_out_in":
        zoom = f"{preset.scale}-{preset.scale-base}*{wave}"
    else:
        zoom = str(preset.scale)
    x = "iw/2-(iw/zoom/2)"
    y = "ih/2-(ih/zoom/2)"
    sign = "-" if preset.motion.endswith("reverse") else ""
    if preset.motion in {"drift_x", "drift_x_reverse", "scale_drift"}:
        x += f"+{sign}{preset.x}*iw*sin({phase})"
    if preset.motion in {"drift_y", "drift_y_reverse", "scale_drift"}:
        y += f"+{sign}{preset.y}*ih*sin({phase})"
    if preset.motion == "orbit":
        x += f"+{preset.x}*iw*sin({phase})"
        y += f"+{preset.y}*ih*(1-cos({phase}))"
    portrait = (
        f"[0:v]scale=2160:3840:force_original_aspect_ratio=increase,crop=2160:3840,"
        f"zoompan=z='{zoom}':x='{x}':y='{y}':d={frames}:s={config.width}x{config.height}:fps={config.fps}"
    )
    if preset.motion == "tilt":
        rotate_phase = f"2*PI*n/{n}"
        angle = f"{math.radians(preset.rotation_deg)}*sin({rotate_phase})"
        portrait += f",rotate='{angle}':ow=iw:oh=ih:c=black"
    portrait += "[portrait]"
    grain = f"[1:v]scale={config.width}:{config.height}:force_original_aspect_ratio=increase,crop={config.width}:{config.height},fps={config.fps}[grain]"
    blend = f"[portrait][grain]blend=all_mode=overlay:all_opacity={config.grain_opacity},format={config.pixel_format}[out]"
    return ";".join([portrait, grain, blend])


def generate(config: Config, candidate: Candidate) -> Path:
    for source in (candidate.portrait, candidate.grain):
        if not source.is_file():
            raise FileNotFoundError(source)
    candidate.output.parent.mkdir(parents=True, exist_ok=True)
    frames = candidate.duration_sec * config.fps
    command = [find_ffmpeg(), "-y", "-loop", "1", "-i", str(candidate.portrait), "-stream_loop", "-1", "-i", str(candidate.grain),
               "-filter_complex", build_filter(config, candidate.preset, frames), "-map", "[out]", "-frames:v", str(frames),
               "-an", "-c:v", config.codec, "-crf", "18", "-preset", "medium", "-movflags", "+faststart", str(candidate.output)]
    subprocess.run(command, check=True)
    metadata = {"portrait": str(candidate.portrait), "grain": str(candidate.grain), "preset": candidate.preset.id,
                "seed": candidate.seed, "durationSec": candidate.duration_sec, "fps": config.fps, "frames": frames,
                "output": str(candidate.output), "generatorVersion": config.version}
    candidate.output.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n")
    return candidate.output
