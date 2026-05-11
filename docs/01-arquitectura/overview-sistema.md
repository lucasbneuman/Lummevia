# Overview del Sistema — Lummevia OS

## Objetivo

Definir la arquitectura general, las capas del sistema, el ownership semántico y la jerarquía de información de Lummevia OS.

## Capas del sistema

### YouTrack

YouTrack es:

```text
memoria operacional + sistema de coordinación
```

Contiene:
- briefs
- épicas
- tasks
- bugs
- workflows
- SOPs
- estado de ejecución
- comunicación entre agentes
- links a PRs
- links a trazas

No debe contener:
- implementación técnica extensa
- código fuente
- lógica runtime
- documentación arquitectónica detallada del repositorio

### Repositorio

El repositorio es:

```text
verdad técnica local del proyecto
```

Contiene:
- código
- documentación técnica
- arquitectura
- ADRs
- tests
- contratos
- workflows técnicos
- `AGENTS.md` local

No debe contener:
- backlog operacional central
- prioridades globales
- memoria operacional principal

### Orquestador

El orquestador es:

```text
runtime de ejecución
```

Coordina:
- agentes
- workflows
- routing
- checkpoints
- locks
- estado runtime
- ejecución distribuida

No debe contener:
- memoria durable de negocio
- documentación principal
- contexto técnico principal

### Phoenix

Phoenix es:

```text
capa de observabilidad
```

Registra:
- trazas
- prompts
- latencia
- costos
- evaluaciones
- errores
- comportamiento de agentes

No debe contener:
- decisiones finales de negocio
- documentación operacional
- arquitectura principal
- memoria persistente

### Model Router

El Model Router desacopla:
- agentes
- modelos
- providers

Permite:
- routing por rol
- routing por proyecto
- routing por entorno
- fallbacks
- cambio de modelos sin modificar agentes

## Jerarquía de información

| Capa | Función principal |
|---|---|
| YouTrack KB | memoria operacional estable |
| YouTrack Issues | coordinación y ejecución activa |
| Repositorio | verdad técnica local |
| Orquestador | estado runtime |
| Phoenix | observabilidad y trazabilidad |

## Principio de contexto

Cada agente debe consumir contexto únicamente desde las fuentes correctas.

La separación obligatoria es:

```text
memoria operacional
memoria técnica
estado runtime
observabilidad
```

Ninguna capa debe absorber responsabilidades de otra.

## Flujo de información

El flujo principal del sistema es:

```text
Founder → PM conversation loop → Business Brief draft → Founder approval →
Business Brief approved → PO ExecutionPackage → PO TaskPlan →
PO TaskPackages iterativos → DEV → QA → PR → QC → PO final
```

La definición detallada de handoffs, artefactos y validaciones vive en `docs/03-workflows/loop-desarrollo.md`.

La decisión arquitectónica que formaliza el gate `Founder ↔ PM` antes del `PO` vive en `docs/06-decisiones/0004-founder-pm-approval-gate.md`.
La decisión arquitectónica que formaliza la descomposición del `PO` por fases vive en `docs/06-decisiones/0005-po-task-decomposition-flow.md`.

## Descomposición del PO

El `PO` no genera todo el trabajo técnico en una sola expansión monolítica.

La arquitectura separa tres artefactos secuenciales:
- `ExecutionPackage` como marco técnico global
- `TaskPlan` como plan de secuencia y workstreams
- `TaskPackage` como unidad pequeña de ejecución para DEV y QA

Consecuencias arquitectónicas:
- reduce presión de tokens sobre Kilo CLI
- mejora trazabilidad entre brief, plan, paquete y validación
- evita mega prompts difíciles de auditar
- mantiene YouTrack alineado con unidades pequeñas de trabajo

## Regla sobre AGENTS.md

Cada proyecto posee su propio `AGENTS.md`.

`AGENTS.md`:
- funciona como router de contexto
- no reemplaza `docs/`
- no reemplaza la arquitectura
- no reemplaza los workflows
