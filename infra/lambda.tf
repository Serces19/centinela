# infra/lambda.tf
# Funcion Lambda en contenedor con AWS Lambda Web Adapter (Streaming SSE)

resource "aws_lambda_function" "backend" {
  function_name = "centinela-backend"
  role          = aws_iam_role.lambda_exec.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.backend.repository_url}:latest"
  memory_size   = 1024
  timeout       = 300

  environment {
    variables = {
      AWS_LWA_INVOKE_MODE = "response_stream"
      PORT                = "8080"
      AWS_LWA_PORT        = "8080"
      CENTINELA_ENTORNO   = var.entorno
    }
  }

  tags = {
    Modulo = "backend"
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic,
    aws_iam_role_policy_attachment.lambda_bedrock,
    aws_iam_role_policy_attachment.lambda_dynamodb,
  ]
}

resource "aws_lambda_function_url" "backend_url" {
  function_name      = aws_lambda_function.backend.function_name
  authorization_type = "NONE"
  invoke_mode        = "RESPONSE_STREAM"

  cors {
    allow_credentials = false
    allow_origins     = ["*"]
    allow_methods     = ["*"]
    allow_headers     = ["*"]
    expose_headers    = ["*"]
    max_age           = 86400
  }
}

resource "aws_lambda_permission" "public_function_url" {
  statement_id           = "FunctionURLAllowPublicAccess"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.backend.function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}

resource "aws_lambda_permission" "public_function_invoke" {
  statement_id  = "FunctionAllowInvokeFunction"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.backend.function_name
  principal     = "*"
}

output "lambda_function_url" {
  value       = aws_lambda_function_url.backend_url.function_url
  description = "URL publica con soporte Streaming SSE para Centinela Backend"
}
