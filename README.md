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
  capabilities/
    lummevia_capabilities/
      __init__.py
      schemas.py
      registry.py
      allocator.py
      policies.py
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
  conversations/
    lummevia_conversations/
      __init__.py
      schemas.py
      registry.py
  memory/
    lummevia_memory/
      __init__.py
      schemas.py
      registry.py
  evaluations/
    lummevia_evaluations/
      __init__.py
      regression.py
      schemas.py
      scoring.py
      registry.py
  reviews/
    lummevia_reviews/
      __init__.py
      schemas.py
      registry.py
  sessions/
    lummevia_sessions/
      __init__.py
      schemas.py
      registry.py
  timeline/
    lummevia_timeline/
      __init__.py
      schemas.py
      registry.py
      builder.py
  datasets/
    lummevia_datasets/
      __init__.py
      schemas.py
      registry.py
      fixtures/
        pm_business_brief_dataset.json
  kilo-adapter/
    lummevia_kilo/
      client.py
      schemas.py
      execution.py
      exceptions.py
      modes.py
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
- `MODEL_<ROL>_PROVIDER` debe coincidir con `DEEPSEEK`, `OPENAI`, `OPENROUTER`, `ANTHROPIC` o `LOCAL`
- `MODEL_<ROL>_TEMPERATURE` se parsea como `float`
- `MODEL_<ROL>_MAX_TOKENS` se parsea como `int`
- los errores de parseo fallan de forma explicita

Compatibilidad legacy:

- `MODEL_PM`
- `MODEL_DEV`

Estas variables legacy siguen funcionando, pero solo sobrescriben `model` y deben considerarse deprecadas frente a `MODEL_<ROL>_NAME`.

### Ejemplo por rol

```powershell
$env:MODEL_PM_PROVIDER="DEEPSEEK"
$env:MODEL_PM_NAME="deepseek-v4-strong-placeholder"
$env:MODEL_PM_TEMPERATURE="0.2"
$env:MODEL_PM_MAX_TOKENS="8192"

$env:MODEL_DEV_PROVIDER="DEEPSEEK"
$env:MODEL_DEV_NAME="deepseek-v4-lite-placeholder"
$env:MODEL_DEV_TEMPERATURE="0.1"
$env:MODEL_DEV_MAX_TOKENS="4096"
```

## Core artifacts

`packages/core/lummevia_core/` define contratos de datos compartidos para los artefactos principales del flujo:

- `BusinessBrief`
- `ExecutionPackage`
- `TaskPlan`
- `TaskPackage`
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
- cada agente de runtime puede producir su artefacto fake via `produce_artifact(...)` o `execute_prompt_pipeline(...)`
- cada `run(...)` falla de forma explicita como placeholder
- no ejecutan el workflow real por si mismos
- el runtime principal sigue usando `FakeModelProvider`
- solo existe un dry-run controlado para `PM` que puede usar DeepSeek API directa cuando se habilita
- `PO`, `DEV`, `QA` y `QC` siguen en fake
- no hay integraciones externas productivas

## Founder conversation memory

`packages/conversations/lummevia_conversations/` agrega la primera capa stateful minima para la iteracion estrategica `Founder ↔ PM` antes de aprobar el `BusinessBrief`.

Alcance actual:

- define contratos para `ConversationMessage`, `ConversationThread`, `ConversationStatus` y `AuthorType`
- mantiene un `ConversationRegistry` en memoria con `create_thread`, `add_message`, `get_thread`, `list_threads` y `close_thread`
- permite un ciclo simple `Founder -> PM -> Founder feedback` dentro del runtime
- asocia el `BusinessBrief` aprobado con `thread_id` via metadata runtime
- expone endpoints `GET /conversations`, `GET /conversations/{thread_id}` y `POST /conversations/{thread_id}/message`
- guarda solo `thread_id` en persistence runtime cuando esta habilitada
- agrega metadata de conversacion a Phoenix: `thread_id`, `conversation_status`, `iteration_count`, `message_count`

Lifecycle actual del thread:

```text
ACTIVE -> APPROVED -> CLOSED
```

Roadmap deliberadamente fuera de alcance en esta etapa:

- chat UI
- websocket realtime
- auth real
- vector DB o embeddings
- memoria semantica avanzada
- RAG real
- agentes conversacionales autonomos
- colaboracion multi-user
- integraciones Slack o Discord

## Project Memory

`packages/memory/lummevia_memory/` agrega la primera capa de project memory compartida entre workflows, conversaciones, reviews y task sessions sin introducir todavia embeddings ni almacenamiento vectorial.

Incluye:

- `ProjectMemoryRecord` como contrato minimo para memoria organizacional del proyecto
- `MemoryCategory` con `BUSINESS_DECISION`, `TASK_LEARNING`, `QA_ISSUE`, `IMPLEMENTATION_NOTE`, `PROMPT_LEARNING` y `REVIEW_DECISION`
- `MemorySourceType` con `CONVERSATION`, `SESSION`, `REVIEW`, `WORKFLOW` y `SYSTEM`
- `ProjectMemoryRegistry` en memoria con `add_memory()`, `get_memory()`, `list_project_memories()`, `search_by_tag()` y `search_by_category()`
- `get_project_context(project)` para devolver decisiones recientes, issues de QA, prompt learnings y reviews recientes ordenados por fecha

Integracion actual:

- founder conversation crea `BUSINESS_DECISION`
- QA fail crea `QA_ISSUE`
- prompt promotion crea `PROMPT_LEARNING`
- reviews completadas crean `REVIEW_DECISION`
- task session completion crea `TASK_LEARNING`
- el `PM` consume `project_context` resumido dentro del prompt pipeline
- Phoenix recibe metadata de `memory_records_created`, `memory_categories` y `project_memory_count`

