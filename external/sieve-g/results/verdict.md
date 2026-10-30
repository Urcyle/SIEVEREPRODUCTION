# Held-out verdict (pre-registered, PREREGISTRATION.md)

SIEVE-G with the frozen ghost ratio 0.25, Twitter clusters 25-54, 30 of 30 run. Relative reduction of SIEVE-G over SIEVE; better / equal / worse by more than 0.0001 in miss ratio.

| set | cache | clusters | mean rel. reduction | median | better | equal | worse | worse share | mean > 0 | median ≥ 0 | worse ≤ 25% | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| primary: 25-54 without 49 | 0.1% | 29 | +0.0190 | +0.0021 | 19 | 8 | 2 | 7% | yes | yes | yes | PASS |
| primary: 25-54 without 49 | 10% | 29 | +0.0045 | +0.0000 | 7 | 22 | 0 | 0% | yes | yes | yes | PASS |
| secondary: all of 25-54 | 0.1% | 30 | +0.0294 | +0.0023 | 20 | 8 | 2 | 7% | yes | yes | yes | PASS |
| secondary: all of 25-54 | 10% | 30 | +0.0077 | +0.0000 | 8 | 22 | 0 | 0% | yes | yes | yes | PASS |

## Per cluster (miss ratio)

| cluster | size | FIFO | SIEVE | SIEVE-G 0.25 | diff | rel | outcome |
|---|---|---|---|---|---|---|---|
| cluster25 | large | 0.0187 | 0.0158 | 0.0158 | 0.0 | 0.0 | equal |
| cluster26 | large | 0.0783 | 0.0782 | 0.0782 | 0.0 | 0.0 | equal |
| cluster27 | large | 0.4677 | 0.4315 | 0.4131 | -0.0184 | 0.0426 | better |
| cluster28 | large | 0.0196 | 0.0163 | 0.0162 | -0.0001 | 0.0061 | equal |
| cluster29 | large | 0.0552 | 0.0468 | 0.0468 | 0.0 | 0.0 | equal |
| cluster30 | large | 0.0117 | 0.0084 | 0.0084 | 0.0 | 0.0 | equal |
| cluster31 | large | 0.9383 | 0.9383 | 0.9383 | 0.0 | 0.0 | equal |
| cluster32 | large | 0.97 | 0.97 | 0.97 | 0.0 | 0.0 | equal |
| cluster33 | large | 0.0145 | 0.0096 | 0.0097 | 0.0001 | -0.0103 | equal |
| cluster34 | large | 0.3421 | 0.2425 | 0.2311 | -0.0114 | 0.047 | better |
| cluster35 | large | 0.07 | 0.07 | 0.07 | 0.0 | 0.0 | equal |
| cluster36 | large | 0.0533 | 0.044 | 0.044 | 0.0 | 0.0 | equal |
| cluster37 | large | 0.2188 | 0.2174 | 0.2174 | 0.0 | 0.0 | equal |
| cluster38 | large | 0.9382 | 0.9382 | 0.9382 | 0.0 | 0.0 | equal |
| cluster39 | large | 0.9384 | 0.9384 | 0.9384 | 0.0 | 0.0 | equal |
| cluster40 | large | 0.0859 | 0.0826 | 0.0826 | 0.0 | 0.0 | equal |
| cluster41 | large | 0.09 | 0.0866 | 0.0866 | 0.0 | 0.0 | equal |
| cluster42 | large | 0.0061 | 0.005 | 0.005 | 0.0 | 0.0 | equal |
| cluster43 | large | 0.0596 | 0.0557 | 0.0557 | 0.0 | 0.0 | equal |
| cluster44 | large | 0.038 | 0.0286 | 0.0284 | -0.0002 | 0.007 | better |
| cluster45 | large | 0.3916 | 0.3764 | 0.3758 | -0.0006 | 0.0016 | better |
| cluster46 | large | 0.1927 | 0.1896 | 0.1896 | 0.0 | 0.0 | equal |
| cluster47 | large | 0.003 | 0.0016 | 0.0016 | 0.0 | 0.0 | equal |
| cluster48 | large | 0.3699 | 0.3366 | 0.3365 | -0.0001 | 0.0003 | equal |
| cluster49 | large | 0.1094 | 0.0938 | 0.0844 | -0.0094 | 0.1002 | better |
| cluster50 | large | 0.2173 | 0.1884 | 0.1845 | -0.0039 | 0.0207 | better |
| cluster51 | large | 0.0065 | 0.0038 | 0.0038 | 0.0 | 0.0 | equal |
| cluster52 | large | 0.065 | 0.0524 | 0.0523 | -0.0001 | 0.0019 | equal |
| cluster53 | large | 0.0678 | 0.0555 | 0.0552 | -0.0003 | 0.0054 | better |
| cluster54 | large | 0.0652 | 0.0436 | 0.0432 | -0.0004 | 0.0092 | better |
| cluster25 | small | 0.0286 | 0.028 | 0.028 | 0.0 | 0.0 | equal |
| cluster26 | small | 0.1115 | 0.1013 | 0.1 | -0.0013 | 0.0128 | better |
| cluster27 | small | 0.7304 | 0.7029 | 0.7014 | -0.0015 | 0.0021 | better |
| cluster28 | small | 0.1095 | 0.0762 | 0.0746 | -0.0016 | 0.021 | better |
| cluster29 | small | 0.2408 | 0.2037 | 0.2024 | -0.0013 | 0.0064 | better |
| cluster30 | small | 0.2664 | 0.17 | 0.1709 | 0.0009 | -0.0053 | worse |
| cluster31 | small | 0.9383 | 0.9383 | 0.9383 | 0.0 | 0.0 | equal |
| cluster32 | small | 0.97 | 0.97 | 0.97 | 0.0 | 0.0 | equal |
| cluster33 | small | 0.1533 | 0.124 | 0.1205 | -0.0035 | 0.0282 | better |
| cluster34 | small | 0.5185 | 0.4765 | 0.4753 | -0.0012 | 0.0025 | better |
| cluster35 | small | 0.07 | 0.07 | 0.07 | 0.0 | 0.0 | equal |
| cluster36 | small | 0.2498 | 0.2135 | 0.212 | -0.0015 | 0.007 | better |
| cluster37 | small | 0.252 | 0.2405 | 0.2404 | -0.0001 | 0.0004 | equal |
| cluster38 | small | 0.9382 | 0.9383 | 0.9383 | 0.0 | 0.0 | equal |
| cluster39 | small | 0.9384 | 0.9384 | 0.9384 | 0.0 | 0.0 | equal |
| cluster40 | small | 0.2479 | 0.228 | 0.2277 | -0.0003 | 0.0013 | better |
| cluster41 | small | 0.2615 | 0.28 | 0.2406 | -0.0394 | 0.1407 | better |
| cluster42 | small | 0.2163 | 0.1594 | 0.1582 | -0.0012 | 0.0075 | better |
| cluster43 | small | 0.2412 | 0.2344 | 0.2144 | -0.02 | 0.0853 | better |
| cluster44 | small | 0.3141 | 0.2415 | 0.2408 | -0.0007 | 0.0029 | better |
| cluster45 | small | 0.5249 | 0.505 | 0.504 | -0.001 | 0.002 | better |
| cluster46 | small | 0.244 | 0.2389 | 0.2389 | 0.0 | 0.0 | equal |
| cluster47 | small | 0.3287 | 0.231 | 0.2324 | 0.0014 | -0.006 | worse |
| cluster48 | small | 0.7681 | 0.7488 | 0.7379 | -0.0109 | 0.0146 | better |
| cluster49 | small | 0.4956 | 0.9185 | 0.6137 | -0.3048 | 0.3318 | better |
| cluster50 | small | 0.7204 | 0.8811 | 0.7324 | -0.1487 | 0.1688 | better |
| cluster51 | small | 0.3359 | 0.2792 | 0.2658 | -0.0134 | 0.048 | better |
| cluster52 | small | 0.256 | 0.2123 | 0.2107 | -0.0016 | 0.0075 | better |
| cluster53 | small | 0.5103 | 0.3794 | 0.3786 | -0.0008 | 0.0021 | better |
| cluster54 | small | 0.7076 | 0.5788 | 0.578 | -0.0008 | 0.0014 | better |
