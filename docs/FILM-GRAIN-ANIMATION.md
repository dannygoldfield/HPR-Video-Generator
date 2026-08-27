# Film Grain Animation

Status: production layer rejected on 2026-08-21. Shipping visuals contain no
film grain. All test recipes and renders remain reproducible research history.

## Production decision

Danny reviewed the film-grain work on both the 14-inch MacBook Pro and iPhone,
including the final 13-step opacity ladder from 10% through 40%, and concluded
that the layer did not add enough to the portrait. The shipping decision is:

- film grain: disabled;
- opacity: 0%;
- source plate: none;
- approved visuals: the selected `PDE-002` Development Animation for
  NYChildren and 10000, and the complete `PDE-002` plus `IBN-001` Infinity
  composite;
- next stage: audio pairing without another visual texture layer.

The machine-readable decision is
`components/video-generator/config/production-visual-policy.json`. A zero-grain
test transcode is not substituted for the approved base visual; production
uses the already selected no-grain visual candidates directly.

## Research purpose

Film Grain Animation asked whether the photographed surface could feel
continuously alive even when the subject and camera did not move. It was tested
as the smallest and fastest visual event in the HPR system, with the requirement
that it support human presence rather than announce a vintage treatment.

The active reference is Steven Spielberg's description of grain as always
moving or “swimming,” allowing a still subject to remain alive. HPR adopts the
underlying principle, not a period-film look.

## Research order of operations

The completed tests treated grain as a finishing layer:

1. Render the locked `PDE-002` Development Animation.
2. For Infinity, composite the locked `IBK-001` number background.
3. Apply grain to the complete approved visual.
4. Add and review audio.
5. Create the release master only after both visual and audio decisions lock.

Applying grain last isolated it from the Development Animation and Infinity
background. The shipping path now skips step 3 and proceeds directly from the
approved silent visual to audio review.

## Source and rights record

The locally managed scans were downloaded from the TDCatTech/LightKino film
grain page:

- Page: <https://tdcat.com/downloads/filmgrain>
- Permission wording observed 2026-08-20: “free to download and use as you wish”
- Format: 4096 × 2160 ProRes 422 HQ, 10-bit, 24 fps, 15 seconds
- Local policy: retain raw plates locally; never commit, redistribute, or expose
  them as downloadable project assets

Each candidate manifest records the exact plate filename and SHA-256 checksum.
This keeps the public repository reproducible without containing the licensed
media itself.

## Image model

The grain plate is converted to a neutral grayscale signal and composited only
into the approved video's luma plane. The original chroma planes pass through
unchanged. The current test uses Overlay because the supplied scans are
centered around neutral gray:

```text
output_luma = overlay(base_luma, grain_luma, opacity)
output_chroma = base_chroma
```

The output returns to 4:2:0 only at delivery encoding and carries complete
limited-range BT.709 characteristics. Geometry never changes.

## Layer-completeness comparison: `film-grain-composite-v21`

This round applied the same seven recipes to all three complete locked
visuals. This makes the layer stack explicit in every test:

1. the photograph stays fixed in the frame;
2. the five-star `PDE-002` Development Animation remains active;
3. Infinity also retains the shipped `IBK-001` moving-number background;
4. film grain is applied last to the complete image.

The renderer uses `VIS-30FE48FB73CE-PDE-002` for NYChildren,
`VIS-90500D66EBBF-PDE-002` for 10000, and
`VIS-4DF5D853ACDA-IBK-001` for Infinity. A decoded registration audit at five
points in each representative medium-grain candidate measured zero horizontal
and zero vertical displacement from its parent visual.

| ID | Treatment | Purpose |
| --- | --- | --- |
| `FGC-001` | No-grain transcode control | Separate grain from delivery re-encoding |
| `FGC-002` | Super 35 Light at 6% | Subtle visibility boundary |
| `FGC-003` | 35mm Light at 12% | Finer-grain character |
| `FGC-004` | Super 35 Light at 12% | Existing-source medium control |
| `FGC-005` | 16mm Light at 12% | Coarser-grain character |
| `FGC-006` | Super 35 Heavy at 12% | Denser source boundary |
| `FGC-007` | Super 35 Light at 20% | Strong visibility boundary |

The review found no visible difference among the 21 candidates. Measurement at
the 280-pixel-wide review size confirmed why: the strongest candidate changed
the image by only 0.726 display-code values on average, with no pixels changing
by more than four values. Fine scanned grain had been averaged away by delivery
compression and display reduction. V21 is therefore failed visibility research,
not a grain-character decision.

## Active visibility calibration: `film-grain-visibility-v22`

V22 uses the fixed-camera 10000 `PDE-002` parent and one Super 35 Light plate.
It varies only delivered grain size and signal magnitude so the visibility
threshold can be found before repeating a cross-portrait comparison.

| ID | Texture scale | Signal gain | Mix | Purpose |
| --- | ---: | ---: | ---: | --- |
| `FGV-001` | 1.0× | 1.0× | 0% | No-grain control |
| `FGV-002` | 1.0× | 1.0× | 50% | Native-grain lower boundary |
| `FGV-003` | 1.0× | 1.0× | 100% | Full native scanned signal |
| `FGV-004` | 1.5× | 1.5× | 65% | Moderately enlarged grain |
| `FGV-005` | 2.0× | 2.0× | 65% | Clearly visible grain |
| `FGV-006` | 2.0× | 3.0× | 85% | Strong boundary |
| `FGV-007` | 2.5× | 4.0× | 100% | Intentionally excessive boundary |

At review size, the new sequence progresses from 1.125 average display-code
change in `FGV-002` to 12.436 in `FGV-007`; the share of pixels changing by
more than four values rises from 0.22% to 73.62%. This is a genuine visible
range. Grain size and signal gain are recorded separately in every manifest.

