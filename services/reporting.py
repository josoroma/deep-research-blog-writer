"""Build and classify the run report (US-8.1, US-8.2, PD-017, PD-018)."""

from pathlib import Path

from schemas.responses import RunReport, UrlOutcomeEntry
from schemas.state import RunState
from services.artifacts import write_json

REPORT_PATH = "output/run.json"
FAILURE_REASONS = ("no_results", "no_sources", "phase_failed", "dangling_citations")
DEGRADED_REASONS = ("too_few_sources", "blog_length")
EXIT_STATUS = {"succeeded": 0, "degraded": 3, "failed": 1}


class UsageRecord:
    """One model response. A missing reported cost is priced from its tokens."""

    def __init__(self, tokens: int, reported_cost: float | None) -> None:
        self.tokens = tokens
        self.reported_cost = reported_cost


class RunLedger:
    """What the run observed and the report cannot reconstruct from state alone."""

    def __init__(self, model: str, *, price_per_token: float = 0.0) -> None:
        self.model = model
        self.price_per_token = price_per_token
        self.phase_timings: dict[str, float] = {}
        self.usage: list[UsageRecord] = []
        self.retries = 0

    def cost(self) -> tuple[int, float]:
        tokens = sum(record.tokens for record in self.usage)
        total = 0.0
        for record in self.usage:
            if record.reported_cost is None:
                total += record.tokens * self.price_per_token
            else:
                total += record.reported_cost
        return tokens, total


def classify_outcome(
    run: RunState, *, max_urls: int, recorded_reasons: list[str]
) -> tuple[str, list[str]]:
    """PD-017. Failure wins, then degradation, otherwise success."""
    reasons = list(recorded_reasons)
    extracted = sum(1 for outcome in run.url_outcomes.values() if outcome.outcome == "extracted")
    if not run.clean_results and "no_results" not in reasons:
        reasons.append("no_results")
    elif run.clean_results and extracted == 0 and "no_sources" not in reasons:
        reasons.append("no_sources")
    elif extracted < 0.8 * max_urls and "too_few_sources" not in reasons:
        reasons.append("too_few_sources")
    failing = [reason for reason in reasons if reason in FAILURE_REASONS]
    if failing:
        return "failed", reasons
    if any(reason in DEGRADED_REASONS for reason in reasons):
        return "degraded", reasons
    return "succeeded", reasons


def build_run_report(
    run: RunState,
    ledger: RunLedger,
    *,
    workspace: Path,
    blog_path: str,
    citation_count: int,
    duration_seconds: float,
    status: str,
    status_reasons: list[str],
) -> RunReport:
    """Counts come from the corpus, so the report cannot drift from the files."""
    outcomes = run.url_outcomes.values()
    extracted = sum(1 for outcome in outcomes if outcome.outcome == "extracted")
    tokens, cost = ledger.cost()
    report = RunReport(
        run_id=run.run_id,
        topic=run.topic,
        model=ledger.model,
        status=status,  # type: ignore[arg-type]
        status_reasons=status_reasons,
        phase_timings_seconds=ledger.phase_timings,
        urls_found=len(run.clean_results),
        urls_clean=len(run.clean_results),
        urls_fetched=sum(1 for outcome in outcomes if outcome.outcome != "pending"),
        urls_extracted=extracted,
        urls_thin=sum(1 for outcome in outcomes if outcome.outcome == "too_thin"),
        urls_failed=sum(
            1 for outcome in outcomes if outcome.outcome in {"failed", "extraction_failed"}
        ),
        extraction_failures=sum(1 for outcome in outcomes if outcome.outcome != "extracted"),
        url_outcomes=[
            UrlOutcomeEntry(
                rank=outcome.rank,
                url=outcome.url,
                outcome=outcome.outcome,
                reason=outcome.reason,
                source_id=outcome.source_id,
            )
            for outcome in sorted(outcomes, key=lambda item: item.rank)
        ],
        blog_path=blog_path,
        citation_count=citation_count,
        tokens_used=tokens,
        cost_usd=cost,
        duration_seconds=duration_seconds,
        retries=ledger.retries,
    )
    del workspace
    return report


def write_run_report(workspace: Path, report: RunReport) -> Path:
    path = workspace / REPORT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, report.model_dump(mode="json"))
    RunReport.model_validate_json(path.read_text())
    return path
