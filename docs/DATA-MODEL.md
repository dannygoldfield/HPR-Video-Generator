# Data model

## Portrait

A source image with a stable ID and immutable source filename.

## Development source

One finished Lightroom export attached to a Registry portrait revision. It is
the authoritative maximum. The generator records its checksum and creates a
deterministic, pixel-aligned under-resolved surrogate. Seven aligned Lightroom
stage exports may be supplied for a future calibration study, but they are not
required for every portrait or candidate.

## Surface recipe

A versioned fixed-geometry definition containing the animation mode, surrogate
strength, masks, spatial-field parameters, timing, loop rules, and seeds. An
existing recipe ID never silently changes meaning.

## Legacy motion preset

A versioned closed-loop camera-motion definition retained for prior-candidate
reproducibility. It is not part of the active visual testing plan.

## Video candidate

A deterministic result derived from one finished portrait revision, its
surrogate model, one surface recipe, one duration, and recorded spatial and temporal seeds.
Candidates begin as eligible. The pairing system may retire a candidate only
after its pairing is approved for publication.
