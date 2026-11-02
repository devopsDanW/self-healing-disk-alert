import json
import logging
import os
from pathlib import Path

import boto3

# Logging & configuration
logger = logging.getLogger()
logger.setLevel(logging.INFO)

SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN", "")
TARGET_LOG_DIR = os.environ.get("TARGET_LOG_DIR", "/var/log/app")
APPLY = os.environ.get("APPLY", "false").lower() == "true"
SSM_DOCUMENT = "AWS-RunShellScript"
REQUIRED_TAG_KEY = "AutoRemediate"
REQUIRED_TAG_VALUE = "true"
CLEANUP_SCRIPT_PATH = Path(__file__).resolve().parent /"cleanup_logs.sh"

# Event parsing
def parse_alarm_event(event):
    detail = event["detail"]
    alarm_name = detail["alarmName"]
    state = detail["state"]["value"]
    metrics = detail["configuration"]["metrics"]
    dimensions = metrics[0]["metricStat"]["metric"]["dimensions"]
    instance_id = dimensions["InstanceId"]

    return {
        "alarm_name" : alarm_name,
        "state" : state,
        "instance_id" : instance_id,
    }

# Eligibility guard
def _is_eligible(ec2, instance_id):
    resp = ec2.describe_instances(InstanceIds=[instance_id])
    reservations = resp["Reservations"]
    if not reservations:
        return False

    instance = reservations[0]["Instances"][0]

    if instance["State"]["Name"] != "running":
        return False

    tags = {t["Key"]: t["Value"] for t in instance.get("Tags", [])}
    return tags.get(REQUIRED_TAG_KEY) == REQUIRED_TAG_VALUE

# Handler
def handler(event, context, ec2=None, ssm=None, sns=None):
    ec2 = ec2 or boto3.client("ec2")
    ssm = ssm or boto3.client("ssm")
    sns = sns or boto3.client("sns")

    parsed = parse_alarm_event(event)
    alarm_name = parsed["alarm_name"]
    state = parsed["state"]
    instance_id = parsed["instance_id"]

    logger.info(json.dumps({
        "event": "alarm_received",
        "alarm_name": alarm_name,
        "state": state,
        "instance_id": instance_id
    }))

    # Guard: ignore non-Alarm transitions
    if state != "ALARM":
        logger.info(json.dumps({
            "event": "ignored_non_alarm_state",
            "state": state
        }))
        return {"action": "ignored", "reason": "state not ALARM"}
    # Guard: block ineligible instances, escalate to a human
    if not _is_eligible(ec2, instance_id):
        message = (
            f"Disk alarm {alarm_name} fired for instance {instance_id}, but it is not running and tagged AutoRemediate=true, Manual action needed."
        )
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject="Disk alarm: manual action needed",
            Message=message
        )
        logger.info(json.dumps({"event": "blocked", "instance_id": instance_id}))
        return {"action": "blocked", "instance_id": instance_id}

    # Remediation: ship and run the cleanup script via SSM Run Command
    script_content = CLEANUP_SCRIPT_PATH.read_text()
    _cleanup_cmd = f"LOG_DIR={TARGET_LOG_DIR} /tmp/cleanup_logs.sh" + (" --apply" if APPLY else "")
    command = ssm.send_command(
        InstanceIds=[instance_id],
        DocumentName=SSM_DOCUMENT,
        Parameters={
            "commands": [
                "cat << 'CLEANUP_SCRIPT_EOF' > /tmp/cleanup_logs.sh",
                script_content,
                "CLEANUP_SCRIPT_EOF",
                "chmod +x /tmp/cleanup_logs.sh",
                _cleanup_cmd,
            ]
        }
    )

    command_id = command["Command"]["CommandId"]

    # Notify, log, return
    message = (
        f"Disk alarm {alarm_name} fired for instance {instance_id}. Ran cleanup via SSM, command id {command_id}"
    )
    sns.publish(
        TopicArn=SNS_TOPIC_ARN,
        Subject="Disk alarm: cleanup executed",
        Message=message,
    )

    logger.info(json.dumps({
        "event": "remediated",
        "instance_id": instance_id,
        "command_id": command_id,
    }))
    return {"action": "remediated", "instance_id": instance_id, "command_id": command_id}