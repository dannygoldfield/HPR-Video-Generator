# Portrait Development Animation

Status: active HPR visual research direction as of 2026-08-17.

This specification supersedes camera-motion and Ken Burns-style movement as the
active testing plan. The earlier motion-rhythm, motion-variable, and White
Balance experiments remain reproducible research records; they are not the
current production direction.

## Plain-language concept

The photograph stays physically still while its surface seems to become more
fully realized. Skin color settles, shadow and highlight detail becomes
available, tonal transitions become smoother and deeper, and a restrained
amount of texture becomes tactile. Different areas can awaken at different
times, influence nearby areas, fade, and emerge elsewhere.

The viewer should experience a living human presence—not an edit, a filter, or
an interface. The person must remain more compelling than the animation.

## Creative thesis

The source vocabulary is Danny's actual Lightroom finishing sequence:

1. White balance, especially accurate skin tone.
2. Open shadows to reveal skin-surface detail.
3. Lower highlights to recover skin detail.
4. Adjust whites to smooth tonal transitions in skin.
5. Add blacks for depth and subtle pop.
6. Add clarity carefully so skin feels tactile.

These stages are a causal palette, not a requirement to show six obvious steps.
In most successful modes the stages should overlap in time and space. A literal
one-after-another demonstration would read as an editing tutorial and is not the
goal.

The useful parts of the visual references are limited:

- slow boiling suggests local activity appearing and disappearing, not bubbles;
- ocean swells suggest slow overlap and neighbor influence, not water;
- an irregular illuminated grid suggests distributed activation, not visible
  cells or a digital effect.

The working term is **activation field**: a continuous, feathered field that
controls where each authentic development difference is visible.

## Non-negotiable motion specification

| Property | Requirement |
| --- | --- |
| Geometry | Fixed crop, position, scale, rotation, perspective, and facial structure in every frame |
| Spatial resampling | No warp, displacement, optical-flow deformation, mesh animation, or simulated camera move |
| Changing qualities | Color balance, luminance distribution, tonal separation, and restrained local texture only |
| Visual hierarchy | The person is perceived first; the mechanism should be noticed second or not at all |
| Surface behavior | Continuous, organic, feathered, and temporally smooth; never cellular, bubbly, liquid, or heat-like |
| Clarity | Lowest-strength stage, restricted to useful skin texture; no halos or crunchy detail |
| Presentation | No controls, labels, cursors, grids, masks, or Lightroom interface inside the video |
| Initial pilot | Silent, no grain, no text, 1080 × 1920, 24 fps, 7 seconds, 168 frames |
| Active TIFF round | Silent, no grain, no text, 1080 × 1920, 24 fps, 11 seconds, 264 frames |
| Loop | First and last states match exactly and their rate of change approaches zero |

The rendered pixels may change, but the mapping from source coordinates to
output coordinates must remain the identity transform.

## Authoritative finished-source contract

There is an important technical limit: a finished JPEG cannot truly recover
highlight or shadow information that is no longer present. The active process
therefore makes no recovery claim and does not simulate Lightroom sliders. It
uses one finished Lightroom export as the authoritative maximum.

For each portrait, the generator normalizes orientation and creates two exactly
aligned internal images:

- `F`: the untouched finished portrait;
- `S`: a deterministic under-resolved surrogate derived from `F` by withholding
  a restrained amount of color accuracy, tonal separation, and texture.

Every frame is a spatial blend between those two images:

```text
frame(x, y, t) = S(x, y) * (1 - A(x, y, t)) + F(x, y) * A(x, y, t)
base_final_mix <= A(x, y, t) <= 1
```

The field `A` may only reveal toward `F`. It never overshoots, adds recovered
detail, or exceeds the finished source. The final image pixels remain untouched
inside the compositor. Source, normalized-final, surrogate, and mask-stream
checksums are recorded in every candidate manifest.

