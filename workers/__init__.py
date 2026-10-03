"""Background scheduling for research jobs. Claims durable work and executes it."""

from workers.research_worker import ResearchWorker, WorkerOutcome

__all__ = ["ResearchWorker", "WorkerOutcome"]
