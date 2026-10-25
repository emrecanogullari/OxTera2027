# blunder: move loses >= 20 win% points

Top 8 features that are not near-duplicates of a stronger one: **last_swing, sf_gap, sf_n_near_best, wp_self, abs_cp, mat_total, n_captures, clock_opp**

| feature | meaning | keep | mean eta | eta blitz | rho blitz | eta inside Elo bands | split-half gap |
|---|---|:-:|---:|---:|---:|---:|---:|
| `last_swing` | win% my opponent gave away on their last move | ✓ | 0.231 | 0.231 | +0.116 | 0.218 | 0.009 |
| `sf_gap` | win% gap: Stockfish's best move minus its 2nd best | ✓ | 0.216 | 0.216 | +0.168 | 0.214 | 0.017 |
| `sf_n_near_best` | of Stockfish's top 4 moves, how many are within 5 win% of the best | ✓ | 0.203 | 0.203 | -0.198 | 0.200 | 0.005 |
| `wp_self` | my engine win% before the move | ✓ | 0.150 | 0.150 | +0.073 | 0.153 | 0.003 |
| `sf_best_wp` | Stockfish's best move: my win% (depth 12) |  | 0.142 | 0.142 | +0.072 | 0.149 | 0.007 |
| `abs_cp` | absolute eval in centipawns (how decided the game is) | ✓ | 0.111 | 0.111 | -0.018 | 0.111 | 0.009 |
| `mat_total` | total material on the board (game phase) | ✓ | 0.104 | 0.104 | -0.035 | 0.115 | 0.016 |
| `ply` | half-move number |  | 0.101 | 0.101 | +0.059 | 0.119 | 0.008 |
| `frac_self` | clock_self / starting time (NaN for 0+k games) |  | 0.098 | 0.098 | -0.069 | 0.110 | 0.003 |
| `n_captures` | legal captures available | ✓ | 0.095 | 0.095 | +0.091 | 0.098 | 0.005 |
| `clock_opp` | seconds on opponent's clock | ✓ | 0.088 | 0.088 | -0.044 | 0.094 | 0.012 |
| `clock_self` | seconds on my clock as I start thinking |  | 0.088 | 0.088 | -0.039 | 0.096 | 0.017 |
| `mat_diff` | my material - opponent's (P=1 N=B=3 R=5 Q=9) |  | 0.083 | 0.083 | +0.031 | 0.099 | 0.003 |
| `prev_opp_spent` | opponent's think time on their last move |  | 0.083 | 0.083 | +0.082 | 0.080 | 0.006 |
| `n_legal` | number of legal moves (complexity) |  | 0.074 | 0.074 | +0.069 | 0.084 | 0.008 |
| `prior_blunders_self` | my blunders so far this game |  | 0.074 | 0.074 | +0.072 | 0.092 | 0.005 |
| `avg_self_spent` | my average think time so far this game |  | 0.072 | 0.072 | +0.067 | 0.085 | 0.002 |
| `clock_ratio` | clock_self / clock_opp |  | 0.071 | 0.071 | +0.011 | 0.090 | 0.010 |
| `prev_self_spent` | my think time on my previous move |  | 0.071 | 0.071 | +0.070 | 0.069 | 0.004 |
| `sf_vs_lichess` | |Stockfish win% - Lichess win%| for this position: how unsure the eval is |  | 0.061 | 0.061 | +0.057 | 0.072 | 0.020 |
| `n_checks` | legal checks available |  | 0.049 | 0.049 | +0.061 | 0.062 | 0.008 |
| `elo_opp` | opponent's rating |  | 0.041 | 0.041 | -0.038 | 0.047 | 0.005 |
| `elo_self` | my rating |  | 0.041 | 0.041 | -0.039 | 0.047 | 0.007 |
| `sf_best_check` | 1 if Stockfish's best move gives check |  | 0.032 | 0.032 | +0.032 | 0.036 | 0.004 |
| `sf_best_capture` | 1 if Stockfish's best move is a capture |  | 0.020 | 0.020 | +0.020 | 0.022 | 0.005 |
| `elo_diff` | elo_self - elo_opp |  | 0.016 | 0.016 | -0.004 | 0.044 | 0.007 |
| `in_check` | 1 if I am in check |  | 0.015 | 0.015 | -0.015 | 0.014 | 0.009 |
| `base` | starting time (s) |  | 0.007 | 0.007 | +0.007 | 0.017 | 0.003 |
| `inc` | increment (s) |  | nan | nan | +nan | nan | nan |

eta: correlation ratio over feature deciles (0-1, catches non-linear shapes). rho: Spearman (sign = direction). 'inside Elo bands' = mean eta computed within each rating band: if it is much lower than mean eta, the feature mostly stands in for rating. split-half gap = |eta(half A) - eta(half B)| over two random halves of the games (small = stable).
