"""Try trait extraction on real images from the terminal, with the model set in .env.

Run from the repo root (put the images anywhere outside the repo, or in local_test_images/):

    python -m backend.ai_core.try_extract --brand "Some Brand" --category "vacuum cleaners" \
        C:\\path\\to\\photo1.jpg C:\\path\\to\\photo2.png https://example.com/photo3.jpg

    python -m backend.ai_core.try_extract --brand "Some Brand" --model gemini-3.1-pro-preview *.jpg

Images can be file paths or web addresses. They are read into memory for this one run and
are never copied into the repo. This calls the real model, so it uses your API quota.
Works regardless of MOCK_MODE.
"""

import argparse
import base64
import logging
import mimetypes
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from backend.ai_core import usage
from backend.ai_core.errors import AiCoreError
from backend.ai_core.extract import extract_dna
from contracts.models import Brand, HouseStylePackage, ImageCandidate, Trait


def build_candidates(sources: list[str]) -> list[ImageCandidate]:
    """One ImageCandidate per file path or web address, numbered img_01, img_02, ..."""
    candidates = []
    for number, source in enumerate(sources, start=1):
        if source.startswith(("http://", "https://")):
            url, domain = source, source.split("/")[2]
        else:
            path = Path(source)
            media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            url = f"data:{media_type};base64," + base64.b64encode(path.read_bytes()).decode("ascii")
            domain = "local file"
        candidates.append(ImageCandidate(
            id=f"img_{number:02d}", url=url, thumbnail_url=url, source_domain=domain,
            source_type="upload", category="other", relevance=1.0, included=True,
        ))
    return candidates


SAME_TRAIT_OVERLAP = 0.5  # two traits are "the same" if their evidence images overlap this much


def group_runs(runs: list[list[Trait]]) -> list[dict]:
    """Match traits across runs by the images they cite (the names change from run to run).

    Returns groups, most frequent first: how many runs found the trait, the names it went by,
    and how many runs cited each image for it.
    """
    groups: list[dict] = []
    for run_number, traits in enumerate(runs):
        for trait in traits:
            evidence = set(trait.evidence_image_ids)
            best = max(
                (g for g in groups if run_number not in g["runs"]),  # one trait per run per group
                key=lambda g: len(evidence & g["evidence"]) / len(evidence | g["evidence"]),
                default=None,
            )
            if best and len(evidence & best["evidence"]) / len(evidence | best["evidence"]) >= SAME_TRAIT_OVERLAP:
                group = best
            else:
                group = {"runs": [], "names": [], "evidence": set(), "image_counts": {}}
                groups.append(group)
            group["runs"].append(run_number)
            group["names"].append(trait.name)
            group["evidence"] |= evidence
            for image_id in evidence:
                group["image_counts"][image_id] = group["image_counts"].get(image_id, 0) + 1
    return sorted(groups, key=lambda g: len(g["runs"]), reverse=True)


def print_runs_summary(groups: list[dict], run_count: int) -> None:
    print(f"\nTRAITS ACROSS {run_count} RUNS (traits matched by the images they cite)\n")
    for group in groups:
        found = len(group["runs"])
        print(f"found in {found}/{run_count} runs   {' / '.join(dict.fromkeys(group['names']))}")
        images = sorted(group["image_counts"].items(), key=lambda item: (-item[1], item[0]))
        print("      images (runs citing them): " + ", ".join(f"{i} ({n})" for i, n in images))
    print()


def main(argv: list[str]) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Try Style DNA extraction on real images.")
    parser.add_argument("--brand", required=True)
    parser.add_argument("--category", default="")
    parser.add_argument("--keywords", default="", help="comma-separated")
    parser.add_argument("--values", default="")
    parser.add_argument("--model", help="overrides VISION_MODEL from .env for this run")
    parser.add_argument("--detail", choices=["low", "medium", "high"], help="image detail for this run (VISION_IMAGE_DETAIL)")
    parser.add_argument("--save-package", metavar="FILE",
                        help="write the result as a House Style Package JSON, for try_compare "
                             "(keep it in local_test_images/: it contains the brand name)")
    parser.add_argument("--runs", type=int, default=1,
                        help="run extraction this many times and show which traits keep coming back "
                             "(each run is one API request)")
    parser.add_argument("images", nargs="+", help="image file paths or web addresses")
    args = parser.parse_args(argv)

    load_dotenv(".env")
    if args.model:
        os.environ["VISION_MODEL"] = args.model
    if args.detail:
        os.environ["VISION_IMAGE_DETAIL"] = args.detail
    logging.basicConfig(level=logging.WARNING, format="  note: %(message)s")

    missing = [s for s in args.images if not s.startswith("http") and not Path(s).is_file()]
    if missing:
        sys.exit("These files were not found: " + ", ".join(missing))

    candidates = build_candidates(args.images)
    brand = Brand(name=args.brand, category=args.category,
                  keywords=[k.strip() for k in args.keywords.split(",") if k.strip()], values=args.values)

    print(f"\nModel: {os.getenv('VISION_PROVIDER')} / {os.getenv('VISION_MODEL') or '(default)'}")
    print("Images:")
    for candidate, source in zip(candidates, args.images):
        print(f"  {candidate.id}  {Path(source).name if candidate.source_domain == 'local file' else source}")

    if args.runs > 1:
        all_runs = []
        for number in range(1, args.runs + 1):
            started = time.time()
            try:
                all_runs.append(extract_dna(brand, candidates).traits)
            except AiCoreError as problem:
                print(f"run {number}/{args.runs}: FAILED ({problem.code}): {problem.message}")
                break
            print(f"run {number}/{args.runs}: {len(all_runs[-1])} traits in {time.time() - started:.0f}s")
        if not all_runs:
            sys.exit("No run finished, so there is nothing to summarise.")
        print_runs_summary(group_runs(all_runs), len(all_runs))
        print(usage.session_summary())
        return

    started = time.time()
    try:
        result = extract_dna(brand, candidates)
    except AiCoreError as problem:
        sys.exit(f"\nError ({problem.code}): {problem.message}")
    print(f"\nDone in {time.time() - started:.0f}s. {len(result.traits)} traits found.\n")

    for trait in result.traits:
        flag = "  [LOW CONFIDENCE]" if trait.low_confidence else ""
        print(f"{trait.id}  {trait.name}{flag}")
        print(f"      {trait.description}")
        print(f"      seen in {trait.seen_count}/{len(candidates)} images: {', '.join(trait.evidence_image_ids)}"
              f"   confidence {trait.confidence:.2f}   suggested importance {trait.importance}")
    print("\nTone words:", ", ".join(result.tone_words) or "-")
    print("Colors:    ", ", ".join(f"{c.name} {c.hex}" for c in result.colors) or "-")
    print("Do / don't:" + ("" if result.do_dont else " -"))
    for rule in result.do_dont:
        print(f"   do:   {rule.do}\n   dont: {rule.dont}")
    print("Skipped:   ", ", ".join(f"{s.id} ({s.reason})" for s in result.skipped_images) or "none")
    print()

    if args.save_package:
        package = HouseStylePackage(
            created_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            brand=brand, traits=result.traits, tone_words=result.tone_words, colors=result.colors, do_dont=result.do_dont,
            source_image_ids=[c.id for c in candidates],
        )
        Path(args.save_package).write_text(package.model_dump_json(indent=2), encoding="utf-8")
        print(f"Saved package to {args.save_package}\n")
    print(usage.session_summary())


if __name__ == "__main__":
    main(sys.argv[1:])
