# Figure 4 check: SIEVE-G vs SIEVE on the 13 Figure 4 traces

diff = SIEVE-G − SIEVE miss ratio (> 0: SIEVE-G worse); flagged if > 0.005.

| trace | size | cache_size_obj | cache_fig4 | SIEVE | sieve_fig4 | sieve_equals_fig4 | SIEVE-G 0.25 | diff | flag_loss_gt_0.005 |
|---|---|---|---|---|---|---|---|---|---|
| kvcache_traces_1 | large | 1698213 | 1698213 | 0.0772 | 0.0772 | True | 0.0761 | -0.0011 | False |
| kvcache_traces_1 | small | 16982 | 16982 | 0.2951 | 0.2951 | True | 0.2949 | -0.0002 | False |
| kvcache_traces_2 | large | 1654200 | 1654200 | 0.0766 | 0.0766 | True | 0.0756 | -0.001 | False |
| kvcache_traces_2 | small | 16542 | 16542 | 0.2969 | 0.2969 | True | 0.2967 | -0.0002 | False |
| kvcache_traces_3 | large | 1616850 | 1616850 | 0.0767 | 0.0767 | True | 0.0757 | -0.001 | False |
| kvcache_traces_3 | small | 16168 | 16168 | 0.2973 | 0.2973 | True | 0.2971 | -0.0002 | False |
| kvcache_traces_4 | large | 1623601 | 1623601 | 0.0742 | 0.0742 | True | 0.0732 | -0.001 | False |
| kvcache_traces_4 | small | 16236 | 16236 | 0.291 | 0.291 | True | 0.2908 | -0.0002 | False |
| kvcache_traces_5 | large | 1666145 | 1666145 | 0.0754 | 0.0754 | True | 0.0744 | -0.001 | False |
| kvcache_traces_5 | small | 16661 | 16661 | 0.2919 | 0.2919 | True | 0.2917 | -0.0002 | False |
| meta_reag | large | 1226253 | 1226253 | 0.3213 | 0.3213 | True | 0.3195 | -0.0018 | False |
| meta_reag | small | 12262 | 12262 | 0.4269 | 0.4269 | True | 0.4255 | -0.0014 | False |
| meta_rnha | large | 3504028 | 3504028 | 0.4772 | 0.4772 | True | 0.4725 | -0.0047 | False |
| meta_rnha | small | 35040 | 35040 | 0.6606 | 0.6606 | True | 0.6584 | -0.0022 | False |
| meta_rprn | large | 2903028 | 2903028 | 0.4282 | 0.4282 | True | 0.4233 | -0.0049 | False |
| meta_rprn | small | 29030 | 29030 | 0.5823 | 0.5823 | True | 0.5799 | -0.0024 | False |
| tencent_photo1 | large | 5294521 | 5294521 | 0.2392 | 0.2392 | True | 0.2364 | -0.0028 | False |
| tencent_photo1 | small | 52945 | 52945 | 0.6785 | 0.6785 | True | 0.656 | -0.0225 | False |
| tencent_photo2 | large | 5081613 | 5081613 | 0.2448 | 0.2448 | True | 0.2416 | -0.0032 | False |
| tencent_photo2 | small | 50816 | 50816 | 0.6843 | 0.6843 | True | 0.6621 | -0.0222 | False |
| wiki_2016u | large | 3721819 | 3721819 | 0.0611 | 0.0611 | True | 0.0601 | -0.001 | False |
| wiki_2016u | small | 37218 | 37218 | 0.4598 | 0.4598 | True | 0.4657 | 0.0059 | True |
| wiki_2019t | large | 1837711 | 1837711 | 0.1866 | 0.1866 | True | 0.1833 | -0.0033 | False |
| wiki_2019t | small | 18377 | 18377 | 0.7196 | 0.7196 | True | 0.7182 | -0.0014 | False |
| wiki_2019u | large | 4961998 | 4961998 | 0.0912 | 0.0912 | True | 0.0933 | 0.0021 | False |
| wiki_2019u | small | 49619 | 49619 | 0.6459 | 0.6459 | True | 0.6448 | -0.0011 | False |
