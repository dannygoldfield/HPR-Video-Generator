# Motion Rhythm pilot

Status: historical research. Camera-motion testing has been superseded by
[Portrait Development Animation](PORTRAIT-DEVELOPMENT-ANIMATION.md) as the
active HPR visual direction.

The pilot separates movement timing from movement amplitude. All five recipes
use the same restrained scale range (`1.025`–`1.0325`) so Danny can compare the
rhythm rather than being distracted by a larger or smaller move.

| Recipe | Rhythm |
| --- | --- |
| `MR-001` | Current smooth cosine baseline |
| `MR-002` | Slow, slightly faster, then slow variable-speed movement |
| `MR-003` | Approach, one-second-equivalent hold, then return |
| `MR-004` | Two small stages separated by near-stillness |
| `MR-005` | Longer gradual approach and shorter return |

Each recipe is a versioned list of normalized-time keyframes. Every keyframe
records scale, horizontal and vertical fractions, and the easing curve leading
to the next keyframe. The first and final states must match exactly.

The render manifest expands normalized times into exact frame numbers and
seconds for the chosen duration and frame rate. It also records the portrait
revision, source checksum, recipe and configuration versions, seed, complete
FFmpeg filter graph, and output path.

The first 15 candidates are seven-second silent motion-isolation tests: five
recipes for each of the three pilot portraits. Grain is deliberately omitted
so the review measures rhythm. The selected motion can later be rerendered with
the approved grain treatment and paired audio.

## Motion-variable round 2

The first review selected MR-005 timing for the children and MIT Infinity
portraits, and MR-004 timing for the centenarian. Round 2 preserves each of
those portrait-specific rhythms as the reference and changes one dimension at
a time:

| Probe | Change from selected reference |
| --- | --- |
| Lower scale amplitude | Half the reference's scale-change range |
| Higher scale amplitude | One-and-a-half times the scale-change range |
| Horizontal micro-movement | Constant scale with up to `0.004` horizontal frame fraction |
| Vertical micro-movement | Constant scale with up to `0.003` vertical frame fraction |

The three existing references plus 12 new renders form 15 comparisons. New
candidates link to their reference through `parent_visual_id`, retain the same
portrait revision and duration, and carry `experimentId` and exact variable
parameters in their manifests. Grain and audio remain off.
