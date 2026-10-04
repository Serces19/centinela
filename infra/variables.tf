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

variable "guardrail_id" {
  type        = string
  description = "ID del Bedrock Guardrail de Centinela (creado con scripts/setup_guardrail.py)"
  default     = "zuonkeflxh8f"
}

variable "guardrail_version" {
  type        = string
  description = "Versión numerada del guardrail (no DRAFT)"
  default     = "1"
}

variable "api_key_param" {
  type        = string
  description = "Nombre del parámetro SSM SecureString con la API key (se crea fuera de Terraform para no guardarla en el estado)"
  default     = "/centinela/api_key"
}
