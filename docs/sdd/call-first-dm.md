# Arquitectura del setter Tato Calistenia

Fecha: 2026-09-02
Estado: implementación local v3

## Objetivo

Producir el próximo movimiento natural de cada conversación y entregar a Tato leads mejor preparados. La calistenia se presenta como vehículo hacia una capacidad vital elegida por el lead; la llamada llega después de una aceptación positiva de la ruta, sin filtro económico proactivo.

## Principios

- El historial completo manda sobre el último mensaje.
- La calificación es adaptativa y nunca un formulario.
- Una respuesta equivale a un movimiento y una pregunta máxima.
- La decisión interna se completa antes de redactar; la redacción se construye de cero y no se recupera desde ejemplos.
- La brevedad es el valor por defecto, pero la extensión aumenta cuando la apertura del lead necesita reconocimiento proporcional.
- Toda conversación activa termina con una pregunta de dirección; los cierres excepcionales quedan sin pregunta.
- La habilidad técnica puede ser un hito, no el destino universal.
- La autoridad de Tato nace del criterio, no de presión o estatus.
- El DM diagnostica comercialmente lo mínimo; la llamada profundiza y cierra.
- Los LOOM aportan pedagogía curada, no voz literal ni datos privados.
- El corpus escrito propio gobierna la forma; los audios salientes de Tato aportan criterio y vocabulario después de una curación privada, nunca recuperación literal.
- Las fuentes externas solo aportan criterios aprobados; su matriz de mantenimiento no gobierna respuestas.
- El maseteo organiza leads conocidos y nunca automatiza envíos.
- El CRM persiste eventos comerciales idempotentes, no transcripciones; el EOD es una salida revisable.
- Cada chat nuevo del workspace reconstruye la v3 desde el skill y sus referencias, sin depender de conversaciones anteriores.

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

Definen el ledger SQLite privado, el contrato de eventos y la agregación del formulario. Los textos se convierten en huellas antes de persistirse; un borrador nunca cuenta como envío.

## Interfaces

### `prospect_dm`

Salida por defecto:

- solo el próximo DM;
- una idea por línea;
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

Solo por pedido explícito. Devuelve destino, situación, brecha, sentido, disposición, ruta aceptada, salud, objeciones, pendientes, lenguaje útil, ángulo y datos que no deben repetirse.

### `eod_review`

Genera los nueve campos del cierre desde eventos verificables, mantiene contactos y burbujas separados, pide energía y sensación y espera aprobación. No envía el formulario.

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
2. Menor confirmado.
3. Bloqueo operativo verificable.
4. Reserva confirmada.
5. Llamada aceptada o agenda enviada.
6. Objeción activa.
7. Segundo rechazo o incompatibilidad confirmada.
8. Pregunta operativa.
9. Rama técnica, comercial o conversacional normal.

Esta precedencia impide vender durante una emergencia, seguir calificando después de una aceptación o ignorar un freno activo.

## Calificación

Las siete fases son:

`contexto -> destino -> brecha -> sentido -> disposición -> ruta -> conversión`

El historial puede completar varias. El agente salta las fases resueltas, pregunta por la primera evidencia relevante que falte y nunca pregunta para llenar una casilla.

### Contexto

Punto de partida y restricciones reales.

### Destino

Capacidad o hito y, si existe, lo que permitiría vivir, sentir o compartir.

### Brecha

Traba, intentos y experiencia que no quiere repetir.

### Sentido

Importancia personal sin exigir dolor ni confesión emocional.

### Disposición

Evidencia práctica de que puede sostener un proceso, sin interrogatorio de tiempo o dinero.

### Ruta

Movimiento A→B que combina prioridad, capacidad, observación, adaptación y autonomía. Plan, video y ajustes son mecanismos disponibles, no un folleto obligatorio.

### Conversión

Aceptación de ruta, invitación a llamada, agenda y confirmación. Precio o dinero se atienden solamente si el lead los trae.

## Posicionamiento y oferta

- Público prioritario 40+; avatar ideal 45+.
- Adultos menores avanzan si existe encaje.
- No se pregunta edad por rutina ni se infiere capacidad económica.
- Coaching 1 a 1 online de 90 días.
- USD 300 como precio interno, comunicado solamente en llamada.
- Sin cuotas, reserva, descuentos, resultados ni duración de llamada inventados.
- Cal.com oficial después de aceptar la llamada.

## Integración técnica

Ante técnica:

1. identificar un hecho;
2. elegir un patrón respaldado;
3. marcar una prioridad;
4. dar una lectura o cue;
5. volver a la fase comercial pendiente.

El DM no analiza videos, prescribe dosis, modifica rutinas ni abre seguimiento personalizado gratis.

## Persistencia CRM y EOD

- Identificar por handle de Instagram o ID estable de ManyChat.
- Reprocesar el historial completo de forma segura: la huella idempotente descarta eventos repetidos.
- Persistir `dm_drafted` al preparar y `outbound_sent` o `followup_sent` solo al observar o verificar el envío.
- Derivar contactos, respuestas, seguimientos, calidad, objeciones y comentarios desde el ledger.
- Conservar energía y sensación como campos personales pendientes.
- Mantener la base fuera de Git y no guardar el texto crudo.

