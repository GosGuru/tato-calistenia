# Arquitectura del setter Tato Calistenia

Fecha: 2026-09-02
Estado: implementación local v3

## Objetivo

Producir el próximo movimiento natural de cada conversación y entregar a Tato leads mejor preparados. La calistenia se presenta como vehículo hacia una capacidad vital elegida por el lead; la llamada llega después de una aceptación positiva de la ruta, sin filtro económico proactivo.

## Principios

- El historial completo manda sobre el último mensaje.
- La calificación es adaptativa y nunca un formulario.
- Una respuesta equivale a un movimiento y una pregunta sustantiva máxima; el saludo social de reentrada no cuenta como calificación.
- La decisión interna se completa antes de redactar; la redacción se construye de cero y no se recupera desde ejemplos.
- La prueba de intención del motor exige utilidad concreta y una pregunta cuya respuesta cambie una decisión pendiente, sin eco más interrogación vaga ni cue, rapport o prefacio obligatorios.
- La brevedad es el valor por defecto, pero la extensión aumenta cuando la apertura del lead necesita reconocimiento proporcional.
- Toda conversación activa termina con una pregunta de dirección; los cierres excepcionales quedan sin pregunta.
- Un puente coloquial breve con el nombre conocido puede separar reconocimiento y pregunta cuando mejora el ritmo; no es obligatorio ni autoriza inventar nombres o copiar una fórmula.
- La habilidad técnica puede ser un hito, no el destino universal.
- La autoridad de Tato nace del criterio, no de presión o estatus.
- El DM diagnostica comercialmente lo mínimo; la llamada profundiza y cierra.
- Los LOOM aportan pedagogía curada, no voz literal ni datos privados.
- El corpus escrito propio gobierna la forma; los audios salientes de Tato aportan criterio y vocabulario después de una curación privada, nunca recuperación literal.
- Las fuentes externas solo aportan criterios aprobados; su matriz de mantenimiento no gobierna respuestas.
- El maseteo organiza leads conocidos y nunca automatiza envíos.
- El agente no consulta ni escribe el CRM; el registro web es manual y el EOD usa evidencia aportada para revisión.
- Cada chat nuevo del workspace reconstruye la v3 desde el skill y sus referencias, sin depender de conversaciones anteriores.

## Gobernanza de mantenimiento

Este diseño resume el runtime, no introduce autoridad duplicada. `assets/source-governance.json` del skill asigna dueños por dominio; `references/feedback-controlado.md` gobierna correcciones durables solo en mantenimiento. Distinguir edición local, preferencia de estilo y regla general. Mostrar principio exacto, alcance, excepción, contraste sintético y regla reemplazada antes de obtener aprobación actual explícita para escribir. Elogios o transcripciones históricas no autorizan promoción.

`assets/feedback-ledger.json` empieza vacío y no se carga como runtime. Sus estados documentan mantenimiento, no activan instrucciones. Aplicar o revertir requiere editar el dueño real y verificar; metadatos no prueban identidad humana. La CLI es de solo lectura y el validador normal integra sus controles sin CRM. `docs/source-audit-status.md` distingue cobertura reportada, inventario y material no localizado. Los cursos inventariados no se presentan como leídos.

Codex requiere una sesión nueva tras cambiar la cadena AGENTS; el README documenta invocación explícita del skill. Antigravity se limita a carga manual, sin integración nativa verificada ni promesa de sandbox. Estas reglas de prosa no fuerzan herramientas.

## Componentes

### `SKILL.md`

Contrato LLM-first, modos de salida y carga progresiva. Usa frontmatter compatible con `skill-creator`.

### `motor-agentico.md`

Único dueño de estado, puertas prioritarias, fases, composición y revisión silenciosa.

### `operativa-dm.md`

Fuente normativa de posicionamiento, evidencia comercial, ruta personalizada y criterio de llamada.

### `operativa-maseteo.md`

Define elegibilidad, prioridad, aislamiento de estado y salida interna de `outbound_batch`.

### `voz-escrita-tato.md`

Define ritmo, escucha visible, autoridad, preguntas, ruta e invitación sin duplicar decisiones comerciales.

### `objeciones-agenda.md`

