# Kickoff prompt A: Sourcing (good fit for the Codex user)

Clone the repo, open a session in it, and paste the prompt below. In later sessions you only
need the "Each new session" line at the bottom.

---

You are working with me on the Brand DNA project. Read `AGENTS.md` and `docs/STATUS.md`
before doing anything. I am **Person A — Sourcing**. You only edit `/backend/sourcing/`,
`/docs/` and tests for my module. Never edit other owners' folders.

**My job:** `POST /api/sources/search`. It takes a Brand and returns ImageCandidate[] exactly
as the contract defines. The designer reviews these in the Sources screen, so the output has to be easy
to judge: good categories, honest relevance scores, and clear flag reasons.

**Milestones, in order. Stop after each one and show me the result before continuing:**
1. Keep the mock path working, and add a real path behind `MOCK_MODE=0` using one image
   search API (suggest SerpAPI or Google Custom Search, and tell me the free-tier limits so I
   can choose). Build queries from brand name + category + keywords (e.g. "<brand> logo",
   "<brand> <category> official").
2. Optional scraping of the brand's official website URL: collect `<img>` tags from that
   single page only. Respect robots.txt. No crawling beyond the given URL.
3. Remove duplicates (same URL, or near-identical images via a perceptual hash) and drop
   tiny images.
4. Flagging with plain-language reasons: low resolution, a domain that doesn't match the
   brand (possible different company), and likely fan art or renders. Flagged images get
   `included: false`. Keep heuristics simple and explain each one in a code comment.
5. Category and relevance: a simple first version (keywords in the title/URL/alt text) is
   fine. Only add a vision model if I ask for it.

**Rules:** no new dependencies without asking me first. Clear error messages for the designer
(no results, API quota reached, invalid key). Use small commits on branch `sourcing/<topic>`.
At the end of each session, update my section of `docs/STATUS.md` and log decisions in
`docs/decision-log.md`.

Start by summarising the contract for my endpoint in 5 lines, then propose a plan for
milestone 1.

---
**Each new session:** "Read AGENTS.md and docs/STATUS.md, pull main, and continue as Person A
from where STATUS.md says we left off."
