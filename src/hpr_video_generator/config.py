from dataclasses import dataclass
from pathlib import Path
import xml.etree.ElementTree as ET


@dataclass(frozen=True)
class Preset:
    id: str
    name: str
    motion: str
    scale: float
    x: float
    y: float
    rotation_deg: float
    grain_opacity: float
    loop_safe: bool


@dataclass(frozen=True)
class Config:
    version: str
    width: int
    height: int
    fps: int
    codec: str
    pixel_format: str
    duration_sec: int
    grain_opacity: float
    presets: dict[str, Preset]


def load_config(path: Path) -> Config:
    root = ET.parse(path).getroot()
    output = root.find("output")
    defaults = root.find("defaults")
    if output is None or defaults is None:
        raise ValueError("Configuration requires output and defaults")
    presets = {}
    for node in root.findall("./presets/preset"):
        preset = Preset(
            id=node.attrib["id"], name=node.attrib["name"], motion=node.attrib["motion"],
            scale=float(node.attrib["scale"]), x=float(node.attrib["x"]), y=float(node.attrib["y"]),
            rotation_deg=float(node.attrib["rotationDeg"]), grain_opacity=float(node.attrib["grainOpacity"]),
            loop_safe=node.attrib["loopSafe"] == "true",
        )
        presets[preset.id] = preset
    return Config(
        version=root.attrib["version"], width=int(output.attrib["width"]), height=int(output.attrib["height"]),
        fps=int(output.attrib["fps"]), codec=output.attrib["codec"], pixel_format=output.attrib["pixelFormat"],
        duration_sec=int(defaults.attrib["durationSec"]), grain_opacity=float(defaults.attrib["grainOpacity"]), presets=presets,
    )
