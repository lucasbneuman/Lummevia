# ADR-0002 — Usar Phoenix como capa inicial de observabilidad

## Estado

Acordado.

## Contexto

Lummevia OS necesita observabilidad completa sobre:
- agentes
- prompts
- ejecución
- validaciones
- latencia
- errores
- costos
- workflows
- loops DEV ↔ QA
- decisiones runtime

## Decisión

Lummevia OS utilizará `Phoenix` como primera capa de observabilidad del sistema.

## Objetivos iniciales

Registrar:
- agente
- rol
- proyecto
- issue relacionado
- prompts
- modelo usado
- latencia
- costo estimado
- errores
- fallback utilizado
- resultado de ejecución

## Regla arquitectónica

Phoenix es:

```text
capa de observabilidad
```

Phoenix no es:
- memoria operacional
- repositorio técnico
- sistema documental
- runtime
- sistema de coordinación

## Relación con otras capas

| Componente | Responsabilidad |
|---|---|
| YouTrack | memoria operacional |
| Repositorio | verdad técnica |
| LangGraph | runtime |
| Phoenix | observabilidad |
| GitHub | evidencia de cambios y PRs |