Alcance deliberado en esta etapa:

- no embeddings
- no vector DB
- no semantic search
- no RAG real
- no memory agents autonomos
- no summarization IA automatica
- no persistencia durable de memory

Roadmap futuro:

- persistencia durable de `ProjectMemoryRecord`
- retrieval hibrido con filtros y recencia
- embeddings y semantic search cuando la capa contractual este estable
- RAG real sobre memoria organizacional y tecnica cuando exista storage durable

### Prompt Pipeline

La primera capa de pipeline de prompts vive en `packages/agents/lummevia_agents/prompts/`.

Incluye:

- `PromptTemplate` para declarar identidad estable del prompt con `template_id`, `version`, `created_at`, `tags`, rol, artefacto destino, system prompt e instrucciones base
- `PromptRegistry` para resolver templates por `role + target_artifact`, version explicita o baseline activa
- `ContextBuilder` para armar contexto minimo desde `project`, `issue_id`, `role`, `available_artifacts` y `metadata`
- `PromptPipeline` para renderizar prompt final, calcular `prompt_hash` deterministico con `sha256`, ejecutar `ModelExecutor` y devolver un resultado estructurado con metadata versionada
- el flujo del `PO` ahora se decompone en `ExecutionPackage -> TaskPlan -> TaskPackage`

Los templates iniciales cubren:

- `PM -> BusinessBrief`
- `PO -> ExecutionPackage`
- `PO -> TaskPlan`
- `PO -> TaskPackage`
- `DEV -> ImplementationPackage`
- `QA -> ValidationPackage`
- `QC -> QualityApproval`

Convencion inicial de versionado:

- `pm_business_brief:v1`
- `po_execution_package:v1`
- `po_task_plan:v1`
- `po_task_package:v1`
- `dev_implementation_package:v1`
- `qa_validation_package:v1`
- `qc_quality_approval:v1`

Flujo actual:

```text
PromptExecutionRequest
-> PromptRegistry
-> ContextBuilder
-> PromptTemplate.render(...)
-> sha256(prompt renderizado)
-> ModelExecutor
-> fake structured output validado con artifacts de core
```

Resolucion activa actual:

- si el caller envia `template_version`, se usa esa version
- si no se envia version y existe baseline promovida para `template_id`, se usa la version activa
- si no existe baseline, se usa la ultima version registrada para ese template

Para el `PO`, el fake pipeline ahora puede producir:

- un `TaskPlan` valido
- multiples `TaskPackages` validos
- prompts pequenos que Kilo CLI podra consumir por iteracion

Todavia es una simulacion:

- sigue usando `FakeModelProvider`
- no hay parsing real de LLM
- no hay integracion real con Kilo CLI
- no se crean tickets reales

### Prompt Evaluation Framework

La primera capa de evaluacion de prompts vive en `packages/evaluations/lummevia_evaluations/`.

Incluye:

- `PromptEvaluation` como contrato minimo de evaluacion
- `EvaluationStatus` con `PENDING`, `PASSED`, `FAILED` y `NEEDS_REVIEW`
- `PromptEvaluationRegistry` en memoria para registrar evaluaciones sin DB
- `PromptBaseline` para guardar la baseline activa por `template_id`
- `PromptPromotionResult` y `PromotionStatus` para formalizar promociones
- `PromptBaselineRegistry` en memoria para comparar candidato vs baseline y registrar la version activa
- `score_prompt_execution(...)` como evaluator fake y deterministico
- metadata contractual para `review_required` y `review_id` sobre promociones

La evaluacion fake actual revisa:

- longitud minima del prompt renderizado
- presencia de secciones esperadas por template
- validez del `structured_output`
- penalizacion suave cuando `fallback_used=true`

En esta etapa:

- no hay benchmarking complejo
- no hay scoring automatico con otro LLM
- no hay datasets masivos
- no hay UI de evaluacion humana
- no hay persistencia durable de evaluaciones
- no hay approval UI
- no hay persistencia DB de baselines
- no hay evaluadores IA avanzados

### Human Review Layer

La primera capa contractual de revision/aprobacion humana vive en `packages/reviews/lummevia_reviews/`.

Incluye:

- `HumanReview` como contrato minimo para revisiones humanas
- `ReviewDecision` con `APPROVED`, `REJECTED` y `NEEDS_CHANGES`
- `ReviewStatus` con `PENDING`, `IN_REVIEW` y `COMPLETED`
- `ReviewType` con `PROMPT_PROMOTION`, `BUSINESS_BRIEF`, `TASK_PLAN`, `QA_VALIDATION` y `QC_APPROVAL`
- `HumanReviewRegistry` en memoria con `create_review()`, `get_review()`, `list_reviews()` y `complete_review()`

Objetivo actual:

- dejar approval gates trazables sin UI ni auth real
- registrar decisiones humanas futuras como contratos explicitos
- permitir endpoints simples para inspeccion y cierre manual de reviews

Fuera de alcance en esta etapa:

- UI real
- auth real
- RBAC completo
- approvals distribuidos
- notificaciones reales
- workflows async complejos

### Task Queue

`packages/queue/lummevia_queue/` agrega la primera capa de queue y orquestacion multi-`TaskPackage` sin introducir workers reales ni paralelismo.

Incluye:

