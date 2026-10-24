# blunder_next5: blunder on this move or my next 4

Top 8 features that are not near-duplicates of a stronger one: **wp_self, last_swing, abs_cp, mat_total, mat_diff, n_captures, frac_self, n_legal**

| feature | meaning | keep | mean eta | eta bullet | eta blitz | eta classical | rho bullet | rho blitz | rho classical | eta inside Elo bands | split-half gap |
|---|---|:-:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `wp_self` | my engine win% before the move | ✓ | 0.231 | 0.239 | 0.220 | 0.236 | +0.063 | +0.064 | +0.061 | 0.244 | 0.013 |
| `last_swing` | win% my opponent gave away on their last move | ✓ | 0.227 | 0.237 | 0.219 | 0.224 | +0.160 | +0.133 | +0.138 | 0.225 | 0.013 |
| `abs_cp` | absolute eval in centipawns (how decided the game is) | ✓ | 0.215 | 0.222 | 0.208 | 0.216 | -0.117 | -0.084 | -0.116 | 0.228 | 0.012 |
| `mat_total` | total material on the board (game phase) | ✓ | 0.155 | 0.164 | 0.167 | 0.135 | -0.008 | -0.013 | +0.028 | 0.176 | 0.008 |
| `mat_diff` | my material - opponent's (P=1 N=B=3 R=5 Q=9) | ✓ | 0.155 | 0.178 | 0.136 | 0.151 | +0.027 | +0.024 | +0.033 | 0.174 | 0.017 |
| `ply` | half-move number |  | 0.144 | 0.146 | 0.156 | 0.131 | +0.046 | +0.043 | +0.000 | 0.164 | 0.003 |
| `n_captures` | legal captures available | ✓ | 0.125 | 0.133 | 0.128 | 0.113 | +0.132 | +0.135 | +0.120 | 0.131 | 0.011 |
| `frac_self` | clock_self / starting time (NaN for 0+k games) | ✓ | 0.118 | 0.129 | 0.130 | 0.095 | -0.060 | -0.059 | -0.022 | 0.133 | 0.005 |
| `n_legal` | number of legal moves (complexity) | ✓ | 0.115 | 0.123 | 0.118 | 0.105 | +0.119 | +0.115 | +0.102 | 0.124 | 0.009 |
| `clock_self` | seconds on my clock as I start thinking |  | 0.101 | 0.110 | 0.113 | 0.079 | -0.053 | -0.024 | -0.010 | 0.120 | 0.009 |
| `clock_opp` | seconds on opponent's clock |  | 0.100 | 0.101 | 0.123 | 0.076 | -0.052 | -0.025 | -0.011 | 0.120 | 0.014 |
| `elo_self` | my rating |  | 0.098 | 0.060 | 0.103 | 0.130 | -0.055 | -0.097 | -0.130 | 0.060 | 0.027 |
| `elo_opp` | opponent's rating |  | 0.095 | 0.062 | 0.101 | 0.122 | -0.056 | -0.096 | -0.121 | 0.062 | 0.024 |
| `clock_ratio` | clock_self / clock_opp |  | 0.086 | 0.087 | 0.108 | 0.065 | +0.002 | +0.005 | +0.001 | 0.102 | 0.007 |
| `prev_opp_spent` | opponent's think time on their last move |  | 0.083 | 0.073 | 0.111 | 0.066 | +0.078 | +0.112 | +0.064 | 0.079 | 0.015 |
| `prev_self_spent` | my think time on my previous move |  | 0.078 | 0.066 | 0.105 | 0.064 | +0.069 | +0.106 | +0.062 | 0.073 | 0.013 |
| `avg_self_spent` | my average think time so far this game |  | 0.058 | 0.056 | 0.087 | 0.030 | +0.046 | +0.075 | +0.009 | 0.069 | 0.013 |
| `prior_blunders_self` | my blunders so far this game |  | 0.053 | 0.050 | 0.057 | 0.051 | +0.050 | +0.051 | +0.060 | 0.067 | 0.034 |
| `n_checks` | legal checks available |  | 0.037 | 0.036 | 0.037 | 0.037 | +0.049 | +0.057 | +0.050 | 0.046 | 0.022 |
| `elo_diff` | elo_self - elo_opp |  | 0.030 | 0.022 | 0.028 | 0.039 | -0.001 | -0.008 | -0.021 | 0.051 | 0.008 |
| `base` | starting time (s) |  | 0.022 | 0.037 | 0.022 | 0.007 | -0.030 | +0.016 | -0.004 | 0.042 | 0.015 |
| `inc` | increment (s) |  | 0.020 | 0.014 | 0.011 | 0.035 | -0.004 | -0.001 | -0.034 | 0.029 | 0.030 |
| `in_check` | 1 if I am in check |  | 0.014 | 0.014 | 0.013 | 0.014 | -0.014 | -0.013 | -0.014 | 0.022 | 0.013 |

eta: correlation ratio over feature deciles (0-1, catches non-linear shapes). rho: Spearman (sign = direction). 'inside Elo bands' = mean eta computed within each rating band: if it is much lower than mean eta, the feature mostly stands in for rating. split-half gap = |eta(half A) - eta(half B)| over two random halves of the games (small = stable).
