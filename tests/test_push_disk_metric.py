import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FAKE_BIN = Path(__file__).resolve().parent /"fake_bin"
GNU_BIN = subprocess.run(
    ["brew", "--prefix", "coreutils"],
    capture_output=True,
    text=True
).stdout.strip() + "/libexec/gnubin"

def test_push_disk_metric_calls_fake_aws(tmp_path):
    log_file = tmp_path / "fake_aws.log"
    env = os.environ.copy()
    env["PATH"] = f"{GNU_BIN}:{FAKE_BIN}:{env['PATH']}"
    env["INSTANCE_ID"] = "i-fake123456"
    env["FAKE_AWS_LOG"] = str(log_file)

    result = subprocess.run(
        ["bash", str(REPO_ROOT / "push_disk_metric.sh")],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "sent UsedPercent=" in result.stdout
    assert "instance=i-fake123456" in result.stdout

    log_content = log_file.read_text()
    assert "put-metric-data" in log_content
    assert "KangaNews/Disk" in log_content