The first conceptual round used three JPEGs. The active round uses embedded-profile
16-bit TIFFs and keeps source normalization, surrogate construction, and
compositing at 16-bit precision until H.264 delivery conversion. This retains
more tonal precision; it does not create detail absent from Lightroom's finished
export. Seven aligned Lightroom development exports may be useful later as a
one-time calibration reference, but they are not required for every portrait or
every video.

## Development qualities

The surrogate combines the finishing priorities into one restrained starting
surface rather than presenting six literal steps. The current version uses:

| Quality withheld in `S` | Reveal behavior | Guardrail |
| --- | --- | --- |
| White-balance accuracy | Broad and highly correlated return to final skin color | No isolated colored spots or hue pumping |
| Shadow separation | Broad lower-tone return to the finished portrait | No invented detail, gray blacks, or exposure breathing |
| Highlight and white separation | Very soft return to finished bright-skin transitions | No milky veil, flat face, or highlight halos |
| Black depth | Restrained return to final structural contrast | No crushing, edge outlines, or artificial pop |
| Texture/clarity impression | Weakest and most spatially restrained return | No crunchy pores, wrinkle emphasis, or halos |

These are perceptual ingredients, not claims that the generator reproduces
Lightroom's processing. The first review determines whether this compact model
is emotionally useful before any more elaborate source preparation is justified.

## Animation modes

### Global development

**What it looks like:** The entire portrait moves gradually from slightly less
resolved toward the finished state. The six stages overlap but retain their
general order.

**Adjustments:** The complete surrogate-to-final difference moves uniformly,
combining broad skin-color, tone, and restrained texture change.

**HPR fit:** Useful as a diagnostic control because the source idea is legible.
It is unlikely to be the final answer: a whole-frame progression can resemble a
before/after demo, and its return path can look like an undo operation.

### Sweep

**What it looks like:** A single very broad, soft front travels across the
portrait. The leading and trailing edges are so feathered that the viewer senses
a change of surface rather than a wipe.

**Adjustments:** The complete surrogate-to-final difference follows one broad
front. Direction may be horizontal, vertical, diagonal, or radial, but should
not repeatedly track facial contours.

**HPR fit:** More organic and spatial than global development, and easy to read
on a phone. It fails if the boundary is perceptible as a scan, light pass, or
software transition.

### Band

**What it looks like:** One or two wide, overlapping zones of development drift
slowly through the portrait while the rest remains near the final state. A band
has a soft center and no visible edge.

**Adjustments:** Primarily tonal change, with weaker color and texture influence.
Texture should not occupy a narrow moving band.

**HPR fit:** It can suggest ocean-swell rhythm without moving geometry. It has a
high risk of looking like a scanner, spotlight, or animated gradient, so it is a
second-round mode rather than an initial priority.

### Activation field

**What it looks like:** A few irregular, softly connected regions become active,
influence neighboring regions, fade, and reappear elsewhere. Nothing has a hard
cell boundary, and the field itself is never visible.

**Adjustments:** The shared surrogate-to-final difference uses broad, correlated
regions. Color and major tone changes must remain broadly connected; texture is
inherently limited by the restrained surrogate and never receives independent noise.

**HPR fit:** This is the strongest conceptual match. It can make the portrait
feel alive at the surface without implying camera movement. Its main risk is
blotchiness: small, high-contrast, or weakly feathered patches could resemble a
rash, heat map, compression damage, or a special effect.

### Field-led global convergence

**What it looks like:** A nearly imperceptible global movement toward the final
state provides coherence while a low-strength activation field creates local
variation.

**Adjustments:** One global reveal envelope carries the source change, while the
local field adds restrained variation concentrated around the portrait.

**HPR fit:** This hybrid may preserve the legibility of development while
avoiding the software-demo quality of a purely global change. It should be tested
only after the pure activation field establishes acceptable patch scale and
strength.

## Parameters

### Development response

