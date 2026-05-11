# ADR-0004 — Introducir gate formal de aprobación Founder ↔ PM antes del PO

## Estado

Acordado.

## Contexto

Lummevia OS separa explícitamente:
- intención y prioridad de negocio
- traducción estratégica del PM
- expansión técnica del PO
- ejecución técnica posterior

El flujo principal ya evolucionó para incorporar una conversación iterativa entre Founder y PM antes de producir el `BusinessBrief`, y una aprobación explícita del Founder antes del handoff al PO.

Esta regla ya fue reflejada en:
- documentación del workflow
- límites y ownership de agentes
- workflow contractual en `packages/core/lummevia_core/workflow.py`
- runtime LangGraph en `packages/runtime/lummevia_runtime/graph.py`

Faltaba registrar esa decisión como ADR oficial para mantener trazabilidad arquitectónica y evitar que el gate quede implícito o se diluya en cambios futuros.

## Problema

Sin un gate formal Founder ↔ PM antes del PO:
- el PO puede comenzar a expandir decisiones todavía no aprobadas
- la capa técnica puede absorber incertidumbre de negocio demasiado temprano
- aumenta el retrabajo técnico por briefs incompletos o cambiantes
- se debilita el ownership entre decisión de negocio, alineación estratégica y ejecución técnica
- el runtime puede perder un checkpoint claro de control humano sobre el brief

## Decisión

Lummevia OS adopta un gate formal de aprobación Founder ↔ PM antes de la intervención del PO.

La decisión implica que:
- Founder y PM pueden iterar en conversación para alinear objetivo, alcance y prioridad
- PM actúa como agente estratégico iterativo y produce un `BusinessBrief` en estado `draft`
- Founder approval es el gate formal que habilita el handoff al PO
- el PO no trabaja sobre decisiones no aprobadas
- el PO consume únicamente briefs aprobados explícitamente

## Impacto arquitectónico

### Workflow contractual

El workflow principal incorpora explícitamente los steps:
- `founder_pm_conversation`
- `founder_business_approval`

La secuencia contractual relevante queda:

```text
founder_input
→ founder_pm_conversation
→ pm_business_brief
→ founder_business_approval
→ po_execution_package
```

### Runtime LangGraph

El runtime refleja esta decisión mediante:
- nuevos workflow steps previos al PO
- el nodo `founder_pm_conversation` para modelar la iteración Founder ↔ PM
- el nodo `founder_business_approval` para materializar la aprobación formal del brief
- un edge obligatorio desde `founder_business_approval` hacia `po_execution_package`

Además, el runtime hace cumplir la decisión al requerir que el `BusinessBrief` tenga:
- `business_brief_status = approved`
- `founder_approved = true`

antes de permitir que el nodo del PO produzca el `ExecutionPackage`.

### Impacto en agentes

La decisión redefine responsabilidades operativas:
- PM pasa a ser un agente estratégico iterativo, no un mero traductor lineal
- PO deja de operar sobre intención cruda y consume sólo briefs aprobados
- Founder conserva control formal sobre el cierre del brief de negocio antes del handoff técnico

## Consecuencias

Consecuencias positivas:
- mejora la alineación negocio-técnica antes del trabajo del PO
- reduce retrabajo técnico originado en briefs ambiguos o cambiantes
- fortalece trazabilidad entre intención, draft, aprobación y expansión técnica
- preserva ownership entre Founder, PM y PO
- agrega un checkpoint claro para auditoría documental y runtime

Consecuencias operativas:
- aumenta deliberadamente la latencia inicial del flujo
- agrega un handoff formal adicional antes del arranque técnico
- exige que la documentación, el workflow contractual y el runtime mantengan consistencia sobre el estado de aprobación

## Tradeoffs

Beneficios:
- mayor claridad de negocio antes de la expansión técnica
- menor riesgo de que el PO o el runtime propaguen requerimientos prematuros
- mejor separación entre decisión humana y ejecución técnica

Costos:
- menor velocidad inicial para tareas urgentes
- más pasos explícitos para llegar al `ExecutionPackage`
- necesidad de sostener metadata y validaciones de aprobación en runtime y contratos

## Relación con otras decisiones

Esta decisión:
- complementa [ADR-0001](./0001-usar-langgraph.md) al usar LangGraph para modelar y hacer cumplir el gate
- no altera [ADR-0002](./0002-usar-phoenix-primero.md), pero agrega un checkpoint relevante para observabilidad
- es consistente con [ADR-0003](./0003-modelos-configurables-por-rol.md), ya que PM y PO conservan responsabilidades distintas sin hardcodear capacidades
