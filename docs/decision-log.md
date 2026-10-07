# Decision log — AI-related design decisions (date, what, why)

## 2026-10-07 — Scoring is computed in code, not by the model (Person B)

- **What:** The model will only supply a score, status and note per trait. Overall fit, the gap
  ranking that orders directions, and the signature-trait departure are computed by plain
  functions in `backend/ai_core/scoring.py`.
- **Why:** The designer can trace every derived number back to a trait score and the importance
  they set themselves, and changing an importance changes the result predictably. A model asked
  for an "overall fit" would give a number nobody can inspect.

## 2026-10-07 — A trait without a judgement is "not assessable", never 0 (Person B)

- **What:** If a trait in the package has no score (e.g. a trait the designer added by hand, or a
  view that doesn't show the feature), it gets `score: null`, `status: not_assessable` and is left
  out of overall fit. Overall fit is `null` when nothing could be assessed.
- **Why:** Counting it as 0 would lower the fit for something the AI simply could not see, which
  presents a gap in the evidence as a flaw in the design.
