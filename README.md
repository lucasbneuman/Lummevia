# Lummevia OS

Bootstrap tecnico del runtime inicial del orquestador.

En esta etapa el repositorio ya integra un primer runtime real basado en LangGraph para ejecutar de forma simulada el workflow principal de desarrollo. Todavia no incluye agentes con LLMs reales, prompts reales, providers IA reales ni logica de negocio. Si incluye una instrumentacion inicial real hacia Phoenix para observar `WorkflowRun`, steps, eventos runtime y el loop `DEV ↔ QA`.

## Stack local

- `orchestrator-api`: API FastAPI minima con endpoints de salud y metadata.
- `postgres`: base de datos del runtime para iteraciones futuras.
- `redis`: cache y coordinacion liviana para el runtime futuro.
- `phoenix`: servicio local de observabilidad para desarrollo, ya conectado al runtime simulado mediante OpenTelemetry.

Phoenix tambiÃ©n puede correr como servicio externo desplegado en Coolify para uso compartido entre entornos, sin mover su instalaciÃ³n a una carpeta aparte de este repositorio.

## Estructura principal

```text
apps/
  orchestrator-api/
    app/
      api/
      core/
      models/
      schemas/
      services/
    main.py
infra/
  compose/
    docker-compose.yml
  docker/
    orchestrator-api.Dockerfile
docs/
packages/
  agents/
    lummevia_agents/
      __init__.py
      base.py
      schemas.py
      exceptions.py
      pm.py
      po.py
      dev.py
      qa.py
      qc.py
  model-router/
    model_router/
      __init__.py
      router.py
      registry.py
      schemas.py
      exceptions.py
  core/
    lummevia_core/
      workflow.py
      workflow_steps.py
  runtime/
    lummevia_runtime/
      __init__.py
      state.py
      events.py
      transitions.py
      graph.py
      exceptions.py
      nodes/
tests/
```

## Model Router

`model-router` es el primer skeleton real para desacoplar roles, providers y modelos del resto del runtime.

En esta etapa:

- resuelve configuraciones por `role`
- permite overrides estaticos por `project` y `environment`
- permite overrides completos por rol via environment variables
- no hace llamadas reales a providers
- no ejecuta prompts
- no integra observabilidad ni clientes LLM

### Routing basico

El flujo actual es:

```text
RoutingRequest -> registry estatico -> resolve_model(...) -> RoutingResolution
```

La precedencia de resolucion es:

1. `project + environment`
2. `project`
3. `environment`
4. `default`
5. override final por variable de entorno del rol

### Ejemplo de uso

```python
from model_router import AgentRole, RoutingRequest, resolve_model

resolution = resolve_model(
    RoutingRequest(
        role=AgentRole.PM,
        project="lummevia-os",
        environment="development",
    )
)

print(resolution.model)
```

### Override por variables de entorno

```powershell
$env:MODEL_PM_PROVIDER="OPENAI"
$env:MODEL_PM_NAME="gpt-4.1-mini"
$env:MODEL_PM_TEMPERATURE="0.35"
$env:MODEL_PM_MAX_TOKENS="8192"
```

Variables soportadas por rol:

- `MODEL_PM_PROVIDER`, `MODEL_PM_NAME`, `MODEL_PM_TEMPERATURE`, `MODEL_PM_MAX_TOKENS`
- `MODEL_PO_PROVIDER`, `MODEL_PO_NAME`, `MODEL_PO_TEMPERATURE`, `MODEL_PO_MAX_TOKENS`
- `MODEL_DEV_PROVIDER`, `MODEL_DEV_NAME`, `MODEL_DEV_TEMPERATURE`, `MODEL_DEV_MAX_TOKENS`
- `MODEL_QA_PROVIDER`, `MODEL_QA_NAME`, `MODEL_QA_TEMPERATURE`, `MODEL_QA_MAX_TOKENS`
- `MODEL_QC_PROVIDER`, `MODEL_QC_NAME`, `MODEL_QC_TEMPERATURE`, `MODEL_QC_MAX_TOKENS`

Comportamiento:

- si se setea solo `MODEL_<ROL>_NAME`, cambia solo el nombre del modelo
- `MODEL_<ROL>_PROVIDER` debe coincidir con `OPENAI`, `OPENROUTER`, `ANTHROPIC` o `LOCAL`
- `MODEL_<ROL>_TEMPERATURE` se parsea como `float`
- `MODEL_<ROL>_MAX_TOKENS` se parsea como `int`
- los errores de parseo fallan de forma explicita

Compatibilidad legacy:

- `MODEL_PM`
- `MODEL_DEV`

Estas variables legacy siguen funcionando, pero solo sobrescriben `model` y deben considerarse deprecadas frente a `MODEL_<ROL>_NAME`.

### Ejemplo por rol

```powershell
$env:MODEL_PM_PROVIDER="OPENAI"
$env:MODEL_PM_NAME="gpt-4.1-mini"
$env:MODEL_PM_TEMPERATURE="0.2"
$env:MODEL_PM_MAX_TOKENS="8192"

$env:MODEL_DEV_NAME="deepseek/deepseek-coder"
$env:MODEL_DEV_TEMPERATURE="0.1"
$env:MODEL_DEV_MAX_TOKENS="4096"
```

