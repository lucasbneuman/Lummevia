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

## Configuración del orquestador

La configuración de Lummevia OS para Phoenix se apoya en estas variables:

- `PHOENIX_ENABLED`: activa o desactiva exportación hacia Phoenix.
- `PHOENIX_BASE_URL`: URL base que usará el sistema para conectarse a Phoenix. Para entornos externos en Coolify es la referencia principal.
- `PHOENIX_HOST`: host de Phoenix. En desarrollo local normalmente es `phoenix`.
- `PHOENIX_PORT`: puerto HTTP de Phoenix. En desarrollo local y Coolify normalmente es `6006`.
- `PHOENIX_API_KEY`: API key usada por el exporter OTLP HTTP cuando Phoenix tiene auth activada.

Convención recomendada:

- desarrollo local: `PHOENIX_HOST=phoenix`, `PHOENIX_PORT=6006`, `PHOENIX_BASE_URL=http://phoenix:6006`
- despliegue compartido con Coolify: `PHOENIX_HOST=phoenix.lummevia.com`, `PHOENIX_PORT=6006`, `PHOENIX_BASE_URL=https://phoenix.lummevia.com`

`PHOENIX_ENABLED=false` desactiva la exportación de trazas sin alterar la ejecución del workflow.

## Deploy externo en Coolify

El despliegue externo validado corre como Docker Compose separado del orquestador, con Phoenix y Postgres dedicado en el mismo stack.

Dominio público:

```text
https://phoenix.lummevia.com
```

En Coolify, el dominio del servicio `phoenix` debe apuntar al puerto interno `6006`. En service stacks, el dominio puede configurarse como:

```text
https://phoenix.lummevia.com:6006
```

El sufijo `:6006` indica el puerto interno del contenedor para Traefik/Coolify; no implica que el usuario deba navegar públicamente con ese puerto.

Compose operativo:

```yaml
services:
  phoenix:
    image: 'arizephoenix/phoenix:version-15.5.1'
    restart: unless-stopped
    depends_on:
      - postgres
    environment:
      - PHOENIX_PORT=6006
      - 'PHOENIX_SQL_DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}'
      - PHOENIX_ENABLE_AUTH=true
      - 'PHOENIX_SECRET=${PHOENIX_SECRET}'
      - 'PHOENIX_DEFAULT_ADMIN_INITIAL_PASSWORD=${PHOENIX_DEFAULT_ADMIN_INITIAL_PASSWORD}'
      - PHOENIX_USE_SECURE_COOKIES=true
      - PHOENIX_TELEMETRY_ENABLED=false
    ports:
      - '6006:6006'
    volumes:
      -
        type: bind
        source: ./phoenix-data
        target: /mnt/data
        is_directory: true

  postgres:
    image: 'postgres:16-alpine'
    restart: unless-stopped
    environment:
      - 'POSTGRES_DB=${POSTGRES_DB}'
      - 'POSTGRES_USER=${POSTGRES_USER}'
      - 'POSTGRES_PASSWORD=${POSTGRES_PASSWORD}'
    volumes:
      -
        type: bind
        source: ./postgres-data
        target: /var/lib/postgresql/data
        is_directory: true
```

Variables del stack Phoenix en Coolify:

```env
POSTGRES_DB=phoenix
POSTGRES_USER=<phoenix-postgres-user>
POSTGRES_PASSWORD=<phoenix-postgres-password>

PHOENIX_SECRET=<secret-de-32-o-mas-caracteres>
PHOENIX_DEFAULT_ADMIN_INITIAL_PASSWORD=<password-admin-inicial>
```

Notas operativas:

- `PHOENIX_SECRET` debe tener al menos 32 caracteres.
- `PORT=6006` no es necesario; Phoenix usa `PHOENIX_PORT=6006`.
- `PHOENIX_CSRF_TRUSTED_ORIGINS` queda omitida en el deploy actual porque generó `untrusted referer` detrás de Coolify. Se puede reactivar más adelante con el origin exacto si se valida el comportamiento detrás del proxy.
- El cartel de Coolify `No health check configured` no bloquea el routing. Puede agregarse un healthcheck después de estabilizar el servicio.
- El cartel `Hardcoded variables are not shown here` indica que variables definidas directamente en el compose no aparecen como variables editables en la UI.

Login inicial:

```text
usuario: admin@localhost
password: valor de PHOENIX_DEFAULT_ADMIN_INITIAL_PASSWORD
```

Después del primer ingreso, crear una System API Key en Phoenix para que el orquestador pueda exportar trazas con auth activa.

## Conexión del orquestador

Para conectar o revalidar la API desplegada con Phoenix externo:

1. Crear una System API Key en Phoenix.
2. Cargar estas variables en el deploy Coolify del orquestador:

```env
PHOENIX_ENABLED=true
PHOENIX_HOST=phoenix.lummevia.com
PHOENIX_PORT=6006
PHOENIX_BASE_URL=https://phoenix.lummevia.com
PHOENIX_API_KEY=<system-api-key>
```

3. Publicar el código en `main` y redeployar el orquestador.
4. Validar `/readiness`; el check Phoenix debe reportar `status=ok`, `base_url=https://phoenix.lummevia.com` y `api_key_configured=true`.
5. Ejecutar un flujo mínimo del runtime que genere spans.
6. Confirmar en Phoenix que aparecen trazas bajo el servicio `lummevia-orchestrator-api`.
7. Si no aparecen trazas, revisar logs del orquestador y confirmar que el endpoint OTLP HTTP efectivo sea `https://phoenix.lummevia.com/v1/traces`.

## Estado productivo validado

Validado el 2026-05-28.

Código desplegado:

```text
d340656 Enable Phoenix API key export
```

Deploy Coolify validado:

```text
nggo0c08k08w888s4cskc804
```

Container productivo validado:

```text
lssw8gk08scso4okcgs8wg00-223553712295
```

Readiness público validado:

```json
{
  "phoenix": {
    "status": "ok",
    "base_url": "https://phoenix.lummevia.com",
    "api_key_configured": true,
    "non_blocking_export": true
  }
}
```

Smoke runtime validado:

```text
run_id: run-1caf9209-e446-4058-a7b2-ab960c3f4d8e
issue_id: OS-PHX-PROD-SMOKE-2
status: COMPLETED
```

Resultado observado:

- el runtime completó el workflow
- Phoenix recibió spans del run validado
- no quedaron errores recientes `401 Invalid token` en logs del orquestador después del deploy `d340656`
- los spans quedaron registrados en Phoenix con nombres como `step:workflow_completed`, `step:qa_validation` y `step:dev_implementation`

Nota operativa: si vuelve a aparecer `Failed to export span batch code: 401, reason: Invalid token`, revisar primero que el deploy productivo esté corriendo un commit que incluya soporte para `PHOENIX_API_KEY` y que `/readiness` reporte `api_key_configured=true`.

## Estado actual

Phoenix ya tiene integración real inicial en el código del orquestador mediante OpenTelemetry OTLP HTTP:

- crea spans de workflow runtime
- crea spans para pasos del runtime
- exporta metadata de runtime, modelo, estrategia, costos estimados, sesiones, queue y evaluaciones según el flujo implementado
- soporta `PHOENIX_API_KEY` para Phoenix externo con auth activada

La instalación de Phoenix externo no vive en una carpeta aparte dentro del repositorio. El repositorio conserva los contratos, variables y documentación; Coolify conserva el stack operativo externo.
