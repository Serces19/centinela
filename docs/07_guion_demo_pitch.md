# 07 · Guion de Demo Cronometrada (5 min) y Pitch de Negocio (3 min)

**Proyecto:** Centinela · Sistema Serverless de Agentes de IA de Vigilancia Operacional y Financiera  
**Organización:** Distribuidora Andina S.A.S. (Hackatón By Paseo)  
**URLs en Vivo:**
- **Frontend Web (AWS Amplify):** `https://main.d1y5ytuqvgx3m2.amplifyapp.com`
- **Backend API (AWS Lambda Function URL):** `https://kshttlmqbtzbjc5a73m5v6rfre0qimbv.lambda-url.us-east-1.on.aws/`
- **Dashboard CloudWatch:** `Centinela-Operaciones` en `us-east-1`

---

## 1. Guion de Demostración en Vivo (5 Minutos Exactos)

| Minuto | Acción en Pantalla | Qué Mostrar en la UI | Qué Decir al Jurado (Voz) |
|---|---|---|---|
| **0:00 - 0:40** | **Inicio en Corte Limpio** | Topbar con corte `18 Jun 2026` (badge verde *"Corte Limpio"*). Bandeja con 0 alertas de crisis activa. | *"Buenos días jurado. Distribuidora Andina factura 23.500 millones de pesos al año, pero pierde cientos de millones en fugas operacionales invisibles. Hoy les presentamos a Centinela. Empezamos en nuestro corte inicial limpio: 18 de junio de 2026. La operación transcurre en parámetros normales."* |
| **0:40 - 1:30** | **Simulación Temporal y Detección Temprana (S1)** | Clic en el Topbar para avanzar fecha a `2026-08-15` (o botón `+7 días`). La bandeja actualiza en 3 segundos y resalta la alerta **CRÍTICA**: `costo|PR08` (Proveedor Alimentos del Valle S.A.). Banner Hero: **$23.558.346 COP en riesgo**. | *"Avanzamos el reloj al 15 de agosto de 2026. Inmediatamente el Agente Vigía detecta que el proveedor PR08 incrementó sus costos más del 5%. En menos de 30 segundos, el director comercial ve el impacto exacto en pesos: 23 millones y medio de pesos en riesgo mensual antes de que la gerencia se entere por los balances a fin de mes."* |
| **1:30 - 2:15** | **Detalle en 3 Niveles y Trazabilidad** | Clic en *"Examinar Causa"*:<br>• **Nivel 1:** Resumen ejecutivo y propuesta.<br>• **Nivel 2:** Causa con cifras trazables (`Q-xxxx`) y cita normativa a `OPE-POL-007 §4`.<br>• **Nivel 3 ("Cómo llegué aquí"):** SQL DuckDB ejecutado y hash SHA-256. | *"Centinela no inventa números. En el Nivel 2 vemos las 4 referencias afectadas (P0001, P0006, P0011, P0016), citando la política oficial OPE-POL-007 sección 4. Y en 'Cómo llegué aquí' desplegamos la consulta SQL exacta sobre la capa semántica DuckDB con su hash criptográfico. Cero alucinaciones."* |
| **2:15 - 3:00** | **Chat Anclado con Streaming SSE** | Abrir panel de chat lateral y enviar: *"¿Qué otros SKU le compramos a este proveedor?"*. Ver streaming token a token en tiempo real y etiquetas interactivas. | *"El analista de negocio puede interrogar a Centinela en lenguaje natural mediante Server-Sent Events en tiempo real. La IA responde anclada a los datos reales de compras de la empresa, citando el costo en fracciones de centavo de dólar."* |
| **3:00 - 3:40** | **Aprobación Humana (HITL) y Bitácora SHA-256** | Usar el **Active Persona Switcher** en la esquina inferior (elegir *David Osorio - Líder de Abastecimiento*). Clic en **Aprobar Propuesta**. Ver borrador sandbox (`sandbox://correos/...') y abrir visor de bitácora con sello verde verificado. | *"El sistema nunca ejecuta a ciegas. Nuestro Active Persona Switcher registra que David Osorio, líder de abastecimiento, aprueba la acción con Idempotency-Key. Se genera el borrador de orden de compra y correo en sandbox y la bitácora inmutable encadena un hash SHA-256 verificable matemáticamente."* |
| **3:40 - 4:20** | **Cierre del Año (2026-09-30) y Priorización por Capital** | Avanzar el reloj a `2026-09-30`. Se despliegan los 5 escenarios (S1 Costo, S2 Cartera El Sol, S3 Quiebre Inventario Itagüí, S4 Descuentos Gómez, S5 Cliente Inactivo). | *"Llegamos al cierre del año: 30 de septiembre. Centinela detecta los 5 escenarios sembrados, priorizándolos de mayor a menor dinero en riesgo. En 30 segundos, el comité directivo sabe exactamente a qué cliente cobrar, qué orden expeditar y qué descuento frenar."* |
| **4:20 - 4:45** | **Prueba de Fuego de Ciberseguridad (EJ-03)** | Mostrar prueba del Bedrock Guardrail (`zuonkeflxh8f`) con política adulterada o inyección de prompt. | *"Si un atacante inyecta instrucciones maliciosas en un PDF de políticas para autorizar descuentos ilegales, Bedrock Guardrails y nuestra capa de defensa en profundidad neutralizan el ataque y sellan la alerta de seguridad en CloudWatch sin alterar el criterio financiero."* |
| **4:45 - 5:00** | **Observabilidad CloudWatch y ROI** | Mostrar Dashboard `Centinela-Operaciones` en CloudWatch y Panel de Costo en la UI ($0.04 USD por ciclo completo vs. $23.5 M protegidos). | *"Con un costo operativo de menos de 4 centavos de dólar por alerta en AWS Lambda serverless y Bedrock Haiku, protegemos más de 115 millones de pesos en riesgo. Eso es un ROI de más de 10.000 a 1. Muchas gracias."* |

---

## 2. Pitch de Negocio (3 Minutos)

### Lámina 1: El Dolor Invisible (0:00 - 0:45)
- **El Problema:** Las empresas de distribución masiva como Distribuidora Andina operan con márgenes del 15% al 25% sobre miles de transacciones diarias. La mayoría de pérdidas no ocurren por quiebras catastróficas, sino por **fugas silenciosas**:
  - Proveedores que suben precios sin aviso (+5% = 23 millones en pérdida mensual).
  - Vendedores que otorgan descuentos desmedidos a fin de mes.
  - Cartera que pasa de 30 a 60 días sin que nadie llame.
  - Clientes fieles que reducen sus pedidos gradualmente hasta abandonar.
- **La Realidad Actual:** Los informes de BI llegan semanas tarde, cuando el dinero ya se perdió.

### Lámina 2: La Solución Centinela (0:45 - 1:45)
- **Vigilancia Continua Serverless:** Agentes deterministas sobre DuckDB y Bedrock que vigilan los datos día a día sin descanso.
- **Diferenciales Clave:**
  1. **Regla de Oro:** El LLM razona y cita normas; **el código determinista calcula los pesos**. Cero cifras alucinadas.
  2. **Human-in-the-Loop:** Las propuestas llegan masticadas a la bandeja de quien tiene que decidir (comercial, cartera, compras) con botones de Aprobar, Editar o Rechazar.
  3. **Auditoría Criptográfica SHA-256:** Cada recomendación, decisión y borrador queda sellado en una bitácora inmutable a prueba de fraudes y con cumplimiento de la Ley 1581 de protección de datos.

### Lámina 3: Economía y Modelo de Negocio (1:45 - 2:30)
- **Costo Marginal Serverless:** Arquitectura 100% serverless en AWS (Lambda Web Adapter, DynamoDB on-demand, Bedrock Claude Haiku 4.5).
  - Costo de infraestructura en reposo: **$0 USD/mes**.
  - Costo por alerta analizada: **$0.02 a $0.04 USD**.
  - Presupuesto mensual de operación: **< $20 USD/mes**.
- **Impacto Financiero:** Detección de $115 millones de pesos en riesgo tan solo en los escenarios analizados. Un ROI de 10.000x sobre el costo de cómputo en la nube.

### Lámina 4: Hoja de Ruta y Escalabilidad (2:30 - 3:00)
- **Fase 1 (MVP Actual):** Monitoreo sobre DuckDB/Postgres, aprobación humana interactiva y borrador en Sandbox.
- **Fase 2 (Próximos 6 meses):** Conectores directos a ERPs líderes en Colombia (SAP Business One, SIIGO, World Office).
- **Fase 3 (Autonomía Gradual):** Conforme el historial de aprobaciones en la bitácora demuestre un 99% de acierto humano en ciertas categorías (ej. llamadas preventivas de cartera), el sistema asciende automáticamente su autonomía de *Propone* a *Ejecuta*.

---

## 3. Matriz de Preguntas Difíciles del Jurado y Respuestas

1. **¿Qué pasa si el modelo de lenguaje se equivoca o alucina una cifra?**
   - *Respuesta:* Arquitecturalmente es imposible que alucine una cifra económica. Las cifras provienen exclusivamente de consultas SQL validadas contra DuckDB y viajan encapsuladas en contratos inmutables de Pydantic (`CifraTrazable` con `consulta_id`). Si el LLM intenta escribir un número libre en el texto, el validador de Pydantic lo rechaza y fuerza una reescritura.
2. **¿Cómo garantizan el cumplimiento de la Ley 1581 (Habeas Data / Privacidad)?**
   - *Respuesta:* Aplicamos privacidad por diseño. Las herramientas y agentes de IA solo procesan identificadores técnicos seudonimizados (`C0496`, `V03`, `PR08`). Los nombres reales se resuelven exclusivamente en el cliente frontend para la vista humana. Adicionalmente, Bedrock Guardrails anonimiza correos, teléfonos y direcciones.
3. **¿Por qué usaron DuckDB en memoria en vez de consultar una base de datos Postgres tradicional?**
   - *Respuesta:* Por latencia y costo. DuckDB corre in-process en la memoria de la Lambda, ejecutando agregaciones analíticas complejas sobre 270.000 filas en menos de 15 milisegundos sin latencia de red ni costos de instancias RDS permanentes.
4. **¿Por qué no usaron Langfuse o LangSmith?**
   - *Respuesta:* Cumplimos con el principio de simplicidad y arquitectura nativa de AWS. Desarrollamos nuestra propia observabilidad con CloudWatch Embedded Metric Format (EMF) a costo cero de API, trazas persistidas en DynamoDB y dashboard operacional en tiempo real, evitando dependencias externas que requieren servidores dedicados.
