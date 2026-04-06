import time
import structlog
from app.utils.logger import get_logger

log = get_logger(__name__)


class RequestTrace:
    """Trace le timing de chaque étape d'une requête."""

    def __init__(self, trace_id: str, question: str):
        self.trace_id  = trace_id
        self.question  = question
        self.start     = time.time()
        self.steps: list[dict] = []

    def step(self, name: str, **kwargs):
        elapsed = round((time.time() - self.start) * 1000)
        self.steps.append({"step": name, "ms": elapsed, **kwargs})
        log.info(name, trace_id=self.trace_id, elapsed_ms=elapsed, **kwargs)

    def finish(self, **kwargs):
        total = round((time.time() - self.start) * 1000)
        log.info(
            "request_complete",
            trace_id=self.trace_id,
            total_ms=total,
            steps=len(self.steps),
            **kwargs,
        )
        return total