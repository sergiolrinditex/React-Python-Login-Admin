#!/usr/bin/env bash
# GET /users/me step for J100 journey verification
# Reads access_token from 03-2fa-verify.response.json
set -euo pipefail
EVDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOKEN="$(python3 -c "import json; d=json.load(open('$EVDIR/03-2fa-verify.response.json')); print(d['data']['access_token'])")"
REQ_ID="$(python3 -c 'import uuid; print(str(uuid.uuid4()))')"
echo "Using X-Request-ID: $REQ_ID"
curl -i -sS \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Request-ID: $REQ_ID" \
  http://localhost:8000/api/v1/users/me
