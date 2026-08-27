from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import io
import json
import unittest
from unittest.mock import Mock, patch

from PIL import Image, ImageFont

from hpr_video_generator.config import load_config
from hpr_video_generator.development import (
    DevelopmentCandidate,
    build_development_filter,
    development_mask_frames,
    estimate_focal_point,
    generate_development_candidate,
    load_development_config,
    prepare_source_pair,
)
from hpr_video_generator.infinity_background import (
    background_effect_frame,
    background_visibility_metrics,
    build_background_context,
    build_infinity_background_filter,
    load_infinity_background_config,
    personalize_infinity_background_recipe,
    require_perceptual_visibility,
    resolve_font_file,
)


ROOT = Path(__file__).resolve().parents[1]


class FakeProcess:
    latest_command = None

    def __init__(self, *args, **kwargs) -> None:
        type(self).latest_command = args[0]
        self.stdin = io.BytesIO()
        self.killed = False

    def wait(self) -> int:
        return 0

    def kill(self) -> None:
        self.killed = True


class DevelopmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.video_config = load_config(ROOT / "config/generator.xml")
        self.development_config = load_development_config(
            ROOT / "config/portrait-development-recipes.json"
        )
        self.round2_config = load_development_config(
            ROOT / "config/portrait-development-round2-recipes.json"
        )
        self.finalist_config = load_development_config(
            ROOT / "config/portrait-development-finalist-recipes.json"
        )
        self.visibility_config = load_development_config(
            ROOT / "config/portrait-development-visibility-recipes.json"
        )
        self.settlement_config = load_development_config(
            ROOT / "config/portrait-development-settlement-recipes.json"
        )
        self.infinity_background_config = load_infinity_background_config(
            ROOT / "config/infinity-background-recipes.json"
        )
        self.infinity_visibility_config = load_infinity_background_config(
            ROOT / "config/infinity-background-visibility-recipes.json"
        )
        self.infinity_concept_config = load_infinity_background_config(
            ROOT / "config/infinity-background-concept-recipes.json"
        )
        self.infinity_flat_config = load_infinity_background_config(
            ROOT / "config/infinity-background-flat-recipes.json"
        )
        self.infinity_directed_config = load_infinity_background_config(
            ROOT / "config/infinity-background-directed-recipes.json"
        )
        self.infinity_palette_config = load_infinity_background_config(
            ROOT / "config/infinity-background-fixed-palette-recipes.json"
        )
        self.infinity_contrast_config = load_infinity_background_config(
            ROOT / "config/infinity-background-contrast-calibration-recipes.json"
        )
        self.infinity_blob_config = load_infinity_background_config(
            ROOT / "config/infinity-background-number-blobs-recipes.json"
        )
        self.infinity_static_blob_config = load_infinity_background_config(
            ROOT / "config/infinity-background-static-number-blobs-recipes.json"
        )
        self.infinity_static_production_config = load_infinity_background_config(
            ROOT / "config/infinity-background-static-production-recipes.json"
        )

    def test_pilot_has_five_fixed_geometry_recipes(self) -> None:
        self.assertEqual("portrait-development-pilot-v5", self.development_config.experiment_id)
        self.assertEqual(
            ["PDA-001", "PDA-002", "PDA-003", "PDA-004", "PDA-005"],
            list(self.development_config.recipes),
        )
        self.assertEqual(
            {"static_reference", "global_development", "activation_field", "soft_sweep"},
            {recipe.mode for recipe in self.development_config.recipes.values()},
        )

    def test_every_mask_is_one_direction_and_closes_exactly(self) -> None:
        width = int(self.development_config.mask["width"])
        height = int(self.development_config.mask["height"])
        for recipe in self.development_config.recipes.values():
            masks, timeline = development_mask_frames(
                recipe,
                seed=123,
                frames=168,
                width=width,
                height=height,
                focal_point=(0.5, 0.45),
                mask_settings=self.development_config.mask,
            )
            self.assertEqual(168, len(masks))
            self.assertEqual(masks[0], masks[-1])
            self.assertTrue(
                all(
                    recipe.base_final_mix <= item["minimumFinalMix"] <= 1
                    and recipe.base_final_mix <= item["maximumFinalMix"] <= 1
                    for item in timeline
                )
            )

    def test_static_reference_is_untouched_finished_source(self) -> None:
        recipe = self.development_config.recipes["PDA-001"]
        masks, timeline = development_mask_frames(
            recipe,
            seed=123,
            frames=12,
            width=27,
            height=48,
            focal_point=(0.5, 0.5),
            mask_settings=self.development_config.mask,
        )
        self.assertTrue(all(set(mask) == {255} for mask in masks))
        self.assertTrue(all(item["meanFinalMix"] == 1 for item in timeline))

    def test_activation_field_has_spatial_range(self) -> None:
        recipe = self.development_config.recipes["PDA-004"]
        _, timeline = development_mask_frames(
            recipe,
            seed=456,
            frames=48,
            width=54,
            height=96,
            focal_point=(0.58, 0.42),
            mask_settings=self.development_config.mask,
        )
        self.assertTrue(
            any(item["maximumFinalMix"] - item["minimumFinalMix"] > 0.12 for item in timeline)
        )

    def test_source_pair_is_aligned_and_under_resolved(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            portrait = root / "portrait.jpg"
            Image.new("RGB", (90, 160), (145, 105, 80)).save(portrait)
            final = root / "final.png"
            surrogate = root / "surrogate.png"
            provenance = prepare_source_pair(
                portrait, final, surrogate, self.development_config.surrogate
            )
            with Image.open(final) as final_image, Image.open(surrogate) as under:
                self.assertEqual(final_image.size, under.size)
                self.assertNotEqual(final_image.getpixel((45, 80)), under.getpixel((45, 80)))
            self.assertEqual(90, provenance["sourceWidth"])
            self.assertTrue(provenance["normalizedFinalSha256"])

    def test_filter_has_no_geometric_animation(self) -> None:
        graph = build_development_filter(self.video_config, 135, 240)
        self.assertIn("maskedmerge", graph)
        self.assertIn("fps=24", graph)
        self.assertIn("gbrp16le", graph)
        self.assertIn("gray16le", graph)
        self.assertIn(
            "setparams=range=limited:color_primaries=bt709:color_trc=bt709:colorspace=bt709",
            graph,
        )
        self.assertNotIn("zoompan", graph)
        self.assertNotIn("rotate", graph)
        self.assertNotIn("displace", graph)

    @patch("hpr_video_generator.development.subprocess.Popen", FakeProcess)
    def test_manifest_records_fixed_geometry_and_exact_telemetry(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            portrait = root / "portrait.jpg"
            Image.new("RGB", (90, 160), (145, 105, 80)).save(portrait)
            output = root / "candidate.mp4"
            generate_development_candidate(
                self.video_config,
                self.development_config,
                DevelopmentCandidate(
                    "POR-TEST",
                    "POR-TEST-R001",
                    portrait,
                    self.development_config.recipes["PDA-003"],
                    789,
                    7,
                    output,
                ),
                ffmpeg="ffmpeg",
            )
            manifest = json.loads(output.with_suffix(".json").read_text())
            self.assertEqual("visual_portrait_development", manifest["candidateType"])
            self.assertEqual("single finished source, one-direction reveal", manifest["sourceModel"])
            self.assertFalse(manifest["overshootAllowed"])
            self.assertTrue(manifest["geometry"]["fixed"])
            self.assertEqual("none", manifest["geometry"]["displacement"])
            self.assertEqual(168, len(manifest["developmentTelemetry"]["frameTimeline"]))
            self.assertTrue(manifest["field"]["firstLastMaskIdentical"])
            command = FakeProcess.latest_command
            self.assertIsNotNone(command)
            self.assertEqual(3, command.count("-framerate"))
            self.assertTrue(
                all(command[index + 1] == "24" for index, item in enumerate(command) if item == "-framerate")
            )

    def test_focal_estimate_is_normalized(self) -> None:
        with TemporaryDirectory() as directory:
            portrait = Path(directory) / "portrait.jpg"
            image = Image.new("RGB", (90, 160), "black")
            for x in range(55, 80):
                for y in range(45, 110):
                    image.putpixel((x, y), (220, 170, 130))
            image.save(portrait)
            x, y = estimate_focal_point(portrait, 54, 96)
            self.assertTrue(0 <= x <= 1)
            self.assertTrue(0 <= y <= 1)

    def test_round_two_has_five_new_traceable_recipes(self) -> None:
        self.assertEqual(
            "portrait-development-tiff-v6", self.round2_config.experiment_id
        )
        self.assertEqual(
            ["PDB-001", "PDB-002", "PDB-003", "PDB-004", "PDB-005"],
            list(self.round2_config.recipes),
        )
        self.assertEqual(
            0.67, self.round2_config.recipes["PDB-002"].base_final_mix
        )
        self.assertEqual(
            0.70, self.round2_config.recipes["PDB-005"].base_final_mix
        )
        self.assertNotEqual(
            self.round2_config.recipes["PDB-003"].speed,
            self.round2_config.recipes["PDB-004"].speed,
        )

    def test_round_two_uses_full_final_rests_and_exact_loop(self) -> None:
        width = int(self.round2_config.mask["width"])
        height = int(self.round2_config.mask["height"])
        for recipe in self.round2_config.recipes.values():
            masks, timeline = development_mask_frames(
                recipe,
                seed=123,
                frames=264,
                width=width,
                height=height,
                focal_point=(0.5, 0.45),
                mask_settings=self.round2_config.mask,
            )
            self.assertEqual(masks[0], masks[-1])
            self.assertEqual({255}, set(masks[0]))
            self.assertTrue(
                all(
                    recipe.base_final_mix <= item["minimumFinalMix"] <= 1
                    and recipe.base_final_mix <= item["maximumFinalMix"] <= 1
                    for item in timeline
                )
            )
        global_timeline = development_mask_frames(
            self.round2_config.recipes["PDB-002"],
            seed=123,
            frames=264,
            width=width,
            height=height,
            focal_point=(0.5, 0.45),
            mask_settings=self.round2_config.mask,
        )[1]
        fully_finished = sum(item["minimumFinalMix"] == 1 for item in global_timeline)
        self.assertGreaterEqual(fully_finished, 130)

    def test_finalist_round_is_narrowed_from_review_notes(self) -> None:
        self.assertEqual(
            "portrait-development-finalist-v7", self.finalist_config.experiment_id
        )
        self.assertEqual(
            ["PDC-001", "PDC-002", "PDC-003"],
            list(self.finalist_config.recipes),
        )
        self.assertEqual(
            {"activation_field", "soft_sweep"},
            {recipe.mode for recipe in self.finalist_config.recipes.values()},
        )
        self.assertTrue(
            all(recipe.finished_hold == 0.128 for recipe in self.finalist_config.recipes.values())
        )
        self.assertEqual(0.50, self.finalist_config.recipes["PDC-003"].base_final_mix)

    def test_finalist_round_has_short_full_final_pause_and_exact_loop(self) -> None:
        width = int(self.finalist_config.mask["width"])
        height = int(self.finalist_config.mask["height"])
        for recipe in self.finalist_config.recipes.values():
            masks, timeline = development_mask_frames(
                recipe,
                seed=123,
                frames=264,
                width=width,
                height=height,
                focal_point=(0.5, 0.45),
                mask_settings=self.finalist_config.mask,
            )
            self.assertEqual(masks[0], masks[-1])
            self.assertEqual({255}, set(masks[0]))
            fully_finished = sum(
                item["minimumFinalMix"] == 1 for item in timeline
            )
            self.assertGreaterEqual(fully_finished, 30)
            self.assertLessEqual(fully_finished, 40)
            self.assertTrue(
                all(
                    recipe.base_final_mix <= item["minimumFinalMix"] <= 1
                    and recipe.base_final_mix <= item["maximumFinalMix"] <= 1
                    for item in timeline
                )
            )

    def test_visibility_round_pushes_every_candidate_harder(self) -> None:
        self.assertEqual(
            "portrait-development-visibility-v8", self.visibility_config.experiment_id
        )
        self.assertEqual(
            ["PDD-001", "PDD-002", "PDD-003"],
            list(self.visibility_config.recipes),
        )
        self.assertTrue(
            all(
                recipe.base_final_mix <= 0.25
                for recipe in self.visibility_config.recipes.values()
            )
        )
        self.assertEqual(0.0, self.visibility_config.recipes["PDD-003"].base_final_mix)
        self.assertLess(
            self.visibility_config.recipes["PDD-002"].feather,
            self.finalist_config.recipes["PDC-002"].feather,
        )

    def test_visibility_round_has_brief_pause_and_exact_loop(self) -> None:
        width = int(self.visibility_config.mask["width"])
        height = int(self.visibility_config.mask["height"])
        for recipe in self.visibility_config.recipes.values():
            masks, timeline = development_mask_frames(
                recipe,
                seed=123,
                frames=264,
                width=width,
                height=height,
                focal_point=(0.5, 0.45),
                mask_settings=self.visibility_config.mask,
            )
            self.assertEqual(masks[0], masks[-1])
            self.assertEqual({255}, set(masks[0]))
            fully_finished = sum(
                item["minimumFinalMix"] == 1 for item in timeline
            )
            self.assertGreaterEqual(fully_finished, 8)
            self.assertLessEqual(fully_finished, 20)
            self.assertTrue(
                all(
                    recipe.base_final_mix <= item["minimumFinalMix"] <= 1
                    and recipe.base_final_mix <= item["maximumFinalMix"] <= 1
                    for item in timeline
                )
            )

    def test_settlement_round_is_exactly_65_percent_toward_visibility(self) -> None:
        self.assertEqual(
            "portrait-development-settlement-v9", self.settlement_config.experiment_id
        )
        self.assertEqual(
            ["PDE-001", "PDE-002", "PDE-003"],
            list(self.settlement_config.recipes),
        )
        pairs = [
            ("PDC-001", "PDD-001", "PDE-001"),
            ("PDC-002", "PDD-002", "PDE-002"),
            ("PDC-003", "PDD-003", "PDE-003"),
        ]
        continuous_fields = [
            "base_final_mix",
            "patch_size_min",
            "patch_size_max",
            "feather",
            "neighbor_coupling",
            "speed",
            "finished_hold",
            "ease_power",
        ]
        for finalist_id, visibility_id, settlement_id in pairs:
            finalist = self.finalist_config.recipes[finalist_id]
            visibility = self.visibility_config.recipes[visibility_id]
            settlement = self.settlement_config.recipes[settlement_id]
            for field in continuous_fields:
                expected = getattr(finalist, field) + 0.65 * (
                    getattr(visibility, field) - getattr(finalist, field)
                )
                self.assertAlmostEqual(expected, getattr(settlement, field), places=6)
        self.assertEqual(4, self.settlement_config.recipes["PDE-001"].patch_count)
        self.assertEqual(5, self.settlement_config.recipes["PDE-003"].patch_count)

    def test_settlement_round_has_intermediate_pause_and_exact_loop(self) -> None:
        width = int(self.settlement_config.mask["width"])
        height = int(self.settlement_config.mask["height"])
        for recipe in self.settlement_config.recipes.values():
            masks, timeline = development_mask_frames(
                recipe,
                seed=123,
                frames=264,
                width=width,
                height=height,
                focal_point=(0.5, 0.45),
                mask_settings=self.settlement_config.mask,
            )
            self.assertEqual(masks[0], masks[-1])
            self.assertEqual({255}, set(masks[0]))
            fully_finished = sum(item["minimumFinalMix"] == 1 for item in timeline)
            self.assertGreaterEqual(fully_finished, 18)
            self.assertLessEqual(fully_finished, 28)
            self.assertTrue(
                all(
                    recipe.base_final_mix <= item["minimumFinalMix"] <= 1
                    and recipe.base_final_mix <= item["maximumFinalMix"] <= 1
                    for item in timeline
                )
            )

    def test_infinity_background_config_has_seven_distinct_effects(self) -> None:
        self.assertEqual(
            "infinity-background-v10", self.infinity_background_config.experiment_id
        )
        self.assertEqual(
            [f"INF-{index:03d}" for index in range(1, 8)],
            list(self.infinity_background_config.recipes),
        )
        self.assertEqual(
            7,
            len(
                {
                    recipe.effect
                    for recipe in self.infinity_background_config.recipes.values()
                }
            ),
        )
        self.assertEqual(
            "PDE-002",
            self.infinity_background_config.base_portrait_treatment[
                "developmentRecipeId"
            ],
        )

    def test_infinity_background_effects_loop_exactly(self) -> None:
        import numpy as np

        height, width = 48, 27
        background = np.full((height, width, 3), 62000, dtype=np.uint16)
        subject = np.zeros((height, width, 3), dtype=np.uint16)
        subject[:, :, 0] = 42000
        subject[:, :, 1] = 30000
        subject[:, :, 2] = 24000
        alpha = np.zeros((height, width), dtype=np.uint16)
        alpha[8:42, 7:22] = 65535
        context = build_background_context(background, subject, alpha)
        for recipe in self.infinity_background_config.recipes.values():
            first = background_effect_frame(recipe, 0.0, context)
            middle = background_effect_frame(recipe, 0.5, context)
            last = background_effect_frame(recipe, 1.0, context)
            self.assertTrue(np.array_equal(first, last), recipe.id)
            self.assertTrue(np.array_equal(first, background), recipe.id)
            metrics = background_visibility_metrics(middle, first)
            self.assertGreater(metrics["meanDelta8Bit"], 0.0, recipe.id)

    def test_infinity_visibility_round_requires_perceptible_display_change(self) -> None:
        self.assertEqual(
            "infinity-background-visibility-v11",
            self.infinity_visibility_config.experiment_id,
        )
        self.assertEqual(
            [f"IBV-{index:03d}" for index in range(1, 8)],
            list(self.infinity_visibility_config.recipes),
        )
        for recipe in self.infinity_visibility_config.recipes.values():
            self.assertGreater(recipe.visibility_boost, 1.0, recipe.id)
            self.assertGreater(
                recipe.perceptual_floor["meanDelta8Bit"], 0.0, recipe.id
            )
            self.assertGreater(
                recipe.perceptual_floor["activePixelsAbove3Percent"],
                0.0,
                recipe.id,
            )
            require_perceptual_visibility(recipe, recipe.perceptual_floor)
            with self.assertRaisesRegex(ValueError, recipe.id):
                require_perceptual_visibility(
                    recipe,
                    {key: 0.0 for key in recipe.perceptual_floor},
                )

    def test_infinity_concept_round_implements_the_seven_sketch_directions(self) -> None:
        self.assertEqual(
            "infinity-background-concepts-v12",
            self.infinity_concept_config.experiment_id,
        )
        self.assertEqual(
            [f"IBC-{index:03d}" for index in range(1, 8)],
            list(self.infinity_concept_config.recipes),
        )
        self.assertEqual(
            {"family": "Brandon Grotesque", "style": "Regular"},
            self.infinity_concept_config.font,
        )
        self.assertEqual(
            {
                "number_depth_field",
                "number_side_streams",
                "number_evasive_corridor",
                "gradient_curtain",
                "sliding_panel",
                "hinged_door",
                "number_doorway",
            },
            {recipe.effect for recipe in self.infinity_concept_config.recipes.values()},
        )
        self.assertTrue(
            all(recipe.parameters for recipe in self.infinity_concept_config.recipes.values())
        )

    def test_font_resolver_uses_internal_family_and_style_names(self) -> None:
        with TemporaryDirectory() as directory:
            font_file = Path(directory) / "licensed-font.otf"
            font_file.touch()
            fake_font = Mock()
            fake_font.getname.return_value = ("Brandon Grotesque", "Regular")
            with patch(
                "hpr_video_generator.infinity_background.ImageFont.truetype",
                return_value=fake_font,
            ):
                resolved = resolve_font_file(
                    "Brandon Grotesque", "Regular", [Path(directory)]
                )
            self.assertEqual(font_file, resolved)

    def test_infinity_concept_frames_are_visible_and_mathematically_loop_safe(self) -> None:
        import numpy as np

        height, width = 192, 108
        background = np.full((height, width, 3), 62000, dtype=np.uint16)
        subject = np.zeros((height, width, 3), dtype=np.uint16)
        subject[:, :, 0] = 42000
        subject[:, :, 1] = 30000
        subject[:, :, 2] = 24000
        alpha = np.zeros((height, width), dtype=np.uint16)
        alpha[28:170, 24:91] = 65535
        context = build_background_context(background, subject, alpha)
        context["fontPath"] = "test-font.otf"
        with patch(
            "hpr_video_generator.infinity_background._font",
            side_effect=lambda _path, size: ImageFont.load_default(size=size),
        ):
            for recipe in self.infinity_concept_config.recipes.values():
                first = background_effect_frame(recipe, 0.0, context)
                middle = background_effect_frame(recipe, 0.5, context)
                last = background_effect_frame(recipe, 1.0, context)
                self.assertTrue(np.array_equal(first, last), recipe.id)
                self.assertGreater(
                    background_visibility_metrics(middle, first)["meanDelta8Bit"],
                    0.25,
                    recipe.id,
                )

    def test_infinity_flat_round_removes_number_depth_and_records_resets(self) -> None:
        self.assertEqual(
            "infinity-background-flat-fields-v13",
            self.infinity_flat_config.experiment_id,
        )
        self.assertEqual(
            [f"IBF-{index:03d}" for index in range(1, 8)],
            list(self.infinity_flat_config.recipes),
        )
        number_effects = {
            recipe.effect
            for recipe in self.infinity_flat_config.recipes.values()
            if "number" in recipe.effect
        }
        self.assertEqual(
            {
                "flat_number_drift",
                "flat_number_grid",
                "flat_number_separation",
                "flat_number_wipe",
            },
            number_effects,
        )
        self.assertFalse(any("depth" in effect for effect in number_effects))
        self.assertEqual(
            {"IBF-006", "IBF-007"},
            {
                recipe.id
                for recipe in self.infinity_flat_config.recipes.values()
                if recipe.loop_behavior == "intentional_hard_reset"
            },
        )

    def test_infinity_flat_fields_keep_size_fixed_and_follow_loop_contract(self) -> None:
        import numpy as np

        height, width = 192, 108
        background = np.full((height, width, 3), 62000, dtype=np.uint16)
        subject = np.zeros((height, width, 3), dtype=np.uint16)
        subject[:, :, :] = [42000, 30000, 24000]
        alpha = np.zeros((height, width), dtype=np.uint16)
        alpha[28:170, 24:91] = 65535
        context = build_background_context(background, subject, alpha)
        context["fontPath"] = "test-font.otf"
        with patch(
            "hpr_video_generator.infinity_background._font",
            side_effect=lambda _path, size: ImageFont.load_default(size=size),
        ):
            for recipe in self.infinity_flat_config.recipes.values():
                first = background_effect_frame(recipe, 0.0, context)
                middle = background_effect_frame(recipe, 0.5, context)
                last = background_effect_frame(recipe, 1.0, context)
                if recipe.loop_behavior == "continuous":
                    self.assertTrue(np.array_equal(first, last), recipe.id)
                else:
                    self.assertFalse(np.array_equal(first, last), recipe.id)
                self.assertGreater(
                    background_visibility_metrics(middle, first)["meanDelta8Bit"],
                    0.25,
                    recipe.id,
                )

    def test_infinity_directed_round_translates_every_review_decision(self) -> None:
        config = self.infinity_directed_config
        self.assertEqual(
            "infinity-background-directed-variations-v14",
            config.experiment_id,
        )
        self.assertEqual(
            [f"IBR-{index:03d}" for index in range(1, 12)],
            list(config.recipes),
        )
        self.assertEqual("Bold", config.font["style"])
        self.assertNotIn(
            "flat_number_separation",
            {recipe.effect for recipe in config.recipes.values()},
        )
        dense = config.recipes["IBR-001"]
        self.assertEqual(420, dense.parameters["columns"] * dense.parameters["rows"])
        self.assertEqual(dense.parameters["minimumSize"], dense.parameters["maximumSize"])
        self.assertTrue(dense.parameters["balancedRandomDigits"])
        self.assertEqual(
            [0.22, 0.30],
            [config.recipes[key].speed for key in ("IBR-002", "IBR-003")],
        )
        self.assertEqual(
            [0.0, 90.0, 31.0],
            [
                config.recipes[key].parameters["angleDegrees"]
                for key in ("IBR-004", "IBR-005", "IBR-006")
            ],
        )
        self.assertTrue(config.recipes["IBR-007"].parameters["oneWay"])
        self.assertTrue(config.recipes["IBR-008"].parameters["oneWay"])
        self.assertEqual(2.4, config.recipes["IBR-009"].parameters["easingExponent"])
        self.assertEqual(
            ["static", "linear_left"],
            [
                config.recipes[key].parameters["numberMotion"]
                for key in ("IBR-010", "IBR-011")
            ],
        )
        self.assertEqual(
            {f"IBR-{index:03d}" for index in range(7, 12)},
            {
                recipe.id
                for recipe in config.recipes.values()
                if recipe.loop_behavior == "intentional_hard_reset"
            },
        )

    def test_infinity_directed_frames_follow_the_recorded_loop_contract(self) -> None:
        import numpy as np

        height, width = 192, 108
        background = np.full((height, width, 3), 62000, dtype=np.uint16)
        subject = np.zeros((height, width, 3), dtype=np.uint16)
        subject[:, :, :] = [42000, 30000, 24000]
        alpha = np.zeros((height, width), dtype=np.uint16)
        alpha[28:170, 24:91] = 65535
        context = build_background_context(background, subject, alpha)
        context["fontPath"] = "test-font.otf"
        with patch(
            "hpr_video_generator.infinity_background._font",
            side_effect=lambda _path, size: ImageFont.load_default(size=size),
        ):
            for recipe in self.infinity_directed_config.recipes.values():
                first = background_effect_frame(recipe, 0.0, context)
                middle = background_effect_frame(recipe, 0.5, context)
                last = background_effect_frame(recipe, 1.0, context)
                if recipe.loop_behavior == "continuous":
                    self.assertTrue(np.array_equal(first, last), recipe.id)
                else:
                    self.assertFalse(np.array_equal(first, last), recipe.id)
                self.assertGreater(
                    background_visibility_metrics(middle, first)["meanDelta8Bit"],
                    0.25,
                    recipe.id,
                )

    def test_infinity_palette_round_uses_only_the_two_requested_colors(self) -> None:
        config = self.infinity_palette_config
        self.assertEqual("infinity-background-fixed-palette-v15", config.experiment_id)
        self.assertEqual(
            [f"IBP-{index:03d}" for index in range(1, 12)],
            list(config.recipes),
        )
        requested_palette = {
            (0.941176, 0.933333, 0.913725),
            (0.968627, 0.960784, 0.937255),
        }
        color_keys = {
            "backgroundColor",
            "color",
            "colorA",
            "colorB",
            "numberColor",
            "panelColor",
        }
        used_colors = {
            tuple(value)
            for recipe in config.recipes.values()
            for key, value in recipe.parameters.items()
            if key in color_keys
        }
        self.assertEqual(requested_palette, used_colors)
        self.assertEqual(
            [0.10, 0.14],
            [config.recipes[key].speed for key in ("IBP-002", "IBP-003")],
        )
        self.assertTrue(config.recipes["IBP-002"].parameters["bleedEdges"])
        self.assertTrue(config.recipes["IBP-003"].parameters["bleedEdges"])
        self.assertEqual(
            [1.7, 2.6],
            [
                config.recipes[key].parameters["easingExponent"]
                for key in ("IBP-007", "IBP-008")
            ],
        )
        self.assertEqual(4.0, config.recipes["IBP-009"].parameters["featherPixels"])
        self.assertEqual(
            ["random", "random"],
            [
                config.recipes[key].parameters["positionLayout"]
                for key in ("IBP-010", "IBP-011")
            ],
        )
        self.assertEqual(
            ["static", "linear_right"],
            [
                config.recipes[key].parameters["numberMotion"]
                for key in ("IBP-010", "IBP-011")
            ],
        )

    def test_infinity_palette_frames_follow_the_recorded_loop_contract(self) -> None:
        import numpy as np

        height, width = 192, 108
        background = np.full((height, width, 3), 62000, dtype=np.uint16)
        subject = np.zeros((height, width, 3), dtype=np.uint16)
        subject[:, :, :] = [42000, 30000, 24000]
        alpha = np.zeros((height, width), dtype=np.uint16)
        alpha[28:170, 24:91] = 65535
        context = build_background_context(background, subject, alpha)
        context["fontPath"] = "test-font.otf"
        with patch(
            "hpr_video_generator.infinity_background._font",
            side_effect=lambda _path, size: ImageFont.load_default(size=size),
        ):
            for recipe in self.infinity_palette_config.recipes.values():
                first = background_effect_frame(recipe, 0.0, context)
                middle = background_effect_frame(recipe, 0.5, context)
                last = background_effect_frame(recipe, 1.0, context)
                if recipe.loop_behavior == "continuous":
                    self.assertTrue(np.array_equal(first, last), recipe.id)
                else:
                    self.assertFalse(np.array_equal(first, last), recipe.id)
                self.assertGreater(
                    background_visibility_metrics(middle, first)["meanDelta8Bit"],
                    0.10,
                    recipe.id,
                )

    def test_infinity_contrast_calibration_is_three_matched_pairs(self) -> None:
        config = self.infinity_contrast_config
        self.assertEqual(
            "infinity-background-contrast-calibration-v16",
            config.experiment_id,
        )
        self.assertEqual(
            [f"IBK-{index:03d}" for index in range(1, 7)],
            list(config.recipes),
        )
        light = (0.968627, 0.960784, 0.937255)
        darker = [
            (0.929412, 0.917647, 0.890196),
            (0.909804, 0.894118, 0.862745),
            (0.886275, 0.866667, 0.831373),
        ]
        for pair_index, dark in enumerate(darker):
            numbers = config.recipes[f"IBK-{pair_index * 2 + 1:03d}"]
            panel = config.recipes[f"IBK-{pair_index * 2 + 2:03d}"]
            self.assertEqual("flat_number_grid", numbers.effect)
            self.assertEqual("sliding_panel_full", panel.effect)
            self.assertEqual(light, tuple(numbers.parameters["backgroundColor"]))
            self.assertEqual(light, tuple(panel.parameters["backgroundColor"]))
            self.assertEqual(dark, tuple(numbers.parameters["color"]))
            self.assertEqual(dark, tuple(panel.parameters["color"]))
            self.assertEqual(1.0, numbers.parameters["maximumMix"])
            self.assertEqual(1.0, panel.parameters["maximumMix"])

    def test_infinity_contrast_panels_reach_the_recorded_color_endpoint(self) -> None:
        import numpy as np

        height, width = 192, 108
        background = np.full((height, width, 3), 62000, dtype=np.uint16)
        subject = np.zeros((height, width, 3), dtype=np.uint16)
        alpha = np.zeros((height, width), dtype=np.uint16)
        context = build_background_context(background, subject, alpha)
        for recipe_id in ("IBK-002", "IBK-004", "IBK-006"):
            recipe = self.infinity_contrast_config.recipes[recipe_id]
            final_frame = background_effect_frame(recipe, 1.0, context)
            expected = np.rint(
                np.asarray(recipe.parameters["color"]) * 65535.0
            ).astype(np.uint16)
            self.assertTrue(
                np.allclose(final_frame[-1, -1], expected, atol=1),
                recipe.id,
            )

    def test_infinity_number_phase_varies_start_without_changing_loop(self) -> None:
        import numpy as np

        height, width = 192, 108
        background = np.full((height, width, 3), 62000, dtype=np.uint16)
        subject = np.zeros((height, width, 3), dtype=np.uint16)
        alpha = np.zeros((height, width), dtype=np.uint16)
        context = build_background_context(background, subject, alpha)
        context["fontPath"] = "test-font.otf"
        reference = self.infinity_contrast_config.recipes["IBK-001"]
        phased = replace(
            reference,
            parameters={**reference.parameters, "phaseOffset": 0.37},
        )
        with patch(
            "hpr_video_generator.infinity_background._font",
            side_effect=lambda _path, size: ImageFont.load_default(size=size),
        ):
            reference_start = background_effect_frame(reference, 0.0, context)
            phased_start = background_effect_frame(phased, 0.0, context)
            phased_end = background_effect_frame(phased, 1.0, context)
        self.assertFalse(np.array_equal(reference_start, phased_start))
        self.assertTrue(np.array_equal(phased_start, phased_end))

    def test_infinity_blob_round_changes_only_the_nested_blob_count(self) -> None:
        config = self.infinity_blob_config
        self.assertEqual("infinity-background-number-blobs-v17", config.experiment_id)
        self.assertEqual(
            ["IBL-001", "IBL-002", "IBL-003"],
            list(config.recipes),
        )
        ignored = {"blobCount"}
        reference = config.recipes["IBL-001"]
        for index, recipe in enumerate(config.recipes.values(), start=1):
            self.assertEqual("flat_number_blobs", recipe.effect)
            self.assertEqual(index, recipe.parameters["blobCount"])
            self.assertEqual(
                {key: value for key, value in reference.parameters.items() if key not in ignored},
                {key: value for key, value in recipe.parameters.items() if key not in ignored},
            )
            self.assertEqual("continuous", recipe.loop_behavior)

    def test_infinity_blob_round_is_visible_nested_and_exactly_closed(self) -> None:
        import numpy as np

        height, width = 192, 108
        background = np.full((height, width, 3), 62000, dtype=np.uint16)
        subject = np.zeros((height, width, 3), dtype=np.uint16)
        alpha = np.zeros((height, width), dtype=np.uint16)
        context = build_background_context(background, subject, alpha)
        context["fontPath"] = "test-font.otf"
        mid_deltas = []
        with patch(
            "hpr_video_generator.infinity_background._font",
            side_effect=lambda _path, size: ImageFont.load_default(size=size),
        ):
            for recipe in self.infinity_blob_config.recipes.values():
                first = background_effect_frame(recipe, 0.0, context)
                middle = background_effect_frame(recipe, 0.5, context)
                last = background_effect_frame(recipe, 1.0, context)
                self.assertTrue(np.array_equal(first, last), recipe.id)
                baseline = np.broadcast_to(
                    np.rint(
                        np.asarray(recipe.parameters["backgroundColor"]) * 65535.0
                    ).astype(np.uint16),
                    middle.shape,
                )
                mid_deltas.append(
                    background_visibility_metrics(middle, baseline)["meanDelta8Bit"]
                )
        self.assertEqual(sorted(mid_deltas), mid_deltas)
        self.assertGreater(mid_deltas[0], 0.1)

    def test_infinity_static_blob_round_changes_only_number_motion(self) -> None:
        config = self.infinity_static_blob_config
        self.assertEqual(
            "infinity-background-static-number-blobs-v18",
            config.experiment_id,
        )
        self.assertEqual(
            ["IBS-001", "IBS-002", "IBS-003"],
            list(config.recipes),
        )
        for index, recipe in enumerate(config.recipes.values(), start=1):
            moving = self.infinity_blob_config.recipes[f"IBL-{index:03d}"]
            expected = dict(moving.parameters)
            expected["numberMotion"] = "static"
            self.assertEqual(expected, recipe.parameters)
            self.assertEqual(index, recipe.parameters["blobCount"])
            self.assertEqual("continuous", recipe.loop_behavior)

    def test_infinity_static_blob_round_is_visible_and_exactly_closed(self) -> None:
        import numpy as np

        height, width = 192, 108
        background = np.full((height, width, 3), 62000, dtype=np.uint16)
        subject = np.zeros((height, width, 3), dtype=np.uint16)
        alpha = np.zeros((height, width), dtype=np.uint16)
        context = build_background_context(background, subject, alpha)
        context["fontPath"] = "test-font.otf"
        with patch(
            "hpr_video_generator.infinity_background._font",
            side_effect=lambda _path, size: ImageFont.load_default(size=size),
        ):
            for recipe in self.infinity_static_blob_config.recipes.values():
                first = background_effect_frame(recipe, 0.0, context)
                middle = background_effect_frame(recipe, 0.5, context)
                last = background_effect_frame(recipe, 1.0, context)
                self.assertTrue(np.array_equal(first, last), recipe.id)
                self.assertGreater(
                    background_visibility_metrics(middle, first)["meanDelta8Bit"],
                    0.1,
                    recipe.id,
                )

    def test_infinity_production_number_field_is_static_and_portrait_unique(self) -> None:
        import numpy as np

        config = self.infinity_static_production_config
        self.assertEqual("infinity-background-static-production-v26", config.experiment_id)
        self.assertEqual(["IBN-001"], list(config.recipes))
        configured = config.recipes["IBN-001"]
        self.assertEqual(0.0, configured.speed)
        self.assertEqual("static", configured.parameters["numberMotion"])
        first_portrait = personalize_infinity_background_recipe(configured, "POR-FIRST")
        second_portrait = personalize_infinity_background_recipe(configured, "POR-SECOND")
        self.assertNotEqual(
            first_portrait.parameters["numberSeed"],
            second_portrait.parameters["numberSeed"],
        )

        height, width = 192, 108
        background = np.full((height, width, 3), 62000, dtype=np.uint16)
        subject = np.zeros((height, width, 3), dtype=np.uint16)
        alpha = np.zeros((height, width), dtype=np.uint16)
        context = build_background_context(background, subject, alpha)
        context["fontPath"] = "test-font.otf"
        with patch(
            "hpr_video_generator.infinity_background._font",
            side_effect=lambda _path, size: ImageFont.load_default(size=size),
        ):
            first_start = background_effect_frame(first_portrait, 0.0, context)
            first_middle = background_effect_frame(first_portrait, 0.5, context)
            first_end = background_effect_frame(first_portrait, 1.0, context)
            second_start = background_effect_frame(second_portrait, 0.0, context)
        self.assertTrue(np.array_equal(first_start, first_middle))
        self.assertTrue(np.array_equal(first_start, first_end))
        self.assertFalse(np.array_equal(first_start, second_start))
        self.assertGreater(
            background_visibility_metrics(first_start, background)["meanDelta8Bit"],
            0.25,
        )

    def test_infinity_background_filter_preserves_subject_geometry(self) -> None:
        graph = build_infinity_background_filter(self.video_config, 135, 240)
        self.assertEqual(2, graph.count("maskedmerge"))
        self.assertIn("alphaextract", graph)
        self.assertIn("gbrp16le", graph)
        self.assertIn("fps=24", graph)
        self.assertNotIn("zoompan", graph)
        self.assertNotIn("rotate", graph)
        self.assertNotIn("displace", graph)


if __name__ == "__main__":
    unittest.main()
