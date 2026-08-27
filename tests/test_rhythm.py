from pathlib import Path
from tempfile import TemporaryDirectory
import json
import math
import unittest
from unittest.mock import patch

from hpr_video_generator.config import load_config
from hpr_video_generator.generator import loop_phase
from hpr_video_generator.experiments import derive_motion_variable_variants
from hpr_video_generator.rhythm import (
    RhythmCandidate,
    build_rhythm_filter,
    exact_timeline,
    generate_rhythm_candidate,
    load_rhythm_config,
    sample_recipe,
)


ROOT = Path(__file__).resolve().parents[1]


class MotionRhythmTests(unittest.TestCase):
    def setUp(self) -> None:
        self.video_config = load_config(ROOT / "config/generator.xml")
        self.rhythm_config = load_rhythm_config(ROOT / "config/motion-rhythms.json")

    def test_five_loop_safe_pilot_recipes_load(self) -> None:
        self.assertEqual(
            {"MR-001", "MR-002", "MR-003", "MR-004", "MR-005"},
            set(self.rhythm_config.recipes),
        )
        for recipe in self.rhythm_config.recipes.values():
            self.assertEqual(sample_recipe(recipe, 0.0), sample_recipe(recipe, 1.0))

    def test_baseline_matches_existing_cosine_scale(self) -> None:
        recipe = self.rhythm_config.recipes["MR-001"]
        for frame in (0, 21, 42, 84, 126, 167):
            fraction = frame / 167
            expected = 1.025 + (1.0325 - 1.025) * (
                1.0 - math.cos(loop_phase(frame, 168))
            ) / 2.0
            self.assertAlmostEqual(expected, sample_recipe(recipe, fraction).scale, places=10)

    def test_hold_has_identical_states_at_its_boundaries(self) -> None:
        recipe = self.rhythm_config.recipes["MR-003"]
        self.assertEqual(sample_recipe(recipe, 0.38), sample_recipe(recipe, 0.52))
        timeline = exact_timeline(recipe, duration_sec=7, fps=24)
        self.assertAlmostEqual(1.0, timeline["holds"][0]["durationSec"], places=2)

    def test_filter_uses_exact_frame_count_and_output_size(self) -> None:
        recipe = self.rhythm_config.recipes["MR-004"]
        graph = build_rhythm_filter(self.video_config, recipe, frames=168)
        self.assertIn("zoompan", graph)
        self.assertIn(":d=168:", graph)
        self.assertIn("scale=1080:1920", graph)

    def test_variable_experiment_changes_one_motion_dimension_at_a_time(self) -> None:
        base = self.rhythm_config.recipes["MR-005"]
        variants = derive_motion_variable_variants(base)
        self.assertEqual(4, len(variants))
        low, high, horizontal, vertical = variants
        self.assertAlmostEqual(1.02875, max(k.scale for k in low.recipe.keyframes))
        self.assertAlmostEqual(1.03625, max(k.scale for k in high.recipe.keyframes))
        self.assertEqual({1.025}, {k.scale for k in horizontal.recipe.keyframes})
        self.assertEqual({0.0}, {k.y for k in horizontal.recipe.keyframes})
        self.assertAlmostEqual(0.004, max(k.x for k in horizontal.recipe.keyframes))
        self.assertEqual({0.0}, {k.x for k in vertical.recipe.keyframes})
        self.assertAlmostEqual(0.003, max(k.y for k in vertical.recipe.keyframes))
        for variant in variants:
            self.assertEqual(
                sample_recipe(variant.recipe, 0.0),
                sample_recipe(variant.recipe, 1.0),
            )

    @patch("hpr_video_generator.rhythm.subprocess.run")
    def test_manifest_records_reproducible_timeline(self, run) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            portrait = root / "portrait.jpg"
            portrait.write_bytes(b"pilot portrait")
            output = root / "candidate.mp4"
            recipe = self.rhythm_config.recipes["MR-005"]
            candidate = RhythmCandidate(
                "POR-TEST",
                "POR-TEST-R001",
                portrait,
                recipe,
                2026081401,
                7,
                output,
            )
            generate_rhythm_candidate(
                self.video_config, self.rhythm_config, candidate, ffmpeg="ffmpeg"
            )
            manifest = json.loads(output.with_suffix(".json").read_text())
            self.assertEqual("MR-005", manifest["motionRecipeId"])
            self.assertEqual("POR-TEST-R001", manifest["portraitRevisionId"])
            self.assertEqual(168, manifest["frames"])
            self.assertEqual("none", manifest["grainTreatment"]["mode"])
            run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
