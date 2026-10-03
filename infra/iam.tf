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