| Parameter | Meaning |
| --- | --- |
| `base_final_mix` | Minimum fraction of the untouched finished portrait present anywhere |
| `temperature_gains` | Restrained red, green, and blue gains used only to construct the surrogate |
| `black_lift` | Surrogate black-floor offset removed as the final is revealed |
| `shadow_suppression` | Amount, center, and width of withheld lower-tone separation |
| `highlight_veil` | Amount, center, and width of withheld upper-tone separation |
| `texture_softening` | Maximum texture reduction in the surrogate; the clarity-like quality remains weakest |
| `focal_radius` | Broad portrait-weighted area receiving full field influence |
| `background_influence` | Reduced field strength outside the broad portrait area |

### Spatial field

| Parameter | Meaning |
| --- | --- |
| `mode` | Global, sweep, band, activation field, or hybrid |
| `direction` | Sweep/band vector or radial origin |
| `patch_size` | Typical active-region diameter, expressed relative to face height |
| `patch_count` | Approximate number of simultaneously active regions |
| `neighbor_coupling` | Strength of diffusion between adjacent regions |
| `feather` | Width of the soft transition around an active region |
| `anisotropy` | Degree to which regions stretch in one direction |
| `field_resolution` | Low-resolution grid used to generate broad organic structure |
| `spatial_seed` | Reproducible field layout |

Initial activation-field patches should be broad: roughly 12–30 percent of face
height, with feathering at least half the patch radius and two to five partially
overlapping active regions. Smaller patches are intentionally excluded from the
first pilot.

### Time and rhythm

| Parameter | Meaning |
| --- | --- |
| `duration_sec` and `fps` | Candidate duration and exact frame rate |
| `speed` | Rate at which active regions grow, spread, and fade |
| `phase_offsets` | Small deterministic delays connecting neighboring regions |
| `pause_probability` | Proposed second-round chance of a short quiet interval in a region |
| `pause_range_sec` | Proposed second-round minimum and maximum quiet interval |
| `rhythm_profile` | Continuous swell, asymmetric emergence/decay, or clustered activity |
| `temporal_smoothing` | Limit on frame-to-frame mask change |
| `loop_phase` | Periodic time coordinate used to close the field exactly |
| `temporal_seed` | Reproducible rhythm variation |

Activity should rise and fall over approximately 0.8–2.2 seconds, with occasional
0.3–0.8-second quiet regions. Rhythms should overlap and avoid a metronomic
sequence of equally spaced events.

### Loop and quality controls

- Build fields from periodic time coordinates—for example, noise sampled with
  `cos(2πt)` and `sin(2πt)`—so the mathematical field closes without a crossfade.
- Make the first and last development state identical and ease their derivatives
  toward zero.
- Reject any visible seam, exposure pulse, hue jump, or reversal that calls
  attention to the loop.
- Record first/last-frame similarity and a temporal-flicker metric, but do not
  use either metric as a substitute for human judgment.

## Computational implementation

1. **Finished-source preparation.** Normalize EXIF orientation, preserve the
   source file, make the aligned lossless finished-source PNG, and record sizes
   and checksums.
2. **Surrogate compiler.** Derive a deterministic under-resolved image with a
   modest cool/green color offset, restrained shadow and highlight separation,
   lifted black floor, and slight texture softening. The transformation is
   versioned and reversible only toward the finished source.
3. **Field engine.** Generate low-resolution seeded fields, diffuse or blur them
   to establish neighbor correlation, apply smooth thresholds, and upscale with
   soft interpolation. Global, sweep, and band modes are analytic fields;
   activation fields use broad seeded periodic ellipses with coupled neighbors.
   The pilot computes a 135 × 240 mask and enlarges it with soft interpolation.
4. **Frame compositor.** Stream the exact `duration × fps` grayscale masks to
   FFmpeg and use `maskedmerge` to reveal the untouched finished image from the
   surrogate. All inputs and the output share one 24-fps clock; no geometric
   filter is present. TIFF-round image streams remain 16-bit through this stage.
5. **Guardrails.** Enforce `base_final_mix <= A <= 1`, exact first/last mask
   identity, fixed geometry, deterministic seeds, exact duration, and the
   absence of grain, audio, and text.
