# infra/iam.tf
data "aws_caller_identity" "current" {}

# Política mínima de IAM para la Lambda de Centinela interactuando con Bedrock
data "aws_iam_policy_document" "lambda_bedrock" {
  statement {
    sid    = "BedrockInferenceProfile"
    effect = "Allow"
    actions = [
      "bedrock:InvokeModel",
      "bedrock:InvokeModelWithResponseStream",
      "bedrock:Converse",
      "bedrock:ConverseStream",
    ]
    resources = [
      # Perfil de inferencia en us-east-1
      "arn:aws:bedrock:${var.aws_region}:${data.aws_caller_identity.current.account_id}:inference-profile/us.anthropic.claude-haiku-4-5-20251001-v1:0",
      # Modelos base subyacentes en todas las regiones que enruta el perfil (us-east-1, us-east-2, us-west-2)
      "arn:aws:bedrock:*::foundation-model/anthropic.claude-haiku-4-5-20251001-v1:0",
      "arn:aws:bedrock:*::foundation-model/amazon.titan-embed-text-v2:0",
    ]
  }

  statement {
    sid       = "LeerApiKey"
    effect    = "Allow"
    actions   = ["ssm:GetParameter"]
    resources = ["arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${var.api_key_param}"]
  }

  statement {
    sid    = "BedrockKnowledgeBaseAndGuardrail"
    effect = "Allow"
    actions = [
      "bedrock:ApplyGuardrail",
      "bedrock:Retrieve",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "lambda_bedrock" {
  name        = "centinela-lambda-bedrock-policy"
  description = "Permisos minimos para Centinela Lambda en Amazon Bedrock"
  policy      = data.aws_iam_policy_document.lambda_bedrock.json
}

# Rol de ejecución para Lambda Backend
resource "aws_iam_role" "lambda_exec" {
  name = "centinela-lambda-exec-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Modulo = "seguridad"
  }
}

# Logs básicos de CloudWatch
resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Permisos Bedrock
resource "aws_iam_role_policy_attachment" "lambda_bedrock" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = aws_iam_policy.lambda_bedrock.arn
}

# Permisos DynamoDB (con inmutabilidad de bitácora)
data "aws_iam_policy_document" "lambda_dynamodb" {
  statement {
    sid    = "CentinelaDynamoDBTables"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:DeleteItem",
      "dynamodb:Query",
      "dynamodb:Scan",
      "dynamodb:BatchGetItem",
      "dynamodb:BatchWriteItem",
    ]
    resources = [
      aws_dynamodb_table.alertas.arn,
      "${aws_dynamodb_table.alertas.arn}/index/*",
      aws_dynamodb_table.bitacora.arn,
      aws_dynamodb_table.trazas.arn,
      aws_dynamodb_table.reloj.arn,
      aws_dynamodb_table.config.arn,
    ]
  }

  statement {
    sid    = "CentinelaBitacoraInmutable"
    effect = "Deny"
    actions = [
      "dynamodb:UpdateItem",
      "dynamodb:DeleteItem",
    ]
    resources = [
      aws_dynamodb_table.bitacora.arn,
    ]
  }
}

resource "aws_iam_policy" "lambda_dynamodb" {
  name        = "centinela-lambda-dynamodb-policy"
  description = "Permisos minimos para Centinela Lambda en DynamoDB con bitacora inmutable"
  policy      = data.aws_iam_policy_document.lambda_dynamodb.json
}

resource "aws_iam_role_policy_attachment" "lambda_dynamodb" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = aws_iam_policy.lambda_dynamodb.arn
}
