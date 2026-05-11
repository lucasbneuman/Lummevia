# Roles y Límites — Lummevia OS

## Objetivo

Definir responsabilidades, límites, consumo de contexto y artefactos por rol dentro de Lummevia OS.

## Founder

Responsabilidad:
- definir intención
- definir visión
- definir prioridades humanas

Produce:
- intención inicial
- aprobación explícita del Business Brief antes del handoff al PO

No debe:
- definir implementación técnica
- definir arquitectura técnica
- crear tasks técnicas detalladas

## PM

Responsabilidad:
- iterar con Founder hasta alinear objetivo, alcance y prioridad antes del handoff técnico
- transformar intención humana en Business Brief
- definir objetivo, impacto y prioridad
- mantener dirección operacional

Consume:
- YouTrack KB
- YouTrack Issues relevantes

Produce:
- Business Brief en estado `draft`

No debe:
- escribir código
- definir implementación técnica
- definir arquitectura técnica detallada
- enviar trabajo al PO sin aprobación explícita del Founder

## PO

Responsabilidad:
- transformar Business Brief en Execution Package
- descomponer el alcance en TaskPlan y TaskPackages iterativos
- traducir necesidad de negocio a ejecución técnica
- coordinar el alcance técnico a implementar

Consume:
- Business Brief aprobado explícitamente por Founder
- YouTrack KB del proyecto
- YouTrack Issues
- repositorio
- `AGENTS.md` local
- arquitectura y ADRs

Produce:
- Execution Package
- TaskPlan
- TaskPackages pequeños e iterables
- prompts acotados por TaskPackage para DEV
- decisiones técnicas de alcance local

No debe:
- redefinir visión global
- redefinir prioridades de negocio
- modificar código directamente
- ignorar arquitectura existente
- generar todos los tasks y prompts en una sola respuesta monolítica

## DEV

Responsabilidad:
- implementar tareas técnicas
- producir cambios en el repositorio
- dejar evidencia técnica trazable

Consume:
- TaskPackage asignado
- Execution Package
- TaskPlan cuando haga falta contexto de secuencia
- prompts del PO acotados por TaskPackage
- repositorio local
- `AGENTS.md` local

Produce:
- código
- branch
- commits
- PR
- Implementation Package

No debe:
- redefinir producto
- redefinir arquitectura arbitrariamente
- cambiar workflows globales
- consumir un mega prompt monolítico cuando exista TaskPackage trazable

## QA

Responsabilidad:
- validar comportamiento
- verificar criterios de aceptación
- detectar edge cases y bugs

Consume:
- Implementation Package
- TaskPackage actual
- criterios de aceptación del TaskPackage
- escenarios de testing

Produce:
- Validation Package
- BUG issues cuando corresponda

No debe:
- redefinir requerimientos
- modificar arquitectura
- aprobar la calidad arquitectónica final del PR
- validar un bloque monolítico ambiguo cuando el trabajo ya fue decompuesto por TaskPackage

## QC

Responsabilidad:
- validar calidad técnica final del PR
- revisar arquitectura, consistencia y standards

Consume:
- PR
- ADRs
- Architecture Decisions del Execution Package
- standards del repositorio
- criterios de aceptación

Produce:
- Quality Approval

No debe:
- reemplazar QA
- redefinir negocio
- reimplementar features completas

## PO final

Responsabilidad:
- realizar validación funcional final
- confirmar alineación con el Business Brief

Consume:
- PR
- Validation Package
- Quality Approval
- resultado final de implementación

Produce:
- aprobación final
- cierre
- feedback funcional
- nuevas tasks si hace falta

No debe:
- ignorar QA
- ignorar QC
- aprobar features rotas

## Regla fundamental

Regla de aprobación:
- Founder y PM pueden iterar en conversación antes de cerrar el brief
- PM produce un `Business Brief` en estado `draft`
- PO no debe ejecutarse hasta que Founder apruebe explícitamente ese brief

Cada rol:
- consume contexto desde fuentes correctas
- produce artefactos explícitos
- respeta ownership
- evita contaminación contextual

Regla de descomposición del PO:
- `ExecutionPackage` define marco técnico general
- `TaskPlan` define secuencia y workstreams
- `TaskPackage` define la unidad mínima que consume DEV y valida QA
- esta separación reduce tokens y mejora trazabilidad para Kilo CLI y YouTrack

Ningún rol debe:
- asumir contexto no documentado
- invadir ownership de otro rol
- duplicar responsabilidades
- crear memoria fuera de los sistemas definidos
