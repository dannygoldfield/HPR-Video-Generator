# Architecture

The Video Generator is one bounded component of the future HPR system.

Input: portrait image + motion preset + duration + seed + optional grain source.

Output: silent, loop-safe MP4 candidate + JSON provenance record.

It does not select audio, publish episodes, or retire assets. Those responsibilities belong to the future HPR Generator pairing and review system.

