# Integración GitHub — Lummevia OS

## Objetivo

Definir cómo Lummevia OS utiliza GitHub para versionado, branches, commits, pull requests y validación técnica sobre cambios.

## Principio fundamental

GitHub es la plataforma de cambios y revisión técnica del repositorio.

GitHub contiene:
- branches
- commits
- pull requests
- checks
- historial de cambios

GitHub no reemplaza:
- la memoria operacional de YouTrack
- la documentación técnica del repositorio
- la observabilidad de Phoenix

## Responsabilidades

GitHub debe registrar:
- implementación técnica versionada
- cambios realizados
- PRs
- validaciones sobre PR
- historial de ejecución técnica

## Flujo en GitHub

```text
DEV
↓
branch
↓
commits
↓
PR
↓
QA validado
↓
QC validado
↓
PO final validado
↓
merge
```

## Reglas de uso

### Branches

Cada task debe generar:
- branch propia
- scope claro
- referencia al issue correspondiente

### Commits

Los commits deben:
- ser trazables
- representar cambios claros
- relacionarse con tasks o bugs

### Pull Requests

Todo cambio validado debe materializarse en un PR.

El PR debe poder relacionarse con:
- task original
- bugs relacionados
- Execution Package
- Validation Package
- Quality Approval

Los links y referencias operacionales deben quedar registrados en YouTrack.

## Relación con otras capas

### Con YouTrack

YouTrack conserva la memoria operacional del flujo.

GitHub aporta la evidencia técnica de cambios, branches, commits y PRs.

### Con Phoenix

Phoenix conserva trazas, prompts, errores, latencia y costos.

GitHub debe poder relacionarse con runs y trazas mediante metadata compartida cuando corresponda.

## Regla final

GitHub es evidencia técnica de cambios.

La verdad técnica del proyecto sigue viviendo en el repositorio y su documentación local.
