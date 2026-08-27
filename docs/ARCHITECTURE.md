# Architecture

The Video Generator is one bounded component of the future HPR system.

Active input: one finished Registry portrait revision + surrogate model +
surface recipe + duration + deterministic field seed.

Output: silent, loop-safe MP4 candidate + JSON provenance record.

The active renderer creates a pixel-aligned under-resolved surrogate and reveals
the untouched finished portrait through a periodic field. It keeps geometry
fixed and changes only color balance, tone, surface detail, and restrained
texture. Legacy motion presets remain supported for reproducibility but do not
define the current HPR visual direction.

It does not select audio, publish episodes, or retire assets. Those responsibilities belong to the future HPR Generator pairing and review system.
