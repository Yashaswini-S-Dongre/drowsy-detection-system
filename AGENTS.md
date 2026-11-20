# AGENTS.md

## Rules for All Agents

These rules apply to all agents working on the Driver Drowsiness Detection System project.

1.  **Follow the synopsis first;** log any deviation in `docs/DECISIONS.md`.
2.  **Only edit your own folder.** Never edit `/contracts` unilaterally (requires PR approved by all owners).
3.  **Every module has unit tests;** no merge with failing tests; keep code `ruff`/`black` clean.
4.  **Use type hints and docstrings** on public functions; use config-driven thresholds (no magic numbers).
5.  **Never commit datasets,** model weights over 50 MB, or any raw driver video. Provide download scripts instead.
6.  **Never fabricate accuracy numbers.** All reported metrics must come from an actual run, saved in a report file. If a dataset is unavailable, say so and use the synthetic path, clearly labelled as synthetic.
7.  **Do not fabricate citations.** Use only references from the synopsis. Note: refs [2] and [7] have unconfirmed authors; keep the "verify before submission" flag.
8.  **Keep code runnable** on Windows, macOS, and Linux where feasible (provide `.ps1` and `.sh` scripts).
9.  **Prefer small, reviewable commits;** use branches named `p1/...`, `p2/...`, `p3/...`, `p4/...`.
10. **If something is ambiguous or blocked, ask the lead/user** rather than guessing on anything that affects interfaces, safety behavior, or scope.
