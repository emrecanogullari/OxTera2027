# think_time: seconds spent on the move

Top 8 features that are not near-duplicates of a stronger one: **avg_self_spent, prev_self_spent, prev_opp_spent, ply, clock_self, n_legal, inc, n_captures**

| feature | meaning | keep | mean eta | eta bullet | eta blitz | eta classical | rho bullet | rho blitz | rho classical | eta inside Elo bands | split-half gap |
|---|---|:-:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `avg_self_spent` | my average think time so far this game | ✓ | 0.395 | 0.424 | 0.351 | 0.411 | +0.403 | +0.345 | +0.406 | 0.381 | 0.016 |
| `prev_self_spent` | my think time on my previous move | ✓ | 0.364 | 0.325 | 0.345 | 0.423 | +0.323 | +0.353 | +0.425 | 0.352 | 0.009 |
| `prev_opp_spent` | opponent's think time on their last move | ✓ | 0.356 | 0.333 | 0.363 | 0.371 | +0.321 | +0.369 | +0.374 | 0.345 | 0.014 |
| `ply` | half-move number | ✓ | 0.326 | 0.319 | 0.371 | 0.289 | +0.098 | +0.050 | -0.002 | 0.329 | 0.018 |
| `mat_total` | total material on the board (game phase) |  | 0.298 | 0.286 | 0.331 | 0.276 | -0.050 | -0.005 | +0.070 | 0.299 | 0.009 |
| `frac_self` | clock_self / starting time (NaN for 0+k games) |  | 0.285 | 0.298 | 0.320 | 0.238 | -0.100 | -0.089 | -0.186 | 0.286 | 0.017 |
| `clock_self` | seconds on my clock as I start thinking | ✓ | 0.253 | 0.300 | 0.299 | 0.160 | +0.090 | +0.055 | -0.090 | 0.277 | 0.018 |
| `n_legal` | number of legal moves (complexity) | ✓ | 0.246 | 0.215 | 0.264 | 0.259 | +0.213 | +0.260 | +0.256 | 0.251 | 0.019 |
| `clock_opp` | seconds on opponent's clock |  | 0.225 | 0.288 | 0.261 | 0.125 | +0.081 | +0.054 | -0.025 | 0.242 | 0.016 |
| `inc` | increment (s) | ✓ | 0.221 | 0.296 | 0.228 | 0.141 | +0.257 | +0.202 | +0.129 | 0.208 | 0.011 |
| `n_captures` | legal captures available | ✓ | 0.218 | 0.217 | 0.233 | 0.204 | +0.220 | +0.253 | +0.223 | 0.231 | 0.018 |
| `clock_ratio` | clock_self / clock_opp |  | 0.217 | 0.190 | 0.240 | 0.222 | +0.020 | +0.012 | -0.101 | 0.217 | 0.015 |
| `base` | starting time (s) |  | 0.210 | 0.342 | 0.198 | 0.089 | +0.299 | +0.193 | +0.068 | 0.207 | 0.025 |
| `abs_cp` | absolute eval in centipawns (how decided the game is) |  | 0.187 | 0.171 | 0.206 | 0.184 | +0.074 | +0.072 | -0.037 | 0.197 | 0.027 |
| `wp_self` | my engine win% before the move |  | 0.176 | 0.160 | 0.187 | 0.181 | +0.032 | +0.029 | +0.018 | 0.185 | 0.024 |
| `last_swing` | win% my opponent gave away on their last move |  | 0.139 | 0.123 | 0.151 | 0.144 | +0.090 | +0.114 | +0.103 | 0.145 | 0.009 |
| `mat_diff` | my material - opponent's (P=1 N=B=3 R=5 Q=9) |  | 0.137 | 0.122 | 0.129 | 0.160 | +0.066 | +0.087 | +0.084 | 0.159 | 0.009 |
| `elo_self` | my rating |  | 0.135 | 0.195 | 0.142 | 0.067 | -0.198 | -0.146 | +0.054 | 0.079 | 0.026 |
| `elo_opp` | opponent's rating |  | 0.130 | 0.181 | 0.136 | 0.073 | -0.182 | -0.138 | +0.058 | 0.091 | 0.026 |
| `in_check` | 1 if I am in check |  | 0.070 | 0.021 | 0.080 | 0.108 | -0.016 | -0.079 | -0.110 | 0.074 | 0.008 |
| `n_checks` | legal checks available |  | 0.061 | 0.073 | 0.076 | 0.035 | +0.099 | +0.105 | +0.063 | 0.066 | 0.013 |
| `prior_blunders_self` | my blunders so far this game |  | 0.059 | 0.032 | 0.082 | 0.064 | +0.033 | +0.028 | -0.041 | 0.086 | 0.033 |
| `elo_diff` | elo_self - elo_opp |  | 0.055 | 0.081 | 0.044 | 0.040 | -0.030 | -0.016 | -0.007 | 0.070 | 0.035 |

eta: correlation ratio over feature deciles (0-1, catches non-linear shapes). rho: Spearman (sign = direction). 'inside Elo bands' = mean eta computed within each rating band: if it is much lower than mean eta, the feature mostly stands in for rating. split-half gap = |eta(half A) - eta(half B)| over two random halves of the games (small = stable). think_time is measured as log(1 + seconds).
