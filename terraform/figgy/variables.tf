variable "run_env" {
  description = "Defaults are dev/qa/stage/prod/mgmt but can be anything you like."
}

variable "region" {
  description = "AWS region to apply these configurations to"
}

variable "aws_account_id" {
  description = "Account id to enable role assumption for"
}

variable "deploy_bucket" {
  description = "Bucket where your figgy lambdas will be deployed and versioned."
}

variable "max_session_duration" {
  description = "Max session duration in seconds for this assumed role. Default: 12 hours"
  default     = "43200"
}

variable "webhook_url" {
  description = "Slack Webhook URL for figgy submit notifications such as parameter shares / critical figgy errors."
  default = "unconfigured"  # don't change this unless you update the logic in the SSM parameter
}

variable "sandbox_deploy" {
  description = "Ignore this and keep this false. This is only used for the figgy sandbox environment to facilitate the figgy playground."
  default = false
}