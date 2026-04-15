from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import ROOT
from .runner import ScenarioRunner


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Crescent Harbor direct filer")
    parser.add_argument("--scenario", help="Single scenario file to run")
    parser.add_argument("--output", default="results.json", help="Results file path")
    args = parser.parse_args()

    runner = ScenarioRunner()
    if args.scenario:
        payload = {"results": [runner.run_scenario(Path(args.scenario)).__dict__]}
    else:
        payload = runner.run_all(ROOT / "scenarios")

    output_path = Path(args.output)
    output_path.write_text(json.dumps(payload, indent=2) + "\n")


if __name__ == "__main__":
    main()
