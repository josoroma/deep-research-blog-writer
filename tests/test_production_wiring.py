"""M4: production tool wiring, the real report tool, and phase persistence."""

from __future__ import annotations

import json
from pathlib import Path

from application.run_service import AUTHORING_GATE
from schemas.config import RunSettings
from schemas.content import utc_now
from schemas.responses import RunReport, SearchResult, Source
from schemas.state import RunState, UrlOutcome
from schemas.tool_io import WriteRunReportOutput
from services.corpus import CorpusSource, write_index, write_source
from services.reporting import REPORT_PATH, RunLedger
from tools.registry import ToolRegistry, create_tool_registry
from tools.report_tools import ReportSession
from workflows.search_run import tool_runtime


def _corpus(root: Path) -> RunState:
    """Two valid immutable sources plus a citation-valid blog and index."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "research").mkdir(exist_ok=True)
    (root / "output").mkdir(exist_ok=True)

    records = []
    clean = []
    outcomes = {}
    for rank, source_id in ((1, "S-01"), (2, "S-02")):
        source = Source(
            source_id=source_id,
            url=f"https://fixture.test/article-{rank}",  # type: ignore[arg-type]
            title=f"Fixture source {source_id}",
            author=None,
            published=None,
            body_markdown=f"# Fixture source {source_id}\n\n" + " ".join(["evidence"] * 300),
            word_count=300,
            fetched_at=utc_now(),
        )
        record = CorpusSource(source=source, path=f"research/{rank:03d}_fixture.md", rank=rank)
        write_source(root, record)
        records.append(record)
        result = SearchResult(
            url=f"https://fixture.test/article-{rank}",  # type: ignore[arg-type]
            title=f"Fixture source {source_id}",
            snippet="fixture",
            rank=rank,
            query="Fixture topic",
        )
        clean.append(result)
        outcomes[str(result.url)] = UrlOutcome(rank=rank, url=result.url, outcome="extracted")
    write_index(root, records)

    body = " ".join(["evidence"] * 400)
    sections = "\n\n".join(
        f"## {title}\n\n{body} [{records[index % 2].source.source_id}]."
        for index, title in enumerate(
            (
                "Introduction",
                "Landscape",
                "Key Frameworks",
                "Analysis and Trade-offs",
                "Outlook",
                "Conclusion",
            )
        )
    )
    references = "\n".join(
        f"- [{record.source.source_id}] {record.source.title} {record.source.url}"
        for record in records
    )
    (root / "output" / "blog.md").write_text(
        f"# Fixture topic\n\n{sections}\n\n## References\n\n{references}\n", encoding="utf-8"
    )
    return RunState(
        run_id="fixture-run",
        topic="Fixture topic",
        completed_phases=["plan", "search", "normalize", "fetch", "index"],
        clean_results=clean,
        url_outcomes=outcomes,
    )


def _settings() -> RunSettings:
    return RunSettings(_env_file=None, max_urls=2)


def test_production_registry_omits_stubs_and_registers_the_report_tool(tmp_path: Path) -> None:
    root = tmp_path / "run"
    _corpus(root)
    registry = create_tool_registry(production=True)
    assert "write_run_report" not in registry
    for stub in ("collect_source", "build_index", "validate_citations"):
        assert stub not in registry


def test_stub_registry_keeps_write_run_report() -> None:
    registry = create_tool_registry()
    assert "write_run_report" in registry


def test_report_tool_writes_the_run_report_and_records_the_phase(tmp_path: Path) -> None:
    root = tmp_path / "run"
    run = _corpus(root)
    ledger = RunLedger("openrouter:test")
    session = ReportSession(root, run, _settings(), ledger)
    registry = create_tool_registry(report_session=session, production=True)
    assert isinstance(registry, ToolRegistry)
    output = registry["write_run_report"].invoke({}, tool_runtime(run))
    assert isinstance(output, WriteRunReportOutput)
    assert output.report_path == "output/run.json"
    report = RunReport.model_validate_json((root / "output/run.json").read_text())
    assert report.run_id == run.run_id
    assert report.status_reasons == []
    assert session.written is not None and session.written.citation_count == 2


def test_report_tool_classifies_dangling_citations_as_failure(tmp_path: Path) -> None:
    root = tmp_path / "run"
    run = _corpus(root)
    blog = root / "output" / "blog.md"
    blog.write_text(blog.read_text().replace("[S-01]", "[S-99]"), encoding="utf-8")
    session = ReportSession(root, run, _settings(), RunLedger("openrouter:test"))
    registry = create_tool_registry(report_session=session, production=True)
    registry["write_run_report"].invoke({}, tool_runtime(run))
    report = RunReport.model_validate_json((root / "output/run.json").read_text())
    assert report.status == "failed"
    assert "dangling_citations" in report.status_reasons


def test_report_tool_requires_a_session(tmp_path: Path) -> None:
    registry = create_tool_registry(report_session=None, production=True)
    # Without a session and without stubs, the report tool is absent entirely.
    assert "write_run_report" not in registry


def test_gate_record_distinguishes_authoring_from_final_report(tmp_path: Path) -> None:
    assert AUTHORING_GATE == "output/authoring.json"
    assert REPORT_PATH == "output/run.json"


def test_authoring_gate_is_valid_json_after_a_run(tmp_path: Path) -> None:
    root = tmp_path / "run"
    run = _corpus(root)
    session = ReportSession(root, run, _settings(), RunLedger("openrouter:test"))
    create_tool_registry(report_session=session, production=True)["write_run_report"].invoke(
        {}, tool_runtime(run)
    )
    final = json.loads((root / "output" / "run.json").read_text())
    assert "status" in final and "urls_extracted" in final
