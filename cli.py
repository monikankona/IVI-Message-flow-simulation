from __future__ import annotations

import argparse
from pathlib import Path
from .core import IVISimulator


def main() -> int:
    parser = argparse.ArgumentParser(description="IVI Media Service to Audio HAL message-flow simulator")
    parser.add_argument("--scenario", choices=["normal", "navigation", "call"], default="normal")
    parser.add_argument("--output", default="output")
    args = parser.parse_args()

    sim = IVISimulator()
    sim.run(args.scenario)
    paths = sim.save_outputs(Path(args.output))
    print(f"Scenario: {args.scenario}")
    print(f"Messages: {len(sim.trace.messages)}")
    print("Generated:")
    for p in paths.values():
        print(f"  - {p}")
    print("\nLast 5 log entries:")
    for line in sim.trace.logs[-5:]:
        print(line)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
