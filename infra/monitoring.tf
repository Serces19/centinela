# infra/monitoring.tf
# Fase 3b: Dashboard de CloudWatch "Centinela-Operaciones" y Alarmas SNS

# -----------------------------------------------------------------------------
# Topico SNS y Suscripción para Notificaciones Críticas y Operativas
# -----------------------------------------------------------------------------
resource "aws_sns_topic" "alarmas" {
  name = "centinela-alarmas-operaciones"

  tags = {
    Modulo = "observabilidad"
  }
}

resource "aws_sns_topic_subscription" "email_alarmas" {
  topic_arn = aws_sns_topic.alarmas.arn
  protocol  = "email"
  endpoint  = var.alerta_email
}

# -----------------------------------------------------------------------------
# Alarmas CloudWatch
# -----------------------------------------------------------------------------

# 1. Alarma Crítica: Manipulación o Inconsistencia en Cadena de Bitácora SHA-256
resource "aws_cloudwatch_metric_alarm" "bitacora_cadena_rota" {
  alarm_name          = "centinela-critica-bitacora-rota"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "BitacoraCadenaRota"
  namespace           = "Centinela"
  period              = 60
  statistic           = "Sum"
  threshold           = 1
  alarm_description   = "Alarma CRÍTICA: Se detectó una ruptura de secuencia o hash en la bitácora inmutable SHA-256."
  alarm_actions       = [aws_sns_topic.alarmas.arn]
  treat_missing_data  = "notBreaching"

  tags = {
    Severidad = "CRITICA"
  }
}

# 2. Alarma de Rendimiento: Latencia de Pipeline p95 > 20 segundos
resource "aws_cloudwatch_metric_alarm" "pipeline_latencia_alta" {
  alarm_name          = "centinela-latencia-p95-alta"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "PipelineLatenciaMs"
  namespace           = "Centinela"
  period              = 300
  extended_statistic  = "p95"
  threshold           = 20000
  alarm_description   = "La latencia p95 del pipeline de agentes superó los 20 segundos."
  alarm_actions       = [aws_sns_topic.alarmas.arn]
  treat_missing_data  = "notBreaching"
}

# 3. Alarma de Seguridad: Detección de Prompt Injection en Guardrail
resource "aws_cloudwatch_metric_alarm" "guardrail_ataque_detectado" {
  alarm_name          = "centinela-seguridad-ataque-prompt"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "GuardrailIntervino"
  namespace           = "Centinela"
  period              = 60
  statistic           = "Sum"
  threshold           = 1
  alarm_description   = "Alerta de Seguridad: Se detectó e interceptó un intento de ataque de inyección de prompt."
  alarm_actions       = [aws_sns_topic.alarmas.arn]
  treat_missing_data  = "notBreaching"

  dimensions = {
    Tipo = "ataque"
  }
}

# 4. Alarma de Errores en Función Lambda Backend
resource "aws_cloudwatch_metric_alarm" "lambda_errores" {
  alarm_name          = "centinela-lambda-backend-errores"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 1
  alarm_description   = "Se presentaron errores de ejecución no controlados en la Lambda de Centinela."
  alarm_actions       = [aws_sns_topic.alarmas.arn]
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.backend.function_name
  }
}