- `TaskQueueItem`
- `TaskQueueStatus` con `QUEUED`, `READY`, `RUNNING`, `BLOCKED`, `COMPLETED`, `FAILED` y `CANCELLED`
- `TaskPriority` con `LOW`, `NORMAL`, `HIGH` y `CRITICAL`
- `TaskQueue`
- `TaskQueueRegistry` en memoria con `create_queue()`, `add_item()`, `get_queue()`, `list_queues()`, `update_item_status()`, `list_ready_items()` y `mark_completed()`
- `TaskQueueScheduler` para detectar `READY`, resolver el siguiente item por prioridad y timestamp, y respetar dependencias sin paralelismo real

Semantica actual:

- `po_task_packages` crea una `TaskQueue` con todos los `TaskPackages` producidos por el `PO`
- el runtime conserva la queue completa en `RuntimeState.metadata.task_queue`
- el scheduler activa solo el primer item `READY` como MVP y lo expone como `current_task_package`
- `qa_validation` marca ese item como `COMPLETED` cuando la validacion pasa
- los dependientes se desbloquean y pasan a `READY`, pero todavia no se ejecutan en la misma corrida

Dependency handling actual:

- cada item puede declarar `dependencies` por `task_id`
- si una dependencia no termino, el item queda `BLOCKED`
- cuando la dependencia termina, el item pasa a `READY`
- la cola sigue siendo in-memory, sin persistence ni scheduling durable

Roadmap inmediato:

- ejecutar mas de un `TaskPackage` por workflow
- introducir resumability y persistence de queue
- agregar workers y orchestration real cuando la semantica de contratos este estable

Fuera de alcance deliberado por ahora:

- Celery, RQ, Temporal o Kafka
- workers distribuidos
- paralelismo real
- subprocess Kilo real
- scheduling persistente
- locking distribuido
- git real o multiples PRs reales

### Capabilities y Resource Allocation

`packages/capabilities/lummevia_capabilities/` agrega la primera capa de capabilities, capacity registry y allocation policy para controlar concurrencia antes de permitir ejecucion paralela real.

Incluye:

- `AgentCapability`
- `ModelCapability`
- `ExecutionCapacity`
- `AllocationRequest`
- `AllocationResult`
- `AllocationStatus` con `GRANTED`, `WAITING` y `DENIED`
- `CapabilityRegistry` en memoria con registro de capabilities, capacities y allocations activos
- `CapabilityAllocator` como facade simple para pedir y liberar allocations
- `evaluate_allocation_request(...)` con politica inicial deterministica

Semantica actual:

- cada rol operativo (`PM`, `PO`, `DEV`, `QA`, `QC`) arranca con `max_concurrent_tasks=1`
- cada modelo resuelto por `model-router` arranca con `max_concurrent_requests=1`
- antes de ejecutar un paso Kilo fake, el runtime pide allocation para rol y modelo
- si hay slots disponibles, la request queda `GRANTED`
- si no hay slots, queda `WAITING`
- si el capability no existe o el modo no aplica al rol, queda `DENIED`
- la metadata de allocation se propaga a queue, sessions, requests Kilo y Phoenix
- al finalizar cada ejecucion Kilo fake, el allocation se libera

Guardrails actuales:

- no existe paralelismo real aunque ya exista capacity metadata
- no hay quotas persistidas en DB
- no hay billing real ni rate limit externo real
- no hay autoscaling ni control distribuido
- el sistema sigue ejecutando un solo `TaskQueueItem` activo por queue como MVP

Roadmap posterior de esta capa:

- politicas de costo mas finas por provider y proyecto
- fairness entre colas o proyectos
- quotas persistidas cuando exista storage dedicado
- asignacion real multi-worker cuando el runtime deje de ser single-runner
- integracion futura con providers reales sin romper estos contratos

### Task Execution Sessions

`packages/sessions/lummevia_sessions/` agrega la primera capa operacional para representar el ciclo de trabajo sobre un `TaskPackage` sin abrir todavia una terminal viva ni lanzar workers reales.

Incluye:

- `TaskExecutionSession`
- `SessionStatus` con `CREATED`, `RUNNING`, `WAITING_REVIEW`, `COMPLETED`, `FAILED` y `CANCELLED`
- `SessionEvent`
- `SessionOutput`
- `SessionRegistry` en memoria con `create_session()`, `add_event()`, `add_output()`, `update_status()`, `get_session()` y `list_sessions()`

Lifecycle actual:

```text
CREATED -> RUNNING -> WAITING_REVIEW -> RUNNING -> COMPLETED
```

Integracion actual:

- `po_task_packages` crea la session del `TaskPackage` activo
- `dev_implementation` y `qa_validation` reutilizan la misma session
- la session queda asociada al `TaskPackage` via `task_package.metadata.session_id`
- la session tambien registra `queue_id` y `queue_item_id` cuando proviene de la task queue
- el runtime deja snapshots serializados en `RuntimeState.metadata.sessions`
- los endpoints `GET /sessions` y `GET /sessions/{session_id}` permiten inspeccionarla

Relacion con Kilo:

- cada ejecucion Kilo del `TaskPackage` activo queda asociada al mismo `session_id`
- cada ejecucion agrega `SessionEvent` y `SessionOutput` fake
- `session_attempts` acumula intentos simulados de Kilo durante la vida de la session

Relacion con runtime:

- la session vive en memoria como estado runtime, no como memoria durable de negocio
- persistence DB todavia no existe para sessions; solo se serializa el snapshot dentro del payload del runtime cuando la persistence del workflow esta habilitada
- Phoenix recibe metadata de `session_id`, `session_status`, `session_role`, `session_attempts`, `output_count` y `event_count`
- al cerrar la session, el runtime tambien registra `TASK_LEARNING` dentro de project memory

