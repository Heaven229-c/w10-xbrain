variable "aws_region" {
  type        = string
  description = "AWS region used to create resources."
  default     = "ap-southeast-1"
}

variable "vpc_cidr" {
  type        = string
  description = "CIDR block for the VPC."

  validation {
    condition     = can(cidrhost(var.vpc_cidr, 0))
    error_message = "vpc_cidr must be a valid CIDR block, for example 10.0.0.0/16."
  }
}

variable "vpc_name" {
  type        = string
  description = "Value for the VPC Name tag."
}
