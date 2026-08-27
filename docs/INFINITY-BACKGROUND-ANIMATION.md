# Infinity Background Animation

## Decision context

The portrait-surface treatment is no longer a variable in this experiment.
`PDE-002`, the settled soft sweep, received five stars for all three pilot
portraits. Infinity alone has a separately supplied background layer, so this
round tests whether restrained background activity adds presence without
turning the portrait into an illustration.

## Source contract

- Layered TIFF: `26-Sam-359-LAYERS.tif`
- 2104 × 3740, 16 bits per channel, ProPhoto RGB
- Two visible layers: `Subject` and `Background`
- Subject has real transparency from 0 through fully opaque
- Existing light Background layer remains the foundation of every treatment
- Source TIFF is never modified

Photoshop exports 16-bit working copies of both layers. The layer pixels inherit
the authoritative TIFF's embedded ProPhoto RGB profile, then use the same
LittleCMS 16-bit conversion to sRGB as the portrait-development pipeline.

## Controlled comparison

| ID | Treatment | Intended reading |
| --- | --- | --- |
| `INF-001` | Momentum wake | The background registers the pose's implied direction without a literal trail. |
| `INF-002` | Photographic emulsion bloom | Local photographic density emerges and recedes in large organic regions. |
| `INF-003` | Floating photographic print | A soft changing cast shadow makes the cutout feel fractionally suspended. |
| `INF-004` | Negative-space aperture | Empty space opens around the face and gesture while the periphery gains density. |
| `INF-005` | Residual gesture | Faint displaced impressions suggest that the background remembers another instant. |
| `INF-006` | Incomplete geometry | Sparse arcs, points, and relationships appear without explaining themselves. |
| `INF-007` | Borrowed-color field | Large atmospheric regions borrow restrained skin and clothing colors. |

## Visibility-calibration round

The first `INF` render proved that seven files could be technically different
while remaining perceptually identical at the 280-pixel review size. Several
delivered backgrounds changed by an average of only one or two 8-bit display
codes. The original unit test also used a one-code threshold in 16-bit space,
which established mathematical non-identity rather than visible difference.

`infinity-background-visibility-v11` preserves those seven concepts under new
`IBV` identifiers so the failed round remains reproducible. Every recipe now
declares a visibility boost and three minimum display-scale measures:

- mean RGB change in familiar 8-bit code values;
- 95th-percentile RGB change;
- percentage of background pixels whose mean RGB change exceeds three codes.

The renderer refuses a candidate before compositing if any declared minimum is
missed. The seven delivered candidates span approximately 2.2–17.0 mean 8-bit
codes on the uncovered background at peak activity. The sparse geometry option
is intentionally localized; the other six affect broad areas. This is a
calibration round, so an option may be conspicuously too strong.

Human review nevertheless found only one of the seven effects visibly distinct,
and even that one was weak. The analytic floors measured pixel change but did
not prove that a viewer could recognize a coherent event. `IBV` is therefore a
second failed creative test and remains available as evidence; it is not a
candidate-final round.

| ID | Treatment | Boundary being tested |
| --- | --- | --- |
| `IBV-001` | Visible momentum wake | Directional warmth behind the gesture |
| `IBV-002` | Visible emulsion bloom | Broad overlapping photographic density |
| `IBV-003` | Visible floating print | Dimensional shadow versus cutout artifact |
| `IBV-004` | Visible negative-space aperture | Portrait vignette versus spotlight |
| `IBV-005` | Visible residual gesture | Remembered movement versus echo effect |
| `IBV-006` | Visible incomplete geometry | Relational graphic versus explanatory diagram |
| `IBV-007` | Visible borrowed-color field | Chromatic atmosphere versus tinted backdrop |

## Sketch-directed concept round

The `infinity-background-concepts-v12` round replaces abstract tonal variants
with seven explicit spatial constructions derived from Danny's Photoshop
sketches. These are not seven strengths of one effect. Each tests a different
idea and must be recognizable in an ordinary mobile-size frame before artistic
subtlety is considered.

| ID | Construction | What changes behind the subject |
| --- | --- | --- |
| `IBC-001` | Deep number field | Individual digits at several apparent depths recede toward a vanishing area. |
| `IBC-002` | Side-entering numbers | Digits enter from both side edges and diminish into depth. |
| `IBC-003` | Evasive number corridor | Larger digits curve around the pose and disappear behind the isolated subject. |
| `IBC-004` | Moving gradient curtain | A broad, low-contrast tonal curtain crosses the light field and returns. |
| `IBC-005` | Sliding panel | A legible vertical edge carries a two-dimensional panel across the background. |
| `IBC-006` | Hinged perspective door | A plane stays fixed to its left hinge while its far edge contracts away from the viewer. |
| `IBC-007` | Number doorway | Two perspective panels open to reveal a receding numerical field. |

