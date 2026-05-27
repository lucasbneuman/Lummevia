# Integración Telegram — Lummevia OS

## Objetivo

Definir cómo Lummevia OS recibe intención del Founder desde Telegram sin convertir Telegram en memoria operacional ni en runtime.

## Principio fundamental

Telegram es un canal de entrada humano.

Telegram no reemplaza:
- la memoria operacional de YouTrack
- el runtime de orquestación
- la documentación técnica del repositorio
- la aprobación explícita del Founder

## Flujo actual

El bot usa webhook HTTP:

```text
Telegram
↓
POST /telegram/webhook
↓
PM conversation loop
↓
YouTrack issue / comments
↓
Founder approval
↓
handoff al runtime
```

El endpoint espera mensajes de texto con este formato:

```text
/lummevia project=<shortName> [issue=<ISSUE-ID>]
texto de intención o respuesta del Founder
```

Para aprobar un brief pendiente:

```text
/approve project=<shortName> issue=<ISSUE-ID>
apruebo
```

## Variables de configuración

- `TELEGRAM_ENABLED`: habilita checks de readiness para Telegram.
- `TELEGRAM_BOT_TOKEN`: token del bot emitido por BotFather.
- `TELEGRAM_WEBHOOK_SECRET`: secreto enviado por Telegram al webhook.
- `TELEGRAM_BOT_USERNAME`: username público del bot, usado como metadata operativa.
- `TELEGRAM_ALLOWED_CHAT_IDS`: lista CSV de chats permitidos. Si está vacía, el webhook acepta cualquier chat que pase el secreto.
- `PUBLIC_API_URL`: URL pública de la API. El webhook esperado es `PUBLIC_API_URL + /telegram/webhook`.
- `PUBLIC_BASE_URL`: URL pública base de la app. Se usa como fallback cuando `PUBLIC_API_URL` no está configurada.

El webhook también requiere YouTrack configurado para crear issues o agregar comentarios:

- `YOUTRACK_ENABLED=true`
- `YOUTRACK_BASE_URL`
- `YOUTRACK_TOKEN`

## Registro del webhook

Después de desplegar la API con una URL pública HTTPS:

```bash
python scripts/telegram_webhook.py set --drop-pending-updates
```

Para inspeccionar el webhook actual:

```bash
python scripts/telegram_webhook.py info
```

Para borrar el webhook:

```bash
python scripts/telegram_webhook.py delete
```

## Validación

Antes de registrar el webhook productivo:

```bash
curl "$PUBLIC_API_URL/readiness"
python scripts/smoke_coolify.py --base-url "$PUBLIC_API_URL" --telegram-secret "$TELEGRAM_WEBHOOK_SECRET"
```

Luego enviar un mensaje al bot:

```text
/lummevia project=LUM
crear app para reservas medicas
```

El resultado esperado es:
- issue creado o actualizado en YouTrack
- comentario con la respuesta del Founder
- preguntas del PM o draft de Business Brief
- conversación visible en `GET /telegram/conversations`

## Reglas

- No almacenar tokens ni secretos en documentación, issues o PRs.
- Usar `TELEGRAM_WEBHOOK_SECRET` en producción.
- Configurar `TELEGRAM_ALLOWED_CHAT_IDS` cuando el bot no deba aceptar cualquier chat.
- Mantener la aprobación explícita del Founder antes del handoff al PO.
- Mantener YouTrack como memoria operacional; Telegram sólo transporta mensajes.
