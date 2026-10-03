# infra/dynamodb.tf
# Tablas DynamoDB para Centinela (Modo PAY_PER_REQUEST)
# Ver docs/03_contratos_datos.md (§8.4)

# 1. centinela_alertas
resource "aws_dynamodb_table" "alertas" {
  name         = "centinela_alertas"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "alerta_id"
  range_key    = "tipo_registro"

  attribute {
    name = "alerta_id"
    type = "S"
  }

  attribute {
    name = "tipo_registro"
    type = "S"
  }

  attribute {
    name = "estado"
    type = "S"
  }

  attribute {
    name = "dinero_en_riesgo_cop"
    type = "N"
  }

  attribute {
    name = "huella_causa"
    type = "S"
  }

  global_secondary_index {
    name            = "gsi_estado"
    hash_key        = "estado"
    range_key       = "dinero_en_riesgo_cop"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "gsi_huella"
    hash_key        = "huella_causa"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Modulo = "persistencia"
    Tabla  = "alertas"
  }
}

# 2. centinela_bitacora
resource "aws_dynamodb_table" "bitacora" {
  name         = "centinela_bitacora"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "alerta_id"
  range_key    = "seq"

  attribute {
    name = "alerta_id"
    type = "S"
  }

  attribute {
    name = "seq"
    type = "N"
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Modulo = "bitacora"
    Tabla  = "bitacora"
  }
}

# 3. centinela_checkpoints (LangGraph checkpoints)
resource "aws_dynamodb_table" "checkpoints" {
  name         = "centinela_checkpoints"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "thread_id"
  range_key    = "checkpoint_id"

  attribute {
    name = "thread_id"
    type = "S"
  }

  attribute {
    name = "checkpoint_id"
    type = "S"
  }

  tags = {
    Modulo = "agentes"
    Tabla  = "checkpoints"
  }
}

# 4. centinela_trazas (Trazas LLM y consultas con TTL de 30 días)
resource "aws_dynamodb_table" "trazas" {
  name         = "centinela_trazas"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "alerta_id"
  range_key    = "ts_tipo"

  attribute {
    name = "alerta_id"
    type = "S"
  }

  attribute {
    name = "ts_tipo"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = {
    Modulo = "trazabilidad"
    Tabla  = "trazas"
  }
}

# 5. centinela_reloj (Reloj de simulación)
resource "aws_dynamodb_table" "reloj" {
  name         = "centinela_reloj"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "reloj_pk"
  range_key    = "reloj_sk"

  attribute {
    name = "reloj_pk"
    type = "S"
  }

  attribute {
    name = "reloj_sk"
    type = "S"
  }

  tags = {
    Modulo = "simulacion"
    Tabla  = "reloj"
  }
}

# 6. centinela_config (Configuración de KPIs y parámetros)
resource "aws_dynamodb_table" "config" {
  name         = "centinela_config"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "clave"

  attribute {
    name = "clave"
    type = "S"
  }

  tags = {
    Modulo = "configuracion"
    Tabla  = "config"
  }
}
