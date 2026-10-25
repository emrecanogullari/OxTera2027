# blunder_next5: blunder on this move or my next 4

Top 8 features that are not near-duplicates of a stronger one: **wp_self, sf_n_near_best, abs_cp, sf_gap, last_swing, mat_total, mat_diff, n_captures**

| feature | meaning | keep | mean eta | eta blitz | rho blitz | eta inside Elo bands | split-half gap |
|---|---|:-:|---:|---:|---:|---:|---:|
| `wp_self` | my engine win% before the move | ✓ | 0.231 | 0.231 | +0.064 | 0.237 | 0.005 |
| `sf_best_wp` | Stockfish's best move: my win% (depth 12) |  | 0.228 | 0.228 | +0.061 | 0.239 | 0.006 |
| `sf_n_near_best` | of Stockfish's top 4 moves, how many are within 5 win% of the best | ✓ | 0.227 | 0.227 | -0.227 | 0.224 | 0.007 |
| `abs_cp` | absolute eval in centipawns (how decided the game is) | ✓ | 0.221 | 0.221 | -0.107 | 0.221 | 0.005 |
| `sf_gap` | win% gap: Stockfish's best move minus its 2nd best | ✓ | 0.216 | 0.216 | +0.198 | 0.214 | 0.011 |
| `last_swing` | win% my opponent gave away on their last move | ✓ | 0.211 | 0.211 | +0.122 | 0.206 | 0.000 |
| `mat_total` | total material on the board (game phase) | ✓ | 0.187 | 0.187 | -0.018 | 0.200 | 0.026 |
| `ply` | half-move number |  | 0.174 | 0.174 | +0.052 | 0.202 | 0.022 |
| `frac_self` | clock_self / starting time (NaN for 0+k games) |  | 0.163 | 0.163 | -0.066 | 0.184 | 0.018 |
| `mat_diff` | my material - opponent's (P=1 N=B=3 R=5 Q=9) | ✓ | 0.156 | 0.156 | +0.031 | 0.171 | 0.007 |
| `n_captures` | legal captures available | ✓ | 0.144 | 0.144 | +0.143 | 0.148 | 0.003 |
| `clock_opp` | seconds on opponent's clock |  | 0.143 | 0.143 | -0.029 | 0.155 | 0.029 |
| `clock_self` | seconds on my clock as I start thinking |  | 0.141 | 0.141 | -0.023 | 0.158 | 0.040 |
| `n_legal` | number of legal moves (complexity) |  | 0.130 | 0.130 | +0.123 | 0.143 | 0.007 |
| `clock_ratio` | clock_self / clock_opp |  | 0.123 | 0.123 | +0.013 | 0.149 | 0.005 |
| `prev_opp_spent` | opponent's think time on their last move |  | 0.114 | 0.114 | +0.116 | 0.112 | 0.014 |
| `prev_self_spent` | my think time on my previous move |  | 0.105 | 0.105 | +0.106 | 0.100 | 0.011 |
| `avg_self_spent` | my average think time so far this game |  | 0.085 | 0.085 | +0.066 | 0.107 | 0.010 |
| `elo_self` | my rating |  | 0.081 | 0.081 | -0.077 | 0.094 | 0.004 |
| `elo_opp` | opponent's rating |  | 0.080 | 0.080 | -0.075 | 0.090 | 0.002 |
| `sf_vs_lichess` | |Stockfish win% - Lichess win%| for this position: how unsure the eval is |  | 0.067 | 0.067 | +0.058 | 0.084 | 0.012 |
| `prior_blunders_self` | my blunders so far this game |  | 0.066 | 0.066 | +0.055 | 0.105 | 0.007 |
| `sf_best_capture` | 1 if Stockfish's best move is a capture |  | 0.036 | 0.036 | +0.036 | 0.030 | 0.006 |
| `elo_diff` | elo_self - elo_opp |  | 0.034 | 0.034 | -0.009 | 0.083 | 0.013 |
| `n_checks` | legal checks available |  | 0.032 | 0.032 | +0.051 | 0.047 | 0.029 |
| `in_check` | 1 if I am in check |  | 0.016 | 0.016 | -0.016 | 0.028 | 0.009 |
| `base` | starting time (s) |  | 0.011 | 0.011 | +0.011 | 0.028 | 0.002 |
| `sf_best_check` | 1 if Stockfish's best move gives check |  | 0.003 | 0.003 | +0.003 | 0.026 | 0.006 |
| `inc` | increment (s) |  | nan | nan | +nan | nan | nan |

eta: correlation ratio over feature deciles (0-1, catches non-linear shapes). rho: Spearman (sign = direction). 'inside Elo bands' = mean eta computed within each rating band: if it is much lower than mean eta, the feature mostly stands in for rating. split-half gap = |eta(half A) - eta(half B)| over two random halves of the games (small = stable).