Fuera de alcance deliberado por ahora:

- terminal streaming
- websocket realtime
- subprocess persistentes
- workers distribuidos
- replay real de ejecucion
- sandboxing real

### Workflow Timelines

`packages/timeline/lummevia_timeline/` agrega la primera capa de timeline historico y replay contractual para workflows sin introducir todavia replay ejecutable real.

Incluye:

- `TimelineEvent`
- `TimelineSourceType` con `WORKFLOW`, `CONVERSATION`, `SESSION`, `REVIEW`, `MEMORY` y `SYSTEM`
- `WorkflowTimeline`
- `TimelineRegistry` en memoria con `create_timeline()`, `add_event()`, `get_timeline()` y `list_timelines()`
- `build_workflow_timeline(...)` para reconstruir una timeline cronologica desde workflow events, conversaciones, sessions, reviews y memory

Integracion actual:

- el runtime sincroniza una `WorkflowTimeline` reconstruida durante la ejecucion
- `founder_pm_conversation` aporta mensajes y estado del thread
- `qa_validation` aporta reviews pendientes/completadas y transiciones de session
- las reviews de founder approval quedan reflejadas como eventos historicos
- project memory y sessions quedan agregadas a la timeline del `workflow_run`
- la queue aporta eventos `QUEUE_CREATED`, `TASK_QUEUED`, `TASK_READY`, `TASK_STARTED` y `TASK_COMPLETED`
- Phoenix recibe `timeline_event_count`, `timeline_sources` y `replay_available=true`
- los endpoints `GET /timelines` y `GET /timelines/{workflow_run_id}` devuelven la timeline reconstruida

Arquitectura de replay actual:

- replay disponible solo como reconstruccion historica de eventos
- no hay replay de ejecucion real
- no hay time travel
- no hay event sourcing completo
- no hay streaming realtime

Roadmap futuro deliberado:

- replay navegable por step y source
- snapshots mas ricos para reconstruccion post-persistencia
- filtros por source type y step
- persistencia durable de timelines
- herramientas de diagnostico y auditoria sobre la historia del workflow

### Prompt Regression Datasets

La primera capa de datasets de regression vive en `packages/datasets/lummevia_datasets/`.

Incluye:

- `PromptDatasetCase` con `case_id`, `template_id`, `input_prompt`, `expected_keywords`, `expected_sections` y `metadata`
- `PromptDataset` con `dataset_id`, `template_id`, `version`, `description` y `cases`
- `DatasetRegistry` para cargar fixtures JSON pequenos y manuales sin DB
- un dataset inicial `pm_business_brief_dataset` con casos de onboarding, retencion, dashboard analytics, automatizacion y colaboracion

Objetivo actual:

- comparar versiones de prompts sobre datasets chicos y deterministas
- detectar degradaciones simples antes de promover cambios
- mantener fixtures fake o manuales faciles de auditar

Fuera de alcance en esta etapa:

- UI de datasets
- pipelines async
- persistencia de regression runs
- evaluacion con LLM juez
- benchmarking distribuido

### Prompt Regression Runs

La primera capa de regression runner vive en `packages/evaluations/lummevia_evaluations/regression.py`.

Incluye:

- `PromptRegressionRunner` para ejecutar dataset cases en serie
- `RegressionCaseResult` y `RegressionRunResult` como contratos de salida
- `RegressionRunSummary` con `total`, `passed`, `failed`, `avg_score` y `avg_latency_ms`
- comparacion deterministica por `expected_keywords` y `expected_sections` usando el evaluator fake existente
- comparacion simple contra baseline activa por `avg_score`, pass rate, `avg_latency_ms` y delta de `failed_cases`

Flujo actual:

```text
PromptDataset
-> PromptRegressionRunner
-> PromptPipeline
-> ModelExecutor
-> FakeModelProvider o DeepSeek controlado para PM
-> evaluator fake deterministico
-> RegressionRunResult
```

El primer endpoint disponible es:

- `POST /evaluations/pm/regression-run`
- `POST /evaluations/pm/promote`

`POST /evaluations/pm/regression-run`:

- ejecuta el dataset `pm_business_brief_dataset`
- usa DeepSeek solo si `DEEPSEEK_ENABLED=true`
- cae a `FakeModelProvider` cuando DeepSeek esta deshabilitado
- no persiste corridas
- agrega metadata de regression en Phoenix (`regression_run_id`, `dataset_id`, `total_cases`, `passed_cases`, `failed_cases`, `avg_score`, `avg_latency_ms`)

`POST /evaluations/pm/promote`:

- corre regression para una `candidate_version`
- compara el resultado contra la baseline activa si existe
- decide `PROMOTED`, `REJECTED` o `NEEDS_REVIEW`
- registra la nueva baseline activa solo cuando promueve
- crea un `HumanReview` automatico solo cuando la decision es `NEEDS_REVIEW`
- expone `review_required` y `review_id` en el contrato de promotion
- expone deltas de score, pass rate, latencia y `failed_cases`
- agrega metadata de promotion en Phoenix (`promotion_status`, `baseline_version`, `candidate_version`, `regression_delta_score`, `regression_delta_latency`, `review_id`, `review_type`, `review_status`, `review_decision`)

Reglas minimas de gating:

- no promueve si `failed_cases` empeora demasiado
- no promueve si `avg_score` cae de forma significativa
- puede devolver `NEEDS_REVIEW` para regresiones leves o dudas de latencia

