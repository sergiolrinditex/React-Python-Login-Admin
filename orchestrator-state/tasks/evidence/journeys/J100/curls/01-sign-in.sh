#!/usr/bin/env bash
# Sign-in step for J100 journey verification
# Password replaced with <REDACTED> in this script — see 01-sign-in.response.json for actual response
set -euo pipefail
REQ_ID="$(python3 -c 'import uuid; print(str(uuid.uuid4()))')"
echo "Using X-Request-ID: $REQ_ID"
curl -i -sS \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: $REQ_ID" \
  -c orchestrator-state/tasks/evidence/journeys/J100/curls/cookies.txt \
  -d '{"email":"employee.verification@inditex-sandbox.com","password":"<REDACTED>"}' \
  http://localhost:8000/api/v1/auth/sign-in