6. **Provenance and review telemetry.** Record source and surrogate checksums, recipe,
   exact parameters, seeds, stage schedules, field thumbnails or checksums,
   software versions, and output path. The review interface may show stage and
   field diagnostics outside the video; none appear in the work itself.

Computing the field at a coarse grid—approximately 64–128 cells across the
portrait—then upscaling and feathering is both efficient and creatively useful:
it prevents the tiny independent changes that would make skin look noisy or ill.

## First test plan

Use the existing three pilot portraits because they provide different ages,
skin surfaces, source projects, and tonal structures. Use their current finished
JPEGs as the authoritative sources. Keep the first experiment at seven seconds,
silent, without grain or text.

Render five candidates per portrait:

| Candidate | Purpose |
| --- | --- |
| `PDA-001` | Static authoritative final portrait |
| `PDA-002` | Global development diagnostic control |
| `PDA-003` | Broad sparse activation field |
| `PDA-004` | Overlapping swell-like activation field |
| `PDA-005` | One extremely soft sweep |

The 15 candidates are rendered and registered as
`portrait-development-pilot-v5`. `PDA-003` and `PDA-004` share the surrogate
model so their comparison concentrates on field structure. Candidate order may
be varied during review after the static reference.

## Implemented 11-second TIFF timing/easing round

The first review established enough value in the direction to continue, with
the 10000 notes as the relevant control. The second round replaces the
NYChildren and Infinity photographs, retains the 10000 portrait as revision 2,
and isolates timing, easing, and quiet-time choices rather than changing the
surrogate model. Infinity's light background remains untouched; separated-layer
experiments are postponed until a current field treatment is chosen.

The source set is:

| Project shorthand | TIFF | Registry treatment |
| --- | --- | --- |
| NYChildren | `israel.batel.oshrat.390.tif` | New portrait identity |
| 10000 | `new_jersey_m_0180.tif` | Revision 2 of the existing portrait |
| Infinity | `26-Sam-359.tif` | New portrait identity |

All three sources are flattened, embedded-ProPhoto RGB, 16 bits per channel.
The generator performs an embedded-profile-to-sRGB LittleCMS transform in
native 16-bit precision, creates two lossless 16-bit PNG working states, blends
them in 16-bit planar RGB, and converts only the encoded delivery to H.264
`yuv420p`. Delivery characteristics are explicitly BT.709.

The five candidates per portrait are:

| ID | Treatment | Minimum finished image | Speed | Fully finished rest | Easing |
| --- | --- | ---: | ---: | ---: | ---: |
| `PDB-001` | Finished TIFF reference | 100% | Static | Entire loop | — |
| `PDB-002` | Global development, long finished rest | 67% | 1.00 | 50% | 1.20 |
| `PDB-003` | Sparse activation, slow ease | 70% | 0.72 | 32% | 1.30 |
| `PDB-004` | Overlapping swells, flowing ease | 63% | 1.35 | 20% | 0.82 |
| `PDB-005` | Soft sweep, unhurried ease | 70% | 0.85 | 32% | 1.40 |

`finished rest` is the combined fraction of the loop held at the fully finished
portrait around the loop boundary. It is split between the end of one playback
and the beginning of the next, so repeated playback has one continuous quiet
interval. Easing changes how gently the treatment leaves and returns to that
rest. Every animated candidate still moves in one direction only: from the
under-resolved state toward the untouched final, never past it.

The registered experiment is `portrait-development-tiff-v6`: 15 silent,
image-only candidates, each 11 seconds, 1080 × 1920, 24 fps, and 264 frames.
All files passed duration, frame-count, codec, BT.709, and decoded loop-closure
checks. Review should now concentrate on whether the speed and ease deepen
human presence, whether the completed image remains long enough to be seen,
and whether any field behavior reads as an effect.

## Implemented possible-finals round

The round-2 review produced three actionable conclusions. Sparse activation
was more satisfying than overlapping swells, the soft sweep improved with
repeated viewing, and the fully finished pause should be 40% as long as the
round-2 sparse/sweep pause. Infinity also justified a stronger range probe,
while background invention remains a separate question.

