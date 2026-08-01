import argparse
from pathlib import Path

from .config import load_config
from .generator import Candidate, generate, generate_texture_test


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate silent, loop-safe HPR portrait videos")
    parser.add_argument("command", choices=["generate", "texture-test"])
    parser.add_argument("--portrait", required=True, type=Path)
    parser.add_argument("--grain", type=Path, default=Path("media/source/grain/filmgrain.mov"))
    parser.add_argument("--preset", default="VP-002")
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--duration", type=int, choices=[7, 9, 11], default=7)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--texture", type=Path)
    parser.add_argument("--texture-opacity", type=float, default=0.02)
    parser.add_argument("--texture-speed", type=float, default=1.0)
    parser.add_argument("--texture-rotation", type=float, default=0.0)
    parser.add_argument("--config", type=Path, default=Path("config/generator.xml"))
    args = parser.parse_args()
    config = load_config(args.config)
    preset = config.presets[args.preset]
    output = args.output or Path("media/output/candidates") / f"{args.portrait.stem}_{preset.id}_seed-{args.seed}.mp4"
    candidate = Candidate(args.portrait, args.grain, preset, args.seed, args.duration, output)
    if args.command == "texture-test":
        if args.texture is None:
            parser.error("texture-test requires --texture")
        print(generate_texture_test(config, candidate, args.texture, args.texture_opacity, args.texture_speed, args.texture_rotation))
    else:
        print(generate(config, candidate))


if __name__ == "__main__":
    main()
