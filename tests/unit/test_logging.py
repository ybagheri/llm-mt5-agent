"""Structured logging tests."""

from __future__ import annotations

import json
import logging

import pytest

from mt5_agent.logging_utils import configure_logging, get_logger


def test_json_logging_emits_structured_record(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(level="INFO", log_format="json", force=True)
    logger = get_logger("test.json")
    logger.info("hello", extra={"extra_fields": {"symbol": "EURUSD"}})
    out = capsys.readouterr().out.strip().splitlines()
    assert out, "expected log output on stdout"
    record = json.loads(out[-1])
    assert record["msg"] == "hello"
    assert record["symbol"] == "EURUSD"
    assert record["level"] == "INFO"


def test_text_logging_does_not_crash(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(level="DEBUG", log_format="text", force=True)
    logger = get_logger("test.text")
    logger.debug("ping", extra={"extra_fields": {"k": "v"}})
    out = capsys.readouterr().out
    assert "ping" in out
    configure_logging(level="INFO", log_format="json", force=True)


def test_log_level_filtering(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(level="WARNING", log_format="json", force=True)
    logger = get_logger("test.filter")
    logger.info("suppressed")
    assert capsys.readouterr().out == ""
    configure_logging(level="INFO", log_format="json", force=True)
    assert logging.getLogger().level == logging.INFO
