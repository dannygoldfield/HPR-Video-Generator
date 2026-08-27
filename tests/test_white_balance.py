from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest
from unittest.mock import patch

from hpr_video_generator.config import load_config
from hpr_video_generator.white_balance import (
    WhiteBalanceCandidate,
    WhiteBalanceState,
    channel_gains,
    frame_timeline,
    generate_white_balance_candidate,
    load_white_balance_config,
    sample_white_balance,
)


ROOT = Path(__file__).resolve().parents[1]


class WhiteBalanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.video_config = load_config(ROOT / "config/generator.xml")
        self.wb_config = load_white_balance_config(
            ROOT / "config/white-balance-recipes.json"
        )
        self.extreme_config = load_white_balance_config(
            ROOT / "config/white-balance-extreme-recipes.json"
        )

    def test_five_recipes_return_to_accurate_export(self) -> None:
        self.assertEqual(5, len(self.wb_config.recipes))
        for recipe in self.wb_config.recipes.values():
            self.assertEqual(
                sample_white_balance(recipe, 0.0),
                sample_white_balance(recipe, 1.0),
            )

    def test_temperature_and_tint_deltas_have_declared_direction(self) -> None:
        warm = channel_gains(WhiteBalanceState(6, 0))
        magenta = channel_gains(WhiteBalanceState(0, 6))
        self.assertGreater(warm[0], 1)
        self.assertLess(warm[2], 1)
        self.assertGreater(magenta[0], 1)
        self.assertLess(magenta[1], 1)
        self.assertGreater(magenta[2], 1)

    def test_extreme_round_is_versioned_and_unmistakable(self) -> None:
        self.assertEqual("white-balance-extreme-v4", self.extreme_config.experiment_id)
        self.assertEqual(-100, self.extreme_config.value_system["minimum"])
        temperature = self.extreme_config.recipes["WBE-002"]
        tint = self.extreme_config.recipes["WBE-003"]
        warm = channel_gains(sample_white_balance(temperature, 0.72))
        magenta = channel_gains(sample_white_balance(tint, 0.72))
        self.assertGreater(warm[0], 1.14)
        self.assertLess(warm[2], 0.86)
        self.assertLess(magenta[1], 0.89)

    def test_frame_timeline_matches_video_frames_and_neutral_loop(self) -> None:
        recipe = self.wb_config.recipes["WBP-005"]
        timeline = frame_timeline(recipe, duration_sec=7, fps=24)
        self.assertEqual(168, len(timeline))
        self.assertEqual(0, timeline[0]["temperatureDelta"])
        self.assertEqual(0, timeline[-1]["temperatureDelta"])
        self.assertEqual(0, timeline[-1]["tintDelta"])

    @patch("hpr_video_generator.white_balance.subprocess.run")
    def test_manifest_contains_exact_interface_telemetry(self, run) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            portrait = root / "portrait.jpg"
            portrait.write_bytes(b"pilot portrait")
            output = root / "candidate.mp4"
            generate_white_balance_candidate(
                self.video_config,
                self.wb_config,
                WhiteBalanceCandidate(
                    "POR-TEST",
                    "POR-TEST-R001",
                    portrait,
                    self.wb_config.recipes["WBP-004"],
                    123,
                    7,
                    output,
                ),
                ffmpeg="ffmpeg",
            )
            manifest = json.loads(output.with_suffix(".json").read_text())
            self.assertTrue(manifest["imageOnly"])
            self.assertFalse(
                manifest["diagnosticSliders"]["visibleInVideo"]
            )
            self.assertEqual(
                168, len(manifest["diagnosticSliders"]["frameTimeline"])
            )
            self.assertTrue(output.with_suffix(".commands.txt").is_file())
            run.assert_called_once()

    @patch("hpr_video_generator.white_balance.subprocess.run")
    def test_manifest_uses_configured_experiment_and_slider_range(self, run) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            portrait = root / "portrait.jpg"
            portrait.write_bytes(b"pilot portrait")
            output = root / "candidate.mp4"
            generate_white_balance_candidate(
                self.video_config,
                self.extreme_config,
                WhiteBalanceCandidate(
                    "POR-TEST",
                    "POR-TEST-R001",
                    portrait,
                    self.extreme_config.recipes["WBE-002"],
                    456,
                    7,
                    output,
                ),
                ffmpeg="ffmpeg",
            )
            manifest = json.loads(output.with_suffix(".json").read_text())
            self.assertEqual("white-balance-extreme-v4", manifest["experimentId"])
            self.assertEqual(-100, manifest["diagnosticSliders"]["temperature"]["minimum"])
            self.assertEqual(100, manifest["diagnosticSliders"]["temperature"]["maximum"])
            run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
