# Trace files removed from `data/` on 2026-10-20 (to make room for the remaining Twitter samples)

At the user's request, two large Twitter traces whose results are complete and saved were deleted from the main disk. Nothing else was removed. Both are public and can be fetched again from the URL below; the stored SHA-256 identifies the exact file (`local_results/twitter_clusterNN_trace.json` holds the full identity record).

| file | stored bytes | SHA-256 | URL | what remains |
|---|---|---|---|---|
| `data/twitter/cluster21.oracleGeneral.zst` | 14,125,669,039 (13.2 GiB) | `46a0b03f8dfc423f7a123ce5e28cddc329ed5e0fdf01f05c08949649497b93af` | https://ftp.pdl.cmu.edu/pub/datasets/twemcacheWorkload/cacheDatasets/twitter/cluster21.oracleGeneral.zst | six-policy 0.1% counters, exact-WSS scan, ghost-variant runs, trace-frequency sample; 10% runs were never possible (memory gate) |
| `data/twitter/cluster38.oracleGeneral.zst` | 12,848,828,452 (12.0 GiB) | `68e34cba250b3718a98989e72ace48ea47e3e623be9d7649bee1c7cc4e33bce8` | https://ftp.pdl.cmu.edu/pub/datasets/twemcacheWorkload/cacheDatasets/twitter/cluster38.oracleGeneral.zst | six-policy 0.1% and five-policy 10% counters, exact-WSS scan, ghost-variant runs; ARC at 10% was memory-blocked |

Consequences: the saved counters, receipts, tables and figures are unchanged and still verify against their own records. Re-running any simulation on these two clusters, or the retained-input checks that hash the file, needs the file downloaded again (about 25 GB). The choice was made because both traces had the largest size, no outstanding runs, and no retry that fits the 12 GiB memory budget.

**Tests:** one cluster38 test (`test_saved_exact_scan_pins_floor_capacities`) is skipped while the file is absent, and the 16-trace preflight test checks the 14 traces still on disk (`tests/test_trace_key_frequency_sample.py`, `tests/test_twitter_cluster38_reporting.py`). Re-download the files above to run them in full.

## Second removal (2026-10-23): batch-2 Twitter sample files

To make room for the Meta KV per-trace split and further runs, the eleven sample files of the sample10 extension were deleted after all their runs, omissions and ghost checks were complete (results, identity records and counters stay). Each can be fetched again from its URL; the SHA-256 identifies the file.

| file | bytes | SHA-256 | URL |
|---|---|---|---|
| `data/twitter_sample10/cluster25.oracleGeneral.sample10.zst` | 1,838,842,513 | `63b975d7dc865d3d12875d5bf82fd66828c636629b89a0118ab1c407b170b6e3` | https://ftp.pdl.cmu.edu/pub/datasets/twemcacheWorkload/cacheDatasets/twitter/sample10/cluster25.oracleGeneral.sample10.zst |
| `data/twitter_sample10/cluster27.oracleGeneral.sample100.zst` | 1,374,185,931 | `fd371d484ec283ade8eb5fb7efa7119c9db97baebb7b7ef27c088d5a153258d5` | https://ftp.pdl.cmu.edu/pub/datasets/twemcacheWorkload/cacheDatasets/twitter/sample100/cluster27.oracleGeneral.sample100.zst |
| `data/twitter_sample10/cluster28.oracleGeneral.sample10.zst` | 2,874,032,498 | `29270e9bbb440d004eb8f88d64bee4af7cf9d26fc03967790bb7601b515ebb62` | https://ftp.pdl.cmu.edu/pub/datasets/twemcacheWorkload/cacheDatasets/twitter/sample10/cluster28.oracleGeneral.sample10.zst |
| `data/twitter_sample10/cluster30.oracleGeneral.sample10.zst` | 1,243,459,987 | `bd1d2ed5e158d2861769ae7ac8d9553ad68031a9d5c8f4070349a694daa76045` | https://ftp.pdl.cmu.edu/pub/datasets/twemcacheWorkload/cacheDatasets/twitter/sample10/cluster30.oracleGeneral.sample10.zst |
| `data/twitter_sample10/cluster33.oracleGeneral.sample10.zst` | 3,257,485,907 | `7d7e54940604146b2223e3ff8c73f2a33b2afba8031d096f7f0e2967d28f00df` | https://ftp.pdl.cmu.edu/pub/datasets/twemcacheWorkload/cacheDatasets/twitter/sample10/cluster33.oracleGeneral.sample10.zst |
| `data/twitter_sample10/cluster34.oracleGeneral.sample10.zst` | 1,883,906,491 | `655c73054b12677476c74b5accdfc4a8cff950ae6e71693dbc47459ff61db376` | https://ftp.pdl.cmu.edu/pub/datasets/twemcacheWorkload/cacheDatasets/twitter/sample10/cluster34.oracleGeneral.sample10.zst |
| `data/twitter_sample10/cluster36.oracleGeneral.sample10.zst` | 3,225,770,418 | `406f90e542a3ff570c185062b02db268cf87e2639dd1c8b1b43c4993a316c8f2` | https://ftp.pdl.cmu.edu/pub/datasets/twemcacheWorkload/cacheDatasets/twitter/sample10/cluster36.oracleGeneral.sample10.zst |
| `data/twitter_sample10/cluster42.oracleGeneral.sample10.zst` | 1,694,452,248 | `460d8d1f476b59a29cb86a091fea438069d9e71b491405b0156a54abd8f372ab` | https://ftp.pdl.cmu.edu/pub/datasets/twemcacheWorkload/cacheDatasets/twitter/sample10/cluster42.oracleGeneral.sample10.zst |
| `data/twitter_sample10/cluster44.oracleGeneral.sample10.zst` | 3,405,669,965 | `bbbf4bb0682e7a6b229141787532734c03638ade29f5ef4669e06e714242041e` | https://ftp.pdl.cmu.edu/pub/datasets/twemcacheWorkload/cacheDatasets/twitter/sample10/cluster44.oracleGeneral.sample10.zst |
| `data/twitter_sample10/cluster47.oracleGeneral.sample10.zst` | 3,103,009,969 | `e184447c3e7710767c0ffd770050f9978477591ee809e6a88fa59bfcca52320d` | https://ftp.pdl.cmu.edu/pub/datasets/twemcacheWorkload/cacheDatasets/twitter/sample10/cluster47.oracleGeneral.sample10.zst |
| `data/twitter_sample10/cluster51.oracleGeneral.sample10.zst` | 2,975,859,064 | `af133865e9ba572ce9aae6de1353ca5e4e6af2d43e01877d2545b65e28def645` | https://ftp.pdl.cmu.edu/pub/datasets/twemcacheWorkload/cacheDatasets/twitter/sample10/cluster51.oracleGeneral.sample10.zst |

