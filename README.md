# Tato Calistenia

Runtime local del agente de Instagram DM de Tato Calistenia y VALKA. Recibe el historial de un prospecto y devuelve un unico DM listo para copiar y pegar.

## Arquitectura

- [Skill principal](.agents/skills/tato-calistenia/SKILL.md) — entrada y enrutamiento de recursos.
- [Motor agentico](.agents/skills/tato-calistenia/references/motor-agentico.md) — estado interno, prioridades, ciclo de decision y revision final.
- [Voz escrita de Tato](.agents/skills/tato-calistenia/references/voz-escrita-tato.md) — autoridad, brevedad y ritmo humano de Instagram; separada de la voz oral de los LOOM.
- [Operativa de DM](.agents/skills/tato-calistenia/references/operativa-dm.md) — ramas comerciales, objeciones, agenda, seguimiento y ejemplos.
- [Contexto maestro](.agents/skills/tato-calistenia/references/contexto-maestro.md) — identidad, oferta, metodo, seguridad y limites.
- [Biblioteca tecnica](.agents/skills/tato-calistenia/references/biblioteca-tecnica-tato.md) — patrones curados de Tato para dominadas, escapulas, muscle-up, empujes, pino y piernas.
- [Guia de primeras 5 dominadas](.agents/skills/tato-calistenia/assets/guia-primeras-5-dominadas.pdf) — activo que solo se abre cuando la tarea lo requiere.
- [Configuracion del agente](.agents/skills/tato-calistenia/agents/openai.yaml) — metadatos para Codex.
- [Diseno del flujo](docs/sdd/call-first-dm.md) — especificacion y criterios de aceptacion actuales.

## Flujo

1. Interpretar la instruccion de Maxi y el historial completo.
2. Construir un estado interno con hechos, X, encaje, etapa, interes, excepciones y gol del turno.
3. Resolver primero salud, minoridad, llamada aceptada, objeciones o cierres.
4. Cargar solamente las referencias necesarias para la rama.
5. Redactar con la voz escrita de Tato, sin trasladar la cadencia oral de los LOOM.
6. Revisar historial, certeza, etapa, ayuda gratuita, voz y formato antes de entregar.

El agente no expone ese razonamiento. La salida operativa contiene unicamente el DM final.

## Validacion local

```powershell
python .agents/skills/tato-calistenia/scripts/validate_runtime.py
```

El validador usa solo la biblioteca estandar de Python. Comprueba UTF-8, frontmatter, referencias, archivos requeridos, marcadores del flujo y ausencia de timestamps de transcripciones en la biblioteca tecnica.

Los cambios de comportamiento tambien se prueban con casos forward independientes. Una validacion local demuestra coherencia del runtime, no mejora de conversion; eso se mide con conversaciones reales.

## Mantenimiento

- Curar los LOOM en reglas o patrones generalizables; no copiar transcripciones completas.
- Usar los LOOM para criterio tecnico y pedagogico, no como plantilla de redaccion.
- Mantener hechos, hipotesis y personalizacion como niveles distintos de certeza.
- Conservar un solo movimiento y como maximo una pregunta por DM.
- Actualizar skill, motor, referencias y documentacion como una unidad cuando cambia el flujo.
- Los backups `*.bak` permanecen locales y estan excluidos de Git.

## Instalacion

```bash
git clone https://github.com/GosGuru/tato-calistenia.git
cd tato-calistenia
```

La carpeta `.agents` es oculta. En Finder se muestra con `Command + Shift + .`.
