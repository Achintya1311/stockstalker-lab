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
