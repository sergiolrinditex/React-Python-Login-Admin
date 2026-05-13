# Curl examples for P02-S05-T002 endpoints
# (Run after /verify-slice hard reset — requires real admin JWT + seeded model UUID)

## Authenticate as admin (get JWT)
```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/sign-in \
  -H "Content-Type: application/json" \
  -d '{"email":"admin.peopletech@inditex-sandbox.com","password":"AdminVerify2024!"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['data']['access_token'])")
echo "Token: ${TOKEN:0:30}..."
```

## Get model UUID from the catalog
```bash
MODEL_UUID=$(curl -s http://localhost:8000/api/v1/admin/ai/models \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['data'][0]['id'])" 2>/dev/null || echo "<insert-model-uuid>")
echo "Model UUID: $MODEL_UUID"
```

## POST /api/v1/admin/ai/models/{id}/test — happy path (real LLM call via litellm proxy)
```bash
curl -X POST "http://localhost:8000/api/v1/admin/ai/models/${MODEL_UUID}/test" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: $(python3 -c 'import uuid; print(uuid.uuid4())')" \
  -d '{"prompt":"Di hola en una palabra.","max_tokens":10}' \
  | python3 -m json.tool
# Expected: {"data":{"id":"<uuid>","model_id":"<uuid>","output":"Hola","latency_ms":<n>,...,"status":"success"},"meta":{"request_id":"<uuid>"}}
```

## POST /api/v1/admin/ai/models/{id}/test — model not found
```bash
curl -X POST "http://localhost:8000/api/v1/admin/ai/models/00000000-0000-0000-0000-000000000000/test" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Hello"}' \
  | python3 -m json.tool
# Expected: {"errors":[{"code":"AI_MODEL_NOT_FOUND","message":"Model not found."}],...}  HTTP 404
```

## GET /api/v1/admin/usage — group_by=model (last 30 days)
```bash
FROM_DT=$(python3 -c "from datetime import datetime, timezone, timedelta; print((datetime.now(timezone.utc)-timedelta(days=30)).isoformat())")
TO_DT=$(python3 -c "from datetime import datetime, timezone; print(datetime.now(timezone.utc).isoformat())")
curl -s "http://localhost:8000/api/v1/admin/usage?from=${FROM_DT}&to=${TO_DT}&group_by=model" \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -m json.tool
# Expected: {"data":{"from":"...","to":"...","group_by":"model","rows":[...],"totals":{...}},"meta":{...}}
```

## GET /api/v1/admin/usage — window too wide (422)
```bash
curl -s "http://localhost:8000/api/v1/admin/usage?from=2020-01-01T00:00:00Z&to=2026-12-31T00:00:00Z&group_by=day" \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -m json.tool
# Expected: {"errors":[{"code":"ADMIN_USAGE_WINDOW_TOO_WIDE",...}],...}  HTTP 422
```

## DB verification after POST /test
```bash
# Run in psql after a successful /test call:
# SELECT id, model_id, status, latency_ms, estimated_cost, created_at FROM ai_model_tests ORDER BY created_at DESC LIMIT 5;
# SELECT id, model_id, tokens_in, tokens_out, estimated_cost FROM llm_usage_logs ORDER BY created_at DESC LIMIT 5;
# SELECT id, action, actor_user_id, entity_type FROM audit_logs WHERE action='admin.ai.model.test' ORDER BY created_at DESC LIMIT 3;
```
