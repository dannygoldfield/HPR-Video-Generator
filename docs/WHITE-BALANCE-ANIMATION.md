# White Balance animation pilot

Status: historical research that helped reveal the current direction. The
active plan reveals one authoritative finished Lightroom export from a
deterministic under-resolved surrogate within fixed-geometry
[Portrait Development Animation](PORTRAIT-DEVELOPMENT-ANIMATION.md).

White Balance round 3 tests an animation language inspired by manually refining
a portrait in Lightroom Classic. The finished video contains only the portrait
and its evolving color. It does not contain a Lightroom interface, controls,
labels, cursor, audio, grain, text, or geometric movement.

## Review reference

The local review page shows read-only Temperature and Tint sliders below the
video. They are driven by the same exact 168-frame timeline used to render the
color changes, so pausing a video provides a precise value for feedback.

The values are deliberately named **HPR white-balance deltas**. They are not
Lightroom slider units and should not be used as a claim about Lightroom's
internal color processing.

- `0` is the approved JPEG exported from Lightroom Classic.
- Negative Temperature is cooler; positive Temperature is warmer.
- Negative Tint is greener; positive Tint is more magenta.
- The pilot range is `-10` through `+10`.

The numeric reference lets a review note identify a change precisely—for
example, “keep WBP-002 but change the warm peak from +6 to +4.”

## Pilot recipes

| Recipe | Isolated question |
| --- | --- |
| `WBP-001` | Does the unchanged approved export remain the best reference? |
| `WBP-002` | How does a cool-to-warm Temperature search feel? |
| `WBP-003` | How does a green-to-magenta Tint search feel? |
| `WBP-004` | Does Temperature followed by Tint resemble a natural editing process? |
| `WBP-005` | Does coupled, smaller Temperature/Tint fine-tuning feel more organic? |

Each seven-second candidate has 168 exact frames at 24 fps. The first and last
frames use zero Temperature and Tint deltas so the loop returns to the approved
JPEG. `WBP-001` is the static color reference; the other four animate only
color.

## Reproducibility

Every manifest records the portrait and revision IDs, source checksum, recipe
and configuration versions, keyframes, complete frame timeline, RGB gain
mapping, generated per-frame command file and checksum, filter graph, and
output path. The review sliders read that same manifest rather than estimating
values from the encoded video.

The gain mapping is intentionally small and predictable for this pilot. It is a
creative animation control, not a replacement for Danny's authoritative
Lightroom correction. A later round may add selected Tone or Transform
variables after the Temperature/Tint behavior is reviewed.

## Extreme boundary test

The separately versioned `white-balance-extreme-v4` experiment preserves round
3 and repeats its five-part comparison with `WBE-001` through `WBE-005`.
Temperature-only and Tint-only searches reach approximately `-100` and `+100`;
the sequential and coupled recipes use slightly smaller extreme combinations.
The resulting RGB channel gains span approximately `0.85` through `1.15`, making
the color direction unmistakable while retaining a valid, neutral loop seam.

The extreme round is diagnostic, not a proposed production intensity. Danny can
use it to identify the promising direction and then specify a much narrower
range for the next test. All 15 extreme candidates remain image-only and use
the same exact frame-synchronized external slider interface.
