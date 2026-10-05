# Kickoff prompt C: Interface

Clone the repo, open a session in it, and paste the prompt below. In later sessions you only
need the "Each new session" line at the bottom.

---

You are working with me on the Brand DNA project. Read `AGENTS.md` and `docs/STATUS.md`
before doing anything. I am **Person C — Interface**. You only edit `/frontend/`, `/docs/`
and frontend tests. Never edit other owners' folders.

**My job:** turn the clickable mockup in `/frontend/` into the real app, in five steps: Brand →
Sources → Style DNA → House style → Compare. It talks only to the three endpoints in AGENTS.md.
Until the backend is real, it runs against mock mode, so I never have to wait for my teammates.

**Milestones, in order. Stop after each one and show me the result before continuing:**
1. Replace all hard-coded data in the mockup with `fetch` calls to the API. Keep one
   `state` object holding brand, candidates, traits, package and compare result, and render
   every screen from it.
2. Loading and error states for every call: show progress while waiting, and show the API's
   `error.message` text to the designer. Make `null` scores and `not_assessable` /
   `low_confidence` statuses visible and honest (no fake bars).
3. Make the human controls real: include/exclude images, rename/remove/add traits, importance
   sliders. Changing importance on the Compare screen recalculates `overall_fit` and the
   direction order live, using the formula in AGENTS.md (it's cheap, so do it client-side).
4. Upload your own design (file input → data URL → `/api/compare`) and accept/reject
   directions into an editable design-notes list.
5. Export the House Style Package as JSON (download) so a package can be reloaded later.

**Rules:** plain HTML/CSS/JS, no framework or build step. Keep the mockup's visual design.
Never show a real brand's images in committed files. Always show the source domain next to
web images. Use small commits on branch `ui/<topic>`. At the end of each session, update my
section of `docs/STATUS.md`. If I need a change to the API or data shape, write it in
`docs/contract-changes.md` instead of working around it.

Start by listing which mockup screens use which endpoint and contract fields, then propose
a plan for milestone 1.

---
**Each new session:** "Read AGENTS.md and docs/STATUS.md, pull main, and continue as Person C
from where STATUS.md says we left off."
