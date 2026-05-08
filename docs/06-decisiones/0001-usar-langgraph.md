# ADR-0001 — Usar LangGraph

## Estado

Acordado.

## Contexto

Lummevia OS necesita un runtime de orquestación capaz de manejar:
- múltiples agentes
- workflows iterativos
- estado runtime
- checkpoints
- loops DEV ↔ QA
- routing
- validaciones
- trazabilidad
- ejecución multi-proyecto

## Decisión

Lummevia OS utilizará `LangGraph` como runtime principal de orquestación.

## Motivos

LangGraph permite:
- control explícito de workflows
- checkpoints
- estado durable
- loops iterativos
- human-in-the-loop
- routing avanzado
- desacoplamiento de agentes
- integración programática flexible

## Regla arquitectónica

LangGraph es:

```text
runtime de ejecución
```

LangGraph no es:
- memoria operacional
- repositorio técnico
- observabilidad
- sistema documental

## Relación con otras capas

| Componente | Responsabilidad |
|---|---|
| YouTrack | memoria operacional |
| Repositorio | verdad técnica |
| LangGraph | runtime |
| Phoenix | observabilidad |
| GitHub | evidencia de cambios y PRs |
