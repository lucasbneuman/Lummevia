# Flujo de Desarrollo — Lummevia OS

## Objetivo

Definir el flujo principal de contexto, artefactos, ejecución y validación dentro de Lummevia OS.

## Flujo completo

```text
Founder
↓
PM conversation loop
↓
Business Brief draft
↓
Founder approval
↓
Business Brief approved
↓
PO
↓
Execution Package
↓
Task Plan
↓
Task Packages iterativos
↓
DEV
↓
Implementation Package
↓
QA
↓
Validation Package
↓
PR
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

### 1. Founder → PM conversation loop

Founder define intención, necesidad y prioridad humana.

Founder y PM pueden iterar en conversación para aclarar objetivo, alcance y prioridad antes de formalizar el brief.

El resultado de este loop es contexto alineado para producir un `Business Brief` en estado `draft`.

### 2. PM draft → Founder approval

PM transforma esa intención alineada en un `Business Brief`.

Ese brief queda en estado `draft` hasta que Founder apruebe explícitamente su contenido.

El handoff al PO sólo puede ocurrir cuando el `Business Brief` está en estado `approved`.

### 3. PM approved brief → PO

PO consume el `Business Brief` aprobado, el contexto operacional relevante y la documentación técnica del proyecto.

PO no debe generar todo el trabajo en una sola respuesta monolítica.

PO trabaja por fases:
- primero produce un `Execution Package`
- luego produce un `TaskPlan`
- luego produce `TaskPackages` pequeños e iterables

El `Execution Package` define el marco técnico general con:
- alcance técnico
- criterios de aceptación
- edge cases
- escenarios de testing
- restricciones y decisiones técnicas locales

El `TaskPlan` organiza:
- workstreams
- secuencia de ejecución
- ids de `TaskPackages`
- riesgos de coordinación

Cada `TaskPackage` define una unidad pequeña de ejecución para Kilo CLI con:
- objetivo concreto
- contexto puntual
- criterios de aceptación
- restricciones
- prompt acotado para DEV
- artefactos esperados

Esta descomposición reduce tokens, evita prompts gigantes y mejora la trazabilidad entre brief, plan y ejecución.

### 4. PO → DEV

DEV consume el `Execution Package` como contexto paraguas, pero ejecuta una iteración a la vez sobre un `TaskPackage`, no sobre un mega prompt monolítico.

DEV implementa y produce:
- cambios en código
- branch
- commits
- `Implementation Package`

### 5. DEV ↔ QA

QA valida comportamiento, criterios de aceptación y edge cases sobre la implementación del `TaskPackage` actual.

QA produce un `Validation Package`.

Si encuentra errores, crea `BUG issues` y se reabre la iteración DEV ↔ QA hasta que la implementación quede validada.

### 6. QA PASS → GitHub PR

Una vez que QA valida la implementación, DEV materializa la evidencia técnica en GitHub mediante un PR.

El nodo `github_pr` ocurre explícitamente después de `QA PASS`.

### 7. GitHub PR → QC

QC revisa el PR ya generado como validación técnica final.

QC verifica:
- arquitectura
- consistencia
- standards
- alineación con ADRs

QC produce `Quality Approval`.

### 8. QC → PO final

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
| Business Brief draft | PM |
| Business Brief approved | Founder |
| Execution Package | PO |
| TaskPlan | PO |
| TaskPackages | PO |
| Implementation Package | DEV |
| Validation Package | QA |
| Quality Approval | QC |

## Reglas importantes

- `AGENTS.md` es un router de contexto, no el documento maestro del sistema.
- PM no puede enviar trabajo al PO sin aprobación explícita del Founder.
- PO no debe producir todos los tasks, prompts y tickets en una sola generación monolítica.
- Kilo CLI debe consumir `TaskPackages` pequeños y secuenciales.
- QA valida por `TaskPackage`, no por un prompt gigante único.
- YouTrack sigue siendo memoria operacional.
- El repositorio sigue siendo verdad técnica.
- Phoenix sigue siendo observabilidad.
- El Model Router mantiene los modelos configurables por rol, proyecto y entorno.
