# Model Router — Lummevia OS

## Objetivo

Definir cómo Lummevia OS selecciona modelos IA para cada agente sin hardcodear modelos dentro del código de los agentes.

## Principio fundamental

Los agentes no conocen modelos específicos.

Los agentes piden capacidad.

El Model Router resuelve qué modelo usar.

```text
Agente
↓
Model Router
↓
Provider / Modelo
```

## Responsabilidades del Model Router

Debe resolver modelos según:
- rol del agente
- proyecto
- entorno
- costo
- capacidad requerida
- disponibilidad
- fallback

## Distribución inicial por rol

| Rol | Capacidad esperada | Perfil inicial |
|---|---|---|
| PM | reasoning estratégico, síntesis, negocio | modelo fuerte |
| PO | reasoning técnico, expansión, arquitectura | modelo fuerte |
| DEV | ejecución técnica, edición, implementación | modelo liviano o medio |
| QA | validación, edge cases, testing | modelo liviano o medio |
| QC | revisión de PR, arquitectura, standards | modelo medio o fuerte |

## Reglas de configuración

Los modelos deben configurarse fuera del código de agentes.

La configuración debe soportar overrides por:
- rol
- proyecto
- entorno

También debe soportar fallbacks ante:
- provider caído
- rate limit
- error de API
- contexto excedido
- costo excesivo
- latencia alta

## Observabilidad

Cada llamada a modelo debe registrar:
- agente
- rol
- proyecto
- entorno
- provider
- modelo
- fallback usado o no
- latencia
- costo estimado
- resultado
- error si existe

Phoenix debe recibir esta metadata como parte de las trazas.

## Prohibiciones

No se permite:
- hardcodear modelos dentro de agentes
- acoplar agentes a un provider específico
- ocultar fallbacks
- cambiar modelos sin trazabilidad
- mezclar configuración de modelos con lógica de negocio
