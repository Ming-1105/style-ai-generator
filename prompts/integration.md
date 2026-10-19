# Integration prompt: when you come back together (one PC, about twice a week)

Paste this in a session on the shared PC after everyone has pushed their branches.

---

We are doing a team integration session for the Brand DNA project. Read `AGENTS.md`,
`docs/STATUS.md` and `docs/contract-changes.md`.

1. List the open branches and pull requests. For each one, give a one-line summary and whether
   it touches files outside its owner's folder (flag that clearly).
2. Merge them into `main` one at a time, in the order sourcing → ai-core → ui. After each merge,
   run the tests and check that `MOCK_MODE=1` still starts. If a conflict involves another
   owner's code, stop and show it to us. Don't resolve it yourself.
3. Run the full flow with `MOCK_MODE=1`, then with `MOCK_MODE=0` using the Acme fixtures or
   a test brand we choose. Report every place where the frontend and backend disagree with
   the contract.
4. Go through `docs/contract-changes.md` with us. For each agreed change, update AGENTS.md,
   `/contracts/` and `/fixtures/` in one commit.
5. Finish with a short "next 3 days" list per person, and write it into `docs/STATUS.md`.
