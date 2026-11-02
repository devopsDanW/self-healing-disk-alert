import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT /"lambda"))

import remediate

SAMPLE_EVENT_PATH = REPO_ROOT /"samples" / "alarm_event.json"

def load_sample_event():
    return json.loads(SAMPLE_EVENT_PATH.read_text())

def _instance(state_name, tagged):
    tags = [{"Key": "AutoRemediate", "Value": "true"}] if tagged else []
    return {
        "Reservations": [
            {"Instances": [{"State": {"Name": state_name}, "Tags": tags}]}
        ]
    }

def test_parse_alarm_event_reads_sample():
    event = load_sample_event()
    parsed = remediate.parse_alarm_event(event)

    assert parsed["alarm_name"] == "DiskUsageHigh"
    assert parsed["state"] == "ALARM"
    assert parsed["instance_id"] == "i-0123456789abcdef0"

def test_ok_state_is_ignored():
    event = load_sample_event()
    event["detail"]["state"]["value"] = "OK"

    ec2, ssm, sns = MagicMock(), MagicMock(), MagicMock()
    result = remediate.handler(event, None, ec2=ec2, ssm=ssm, sns=sns)

    assert result["action"] == "ignored"
    ec2.describe_instances.assert_not_called()
    ssm.send_command.assert_not_called()
    sns.publish.assert_not_called()

def test_untagged_instance_is_blocked():
    event = load_sample_event()
    ec2, ssm, sns = MagicMock(), MagicMock(), MagicMock()
    ec2.describe_instances.return_value = _instance("running", tagged=False)

    result = remediate.handler(event, None, ec2=ec2, ssm=ssm, sns=sns)

    assert result["action"] == "blocked"
    ssm.send_command.assert_not_called()
    sns.publish.assert_called_once()
    _, kwargs = sns.publish.call_args
    assert "manual action" in kwargs["Subject"]

def test_stopped_instance_is_blocked():
    event = load_sample_event()
    ec2, ssm, sns = MagicMock(), MagicMock(), MagicMock()
    ec2.describe_instances.return_value = _instance("stopped", tagged=True)

    result = remediate.handler(event, None, ec2=ec2, ssm=ssm, sns=sns)

    assert result["action"] == "blocked"
    ssm.send_command.assert_not_called()
    sns.publish.assert_called_once()

def test_success_with_apply_false(monkeypatch):
    monkeypatch.setattr(remediate, "APPLY", False)

    event = load_sample_event()
    ec2, ssm, sns = MagicMock(), MagicMock(), MagicMock()
    ec2.describe_instances.return_value = _instance("running", tagged=True)
    ssm.send_command.return_value = {"Command": {"CommandId": "cmd-1"}}

    result = remediate.handler(event, None, ec2=ec2, ssm=ssm, sns=sns)

    assert result["action"] == "remediated"
    _, kwargs = ssm.send_command.call_args
    last_command = kwargs["Parameters"]["commands"][-1]
    assert "--apply" not in last_command
    sns.publish.assert_called_once()

def test_success_with_apply_true(monkeypatch):
    monkeypatch.setattr(remediate, "APPLY", True)

    event = load_sample_event()
    ec2, ssm, sns = MagicMock(), MagicMock(), MagicMock()
    ec2.describe_instances.return_value = _instance("running", tagged=True)
    ssm.send_command.return_value = {"Command": {"CommandId": "cmd-2"}}

    result = remediate.handler(event, None, ec2=ec2, ssm=ssm, sns=sns)

    assert result["action"] == "remediated"
    _, kwargs = ssm.send_command.call_args
    last_command = kwargs["Parameters"]["commands"][-1]
    assert last_command.endswith("--apply")
    sns.publish.assert_called_once()