Resuelve precio o dinero cuando el lead los trae, modalidad, objeciones, follow-ups y agenda oficial.

### `handoff-llamada.md`

Define un brief factual con ángulo recomendado cuando Maxi lo pide. No produce guiones.

### `contexto-maestro.md`

Fuente estable de identidad, avatar, oferta, precio interno, método, privacidad y seguridad.

### `biblioteca-tecnica-tato.md`

Patrones técnicos curados con separación entre hecho, hipótesis y personalización. Incluye los cuatro criterios Trainology aprobados sobre entrevista, biomecánica, individualización y comunicación sobre dolor.

### `casos-calibracion.md` y `assets/forward-cases.json`

Decisiones esperadas, hard fails, escenarios y expectativas para verificación independiente. No contienen una respuesta prospect-facing para copiar.

### `criterio-fuentes-curadas.md`

Matriz de mantenimiento para Julio Rondinelli, Psychoselling, De 0 a 10 y Trainology. Registra `Rescatar`, `Rechazar`, traducción Tato, riesgo y aprobación sin incorporar transcripciones.

### `tracking-eod.md`, `crm-event.schema.json` y `crm_tracker.py`

`tracking-eod.md` define el cierre con evidencia aportada. El esquema y el tracker se conservan como utilidades históricas/manuales, fuera del runtime conversacional y del EOD. Un borrador nunca cuenta como envío.

## Interfaces

### `prospect_dm`

Salida por defecto:

- solo el próximo DM;
- una idea por línea;
- separar reconocimiento, lectura y puente en bloques naturales sin coma final; conservar comas internas y vocativas, nombres propios con mayúscula e inicios en minúscula; evitar diminutivos forzados y comillas simples;
- un movimiento;
- longitud proporcional al aporte del lead, sin una cuota rígida de líneas;
- exactamente una pregunta de dirección al final si la conversación sigue activa;
- ninguna pregunta si corresponde un cierre excepcional;
- sin análisis, etiquetas ni alternativas;
- sin signos de apertura;
- sin dos puntos en prosa;
- URL oficial permitida como única excepción.

### `outbound_batch`

Solo para seguidores, comentarios, recursos, conversaciones y reactivaciones verificables:

- clasifica `eligible`, `needs_context` o `skip`;
- prioriza bloqueo operativo, inbound, fase pendiente, primer follow-up, apertura y segundo follow-up;
- mantiene un estado independiente por lead;
- devuelve razón, prioridad, fase, siguiente acción y un único DM solo para elegibles;
- nunca envía ni afirma envío.

### `call_brief`

Solo por pedido explícito. Devuelve destino, situación, brecha, sentido, realidad cotidiana, disposición, ruta aceptada, salud, objeciones, pendientes, lenguaje útil, ángulo y datos que no deben repetirse.

### `eod_review`

Genera los nueve campos del cierre desde evidencia aportada, sin consultar bases ni ejecutar el agregador, mantiene contactos y burbujas separados, pide energía y sensación y espera aprobación. No envía el formulario.

### `maintenance`

Respuesta técnica normal. Un cambio de comportamiento obliga a sincronizar runtime, documentación, fixtures y validador.

## Estado interno

El motor resuelve sin mostrar:

- `modo`;
- `lead_key`, fuente y contenido de origen;
- `instruccion_maxi`;
- `hechos_confirmados` y `datos_no_confirmados`;
- `situacion_actual`;
- `destino_funcional` y `destino_vital`;
- `brecha_e_intentos`;
- `sentido_personal`;
- `disposicion_practica`;
- `ruta_tato` y `aceptacion_ruta`;
- `senal_economica`, únicamente cuando el lead trae dinero o precio;
- `fase` y `subestado_conversion`;
- `rama_tecnica`;
- `excepciones`;
- `followups_realizados`;
- `gol_del_turno` y `siguiente_movimiento`.

En lote agrega `lead_ref`, fuente, elegibilidad, motivo, prioridad, bloqueo operativo y contacto duplicado, reconstruidos por separado para cada lead.

## Precedencia

