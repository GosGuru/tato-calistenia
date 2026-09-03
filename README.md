# Tato Calistenia

Runtime local del setter de Instagram de Tato Calistenia y VALKA. Lee el historial completo, devuelve el próximo DM, prepara una cola interna de leads conocidos o, solo bajo pedido explícito, genera un brief para la llamada.

En cada chat nuevo abierto dentro de este proyecto, `AGENTS.md` dirige al skill v3 y el caso se reconstruye desde el runtime local y la entrada actual. No depende del historial de otro chat.

## Arquitectura

- [Skill principal](.agents/skills/tato-calistenia/SKILL.md) — activación, carga progresiva y modos de salida.
- [Motor agéntico](.agents/skills/tato-calistenia/references/motor-agentico.md) — estado, precedencia, ciclo de decisión y revisión final.
- [Operativa de DM](.agents/skills/tato-calistenia/references/operativa-dm.md) — posicionamiento y siete fases adaptativas.
- [Operativa de maseteo](.agents/skills/tato-calistenia/references/operativa-maseteo.md) — elegibilidad, prioridad y cola `outbound_batch` sin envíos.
- [Voz escrita](.agents/skills/tato-calistenia/references/voz-escrita-tato.md) — redacción desde criterio y huella agregada de seis meses de mensajes y audios propios.
- [Precio, objeciones y agenda](.agents/skills/tato-calistenia/references/objeciones-agenda.md) — dinero solo si el lead lo trae, modalidad, follow-up y Cal.com.
- [Handoff de llamada](.agents/skills/tato-calistenia/references/handoff-llamada.md) — formato del brief interno.
- [Contexto maestro](.agents/skills/tato-calistenia/references/contexto-maestro.md) — identidad, avatar, oferta, precio interno, privacidad y salud.
- [Biblioteca técnica](.agents/skills/tato-calistenia/references/biblioteca-tecnica-tato.md) — patrones técnicos curados.
- [Casos de calibración](.agents/skills/tato-calistenia/references/casos-calibracion.md) — decisiones esperadas sin respuestas literales y rúbrica.
- [Criterio de fuentes curadas](.agents/skills/tato-calistenia/references/criterio-fuentes-curadas.md) — matriz de mantenimiento `Rescatar`/`Rechazar`; no es runtime prospect-facing.
- [Fixtures forward](.agents/skills/tato-calistenia/assets/forward-cases.json) — escenarios y expectativas estructuradas.
- [Diseño](docs/sdd/call-first-dm.md) — especificación y criterios de aceptación.

## Posicionamiento

- Público prioritario 40+; 45+ es el avatar ideal.
- Adultos menores pueden avanzar si existe encaje.
- La calistenia es el vehículo para ganar capacidad, control, confianza y autonomía.
- Dominadas, pino y muscle-up son hitos posibles, no el destino universal.
- El producto vigente es coaching 1 a 1 online de 90 días por USD 300; el precio se explica solamente en llamada.

## Flujo

1. Interpretar modo e historial completo.
2. Construir el estado interno y resolver seguridad o bloqueos operativos prioritarios.
3. Recorrer contexto, destino, brecha, sentido y disposición sin formulario.
4. Presentar una ruta A→B contextualizada y esperar aceptación.
5. Invitar a llamada desde el destino real sin filtro económico proactivo.
6. Tras la aceptación, enviar el Cal.com oficial y verificar la reserva.

Si el lead pregunta precio, se aclara que es un acompañamiento pago de 90 días y que el detalle se conversa con Tato en la llamada; USD 300 sigue siendo información interna.

Una duda técnica recibe una sola lectura o cue y vuelve a la fase comercial pendiente. El agente no regala programación, diagnostica ni usa vulnerabilidad para vender.

Una respuesta puede completar varias fases. El agente salta lo ya resuelto y elige la primera evidencia que realmente cambia la decisión.

## Modos de salida

- `prospect_dm`: únicamente el siguiente mensaje listo para copiar, línea por línea, un movimiento y una pregunta de dirección obligatoria al final de toda conversación activa; breve por defecto y proporcional cuando el lead se abre; los cierres excepcionales quedan sin pregunta.
- `outbound_batch`: cola interna de leads conocidos con elegibilidad, prioridad, fase, siguiente acción y un DM máximo por elegible; nunca envía.
- `call_brief`: hechos, pendientes y ángulo para Tato, únicamente cuando Maxi lo solicita.
- `maintenance`: respuesta técnica para revisar, probar o modificar el runtime.

## Validación local

```powershell
python .agents/skills/tato-calistenia/scripts/validate_runtime.py
git diff --check
```

El validador usa solo la biblioteca estándar de Python. Comprueba frontmatter, referencias, módulos, 50 fixtures v3, decisiones de calibración sin plantillas literales, rúbricas individuales y de lote, matriz curada, privacidad, URL autorizada, ausencia del filtro económico proactivo, precio no expuesto y ausencia de reglas anteriores.

Las pruebas individuales se evalúan sobre fidelidad, fase, naturalidad, posicionamiento y seguridad. Los lotes se evalúan sobre elegibilidad, prioridad, continuidad, mensaje y seguridad. La validación local demuestra coherencia; la conversión se confirma con conversaciones reales.

## Mantenimiento

- Usar los LOOM para criterio técnico y pedagógico, no como plantilla de redacción.
- Mantener las transcripciones fuera del runtime; copiar solo criterio aprobado y sanitizado.
- No cargar respuestas modelo, ritmos posibles ni bancos de frases en `prospect_dm`; Sol decide el contenido y construye la redacción desde el caso.
- Las cuatro fichas Trainology aprobadas el 2026-08-31 son operativas mediante su traducción prudente en la biblioteca técnica y sus fixtures; cualquier candidato futuro permanece inactivo.
- Mantener hechos, hipótesis y personalización como niveles distintos.
- No copiar transcripciones ni datos identificables.
- Sincronizar runtime, documentación, fixtures y validador en cada cambio conductual.
- Mantener backups, chats, cachés y temporales fuera de Git.
- No afirmar publicación o despliegue sin evidencia remota.
- No agregar RAG, base de datos ni automatización de envíos a esta versión.

## Instalación

```bash
git clone https://github.com/GosGuru/tato-calistenia.git
cd tato-calistenia
```

La carpeta `.agents` es oculta. En Finder se muestra con `Command + Shift + .`.
