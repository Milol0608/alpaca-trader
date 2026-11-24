from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from trader.config import LIVE_CONFIRMATION_PHRASE, Mode, Settings, check_live_gate

NOW = datetime(2026, 11, 24, 12, tzinfo=timezone.utc)


def settings(tmp_path: Path, **kw) -> Settings:
    return Settings(_env_file=None, gate_file=tmp_path / "gate.json", **kw)  # type: ignore[call-arg]


def gate(tmp_path: Path, passed_at: datetime, passed: bool = True) -> None:
    (tmp_path / "gate.json").write_text(json.dumps({"passed": passed, "passed_at": passed_at.isoformat()}))


def test_defaults_to_paper_and_live_is_locked(tmp_path: Path) -> None:
    s = settings(tmp_path)
    assert s.mode is Mode.PAPER and s.trading_url == "https://paper-api.alpaca.markets"
    assert len(check_live_gate(s, NOW)) == 3


def test_live_needs_mode_phrase_and_fresh_gate(tmp_path: Path) -> None:
    gate(tmp_path, NOW - timedelta(days=3))
    ok = settings(tmp_path, mode="live", live_trading_confirmed=LIVE_CONFIRMATION_PHRASE)
    assert check_live_gate(ok, NOW) == []
    gate(tmp_path, NOW - timedelta(days=31))
    assert any("older than" in f for f in check_live_gate(ok, NOW))
    gate(tmp_path, NOW - timedelta(days=3), passed=False)
    assert any("passed=true" in f for f in check_live_gate(ok, NOW))


def test_paper_and_live_keys_never_mix(tmp_path: Path) -> None:
    s = settings(tmp_path, alpaca_paper_key_id="P", alpaca_paper_secret_key="paper-secret-zzz",
                 alpaca_live_key_id="L", alpaca_live_secret_key="live-secret-qqq")
    assert s.credentials() == ("P", "paper-secret-zzz")
    assert s.model_copy(update={"mode": Mode.LIVE}).credentials() == ("L", "live-secret-qqq")
    assert "secret-zzz" not in repr(s) and "secret-qqq" not in repr(s)  # secrets never print
