# Lummevia OS

Bootstrap tecnico minimo del runtime inicial del orquestador.

En esta etapa el repositorio solo prepara la base para iterar sobre el runtime. No incluye LangGraph, agentes reales, integraciones reales, observabilidad instrumentada ni logica de negocio.

## Stack local

- `orchestrator-api`: API FastAPI minima con endpoints de salud y metadata.
- `postgres`: base de datos del runtime para iteraciones futuras.
- `redis`: cache y coordinacion liviana para el runtime futuro.
- `phoenix`: servicio local de observabilidad listo para futuras integraciones.

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
- cada `run(...)` falla de forma explicita como placeholder
- no existen workflows reales
- no existe orquestacion con LangGraph
- no hay llamadas reales a modelos ni integraciones externas

## Workflow skeleton

El workflow principal del sistema ya queda modelado como contrato de datos con pasos ordenados, `responsible_role`, `consumes`, `produces` y `description`.
El paso `founder_input` usa el rol contractual `FOUNDER` en `core` para representar origen humano, sin introducir `FounderAgent` ni routing de modelo.

En esta etapa:

- no hay runtime de LangGraph
- no se ejecutan agentes reales
- no existe coordinacion automatizada entre pasos
- el objetivo es solo representar el flujo como definicion serializable

## Integrations

`packages/integrations/lummevia_integrations/` contiene skeletons de integraciones externas para el runtime.

Las integraciones disponibles son:

- `youtrack`
- `github`
- `phoenix`

Cada skeleton hoy expone:

- schemas de contrato
- excepciones propias
- un cliente placeholder

El skeleton de `phoenix` define contratos para trazas, spans y evaluaciones, junto con un cliente placeholder para la futura capa de observabilidad.

En `PhoenixTracePayload`, el contrato minimo ya tipa `fallback_used`, `latency_ms`, `estimated_cost` y `error`, mientras `metadata` sigue abierta para contexto adicional.

Todavia no hacen llamadas reales a YouTrack, GitHub o Phoenix, no usan credenciales reales, no implementan clientes HTTP externos y no agregan instrumentacion real ni SDKs externos.

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
- `PHOENIX_HOST`, `PHOENIX_PORT`, `PHOENIX_BASE_URL`

Variables opcionales por ahora:

- `YOUTRACK_BASE_URL`, `YOUTRACK_TOKEN`
- `GITHUB_TOKEN`, `GITHUB_ORG`

YouTrack y GitHub todavia no son obligatorios para levantar `orchestrator-api`. Sus tokens y URLs pueden quedar vacios mientras las integraciones sigan siendo skeletons contractuales.

3. Levantar el stack:

```powershell
docker compose -f infra/compose/docker-compose.yml up --build
```

## Endpoints disponibles

- `GET /health`
- `GET /info`
- `GET /model-router/roles`
- `POST /model-router/resolve`
- `GET /workflows/development`
- `GET /workflows/development/steps`
- `GET /workflows/development/steps/{step_name}`
- `POST /workflow-runs/mock`

Los endpoints de `model-router` son de diagnostico. Sirven para inspeccionar que configuracion de modelo resolveria el runtime por rol, proyecto y entorno.

No ejecutan prompts, no llaman providers reales y no disparan agentes.

Los endpoints de `workflows` tambien son de diagnostico. Sirven para inspeccionar la definicion contractual del workflow de desarrollo expuesta desde `core`.

No ejecutan un workflow real, no mantienen estado runtime, no usan LangGraph y no disparan agentes.

El endpoint `POST /workflow-runs/mock` tambien es solo de diagnostico. Devuelve un `WorkflowRun` serializado en memoria como respuesta de ejemplo.

No ejecuta workflows reales, no persiste estado, no usa base de datos y no conecta integraciones externas.

Por defecto la API queda disponible en [http://localhost:8000](http://localhost:8000) y Phoenix en [http://localhost:6006](http://localhost:6006).

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