1. Emergencia o necesidad fuera de alcance.
2. Menor confirmado, rechazo claro, inversión explícitamente imposible o incompatibilidad confirmada.
3. Bloqueo operativo verificable.
4. Objeción activa o pregunta concreta.
5. Reserva confirmada sin excepción activa.
6. Llamada aceptada o agenda enviada sin freno activo.
7. Rama técnica, comercial o conversacional normal.

Una reserva anterior no anula una excepción nueva. Tras resolver un freno, conservar ruta y llamada ganadas y retomar el paso pendiente si corresponde, sin repetir pitch ni recalificar.

Esta precedencia impide vender durante una emergencia, seguir calificando después de una aceptación o ignorar un freno activo.

## Calificación

Las siete fases son:

`contexto -> destino -> brecha -> sentido -> disposición -> ruta -> conversión`

El historial puede completar varias. El agente salta las fases resueltas, pregunta por la primera evidencia relevante que falte y nunca pregunta para llenar una casilla.

Conservar impulso, asistencia, agarre, capacidad parcial y autoevaluación cuando cambien la lectura: no inferir una repetición estricta por ausencia de banda. Una brecha suficiente no exige conocer la causa exacta; no reabrirla por cada detalle técnico ni volver a formular un objetivo ya respondido.

### Contexto

Punto de partida y restricciones reales.

### Destino

Capacidad o hito y, si existe, lo que permitiría vivir, sentir o compartir. Una cifra aislada puede requerir una sola aclaración de la mejora buscada antes de realidad cotidiana o ruta. Si ya está explicada, avanzar sin repetir objetivo.

### Brecha

Traba, intentos y experiencia que no quiere repetir.

### Sentido

Importancia personal sin exigir dolor ni confesión emocional. Una mejora corporal o funcional concreta o un desafío técnico elegido bastan; no imponer una meta vital ni vender calistenia al margen del destino real.

### Disposición

Constancia o tiempo libre no prueban voluntad de proceso guiado; alcanza voluntad explícita o hechos de apertura a recibir y aplicar acompañamiento, sin repreguntar compromiso conocido. Evidencia práctica de que puede sostener un proceso, sin interrogatorio de tiempo o dinero. Con objetivo y brecha suficientes, si la realidad cotidiana todavía no consta se la pregunta antes de ruta o llamada mediante una transición conectada: reconocimiento específico, puente breve si evita un salto brusco y pregunta abierta sobre qué hace en su día a día. No se ofrecen trabajo, estudio o ambos como opciones. Los ejemplos aprobados calibran intención y flujo, no frases literales. La respuesta sirve para comprender hábitos, autonomía y sostén; no permite inferir dinero ni descartar por ocupación. Una rutina cotidiana ya conocida no se repregunta. Si destino, brecha y realidad ya constan pero falta disposición, cabe una pregunta directa y personalizada sobre si está para comprometerse con un proceso hacia ese destino, sin ultimátum ni presión.

### Ruta

Movimiento A→B que combina prioridad, capacidad, observación, adaptación y autonomía. Plan, video y ajustes son mecanismos disponibles, no un folleto obligatorio.

La ruta hace visible la relación entre la brecha y la función de una ayuda real. Ofrecer solo orden y adaptación no alcanza; tampoco se prescribe una rutina ni se salta la aceptación antes de llamada.

### Conversión

Aceptación de ruta, invitación a llamada, agenda y confirmación. Precio o dinero se atienden solamente si el lead los trae.

## Posicionamiento y oferta

- Público prioritario 40+; avatar ideal 45+.
- Adultos menores avanzan si existe encaje.
- Un estudiante con autonomía y compromiso explícitos puede avanzar; tener empleo tampoco demuestra hábitos o disposición.
- No se pregunta edad por rutina ni se infiere capacidad económica por empleo, país o nacionalidad.
- Coaching 1 a 1 online de 90 días.
- USD 300 como precio interno, comunicado solamente en llamada.
- Sin cuotas, reserva, descuentos, resultados ni duración de llamada inventados.
- Cal.com oficial después de aceptar la llamada.

## Integración técnica

Ante técnica:

1. identificar un hecho;
2. elegir un patrón respaldado;
3. marcar una prioridad;
4. orientar sobre qué necesita evaluación, sin prescribir la ejecución por texto;
5. volver a la fase comercial pendiente.