## Precio y objeciones

- La disposición económica no se pregunta por iniciativa del agente.
- Si el lead pregunta precio, se aclara que es un acompañamiento pago de 90 días y se propone conversar valor y propuesta con Tato en llamada, sin revelar USD 300. Esta es la única excepción a la aceptación previa de ruta; Cal.com todavía requiere que acepte la llamada.
- No se piden ingresos, patrimonio ni presupuesto mínimo.
- Un no económico claro recibe cierre cálido, no debate.
- Miedo, dinero y logística se distinguen internamente.
- No se usan vergüenza, ego, familia, salud, falsas urgencias ni cierres binarios.
- Se permiten dos follow-ups como máximo y ninguno tras rechazo claro.

## Agenda

Después de aceptar:

1. pedir que elija día y hora;
2. enviar `https://cal.com/tato-ramon/reunion-auditoria` en una línea propia;
3. pedir confirmación;
4. no afirmar reserva hasta verla confirmada;
5. no volver a calificar.

El protocolo del URL es la única excepción al veto de dos puntos.

## Seguridad

- Tato puede evaluar molestias musculoesqueléticas como fisioterapeuta; el agente solo pregunta por el estado actual.
- No diagnostica, prescribe ni promete tratamiento, prevención o recuperación.
- Emergencias, problemas endocrinos, trastornos alimentarios, atención de salud mental y pedidos médicos fuera de alcance frenan la venta.
- Salud, edad y familia nunca son palancas comerciales.

## Criterios de aceptación

- Un objetivo técnico aislado no dispara llamada.
- Un audio largo no sustituye evidencia ausente.
- El destino vital se descubre y no se impone.
- La ruta no recita prestaciones.
- Ruta, aceptación e invitación ocurren en momentos diferenciados; no se intercala un filtro económico proactivo.
- Una pregunta directa por precio puede proponer llamada antes de ruta aceptada, pero nunca enviar agenda antes de que la llamada sea aceptada.
- El precio interno no aparece en un DM.
- Un adulto menor de 40 no se descarta por edad.
- Una condición musculoesquelética recibe una pregunta neutral.
- Un caso fuera de alcance frena la calificación.
- Una llamada aceptada pasa al Cal.com exacto.
- Una reserva solo se confirma con evidencia.
- Un brief nunca se mezcla con el próximo DM.
- Cada salida respeta voz, privacidad y formato.
- Cada salida nace del caso, ignora metadatos de interfaz y evita repetir la huella sintáctica reciente.
- Una apertura extensa o sensible recibe reconocimiento proporcional antes de la dirección; una respuesta breve puede recibir una pregunta directa sin prefacio.
- Cada conversación activa termina con una pregunta de dirección conectada con la primera evidencia pendiente; rechazo, seguridad, incompatibilidad, inversión imposible, reserva confirmada y límite de follow-ups conservan cierre sin pregunta.
- Un bloqueo de recurso se resuelve antes de retomar calificación.
- `outbound_batch` no incorpora leads fríos, no prepara DMs para `skip` o `needs_context` y no mezcla estados.
- Un historial pegado varias veces produce los mismos IDs y no infla el EOD.
- Una respuesta redactada pero no enviada permanece fuera de las métricas de envío.
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

Los casos individuales se puntúan sobre fidelidad, fase, naturalidad, posicionamiento y seguridad. Los casos de lote usan elegibilidad, prioridad, continuidad, mensaje y seguridad. Ambos exigen 8/10 y sus dimensiones críticas completas.

## Compatibilidad y límites

- Se admite SQLite local mediante biblioteca estándar; no se agregan APIs, RAG ni automatización de envíos.
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

## Garantías del registro EOD

El agente registra los hechos observados y el borrador internamente por lote; Maxi no lleva cuentas manuales. Identidad estable, evidencia monotónica y orden cronológico evitan duplicaciones y retrocesos. Los cierres usan America/Montevideo, calidad histórica y contactos reales separados de burbujas; los borradores nunca cuentan como envíos.

El reporte conserva los nueve campos y declara cobertura parcial de evidencia registrada, no sincronización con Instagram. Fechas desconocidas quedan pendientes, nunca se inventan. Las consultas son solo lectura; las bases heredadas admiten nuevos eventos sin migrar ni reescribir los históricos. Las lecturas consolidan identidades exactas y mantienen visible la conciliación pendiente. No se cambia la programación ni la aprobación del formulario. Detalles operativos en `.agents/skills/tato-calistenia/references/tracking-eod.md`.

Prueba de regresión sintética: `python -B .agents/skills/tato-calistenia/scripts/test_crm_tracker.py`. Requiere disponibilidad de la zona IANA America/Montevideo en Python; si falta, el tracker informa el error sin asumir otra zona.
