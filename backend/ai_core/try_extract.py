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
from pathlib import Path

from dotenv import load_dotenv

from backend.ai_core.errors import AiCoreError
from backend.ai_core.extract import extract_dna
from contracts.models import Brand, ImageCandidate


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


def main(argv: list[str]) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Try Style DNA extraction on real images.")
    parser.add_argument("--brand", required=True)
    parser.add_argument("--category", default="")
    parser.add_argument("--keywords", default="", help="comma-separated")
    parser.add_argument("--values", default="")
    parser.add_argument("--model", help="overrides VISION_MODEL from .env for this run")
    parser.add_argument("images", nargs="+", help="image file paths or web addresses")
    args = parser.parse_args(argv)

    load_dotenv(".env")
    if args.model:
        os.environ["VISION_MODEL"] = args.model
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
    print()


if __name__ == "__main__":
    main(sys.argv[1:])
