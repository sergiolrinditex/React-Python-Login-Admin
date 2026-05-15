#!/usr/bin/env python3
"""Design-tokens guardian (Fix #6).

Context-aware linter that strips Dart comments and string literals before
searching for literal-style violations. Replaces the pure-grep scanner in
scripts/check-design-tokens.sh.

Why: the original grep pipeline produced (1) false positives in comments
and strings and (2) trivial bypasses by renaming identifiers. This
implementation is not a full Dart AST but removes the two biggest holes:

  1. Strip // and /* ... */ comments before scanning.
  2. Strip string literals (single, double, triple-quoted) so logged or
     documented patterns are ignored.
  3. Require an explicit per-line opt-out with reason:

        EdgeInsets.all(16)  // ignore: design-tokens(reason: "<why>")

     A bare directive without a reason is rejected so opt-outs stay
     traceable in code review and git blame.
  4. Canonical token sources (lib/core/theme/, lib/l10n/, generated/) are
     excluded.

This is deliberately a lightweight pre-AST guard. A true Dart custom_lint
AST rule can replace it later, but this version avoids the noisy grep failure
mode while staying dependency-free for macOS template bootstrap.

Exit codes: 0 = clean, 1 = violations found, 2 = invocation error.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Pattern:
    name: str
    regex: "re.Pattern[str]"
    human: str


PATTERNS = [
    Pattern("color_hex",
            re.compile(r"\bColor\(\s*0x[0-9A-Fa-f]"),
            "literal Color(0xFF...)"),
    Pattern("color_from_argb",
            re.compile(r"\bColor\.fromARGB\("),
            "Color.fromARGB(...)"),
    Pattern("color_from_rgbo",
            re.compile(r"\bColor\.fromRGBO\("),
            "Color.fromRGBO(...)"),
    Pattern("colors_material",
            re.compile(r"\bColors\.[a-zA-Z_][a-zA-Z0-9_]*"),
            "Material Colors.<name>"),
    Pattern("edge_insets_all",
            re.compile(r"\bEdgeInsets\.all\(\s*[1-9]"),
            "EdgeInsets.all(<num>)"),
    Pattern("edge_insets_only",
            re.compile(r"\bEdgeInsets\.only\([^)]*[1-9]"),
            "EdgeInsets.only(... <num> ...)"),
    Pattern("edge_insets_symmetric",
            re.compile(r"\bEdgeInsets\.symmetric\([^)]*[1-9]"),
            "EdgeInsets.symmetric(... <num> ...)"),
    Pattern("sized_box_height",
            re.compile(r"\bSizedBox\(\s*height\s*:\s*[1-9]"),
            "SizedBox(height: <num>)"),
    Pattern("sized_box_width",
            re.compile(r"\bSizedBox\(\s*width\s*:\s*[1-9]"),
            "SizedBox(width: <num>)"),
    Pattern("border_radius_circular",
            re.compile(r"\bBorderRadius\.circular\(\s*[1-9]"),
            "BorderRadius.circular(<num>)"),
    Pattern("box_shadow_blur",
            re.compile(r"\bBoxShadow\([^)]*blurRadius\s*:\s*[1-9]"),
            "BoxShadow(... blurRadius: <num> ...)"),
    Pattern("duration_ms",
            re.compile(r"\bDuration\(\s*milliseconds\s*:\s*[1-9]"),
            "Duration(milliseconds: <num>) en widget UI"),
    Pattern("text_style_font_size",
            re.compile(r"\bTextStyle\([^)]*fontSize\s*:\s*[1-9]"),
            "TextStyle(... fontSize: <num> ...)"),
    Pattern("font_weight_w",
            re.compile(r"\bFontWeight\.w[0-9]"),
            "FontWeight.w<num>"),
]


# Per-line opt-out: requires reason, otherwise rejected.
IGNORE_RE = re.compile(
    r'//\s*ignore\s*:\s*design-tokens\s*\(\s*reason\s*:\s*"[^"]+"\s*\)'
)


EXCLUDED_PARTS = {"l10n", "generated"}
THEME_ROOT_REL = "core/theme"


DQ = chr(0x22)            # "
SQ = chr(0x27)            # '
TRIPLE_DQ = DQ * 3
TRIPLE_SQ = SQ * 3


def _strip_comments_and_strings(src: str) -> str:
    """Replace comments and string literals with spaces (length-preserving)."""
    out = list(src)
    i = 0
    n = len(src)
    while i < n:
        ch = src[i]
        nxt = src[i + 1] if i + 1 < n else ""

        # Block comment
        if ch == "/" and nxt == "*":
            out[i] = " "
            out[i + 1] = " "
            j = i + 2
            while j < n - 1 and not (src[j] == "*" and src[j + 1] == "/"):
                if src[j] != "\n":
                    out[j] = " "
                j += 1
            if j < n - 1:
                out[j] = " "
                out[j + 1] = " "
                j += 2
            i = j
            continue

        # Line comment
        if ch == "/" and nxt == "/":
            j = i
            while j < n and src[j] != "\n":
                out[j] = " "
                j += 1
            i = j
            continue

        # Triple-quoted strings
        if (ch == DQ and src[i:i + 3] == TRIPLE_DQ) or (ch == SQ and src[i:i + 3] == TRIPLE_SQ):
            quote = src[i:i + 3]
            for k in range(3):
                out[i + k] = " "
            j = i + 3
            while j < n - 2 and src[j:j + 3] != quote:
                if src[j] != "\n":
                    out[j] = " "
                j += 1
            if j < n - 2:
                for k in range(3):
                    out[j + k] = " "
                j += 3
            i = j
            continue

        # Single-line single+double quoted strings
        if ch in (SQ, DQ):
            quote = ch
            j = i + 1
            out[i] = " "
            while j < n and src[j] != quote:
                if src[j] == chr(0x5c) and j + 1 < n and src[j + 1] != "\n":
                    out[j] = " "
                    out[j + 1] = " "
                    j += 2
                    continue
                if src[j] == "\n":
                    break
                out[j] = " "
                j += 1
            if j < n and src[j] == quote:
                out[j] = " "
                j += 1
            i = j
            continue

        i += 1

    return "".join(out)


def _is_excluded(rel: Path, theme_rel: str = THEME_ROOT_REL) -> bool:
    parts = rel.as_posix()
    markers = set(EXCLUDED_PARTS)
    if theme_rel:
        markers.add(theme_rel.strip("/"))
    for marker in markers:
        if not marker:
            continue
        if "/" + marker + "/" in "/" + parts or parts.startswith(marker + "/"):
            return True
    return False


def scan_file(path: Path, rel: Path):
    try:
        body = path.read_text(encoding="utf-8")
    except Exception:
        return []
    stripped = _strip_comments_and_strings(body)
    raw_lines = body.splitlines()
    stripped_lines = stripped.splitlines()

    out = []
    for idx, (raw_line, stripped_line) in enumerate(zip(raw_lines, stripped_lines), start=1):
        if IGNORE_RE.search(raw_line):
            continue
        for pat in PATTERNS:
            if pat.regex.search(stripped_line):
                out.append((path, idx, pat.name, pat.human))
    return out


def find_dart_files(app_lib: Path, theme_root: Path | None = None):
    out = []
    theme_rel = THEME_ROOT_REL
    if theme_root:
        try:
            theme_rel = theme_root.resolve().relative_to(app_lib.resolve()).as_posix()
        except Exception:
            theme_rel = THEME_ROOT_REL
    for path in sorted(app_lib.rglob("*.dart")):
        rel = path.relative_to(app_lib)
        if _is_excluded(rel, theme_rel=theme_rel):
            continue
        out.append((path, rel))
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Design-tokens guardian (Dart literal-token scanner).",
    )
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--app-lib", type=Path, default=None)
    parser.add_argument("--theme-root", type=Path, default=None)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    root = (args.root or Path.cwd()).resolve()
    app_lib = (args.app_lib or (root / "app" / "lib")).resolve()
    theme_root = (args.theme_root or (root / "app" / "lib" / "core" / "theme")).resolve()

    if not app_lib.is_dir():
        if not args.quiet:
            print("i  " + str(app_lib) + " no existe todavia - skip (Phase 0 aun no scaffoldeada).")
        return 0

    files = find_dart_files(app_lib, theme_root=theme_root)
    all_violations = []
    for path, _rel in files:
        all_violations.extend(scan_file(path, _rel))

    if all_violations:
        by_pattern = {}
        for path, line_no, name, human in all_violations:
            by_pattern.setdefault(human, []).append((path, line_no, name))
        for human, items in by_pattern.items():
            print("X Design token violation: " + human)
            for path, line_no, _name in items:
                try:
                    rel = path.relative_to(root)
                except ValueError:
                    rel = path
                print("  " + str(rel) + ":" + str(line_no))
            print("")
        try:
            theme_label = str(theme_root.relative_to(root))
        except ValueError:
            theme_label = str(theme_root)
        print("Found " + str(len(all_violations)) + " design-token violation(s) outside " + theme_label + ".")
        print("Mueve los literales al token/theme module declarado en STACK_PROFILE.yaml y consume via context.colors / context.spacing /")
        print("context.textStyles / context.radius / context.shadows / context.motion.")
        print('Excepcion justificada: // ignore: design-tokens(reason: "<motivo>"). La razon es OBLIGATORIA.')
        return 1

    if not args.quiet:
        print("OK Design tokens - cero literales fuera del token/theme module configurado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
