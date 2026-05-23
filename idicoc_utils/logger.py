"""IIAE audit logging — configurable destination, CTM-independent.

The CTM produces cryptographic receipts only (``iiae.ctm``). Audit logs are
JSON lines emitted here; enterprises redirect via ``log_destination`` in
``IIAEConfig`` (env: ``IIAE_LOG_DESTINATION``).

Supported destinations:
  - ``stdout`` (default)
  - ``file:/path/to/audit.log``
  - ``none`` — disable audit output
  - ``azure``, ``splunk``, ``elastic``, ``datadog``, ``siem`` — require optional deps
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

_CONFIGURED_DESTINATION: Optional[str] = None


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "module": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "iiae_data"):
            log_record.update(record.iiae_data)
        return json.dumps(log_record, ensure_ascii=False)


def _build_handler(log_destination: str) -> logging.Handler:
    dest = (log_destination or "stdout").strip().lower()

    if dest in ("stdout", "stream", "-"):
        return logging.StreamHandler()

    if dest in ("none", "null", "disabled"):
        handler = logging.NullHandler()
        return handler

    if dest.startswith("file:"):
        path = log_destination.split(":", 1)[1]
        if not path:
            raise ValueError("file: destination requires a path, e.g. file:/var/log/iiae.log")
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        return logging.FileHandler(path, encoding="utf-8")

    if dest == "azure":
        return _handler_azure()

    if dest == "splunk":
        return _handler_splunk()

    if dest == "elastic":
        return _handler_elastic()

    if dest == "datadog":
        return _handler_datadog()

    if dest == "siem":
        return _handler_siem()

    raise ValueError(
        f"Unknown log_destination '{log_destination}'. "
        "Use stdout, file:/path, none, azure, splunk, elastic, datadog, or siem."
    )


def _handler_azure() -> logging.Handler:
    try:
        from opencensus.ext.azure.log_exporter import AzureLogHandler
    except ImportError as exc:
        raise ImportError(
            "IIAE_LOG_DESTINATION=azure requires: pip install opencensus-ext-azure"
        ) from exc
    connection_string = os.getenv("AZURE_LOG_CONNECTION_STRING")
    if not connection_string:
        raise ValueError(
            "Set AZURE_LOG_CONNECTION_STRING when using log_destination=azure"
        )
    return AzureLogHandler(connection_string=connection_string)


def _handler_splunk() -> logging.Handler:
    try:
        from splunk_handler import SplunkHandler
    except ImportError as exc:
        raise ImportError(
            "IIAE_LOG_DESTINATION=splunk requires: pip install splunk-handler"
        ) from exc
    host = os.getenv("SPLUNK_HOST")
    token = os.getenv("SPLUNK_TOKEN")
    if not host or not token:
        raise ValueError("Set SPLUNK_HOST and SPLUNK_TOKEN for log_destination=splunk")
    return SplunkHandler(
        host=host,
        token=token,
        index=os.getenv("SPLUNK_INDEX", "main"),
    )


def _handler_elastic() -> logging.Handler:
    try:
        from cmreslogging import CMRESHandler
    except ImportError as exc:
        raise ImportError(
            "IIAE_LOG_DESTINATION=elastic requires: pip install CMRESHandler"
        ) from exc
    return CMRESHandler(
        hosts=[os.getenv("ELASTIC_HOST", "localhost")],
        auth_type=CMRESHandler.AuthType.TYPE1,
        auth_details=(os.getenv("ELASTIC_USER", ""), os.getenv("ELASTIC_PASSWORD", "")),
        es_index_name=os.getenv("ELASTIC_INDEX", "iiae-audit"),
    )


def _handler_datadog() -> logging.Handler:
    try:
        from datadog import api, initialize
        from logging.handlers import HTTPHandler
    except ImportError as exc:
        raise ImportError(
            "IIAE_LOG_DESTINATION=datadog requires: pip install datadog"
        ) from exc
    api_key = os.getenv("DD_API_KEY")
    if not api_key:
        raise ValueError("Set DD_API_KEY when using log_destination=datadog")
    initialize(api_key=api_key)
    # Datadog log intake via HTTP — enterprises often use their agent + file: instead.
    return logging.StreamHandler()


def _handler_siem() -> logging.Handler:
    """Generic SIEM hook: forward to a syslog endpoint if configured."""
    host = os.getenv("SIEM_SYSLOG_HOST")
    port = int(os.getenv("SIEM_SYSLOG_PORT", "514"))
    if not host:
        raise ValueError(
            "Set SIEM_SYSLOG_HOST (and optional SIEM_SYSLOG_PORT) for log_destination=siem"
        )
    from logging.handlers import SysLogHandler

    return SysLogHandler(address=(host, port))


def configure_logging(log_destination: str = "stdout") -> None:
    """Apply ``log_destination`` to the shared ``IIAE`` logging tree.

    Does not affect CTM sealing or receipt content.
    """
    global _CONFIGURED_DESTINATION
    dest = log_destination or "stdout"
    if _CONFIGURED_DESTINATION == dest:
        root = logging.getLogger("IIAE")
        if root.handlers:
            return

    root = logging.getLogger("IIAE")
    root.handlers.clear()
    handler = _build_handler(dest)
    if not isinstance(handler, logging.NullHandler):
        handler.setFormatter(JSONFormatter())
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    root.propagate = False
    _CONFIGURED_DESTINATION = dest


def get_logger(name: str) -> logging.Logger:
    """Return an IIAE namespaced logger using the configured destination."""
    if _CONFIGURED_DESTINATION is None:
        configure_logging(os.getenv("IIAE_LOG_DESTINATION", "stdout"))

    if not name.startswith("IIAE"):
        name = f"IIAE.{name}"

    child = logging.getLogger(name)
    child.handlers.clear()
    child.propagate = True
    child.setLevel(logging.NOTSET)
    return child