The digits are the separate characters `1` through `9` and `0`, not multi-digit
numbers, set in Brandon Grotesque Regular. The renderer resolves the locally
licensed Adobe font by its internal family and style name. It records that name
and a local provenance hash in each private render manifest but never copies the
font file into the repository.

This round deliberately permits obvious graphic structure. A successful test
can later be softened; another imperceptible test cannot be meaningfully judged.
The subject remains in front of every construction, so its transparency creates
the apparent occlusion without moving or warping the person.

## Flat-field response round

Review of `IBC-001`–`IBC-007` established a useful direction and a firm
correction: digits should be read as a two-dimensional graphic system, not as
objects traveling toward or away from the viewer. The
`infinity-background-flat-fields-v13` round therefore removes every number
z-axis cue. Each digit receives its size and opacity once; neither value changes
during the video. No digit is emphasized to match the `26` on the hand prop.

| ID | Construction | Review note translated into motion |
| --- | --- | --- |
| `IBF-001` | Dense varied-size 2D drift | Many more digits; evenly distributed fixed sizes; slow independent x-y drift. |
| `IBF-002` | Dense same-size 2D plane | One fixed digit size; the entire flat field moves slowly in and out of frame. |
| `IBF-003` | Orderly 2D separation field | A larger, orderly field separates laterally around the subject without scaling. |
| `IBF-004` | Visible 2D gradient curtain | A stronger two-tone gradient crosses the full background and returns. |
| `IBF-005` | Full-width sliding panel | The panel enters from the right, reaches the opposite edge, and returns with easing over 11 seconds. |
| `IBF-006` | Eleven-second hinged door | One door opens for the full video, disappears, then deliberately resets at the loop. |
| `IBF-007` | Dense 2D number wipe | A right-to-left panel erases a very dense flat field, followed by a deliberate loop reset. |

The first five options remain continuous loops. The last two explicitly test an
abrupt replay cue requested in review; their manifests use
`intentional_hard_reset` rather than falsely describing them as seamless.

## Directed-variation response round

Review of v13 rejected `IBF-003` without a requested repair and generated more
than seven independent tests. The v14 `IBR` family therefore contains eleven
candidates instead of forcing the feedback back into a seven-item template.

| ID | Construction | Recorded review decision |
| --- | --- | --- |
| `IBR-001` | Dense overlapping number loop | 420 bold, equal-size digits; balanced `1`–`9` and `0`; more than 50% active background; one-quarter movement magnitude; exact closed path. |
| `IBR-002` | Coordinated slow number columns | Close columns move as one plane at a saved uniform speed. |
| `IBR-003` | Coordinated columns, reversed palette | Same planar rule with lighter numbers on a darker field and a second saved speed. |
| `IBR-004` | Reversed-color curtain | Horizontal curtain with the two tones exchanged. |
| `IBR-005` | Top-to-bottom curtain | The curtain projection is rotated to 90 degrees. |
| `IBR-006` | Angled curtain | One reproducible 31-degree assignment demonstrates randomized production direction. |
| `IBR-007` | Light warm one-way panel | Completes one crossing in 11 seconds, then cuts to the all-light first frame. |
| `IBR-008` | Quiet neutral one-way panel | Same motion with a second fixed lightness pair. |
| `IBR-009` | Accelerating hinged door | A 2.4-power ease begins slowly and increases speed most strongly near the end. |
| `IBR-010` | Static-number accelerating wipe | Dense equal-size numbers stay fixed while the wipe accelerates. |
| `IBR-011` | Moving-number accelerating wipe | Every number moves left at the same velocity while the same wipe accelerates. |

Brandon Grotesque Bold is used for every v14 number field. Balanced random digit
assembly is deterministic, and all angles, colors, lightness values, speeds,
and easing exponents are stored in the recipe and output manifest. The first
six candidates close continuously. `IBR-007`–`IBR-011` deliberately hard-reset
so replay itself can be judged as a possible invitation to watch again.

## Fixed-palette correction round

V14 review repeatedly requested less contrast and then supplied the exact
palette. V15 treats that palette as a constraint rather than a suggestion:

- darker endpoint: `#f0eee9`
- lighter endpoint: `#f7f5ef`

Every background, digit, curtain, panel, and door color in `IBP-001`–`IBP-011`
is one of those endpoints. Antialiasing and motion feathering may interpolate
between them, but no third design color is permitted. The widest endpoint
contrast is only seven 8-bit RGB code values.

The remaining notes are translated directly: column motion is reduced again;
partial columns touch every frame edge; panel variants compare 1.7- and
2.6-power acceleration; the door feather grows from 0.6 to 4 working pixels;
wipe numbers use deterministic random x-y placement instead of rows and
columns; and `IBP-011` moves its number field right while the wipe travels left.
All eleven remain 11-second, image-only, fixed-subject comparisons using the
same `PDE-002` treatment.

## Contrast-survival calibration

Mobile review of v15 showed that `#f0eee9` and `#f7f5ef` were visually
indistinguishable in every delivered candidate. Their channel differences are
only seven, seven, and six 8-bit code values, and the generator's normal
half-strength color-mix ceiling reduced the rendered difference again before
H.264 encoding and display scaling.

