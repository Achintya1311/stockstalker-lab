# Held experiments

Queue files waiting their turn. The Replay job has a 300-minute limit and commits only when the whole
queue finishes, so the C1 ingredient replays (cards/COMPOSITE_INGREDIENTS.yml) go in batches. To run a
batch, `git mv` its files into `experiments/pending/` and push. Move the next batch only after the
previous Replay run has committed its results. Nothing reads this folder.

`c5/`: month-horizon train replays (A04, A05B, A01, M01, M02; AB approved the month horizon 14 Nov 2026). They
need the month engine change on main first; see `state/engine-issues.md`.