Flujo actual de review para promotions:

```text
RegressionRunResult
-> compare against active baseline
-> PROMOTED | REJECTED | NEEDS_REVIEW
-> if NEEDS_REVIEW: create HumanReview(PROMPT_PROMOTION)
-> expose review_id in API response and Phoenix metadata
```

### Kilo Adapter Skeleton

`packages/kilo-adapter/lummevia_kilo/` agrega el primer adapter contractual para preparar la futura cadena:

```text
Lummevia OS -> Kilo Execution Adapter -> Kilo CLI
```

Incluye:

- `KiloExecutionStatus`
- `KiloRetryPolicy`
- `KiloExecutionAttempt`
- `KiloExecutionRecord`
- `KiloExecutionRequest`
- `KiloExecutionResult`
- `KiloExecutionClient`
- `KiloExecutionMode`
- `KiloRuntimeSettings`
- `KiloSafetyValidator`
- `ControlledSubprocessExecutor`
- `KiloWorkspaceManager`
- helpers para construir requests y envelopes de planning

Modes implementados:

- `ASK`
- `PLAN`
- `CODE`
- `DEBUG`
- `ORCHESTRATOR`

Mapeo inicial por rol:

- `PO -> PLAN`
- `DEV -> CODE`
- `QA -> DEBUG`

En esta etapa:

- el client sigue siendo fake por default
- simula lifecycle sincrono `QUEUED -> RUNNING -> SUCCESS | FAILED | RETRYING | CANCELLED`
- soporta retries fake via `max_attempts` y `fail_first_attempt` en metadata
- agrega una primera capa real controlada opt-in para sandbox
- solo ejecuta real si `KILO_ENABLED=true` y `KILO_DRY_RUN=false`
- valida allowlist via `KILO_ALLOWED_REPOS`
- prepara workspaces aislados bajo `KILO_WORKSPACE_ROOT/<execution_id>`
- usa `subprocess.run(..., shell=False)` con timeout y truncado de output
- registra metadata compacta: `real_execution`, `exit_code`, `stdout_preview`, `stderr_preview`, `workspace_path`, `command_preview`, `safety_status`
- no clona repos ni modifica el repo original
- no toca git real
- no abre PRs reales
- no conecta providers reales ni Kilo CLI real
- no hay workers async ni ejecucion externa

La cadena conectada para el runtime ahora es:

```text
Runtime Node
-> Agent
-> PromptPipeline
-> ModelExecutor
-> FakeModelProvider
```

En esta etapa:

- el pipeline sigue usando `FakeModelProvider`
- los outputs estructurados son mocks validos contra Pydantic
- no existe parsing real de respuesta LLM
- no hay prompts productivos definitivos
- no hay integracion real con DeepSeek fuera del dry-run controlado del `PM`, YouTrack, GitHub o Phoenix desde esta capa

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
- `DeepSeekModelProvider` implementa chat completions reales via DeepSeek API directa para uso controlado
- `ModelExecutionResult.metadata` deja preparada metadata para Phoenix:
  - `role`
  - `project`
  - `resolved_provider`
  - `resolved_model`
  - `effective_provider`
  - `effective_model`
  - `latency_ms`
  - `fallback_used`
- `DEEPSEEK_ENABLED=false` mantiene el fallback seguro a fake
- si `DEEPSEEK_ENABLED=true` y falta `DEEPSEEK_API_KEY`, el dry-run controlado falla de forma explicita
- el runtime principal no usa DeepSeek de forma productiva todavia
- no hay prompts productivos definitivos

## Workflow skeleton

El workflow principal del sistema ya queda modelado como contrato de datos con pasos ordenados, `responsible_role`, `consumes`, `produces` y `description`.
El paso `founder_input` usa el rol contractual `FOUNDER` en `core` para representar origen humano, sin introducir `FounderAgent` ni routing de modelo.
El gate formal `Founder ↔ PM` antes del `PO` queda trazado como decisión arquitectónica en `docs/06-decisiones/0004-founder-pm-approval-gate.md`.

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
- ejecuta pasos simulados para `FOUNDER -> founder_pm_conversation -> PM brief -> founder_business_approval -> PO ExecutionPackage -> PO TaskPlan -> PO TaskPackages -> DEV -> QA -> github_pr -> QC -> PO final`
- delega la produccion fake de `BusinessBrief`, `ExecutionPackage`, `TaskPlan`, `TaskPackage`, `ImplementationPackage`, `ValidationPackage` y `QualityApproval` a agentes conectados al `PromptPipeline`
- envia `TaskPackage` o envelopes de planning a un `KiloExecutionClient` fake en `PO`, `DEV` y `QA`
- crea una `TaskQueue` en memoria para todos los `TaskPackages` y ejecuta solo el primer item `READY`
- representa explicitamente la publicacion simulada de `github_pr`
- representa explicitamente el loop `DEV ↔ QA`
- hace explicito el gate de aprobacion Founder antes del handoff tecnico al PO
- formaliza ese gate con un `HumanReview` de tipo `BUSINESS_BRIEF`
- autoaprueba ese review dentro del flow fake actual para no cambiar el runtime sincrono
- hace explicita la descomposicion del PO antes de DEV
- deja lista la arquitectura para checkpoints futuros

En esta etapa, DEV y QA trabajan sobre el primer `TaskPackage` simulado como MVP, mientras el estado runtime conserva todos los `TaskPackages` generados y una `TaskQueue` completa con `queue_id`, `queue_item_id`, counts de `ready`, `blocked` y `completed`, y snapshots serializados para timeline y observabilidad. El estado tambien registra `kilo_executions` con `execution_id`, `role`, `mode`, `task_id`, `status`, `attempts`, `retry_count`, `final_status` y `error` cuando aplica.

