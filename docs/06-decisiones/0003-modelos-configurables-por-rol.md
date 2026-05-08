# ADR-0003 — Modelos configurables por rol

## Estado

Acordado.

## Contexto

Lummevia OS utiliza múltiples agentes con responsabilidades distintas:
- PM
- PO
- DEV
- QA
- QC

Cada rol requiere distinta capacidad, costo, latencia y nivel de reasoning.

## Decisión

Los modelos IA serán configurables por:
- rol
- proyecto
- entorno

Los agentes no deben conocer directamente:
- modelos
- providers
- configuraciones específicas

La resolución de modelos será responsabilidad del `Model Router`.

## Objetivos

Permitir:
- cambiar modelos sin modificar agentes
- cambiar providers sin modificar workflows
- usar distintos modelos según capacidad requerida
- reducir costos runtime
- implementar fallbacks
- soportar múltiples entornos
- soportar múltiples proyectos

## Regla arquitectónica

Los agentes consumen capacidades.

No consumen:
- modelos específicos
- providers específicos

Toda llamada debe registrar:
- provider
- modelo
- fallback
- agente
- rol
- proyecto
- latencia
- costo estimado
- resultado

## Prohibiciones

No se permite:
- hardcodear modelos dentro de agentes
- acoplar agentes a providers específicos
- cambiar modelos sin trazabilidad
- ocultar fallbacks
- mezclar configuración runtime con lógica de negocio
