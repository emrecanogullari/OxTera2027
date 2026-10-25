# Cross-validation on the training games (5 folds, grouped by game)

Every candidate saw the same held-out games. 'trees (chosen)' is what was saved.

## bullet / think_time

2,000 games, 120,055 moves. Chosen: max_leaf_nodes=7, min_samples_leaf=100, 630 rounds, monotone constraints off.

| model | mae_s | median_ae_s | within_2x | coverage_80 | spearman | loss |
|---|---:|---:|---:|---:|---:|---:|
| constant | 1.3029 | 1.0000 | 0.8749 |  |  | 0.1933 |
| linear | 1.1627 | 1.0000 | 0.9061 |  | 0.4412 | 0.1705 |
| splines (additive) | 1.1228 | 1.0000 | 0.9090 |  | 0.5077 | 0.1653 |
| trees, all 23 features | 1.0823 | 1.0000 | 0.9199 |  | 0.5452 | 0.1596 |
| trees (chosen) | 1.1064 | 1.0000 | 0.9129 | 0.8000 | 0.5143 | 0.1631 |
| repeat my last think time | 1.5771 | 1.0000 | 0.8142 |  | 0.3261 |  |

## bullet / blunder

2,000 games, 121,517 moves. Chosen: max_leaf_nodes=7, min_samples_leaf=500, 300 rounds, monotone constraints on {'elo_self': -1}, flag cutoff 17.9% (f1 rule: precision 30%, recall 40%, F1 0.34, accuracy 92.1%).

| model | auc | pr_auc | log_loss | log_loss_skill | brier_skill | top10_lift | ece |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant | 0.5000 | 0.0511 | 0.2017 | -0.0001 | -0.0000 | 1.0000 | 0.0020 |
| linear | 0.8100 | 0.2263 | 0.1685 | 0.1644 | 0.0869 | 4.4248 | 0.0054 |
| splines (additive) | 0.8454 | 0.2506 | 0.1584 | 0.2149 | 0.1185 | 4.8227 | 0.0024 |
| trees, all 23 features | 0.8529 | 0.2669 | 0.1553 | 0.2301 | 0.1322 | 4.9983 | 0.0010 |
| trees (chosen) | 0.8517 | 0.2593 | 0.1558 | 0.2278 | 0.1292 | 4.9612 | 0.0011 |

## bullet / blunder_next5

2,000 games, 124,055 moves. Chosen: max_leaf_nodes=31, min_samples_leaf=100, 60 rounds, monotone constraints on {'clock_self': -1, 'elo_self': -1}, flag cutoff 22.6% (f1 rule: precision 36%, recall 70%, F1 0.48, accuracy 69.8%).

| model | auc | pr_auc | log_loss | log_loss_skill | brier_skill | top10_lift | ece |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant | 0.5000 | 0.1984 | 0.4982 | -0.0000 | -0.0000 | 1.0000 | 0.0030 |
| linear | 0.7377 | 0.3978 | 0.4401 | 0.1168 | 0.1138 | 2.4015 | 0.0072 |
| splines (additive) | 0.7645 | 0.4280 | 0.4245 | 0.1480 | 0.1425 | 2.5424 | 0.0067 |
| trees, all 23 features | 0.7690 | 0.4347 | 0.4214 | 0.1542 | 0.1485 | 2.5749 | 0.0061 |
| trees (chosen) | 0.7692 | 0.4344 | 0.4213 | 0.1544 | 0.1488 | 2.5778 | 0.0032 |

## blitz / think_time

2,000 games, 132,159 moves. Chosen: max_leaf_nodes=7, min_samples_leaf=500, 500 rounds, monotone constraints off.

| model | mae_s | median_ae_s | within_2x | coverage_80 | spearman | loss |
|---|---:|---:|---:|---:|---:|---:|
| constant | 3.7572 | 2.0000 | 0.7336 |  |  | 0.2902 |
| linear | 3.4132 | 2.0000 | 0.7440 |  | 0.4951 | 0.2506 |
| splines (additive) | 3.2643 | 2.0000 | 0.7648 |  | 0.5563 | 0.2385 |
| trees, all 23 features | 3.1573 | 1.0000 | 0.7846 |  | 0.5981 | 0.2281 |
| trees (chosen) | 3.2319 | 2.0000 | 0.7713 | 0.8000 | 0.5617 | 0.2351 |
| repeat my last think time | 4.6469 | 2.0000 | 0.6454 |  | 0.3440 |  |

## blitz / blunder

2,000 games, 133,646 moves. Chosen: max_leaf_nodes=7, min_samples_leaf=100, 240 rounds, monotone constraints on {'elo_self': -1}, flag cutoff 14.6% (f1 rule: precision 25%, recall 40%, F1 0.31, accuracy 91.9%).

