from pathlib import Path
import unittest

from hpr_video_generator.config import load_config
from hpr_video_generator.generator import build_filter, build_texture_filter, motion_state


ROOT = Path(__file__).resolve().parents[1]


class GeneratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config(ROOT / "config/generator.xml")

    def test_every_motion_returns_to_start(self):
        frames = self.config.duration_sec * self.config.fps
        for preset in self.config.presets.values():
            start = motion_state(preset, 0, frames)
            end = motion_state(preset, frames - 1, frames)
            for a, b in zip(start, end):
                self.assertAlmostEqual(a, b, places=8, msg=preset.id)

    def test_filter_uses_exact_frame_count_and_grain(self):
        frames = 168
        result = build_filter(self.config, self.config.presets["VP-002"], frames)
        self.assertIn("d=168", result)
        self.assertIn("all_mode=overlay", result)
        self.assertIn("all_opacity=0.08", result)
        self.assertIn("s=2160x3840", result)
        self.assertIn("scale=1080:1920:flags=lanczos", result)

    def test_tilt_uses_rotate_filter_frame_variable(self):
        result = build_filter(self.config, self.config.presets["VP-021"], 168)
        self.assertIn("sin(2*PI*n/167)", result)
        self.assertIn("scale=2240:3984,crop=2160:3840", result)

    def test_restrained_presets_use_half_strength_grain(self):
        result = build_filter(self.config, self.config.presets["VP-012"], 168)
        self.assertIn("all_opacity=0.04", result)

    def test_texture_filter_removes_static_scene_and_loops(self):
        result = build_texture_filter(self.config, self.config.presets["VP-012"], 0.02)
        self.assertIn("reverse[texture_reverse]", result)
        self.assertIn("tblend=all_mode=difference", result)
        self.assertIn("lut=y='val*0.02'[mask]", result)
        self.assertIn("extractplanes=y+u+v", result)
        self.assertIn("[lit_y][base_u][base_v]mergeplanes", result)


if __name__ == "__main__":
    unittest.main()
