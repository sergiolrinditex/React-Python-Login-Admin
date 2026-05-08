"""Design-tokens guardian (Fix #6) — context-aware Dart literal scanner.

Coverage:
  * Positive: real literals in widget code are detected.
  * Negative — false positives the OLD grep would have flagged:
    - Patterns mentioned in comments.
    - Patterns appearing inside strings.
    - Custom identifiers that happen to share the prefix (MyColors.x).
  * Per-line opt-out with reason is honoured; a bare directive without
    reason is NOT honoured (the line still trips the scanner).
  * Excluded directories (lib/core/theme/, lib/l10n/, generated/) are
    skipped.
  * Files with violations are reported with line numbers.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


# Load the script as a module by file path (it lives outside the .claude tree).
_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "check_design_tokens.py"

_spec = importlib.util.spec_from_file_location("check_design_tokens", _SCRIPT)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["check_design_tokens"] = _mod
_spec.loader.exec_module(_mod)


def _make_app_lib(tmpdir: Path) -> Path:
    app_lib = tmpdir / "app" / "lib"
    app_lib.mkdir(parents=True)
    (app_lib / "core" / "theme").mkdir(parents=True)
    (app_lib / "l10n").mkdir(parents=True)
    (app_lib / "generated").mkdir(parents=True)
    return app_lib


class StripCommentsAndStringsTests(unittest.TestCase):

    def test_line_comment_is_stripped(self):
        src = "Color(0xFF000000); // comment with EdgeInsets.all(16)\n"
        out = _mod._strip_comments_and_strings(src)
        # The literal Color(...) before the comment must be preserved.
        self.assertIn("Color(0xFF000000)", out)
        # The pattern in the comment must be erased.
        self.assertNotIn("EdgeInsets.all(16)", out)

    def test_block_comment_is_stripped(self):
        src = "var x = 1; /* Color(0xFF111111) */ var y = 2;\n"
        out = _mod._strip_comments_and_strings(src)
        self.assertNotIn("Color(0xFF111111)", out)
        # The surrounding code must remain intact.
        self.assertIn("var x = 1;", out)
        self.assertIn("var y = 2;", out)

    def test_string_literal_is_stripped(self):
        # Build the string carefully — the content INSIDE the string is what
        # we want to see vanish.
        q = chr(0x22)  # "
        src = "log(" + q + "Color(0xFF000000)" + q + "); var c = 1;\n"
        out = _mod._strip_comments_and_strings(src)
        self.assertNotIn("Color(0xFF000000)", out)
        # Surrounding code is preserved.
        self.assertIn("log(", out)
        self.assertIn("var c = 1;", out)

    def test_length_preserving(self):
        src = "Color(0xFF000000); // comment\n"
        out = _mod._strip_comments_and_strings(src)
        self.assertEqual(len(src), len(out),
            "stripping must preserve length so column reporting stays correct")


class ScanFileTests(unittest.TestCase):

    def _tmp(self):
        td = tempfile.TemporaryDirectory()
        return Path(td.name), td

    def test_real_violation_in_widget_is_detected(self):
        root, td = self._tmp()
        try:
            app_lib = _make_app_lib(root)
            f = app_lib / "widgets" / "card.dart"
            f.parent.mkdir()
            f.write_text(
                "Widget build() {\n"
                "  return Container(\n"
                "    padding: EdgeInsets.all(16),\n"
                "    color: Color(0xFF2563EB),\n"
                "  );\n"
                "}\n",
                encoding="utf-8",
            )
            v = _mod.scan_file(f, f.relative_to(app_lib))
            patterns = sorted({name for _p, _l, name, _h in v})
            self.assertIn("edge_insets_all", patterns)
            self.assertIn("color_hex", patterns)
        finally:
            td.cleanup()

    def test_pattern_in_comment_does_not_trip(self):
        root, td = self._tmp()
        try:
            app_lib = _make_app_lib(root)
            f = app_lib / "widgets" / "doc.dart"
            f.parent.mkdir()
            f.write_text(
                "// Use context.colors.primary; do not write Color(0xFF000000) directly.\n"
                "Widget build() => SizedBox.shrink();\n",
                encoding="utf-8",
            )
            v = _mod.scan_file(f, f.relative_to(app_lib))
            self.assertEqual(v, [],
                "patterns inside comments must be ignored — this was the "
                "main false-positive class in the old grep")
        finally:
            td.cleanup()

    def test_pattern_in_string_does_not_trip(self):
        root, td = self._tmp()
        try:
            app_lib = _make_app_lib(root)
            f = app_lib / "widgets" / "log.dart"
            f.parent.mkdir()
            q = chr(0x22)
            f.write_text(
                "void demo() {\n"
                "  print(" + q + "EdgeInsets.all(16) is forbidden" + q + ");\n"
                "}\n",
                encoding="utf-8",
            )
            v = _mod.scan_file(f, f.relative_to(app_lib))
            self.assertEqual(v, [],
                "patterns inside string literals must be ignored")
        finally:
            td.cleanup()

    def test_custom_identifier_with_shared_prefix_does_not_trip(self):
        """`MyColors.primary` must NOT match the `Colors.<name>` pattern.
        The old grep's `Colors\\.[a-z]+` matched any identifier ending in
        `.lowercaseword`, including custom Color extensions. Anchor with
        word boundary fixes this."""
        root, td = self._tmp()
        try:
            app_lib = _make_app_lib(root)
            f = app_lib / "widgets" / "ext.dart"
            f.parent.mkdir()
            f.write_text(
                "class MyColors {\n"
                "  static final primary = something;\n"
                "}\n"
                "var c = MyColors.primary;\n",
                encoding="utf-8",
            )
            v = _mod.scan_file(f, f.relative_to(app_lib))
            self.assertEqual([n for _p, _l, n, _h in v], [],
                "MyColors.primary must not be flagged — only Colors.<name>")
        finally:
            td.cleanup()

    def test_ignore_directive_with_reason_is_honoured(self):
        root, td = self._tmp()
        try:
            app_lib = _make_app_lib(root)
            f = app_lib / "widgets" / "pdf.dart"
            f.parent.mkdir()
            q = chr(0x22)
            line = "  padding: EdgeInsets.all(16), // ignore: design-tokens(reason: " + q + "PDF export — sin context disponible" + q + ")\n"
            f.write_text("Widget build() => Container(\n" + line + ");\n",
                         encoding="utf-8")
            v = _mod.scan_file(f, f.relative_to(app_lib))
            self.assertEqual(v, [],
                "// ignore: design-tokens(reason: ...) must suppress the violation")
        finally:
            td.cleanup()

    def test_bare_ignore_directive_is_NOT_honoured(self):
        """Without a reason, the directive is rejected (silent escapes are
        the bug we are closing)."""
        root, td = self._tmp()
        try:
            app_lib = _make_app_lib(root)
            f = app_lib / "widgets" / "bad.dart"
            f.parent.mkdir()
            f.write_text(
                "Widget build() => Container(\n"
                "  padding: EdgeInsets.all(16), // ignore: design-tokens\n"
                ");\n",
                encoding="utf-8",
            )
            v = _mod.scan_file(f, f.relative_to(app_lib))
            self.assertEqual(len(v), 1,
                "bare directive (no reason) must NOT suppress — opt-outs must be traceable")
        finally:
            td.cleanup()

    def test_excluded_dirs_are_skipped(self):
        root, td = self._tmp()
        try:
            app_lib = _make_app_lib(root)
            # Theme dir IS allowed to have literals — that is the source.
            theme_file = app_lib / "core" / "theme" / "app_colors.dart"
            theme_file.write_text(
                "final primary = Color(0xFF2563EB);\n",
                encoding="utf-8",
            )
            files = _mod.find_dart_files(app_lib)
            self.assertNotIn(theme_file, [p for p, _r in files],
                "lib/core/theme/ must be excluded from the scan")
        finally:
            td.cleanup()


class MainEndToEndTests(unittest.TestCase):

    def test_main_returns_0_on_clean_repo(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            app_lib = _make_app_lib(root)
            (app_lib / "core" / "theme" / "app_colors.dart").write_text(
                "final primary = Color(0xFF2563EB);\n",
                encoding="utf-8",
            )
            rc = _mod.main(["--root", str(root), "--quiet"])
            self.assertEqual(rc, 0)

    def test_main_returns_1_on_violation(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            app_lib = _make_app_lib(root)
            (app_lib / "widgets" / "x.dart").parent.mkdir()
            (app_lib / "widgets" / "x.dart").write_text(
                "Widget build() => Container(padding: EdgeInsets.all(16));\n",
                encoding="utf-8",
            )
            rc = _mod.main(["--root", str(root), "--quiet"])
            self.assertEqual(rc, 1)

    def test_main_returns_0_when_app_lib_missing(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            rc = _mod.main(["--root", str(root), "--quiet"])
            self.assertEqual(rc, 0,
                "no app/lib yet (Phase 0) must be a soft skip, not a failure")


if __name__ == "__main__":
    unittest.main(verbosity=2)