## Third removal (2026-10-24): `wiki_2016u`

Downloaded 2026-10-24 for `docs/wiki_full_extension_protocol.md`; deleted after its 22 runs (CACHEUS omitted by the memory gate), the six TinyLFU build runs and the comparison were complete, to make room for `wiki_2019u` (the disk holds one at a time). Counters, identity record and tables stay; the file can be fetched again and the SHA-256 identifies it.

| file | stored bytes | SHA-256 | URL |
|---|---|---|---|
| `data/wiki/wiki_2016u.oracleGeneral.zst` | 24,283,806,419 | `25d50ca53c22dfca70691d3abbaa5df57c9a86aa88dfc9223ca701dd418c3c38` | https://ftp.pdl.cmu.edu/pub/datasets/twemcacheWorkload/cacheDatasets/wiki/wiki_2016u.oracleGeneral.zst |

Records: 2,803,498,585; distinct objects with nonzero size 37,197,832; decompressed-stream SHA-256 `783e93f7a2b979f893b6cb08f504aba0a9257f810fb6b25c7d71d79af3dc3955`.


## Fourth removal (2026-10-24): `data/metakv_split/` (derived, regenerable)

`/home` reached 0 bytes free while `wiki_2019u` (27.3 GB) was being used, and the Wiki runs need room to write. The five Meta KV parts cut from the merged `202206` file (3.9 GB in all) were deleted: they are derived data, not a download, and their runs (110 of 120; CACHEUS omitted), the pre-fix TinyLFU runs and the capacity-sensitivity runs are complete and saved. Nothing else was removed. The merged source file `data/metakv_2022/` is kept, so the parts are regenerated by `python3 -B scripts/split_metakv_202206.py`, and the SHA-256 below identifies each part (also in `local_results/metakv_split_extension/metakv_trace*_identity.json`). Re-running any Meta KV simulation (for example CACHEUS on these parts) needs that regeneration first.

| file | stored bytes | SHA-256 |
|---|---|---|
| `data/metakv_split/kvcache_traces_1.valid.oracleGeneral.zst` | 843,092,944 | `7538e1c947c8bc6a5cb615b5c1263c734fa85779df3864d3737c0b812d2640c6` |
| `data/metakv_split/kvcache_traces_2.valid.oracleGeneral.zst` | 828,559,200 | `cd8dfd7ab118be4962f29b8c2f3dc41e4f8ccb67ed16bffa4c5a76102386a87d` |
| `data/metakv_split/kvcache_traces_3.valid.oracleGeneral.zst` | 801,218,581 | `5e62714dc55cacdc6f5089f34bddb42fb2de4505b340e8bb25d531f77e5b4d70` |
| `data/metakv_split/kvcache_traces_4.valid.oracleGeneral.zst` | 813,011,103 | `cd8094dbc3122de47ade9589b1af284de359c1e7d64b5a0619f014811ec7a896` |
| `data/metakv_split/kvcache_traces_5.valid.oracleGeneral.zst` | 826,492,032 | `b296e79f2027f5823177a40c6b21e069088f9360be6623997fc8f8b0a7cda9dd` |

## Fifth removal (2026-10-25): `wiki_2019u`

Downloaded 2026-10-24 for `docs/wiki_full_extension_protocol.md`; deleted after its 22 runs (CACHEUS omitted by the memory gate), the six TinyLFU build runs and the comparison were complete. Counters, identity record and tables stay; the file can be fetched again and the SHA-256 identifies it.

| file | stored bytes | SHA-256 | URL |
|---|---|---|---|
| `data/wiki/wiki_2019u.oracleGeneral.zst` | 27,328,797,214 | `271294871178c0ee999989d08e4a4ecfbf205c304096518a6e5ce3f9ab9123c2` | https://ftp.pdl.cmu.edu/pub/datasets/twemcacheWorkload/cacheDatasets/wiki/wiki_2019u.oracleGeneral.zst |

Records: 2,655,612,611; distinct objects with nonzero size 49,707,463; decompressed-stream SHA-256 `540e9ebce40b022a5376ef2f57811785770350bb7f3646d0d13439dd7f6b29ad`.

## Sixth removal (2026-10-26): `wiki_2016u` and `wiki_2019u` again

Both files were downloaded a second time for `docs/wiki_full_extension_protocol.md` amendment 2 (CACHEUS), their SHA-256 checked against the values recorded above, and deleted after the attempts (2016u: both CACHEUS cells ran; 2019u: omitted by the memory gate). `data/wiki/` holds only `wiki_2019t` again. The script's log was lost in a reboot (temporary directory), so the verification is by the script's design and the identical hashes recorded here, not by a saved log.
