# blunder: move loses >= 20 win% points

Top 8 features that are not near-duplicates of a stronger one: **last_swing, wp_self, abs_cp, mat_diff, mat_total, n_captures, frac_self, n_legal**

| feature | meaning | keep | mean eta | eta bullet | eta blitz | eta classical | rho bullet | rho blitz | rho classical | eta inside Elo bands | split-half gap |
|---|---|:-:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `last_swing` | win% my opponent gave away on their last move | ✓ | 0.241 | 0.269 | 0.228 | 0.226 | +0.154 | +0.119 | +0.117 | 0.238 | 0.008 |
| `wp_self` | my engine win% before the move | ✓ | 0.158 | 0.167 | 0.152 | 0.154 | +0.089 | +0.076 | +0.074 | 0.161 | 0.014 |
| `abs_cp` | absolute eval in centipawns (how decided the game is) | ✓ | 0.105 | 0.111 | 0.102 | 0.104 | -0.014 | -0.005 | -0.024 | 0.111 | 0.006 |
| `mat_diff` | my material - opponent's (P=1 N=B=3 R=5 Q=9) | ✓ | 0.090 | 0.101 | 0.082 | 0.087 | +0.032 | +0.028 | +0.032 | 0.098 | 0.005 |
| `mat_total` | total material on the board (game phase) | ✓ | 0.089 | 0.094 | 0.096 | 0.077 | -0.034 | -0.030 | -0.010 | 0.099 | 0.004 |
| `ply` | half-move number |  | 0.087 | 0.091 | 0.092 | 0.078 | +0.062 | +0.052 | +0.031 | 0.096 | 0.004 |
| `n_captures` | legal captures available | ✓ | 0.086 | 0.096 | 0.082 | 0.081 | +0.094 | +0.084 | +0.082 | 0.093 | 0.003 |
| `frac_self` | clock_self / starting time (NaN for 0+k games) | ✓ | 0.078 | 0.087 | 0.087 | 0.060 | -0.073 | -0.064 | -0.032 | 0.086 | 0.003 |
| `n_legal` | number of legal moves (complexity) | ✓ | 0.072 | 0.078 | 0.067 | 0.069 | +0.077 | +0.066 | +0.066 | 0.077 | 0.018 |
| `prior_blunders_self` | my blunders so far this game |  | 0.069 | 0.075 | 0.072 | 0.061 | +0.081 | +0.071 | +0.073 | 0.073 | 0.030 |
| `clock_opp` | seconds on opponent's clock |  | 0.067 | 0.074 | 0.079 | 0.049 | -0.064 | -0.040 | -0.022 | 0.076 | 0.009 |
| `clock_self` | seconds on my clock as I start thinking |  | 0.066 | 0.074 | 0.074 | 0.050 | -0.063 | -0.039 | -0.021 | 0.079 | 0.009 |
| `clock_ratio` | clock_self / clock_opp |  | 0.061 | 0.070 | 0.067 | 0.046 | +0.003 | +0.003 | +0.001 | 0.067 | 0.010 |
| `elo_self` | my rating |  | 0.056 | 0.036 | 0.058 | 0.074 | -0.034 | -0.055 | -0.072 | 0.031 | 0.015 |
| `elo_opp` | opponent's rating |  | 0.055 | 0.038 | 0.057 | 0.070 | -0.035 | -0.054 | -0.068 | 0.032 | 0.014 |
| `prev_opp_spent` | opponent's think time on their last move |  | 0.055 | 0.053 | 0.068 | 0.042 | +0.054 | +0.068 | +0.041 | 0.055 | 0.014 |
| `avg_self_spent` | my average think time so far this game |  | 0.053 | 0.055 | 0.071 | 0.032 | +0.051 | +0.067 | +0.018 | 0.055 | 0.010 |
| `prev_self_spent` | my think time on my previous move |  | 0.051 | 0.046 | 0.069 | 0.039 | +0.046 | +0.069 | +0.037 | 0.050 | 0.004 |
| `n_checks` | legal checks available |  | 0.051 | 0.056 | 0.053 | 0.045 | +0.066 | +0.061 | +0.055 | 0.056 | 0.011 |
| `in_check` | 1 if I am in check |  | 0.022 | 0.026 | 0.020 | 0.021 | -0.026 | -0.020 | -0.021 | 0.023 | 0.007 |
| `elo_diff` | elo_self - elo_opp |  | 0.015 | 0.011 | 0.013 | 0.019 | -0.001 | -0.003 | -0.010 | 0.027 | 0.006 |
| `base` | starting time (s) |  | 0.012 | 0.020 | 0.012 | 0.004 | -0.016 | +0.009 | -0.003 | 0.022 | 0.010 |
| `inc` | increment (s) |  | 0.011 | 0.008 | 0.005 | 0.020 | -0.002 | -0.003 | -0.019 | 0.016 | 0.018 |

eta: correlation ratio over feature deciles (0-1, catches non-linear shapes). rho: Spearman (sign = direction). 'inside Elo bands' = mean eta computed within each rating band: if it is much lower than mean eta, the feature mostly stands in for rating. split-half gap = |eta(half A) - eta(half B)| over two random halves of the games (small = stable).