| model | auc | pr_auc | log_loss | log_loss_skill | brier_skill | top10_lift | ece |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant | 0.5000 | 0.0446 | 0.1825 | -0.0001 | -0.0001 | 1.0000 | 0.0018 |
| linear | 0.7987 | 0.1792 | 0.1559 | 0.1456 | 0.0646 | 4.0756 | 0.0042 |
| splines (additive) | 0.8402 | 0.2087 | 0.1462 | 0.1984 | 0.0941 | 4.6337 | 0.0025 |
| trees, all 23 features | 0.8531 | 0.2263 | 0.1422 | 0.2204 | 0.1104 | 4.9353 | 0.0008 |
| trees (chosen) | 0.8488 | 0.2197 | 0.1433 | 0.2145 | 0.1059 | 4.8180 | 0.0012 |

## blitz / blunder_next5

2,000 games, 136,159 moves. Chosen: max_leaf_nodes=7, min_samples_leaf=500, 340 rounds, monotone constraints on {'elo_self': -1}, flag cutoff 23.4% (f1 rule: precision 36%, recall 63%, F1 0.46, accuracy 73.1%).

| model | auc | pr_auc | log_loss | log_loss_skill | brier_skill | top10_lift | ece |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant | 0.5000 | 0.1792 | 0.4702 | -0.0002 | -0.0002 | 1.0000 | 0.0061 |
| linear | 0.7351 | 0.3674 | 0.4179 | 0.1110 | 0.1048 | 2.4443 | 0.0079 |
| splines (additive) | 0.7691 | 0.4053 | 0.3991 | 0.1511 | 0.1387 | 2.6632 | 0.0062 |
| trees, all 23 features | 0.7790 | 0.4202 | 0.3929 | 0.1642 | 0.1516 | 2.7645 | 0.0046 |
| trees (chosen) | 0.7741 | 0.4111 | 0.3958 | 0.1580 | 0.1448 | 2.7202 | 0.0070 |

## classical / think_time

2,000 games, 131,464 moves. Chosen: max_leaf_nodes=7, min_samples_leaf=500, 780 rounds, monotone constraints off.

| model | mae_s | median_ae_s | within_2x | coverage_80 | spearman | loss |
|---|---:|---:|---:|---:|---:|---:|
| constant | 17.6495 | 7.0000 | 0.4333 |  |  | 0.4375 |
| linear | 17.0913 | 6.0000 | 0.5322 |  | 0.5103 | 0.3752 |
| splines (additive) | 15.2456 | 6.0000 | 0.5873 |  | 0.5785 | 0.3443 |
| trees, all 23 features | 14.8357 | 6.0000 | 0.6122 |  | 0.6150 | 0.3295 |
| trees (chosen) | 15.1397 | 6.0000 | 0.5991 | 0.8000 | 0.5851 | 0.3390 |
| repeat my last think time | 21.2297 | 8.0000 | 0.5026 |  | 0.4164 |  |

## classical / blunder

2,000 games, 132,825 moves. Chosen: max_leaf_nodes=15, min_samples_leaf=500, 130 rounds, monotone constraints on {'elo_self': -1, 'frac_self': -1}, flag cutoff 16.2% (f1 rule: precision 26%, recall 39%, F1 0.31, accuracy 92.5%).

| model | auc | pr_auc | log_loss | log_loss_skill | brier_skill | top10_lift | ece |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant | 0.5000 | 0.0430 | 0.1775 | -0.0002 | -0.0001 | 1.0000 | 0.0022 |
| linear | 0.8043 | 0.1866 | 0.1504 | 0.1525 | 0.0687 | 4.3031 | 0.0037 |
| splines (additive) | 0.8484 | 0.2158 | 0.1405 | 0.2086 | 0.0990 | 4.7632 | 0.0036 |
| trees, all 23 features | 0.8577 | 0.2286 | 0.1375 | 0.2256 | 0.1121 | 4.9521 | 0.0015 |
| trees (chosen) | 0.8577 | 0.2271 | 0.1374 | 0.2258 | 0.1122 | 4.9678 | 0.0014 |

## classical / blunder_next5

2,000 games, 135,464 moves. Chosen: max_leaf_nodes=15, min_samples_leaf=500, 140 rounds, monotone constraints on {'elo_self': -1, 'frac_self': -1, 'clock_self': -1}, flag cutoff 22.3% (f1 rule: precision 36%, recall 64%, F1 0.46, accuracy 74.3%).

| model | auc | pr_auc | log_loss | log_loss_skill | brier_skill | top10_lift | ece |
|---|---:|---:|---:|---:|---:|---:|---:|
| constant | 0.5000 | 0.1717 | 0.4586 | -0.0001 | -0.0001 | 1.0000 | 0.0051 |
| linear | 0.7432 | 0.3706 | 0.4048 | 0.1173 | 0.1110 | 2.5963 | 0.0056 |
| splines (additive) | 0.7749 | 0.4023 | 0.3872 | 0.1558 | 0.1411 | 2.7351 | 0.0088 |
| trees, all 23 features | 0.7869 | 0.4221 | 0.3794 | 0.1726 | 0.1584 | 2.8598 | 0.0035 |
| trees (chosen) | 0.7812 | 0.4147 | 0.3827 | 0.1655 | 0.1515 | 2.8327 | 0.0063 |

