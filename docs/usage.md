# AI usage and cost

Every Gemini call writes one structured log line (`api/kedai/usage.py`). On Cloud Run these land in
**Cloud Logging** as JSON, linked to the action's trace in **Cloud Trace**.

```json
{"event": "gemini_usage", "feature": "ask", "model": "gemini-3.5-flash-lite", "shop_id": "demo",
 "session_id": "8f1c…", "input_tokens": 5120, "output_tokens": 96, "cost_usd": 0.001776}
```

- `feature`: `scan`, `ask`, `briefing` or `speak`
- `session_id`: an anonymous id per browser tab (no login, no personal data)
- `cost_usd`: an **estimate** from the list prices in `PRICES` in `usage.py`; the bill is the source of truth

## See individual calls: Logs Explorer

Console → Logging → Logs Explorer:

```
resource.type="cloud_run_revision"
jsonPayload.event="gemini_usage"
```

Click an entry's trace link to open the whole action in Cloud Trace (Console → Trace → Trace Explorer).

## Add up cost: Log Analytics

Console → Logging → Logs Storage → upgrade the `_Default` bucket to use Log Analytics (one-time, no charge
for the upgrade). Then in Log Analytics:

```sql
-- Cost per feature, last 7 days
SELECT
  JSON_VALUE(json_payload.feature) AS feature,
  COUNT(*) AS calls,
  SUM(CAST(JSON_VALUE(json_payload.input_tokens) AS INT64)) AS input_tokens,
  SUM(CAST(JSON_VALUE(json_payload.output_tokens) AS INT64)) AS output_tokens,
  ROUND(SUM(CAST(JSON_VALUE(json_payload.cost_usd) AS FLOAT64)), 4) AS cost_usd
FROM `PROJECT_ID.global._Default._AllLogs`
WHERE JSON_VALUE(json_payload.event) = 'gemini_usage'
  AND timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
GROUP BY feature
ORDER BY cost_usd DESC;
```

```sql
-- What one visitor costs (e.g. a judge trying the demo)
SELECT
  JSON_VALUE(json_payload.session_id) AS visitor,
  COUNT(*) AS ai_calls,
  ROUND(SUM(CAST(JSON_VALUE(json_payload.cost_usd) AS FLOAT64)), 4) AS cost_usd
FROM `PROJECT_ID.global._Default._AllLogs`
WHERE JSON_VALUE(json_payload.event) = 'gemini_usage'
GROUP BY visitor
ORDER BY cost_usd DESC;
```

Replace `PROJECT_ID` with your project ID. Group by `shop_id` the same way once there is more than one shop.

## Check against real spend

- **Billing → Reports**: actual charges per service (Vertex AI, Cloud Run, Firestore).
- **Monitoring → Metrics Explorer**: Vertex AI's own token-count and request metrics per model.
