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

No debe:
- definir implementación técnica
- definir arquitectura técnica
- crear tasks técnicas detalladas

## PM

Responsabilidad:
- transformar intención humana en Business Brief
- definir objetivo, impacto y prioridad
- mantener dirección operacional

Consume:
- YouTrack KB
- YouTrack Issues relevantes

Produce:
- Business Brief

No debe:
- escribir código
- definir implementación técnica
- definir arquitectura técnica detallada

## PO

Responsabilidad:
- transformar Business Brief en Execution Package
- traducir necesidad de negocio a ejecución técnica
- coordinar el alcance técnico a implementar

Consume:
- Business Brief
- YouTrack KB del proyecto
- YouTrack Issues
- repositorio
- `AGENTS.md` local
- arquitectura y ADRs

Produce:
- Execution Package
- tasks concretas
- prompts para DEV
- decisiones técnicas de alcance local

No debe:
- redefinir visión global
- redefinir prioridades de negocio
- modificar código directamente
- ignorar arquitectura existente

## DEV

Responsabilidad:
- implementar tareas técnicas
- producir cambios en el repositorio
- dejar evidencia técnica trazable

Consume:
- task asignada
- Execution Package
- prompts del PO
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

## QA

Responsabilidad:
- validar comportamiento
- verificar criterios de aceptación
- detectar edge cases y bugs

Consume:
- Implementation Package
- criterios de aceptación
- escenarios de testing

Produce:
- Validation Package
- BUG issues cuando corresponda

No debe:
- redefinir requerimientos
- modificar arquitectura
- aprobar la calidad arquitectónica final del PR

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

Cada rol:
- consume contexto desde fuentes correctas
- produce artefactos explícitos
- respeta ownership
- evita contaminación contextual

Ningún rol debe:
- asumir contexto no documentado
- invadir ownership de otro rol
- duplicar responsabilidades
- crear memoria fuera de los sistemas definidos
