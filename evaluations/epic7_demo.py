"""Offline EPIC-7 demo: summary, cited draft, citation gate, and repair.

No model and no network. A scripted agent writes the summary, the real citation
check runs, and the repair loop is driven against a draft that dangles once.
"""

import json
from pathlib import Path
from typing import Any

from evaluations.epic6_demo import run_demo as run_corpus_demo
from services.authoring import REQUIRED_HEADINGS, check_blog, check_summary, validate_citations
from workflows.authoring_run import load_corpus_run


def run_demo(runs_root: Path) -> dict[str, Any]:
    corpus = run_corpus_demo(runs_root)
    workspace = Path(corpus["workspace"])
    state = load_corpus_run(workspace)
    source_ids = sorted(
        outcome["source_id"]
        for outcome in json.loads((workspace / "corpus_state.json").read_text())[
            "url_outcomes"
        ].values()
        if outcome["source_id"]
    )
    cited = source_ids[0]
    summary = "\n\n".join(
        [
            "## Recurring themes",
            f"### Theme: Evidence\n\nThe corpus agrees [{cited}].",
            "## Named frameworks",
            f"Named in the sources [{cited}].",
            "## Points of agreement",
            f"Consistent across sources [{cited}].",
            "## Points of disagreement",
            f"Sources differ on scope [{cited}].",
            "## Gaps",
            "Cost is not covered.",
            "## Suggested outline",
            "Introduction, then analysis.",
        ]
    )
    (workspace / "research/summary.md").write_text(summary, encoding="utf-8")
    assert check_summary(workspace).passed
    body = " ".join(["word"] * 400)
    sections = "\n\n".join(f"## {title}\n\n{body} [{cited}]." for title in REQUIRED_HEADINGS[:-1])
    record = next(
        line
        for line in (workspace / "research/index.md").read_text(encoding="utf-8").splitlines()
        if line.startswith(f"| {cited} ")
    )
    _, _, title, _, _, url, _ = (record.split("|") + [""] * 7)[:7]
    references = f"## References\n\n- [{cited}] {title.strip()} — {url.strip()}\n"
    blog = f"# Cited draft\n\n{sections}\n\n{references}"
    (workspace / "output").mkdir(exist_ok=True)
    (workspace / "output/blog.md").write_text(blog, encoding="utf-8")
    assert check_blog(workspace).headings_valid
    assert validate_citations(workspace).passed
    dangling = blog.replace(f"[{cited}]", "[S-31]", 1)
    (workspace / "output/blog.md").write_text(dangling, encoding="utf-8")
    assert validate_citations(workspace).dangling_source_ids == ["S-31"]
    (workspace / "output/blog.md").write_text(blog, encoding="utf-8")
    report = {
        "mode": "offline; scripted writer, real citation gate",
        "workspace": str(workspace),
        "summary_passed": True,
        "headings_valid": True,
        "citations_resolved": True,
        "dangling_detected": ["S-31"],
        "source_ids": source_ids,
        "run_id": state.run_id,
    }
    (workspace / "demo_evidence.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    print(json.dumps(run_demo(Path("runs")), indent=2))
