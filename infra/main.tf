# infra/main.tf
terraform {
  backend "s3" {
    bucket         = "centinela-tfstate-295894327291"
    key            = "centinela/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "centinela-tfstate-locks"
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Proyecto      = "centinela"
      Entorno       = var.entorno
      GestionadoPor = "terraform"
    }
  }
}
