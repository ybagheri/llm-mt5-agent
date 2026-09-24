"""Settings / configuration tests (Phase 00: no trading logic)."""

from __future__ import annotations

import pytest

from mt5_agent.config.loader import load_settings
from mt5_agent.config.settings import AppSettings


def test_defaults_are_demo_first() -> None:
    s = AppSettings()
    assert s.trading_mode == "dry_run"
    assert s.enable_live_trading is False


def test_live_requires_explicit_opt_in() -> None:
    with pytest.raises(ValueError, match="Live trading is never enabled"):
        AppSettings(trading_mode="live", enable_live_trading=False)


def test_live_opt_in_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MT5_AGENT_TRADING_MODE", "live")
    monkeypatch.setenv("MT5_AGENT_EXECUTION_MODE", "live")
    monkeypatch.setenv("MT5_AGENT_ENABLE_LIVE_TRADING", "true")
    s = AppSettings()
    assert s.trading_mode == "live"
    assert s.enable_live_trading is True


def test_yaml_loading(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MT5_AGENT_TRADING_MODE", raising=False)
    monkeypatch.delenv("MT5_AGENT_EXECUTION_MODE", raising=False)
    monkeypatch.delenv("MT5_AGENT_ENABLE_LIVE_TRADING", raising=False)
    cfg = tmp_path / "app.yaml"
    cfg.write_text("app_name: test-agent\nlog_level: DEBUG\n", encoding="utf-8")
    s = load_settings(config_path=cfg, load_env_file=False)
    assert s.app_name == "test-agent"
    assert s.log_level == "DEBUG"
    # safety defaults preserved
    assert s.trading_mode == "dry_run"


def test_invalid_yaml_raises(tmp_path) -> None:
    cfg = tmp_path / "bad.yaml"
    cfg.write_text("not: [valid: yaml: :\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid YAML"):
        load_settings(config_path=cfg, load_env_file=False)


def test_env_overrides_file(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "app.yaml"
    cfg.write_text("log_level: DEBUG\n", encoding="utf-8")
    monkeypatch.setenv("MT5_AGENT_LOG_LEVEL", "ERROR")
    s = load_settings(config_path=cfg, load_env_file=False)
    assert s.log_level == "ERROR"


def test_mt5_path_and_connection_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MT5_AGENT_MT5_PATH", raising=False)
    s = AppSettings(mt5_path="C:/mt5/terminal64.exe", mt5_login=1, mt5_server="S")
    assert s.mt5_path == "C:/mt5/terminal64.exe"
    cfg = s.to_connection_config()
    assert cfg.path == "C:/mt5/terminal64.exe"
    assert cfg.login == 1
    assert cfg.server == "S"


def test_risk_config_defaults_and_parsing() -> None:
    s = AppSettings()
    cfg = s.to_risk_config()
    assert cfg.max_risk_pct_per_trade == 1.0
    assert cfg.allowed_symbols is None
    assert len(cfg.allowed_sessions) == 1
    s2 = AppSettings(risk_allowed_symbols="EURUSD, XAUUSD", risk_allowed_sessions="8-18")
    cfg2 = s2.to_risk_config()
    assert cfg2.allowed_symbols == ("EURUSD", "XAUUSD")
    assert cfg2.allowed_sessions[0].start_hour == 8


def test_risk_session_spec_validation() -> None:
    with pytest.raises(ValueError):
        AppSettings(risk_allowed_sessions="nope").to_risk_config()
    with pytest.raises(ValueError):
        AppSettings(risk_allowed_sessions="10-10").to_risk_config()


def test_execution_live_requires_opt_in() -> None:
    with pytest.raises(ValueError, match="Live trading is never enabled"):
        AppSettings(execution_mode="live", enable_live_trading=False)
    s = AppSettings(trading_mode="live", execution_mode="live", enable_live_trading=True)
    assert s.execution_mode == "live"
    assert AppSettings().execution_mode == "dry_run"
