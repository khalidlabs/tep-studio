"""CLI smoke tests for ``tep`` (driven in-process via ``cli.main``)."""

from __future__ import annotations

from tep_studio.cli import main


def test_cli_version(capsys) -> None:
    import tep_studio

    assert main(["version"]) == 0
    assert tep_studio.__version__ in capsys.readouterr().out


def test_cli_list_setpoints(capsys) -> None:
    assert main(["list", "setpoints"]) == 0
    assert "production_rate" in capsys.readouterr().out


def test_cli_list_disturbances(capsys) -> None:
    assert main(["list", "disturbances"]) == 0
    out = capsys.readouterr().out
    assert "idv_01" in out and "A/C ratio" in out


def test_cli_run_writes_dataset(tmp_path, capsys) -> None:
    out = tmp_path / "run.csv"
    assert main(["run", "--horizon", "1", "--control-interval", "0.05", "--out", str(out)]) == 0
    assert out.exists() and out.stat().st_size > 0
    printed = capsys.readouterr().out
    assert "stabilized" in printed or "SHUTDOWN" in printed


def test_cli_invalid_idv_errors(capsys) -> None:
    # A bad disturbance name must fail loudly (validation) without running a simulation.
    assert main(["run", "--horizon", "0.5", "--control-interval", "0.1", "--idv", "idv_99"]) == 2
    assert "error" in capsys.readouterr().err
