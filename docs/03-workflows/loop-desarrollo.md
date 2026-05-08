# Flujo de Desarrollo — Lummevia OS

## Objetivo

Definir el flujo principal de contexto, artefactos, ejecución y validación dentro de Lummevia OS.

## Flujo completo

```text
Founder
↓
PM
↓
Business Brief
↓
PO
↓
Execution Package
↓
DEV
↓
Implementation Package
↓
PR
↓
QA
↓
Validation Package
↓
QC
↓
Quality Approval
↓
PO final
↓
merge / cierre
```

## Secuencia operativa

### 1. Founder → PM

Founder define intención, necesidad y prioridad humana.

PM transforma esa intención en un `Business Brief`.

### 2. PM → PO

PO consume el `Business Brief`, el contexto operacional relevante y la documentación técnica del proyecto.

PO produce un `Execution Package` con:
- alcance técnico
- criterios de aceptación
- edge cases
- escenarios de testing
- restricciones y decisiones técnicas locales
- tasks concretas
- prompts para DEV

### 3. PO → DEV

DEV consume el `Execution Package`, la task asignada y el contexto técnico local del repositorio.

DEV implementa y produce:
- cambios en código
- branch
- commits
- `Implementation Package`
- PR

### 4. DEV ↔ QA

QA valida comportamiento, criterios de aceptación y edge cases sobre la implementación y el PR.

QA produce un `Validation Package`.

Si encuentra errores, crea `BUG issues` y se reabre la iteración DEV ↔ QA hasta que la implementación quede validada.

### 5. QA → QC

Una vez validado el comportamiento, QC revisa el PR como validación técnica final.

QC verifica:
- arquitectura
- consistencia
- standards
- alineación con ADRs

QC produce `Quality Approval`.

### 6. QC → PO final

PO final consume:
- PR
- `Validation Package`
- `Quality Approval`
- resultado final de implementación

PO final realiza la validación funcional final antes de `merge / cierre`.

## Jerarquía de información aplicada al flujo

### YouTrack

Se usa para:
- memoria operacional
- coordinación
- tasks
- bugs
- artefactos del flujo
- links a PRs y trazas

No se usa para documentación técnica extensa.

### Repositorio

Se usa para:
- verdad técnica
- código
- arquitectura
- ADRs
- documentación técnica

### GitHub

Se usa para:
- branches
- commits
- PRs
- evidencia de cambios
- revisión técnica sobre PR

### Phoenix

Se usa para:
- trazas
- prompts
- latencia
- costos
- errores
- metadata de ejecución

## Artefactos del flujo

| Artefacto | Responsable |
|---|---|
| Business Brief | PM |
| Execution Package | PO |
| Implementation Package | DEV |
| Validation Package | QA |
| Quality Approval | QC |

## Reglas importantes

- `AGENTS.md` es un router de contexto, no el documento maestro del sistema.
- YouTrack sigue siendo memoria operacional.
- El repositorio sigue siendo verdad técnica.
- Phoenix sigue siendo observabilidad.
- El Model Router mantiene los modelos configurables por rol, proyecto y entorno.
