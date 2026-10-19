SELECT count(*) AS n, min(id) AS first_id, max(id) AS last_id, count(DISTINCT id) AS distinct_ids FROM metric_results WHERE run_id = 'verify-idem-run-0001' AND item_id = 'verify-idem-item-0001' AND metric_name = 'safety';
SELECT id, run_id, item_id, metric_name, score, normalized_score, confidence, version, cost_usd, created_at FROM metric_results WHERE run_id = 'verify-idem-run-0001' AND item_id = 'verify-idem-item-0001';
SELECT count(*) AS n FROM item_executions WHERE run_id = 'verify-idem-run-0001' AND item_id = 'verify-idem-item-0001';
