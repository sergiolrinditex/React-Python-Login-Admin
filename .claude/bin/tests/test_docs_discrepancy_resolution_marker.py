from __future__ import annotations


def test_docs_discrepancy_resolution_accepts_colon_and_missing_dependency_column_date(tmp_project):
    import common

    notes = tmp_project / "orchestrator-state" / "memory" / "official-doc-notes"
    notes.mkdir(parents=True)
    (notes / "colon.md").write_text("Issue\n\nRESOLVED: source-of-truth updated.\n", encoding="utf-8")
    (notes / "date.md").write_text("Issue\n\nRESOLVED 2026-05-11 source-of-truth updated.\n", encoding="utf-8")

    has_unresolved, unresolved = common.has_unresolved_doc_discrepancies()
    assert not has_unresolved
    assert unresolved == []


def test_docs_discrepancy_resolution_does_not_match_prose(tmp_project):
    import common

    notes = tmp_project / "orchestrator-state" / "memory" / "official-doc-notes"
    notes.mkdir(parents=True)
    (notes / "open.md").write_text("This is not resolved yet.\n", encoding="utf-8")

    has_unresolved, unresolved = common.has_unresolved_doc_discrepancies()
    assert has_unresolved
    assert unresolved == ["orchestrator-state/memory/official-doc-notes/open.md"]
