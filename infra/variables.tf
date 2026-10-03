# infra/variables.tf
variable "aws_region" {
  type        = string
  description = "Región de AWS"
  default     = "us-east-1"
}

variable "entorno" {
  type        = string
  description = "Entorno de despliegue"
  default     = "dev"
}

variable "alerta_email" {
  type        = string
  description = "Correo para alertas de presupuesto"
  default     = "serces19@gmail.com"
}
