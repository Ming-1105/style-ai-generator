# Brand DNA — shared agent instructions

Read this whole file at the start of every session. It is the contract between three people
working in parallel, each with their own coding agent (Claude Code or Codex). The agents
cannot talk to each other, so this file is how they coordinate. When it conflicts with
anything else, this file wins, unless the human in your session says otherwise.

## What we are building

A design tool for the TU Delft IDE course "Generative AI and Design". An industrial designer
enters a brand. The tool finds reference images on the web, and the designer reviews them.
AI extracts the brand's "Style DNA" as a list of named, evidence-linked, editable traits,
which the designer locks into a House Style Package. The designer then uploads their own
design and gets per-trait similarity scores, matches and departures, and suggested design
directions that point back to specific traits.

The core principle is that **the AI measures and suggests, and the designer decides.** Every AI output
must be inspectable and editable, and must report honestly when it cannot judge something.

This is a student prototype for a 7-minute demo, not a product. Prefer simple, readable code
over abstractions. No auth, no database (JSON files on disk are fine), no deployment setup.

## Stack (agreed — change only through a contract change, see below)

- Backend: Python 3.11+, FastAPI, served on `http://localhost:8000`
- Frontend: plain HTML/CSS/JS (no framework), based on the clickable mockup, served by the
  backend from `/frontend`
- Config: `.env` (never committed). `.env.example` lists every variable with an empty value.
- `MOCK_MODE=1` (default) makes every endpoint return fixture data from `/fixtures`, so
  everything runs without API keys. Every module must keep a working mock path.

## Folder ownership

| Folder | Owner | Notes |
|---|---|---|
| `/backend/sourcing/` | Person A — Sourcing | image search, scraping known URLs, dedupe, flagging |
| `/backend/ai_core/` | Person B — AI core | trait extraction, embeddings, scoring, directions |
| `/frontend/` | Person C — Interface | the app UI |
| `/backend/main.py`, `/contracts/`, `/fixtures/`, `AGENTS.md` | Shared | contract changes only |
| `/docs/` | Everyone | status, decision log, contract-change proposals |

**Only edit files in your own folder.** If you need something from another folder, do not
edit it. Tell your human and add a note to `docs/STATUS.md` under the owner's section.

## Data contract

All IDs are strings. Scores are 0–100 integers. Confidence is a 0–1 float. `null` means
"could not be determined". Never replace it with a made-up number.

```jsonc
// ImageCandidate
{
  "id": "img_01",
  "url": "https://…",
  "thumbnail_url": "https://…",
  "source_domain": "vorden-auto.example",
  "source_type": "search | scrape | presskit | upload",
  "category": "product | logo | packaging | web | other",
  "relevance": 0.91,
  "flagged": false,
  "flag_reason": null,            // e.g. "Fan render — not official"
  "included": true                // designer's choice; flagged images default to false
}

// Trait
{
  "id": "tr_01",
  "name": "Blade headlights",
  "description": "Sharp, tapered LED graphic that narrows to a point at the outer edge.",
  "evidence_image_ids": ["img_01", "img_04"],
  "seen_count": 9,                // number of included images showing it
  "confidence": 0.92,
  "importance": 90,               // 0–100, set by the designer (AI may suggest a default)
  "low_confidence": false,        // true when confidence < 0.6
  "origin": "ai | manual"
}

// HouseStylePackage
{
  "version": 1,
  "created_at": "2026-10-05T12:00:00Z",
  "brand": { "name": "", "category": "", "website": "", "keywords": [], "values": "" },
  "traits": [ /* Trait */ ],
  "tone_words": ["Precise", "Restrained"],
  "colors": [ { "name": "Graphite", "hex": "#2B2F33" } ],
  "do_dont": [ { "do": "Taper light graphics to a point", "dont": "Round or oval lamps" } ],
  "source_image_ids": ["img_01"]
}

// CompareResult
{
  "overall_fit": 61,              // null if no trait could be assessed
  "trait_scores": [
    { "trait_id": "tr_01", "score": 31, "status": "ok | low_confidence | not_assessable",
      "note": "Lamps are round; brand uses tapered blades." }
  ],
  "matches":    [ { "text": "…", "trait_ids": ["tr_03"] } ],
  "departures": [ { "text": "…", "trait_ids": ["tr_01"] } ],
  "directions": [
    { "id": "dir_a", "title": "Sharpen the lamps", "rationale": "…",
      "trait_ids": ["tr_01"], "image_url": null }   // image optional
  ]
}
```

### Scoring rules (implemented in ai_core, displayed by frontend)

- `overall_fit = Σ(score × importance) / Σ(importance)` over traits with status `ok` or
  `low_confidence`. Traits that are `not_assessable` are left out, not counted as 0.
- Directions are ranked by `gap = importance × (100 − score)`. Traits with importance 0
  never generate a direction.
- Traits with importance ≥ 80 are "signature" traits. If one of them scores < 40, add a
  departure, whatever the overall fit.

## API

| Method | Path | Body | Returns | Owner |
|---|---|---|---|---|
| POST | `/api/sources/search` | `{ "brand": Brand }` | `{ "candidates": ImageCandidate[] }` | A |
| POST | `/api/dna/extract` | `{ "brand": Brand, "images": ImageCandidate[] }` | `{ "traits": Trait[], "tone_words": [], "colors": [] }` | B |
| POST | `/api/compare` | `{ "package": HouseStylePackage, "design_image": "<data URL or https URL>" }` | `CompareResult` | B |

Errors use HTTP 4xx/5xx with `{ "error": { "code": "…", "message": "…" } }`. The message is
written for the designer, e.g. "Image search returned nothing for this brand — try adding
the official website."

`/backend/main.py` only wires the routers together. Each owner exposes a FastAPI `APIRouter`
from their own package.

## Fixtures

`/fixtures/` holds example responses for every endpoint, using the fictional brand
**"Vorden"** (automotive). Mock mode returns these. The frontend develops against them.
Never use real brand names, logos or scraped images in fixtures or committed files.

## Working rules

1. **Start of session:** `git checkout main && git pull`, read this file and `docs/STATUS.md`,
   then create or switch to your branch: `<area>/<short-name>` (e.g. `sourcing/serpapi`).
2. **Small, frequent merges.** Commit working steps. Open a pull request to `main` at least
   every other day. Do not leave a branch open for a week.
3. **Never commit secrets.** API keys live in `.env` only. Check `git status` before committing.
4. **Keep mock mode working.** `MOCK_MODE=1 uvicorn backend.main:app` must always run.
5. **Honest failures.** Never invent scores, traits or images to fill a gap. Return `null`,
   a `not_assessable` status, or a clear error.
6. **Copyright.** Scraped images are used transiently for analysis. Do not save them in the
   repo. Show the source domain wherever an image is displayed.
7. **End of session:** update your section in `docs/STATUS.md` (done / in progress / blocked /
   needs from others), and add any AI-related design decision to `docs/decision-log.md`
   (date, what, why — we need this for the course report).
8. **Ask your human before** adding a dependency, changing the stack, or doing anything
   outside your folder.

## Contract changes

If the data contract, API or stack needs to change: do not change it yourself. Write a short
proposal in `docs/contract-changes.md` (what, why, who is affected) and tell your human.
The team agrees on it, and then one person updates this file, the fixtures and `/contracts/`
in a single PR.


