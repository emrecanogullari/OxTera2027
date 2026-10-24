-- Test version of option F: clock-only buckets (no engine gap yet).
-- Budget is p75 think time; plan fallback when the knee is not estimated.

DELETE FROM lookup_budgets WHERE version = 'probe-1000-2026-09';

INSERT INTO lookup_budgets (
  version, tc, rating_band, ply_phase, clk_frac_band, gap_band,
  n, p50_s, p75_s, budget_s
)
SELECT
  'probe-1000-2026-09' AS version,
  tc,
  rating_band,
  ply_phase,
  clk_frac_band,
  'none' AS gap_band,
  COUNT(*)::int AS n,
  percentile_cont(0.50) WITHIN GROUP (ORDER BY think_s) AS p50_s,
  percentile_cont(0.75) WITHIN GROUP (ORDER BY think_s) AS p75_s,
  percentile_cont(0.75) WITHIN GROUP (ORDER BY think_s) AS budget_s
FROM move_metrics
WHERE NOT premove
  AND think_s >= 0
  AND success IS NOT NULL
GROUP BY tc, rating_band, ply_phase, clk_frac_band
HAVING COUNT(*) >= 5;
