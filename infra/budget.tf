# infra/budget.tf
resource "aws_budgets_budget" "presupuesto_centinela" {
  name              = "centinela-presupuesto-mensual"
  budget_type       = "COST"
  limit_amount      = "20"
  limit_unit        = "USD"
  time_unit         = "MONTHLY"
  time_period_start = "2026-10-01_00:00"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 50
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alerta_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alerta_email]
  }
}
