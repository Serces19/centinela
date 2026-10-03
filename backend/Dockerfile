# backend/Dockerfile
# Imagen de contenedor para Centinela Backend con AWS Lambda Web Adapter (Streaming SSE)
FROM public.ecr.aws/lambda/python:3.12

# Instalar AWS Lambda Web Adapter binario
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.9.0 /lambda-adapter /opt/extensions/lambda-adapter

# Variables de entorno clave para soporte de streaming response y puertos
ENV AWS_LWA_INVOKE_MODE=response_stream \
    PORT=8080 \
    AWS_LWA_PORT=8080 \
    PYTHONUNBUFFERED=1

WORKDIR ${LAMBDA_TASK_ROOT}

# Copiar manifiesto de dependencias
COPY pyproject.toml README.md ./

# Instalar dependencias de Python
RUN pip install --no-cache-dir .

# Copiar paquetes de la aplicacion y capa semantica DuckDB
COPY api/ ${LAMBDA_TASK_ROOT}/api/
COPY agents/ ${LAMBDA_TASK_ROOT}/agents/
COPY semantic/ ${LAMBDA_TASK_ROOT}/semantic/
COPY tools/ ${LAMBDA_TASK_ROOT}/tools/
COPY contracts/ ${LAMBDA_TASK_ROOT}/contracts/
COPY services/ ${LAMBDA_TASK_ROOT}/services/

# Puerto local expuesto al adaptador
EXPOSE 8080

# Anular el entrypoint por defecto de Lambda RIC para que corra el servidor web Uvicorn
ENTRYPOINT ["python", "-m", "uvicorn"]
CMD ["api.main:app", "--host", "0.0.0.0", "--port", "8080"]