The possible-finals source set uses the unchanged 10000 revision 2, the
sharp-eyed `israel.batel.oshrat.398.tif` as a new NYChildren portrait, and the
adjusted full-resolution `26-Sam-359.tif` as Infinity revision 2. Each source is
an embedded-ProPhoto RGB 16-bit TIFF at or above the 1080 × 1920 delivery
frame. Undersized sources are rejected before finalist rendering.

| ID | Treatment | Minimum finished image | Speed | Fully finished rest | Easing |
| --- | --- | ---: | ---: | ---: | ---: |
| `PDC-001` | Refined sparse activation | 70% | 0.72 | 12.8% | 1.30 |
| `PDC-002` | Refined soft sweep | 70% | 0.85 | 12.8% | 1.40 |
| `PDC-003` | Assertive sparse boundary test | 50% | 0.80 | 12.8% | 1.25 |

The 12.8% rest is approximately 1.4 seconds total in an 11-second loop, split
across the loop boundary. `PDC-001` and `PDC-002` preserve the favored round-2
field behavior; `PDC-003` deliberately tests whether a more obvious surface
change is compelling or excessive, especially with Infinity's smaller face in
the frame.

The registered experiment is `portrait-development-finalist-v7`: nine silent,
image-only candidates at 1080 × 1920, 24 fps, 264 frames, H.264/BT.709. All
nine passed duration, frame-count, color-tag, source-resolution, and decoded
loop-closure checks. The review decision is now portrait-specific selection,
not another broad search across motion families.

## Implemented visibility-boundary round

The possible-finals could support a selection, but their animation might remain
entirely subconscious for most viewers. The next round intentionally pushes all
three portraits harder while holding the underlying color/tone/texture
surrogate constant. This isolates visibility rather than introducing another
image-treatment vocabulary.

NYChildren uses its exposure-corrected forehead edit as revision 2. The 10000
and Infinity revision-2 sources remain unchanged controls.

| ID | Treatment | Minimum finished image | Speed | Feather | Fully finished rest |
| --- | --- | ---: | ---: | ---: | ---: |
| `PDD-001` | Daring sparse activation | 25% | 0.90 | 0.72 | 6.4% |
| `PDD-002` | Daring soft sweep | 25% | 1.05 | 0.72 | 6.4% |
| `PDD-003` | Full-range activation ceiling | 0% | 1.15 | 0.62 | 4.0% |

The first two expose 75% of the available surrogate-to-finished difference,
compared with 30% in the refined possible-final sparse and sweep. The ceiling
test can expose the complete surrogate, uses six less-diffuse regions, and has
only about 0.44 seconds of fully finished rest per 11-second loop. It is allowed
to fail by being too visible, but still may not distort geometry, overshoot the
finished image, or add a new effect layer.

All prior configs, renders, manifests, and Registry decisions remain intact.
The review interface shows each candidate's exact saved field parameters. If
the preferred setting lies between the possible-finals and boundary rounds, the
next value can be interpolated explicitly—for example, a minimum-finished value
between 70% and 25%—rather than recreated by eye.

The registered experiment is `portrait-development-visibility-v8`: nine
silent, image-only candidates at 1080 × 1920, 24 fps, and 264 frames. Infinity
background ideation begins only after the portrait-surface setting is chosen.

## Implemented 65% landing round

All nine visibility-boundary candidates received a latest rating of 4, and the
review direction was to split the difference 65% toward that more visible
round. Each `PDE` recipe therefore pairs one-to-one with its `PDC` and `PDD`
counterparts. Every continuous parameter uses:

`possible final + 0.65 × (visibility boundary − possible final)`

Patch counts, which must be integers, use the nearest practical whole number.
No source response, geometry, output specification, audio, grain, text, or
background treatment changes.

| ID | Treatment | Minimum finished image | Speed | Feather | Patches | Fully finished rest |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `PDE-001` | Settled sparse activation | 40.75% | 0.837 | 0.734 | 4 | 8.64% |
| `PDE-002` | Settled soft sweep | 40.75% | 0.980 | 0.804 | 0 | 8.64% |
| `PDE-003` | Settled activation ceiling | 17.50% | 1.0275 | 0.697 | 5 | 7.08% |