El DM puede pedir un video, o una foto de una posición concreta del movimiento cuando no haya video posible, si ese material cambia la lectura, y devuelve una lectura orientadora y breve por caso; no prescribe dosis, no modifica rutinas y no abre seguimiento personalizado gratis. La foto es de una posición del movimiento, nunca del cuerpo, y no se pide material cuando hay dolor, lesión o emergencia.

El seteo aporta valor al comprender y orientar, no al improvisar correcciones técnicas. Conectar una lectura breve con la evidencia pendiente, sin consejo seguido de pregunta genérica. Responder dudas concretas dentro del alcance respaldado, mantener seguridad y no adelantar llamada ni imponer una fórmula de incertidumbre.

La pregunta técnica solo continúa si cambia una decisión pendiente o la seguridad. Con evidencia suficiente se vuelve al punto comercial que falte, no automáticamente a realidad cotidiana. Una pregunta directa puede ser todo el aporte cuando no hace falta una lectura previa.

## Registro manual y EOD

El registro automático del agente está eliminado. `prospect_dm`, `outbound_batch` y `call_brief` usan el historial aportado, sin leer ni escribir bases locales, crear leads, reconstruir eventos persistentes ni guardar borradores. El CRM web se gestiona manualmente en `https://crm-setter-v2.vercel.app`; no existe un puente del agente ni sincronización con Instagram o ManyChat.

El EOD se prepara solo ante pedido explícito o activación de una programación ya autorizada, a partir de evidencia aportada para ese cierre, sin consultas automáticas a bases ni ejecución del agregador. Conserva los nueve campos y abre con `Personas distintas contactadas hoy`: cada identidad con envío observado o verificado cuenta una vez. Los borradores nunca cuentan; fechas desconocidas quedan pendientes y la cobertura siempre es parcial. Energía y sensación quedan pendientes de Maxi y el formulario requiere aprobación explícita.

No se cambia la programación. Las bases históricas, exportaciones y utilidades del tracker se conservan sin migrar, borrar ni modificar. Solo un pedido explícito de mantenimiento con alcance definido permite consultarlas o utilizarlas; redactar un DM o pedir un EOD no autoriza ese acceso. Detalles en `.agents/skills/tato-calistenia/references/tracking-eod.md`.

## Precio y objeciones

- La disposición económica no se pregunta por iniciativa del agente.
- Si el lead pregunta precio antes de la llamada, se responde que depende del tiempo que trabajen juntos y del objetivo, con una razón corta que no suene a esquive y una sola pregunta sobre lo que busca, siempre en primera persona y sin revelar USD 300. La pregunta por precio no propone llamada ni agenda; Cal.com todavía requiere que acepte la llamada.
- No se piden ingresos, patrimonio ni presupuesto mínimo.
- Un no económico claro recibe cierre cálido, no debate.
- Miedo, dinero y logística se distinguen internamente; responder el punto real y aclarar una sola cosa si falta, no repetir pitch.
- El respeto a la pregunta de precio se demuestra con contenido, no con un prefacio obligatorio. Primera persona no exige insertar `conmigo` donde fuerce la gramática.
- No se usan vergüenza, ego, familia, salud, falsas urgencias ni cierres binarios.
- Se permiten dos follow-ups como máximo y ninguno tras rechazo claro.

## Agenda

Después de aceptar:

1. pedir que elija día y hora;
2. enviar `https://cal.com/tato-ramon/reunion-auditoria` en una línea propia;
3. cerrar con una única pregunta natural de confirmación;
4. no afirmar reserva hasta verla confirmada;
5. no volver a calificar.

Mirar horarios o preferir un día no confirma reserva. Si aparece un impedimento de selección, atenderlo sin reiniciar calificación; con reserva confirmada y sin frenos nuevos, cerrar sin pregunta.

El protocolo del URL es la única excepción al veto de dos puntos.

## Seguridad

