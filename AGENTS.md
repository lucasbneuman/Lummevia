# Lummevia OS — Router de Contexto para Agentes

## Objetivo

Este archivo es un router mínimo de contexto para agentes IA que trabajen en este repositorio.

La documentación principal vive en `docs/`.

## Regla principal

Antes de modificar código, workflows, documentación, arquitectura o integraciones, el agente debe leer los documentos relevantes.

## Rutas de contexto

### Visión

Leer `docs/00-producto/vision.md`.

### Arquitectura

Leer:
- `docs/01-arquitectura/overview-sistema.md`
- `docs/01-arquitectura/model-router.md`

### Roles y límites

Leer `docs/02-agentes/roles-y-limites.md`.

### Workflow principal

Leer `docs/03-workflows/loop-desarrollo.md`.

### Integraciones

Leer según corresponda:
- `docs/04-integraciones/youtrack.md`
- `docs/04-integraciones/github.md`
- `docs/04-integraciones/phoenix.md`

### Decisiones arquitectónicas

Leer `docs/06-decisiones/` antes de modificar runtime, observabilidad, model routing o arquitectura principal.

## Reglas mínimas

Los agentes deben:
- consumir contexto desde las fuentes correctas
- respetar ownership
- evitar duplicación
- mantener trazabilidad
- respetar la arquitectura existente

Los agentes no deben:
- inventar arquitectura no documentada
- hardcodear modelos
- mezclar responsabilidades
- mover reglas centrales fuera de `docs/`
- reemplazar ownership humano
- crear memoria paralela