## Core artifacts

`packages/core/lummevia_core/` define contratos de datos compartidos para los artefactos principales del flujo:

- `BusinessBrief`
- `ExecutionPackage`
- `ImplementationPackage`
- `ValidationPackage`
- `QualityApproval`

Tambien expone enums comunes para prioridad, estados de validacion y roles usados por estos contratos.

En esta etapa el paquete solo modela y valida datos con Pydantic. Todavia no incluye integracion real con YouTrack, endpoints FastAPI, base de datos ni workflows ejecutables.

Tambien incluye un workflow skeleton contractual en `workflow.py` y `workflow_steps.py` para representar el flujo principal del desarrollo sin ejecutar pasos reales.
Tambien incluye un skeleton contractual de `WorkflowRun` y `WorkflowRunEvent` para modelar futuras ejecuciones sin ejecutarlas ni persistirlas.

## Agents

`packages/agents/lummevia_agents/` contiene skeletons contractuales para los roles `PM`, `PO`, `DEV`, `QA` y `QC`.

En esta etapa:

- cada agente expone `name` y `role`
- cada agente puede resolver configuracion de modelo via `model-router`
- cada agente puede ejecutar prompts contra una abstraccion de provider via `execute_model(...)`
- cada `run(...)` falla de forma explicita como placeholder
- no ejecutan el workflow real por si mismos
- no hay llamadas reales a modelos ni integraciones externas

### Model Execution Abstraction

La primera capa de ejecucion de modelos vive en `packages/agents/lummevia_agents/execution.py`.

Incluye:

- `ModelExecutionRequest`
- `ModelExecutionResult`
- `ModelProvider`
- `ModelExecutionError`
- `ModelExecutor`
- `FakeModelProvider`

El flujo actual es:

```text
BaseAgent.execute_model(...)
-> ModelExecutor
-> model-router
-> FakeModelProvider
-> ModelExecutionResult
```

En esta etapa:

- `ModelExecutor` resuelve `provider` y `model` via `model-router`
- `FakeModelProvider` devuelve outputs deterministicos utiles para tests
- `ModelExecutionResult.metadata` deja preparada metadata para Phoenix:
  - `role`
  - `project`
  - `provider`
  - `model`
  - `latency_ms`
  - `fallback_used`
- no existen providers reales conectados
- no hay llamadas HTTP reales
- no hay prompts productivos reales

## Workflow skeleton

El workflow principal del sistema ya queda modelado como contrato de datos con pasos ordenados, `responsible_role`, `consumes`, `produces` y `description`.
El paso `founder_input` usa el rol contractual `FOUNDER` en `core` para representar origen humano, sin introducir `FounderAgent` ni routing de modelo.

En esta etapa:

- el contrato del workflow sigue siendo serializable e independiente del runtime
- `github_pr` sigue existiendo como paso contractual del flujo documentado
- no se ejecutan agentes reales ni prompts
- la coordinacion automatizada vive en el runtime LangGraph separado

## Runtime LangGraph

`packages/runtime/lummevia_runtime/` implementa el primer runtime ejecutable del sistema usando `LangGraph` como:

- runtime
- state machine
- execution orchestrator

No actua como:

- memoria operacional
- observabilidad
- repositorio tecnico
- capa de integracion externa

El runtime actual:

- crea `WorkflowRun` reales en memoria
- mantiene `RuntimeState` serializable
- genera `WorkflowRunEvent` reales
- ejecuta pasos simulados para `FOUNDER -> PM -> PO -> DEV -> QA -> github_pr -> QC -> PO final`
- representa explicitamente la publicacion simulada de `github_pr`
- representa explicitamente el loop `DEV ↔ QA`
- deja lista la arquitectura para checkpoints futuros

Limitaciones actuales:

- no hay llamadas reales a modelos
- no hay integracion real con YouTrack
- no hay integracion real con GitHub
- no hay prompts reales instrumentados
- no hay tokens ni costos reales instrumentados
- no hay persistencia en Postgres
- toda la ejecucion es simulada y en memoria

## Integrations

`packages/integrations/lummevia_integrations/` contiene integraciones externas desacopladas del runtime.

Las integraciones disponibles son:

- `youtrack`
- `github`
- `phoenix`

Hoy expone:

- schemas de contrato
- excepciones propias
- un adaptador real minimo para Phoenix
- clientes placeholder para YouTrack y GitHub

La integracion de `phoenix` define contratos para trazas, spans y evaluaciones, y agrega un adaptador real minimo basado en OpenTelemetry para exportar trazas del runtime simulado a `PHOENIX_BASE_URL`.

En `PhoenixTracePayload`, el contrato minimo ya tipa `fallback_used`, `latency_ms`, `estimated_cost` y `error`, mientras `metadata` sigue abierta para contexto adicional.

La instrumentacion actual de Phoenix:

