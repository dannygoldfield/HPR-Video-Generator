# HPR Video Generator

> **Canonical video source.** As of August 26, 2026, this standalone repository
> is the authoritative implementation, configuration, and research history for
> HPR visual generation. HPR Umbrella consumes approved silent-video outputs
> and provenance; it does not contain or execute a second video generator.

An image-first, audio-independent system for generating silent, loop-safe
vertical videos from portraits.

The generator deliberately knows nothing about audio, pairing, publishing, or analytics. Its output becomes an eligible video pool for the future HPR Generator.

## Active visual direction

Portrait Development Animation keeps the photograph's geometry fixed while
the untouched finished Lightroom export emerges from a deliberately
under-resolved surrogate across the surface. Global development, a very soft
sweep, and activation fields are implemented in the first 15-candidate pilot.
See the complete
[Portrait Development Animation specification](docs/PORTRAIT-DEVELOPMENT-ANIMATION.md).

The shared five-star `PDE-002` Development Animation is now locked. Infinity
adds the locked `IBN-001` static, portrait-unique number background. Film grain was tested as a
finishing layer and rejected on 2026-08-21 because it did not improve the
portrait enough to justify the added effect. The photographed image remains
fixed in the frame; shipping visuals contain Development Animation and, for
Infinity, the approved number background, with no film grain. See the completed
[Film Grain Animation research record](docs/FILM-GRAIN-ANIMATION.md).

The older camera-motion, texture, and White Balance-only renderers remain
reproducible research tools; they are not the active production direction.

## Production format

- one portrait per candidate
- 1080 × 1920, 9:16
- 24 frames per second
- 11-second active portrait format; earlier 7-second research retained
- fixed geometry with loop-safe tonal and surface development
- no film grain in the approved production visual policy
- deterministic seeds and complete provenance

## Local media

Source portraits, grain, and rendered videos are intentionally excluded from
Git. Production media belongs in the private HPR production workspace. The
`media/source/` and `media/output/candidates/` directories remain available for
small local experiments only.

## Generate

```text
python -m hpr_video_generator.cli generate --portrait media/source/portraits/bhutan_450.jpg --preset VP-002 --seed 2026073101
```

Generation requires FFmpeg. The program accepts a system FFmpeg or the executable supplied by the optional `imageio-ffmpeg` package.
