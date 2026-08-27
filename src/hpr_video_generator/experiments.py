from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .rhythm import (
    MotionKeyframe,
    MotionRecipe,
    validate_recipe,
)


@dataclass(frozen=True)
class MotionVariableVariant:
    recipe: MotionRecipe
    variable: str
    parameters: dict[str, Any]


def _scale_variant(
    base: MotionRecipe,
    *,
    suffix: str,
    name: str,
    factor: float,
) -> MotionVariableVariant:
    minimum = min(keyframe.scale for keyframe in base.keyframes)
    maximum = max(keyframe.scale for keyframe in base.keyframes)
    keyframes = tuple(
        MotionKeyframe(
            time=keyframe.time,
            scale=minimum + (keyframe.scale - minimum) * factor,
            x=0.0,
            y=0.0,
            easing_to_next=keyframe.easing_to_next,
        )
        for keyframe in base.keyframes
    )
    recipe = MotionRecipe(
        id=f"MV2-{base.id.replace('-', '')}-{suffix}",
        name=f"{name} using {base.id} timing",
        rhythm_type=f"motion_variable_{suffix.lower().replace('-', '_')}",
        loop_safe=True,
        holds=base.holds,
        keyframes=keyframes,
    )
    validate_recipe(recipe)
    return MotionVariableVariant(
        recipe=recipe,
        variable="scale_amplitude",
        parameters={
            "sourceRhythmId": base.id,
            "scaleAmplitudeFactor": factor,
            "minimumScale": minimum,
            "sourceMaximumScale": maximum,
            "maximumScale": max(keyframe.scale for keyframe in keyframes),
        },
    )


def _position_variant(
    base: MotionRecipe,
    *,
    suffix: str,
    name: str,
    axis: str,
    fraction: float,
) -> MotionVariableVariant:
    minimum = min(keyframe.scale for keyframe in base.keyframes)
    maximum = max(keyframe.scale for keyframe in base.keyframes)
    amplitude = maximum - minimum
    if amplitude <= 0:
        raise ValueError(f"{base.id} needs scale movement to derive position timing")
    keyframes = []
    for keyframe in base.keyframes:
        progress = (keyframe.scale - minimum) / amplitude
        keyframes.append(
            MotionKeyframe(
                time=keyframe.time,
                scale=minimum,
                x=fraction * progress if axis == "horizontal" else 0.0,
                y=fraction * progress if axis == "vertical" else 0.0,
                easing_to_next=keyframe.easing_to_next,
            )
        )
    recipe = MotionRecipe(
        id=f"MV2-{base.id.replace('-', '')}-{suffix}",
        name=f"{name} using {base.id} timing",
        rhythm_type=f"motion_variable_{suffix.lower().replace('-', '_')}",
        loop_safe=True,
        holds=base.holds,
        keyframes=tuple(keyframes),
    )
    validate_recipe(recipe)
    return MotionVariableVariant(
        recipe=recipe,
        variable="position_axis",
        parameters={
            "sourceRhythmId": base.id,
            "axis": axis,
            "maximumPositionFraction": fraction,
            "scaleMode": "constant",
            "constantScale": minimum,
        },
    )


def derive_motion_variable_variants(
    base: MotionRecipe,
) -> tuple[MotionVariableVariant, ...]:
    """Derive four one-variable probes from a successful timing rhythm."""
    return (
        _scale_variant(
            base,
            suffix="LOW-SCALE",
            name="Lower scale amplitude",
            factor=0.5,
        ),
        _scale_variant(
            base,
            suffix="HIGH-SCALE",
            name="Higher scale amplitude",
            factor=1.5,
        ),
        _position_variant(
            base,
            suffix="HORIZONTAL",
            name="Horizontal micro-movement only",
            axis="horizontal",
            fraction=0.004,
        ),
        _position_variant(
            base,
            suffix="VERTICAL",
            name="Vertical micro-movement only",
            axis="vertical",
            fraction=0.003,
        ),
    )
