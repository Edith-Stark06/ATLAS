"""Structured (JSON) logging setup.

Before this, the API had no logging configuration at all — uvicorn's default
console formatter, and nothing else. That's fine on a laptop and useless
anywhere a deployment needs its logs aggregated, searched, or correlated
across a request: there was no request ID anywhere, and no machine-readable
shape to filter on.

No new dependency: a hand-rolled `JSONFormatter` is a few lines, and every
field it needs (`request_id`, `method`, `path`, `status_code`, `duration_ms`)
is either already on the `LogRecord` or supplied by `RequestContextMiddleware`
via `request_id_var` in `app/core/middleware.py`.
"""

import json
import logging
from logging.config import dictConfig

from app.core.middleware import request_id_var

#: Attributes already on every stdlib LogRecord — anything else in `extra=`
#: is request/log-specific and gets folded into the JSON output.
_STANDARD_RECORD_KEYS = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__)


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        request_id = request_id_var.get()
        if request_id is not None:
            payload["request_id"] = request_id

        for key, value in record.__dict__.items():
            if key not in _STANDARD_RECORD_KEYS:
                payload[key] = value

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


def configure_logging() -> None:
    """Route the root logger and uvicorn's own loggers through one JSON
    formatter, so console output is one consistent, parseable shape instead
    of uvicorn's default text plus whatever ad-hoc `print()`s existed before.

    Called once, before the FastAPI app is constructed (`app/main.py`) — the
    logging module is process-global, so configuring it any later risks
    uvicorn having already attached its own handlers first.
    """
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {"json": {"()": JSONFormatter}},
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "json",
                }
            },
            "root": {"handlers": ["console"], "level": "INFO"},
            "loggers": {
                # uvicorn's access log already duplicates what
                # RequestContextMiddleware logs (`atlas.access`), with less
                # detail and no request ID — propagate to root's JSON handler
                # but don't also let uvicorn's own default formatter fire.
                "uvicorn": {"handlers": ["console"], "level": "INFO", "propagate": False},
                "uvicorn.error": {"handlers": ["console"], "level": "INFO", "propagate": False},
                "uvicorn.access": {"handlers": [], "level": "INFO", "propagate": False},
            },
        }
    )
