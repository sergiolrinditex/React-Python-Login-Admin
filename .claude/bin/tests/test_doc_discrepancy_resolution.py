from __future__ import annotations


def test_doc_discrepancy_resolved_marker_accepts_canonical_and_missing_dependency_column_date(tmp_project):
    import common

    notes = tmp_project / "orchestrator-state" / "memory" / "official-doc-notes"
    notes.mkdir(parents=True, exist_ok=True)
    (notes / "canonical.md").write_text("Issue\n\nRESOLVED: patched implementation.\n", encoding="utf-8")
    (notes / "missing_dependency_column-date.md").write_text("Issue\n\nRESOLVED 2026-05-11 patched implementation.\n", encoding="utf-8")

    has_unresolved, unresolved = common.has_unresolved_doc_discrepancies()
    assert has_unresolved is False
    assert unresolved == []


def test_doc_discrepancy_unresolved_marker_is_still_reported(tmp_project):
    import common

    notes = tmp_project / "orchestrator-state" / "memory" / "official-doc-notes"
    notes.mkdir(parents=True, exist_ok=True)
    (notes / "open.md").write_text("Issue\n\nNot resolved yet.\n", encoding="utf-8")

    has_unresolved, unresolved = common.has_unresolved_doc_discrepancies()
    assert has_unresolved is True
    assert unresolved == ["orchestrator-state/memory/official-doc-notes/open.md"]


def test_doc_discrepancy_resolved_marker_accepts_markdown_prefixes(tmp_project):
    import common

    notes = tmp_project / "orchestrator-state" / "memory" / "official-doc-notes"
    notes.mkdir(parents=True, exist_ok=True)
    (notes / "bullet.md").write_text("Issue\n\n- RESOLVED: reconciled in code.\n", encoding="utf-8")
    (notes / "heading.md").write_text("Issue\n\n### RESOLVED 2026-05-14 reconciled in docs.\n", encoding="utf-8")
    (notes / "quote.md").write_text("Issue\n\n> RESOLVED - reconciled by baseline update.\n", encoding="utf-8")

    has_unresolved, unresolved = common.has_unresolved_doc_discrepancies()
    assert has_unresolved is False
    assert unresolved == []