Ademas, antes de cada ejecucion Kilo fake, el runtime registra una `AllocationRequest` y conserva metadata de `allocation_id`, `allocation_status`, `capacity_id`, `capacity_used_slots`, `capacity_max_slots` y `allocated_resources` para trazabilidad de capacidad.

Limitaciones actuales:

- no hay llamadas reales a modelos
- se sigue usando `FakeModelProvider`
- no hay providers reales conectados fuera del dry-run controlado de DeepSeek para `PM`
- no hay ejecucion real de Kilo CLI
- no hay integracion real con YouTrack
- no hay integracion real con GitHub
- no hay prompts reales instrumentados
- no hay tokens ni costos reales instrumentados
- la persistencia durable de `workflow_runs` y del estado operacional usa snapshots en Postgres cuando `RUNTIME_PERSISTENCE_ENABLED=true`
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
- agrega metadata de session: `session_id`, `session_status`, `session_role`, `session_attempts`, `output_count` y `event_count`
- agrega metadata de queue: `queue_id`, `queue_size`, `ready_count`, `blocked_count`, `completed_count` y `current_queue_item_id`
- agrega metadata de allocation: `allocation_id`, `allocation_status`, `capacity_used_slots`, `capacity_max_slots` y `allocated_resources_count`
- agrega metadata de project memory: `memory_records_created`, `memory_categories` y `project_memory_count`
- en el dry-run de `PM` tambien registra `template_id`, `template_version`, `prompt_hash`, `evaluation_status` y `evaluation_score`
- agrega metadata de review cuando existe: `review_id`, `review_type`, `review_status` y `review_decision`
- deja lista metadata adicional por step para `kilo_mode`, `execution_id`, `session_id`, `role`, `task_id`, `kilo_status`, `retry_count`, `attempts_count` y `final_status`
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

Variables futuras para Kilo:

- `KILO_ENABLED=false`
- `KILO_CLI_PATH`
- `KILO_WORKSPACE_ROOT`
- `KILO_DEFAULT_TIMEOUT_SECONDS=300`
- `KILO_DRY_RUN=true`
- `KILO_ALLOWED_REPOS=`
- `KILO_MAX_OUTPUT_BYTES=32768`

Comportamiento actual de Kilo:

- el adapter de `packages/kilo-adapter/` sigue siendo fake y deterministico por default
- `KILO_ENABLED=false` por defecto
- con `KILO_ENABLED=false` no se exige `KILO_CLI_PATH` ni `KILO_WORKSPACE_ROOT`
- `KILO_DRY_RUN=true` queda como default seguro
- `KILO_ALLOWED_REPOS` queda vacio por defecto y bloquea cualquier ejecucion real
- `KILO_MAX_OUTPUT_BYTES` limita previews persistidas para stdout y stderr
- con `KILO_ENABLED=true` solo se permite sandbox real si pasan enablement, dry-run off, allowlist, root de workspace y path safety
- aun con sandbox real habilitado, Lummevia OS no hace push, merge, PR automatico ni git destructivo

ConvenciÃ³n recomendada para Phoenix:

- desarrollo local con `docker compose`: `PHOENIX_HOST=phoenix`, `PHOENIX_PORT=6006`, `PHOENIX_BASE_URL=http://phoenix:6006`
- Phoenix externo en Coolify: usar la URL publicada en `PHOENIX_BASE_URL`, por ejemplo `https://phoenix.example.com`

`PHOENIX_BASE_URL` debe considerarse la referencia principal para la conexiÃ³n. `PHOENIX_HOST` y `PHOENIX_PORT` mantienen una configuraciÃ³n explÃ­cita y consistente para el caso local y para metadata operativa en despliegues externos.

`PHOENIX_ENABLED=false` desactiva la exportacion de trazas hacia Phoenix sin alterar la ejecucion del workflow.

Variables opcionales por ahora:

- `YOUTRACK_BASE_URL`, `YOUTRACK_TOKEN`
- `GITHUB_TOKEN`, `GITHUB_ORG`

Variables para DeepSeek:

- `DEEPSEEK_API_KEY`
- `DEEPSEEK_BASE_URL=https://api.deepseek.com`
- `DEEPSEEK_ENABLED=false`
- `DEEPSEEK_TIMEOUT_SECONDS=60`
- `MODEL_PM_PROVIDER=DEEPSEEK`
- `MODEL_PM_NAME=deepseek-chat`
- `MODEL_PO_PROVIDER=DEEPSEEK`
- `MODEL_PO_NAME=deepseek-v4-strong-placeholder`
- `MODEL_DEV_PROVIDER=DEEPSEEK`
- `MODEL_DEV_NAME=deepseek-v4-lite-placeholder`
- `MODEL_QA_PROVIDER=DEEPSEEK`
- `MODEL_QA_NAME=deepseek-v4-lite-placeholder`
- `MODEL_QC_PROVIDER=DEEPSEEK`
- `MODEL_QC_NAME=deepseek-v4-qc-placeholder`

Comportamiento actual de DeepSeek:

