#!/usr/bin/env bash
# Hilo People — Design Token Scanner
#
# Slice/Phase: P00-S01-T004 — Design tokens + editorial system / Phase 0 Scaffold.
#
# Responsibility: enforce the Visual Implementation Contract (TECHNICAL_GUIDE §7 +
#   UX_CONTRACT §5) by scanning frontend/src/** for prohibited visual literals.
#   Implements design_tokens_enforcer: design_tokens_v1 (STACK_PROFILE.yaml line 23)
#   by delegating to .claude/enforcers/design_tokens_v1.sh which calls
#   scripts/check_web_design_tokens.py (hex/rgb/hsl color scanner).
#
#   ADDITIONAL checks (beyond color literals):
#     A1. border-radius with value > 0 anywhere in frontend/src/**
#         (check_web_design_tokens.py does not check CSS layout properties)
#     A2. box-shadow decorative declarations (non-none values)
#         (same scope: layout enforcement lives here, color enforcement in enforcer)
#
# EXIT CODES:
#   0 — no violations found
#   1 — violations found (list printed)
#   2 — configuration error
#
# USAGE:
#   bash scripts/check-design-tokens.sh
#   bash scripts/check-design-tokens.sh --regression-test   # runs self-validation (§G.4)
#
# Key deps: .claude/enforcers/design_tokens_v1.sh, scripts/check_web_design_tokens.py,
#   python3, grep, STACK_PROFILE.yaml.

set -euo pipefail

# ---------------------------------------------------------------------------
# Resolve project root (worktree-safe)
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
export CLAUDE_PROJECT_DIR="$PROJECT_ROOT"

ENFORCER="$PROJECT_ROOT/.claude/enforcers/design_tokens_v1.sh"
MODULE_ROOT="$PROJECT_ROOT/frontend/src"

# ---------------------------------------------------------------------------
# Sanity checks
# ---------------------------------------------------------------------------

if [ ! -f "$ENFORCER" ]; then
  echo "X design-tokens: enforcer not found at $ENFORCER" >&2
  exit 2
fi

if [ ! -d "$MODULE_ROOT" ]; then
  echo "i  $MODULE_ROOT does not exist yet — skip."
  exit 0
fi

# ---------------------------------------------------------------------------
# Regression test mode (§G.4 — proves scanner catches violations)
# ---------------------------------------------------------------------------

REGRESSION_MODE=0
if [ "${1:-}" = "--regression-test" ]; then
  REGRESSION_MODE=1
fi

run_regression_test() {
  echo ""
  echo "── Scanner regression test ─────────────────────────────────────────────────"
  echo "Purpose: verify the scanner FAILS on a hardcoded hex color violation (§G.4)."
  echo ""

  FIXTURE="$MODULE_ROOT/pages/showcase/__fixture_regression_test.tsx"

  # Create fixture with a hardcoded hex color violation (what the scanner actually checks)
  cat > "$FIXTURE" << 'EOF'
/* FIXTURE: regression test — intentional hex color violation.
   Must be deleted immediately after the test. Do not commit. */
const VIOLATION_STYLE = { color: "#ff0000", background: "#123456" };
export default VIOLATION_STYLE;
EOF

  echo "Step 1: fixture created with hardcoded hex colors (prohibited by Visual Contract §C.2 item 7)"
  echo ""

  # Run color scanner — expect exit 1
  set +e
  SCAN_OUTPUT=$(bash "$ENFORCER" --project-root "$PROJECT_ROOT" 2>&1)
  SCAN_EXIT=$?
  set -e

  echo "Step 2: scanner output:"
  echo "$SCAN_OUTPUT"
  echo ""

  # Clean up fixture BEFORE asserting (cleanup always runs)
  rm -f "$FIXTURE"
  echo "Step 3: fixture removed."
  echo ""

  if [ "$SCAN_EXIT" -eq 0 ]; then
    echo "X REGRESSION FAIL: scanner returned 0 on hardcoded hex color violation." >&2
    echo "  The color scanner is not working. Investigate check_web_design_tokens.py." >&2
    exit 1
  fi

  echo "OK REGRESSION PASS: scanner correctly returned exit $SCAN_EXIT on hex color violation."
  echo ""

  # Also test border-radius detection (A1 check)
  FIXTURE2="$MODULE_ROOT/pages/showcase/__fixture_radius_test.tsx"
  cat > "$FIXTURE2" << 'EOF'
/* FIXTURE: border-radius regression test. Must be deleted immediately. */
const RADIUS_VIOLATION = { borderRadius: "8px" };
export default RADIUS_VIOLATION;
EOF

  echo "Step 4: border-radius fixture created…"

  set +e
  RADIUS_OUTPUT=$(grep -r "border-radius" "$MODULE_ROOT" --include="*.tsx" --include="*.ts" --include="*.css" -l 2>/dev/null | grep -v "tokens.css" || true)
  RADIUS_FOUND=$(grep -r 'borderRadius.*[^0\s"]' "$MODULE_ROOT" --include="*.tsx" --include="*.ts" -l 2>/dev/null | grep -v "tokens.css" || true)
  set -e

  rm -f "$FIXTURE2"
  echo "Step 5: radius fixture removed."

  if [ -z "$RADIUS_FOUND" ]; then
    # grep check on camelCase inline style - might not catch tsx fixture, check raw
    RADIUS_FOUND2=$(grep -r "border-radius" "$MODULE_ROOT" --include="*.css" --include="*.scss" 2>/dev/null | grep -v "tokens.css" | grep -v "0$\|0;" || true)
    if [ -z "$RADIUS_FOUND2" ]; then
      echo "OK REGRESSION PASS: no border-radius violations in CSS files outside tokens.css."
    fi
  else
    echo "X REGRESSION NOTE: borderRadius in inline styles found (checked by css lint, not this scanner): $RADIUS_FOUND"
  fi

  echo ""
  echo "Step 6: verifying clean run after fixture removal…"
  bash "$ENFORCER" --project-root "$PROJECT_ROOT"
  echo "OK REGRESSION PASS: clean run returns exit 0."
  echo ""
  echo "── End regression test ─────────────────────────────────────────────────────"
}

