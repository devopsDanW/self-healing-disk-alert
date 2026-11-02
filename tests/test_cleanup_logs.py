import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

def _gnubin(formula):
    prefix = subprocess.run(
        ["brew", "--prefix", formula],
        capture_output=True,
        text=True,
    ).stdout.strip()

    return f"{prefix}/libexec/gnubin"

GNU_BIN = _gnubin("coreutils")
GNU_FIND_BIN = _gnubin("findutils")

def run_cleanup(log_dir, args=None):
    env = os.environ.copy()
    env["PATH"] = f"{GNU_FIND_BIN}:{GNU_BIN}:{env['PATH']}"
    env["LOG_DIR"] = str(log_dir)
    cmd = ["bash", str(REPO_ROOT / "cleanup_logs.sh")]
    if args:
        cmd += args
    return subprocess.run(cmd, env=env, capture_output=True, text=True)

def test_dry_run_changes_nothing(tmp_path):
    big_log = tmp_path / "big.log"
    big_log.write_bytes(b"x" * (11 * 1024 * 1024))
    old_gz = tmp_path / "old.gz"
    old_gz.write_text("archived")
    os.utime(old_gz, (0, 0))

    result = run_cleanup(tmp_path)

    assert result.returncode == 0
    assert "MODE=dry-run" in result.stdout
    assert big_log.stat().st_size == 11 * 1024 * 1024
    assert old_gz.exists()

def test_apply_truncates_big_log_but_keeps_file(tmp_path):
    big_log = tmp_path / "big.log"
    big_log.write_bytes(b"x" * (11 * 1024 * 1024))

    result = run_cleanup(tmp_path, args=["--apply"])

    assert result.returncode == 0
    assert "MODE=apply" in result.stdout
    assert big_log.exists()
    assert big_log.stat().st_size == 0

def test_apply_small_log_untouched(tmp_path):
    small_log = tmp_path / "small.log"
    small_log.write_text("just a little bit of log")

    result = run_cleanup(tmp_path, args=["--apply"])

    assert result.returncode == 0
    assert small_log.read_text() == "just a little bit of log"

def test_apply_deletes_old_gz(tmp_path):
    old_gz = tmp_path / "old.gz"
    old_gz.write_text("archived")
    os.utime(old_gz, (0, 0))

    result = run_cleanup(tmp_path, args=["--apply"])

    assert result.returncode == 0
    assert not old_gz.exists()

def test_refuses_root_log_dir():

    result = run_cleanup("/")

    assert result.returncode == 2