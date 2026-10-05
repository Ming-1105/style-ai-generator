# Kickoff prompt B: AI core

Clone the repo, open a session in it, and paste the prompt below. In later sessions you only
need the "Each new session" line at the bottom.

---

You are working with me on the Brand DNA project. Read `AGENTS.md` and `docs/STATUS.md`
before doing anything. I am **Person B — AI core**. You only edit `/backend/ai_core/`,
`/docs/` and tests for my module. Never edit other owners' folders.

**My job:** `POST /api/dna/extract` and `POST /api/compare`. This is where the course's
"AI contribution" is judged, so it has to be explainable: every trait links to evidence images,
every score has a status, and nothing is invented to fill a gap.

**Milestones, in order. Stop after each one and show me the result before continuing:**
1. **Scoring first, with no AI:** implement `overall_fit`, gap ranking and the signature-trait
   rule from AGENTS.md as pure functions, with unit tests based on the fixture numbers.
   Wire them into the mock compare path, so changing an importance value changes the result.
2. **Trait extraction** behind `MOCK_MODE=0`: send the included images plus brand info to a
   vision-capable model (provider set by `VISION_PROVIDER`; ask me which one we have keys for)
   and require **structured JSON output** that validates against the Trait model. Prompt for
   recurring visual features across images, with the image IDs that show each one. Compute
   `seen_count` from the evidence IDs, not from the model's claim. Set `low_confidence` when
   confidence < 0.6. Retry once on invalid JSON, then return a clear error.
3. **Per-trait comparison:** for each trait, ask the vision model to judge the new design
   against that trait's description and evidence images, returning score, status and a short
   note. It must use `not_assessable` when the view doesn't show the feature.
4. **Embeddings (stretch):** add an image-embedding similarity (e.g. open_clip running locally,
   no key needed) as a second signal next to the model's score. Note the known limit:
   embeddings capture content and photo conditions more than style, so record in the
   decision log how we handle that (e.g. cropping to evidence regions).
5. **Directions:** generate 3 text directions from the top gaps, each referencing its
   `trait_ids`. Leave `image_url: null` unless I ask for image generation.

**Rules:** keep the model prompts in separate files in `/backend/ai_core/prompts/` so we can
show them in the report. No new dependencies without asking me first. Use small commits on branch
`ai-core/<topic>`. At the end of each session, update my section of `docs/STATUS.md` and log
model, prompt and design decisions in `docs/decision-log.md`.

Start by summarising the contract for my two endpoints in 5 lines, then propose a plan for
milestone 1.

---
**Each new session:** "Read AGENTS.md and docs/STATUS.md, pull main, and continue as Person B
from where STATUS.md says we left off."
