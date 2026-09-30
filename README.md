# Tato Calistenia

Runtime local del setter de Instagram de Tato Calistenia y VALKA. Lee el historial completo, devuelve el próximo DM, prepara una cola interna de leads conocidos y genera cierres EOD revisables.

En cada chat nuevo abierto dentro de este proyecto, `AGENTS.md` dirige al skill v3 y el caso se reconstruye desde el runtime local y la entrada actual. No depende del historial de otro chat.

## Uso en Codex y Antigravity

Codex es la plataforma principal. Según la documentación oficial consultada por el padre, construye la cadena de `AGENTS.md` una vez por sesión y descubre skills en `.agents/skills` hasta la raíz del repositorio; carga instrucciones completas al usarlos. Invocar `$tato-calistenia` explícitamente ayuda a activar el skill. Después de cambiar `AGENTS.md`, abrir una sesión nueva. `agents/openai.yaml` admite metadatos de invocación; no se modifican aquí.

Fuentes oficiales: [AGENTS.md](https://developers.openai.com/codex/guides/agents-md) y [skills](https://developers.openai.com/codex/skills). La integración nativa de Antigravity no está verificada: cargar manualmente `AGENTS.md`, el skill y las referencias requeridas. No se promete sandbox, enforcement de herramientas, extensión ni ajuste global del host.

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
- [Tracking CRM y EOD](.agents/skills/tato-calistenia/references/tracking-eod.md) — cierre con evidencia aportada y límites del registro manual.
- [Tracker local](.agents/skills/tato-calistenia/scripts/crm_tracker.py) — utilidad histórica/manual conservada; no se ejecuta durante conversaciones o cierres.
- [Fixtures forward](.agents/skills/tato-calistenia/assets/forward-cases.json) — escenarios y expectativas estructuradas.
- [Diseño](docs/sdd/call-first-dm.md) — especificación y criterios de aceptación.

## Posicionamiento

- Público prioritario 40+; 45+ es el avatar ideal.
- Adultos menores pueden avanzar si existe encaje.
- La calistenia es el vehículo para ganar capacidad, control, confianza y autonomía.
- Dominadas, pino y muscle-up son hitos posibles, no el destino universal.
- El producto vigente es coaching 1 a 1 online de 90 días por USD 300; el precio se explica solamente en llamada.

## Flujo

1. Interpretar modo e historial completo aportado, sin consultar ni escribir bases ni crear leads.
2. Construir el estado efímero y resolver seguridad o bloqueos operativos prioritarios.
3. Recorrer contexto, destino, brecha, sentido y disposición sin formulario; con objetivo y brecha suficientes, conocer la realidad cotidiana antes de la ruta si todavía no consta.
4. Presentar una ruta A→B contextualizada y esperar aceptación.
5. Invitar a llamada desde el destino real sin filtro económico proactivo.
6. Tras la aceptación, enviar el Cal.com oficial y verificar la reserva.

Si el lead pregunta precio, se aclara que es un acompañamiento pago de 90 días y que el detalle lo vemos en la llamada; Tato habla siempre en primera persona y USD 300 sigue siendo información interna.

El seteo aporta valor al comprender y orientar, no al improvisar correcciones técnicas por texto. Una lectura breve de lo que requiere evaluación conecta con la evidencia pendiente, sin consejo seguido de pregunta genérica. Las dudas concretas reciben respuestas generales respaldadas; seguridad y puertas de llamada se conservan. El agente no regala programación, diagnostica ni usa vulnerabilidad para vender.

Reconocimiento, lectura y puente se separan en bloques naturales sin coma final. Se conservan comas internas y vocativas, nombres propios con mayúscula e inicios en minúscula; no se usan diminutivos forzados ni comillas simples. El puente puede ir en una línea y la pregunta conectada en la siguiente, sin convertirlo en plantilla.

Una cifra aislada no siempre explica la mejora deseada: aclarar una sola cosa útil antes de realidad cotidiana o ruta si sigue ambigua; si ya está explicada, avanzar. El sentido puede ser corporal, funcional o un desafío técnico, sin exigir emoción. Entrenar con constancia o tener tiempo libre no demuestra voluntad de proceso guiado; voluntad explícita o apertura concreta a aplicar acompañamiento sí, sin repreguntar lo conocido. País y nacionalidad no son filtros económicos.

Seguridad y cierres prevalecen sobre agenda previa. Responder bloqueos, objeciones y preguntas antes del avance automático, preservar ruta y llamada aceptadas y retomar el paso pendiente tras resolver el freno, sin pitch repetido. Precio recibe respuesta respetuosa, no un prefacio obligatorio ni gramática forzada con `conmigo`. Al agendar, enlace en línea propia, elección de día/hora y una pregunta natural de confirmación; mirar horarios no es reservar y la reserva confirmada cierra sin pregunta.

Una respuesta puede completar varias fases. El agente salta lo ya resuelto y elige la primera evidencia que realmente cambia la decisión.

La prueba de intención del motor distingue aporte de paráfrasis: conserva los calificadores del hecho y elige una pregunta cuya respuesta cambie una decisión pendiente, sin forzar cue, rapport ni prefacio. Un detalle técnico no reabre una brecha suficiente ni dispara una pregunta cotidiana por reflejo. La ruta explica cómo una ayuda real responde a la brecha de ese caso.

La realidad cotidiana se abre con una transición conectada al historial: reconocimiento específico, un puente breve cuando evite un salto brusco y una pregunta abierta sobre qué hace en su día a día, sin ofrecer categorías ocupacionales. Los ejemplos aprobados calibran intención y flujo, no texto para copiar. La respuesta sirve para comprender horarios, autonomía y sostén, no para inferir dinero ni descartar estudiantes. Si una rutina suficiente ya consta, no se repregunta. Cuando esa realidad, el destino y la brecha ya están claros pero falta disposición, se puede preguntar directamente si está para comprometerse con un proceso hacia su resultado, sin presión.

## Modos de salida

- `prospect_dm`: únicamente el siguiente mensaje listo para copiar, línea por línea, un movimiento y una pregunta de dirección obligatoria al final de toda conversación activa; breve por defecto y proporcional cuando el lead se abre; puede usar un puente coloquial con el nombre conocido cuando mejore el ritmo, nunca como plantilla; los cierres excepcionales quedan sin pregunta.
- `outbound_batch`: cola interna de leads conocidos con elegibilidad, prioridad, fase, siguiente acción y un DM máximo por elegible; nunca envía.
- `call_brief`: hechos, pendientes y ángulo para Tato, únicamente cuando Maxi lo solicita.
- `eod_review`: abre con `Personas distintas contactadas hoy`, presenta los nueve campos y espera energía, sensación y aprobación; las burbujas quedan fuera del reporte cotidiano y nunca envía.
- `maintenance`: respuesta técnica para revisar, probar o modificar el runtime.

## Validación local

```powershell
python .agents/skills/tato-calistenia/scripts/validate_runtime.py
python -B .agents/skills/tato-calistenia/scripts/test_runtime_no_tracking.py
python -B .agents/skills/tato-calistenia/scripts/test_runtime_direction.py
git diff --check
```

El validador usa solo la biblioteca estándar de Python. Comprueba frontmatter, referencias, módulos, fixtures v3, matriz curada, privacidad y reglas comerciales; no ejecuta el tracker. Sus pruebas históricas se mantienen separadas del runtime. Los tests de dirección comprueban el contrato declarado de rúbrica, cobertura, enum de modos y precedencia, no evalúan semánticamente mensajes.

Las pruebas individuales se evalúan sobre fidelidad, fase, naturalidad, posicionamiento y seguridad; exigen 8/10, fidelidad/fase/naturalidad/seguridad completas e intención aprobada como condición semántica no compensable. Los lotes se evalúan sobre elegibilidad, prioridad, continuidad, mensaje y seguridad. La calidad requiere pruebas forward frescas: el ejecutor recibe historial y skill sin fase ni respuesta esperada, y el evaluador contrasta después la salida con los criterios. La validación estática no demuestra intención ni calidad del DM; la conversión se confirma con conversaciones reales.

## Gobernanza y correcciones

Este README, `AGENTS.md` y el diseño son resúmenes, no nuevos dueños de reglas. [El mapa](.agents/skills/tato-calistenia/assets/source-governance.json) asigna cada dominio y separa traducciones aprobadas de fuentes históricas o pendientes. [La cobertura de auditoría](docs/source-audit-status.md) distingue lectura de inventario.

[Correcciones controladas](.agents/skills/tato-calistenia/references/feedback-controlado.md) define el ciclo de mantenimiento. `Me gusta más así` afecta solo la instancia; no se guardan chats ni frases. Antes de cualquier escritura durable se muestra principio, alcance, excepción, contraste y regla reemplazada para aprobación explícita actual. El ledger vacío no inventa aprobaciones ni activa reglas. Revertir exige editar el dueño real; cambiar un estado no es rollback.

La validación de gobernanza se incluye por defecto sin CRM. Sus tests se ejecutan con `python -B .agents/skills/tato-calistenia/scripts/test_runtime_governance.py`. Son controles estructurales, no prueba de identidad humana ni evaluación automática de DMs. La guardia mecánica de DM pertenece a otra unidad.

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
- El agente no tiene dependencia de bases locales ni conexión al CRM web; no agregar RAG, persistir chats crudos ni automatizar envíos de DMs o formularios.

## Instalación

```bash
git clone https://github.com/GosGuru/tato-calistenia.git
cd tato-calistenia
```

La carpeta `.agents` es oculta. En Finder se muestra con `Command + Shift + .`.

## Registro manual y cierre EOD

El registro automático del agente está eliminado. `prospect_dm`, `outbound_batch` y `call_brief` usan el historial aportado, sin leer ni escribir bases locales, crear leads, reconstruir eventos persistentes ni guardar borradores. El CRM web se gestiona manualmente en `https://crm-setter-v2.vercel.app`; no existe un puente del agente ni sincronización con Instagram o ManyChat.

El EOD se prepara solo ante pedido explícito o activación de una programación ya autorizada, a partir de evidencia aportada para ese cierre, sin consultas automáticas a bases ni ejecución del agregador. Conserva los nueve campos y abre con `Personas distintas contactadas hoy`: cada identidad con envío observado o verificado cuenta una vez. Los borradores nunca cuentan; fechas desconocidas quedan pendientes y la cobertura siempre es parcial. Energía y sensación quedan pendientes de Maxi y el formulario requiere aprobación explícita.

No se cambia la programación. Las bases históricas, exportaciones y utilidades del tracker se conservan sin migrar, borrar ni modificar. Solo un pedido explícito de mantenimiento con alcance definido permite consultarlas o utilizarlas; redactar un DM o pedir un EOD no autoriza ese acceso. Detalles en `.agents/skills/tato-calistenia/references/tracking-eod.md`.

## Calibración de conexión conversacional

La voz distingue reentrada tras días de continuidad inmediata según fechas disponibles: saludar al retomar sin reiniciar la fase, y no repetir saludos por reflejo. El saludo social no cuenta como una segunda pregunta de calificación; queda una sola pregunta sustantiva final, salvo cierres excepcionales. Reconocer y enlazar con naturalidad sin muletillas, decisiones por el lead ni garantías. Solo cuando la llamada esté habilitada, proponer una reunión de auditoría con iniciativa cálida y propósito específico, sin repetir una invitación ya aceptada. No usar emojis; el detalle y sus excepciones pertenecen a `voz-escrita-tato.md`.
