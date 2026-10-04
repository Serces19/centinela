# infra/kb.tf
# Amazon Bedrock Knowledge Base con S3 Vectors (Zero-Cost Serverless Storage)
# Utiliza Titan Embeddings V2 (1024 dim) y S3 Vectors para indexación de las 3 políticas normativas.

variable "s3_vectors_index_arn" {
  description = "ARN del índice de S3 Vectors PROPIO de Centinela (se crea con scripts/provision_vectores.py; no compartir con otras KB)"
  type        = string
  default     = "arn:aws:s3vectors:us-east-1:295894327291:bucket/centinela-vectors-295894327291/index/politicas"
}

# 1. Bucket S3 para documentos de políticas normativas
data "aws_s3_bucket" "politicas" {
  bucket = "centinela-politicas-${data.aws_caller_identity.current.account_id}"
}

# 2. Rol IAM para el servicio de Bedrock Knowledge Base
resource "aws_iam_role" "bedrock_kb" {
  name = "centinela-bedrock-kb-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AmazonBedrockKnowledgeBaseTrustPolicy"
        Effect = "Allow"
        Principal = {
          Service = "bedrock.amazonaws.com"
        }
        Action = "sts:AssumeRole"
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
          ArnLike = {
            "aws:SourceArn" = "arn:aws:bedrock:${var.aws_region}:${data.aws_caller_identity.current.account_id}:knowledge-base/*"
          }
        }
      }
    ]
  })

  tags = {
    Modulo = "conocimiento"
  }
}

# 3. Política IAM de acceso al bucket S3 de documentos de origen
resource "aws_iam_role_policy" "bedrock_kb_s3" {
  name = "centinela-bedrock-kb-s3-policy"
  role = aws_iam_role.bedrock_kb.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3ListBucketStatement"
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = [
          data.aws_s3_bucket.politicas.arn
        ]
        Condition = {
          StringEquals = {
            "aws:ResourceAccount" = data.aws_caller_identity.current.account_id
          }
        }
      },
      {
        Sid    = "S3GetObjectStatement"
        Effect = "Allow"
        Action = [
          "s3:GetObject"
        ]
        Resource = [
          "${data.aws_s3_bucket.politicas.arn}/*"
        ]
        Condition = {
          StringEquals = {
            "aws:ResourceAccount" = data.aws_caller_identity.current.account_id
          }
        }
      }
    ]
  })
}

# 4. Política IAM de invocación del modelo Titan Embeddings V2
resource "aws_iam_role_policy" "bedrock_kb_model" {
  name = "centinela-bedrock-kb-model-policy"
  role = aws_iam_role.bedrock_kb.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "BedrockInvokeModelStatement"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel"
        ]
        Resource = [
          "arn:aws:bedrock:${var.aws_region}::foundation-model/amazon.titan-embed-text-v2:0"
        ]
      }
    ]
  })
}

# 5. Política IAM para S3 Vectors Store
resource "aws_iam_role_policy" "bedrock_kb_s3_vectors" {
  name = "centinela-bedrock-kb-s3-vectors-policy"
  role = aws_iam_role.bedrock_kb.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3VectorsPermissions"
        Effect = "Allow"
        Action = [
          "s3vectors:GetIndex",
          "s3vectors:QueryVectors",
          "s3vectors:PutVectors",
          "s3vectors:GetVectors",
          "s3vectors:ListVectors",
          "s3vectors:DeleteVectors"
        ]
        Resource = var.s3_vectors_index_arn
        Condition = {
          StringEquals = {
            "aws:ResourceAccount" = data.aws_caller_identity.current.account_id
          }
        }
      }
    ]
  })
}

# 6. Recurso CloudFormation Stack nativo en Terraform para Knowledge Base y Data Source
resource "aws_cloudformation_stack" "bedrock_kb" {
  name         = "centinela-bedrock-knowledge-base"
  capabilities = ["CAPABILITY_IAM", "CAPABILITY_NAMED_IAM"]

  parameters = {
    RoleArn           = aws_iam_role.bedrock_kb.arn
    PoliticasBucket   = data.aws_s3_bucket.politicas.arn
    S3VectorsIndexArn = var.s3_vectors_index_arn
  }

  template_body = jsonencode({
    AWSTemplateFormatVersion = "2010-09-09"
    Description              = "Bedrock Knowledge Base con S3 Vectors para Centinela"

    Parameters = {
      RoleArn = {
        Type        = "String"
        Description = "ARN del rol de ejecucion de Bedrock KB"
      }
      PoliticasBucket = {
        Type        = "String"
        Description = "ARN del bucket S3 de politicas"
      }
      S3VectorsIndexArn = {
        Type        = "String"
        Description = "ARN del indice de S3 Vectors"
      }
    }

    Resources = {
      KnowledgeBase = {
        Type = "AWS::Bedrock::KnowledgeBase"
        Properties = {
          Name        = "centinela-politicas-kb"
          Description = "Base de conocimiento normativo para Distribuidora Andina SAS (FIN-POL-004, COM-POL-002, OPE-POL-007)"
          RoleArn     = { Ref = "RoleArn" }
          KnowledgeBaseConfiguration = {
            Type = "VECTOR"
            VectorKnowledgeBaseConfiguration = {
              EmbeddingModelArn = "arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v2:0"
              EmbeddingModelConfiguration = {
                BedrockEmbeddingModelConfiguration = {
                  Dimensions        = 1024
                  EmbeddingDataType = "FLOAT32"
                }
              }
            }
          }
          StorageConfiguration = {
            Type = "S3_VECTORS"
            S3VectorsConfiguration = {
              IndexArn = { Ref = "S3VectorsIndexArn" }
            }
          }
        }
      }

      DataSource = {
        Type = "AWS::Bedrock::DataSource"
        Properties = {
          KnowledgeBaseId = { Ref = "KnowledgeBase" }
          Name            = "centinela-politicas-data-source"
          Description     = "Documentos normativos PDF en S3"
          DataSourceConfiguration = {
            Type = "S3"
            S3Configuration = {
              BucketArn = { Ref = "PoliticasBucket" }
            }
          }
          DataDeletionPolicy = "DELETE"
        }
      }
    }

    Outputs = {
      KnowledgeBaseId = {
        Value       = { Ref = "KnowledgeBase" }
        Description = "ID de la Bedrock Knowledge Base"
      }
      KnowledgeBaseArn = {
        Value       = { "Fn::GetAtt" = ["KnowledgeBase", "KnowledgeBaseArn"] }
        Description = "ARN de la Bedrock Knowledge Base"
      }
      DataSourceId = {
        Value       = { Ref = "DataSource" }
        Description = "ID del DataSource en Bedrock Knowledge Base"
      }
    }
  })

  depends_on = [
    aws_iam_role_policy.bedrock_kb_s3,
    aws_iam_role_policy.bedrock_kb_model,
    aws_iam_role_policy.bedrock_kb_s3_vectors,
  ]
}

output "bedrock_knowledge_base_id" {
  value       = aws_cloudformation_stack.bedrock_kb.outputs["KnowledgeBaseId"]
  description = "ID de la Knowledge Base de Amazon Bedrock con S3 Vectors"
}

output "bedrock_data_source_id" {
  value       = aws_cloudformation_stack.bedrock_kb.outputs["DataSourceId"]
  description = "ID del Data Source de politicas en Bedrock Knowledge Base"
}
