import argparse
from pathlib import Path

from .config import load_config
from .generator import Candidate, generate


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate silent, loop-safe HPR portrait videos")
    parser.add_argument("command", choices=["generate"])
    parser.add_argument("--portrait", required=True, type=Path)
    parser.add_argument("--grain", type=Path, default=Path("media/source/grain/filmgrain.mov"))
    parser.add_argument("--preset", default="VP-002")
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--duration", type=int, choices=[7, 9, 11], default=7)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--config", type=Path, default=Path("config/generator.xml"))
    args = parser.parse_args()
    config = load_config(args.config)
    preset = config.presets[args.preset]
    output = args.output or Path("media/output/candidates") / f"{args.portrait.stem}_{preset.id}_seed-{args.seed}.mp4"
    print(generate(config, Candidate(args.portrait, args.grain, preset, args.seed, args.duration, output)))


if __name__ == "__main__":
    main()