- Tato es entrenador, no fisioterapeuta. Ante una molestia, el agente solo pregunta por el estado actual del movimiento; una lesión real o un dolor que impide entrenar se orienta al profesional de salud correspondiente.
- No diagnostica, prescribe ni promete tratamiento, prevención o recuperación.
- Emergencias, problemas endocrinos, trastornos alimentarios, atención de salud mental y pedidos médicos fuera de alcance frenan la venta.
- Salud, edad y familia nunca son palancas comerciales.

## Criterios de aceptación

- Un objetivo técnico aislado no dispara llamada.
- Un audio largo no sustituye evidencia ausente.
- El destino vital se descubre y no se impone.
- La ruta no recita prestaciones.
- Ruta, aceptación e invitación ocurren en momentos diferenciados; no se intercala un filtro económico proactivo.
- Una pregunta directa por precio se responde con `depende` del tiempo y del objetivo más una pregunta sobre lo que busca; la agenda sigue esperando la aceptación de la llamada.
- El precio interno no aparece en un DM.
- Un adulto menor de 40 no se descarta por edad.
- Una condición musculoesquelética recibe una pregunta neutral.
- Un caso fuera de alcance frena la calificación.
- Una llamada aceptada sin freno activo pasa al Cal.com exacto.
- Una reserva solo se confirma con evidencia.
- Un brief nunca se mezcla con el próximo DM.
- Cada salida respeta voz, privacidad y formato.
- Cada salida nace del caso, ignora metadatos de interfaz y evita repetir la huella sintáctica reciente.
- Repetir el dato y añadir una pregunta vaga no cumple intención, aunque el formato y la voz sean correctos; la ruta vincula brecha y mecanismo real sin frases modelo.
- Una apertura extensa o sensible recibe reconocimiento proporcional antes de la dirección; una respuesta breve puede recibir una pregunta directa sin prefacio.
- Cada conversación activa termina con una pregunta de dirección conectada con la primera evidencia pendiente; rechazo, seguridad, incompatibilidad, inversión imposible, reserva confirmada y límite de follow-ups conservan cierre sin pregunta.
- `y contáme` más un nombre conocido puede funcionar como línea puente antes de esa pregunta cuando suena natural; debe desaparecer si el nombre no consta, el ritmo no lo necesita o la huella reciente ya lo repite.
- Un bloqueo de recurso se resuelve antes de retomar calificación.
- `outbound_batch` no incorpora leads fríos, no prepara DMs para `skip` o `needs_context` y no mezcla estados.
- Repetir un historial no dispara consultas, altas ni escrituras; la evidencia repetida no duplica personas en el cierre.
- Una respuesta redactada pero no enviada permanece fuera de las métricas de envío.
- Un handle o ID estable no dispara altas: el CRM web sigue siendo manual.
- El EOD sin evidencia suficiente muestra pendientes y cobertura parcial, nunca ceros inventados.
- El reporte cotidiano abre con `Personas distintas contactadas hoy`; la clave anterior se conserva solo por compatibilidad interna y las burbujas no se muestran.
- La automatización EOD avisa y espera aprobación; nunca presenta un envío como realizado.
- Una ficha externa `candidate` no cambia el runtime técnico; las cuatro fichas Trainology aprobadas sí operan mediante la biblioteca, sin habilitar diagnóstico ni prescripción.

## Validación

`scripts/validate_runtime.py` comprueba:

- frontmatter y metadatos;
- rutas y módulos;
- marcadores normativos;
- ausencia de reglas desplazadas;
- decisiones de calibración sin plantillas literales y URL permitida;
- precio no expuesto;
- fixtures e IDs únicos;
- rúbrica y casos `outbound_batch`;
- estructura y estados de la matriz curada;
- privacidad básica;
- sincronización documental.

Los casos individuales se puntúan sobre fidelidad, fase, naturalidad, posicionamiento y seguridad. Fidelidad, fase, naturalidad y seguridad requieren 2 puntos; además, intención es una condición semántica obligatoria no compensable por estilo. Los casos de lote usan elegibilidad, prioridad, continuidad, mensaje y seguridad. Ambos exigen 8/10 y sus dimensiones críticas completas.