## Prior slow-swim refinement: `film-grain-slow-swim-v23`

Review found `FGV-002` closest and every candidate from `FGV-003` upward too
strong. The desired temporal character is also calmer than ordinary 24-frame
grain flicker. V23 therefore keeps `FGS-002` byte-for-byte identical to
`FGV-002` and uses overlapping temporal averages to correlate neighboring grain
frames. Signal gain compensates only for the contrast lost through averaging;
it does not change portrait exposure.

| ID | Mix | Texture scale | Temporal window | Purpose |
| --- | ---: | ---: | ---: | --- |
| `FGS-001` | 0% | 1.0× | 1 frame | No-grain control |
| `FGS-002` | 50% | 1.0× | 1 frame | Exact `FGV-002` reference |
| `FGS-003` | 50% | 1.0× | 3 frames | Slow motion only |
| `FGS-004` | 50% | 1.0× | 5 frames | Calmer motion only |
| `FGS-005` | 60% | 1.0× | 5 frames | Modest mix increase |
| `FGS-006` | 60% | 1.15× | 5 frames | Modest size increase |
| `FGS-007` | 67% | 1.25× | 7 frames | Danny's requested upper endpoint |

At review size, adjacent-frame grain correlation rises from 0.473 in the exact
reference to 0.884 in `FGS-007`. Mean visible difference rises much more gently,
from 1.125 to 1.953 display-code values. This makes temporal ease the main
change instead of another leap in visual strength.

Review did not rate this round. The notes reported visible grain only under
close inspection in `FGS-002`, diminishing or uncertain grain through
`FGS-003`–`FGS-006`, and a bad end-of-loop flash in `FGS-007`. V23 therefore did
not settle the layer.

## Prior keep-or-drop comparison: `film-grain-decision-v24`

V24 is a decision matrix rather than another narrow ladder. It contains a
no-grain control plus all four locally held scan plates—Super 35 Light, 35mm
Light, 16mm Light, and Super 35 Heavy—at three treatments per plate:

| Profile | Temporal window | Intended reading |
| --- | ---: | --- |
| Moderate gentle swim | 3 frames | Clearly above the too-faint V23 range |
| Clear calm swim | 5 frames | Confidently visible but still photographic |
| Bold slowest swim | 7 frames | Upper boundary for deciding whether grain belongs at all |

Most candidates retain the requested 67% mix and 1.25× texture size. Signal
gain is calibrated separately for each plate because the supplied 35mm scan is
far finer than 16mm or the Heavy plate. `FGD-007` uses an 86% mix because the
fine 35mm source reaches the renderer's safe signal-gain ceiling before it
matches the bold comparison level.

At the 270 × 480 laptop-review size, the twelve grained candidates span 2.083
to 2.908 average display-code values of change from the control. This begins
above V23 and remains below the 3.917 value of `FGV-005`, which review found too
noticeable at native grain speed.

The loop is now part of the rendering model rather than a subjective hope.
Every grained candidate receives temporal pre-roll before the visible first
frame and a one-second, RMS-normalized blend from the outgoing grain into a
reversed copy of the opening grain. The last-frame-to-first-frame change
measures 0.618–0.943 times an ordinary adjacent change across V24, while first
and last grain amplitude remain within 8% of the median. This removes both the
V23 warm-up flash and a conspicuous slow-grain reset.

## Final opacity-only comparison: `film-grain-opacity-v25`

Review of V24 reframed the decision as a finishing-layer adjustment: choose one
grain material and lower its opacity until it improves skin texture without
reading as a separate effect. V25 therefore uses 13 Super 35 Light candidates
at these opacity values:

```text
10%, 12.5%, 15%, 17.5%, 20%, 22.5%, 25%,
27.5%, 30%, 32.5%, 35%, 37.5%, 40%
```

Opacity is the only changing parameter. Every candidate uses the exact
`FGD-004` plate sample: starting frame 90, horizontal crop 0.9512, 5.9× grain
signal gain, 1.25× texture scale, seven-frame temporal smoothing, and a
24-frame loop blend. The locked `PDE-002` Development Animation and all output
settings also remain unchanged. The V24 no-grain control remains available in
the preceding review set.

The intended selection criterion was tactile skin, not visible noise. No
candidate improved the portrait enough over the prior no-grain control, so the
production system omits the grain layer.

## Review questions

- Does the surface feel alive before the viewer consciously identifies grain?
- Is grain visible on skin at mobile review size without competing with eyes or
  expression?
- Does the grain remain photographic rather than digital noise?
- Does the grain survive browser playback without turning into compression
  smearing?
- Is there any brightness pulse or recognizable reset at the loop boundary?
- Does the coarser material exaggerate wrinkles or make skin feel harsh?
- Does Heavy read as atmosphere, or merely as an effect?

Reject a candidate for color drift, dirt or scratches, gate weave, flicker,
skin harshness, a visible loop pulse, or grain that disappears after ordinary
web playback.

## Research reproducibility

Had grain been selected, stock, opacity, and playback speed would have remained
consistent across the 120 portraits, with deterministic variation in only two
places:

- the starting frame within the 15-second scan;
- the horizontal crop within the wide 4K plate.

Those controls remain documented for reproducibility, but production creates
neither variation because film grain is disabled.

The earlier seven-candidate 10000 round v19 remains reproducible. A temporary
v20 grain-only diagnostic removed Development Animation to isolate the apparent
motion report; that was not the desired creative test. V21 restored the proper
three-layer stack but failed visibility. V22 found the visible range; V23 found
that simple smoothing became too faint and exposed a loop flaw. V24 completed
the multi-source comparison; V25 completed the final opacity-only ladder. No
treatment improved the portrait enough, so HPR ships without grain and moves
directly to audio pairing.