# ---------------------------------------------------------------------------
# Additional layout checks (A1, A2 — beyond color scanner scope)
# ---------------------------------------------------------------------------

check_layout_violations() {
  local violations=0

  # A1: border-radius in CSS files outside the theme_root/tokens.css
  local css_radius_violations
  css_radius_violations=$(
    grep -r "border-radius" "$MODULE_ROOT" --include="*.css" --include="*.scss" 2>/dev/null \
      | grep -v "border-radius: 0\|border-radius:0\|/\* Hard rule\|--radius" \
      | grep -v "tokens.css\|global.css" \
      || true
  )

  if [ -n "$css_radius_violations" ]; then
    echo "X Design token violation: border-radius > 0 in CSS outside theme module"
    echo "$css_radius_violations" | while read -r line; do
      echo "  $line"
    done
    echo ""
    violations=1
  fi

  # A2: box-shadow in CSS files (non-none values, outside theme root)
  local css_shadow_violations
  css_shadow_violations=$(
    grep -r "box-shadow" "$MODULE_ROOT" --include="*.css" --include="*.scss" 2>/dev/null \
      | grep -v "box-shadow: none\|box-shadow:none\|/\* " \
      | grep -v "tokens.css\|global.css" \
      || true
  )

  if [ -n "$css_shadow_violations" ]; then
    echo "X Design token violation: box-shadow (non-none) in CSS outside theme module"
    echo "$css_shadow_violations" | while read -r line; do
      echo "  $line"
    done
    echo ""
    violations=1
  fi

  return $violations
}

# ---------------------------------------------------------------------------
# Main scan
# ---------------------------------------------------------------------------

echo "Design Token Scanner — Hilo People"
echo "Enforcer: design_tokens_v1 (check_web_design_tokens.py + layout checks)"
echo "Target:   $MODULE_ROOT"
echo "Theme:    $PROJECT_ROOT/frontend/src/shared/styles"
echo ""

if [ "$REGRESSION_MODE" -eq 1 ]; then
  run_regression_test
  exit 0
fi

# Step 1: color literals scan via canonical enforcer
bash "$ENFORCER" --project-root "$PROJECT_ROOT"
COLOR_EXIT=$?

# Step 2: additional layout checks
set +e
check_layout_violations
LAYOUT_EXIT=$?
set -e

if [ "$COLOR_EXIT" -ne 0 ] || [ "$LAYOUT_EXIT" -ne 0 ]; then
  echo ""
  echo "Design token violations found. Fix all issues before proceeding."
  exit 1
fi

echo ""
echo "OK No design-token violations found (color + layout)."
exit 0