# -----------------------------------------------------------------------------
# Dashboard CloudWatch: "Centinela-Operaciones"
# -----------------------------------------------------------------------------
resource "aws_cloudwatch_dashboard" "operaciones" {
  dashboard_name = "Centinela-Operaciones"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          title = "Alertas Generadas por Severidad (EMF)"
          metrics = [
            ["Centinela", "AlertasGeneradas", "Severidad", "critica", { stat = "Sum", label = "Crítica", color = "#dc2626" }],
            ["Centinela", "AlertasGeneradas", "Severidad", "alta", { stat = "Sum", label = "Alta", color = "#f97316" }],
            ["Centinela", "AlertasGeneradas", "Severidad", "media", { stat = "Sum", label = "Media", color = "#eab308" }],
            ["Centinela", "AlertasGeneradas", "Severidad", "baja", { stat = "Sum", label = "Baja", color = "#3b82f6" }]
          ]
          view    = "timeSeries"
          stacked = true
          region  = var.aws_region
          period  = 300
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          title = "Latencia de Agentes Pipeline (p50 / p95 ms)"
          metrics = [
            ["Centinela", "PipelineLatenciaMs", "Agente", "vigia", { stat = "p95", label = "Vigía (p95)", color = "#10b981" }],
            ["Centinela", "PipelineLatenciaMs", "Agente", "analista", { stat = "p95", label = "Analista (p95)", color = "#6366f1" }],
            ["Centinela", "PipelineLatenciaMs", "Agente", "estratega", { stat = "p95", label = "Estratega (p95)", color = "#ec4899" }],
            ["Centinela", "PipelineLatenciaMs", "Agente", "analista", { stat = "p50", label = "Analista (p50)", color = "#a5b4fc" }]
          ]
          view   = "timeSeries"
          region = var.aws_region
          period = 300
          yAxis  = { left = { min = 0, label = "Milisegundos" } }
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 8
        height = 6
        properties = {
          title = "Consumo de Tokens Bedrock Claude Haiku 4.5"
          metrics = [
            ["Centinela", "LlmTokensEntrada", "Agente", "analista", { stat = "Sum", label = "Entrada (Analista)", color = "#3b82f6" }],
            ["Centinela", "LlmTokensSalida", "Agente", "analista", { stat = "Sum", label = "Salida (Analista)", color = "#60a5fa" }],
            ["Centinela", "LlmTokensEntrada", "Agente", "estratega", { stat = "Sum", label = "Entrada (Estratega)", color = "#8b5cf6" }],
            ["Centinela", "LlmTokensSalida", "Agente", "estratega", { stat = "Sum", label = "Salida (Estratega)", color = "#a78bfa" }]
          ]
          view   = "timeSeries"
          region = var.aws_region
          period = 300
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 6
        width  = 8
        height = 6
        properties = {
          title = "Seguridad y Guardrails (Intervenciones)"
          metrics = [
            ["Centinela", "GuardrailIntervino", "Tipo", "ataque", { stat = "Sum", label = "Ataque Prompt (Bloqueado)", color = "#ef4444" }],
            ["Centinela", "GuardrailIntervino", "Tipo", "pii", { stat = "Sum", label = "PII Anonimizado", color = "#f59e0b" }]
          ]
          view    = "timeSeries"
          stacked = true
          region  = var.aws_region
          period  = 300
        }
      },
      {
        type   = "metric"
        x      = 16
        y      = 6
        width  = 8
        height = 6
        properties = {
          title = "Integridad Criptográfica de Bitácora"
          metrics = [
            ["Centinela", "BitacoraCadenaRota", "Tipo", "sha256_o_secuencia_invalida", { stat = "Sum", label = "Cadena Rota (Crítico)", color = "#b91c1c" }]
          ]
          view   = "singleValue"
          region = var.aws_region
          period = 300
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 12
        width  = 12
        height = 6
        properties = {
          title = "Decisiones Humanas HITL (Aprobaciones vs Rechazos)"
          metrics = [
            ["Centinela", "AprobacionesHumanas", "Decision", "aprobada", { stat = "Sum", label = "Aprobadas", color = "#22c55e" }],
            ["Centinela", "Rechazos", "Decision", "rechazada", { stat = "Sum", label = "Rechazadas", color = "#ef4444" }]
          ]
          view   = "timeSeries"
          region = var.aws_region
          period = 300
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 12
        width  = 12
        height = 6
        properties = {
          title = "Métricas Nativas Lambda Backend (Invocaciones y Errores)"
          metrics = [
            ["AWS/Lambda", "Invocations", "FunctionName", aws_lambda_function.backend.function_name, { stat = "Sum", label = "Invocaciones", color = "#2563eb" }],
            ["AWS/Lambda", "Errors", "FunctionName", aws_lambda_function.backend.function_name, { stat = "Sum", label = "Errores", color = "#dc2626" }]
          ]
          view   = "timeSeries"
          region = var.aws_region
          period = 300
        }
      }
    ]
  })
}

output "cloudwatch_dashboard_name" {
  value       = aws_cloudwatch_dashboard.operaciones.dashboard_name
  description = "Nombre del Dashboard de Operaciones y Observabilidad en CloudWatch"
}

output "sns_topic_alarmas_arn" {
  value       = aws_sns_topic.alarmas.arn
  description = "ARN del tópico SNS de alertas operativas y críticas de Centinela"
}
