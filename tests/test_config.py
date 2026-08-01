from pathlib import Path
import unittest

from hpr_video_generator.config import load_config


class ConfigTests(unittest.TestCase):
    def test_first_config_is_vertical_and_loop_safe(self):
        config = load_config(Path("config/generator.xml"))
        self.assertEqual((config.width, config.height, config.fps), (1080, 1920, 24))
        self.assertEqual(len(config.presets), 11)
        self.assertTrue(all(p.loop_safe for p in config.presets.values()))


if __name__ == "__main__":
    unittest.main()

