# HPR Video Generator

An image-first, audio-independent system for generating silent, loop-safe vertical videos from portraits.

The generator deliberately knows nothing about audio, pairing, publishing, or analytics. Its output becomes an eligible video pool for the future HPR Generator.

## First production model

- one portrait per candidate
- 1080 × 1920, 9:16
- 24 frames per second
- 7 seconds initially; 9 and 11 seconds supported
- minimal closed-loop motion
- subtle 35 mm film grain
- deterministic seeds and complete provenance

## Local media

Source portraits, grain, and rendered videos are intentionally excluded from Git. Put local media under `media/source/`; generated candidates go under `media/output/candidates/`.

## Generate

```text
python -m hpr_video_generator.cli generate --portrait media/source/portraits/bhutan_450.jpg --preset VP-002 --seed 2026073101
```

Generation requires FFmpeg. The program accepts a system FFmpeg or the executable supplied by the optional `imageio-ffmpeg` package.