V16 therefore isolates the contrast question before rebuilding eleven creative
effects. `IBK-001`–`IBK-006` hold the light endpoint at `#f7f5ef` and compare
three darker endpoints in matched pairs:

| Pair | Thin number field | Broad panel | Darker endpoint |
| --- | --- | --- | --- |
| Subtle | `IBK-001` | `IBK-002` | `#edeae3` |
| Middle | `IBK-003` | `IBK-004` | `#e8e4dc` |
| Stronger | `IBK-005` | `IBK-006` | `#e2ddd4` |

Motion, timing, typography, subject, and `PDE-002` stay constant within each
construction. `maximumMix: 1.0` is explicitly recorded in all six manifests so
opaque digit interiors and fully covered panel regions reach the specified
darker endpoint instead of stopping at a half-strength interpolation. The
number fields close continuously; the one-way panels keep the intentional hard
reset being evaluated as a replay cue.

## Simplified number-and-blob production grammar

V16 review selected the subtle number contrast in `IBK-001` and found that
broad uniform fields needed substantially more contrast. Rather than carry
every earlier effect into production, v17 tests a single system: planar numbers
plus organic localized activity behind them.

`IBL-001`, `IBL-002`, and `IBL-003` use identical Brandon Grotesque Bold digits,
number positions, number motion, `#edeae3` number color, `#f7f5ef` background,
and `PDE-002` subject treatment. They contain one, two, and three blobs
respectively. The comparison is nested: the first blob is identical in all
three candidates, and the second remains identical when the third is added.

Each blob is an irregular elliptical field with a softly feathered edge. Its
center follows a deterministic closed two-axis path while its rotation and
multi-lobed outline change through periodic functions. Position, outline, and
softness therefore meet at the loop boundary without a cut. The blobs use the
same neutral endpoint as the numbers at partial opacity, allowing full-strength
number interiors to remain legible above them.

Production can derive `numberSeed` and `blobSeed` from each portrait ID. That
will vary digit ordering, blob position, shape, size, path, and timing across the
first 40 portraits while preserving the selected visual grammar and making
every result exactly reproducible.

## Motion separation rule

V17 review established that two simultaneous background-motion systems create
unnecessary competition. Production must choose one of two mutually exclusive
grammars:

1. Static numbers with one or more moving blobs.
2. Gently moving numbers with no blobs, represented by `IBK-001`.

V18 tests the first grammar through `IBS-001`–`IBS-003`. These candidates reuse
the exact v17 number arrangement, blob seeds, blob positions, blob shapes, and
closed paths, but set `numberMotion` to `static`. The one-, two-, and three-blob
comparison is still nested, so blob count remains the only within-round
variable. V17 is preserved as research history but its moving-number-plus-blob
combination is not a production option.

Every candidate uses the identical `PDE-002` recipe, seed, focal point, and
264-frame development timeline. The subject is composited from its unmatted
16-bit layer rather than extracted from a flattened video, preventing a pale
cutout halo.

## Production selection

Review rejected the static-number/moving-blob grammar. No blobs will appear in
production. Subsequent review also found the accepted `IBK-001` number motion
unnecessary. `IBN-001` supersedes it for production: subtle `#edeae3` Brandon
Grotesque Bold digits remain completely still over the fixed `#f7f5ef`
background while the subject receives the same five-star `PDE-002` Development
Animation used by the other pilots.

Across the 40 Infinity portraits, position grid, density, size, typography, and
colors remain fixed. `numberSeed` is derived from portrait identity and changes
which digits occupy those positions. There is no `phaseOffset`, speed, path,
direction, or travel amplitude. Every portrait therefore has a unique,
reproducible number layout without creating a second motion system.

The selected `IBN-001` render is already a complete visual composite, not a
background-only asset: it includes the isolated subject, the static number
field, and `PDE-002`. Film grain is permanently absent under the production
policy; audio remains a separate pending pairing decision.

## Output and safeguards

- Seven silent, image-only candidates in v10–v13; eleven in v14–v15; six in v16; three in v17–v18; one production replacement in v26
- 11 seconds, 24 fps, 264 frames, 1080 × 1920
- 16-bit source preparation, effect generation, and compositing
- H.264/BT.709 delivery
- Fixed subject position, scale, rotation, and geometry
- Identical first, middle, and last background frames for `IBN-001`; exact
  matching endpoints for continuous research recipes; explicitly recorded
  non-matching endpoints for hard-reset recipes
- No grain, audio, text, camera motion, displacement, or facial deformation

For `IBC`, “text” means no caption or editorial copy. Single digits are treated
as background graphic material and are explicitly recorded as typography.

Reject an option if it reads as a themed poster, explanatory diagram, sticker,
spotlight, conventional motion trail, smoke, water, or a demonstration of the
cutout technique. The background must remain subordinate to the person's face,
gesture, skin, and the number prop.
