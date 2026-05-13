/**
 * Hilo People — Safe redirect-after-auth URL validator.
 *
 * Slice/Phase: P01-S03-T001 — Auth state provider and protected route guards / Phase 1.
 *
 * Responsibility: Parse and sanitise the `?next=` query parameter
 *   to prevent open-redirect attacks. This is a pure function with unit tests (T13, T14).
 *
 * Security contract (task pack §P #8):
 *   The guard MUST be a named function with unit tests — not an inline regex.
 *
 * Open-redirect rules:
 *   ALLOWED:  starts with "/" AND does NOT start with "//" AND does NOT contain "://".
 *             Also reject backslash-prefixed or javascript: paths.
 *   REJECTED: anything that doesn't pass the above → falls back to DEFAULT_SAFE_REDIRECT.
 *
 * Default safe redirect: "/chat" (first protected employee route per §6.4 Navigation Contract).
 */

export const DEFAULT_SAFE_REDIRECT = "/chat";

/**
 * Validates and returns a safe same-origin redirect path from a `?next=` query param.
 *
 * Security rules (OWASP Open Redirect prevention):
 *   - Must start with "/" (relative path).
 *   - Must NOT start with "//" (protocol-relative URL → external).
 *   - Must NOT contain "://" (absolute URL).
 *   - Must NOT start with "\\" or contain "\\" (backslash tricks).
 *   - Must NOT start with "javascript:" or "data:" (script injection).
 *
 * @param rawNext - The raw value of the `?next=` query parameter (may be null/undefined).
 * @returns A safe relative path starting with "/", or DEFAULT_SAFE_REDIRECT on any violation.
 *
 * @example
 *   getSafeRedirect("/chat/abc?x=1")       // → "/chat/abc?x=1"  (safe)
 *   getSafeRedirect("https://evil.com")    // → "/chat"           (rejected)
 *   getSafeRedirect("//evil.com")          // → "/chat"           (rejected)
 *   getSafeRedirect("javascript:alert(1)") // → "/chat"           (rejected)
 *   getSafeRedirect(null)                  // → "/chat"           (no param)
 */
export function getSafeRedirect(rawNext: string | null | undefined): string {
  if (!rawNext || typeof rawNext !== "string") {
    return DEFAULT_SAFE_REDIRECT;
  }

  const trimmed = rawNext.trim();

  // Must start with "/" (relative path)
  if (!trimmed.startsWith("/")) {
    return DEFAULT_SAFE_REDIRECT;
  }

  // Must NOT start with "//" (protocol-relative URL → external host)
  if (trimmed.startsWith("//")) {
    return DEFAULT_SAFE_REDIRECT;
  }

  // Must NOT contain "://" (absolute URL smuggled after initial "/")
  if (trimmed.includes("://")) {
    return DEFAULT_SAFE_REDIRECT;
  }

  // Must NOT start with backslash (Windows path tricks, some UA canonicalize "\\" → "/")
  if (trimmed.startsWith("\\")) {
    return DEFAULT_SAFE_REDIRECT;
  }

  // Must NOT contain backslash anywhere (some browsers normalize "//evil.com\\@good.com")
  if (trimmed.includes("\\")) {
    return DEFAULT_SAFE_REDIRECT;
  }

  // Must NOT be a javascript: or data: pseudo-scheme
  const lower = trimmed.toLowerCase();
  if (lower.startsWith("javascript:") || lower.startsWith("data:")) {
    return DEFAULT_SAFE_REDIRECT;
  }

  return trimmed;
}