- la API key va en `.env` como `DEEPSEEK_API_KEY`
- `infra/compose/docker-compose.yml` ahora pasa `DEEPSEEK_*` y `MODEL_*` al contenedor `orchestrator-api` via interpolacion desde `.env`
- `/info` no expone la API key
- por defecto `DEEPSEEK_ENABLED=false`
- solo `POST /model-execution/pm/dry-run` puede usar el provider real
- si DeepSeek esta disabled, ese endpoint cae a `FakeModelProvider`
- si DeepSeek esta enabled pero falta la API key, el dry-run falla de forma explicita
- `deepseek-chat` es el modelo validado y recomendado hoy para el dry-run controlado de `PM`
- `deepseek-v4-strong-placeholder`, `deepseek-v4-lite-placeholder` y `deepseek-v4-qc-placeholder` siguen siendo placeholders de naming hasta confirmacion oficial
- `PO`, `DEV`, `QA`, `QC`, Kilo, GitHub y YouTrack siguen fuera de alcance real

YouTrack y GitHub todavia no son obligatorios para levantar `orchestrator-api`. Sus tokens y URLs pueden quedar vacios mientras las integraciones sigan siendo skeletons contractuales.

3. Levantar el stack local de desarrollo:

```powershell
docker compose -f infra/compose/docker-compose.yml up --build
```

Ese stack levanta Phoenix local dentro de Docker Compose para desarrollo. Para un entorno compartido con Phoenix desplegado en Coolify, la API debe configurarse con `PHOENIX_BASE_URL` apuntando al servicio externo y no necesita otra instalaciÃ³n de Phoenix dentro de este repositorio.

## Endpoints disponibles

- `GET /health`
- `GET /info`
- `POST /evaluations/pm/regression-run`
- `POST /evaluations/pm/promote`
- `POST /model-execution/pm/dry-run`
- `POST /kilo/sandbox/run`
- `GET /model-router/roles`
- `POST /model-router/resolve`
- `GET /reviews`
- `GET /reviews/{review_id}`
- `POST /reviews/{review_id}/approve`
- `POST /reviews/{review_id}/reject`
- `GET /memory/projects/{project}`
- `GET /memory/projects/{project}/category/{category}`
- `GET /memory/projects/{project}/tags/{tag}`
- `GET /sessions`
- `GET /sessions/{session_id}`
- `GET /capabilities/agents`
- `GET /capabilities/models`
- `GET /capabilities/capacity`
- `GET /capabilities/allocations`
- `GET /queues`
- `GET /queues/{queue_id}`
- `GET /queues/{queue_id}/ready`
- `GET /persistence/health`
- `POST /persistence/rehydrate`
- `GET /timelines`
- `GET /timelines/{workflow_run_id}`
- `POST /runtime/development/run`
- `GET /runtime/development/run/{run_id}`
- `GET /workflows/development`
- `GET /workflows/development/steps`
- `GET /workflows/development/steps/{step_name}`
- `POST /workflow-runs/mock`

Los endpoints de `model-router` son de diagnostico. Sirven para inspeccionar que configuracion de modelo resolveria el runtime por rol, proyecto y entorno.

No ejecutan prompts, no llaman providers reales y no disparan agentes.

El endpoint `POST /model-execution/pm/dry-run` tambien es de diagnostico controlado. Ejecuta solo el `PM`, puede usar DeepSeek API directa si `DEEPSEEK_ENABLED=true` y, aun asi, mantiene el `BusinessBrief` estructurado como salida fake validada mientras expone el texto real y `raw_output` para observabilidad basica.

Model reporting del dry-run:

- `resolved_provider` y `resolved_model` describen lo que resolvio Lummevia OS via `model-router`
- `effective_provider` y `effective_model` describen lo que realmente ejecuto o reporto el provider
- `provider` y `model` se mantienen por compatibilidad y reflejan el valor efectivo
- `template_id`, `template_version` y `prompt_hash` identifican exactamente el prompt ejecutado
- `evaluation_id`, `evaluation_status` y `evaluation` exponen la salida del evaluator fake actual

Ese endpoint:

- no modifica el runtime principal
- no persiste workflows
- no crea artefactos reales en YouTrack
- no habilita DeepSeek real para `PO`, `DEV`, `QA` ni `QC`

El endpoint `POST /kilo/sandbox/run` tambien es de diagnostico controlado.

Input minimo:

- `project`
- `repo_path`
- `task_id`
- `prompt`
- `mode`

Ese endpoint:

- valida safety antes de cualquier ejecucion real
- usa fake si `KILO_ENABLED=false` o `KILO_DRY_RUN=true`
- solo ejecuta Kilo CLI real dentro del sandbox si el repo esta en `KILO_ALLOWED_REPOS`
- no persiste workflows
- no usa el workflow principal
- no hace push, merge ni PR

Ejemplo recomendado para probar sandbox con un repo de prueba:

```powershell
$env:KILO_ENABLED="true"
$env:KILO_DRY_RUN="false"
$env:KILO_CLI_PATH="C:\sandbox\kilo.exe"
$env:KILO_WORKSPACE_ROOT="C:\sandbox\lummevia-kilo"
$env:KILO_ALLOWED_REPOS="lummevia-os-sandbox"

curl -X POST http://localhost:8000/kilo/sandbox/run `
  -H "Content-Type: application/json" `
  -d '{
    "project": "lummevia-os-sandbox",
    "repo_path": "C:/sandbox/lummevia-os-sandbox",
    "task_id": "OS-900-T1",
    "prompt": "Run sandbox validation only.",
    "mode": "CODE"
  }'
```

Roadmap futuro de evaluacion:

- approval UI
- review inbox UI
- founder approval UI
- persistencia durable de baselines y promotions
- persistencia durable de reviews
- CI/CD y gating reales
- rollout gradual y A/B testing
- comparacion automatica mas rica entre versiones de prompt
- regression detection mas sofisticado por template
- almacenamiento durable de evaluaciones
- datasets y suites de regression dedicadas
- evaluacion humana y scoring mas sofisticado
- multi-tenant prompt stores

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