## Production selection and name

The production name is **Portrait Development Animation**, shortened to
**Development Animation** when context is clear. “Adjustment Animation” is not
used: it suggests visible software controls or an editing tutorial, while the
selected treatment is meant to read as a living portrait surface.

`PDE-002`, Settled soft sweep, is locked as the shared production treatment for
10000, NYChildren, and Infinity. Each received a five-star review. The recipe
keeps portrait geometry fixed while the finished Lightroom pixels are revealed
through an 11-second, 24 fps, exactly closed tonal field. It contains no camera
movement, facial distortion, grain, audio, or editorial text.

The approved files are shippable silent visual components. The separate grain
decision is complete: production uses no grain layer. They become final
audio-video release masters after an approved audio pairing.

The registered experiment is `portrait-development-settlement-v9`: nine
silent, image-only candidates at 1080 × 1920, 24 fps, and 264 frames. All nine
passed decoded duration, frame-count, BT.709, fixed-geometry, source-resolution,
manifest-timeline, and loop-closure checks. Previous rounds remain available
in the review menu with their exact saved settings.

Review at normal phone size and watch each loop at least three times before
opening technical diagnostics. Score these dimensions independently:

1. **Human presence:** Does attention remain on the person?
2. **Mentalizing:** Does the treatment invite curiosity about the person rather
   than curiosity about the effect?
3. **Skin accuracy:** Does color remain believable throughout?
4. **Tactile realism:** Does skin gain physical presence without looking harsh?
5. **Organic emergence:** Do changes feel related and alive rather than random?
6. **Effect invisibility:** Is the mechanism subordinate to the portrait?
7. **Loop continuity:** Does repetition remain unobtrusive?
8. **Overall viability:** Would this treatment deserve another refinement round?

### Hard rejection failures

- any bending, melting, breathing, or shifting of facial structure;
- boiling, watery, smoky, heat-distortion, or liquid appearance;
- rash-like, mottled, cellular, or heat-map patches;
- visible masks, bands, wipes, scan lines, or spotlight behavior;
- global exposure pumping, color flicker, crawling noise, or compression shimmer;
- inaccurate or unstable skin hue;
- clipped highlights, gray shadows, crushed blacks, clarity halos, crunchy pores,
  or exaggerated wrinkles;
- an obvious before/after tutorial or edit/undo sequence;
- a visible loop seam or mechanical reversal;
- an effect that is technically subtle but adds nothing to human presence.

## Implemented first-round set

1. **Activation field.** Broad sparse and overlapping-swell variants.
   This is the best match for localized, neighbor-influenced development and the
   “living surface” idea.
2. **Global development as a control.** It establishes whether the basic
   surrogate-to-final change is emotionally useful, even though the mode is
   probably too tutorial-like for production.
3. **Soft sweep as the third comparison.** It tests whether spatial progression
   adds life with less blotch risk than an activation field.

Defer the band mode. Its similarity to a scanner or moving light makes it the
weakest initial fit. Also defer automatic face segmentation, film grain, audio,
text, and Clarity-heavy variants until the basic surface behavior succeeds.

## Decisions and pushback

- Do not implement literal boiling-water physics. The metaphor is useful only
  for asynchronous emergence and decay; fluid simulation would lead directly
  toward the gimmick the project is trying to avoid.
- Do not turn the Lightroom sequence into six labeled or clearly separated
  steps. That would explain the process instead of deepening the portrait.
- Do not claim that one JPEG can recover missing tonal information. Treat the
  current work as a one-direction conceptual prototype, and prefer a 16-bit TIFF
  when production sources are prepared.
- Do not let Clarity carry the animation. It is the most likely stage to make
  the mechanism visible and should remain the weakest layer.
- Do not make subtlety the only criterion. A nearly invisible treatment that
  does not increase presence, tactile reality, or mentalizing is unnecessary.
