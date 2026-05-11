# ADR-0005 — Descomponer la salida del PO en ExecutionPackage, TaskPlan y TaskPackages

## Estado

Acordado.

## Contexto

El flujo inicial permitía que el `PO` expandiera el `BusinessBrief` aprobado en una única respuesta grande, mezclando:
- alcance técnico general
- checklist de trabajo
- prompts de implementación
- contexto de testing
- múltiples tareas potenciales

Ese enfoque monolítico es frágil para una integración futura con Kilo CLI porque:
- aumenta consumo de tokens
- hace más difícil mantener foco por iteración
- mezcla planeamiento y ejecución en un solo artefacto
- complica trazabilidad entre intención, task puntual y validación
- vuelve más difusa la sincronización futura con YouTrack

## Problema

Cuando el `PO` intenta generar todos los tickets, tareas y prompts en una única ejecución grande:
- el contexto crece demasiado rápido
- DEV recibe un prompt excesivo y menos accionable
- QA valida un bloque ambiguo en lugar de una unidad clara
- el runtime pierde checkpoints intermedios útiles
- YouTrack corre riesgo de reflejar paquetes poco granulares

## Decisión

Lummevia OS adopta un flujo de descomposición del `PO` por fases:

1. `ExecutionPackage`
2. `TaskPlan`
3. `TaskPackages` iterativos

La secuencia contractual relevante queda:

```text
founder_business_approval
→ po_execution_package
→ po_task_plan
→ po_task_packages
→ dev_implementation
→ qa_validation
```

## Detalle de la decisión

### ExecutionPackage

Mantiene el contexto técnico paraguas:
- historia técnica
- criterios globales
- edge cases
- escenarios de testing
- decisiones arquitectónicas locales

### TaskPlan

Introduce una capa liviana de coordinación:
- workstreams
- ids de `TaskPackages`
- notas de secuencia
- riesgos

### TaskPackage

Define la unidad mínima que ejecuta el runtime:
- objetivo concreto
- referencias de contexto
- criterios de aceptación
- restricciones
- prompt pequeño y enfocado
- artefactos esperados

## Beneficios

- reduce tokens y tamaño de prompt para Kilo CLI
- mejora foco operativo de DEV
- permite que QA valide por unidad acotada
- mejora trazabilidad entre PO, runtime y artefactos
- facilita futuras actualizaciones pequeñas en YouTrack
- agrega checkpoints intermedios claros en runtime y observabilidad

## Tradeoffs

- agrega dos artefactos más al flujo
- incrementa la latencia inicial antes de DEV
- obliga a mantener consistencia entre `ExecutionPackage`, `TaskPlan` y `TaskPackages`
- introduce una capa adicional de estado en runtime

## Impacto en Kilo CLI

Kilo CLI deja de depender de un mega prompt del `PO`.

En cambio, consumirá `TaskPackages` pequeños, secuenciales y trazables. Esto mejora foco, reduce contexto innecesario y simplifica iteraciones futuras.

## Impacto en YouTrack

Todavía no se crean tickets reales ni integración real.

Sin embargo, la descomposición deja preparado el modelo para que YouTrack refleje:
- un issue paraguas
- un plan de secuencia
- paquetes pequeños de trabajo

Esto favorece trazabilidad y evita artefactos operacionales demasiado grandes o ambiguos.

## Impacto en runtime

El runtime simulado ahora:
- representa `po_execution_package`
- representa `po_task_plan`
- representa `po_task_packages`
- conserva todos los `TaskPackages` en estado
- ejecuta sólo el primer `TaskPackage` como MVP

No se introduce todavía:
- ejecución paralela
- múltiples ramas reales
- integración real con Kilo CLI
- integración real con YouTrack

## Consecuencias

Consecuencias positivas:
- flujo más modular
- menor riesgo de expansión monolítica del PO
- mejor auditoría de handoffs

Consecuencias operativas:
- más artefactos para serializar y testear
- más metadata para mantener consistente en runtime

## Relación con otras decisiones

Esta decisión:
- preserva el gate formal de [ADR-0004](./0004-founder-pm-approval-gate.md)
- complementa [ADR-0001](./0001-usar-langgraph.md) al agregar nuevos nodos secuenciales
- no cambia la política de modelos configurables definida en [ADR-0003](./0003-modelos-configurables-por-rol.md)
