#!/usr/bin/env bash
# 2FA verify step for J100 journey verification
# Reads challenge token from 01-sign-in.response.json
# Generates fresh TOTP code at runtime (never hardcoded)
set -euo pipefail
EVDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHALLENGE="$(python3 -c "import json; d=json.load(open('$EVDIR/01-sign-in.response.json')); print(d['data']['mfa_challenge_token'])")"
CODE="$(python3 -c "import pyotp; print(pyotp.TOTP('JBSWY3DPEHPK3PXP').now())")"
REQ_ID="$(python3 -c 'import uuid; print(str(uuid.uuid4()))')"
echo "Using X-Request-ID: $REQ_ID"
echo "Using TOTP code: $CODE (generated now)"
curl -i -sS \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: $REQ_ID" \
  -c "$EVDIR/cookies.txt" \
  -d "{\"challenge_id\":\"$CHALLENGE\",\"code\":\"$CODE\"}" \
  http://localhost:8000/api/v1/auth/2fa/verify