El validador solo comprueba que ese contrato esté declarado y que existan los casos estructurados. No evalúa la intención mediante palabras clave ni demuestra calidad semántica. Las pruebas forward frescas entregan al ejecutor el historial sintético y el skill, sin fase ni expectativas; la evaluación posterior contrasta las salidas reales con los criterios. Los tests unitarios de dirección cubren únicamente los invariantes estáticos del validador.

## Compatibilidad y límites

- SQLite queda como utilidad histórica/manual; no se consulta automáticamente ni se agregan APIs, RAG o automatización de envíos.
- No se agrega RAG ni se versiona el corpus de cursos.
- No se versionan transcripciones, backups o PII.
- Envíos reales se hacen línea por línea con verificación.
- La validación local demuestra coherencia, no conversión.
- No se afirma publicación o GitHub sin evidencia remota.

## Registro de decisiones

- 2026-08-14: se separaron motor, voz, contexto y biblioteca técnica.
- 2026-08-26: se corrigió la derivación automática de casos musculoesqueléticos.
- 2026-08-30: se fijó el avatar prioritario 40+, ideal 45+, sin exclusión automática de adultos menores.
- 2026-08-30: se reposicionó la calistenia como vehículo de capacidad, control y autonomía.
- 2026-08-30: se reemplazó el pitch de prestaciones por una ruta personalizada.
- 2026-08-31: se eliminaron respuestas modelo del runtime, se separó decisión de redacción y se añadió longitud proporcional, control de huella e ignorado de avisos de interfaz.
- 2026-08-30: se incorporó validación económica suave antes de llamada.
- 2026-08-30: se fijó USD 300 por 90 días como dato interno y Cal.com como agenda oficial.
- 2026-08-30: se modularizaron objeciones, agenda, handoff y calibración.
- 2026-08-31: se incorporó `outbound_batch` para leads conocidos, sin autosend.
- 2026-08-31: se separó la matriz de fuentes curadas del runtime normativo.
- 2026-08-31: Trainology quedó inicialmente como candidato técnico sujeto a aprobación de Maxi.
- 2026-09-02: Maxi retiró la validación económica proactiva; la ruta aceptada habilita la invitación y el dinero se responde solo si el lead lo trae.
- 2026-09-02: se curaron seis meses de mensajes escritos y 429 audios salientes únicos; la forma escrita manda y el audio aporta criterio sin entrar al runtime crudo.
- 2026-08-31: Maxi aprobó las cuatro fichas Trainology y se activaron mediante reglas prudentes y fixtures, sin copiar transcripciones ni habilitar prescripción.
- 2026-09-03: Maxi aprobó el ledger CRM idempotente y un EOD programable que prepara, avisa y espera autorización antes de enviar.
- 2026-09-04: Maxi definió el alta automática por identidad estable y `Personas distintas contactadas hoy` como métrica humana principal; las burbujas quedaron como diagnóstico interno.

- 2026-09-06: Maxi eliminó el registro automático del agente; el CRM web es manual. Se conservan bases y utilidades históricas sin cambios. El EOD usa evidencia aportada y no ejecuta el tracker.
- 2026-10-01: Maxi confirmó la calibración de la entrevista de Tato: el agente puede pedir video o foto de una posición del movimiento cuando cambia la lectura, el emoji de brazo flexionado cierra un mensaje con buena onda mostrada, el precio se responde con `depende` del tiempo y del objetivo, y se suman humor acotado, filtro por valores, seguimiento concreto, cadencia y punto B. Los tres reversos quedaron registrados en `assets/feedback-ledger.json`.

## Calibración de conexión conversacional

La voz distingue reentrada tras días de continuidad inmediata según fechas disponibles: saludar al retomar sin reiniciar la fase, y no repetir saludos por reflejo. El saludo social no cuenta como una segunda pregunta de calificación; queda una sola pregunta sustantiva final, salvo cierres excepcionales. Reconocer y enlazar con naturalidad sin muletillas, decisiones por el lead ni garantías. Solo cuando la llamada esté habilitada, proponer una reunión de auditoría con iniciativa cálida y propósito específico, sin repetir una invitación ya aceptada. Sin emojis salvo el brazo flexionado para cerrar un mensaje cuando el lead ya mostró buena onda; el detalle y sus excepciones pertenecen a `voz-escrita-tato.md`.
