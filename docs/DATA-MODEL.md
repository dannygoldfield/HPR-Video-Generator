# Data model

## Portrait

A source image with a stable ID and immutable source filename.

## Motion preset

A versioned closed-loop motion definition. An existing preset ID never silently changes meaning.

## Video candidate

A deterministic result derived from one portrait, one preset, one duration, and one seed. Candidates begin as eligible. The future pairing system may retire a candidate only after its pairing is approved for publication.