## Resource Locks y Workspace Isolation

Lummevia OS ahora agrega una primera capa contractual de `Resource Locks` y `Workspace Isolation` para preparar la ejecucion paralela segura de `TaskPackages`.

Esto existe porque dos tareas DEV o QA sobre el mismo repo o workspace pueden pisarse entre si incluso antes de tener paralelismo real, worktrees o merges automatizados.

La estrategia actual es deliberadamente conservadora:

- cada `TaskQueueItem` activo recibe un `workspace_id` aislado
- el runtime reserva locks en memoria para `REPO`, `WORKSPACE` y `PATH`
- se propagan `branch_name`, `worktree_path` y `lock_ids` a queue, sessions, requests Kilo y Phoenix
- `QA PASS` libera el workspace y sus locks
- `QA FAIL` conserva el workspace activo para revision o rework

Limites recomendados en esta etapa:

- un solo `TaskQueueItem` activo por queue
- un workspace activo por item
- evitar mas de una task simultanea por repo hasta introducir politicas de concurrencia mas finas

Todavia no se ejecuta:

- `git worktree`
- `git checkout`
- mutacion real de filesystem
- Kilo real
- paralelismo real
- merge orchestration

La ruta futura es reemplazar el `worktree_path` simulado por workspaces reales bajo `KILO_WORKSPACE_ROOT`, manteniendo el mismo contrato observable para que el runtime no tenga que redisenarse cuando llegue esa capa.

## Supervisor Layer

Lummevia OS ahora incluye una primera capa MVP de supervision operacional para workflows, sessions, queue items y ejecuciones Kilo.

Esta capa vive en `packages/supervisor` y agrega:

- `watchdogs` en memoria con heartbeats on-demand
- `ExecutionHealthStatus` comun para runtime, queue, sessions y metadata Kilo
- `SupervisorEvent` y `RecoveryAction` trazables
- `dead-letter` para tasks que agotan retries contractuales
- cancelacion explicita de workflow con liberacion de locks, workspace y allocation
- metadata observable en timeline y Phoenix

Semantica actual del MVP:

- un target `RUNNING` sin heartbeat por encima de su `timeout_seconds` pasa a `STUCK`
- un `STUCK` puede disparar `RETRY`
- si los retries contractuales se agotan, el item pasa a `DEAD_LETTER`
- `cancel_workflow` no mata procesos reales: marca estado, registra recovery, libera recursos simulados y deja trazabilidad

Eventos de timeline agregados:

- `WATCHDOG_CREATED`
- `EXECUTION_STUCK`
- `RECOVERY_TRIGGERED`
- `TASK_REQUEUED`
- `DEAD_LETTERED`
- `WORKFLOW_CANCELLED`

Endpoints nuevos:

- `GET /supervisor/watchdogs`
- `GET /supervisor/recovery-actions`
- `GET /supervisor/dead-letters`
- `POST /supervisor/workflows/{workflow_run_id}/cancel`
- `POST /supervisor/watchdogs/detect-stuck`

Limites actuales:

- sin workers reales
- sin threads ni cron
- sin retries distribuidos
- sin scheduler externo
- sin persistence dedicada del supervisor
- sin kill real de procesos
- sin auto-recovery destructivo

Roadmap natural despues de este MVP:

- persistencia durable de watchdogs y dead-letters
- requeue real y resume real de ejecuciones
- politicas de starvation por cola
- scheduler supervisor desacoplado
- reconciliacion automatica entre runtime y recursos huerfanos

## Persistencia operacional

Lummevia OS ahora incorpora una estrategia hibrida `in-memory cache + Postgres durable` para el estado operacional critico.

Entidades que ya persisten en snapshots:

- queues y queue items
- task execution sessions
- supervisor state: watchdogs, recovery actions, supervisor events y dead letters
- conversation threads y mensajes
- project memory
- human reviews
- resource locks y workspaces
- capability/capacity snapshots
- workflow runs

Comportamiento actual:

- los registries siguen sirviendo como cache en memoria del proceso
- cada cambio critico intenta persistirse en Postgres sin bloquear el flujo si la escritura falla
- al iniciar la API, los registries pueden rehidratarse desde storage durable
- el timeline puede reconstruirse desde runtime state o desde snapshots persistidos
- Phoenix recibe metadata de persistencia como `persistence_enabled`, `repository_write_success`, `repository_read_success`, `snapshot_version` y `rehydrated_from_storage`

Lo que todavia sigue fuera de alcance:

- event sourcing completo
- locking distribuido real
- coordinacion cross-node
- workers o consumers de background
- CQRS, sharding o streams

Restart safety actual:

- un reinicio no pierde queues, sessions, watchdogs, dead letters, conversaciones activas, memoria ni workspaces persistidos
- si Postgres falla durante una escritura, el runtime conserva el estado local en memoria y no destruye el cache actual
- `POST /persistence/rehydrate` fuerza reload desde Postgres sin reiniciar el proceso y sin vaciar memoria local si una lectura falla

Roadmap distribuido posterior:

- reconciliacion de estado entre multiples nodos
- locking y ownership distribuidos
- scheduling externo y recovery autonomo
- politicas de replay y recovery mas finas sobre snapshots

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
docker compose -f infra/compose/docker-compose.yml build orchestrator-api --no-cache
docker compose -f infra/compose/docker-compose.yml run --rm orchestrator-api pytest -q /app/tests
```