- crea una trace por `WorkflowRun`
- crea spans por step del workflow
- registra metadata de `run_id`, `workflow`, `project`, `issue_id`, `environment`, `current_step`, `status` y `loop_count`
- agrega eventos runtime por step y refleja el loop `DEV ↔ QA`
- registra errores de runtime e instrumentacion sin romper el workflow

Todavia no hace llamadas reales a YouTrack o GitHub, no envia prompts reales, no instrumenta tokens ni costos reales y no conecta providers LLM.

## Configuracion

1. Crear el archivo de entorno local:

```powershell
Copy-Item .env.example .env
```

2. Configurar las variables minimas del runtime en `.env`.

Variables base:

- `APP_ENV`, `APP_PORT`, `APP_NAME`, `APP_VERSION`
- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- `REDIS_HOST`, `REDIS_PORT`
- `PHOENIX_ENABLED`, `PHOENIX_HOST`, `PHOENIX_PORT`, `PHOENIX_BASE_URL`

ConvenciÃ³n recomendada para Phoenix:

- desarrollo local con `docker compose`: `PHOENIX_HOST=phoenix`, `PHOENIX_PORT=6006`, `PHOENIX_BASE_URL=http://phoenix:6006`
- Phoenix externo en Coolify: usar la URL publicada en `PHOENIX_BASE_URL`, por ejemplo `https://phoenix.example.com`

`PHOENIX_BASE_URL` debe considerarse la referencia principal para la conexiÃ³n. `PHOENIX_HOST` y `PHOENIX_PORT` mantienen una configuraciÃ³n explÃ­cita y consistente para el caso local y para metadata operativa en despliegues externos.

`PHOENIX_ENABLED=false` desactiva la exportacion de trazas hacia Phoenix sin alterar la ejecucion del workflow.

Variables opcionales por ahora:

- `YOUTRACK_BASE_URL`, `YOUTRACK_TOKEN`
- `GITHUB_TOKEN`, `GITHUB_ORG`

YouTrack y GitHub todavia no son obligatorios para levantar `orchestrator-api`. Sus tokens y URLs pueden quedar vacios mientras las integraciones sigan siendo skeletons contractuales.

3. Levantar el stack local de desarrollo:

```powershell
docker compose -f infra/compose/docker-compose.yml up --build
```

Ese stack levanta Phoenix local dentro de Docker Compose para desarrollo. Para un entorno compartido con Phoenix desplegado en Coolify, la API debe configurarse con `PHOENIX_BASE_URL` apuntando al servicio externo y no necesita otra instalaciÃ³n de Phoenix dentro de este repositorio.

## Endpoints disponibles

- `GET /health`
- `GET /info`
- `GET /model-router/roles`
- `POST /model-router/resolve`
- `POST /runtime/development/run`
- `GET /runtime/development/run/{run_id}`
- `GET /workflows/development`
- `GET /workflows/development/steps`
- `GET /workflows/development/steps/{step_name}`
- `POST /workflow-runs/mock`

Los endpoints de `model-router` son de diagnostico. Sirven para inspeccionar que configuracion de modelo resolveria el runtime por rol, proyecto y entorno.

No ejecutan prompts, no llaman providers reales y no disparan agentes.

Los endpoints de `workflows` tambien son de diagnostico. Sirven para inspeccionar la definicion contractual del workflow de desarrollo expuesta desde `core`.

No ejecutan un workflow real y no disparan agentes. La ejecucion simulada vive en los endpoints de `runtime`.

Los endpoints de `runtime` ejecutan un workflow de desarrollo simulado con LangGraph y mantienen el estado resultante en memoria del proceso API.

- `POST /runtime/development/run` crea y ejecuta un `WorkflowRun` real
- `GET /runtime/development/run/{run_id}` recupera el estado final serializado desde el registry en memoria

Estos endpoints:

- no llaman LLMs reales
- no conectan YouTrack ni GitHub reales
- si conectan Phoenix para observabilidad del runtime cuando `PHOENIX_ENABLED=true`
- no persisten datos
- si registran estado, artefactos y eventos del runtime simulado

El endpoint `POST /workflow-runs/mock` tambien es solo de diagnostico. Devuelve un `WorkflowRun` serializado en memoria como respuesta de ejemplo.

No ejecuta workflows reales, no persiste estado, no usa base de datos y no conecta integraciones externas.

Por defecto la API queda disponible en [http://localhost:8000](http://localhost:8000) y Phoenix local en [http://localhost:6006](http://localhost:6006).

## Comandos basicos

```powershell
docker compose -f infra/compose/docker-compose.yml up --build
docker compose -f infra/compose/docker-compose.yml down
docker compose -f infra/compose/docker-compose.yml ps
```

## Tests

Para correr los tests localmente, usa un entorno con Python y las dependencias instaladas desde `requirements.txt`:

```powershell
pip install -r requirements.txt
pytest
```

Para correr los tests dentro de Docker:

```powershell
docker compose -f infra/compose/docker-compose.yml build orchestrator-api
docker compose -f infra/compose/docker-compose.yml run --rm orchestrator-api pytest /app/tests
```
