## 2026-10-16T18:21Z dataset failed
Run: https://github.com/Achintya1311/stockstalker-lab/actions/runs/38946618236
```
Traceback (most recent call last):
  File "/opt/hostedtoolcache/Python/3.12.15/x64/lib/python3.12/site-packages/pandas/core/indexes/base.py", line 3641, in get_loc
    return self._engine.get_loc(casted_key)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "pandas/_libs/index.pyx", line 168, in pandas._libs.index.IndexEngine.get_loc
  File "pandas/_libs/index.pyx", line 197, in pandas._libs.index.IndexEngine.get_loc
  File "pandas/_libs/hashtable_class_helper.pxi", line 7668, in pandas._libs.hashtable.PyObjectHashTable.get_item
  File "pandas/_libs/hashtable_class_helper.pxi", line 7676, in pandas._libs.hashtable.PyObjectHashTable.get_item
KeyError: 'TtlTrdgVal'

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "/home/runner/work/stockstalker-lab/stockstalker-lab/scripts/build_dataset.py", line 182, in <module>
    main()
  File "/home/runner/work/stockstalker-lab/stockstalker-lab/scripts/build_dataset.py", line 170, in main
    fresh = build(raw_root) if raw_root.exists() else pd.DataFrame(columns=PRICE_COLUMNS + ["has_future"])
            ^^^^^^^^^^^^^^^
  File "/home/runner/work/stockstalker-lab/stockstalker-lab/scripts/build_dataset.py", line 122, in build
    cm_frames = [parse_cm_file(p) for p in sorted(raw_root.rglob("cm_*.csv.zip"))]
                 ^^^^^^^^^^^^^^^^
  File "/home/runner/work/stockstalker-lab/stockstalker-lab/scripts/build_dataset.py", line 98, in parse_cm_file
    "turnover": df["TtlTrdgVal"].astype(float),
                ~~^^^^^^^^^^^^^^
  File "/opt/hostedtoolcache/Python/3.12.15/x64/lib/python3.12/site-packages/pandas/core/frame.py", line 4378, in __getitem__
    indexer = self.columns.get_loc(key)
              ^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/hostedtoolcache/Python/3.12.15/x64/lib/python3.12/site-packages/pandas/core/indexes/base.py", line 3648, in get_loc
    raise KeyError(key) from err
KeyError: 'TtlTrdgVal'
```

RESOLVED in this commit: the turnover column is `TtlTrfVal`, not `TtlTrdgVal`. The synthetic test header was also wrong (`SsrIndctr`); both now follow docs/nse_formats.md.

## 2026-10-17T1208Z replay failed (commit step itself; `engine.run_queue` succeeded)
Run: https://github.com/Achintya1311/stockstalker-lab/actions/runs/39024479250

This run's own failure-reporting step also failed, so nothing landed here
automatically - appended by hand after reading the job log via the public
API (`curl .../actions/jobs/117388818220/logs`). Full diagnosis in
`state/engine-issues.md` ("READY FOR WIRING: replay.yml commit-step race").

```
wrote reports/market_line_train.md
wrote reports/selftest.md
wrote reports/champion_v1_train.md
no experiments queued
[main ee4858c] replay: results 2026-10-17T1208Z
 1 file changed, 59 insertions(+)
 create mode 100644 reports/champion_v1_train.md
Auto-merging reports/champion_v1_train.md
CONFLICT (add/add): Merge conflict in reports/champion_v1_train.md
error: could not apply ee4858c... replay: results 2026-10-17T1208Z
Could not apply ee4858c... # replay: results 2026-10-17T1208Z
##[error]Process completed with exit code 1.
git reset -q --hard; git pull -q
You are not currently on a branch.
Please specify which branch you want to merge with.
##[error]Process completed with exit code 1.
```

RESOLVED (supervised, 17 Oct, commit "ci: wire guard, live picks and safe pushes"): replay checks out the latest main and every workflow commits through `.github/push.sh`. See the WIRED entry in engine-issues.md.

## 2026-10-17T15:58Z guard restored protected paths
Commits in 8470946..8131980 changed protected paths outside a supervised session, so they are back as they were at 8470946. Describe the change you need in state/engine-issues.md instead, then add RESOLVED <commit> under this entry.
- `engine/__init__.py`
RESOLVED 8131980 (supervised): a deliberate live test of the guard. Nothing to redo.

## 2026-10-25T17:06Z evidence failed
Run: https://github.com/Achintya1311/stockstalker-lab/actions/runs/40214739477
```
/opt/hostedtoolcache/Python/3.12.15/x64/lib/python3.12/site-packages/arch/bootstrap/multiple_comparison.py:220: RuntimeWarning: invalid value encountered in divide
  std_loss_diffs = loss_diffs / np.sqrt(variances)
/opt/hostedtoolcache/Python/3.12.15/x64/lib/python3.12/site-packages/arch/bootstrap/multiple_comparison.py:221: RuntimeWarning: invalid value encountered in divide
  std_bs_mean_losses = bootstrapped_mean_losses / np.sqrt(variances)
Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "/home/runner/work/stockstalker-lab/stockstalker-lab/scripts/evidence_report.py", line 102, in <module>
    raise SystemExit(main())
                     ^^^^^^
  File "/home/runner/work/stockstalker-lab/stockstalker-lab/scripts/evidence_report.py", line 92, in main
    res = build(Path(a.data), Path(a.done))
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/runner/work/stockstalker-lab/stockstalker-lab/scripts/evidence_report.py", line 61, in build
    out[f"{horizon}/{SIDES[side]}"] = {"experiments": rows, "joint": multiple_testing(frame, size=0.10)}
                                                                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/runner/work/stockstalker-lab/stockstalker-lab/scripts/evidence_stats.py", line 60, in multiple_testing
    mcs.compute()
  File "/opt/hostedtoolcache/Python/3.12.15/x64/lib/python3.12/site-packages/arch/bootstrap/multiple_comparison.py", line 189, in compute
    self._compute_r()
  File "/opt/hostedtoolcache/Python/3.12.15/x64/lib/python3.12/site-packages/arch/bootstrap/multiple_comparison.py", line 239, in _compute_r
    i = loc.squeeze()[0]
        ~~~~~~~~~~~~~^^^
IndexError: index 0 is out of bounds for axis 0 with size 0
```

RESOLVED in the commit that adds this line: A05B's bearish picks are identical to A05's on all 295 dates (A05B is a monotone re-scoring of A05's own z, so the five most lottery-like stocks are the same), which gave two identical edge series. Their loss difference has zero variance, and arch's MCS divided by it and found no model to eliminate (IndexError). `scripts/evidence_stats.multiple_testing` now runs the joint tests on one copy of each exact twin and reports the twin with its original's StepM and MCS membership (`twins` in the JSON, one sentence in the markdown). Reproduced locally first; regression test in `tests/test_evidence_stats.py`. The push to `scripts/evidence_*.py` re-runs `evidence.yml`.
