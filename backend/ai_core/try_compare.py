"""Try design comparison on a real image from the terminal, with the model set in .env.

First make a package (traits from your reference images), then compare a design with it:

    python -m backend.ai_core.try_extract --brand "Some Brand" --save-package local_test_images/pkg.json <images>
    python -m backend.ai_core.try_compare local_test_images/pkg.json local_test_images/my_design.png

Options:
    --runs 3        compare 3 times and show how much each score moves (each run is one API request)
    --model NAME    overrides VISION_MODEL from .env
    --importance tr_01=30 tr_02=0   change the designer's importance values for this run

The design can be a file path or a web address. It is read into memory for this run and
never copied into the repo. Works regardless of MOCK_MODE.
"""

import argparse
import base64
import logging
import mimetypes
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

from backend.ai_core.compare import compare_design
from backend.ai_core.errors import AiCoreError
from contracts.models import CompareResult, HouseStylePackage


def design_as_url(source: str) -> str:
    if source.startswith(("http://", "https://")):
        return source
    path = Path(source)
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return f"data:{media_type};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def print_result(result: CompareResult, package: HouseStylePackage) -> None:
    traits = {t.id: t for t in package.traits}
    print(f"\nOVERALL FIT: {result.overall_fit}\n")
    print(f"{'trait':<7}{'name':<36}{'importance':>10}{'score':>7}  status / note")
    for s in result.trait_scores:
        shown = "-" if s.score is None else s.score
        print(f"{s.trait_id:<7}{traits[s.trait_id].name[:34]:<36}{traits[s.trait_id].importance:>10}{shown:>7}  {s.status}: {s.note}")
    print("\nMATCHES")
    for m in result.matches:
        print(f"  - {m.text}  {m.trait_ids}")
    print("\nDEPARTURES")
    for d in result.departures:
        print(f"  - {d.text}  {d.trait_ids}")
    print()


def print_spread(results: list[CompareResult], package: HouseStylePackage) -> None:
    print(f"\nHOW MUCH THE SCORES MOVE ACROSS {len(results)} RUNS\n")
    print(f"{'trait':<7}{'name':<36}  scores per run")
    for trait in package.traits:
        per_run = []
        for result in results:
            score = next(s for s in result.trait_scores if s.trait_id == trait.id)
            per_run.append("n/a" if score.score is None else str(score.score))
        numbers = [int(x) for x in per_run if x != "n/a"]
        spread = f"   (spread {max(numbers) - min(numbers)})" if len(numbers) > 1 else ""
        print(f"{trait.id:<7}{trait.name[:34]:<36}  {', '.join(per_run)}{spread}")
    print("overall fit per run:", ", ".join(str(r.overall_fit) for r in results), "\n")


def main(argv: list[str]) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Try design comparison on a real image.")
    parser.add_argument("package", help="House Style Package JSON (from try_extract --save-package)")
    parser.add_argument("design", help="design image: file path or web address")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--model")
    parser.add_argument("--importance", nargs="*", default=[], metavar="TRAIT=VALUE")
    args = parser.parse_args(argv)

    load_dotenv(".env")
    if args.model:
        os.environ["VISION_MODEL"] = args.model
    logging.basicConfig(level=logging.WARNING, format="  note: %(message)s")

    package = HouseStylePackage.model_validate_json(Path(args.package).read_text(encoding="utf-8"))
    by_id = {t.id: t for t in package.traits}
    for setting in args.importance:
        trait_id, _, value = setting.partition("=")
        if trait_id not in by_id or not value.isdigit() or int(value) > 100:
            sys.exit(f"Could not read '{setting}'. Use e.g. tr_01=30 (traits: {', '.join(by_id)}).")
        by_id[trait_id].importance = int(value)
    if not args.design.startswith("http") and not Path(args.design).is_file():
        sys.exit(f"Design file not found: {args.design}")

    design = design_as_url(args.design)
    print(f"\nModel: {os.getenv('VISION_PROVIDER')} / {os.getenv('VISION_MODEL') or '(default)'}")
    results = []
    for number in range(1, args.runs + 1):
        started = time.time()
        try:
            results.append(compare_design(package, design))
        except AiCoreError as problem:
            print(f"run {number}/{args.runs}: FAILED ({problem.code}): {problem.message}")
            break
        print(f"run {number}/{args.runs}: done in {time.time() - started:.0f}s")
    if not results:
        sys.exit("No run finished, so there is nothing to show.")

    print_result(results[0], package)
    if len(results) > 1:
        print_spread(results, package)


if __name__ == "__main__":
    main(sys.argv[1:])
