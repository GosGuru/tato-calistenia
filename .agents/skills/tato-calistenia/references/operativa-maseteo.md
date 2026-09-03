# Operativa de maseteo — Tato / VALKA

Esta referencia define `outbound_batch`: una cola interna para trabajar leads conocidos con velocidad sin perder continuidad, criterio ni seguridad. Clasifica y prepara; nunca envía mensajes.

## Alcance

Fuentes permitidas:

- seguidores que ya entraron al ecosistema de Tato;
- comentarios o palabras clave sobre una publicación;
- solicitudes de guía o lead magnet;
- conversaciones abiertas o asignadas;
- reactivaciones de chats con un movimiento pendiente.

Quedan fuera:

- cuentas scrapeadas o compradas;
- perfiles fríos sin señal verificable;
- listas cuya procedencia no consta;
- automatización de envíos;
- cualquier intento de saltar las reglas de elegibilidad, privacidad o seguimiento.

## Contrato del lote

Cada lead se resuelve como un caso independiente. El lote no crea un historial común ni permite copiar hechos, nombres, objetivos, fase o mensaje entre personas.

Para cada entrada reconstruir, cuando conste:

- `lead_ref`: identificador efímero recibido en la entrada;
- `fuente`: seguidor, comentario, recurso, conversación o reactivación;
- `historial_verificable`;
- `ultimo_movimiento` y quién debe responder;
- `fase` y `subestado_conversion`;
- `followups_realizados`;
- `bloqueo_operativo`;
- `excepciones`;
- `contacto_reciente_o_duplicado`.

Si falta el historial necesario para decidir, usar `needs_context`. No completar huecos con el perfil, una etiqueta o la situación de otro lead.

## Elegibilidad

Usar exactamente uno de estos estados:

- `eligible`: existe un movimiento legítimo y verificable para Tato;
- `needs_context`: podría corresponder un movimiento, pero falta evidencia para elegirlo sin adivinar;
- `skip`: no debe prepararse un DM.

### `skip` obligatorio

- rechazo claro;
- dos follow-ups sin respuesta;
- menor confirmado;
- emergencia o necesidad fuera del alcance;
- reserva confirmada;
- mensaje ya enviado o automatización todavía pendiente;
- contacto reciente que duplicaría el mismo movimiento;
- cuenta fría, scrapeada o sin señal conocida;
- historial o captura no atribuible con certeza al lead.

Una llamada aceptada o una agenda enviada no se omiten: se procesan desde su subestado, sin reabrir calificación.

## Prioridad

Ordenar solamente después de resolver seguridad y elegibilidad:

1. `bloqueo_operativo`: enlace roto, recurso prometido o automatización que no cumplió;
2. `inbound_activo`: el lead respondió y espera a Tato;
3. `fase_pendiente`: existe una conversación abierta con siguiente movimiento claro;
4. `followup_1`: primer seguimiento desde la fase pendiente;
5. `apertura_conocida`: primer contacto con señal verificable;
6. `followup_2`: último toque y cierre si no responde.

La prioridad no autoriza presión. Solo organiza qué conversación merece atención primero.

## Selección del movimiento

### Bloqueo operativo

Resolver primero lo prometido. Si un enlace no abre o falta un recurso, reparar esa experiencia antes de preguntar por objetivo o brecha. Retomar el seteo en otro turno.

### Inbound o conversación activa

Leer todo el historial, reconocer la evidencia nueva y continuar desde la primera fase relevante que siga pendiente. Una respuesta puede completar varias fases.

### Apertura conocida

La fuente da contexto, no permiso para fingir intimidad. Abrir breve y humano, nombrando el motivo real solo cuando está verificado. No explicar el servicio ni encadenar preguntas. Si el saludo ya pregunta cómo está, no agregar otra pregunta de segmentación en ese DM.

### Reactivación

Retomar el último movimiento pendiente y el destino real. No reiniciar con una pregunta genérica ni asumir que el silencio es rechazo, dinero o falta de compromiso.

## Dirección eficiente

La estructura comercial aporta dirección, no dominio:

1. abrir o responder desde el dato real;
2. segmentar por situación y objetivo, no por estereotipos;
3. descubrir la brecha sin agravarla;
4. comprobar disposición práctica sin ultimátum;
5. presentar una ruta contextual;
6. esperar aceptación;
7. invitar y, si acepta, agendar en momentos separados, sin filtro económico proactivo.

No convertir esta secuencia en siete mensajes obligatorios. El motor conserva las fases normativas de `operativa-dm.md`.

## Salida

La respuesta es una cola interna. Incluir un resumen con totales y, para cada lead:

```text
lead_ref: referencia recibida
eligibility: eligible | needs_context | skip
reason: motivo breve y verificable
priority: bloqueo_operativo | inbound_activo | fase_pendiente | followup_1 | apertura_conocida | followup_2 | none
phase: contexto | destino | brecha | sentido | disposicion | ruta | conversion | none
next_action: movimiento único o none
dm:
mensaje listo, solo si corresponde
```

Reglas:

- un solo DM por lead elegible;
- el DM respeta el contrato de `prospect_dm`;
- `needs_context` y `skip` no contienen DM;
- el motivo es interno y nunca se copia al prospecto;
- lotes grandes se paginan sin truncar el historial de un lead;
- no declarar un mensaje como enviado ni una reserva como confirmada sin evidencia.

## Envío posterior

`outbound_batch` nunca envía. Si Maxi pide operar Instagram o ManyChat en otra acción:

1. tomar únicamente el DM aprobado de un lead;
2. enviar una línea por vez;
3. verificar visualmente cada burbuja y el compositor vacío;
4. detenerse ante interrupción, captura dudosa o cambio de conversación;
5. actualizar el estado solo con evidencia visible.

## Métricas prudentes

La cola puede resumir, sin almacenar PII en el repositorio:

- revisados;
- `eligible`, `needs_context` y `skip`;
- respuestas pendientes;
- primer y segundo follow-up;
- rutas aceptadas;
- llamadas aceptadas;
- reservas confirmadas.

No tratar volumen, reply rate o cantidad de llamadas como prueba de calidad. La eficiencia válida reduce repreguntas y movimientos innecesarios sin degradar voz, seguridad ni calificación.
