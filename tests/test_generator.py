from pathlib import Path
import unittest

from hpr_video_generator.config import load_config
from hpr_video_generator.generator import build_filter, motion_state


class GeneratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config(Path("config/generator.xml"))

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

    def test_tilt_uses_rotate_filter_frame_variable(self):
        result = build_filter(self.config, self.config.presets["VP-011"], 168)
        self.assertIn("sin(2*PI*n/167)", result)


if __name__ == "__main__":
    unittest.main()
