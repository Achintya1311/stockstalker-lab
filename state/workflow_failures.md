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
