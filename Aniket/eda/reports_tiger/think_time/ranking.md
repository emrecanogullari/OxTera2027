# think_time: seconds spent on the move

Top 8 features that are not near-duplicates of a stronger one: **ply, avg_self_spent, clock_self, prev_opp_spent, prev_self_spent, clock_ratio, n_legal, n_captures**

| feature | meaning | keep | mean eta | eta blitz | rho blitz | eta inside Elo bands | split-half gap |
|---|---|:-:|---:|---:|---:|---:|---:|
| `ply` | half-move number | ✓ | 0.376 | 0.376 | +0.134 | 0.385 | 0.008 |
| `frac_self` | clock_self / starting time (NaN for 0+k games) |  | 0.369 | 0.369 | -0.200 | 0.373 | 0.018 |
| `avg_self_spent` | my average think time so far this game | ✓ | 0.353 | 0.353 | +0.343 | 0.331 | 0.011 |
| `mat_total` | total material on the board (game phase) |  | 0.346 | 0.346 | -0.080 | 0.343 | 0.025 |
| `clock_self` | seconds on my clock as I start thinking | ✓ | 0.338 | 0.338 | -0.005 | 0.330 | 0.073 |
| `prev_opp_spent` | opponent's think time on their last move | ✓ | 0.333 | 0.333 | +0.342 | 0.326 | 0.001 |
| `prev_self_spent` | my think time on my previous move | ✓ | 0.326 | 0.326 | +0.335 | 0.314 | 0.006 |
| `clock_opp` | seconds on opponent's clock |  | 0.320 | 0.320 | +0.006 | 0.314 | 0.059 |
| `clock_ratio` | clock_self / clock_opp | ✓ | 0.258 | 0.258 | -0.013 | 0.267 | 0.019 |
| `n_legal` | number of legal moves (complexity) | ✓ | 0.254 | 0.254 | +0.249 | 0.259 | 0.008 |
| `n_captures` | legal captures available | ✓ | 0.250 | 0.250 | +0.254 | 0.250 | 0.014 |
| `abs_cp` | absolute eval in centipawns (how decided the game is) |  | 0.224 | 0.224 | +0.114 | 0.230 | 0.007 |
| `wp_self` | my engine win% before the move |  | 0.202 | 0.202 | +0.028 | 0.209 | 0.000 |
| `base` | starting time (s) |  | 0.185 | 0.185 | +0.178 | 0.170 | 0.023 |
| `sf_best_wp` | Stockfish's best move: my win% (depth 12) |  | 0.171 | 0.171 | +0.030 | 0.180 | 0.004 |
| `last_swing` | win% my opponent gave away on their last move |  | 0.142 | 0.142 | +0.106 | 0.151 | 0.024 |
| `mat_diff` | my material - opponent's (P=1 N=B=3 R=5 Q=9) |  | 0.136 | 0.136 | +0.083 | 0.148 | 0.007 |
| `n_checks` | legal checks available |  | 0.104 | 0.104 | +0.130 | 0.102 | 0.012 |
| `sf_vs_lichess` | |Stockfish win% - Lichess win%| for this position: how unsure the eval is |  | 0.100 | 0.100 | +0.091 | 0.099 | 0.011 |
| `prior_blunders_self` | my blunders so far this game |  | 0.099 | 0.099 | +0.081 | 0.105 | 0.004 |
| `elo_opp` | opponent's rating |  | 0.095 | 0.095 | -0.093 | 0.075 | 0.015 |
| `elo_self` | my rating |  | 0.094 | 0.094 | -0.093 | 0.072 | 0.016 |
| `sf_gap` | win% gap: Stockfish's best move minus its 2nd best |  | 0.094 | 0.094 | +0.058 | 0.104 | 0.015 |
| `sf_best_capture` | 1 if Stockfish's best move is a capture |  | 0.064 | 0.064 | -0.062 | 0.071 | 0.006 |
| `sf_n_near_best` | of Stockfish's top 4 moves, how many are within 5 win% of the best |  | 0.060 | 0.060 | -0.042 | 0.063 | 0.005 |
| `in_check` | 1 if I am in check |  | 0.059 | 0.059 | -0.057 | 0.064 | 0.002 |
| `elo_diff` | elo_self - elo_opp |  | 0.026 | 0.026 | -0.005 | 0.066 | 0.016 |
| `sf_best_check` | 1 if Stockfish's best move gives check |  | 0.013 | 0.013 | +0.016 | 0.011 | 0.001 |
| `inc` | increment (s) |  | nan | nan | +nan | nan | nan |

eta: correlation ratio over feature deciles (0-1, catches non-linear shapes). rho: Spearman (sign = direction). 'inside Elo bands' = mean eta computed within each rating band: if it is much lower than mean eta, the feature mostly stands in for rating. split-half gap = |eta(half A) - eta(half B)| over two random halves of the games (small = stable). think_time is measured as log(1 + seconds).
