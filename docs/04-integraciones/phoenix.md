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

## Modos de despliegue

Phoenix puede correr de dos formas sin cambiar la arquitectura actual del runtime:

- local en `docker compose` para desarrollo del repositorio
- externo como servicio compartido desplegado en Coolify

El Phoenix local existe para facilitar desarrollo y validaciones del stack. El Phoenix externo existe para entornos compartidos donde varios despliegues de Lummevia OS deben apuntar a una misma capa de observabilidad.

## ConfiguraciÃ³n base

La configuraciÃ³n de Lummevia OS para Phoenix debe apoyarse en estas variables:

- `PHOENIX_BASE_URL`: URL base que usarÃ¡ el sistema para conectarse a Phoenix. Para entornos externos en Coolify esta debe considerarse la referencia principal.
- `PHOENIX_HOST`: host de Phoenix. En desarrollo local normalmente es `phoenix`.
- `PHOENIX_PORT`: puerto HTTP de Phoenix. En desarrollo local normalmente es `6006`.

ConvenciÃ³n recomendada:

- desarrollo local: `PHOENIX_HOST=phoenix`, `PHOENIX_PORT=6006`, `PHOENIX_BASE_URL=http://phoenix:6006`
- despliegue compartido con Coolify: mantener `PHOENIX_BASE_URL` apuntando a la URL publicada del servicio y ajustar `PHOENIX_HOST` y `PHOENIX_PORT` solo como metadata operativa coherente con ese despliegue

## Alcance actual

En esta etapa:

- Lummevia OS solo deja preparada la configuraciÃ³n para Phoenix local o externo
- no se agrega instrumentaciÃ³n real
- no se instala Phoenix en una carpeta aparte dentro del repositorio
- no se modifica LangGraph
- no se cambia la arquitectura del runtime
