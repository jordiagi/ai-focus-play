from __future__ import annotations

import json
import logging
from datetime import datetime, UTC
from typing import Any


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")


def log_event(event: str, **payload: Any) -> None:
    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "event": event,
        **payload,
    }
    logging.getLogger("ai-focus-play").info(json.dumps(record))

