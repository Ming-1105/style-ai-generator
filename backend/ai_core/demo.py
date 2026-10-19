"""Try the compare endpoint from the terminal and see what comes back.

Run from the repo root:

    python -m backend.ai_core.demo                 # the Acme example as it is
    python -m backend.ai_core.demo tr_01=30        # set the importance of tr_01 to 30
    python -m backend.ai_core.demo tr_01=0 tr_03=50

It sends the example House Style Package to the real POST /api/compare and prints the answer.
"""

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import app

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


def main(args: list[str]) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    package = json.loads((FIXTURES / "house_style_package.json").read_text(encoding="utf-8"))
    traits = {t["id"]: t for t in package["traits"]}

    for arg in args:
        trait_id, _, value = arg.partition("=")
        if trait_id not in traits or not value.isdigit() or int(value) > 100:
            sys.exit(f"Could not read '{arg}'. Use e.g. tr_01=30 (traits: {', '.join(traits)}; importance 0-100).")
        traits[trait_id]["importance"] = int(value)

    body = {"package": package, "design_image": "https://acme-auto.example/design.png"}
    response = TestClient(app).post("/api/compare", json=body)
    result = response.json()
    if response.status_code != 200:
        sys.exit(f"Error {response.status_code}: {result['error']['message']}")

    print(f"\nOVERALL FIT: {result['overall_fit']}\n")
    print(f"{'trait':<7}{'name':<33}{'importance':>10}{'score':>7}  status")
    for s in result["trait_scores"]:
        t = traits[s["trait_id"]]
        shown = "-" if s["score"] is None else s["score"]
        print(f"{t['id']:<7}{t['name']:<33}{t['importance']:>10}{shown:>7}  {s['status']}")

    print("\nDEPARTURES")
    for d in result["departures"]:
        print(f"  - {d['text']}  {d['trait_ids']}")

    print("\nDIRECTIONS (in ranked order)")
    for number, d in enumerate(result["directions"], start=1):
        print(f"  {number}. {d['title']}  {d['trait_ids']}")
    print()


if __name__ == "__main__":
    main(sys.argv[1:])
