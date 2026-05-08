# Integración YouTrack — Lummevia OS

## Objetivo

Definir cómo Lummevia OS utiliza YouTrack como memoria operacional y sistema de coordinación del flujo.

## Principio fundamental

YouTrack es la fuente de verdad operacional.

YouTrack no es:
- repositorio técnico
- runtime de agentes
- observabilidad
- almacén de logs extensos

## Componentes

### YouTrack KB

Contiene contexto estable:
- visión
- workflows
- SOPs
- decisiones operacionales
- reglas de negocio
- contexto de área o proyecto

### YouTrack Issues

Contienen contexto dinámico:
- épicas
- tasks
- bugs
- features
- research
- automation
- ejecución activa
- comentarios de agentes
- links a PRs
- links a trazas

## Artefactos del flujo en YouTrack

YouTrack debe contener o enlazar, según corresponda:
- Business Brief
- Execution Package
- Implementation Package
- Validation Package
- Quality Approval
- BUG issues

## Reglas de uso

Sí debe usarse para:
- coordinación operacional
- comunicación entre agentes
- tracking de estado
- artefactos del flujo
- bugs
- links a ejecución

No debe usarse para:
- guardar logs largos
- duplicar código
- reemplazar documentación técnica del repositorio
- reemplazar Phoenix
- almacenar secretos
- guardar contexto runtime interno del orquestador

## Relación con otras capas

### Con el repositorio

El repositorio conserva la verdad técnica del proyecto.

YouTrack conserva la memoria operacional del trabajo sobre ese proyecto.

### Con GitHub

YouTrack debe enlazar branches, commits y PRs relevantes cuando correspondan al flujo.

### Con Phoenix

YouTrack debe enlazar trazas relevantes cuando aporten trazabilidad operativa.

## Regla de contexto

Cada agente debe leer solamente el contexto necesario para su rol.

Esto reduce:
- ruido
- costo
- contaminación contextual
- errores de interpretación
