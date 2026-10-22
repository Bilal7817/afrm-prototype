from __future__ import annotations

import csv
from pathlib import Path

import pytest

from afrm.cli import main
from tests.conftest import CONFIG_PATH

CFG = ["--config", str(CONFIG_PATH)]


def test_plan_command(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([*CFG, "plan", "--scenario", "low_uplift"]) == 0
    out = capsys.readouterr().out
    assert "6,675 kg" in out
    assert "NOT DISPATCHABLE" in out


def test_simulate_then_monitor_from_csv(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    data = tmp_path / "headwind.csv"
    assert main([*CFG, "simulate", "--scenario", "headwind", "--out", str(data)]) == 0
    assert main([*CFG, "monitor", "--scenario", "headwind", "--csv", str(data)]) == 0
    out = capsys.readouterr().out
    assert "AMBER" in out
    assert "NOT FOR OPERATIONAL USE" in out


def test_monitor_reports_invalid_samples(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data = tmp_path / "bad.csv"
    data.write_text(
        "time_s,fob_kg,fuel_flow_kg_h,ground_speed_km_h,remaining_km\n"
        "0,6800,2400,800,1500\n"
        "60,-5,2400,800,1486\n",
        encoding="utf-8",
    )
    assert main([*CFG, "monitor", "--csv", str(data)]) == 0
    assert "DATA INVALID" in capsys.readouterr().out


def test_run_all_writes_results(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main([*CFG, "run-all", "--no-noise", "--out", str(tmp_path)]) == 0
    with (tmp_path / "summary.csv").open(encoding="utf-8") as handle:
        rows = {r["scenario"]: r for r in csv.DictReader(handle)}
    assert rows["nominal"]["status_sequence"] == "GREEN"
    assert rows["headwind"]["status_sequence"] == "GREEN -> AMBER"
    assert rows["low_uplift"]["dispatch"] == "NOT DISPATCHABLE"
    assert float(rows["headwind"]["final_plf_kg"]) == pytest.approx(1550.0, abs=0.1)
    assert (tmp_path / "plf_timeseries.csv").exists()
    assert "run-all" in capsys.readouterr().out
