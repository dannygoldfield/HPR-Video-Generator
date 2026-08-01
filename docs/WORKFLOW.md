# Workflow

1. Export and curate portrait sources outside the repository.
2. Register or place local copies under `media/source/portraits/`.
3. Generate silent candidates from versioned presets and deterministic seeds.
4. Verify dimensions, duration, codec, and loop closure.
5. Admit usable candidates to the future pairing pool.
6. After a video/audio pairing is approved, the pairing system retires both assets.

## Calibration rule

Animation, grain, and overall quality are rated separately from 1 to 5. A low animation or grain score means the treatment is too noticeable. Existing preset IDs remain reproducible; calibration creates new preset IDs rather than silently changing old ones.

## Organic texture experiments

Moving environmental footage can provide motion without geometrically animating the portrait. The first treatment removes stationary scenery through frame differencing, converts the remaining movement to a soft monochrome texture, creates a forward-reverse loop, and blends it over a still portrait at low opacity. Speed and rotation are recorded parameters for later variation.
