# Integración Phoenix — Lummevia OS

## Objetivo

Definir cómo Lummevia OS utiliza Phoenix como capa de observabilidad, tracing y análisis de ejecución.

## Principio fundamental

Phoenix es la capa de observabilidad del sistema.

Phoenix no es:
- memoria operacional
- repositorio técnico
- runtime
- sistema de coordinación
- almacenamiento documental

## Responsabilidades

Phoenix debe registrar:
- trazas
- prompts
- outputs
- latencia
- costos
- errores
- fallbacks
- evaluaciones
- metadata runtime

## Metadata obligatoria

Cada traza debe incluir como mínimo:
- `run_id`
- `workflow`
- `project`
- `environment`
- `issue_id`
- `agent_role`
- `agent_name`
- `provider`
- `model`
- `fallback_used`
- `status`
- `latency_ms`
- `estimated_cost`

## Relación con otras capas

### Con YouTrack

YouTrack almacena la memoria operacional y puede guardar links a trazas relevantes.

### Con GitHub

Phoenix puede relacionar runs con commits, branches, PRs y validaciones mediante metadata compartida.

### Con Model Router

Toda resolución de modelo y todo fallback deben quedar registrados en observabilidad.

## Reglas importantes

Phoenix no debe contener:
- documentación principal
- decisiones finales de negocio
- arquitectura principal
- memoria operacional persistente

Phoenix debe permanecer desacoplado de:
- ownership de agentes
- lógica de negocio
- estructura documental
