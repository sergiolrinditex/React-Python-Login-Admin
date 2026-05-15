#!/usr/bin/env python3
"""Design-token scanner for web stacks (React/Next/Vite/TS/JS/CSS).

It catches common visual literals outside token/theme modules: hex colors,
rgb()/rgba()/hsl()/hsla() and Tailwind arbitrary color classes such as
`bg-[#ffffff]`. A justified per-line opt-out is allowed:

  // ignore: design-tokens(reason: "third-party embed")
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
    Pattern("tailwind_arbitrary_color", re.compile(r"\b(?:bg|text|border|from|to|via|ring|shadow|fill|stroke)-\[#(?:[0-9A-Fa-f]{3,8})\]"), "Tailwind arbitrary color class"),
    Pattern("hex_color", re.compile(r"(?<![A-Za-z0-9_])#[0-9A-Fa-f]{3,8}\b"), "literal hex color"),
    Pattern("rgb_color", re.compile(r"\brgba?\s*\([^)]*\)", re.I), "rgb()/rgba() literal"),
    Pattern("hsl_color", re.compile(r"\bhsla?\s*\([^)]*\)", re.I), "hsl()/hsla() literal"),
]

IGNORE_RE = re.compile(r'//\s*ignore\s*:\s*design-tokens\s*\(\s*reason\s*:\s*"[^"]+"\s*\)|/\*\s*ignore\s*:\s*design-tokens\s*\(\s*reason\s*:\s*"[^"]+"\s*\)\s*\*/')
EXTS = {".ts", ".tsx", ".js", ".jsx", ".css", ".scss", ".sass", ".html"}
DEFAULT_EXCLUDES = {"node_modules", "dist", "build", ".next", ".nuxt", "coverage", "generated", "tokens", "theme", "themes", "design-system"}


def _strip_block_comments(src: str) -> str:
    return re.sub(r"/\*.*?\*/", lambda m: " " * (m.end() - m.start()), src, flags=re.S)


def _is_excluded(path: Path, root: Path, theme_root: Path | None = None) -> bool:
    try:
        rel = path.resolve().relative_to(root.resolve())
    except Exception:
        rel = path
    parts = set(rel.parts)
    if parts & DEFAULT_EXCLUDES:
        return True
    if theme_root:
        try:
            path.resolve().relative_to(theme_root.resolve())
            return True
        except Exception:
            pass
    return False


def iter_files(root: Path, theme_root: Path | None = None):
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in EXTS:
            continue
        if _is_excluded(path, root, theme_root=theme_root):
            continue
        yield path


def scan_file(path: Path, root: Path) -> list[tuple[Path, int, str, str]]:
    try:
        raw = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raw = path.read_text(encoding="utf-8", errors="replace")
    body = _strip_block_comments(raw)
    out: list[tuple[Path, int, str, str]] = []
    for line_no, line in enumerate(body.splitlines(), start=1):
        if IGNORE_RE.search(line):
            continue
        # Remove plain line comments after preserving Tailwind class strings.
        scan_line = re.sub(r"//.*$", "", line)
        for pat in PATTERNS:
            if pat.regex.search(scan_line):
                out.append((path, line_no, pat.name, pat.human))
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Web design-token scanner.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--target", type=Path, default=None)
    parser.add_argument("--theme-root", type=Path, default=None)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    target = (args.target or root).resolve()
    theme_root = args.theme_root.resolve() if args.theme_root else None
    if not target.is_dir():
        if not args.quiet:
            print(f"i  {target} no existe todavia - skip.")
        return 0
    violations: list[tuple[Path, int, str, str]] = []
    for path in iter_files(target, theme_root=theme_root):
        violations.extend(scan_file(path, root))
    if violations:
        grouped: dict[str, list[tuple[Path, int, str]]] = {}
        for path, line, name, human in violations:
            grouped.setdefault(human, []).append((path, line, name))
        for human, items in grouped.items():
            print("X Design token violation: " + human)
            for path, line, _name in items:
                try:
                    rel = path.relative_to(root)
                except Exception:
                    rel = path
                print(f"  {rel}:{line}")
            print("")
        print(f"Found {len(violations)} web design-token violation(s). Move literals to the token/theme module declared in STACK_PROFILE.yaml.")
        print('Excepcion justificada: // ignore: design-tokens(reason: "<motivo>"). La razon es OBLIGATORIA.')
        return 1
    if not args.quiet:
        print("OK Design tokens - web literals are outside app code or inside token/theme modules.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
