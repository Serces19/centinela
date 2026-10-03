# infra/amplify.tf
# Configuración de AWS Amplify Hosting para el frontend de Centinela (Fase 3 / Tarea 3.12)

resource "aws_amplify_app" "centinela_frontend" {
  name        = "centinela-frontend"
  description = "Frontend SPA minimalista de Centinela (React 18 + Vite + Tailwind)"

  custom_rule {
    source = "</^[^.]+$|\\.(?!(css|gif|ico|jpg|js|png|txt|svg|woff|woff2|ttf|map|json)$)([^.]+$)/>"
    target = "/index.html"
    status = "200"
  }

  environment_variables = {
    VITE_API_URL = "https://kshttlmqbtzbjc5a73m5v6rfre0qimbv.lambda-url.us-east-1.on.aws"
    ENV          = var.entorno
  }

  tags = {
    Proyecto = "Centinela"
    Modulo   = "Frontend"
    Fase     = "3"
  }
}

resource "aws_amplify_branch" "main" {
  app_id      = aws_amplify_app.centinela_frontend.id
  branch_name = "main"

  enable_auto_build = false

  tags = {
    Proyecto = "Centinela"
    Branch   = "main"
  }
}

output "amplify_app_id" {
  description = "ID de la aplicación AWS Amplify"
  value       = aws_amplify_app.centinela_frontend.id
}

output "amplify_default_domain" {
  description = "Dominio por defecto de Amplify"
  value       = aws_amplify_app.centinela_frontend.default_domain
}
