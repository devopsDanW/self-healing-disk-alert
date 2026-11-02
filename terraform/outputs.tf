output "instance_id" {
  value = aws_instance.app.id
}

output "sns_topic_arn" {
  value = aws_sns_topic.alerts.arn
}

output "lambda_function_name" {
  value = aws_lambda_function.remediate.function_name
}

output "alarm_name" {
  value = aws_cloudwatch_metric_alarm.disk_usage.alarm_name
}