# Held experiments

Queue files waiting their turn. The Replay job has a 300-minute limit and commits only when the whole
queue finishes, so the C1 ingredient replays (cards/COMPOSITE_INGREDIENTS.yml) go in batches. To run a
batch, `git mv` its files into `experiments/pending/` and push. Move the next batch only after the
previous Replay run has committed its results. Nothing reads this folder.

`c5/`: month-horizon train replays (A04, A05B, A01, M01, M02; AB approved the month horizon 14 Nov 2026). They
need the month engine change on main first; see `state/engine-issues.md`.

`exit/`: exit-plan payoff replays (AB approved exit scoring 14 Nov 2026; `engine/exits.py`). Train only. Four live
rules (A01, A05B, E2A, T04) x three exit presets (fixed, trail, time). `batch_1/` holds the six week-table ymls,
`batch_2/` the six day-table ymls (each day replay takes 20 to 38 minutes, so batch_2 may need splitting to stay
inside the 300-minute limit). Move a batch's files flat into `experiments/pending/`; after the results land, run
`python3 -m scripts.exit_report` to rebuild `research/diagnostics/exit_v1.md`.
