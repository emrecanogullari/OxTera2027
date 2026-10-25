# Stockfish features vs the FEATURE_SET.md features (Tiger blitz games)

993 games, 62,062 moves. eta = correlation ratio (0-1), rho = Spearman (sign = direction), 'inside Elo bands' = mean eta within each rating band. 'closest existing feature' = the FEATURE_SET.md feature with the largest |Spearman rho| to it (>= 0.8 = near-duplicate).

## think_time

Top 8 (no near-duplicates): **ply, avg_self_spent, clock_self, prev_opp_spent, prev_self_spent, clock_ratio, n_legal, n_captures**

| feature | rank (of 29) | eta | eta inside Elo bands | rho | closest existing feature |
|---|---:|---:|---:|---:|---|
| `sf_best_wp` | 15 | 0.171 | 0.180 | +0.030 | `wp_self` (+0.99) |
| `sf_gap` | 23 | 0.094 | 0.104 | +0.058 | `last_swing` (+0.27) |
| `sf_n_near_best` | 25 | 0.060 | 0.063 | -0.042 | `last_swing` (-0.25) |
| `sf_vs_lichess` | 19 | 0.100 | 0.099 | +0.091 | `abs_cp` (+0.28) |
| `sf_best_capture` | 24 | 0.064 | 0.071 | -0.062 | `n_captures` (+0.38) |
| `sf_best_check` | 28 | 0.013 | 0.011 | +0.016 | `n_checks` (+0.39) |

## blunder

Top 8 (no near-duplicates): **last_swing, sf_gap, sf_n_near_best, wp_self, abs_cp, mat_total, n_captures, clock_opp**

| feature | rank (of 29) | eta | eta inside Elo bands | rho | closest existing feature |
|---|---:|---:|---:|---:|---|
| `sf_best_wp` | 5 | 0.142 | 0.149 | +0.072 | `wp_self` (+0.99) |
| `sf_gap` | 2 | 0.216 | 0.214 | +0.168 | `last_swing` (+0.27) |
| `sf_n_near_best` | 3 | 0.203 | 0.200 | -0.198 | `last_swing` (-0.25) |
| `sf_vs_lichess` | 20 | 0.061 | 0.072 | +0.057 | `abs_cp` (+0.28) |
| `sf_best_capture` | 25 | 0.020 | 0.022 | +0.020 | `n_captures` (+0.38) |
| `sf_best_check` | 24 | 0.032 | 0.036 | +0.032 | `n_checks` (+0.39) |

## blunder_next5

Top 8 (no near-duplicates): **wp_self, sf_n_near_best, abs_cp, sf_gap, last_swing, mat_total, mat_diff, n_captures**

| feature | rank (of 29) | eta | eta inside Elo bands | rho | closest existing feature |
|---|---:|---:|---:|---:|---|
| `sf_best_wp` | 2 | 0.228 | 0.239 | +0.061 | `wp_self` (+0.99) |
| `sf_gap` | 5 | 0.216 | 0.214 | +0.198 | `last_swing` (+0.27) |
| `sf_n_near_best` | 3 | 0.227 | 0.224 | -0.227 | `last_swing` (-0.25) |
| `sf_vs_lichess` | 21 | 0.067 | 0.084 | +0.058 | `abs_cp` (+0.28) |
| `sf_best_capture` | 23 | 0.036 | 0.030 | +0.036 | `n_captures` (+0.38) |
| `sf_best_check` | 28 | 0.003 | 0.026 | +0.003 | `n_checks` (+0.39) |
