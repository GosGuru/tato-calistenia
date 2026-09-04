# Registro CRM y cierre EOD

Esta referencia define persistencia operativa. El formulario EOD es una salida agregada; nunca es la fuente de verdad.

## Privacidad y almacenamiento

- Guardar solo estado comercial y huellas de mensajes; nunca persistir chats crudos.
- Usar por defecto la base local privada indicada por `crm_tracker.py` fuera del repositorio.
- No versionar bases, exportaciones, nombres completos innecesarios ni identificadores privados.

## Eventos

El esquema canónico vive en `../assets/crm-event.schema.json`. Antes de responder un chat, consultar el lead. Después de decidir, registrar `dm_drafted` sin contarlo como envío. Registrar `outbound_sent` o `followup_sent` únicamente cuando el historial lo muestre (`observed`) o la interfaz confirme el envío (`verified`). Un borrador, una intención o una salida del agente nunca cuentan como enviados.

Al recibir un historial completo, reconstruir todos los eventos verificables y reenviarlos al tracker: la huella idempotente descarta duplicados. Usar el handle de Instagram o el ID estable de ManyChat como `lead_key`; el nombre visible no es una identidad estable.

Registrar también cambios comerciales comprobables: `route_presented`, `route_accepted`, `call_invited`, `calendar_sent`, `booking_confirmed`, `objection_observed`, `disqualified` y `operational_block`.

## Comandos

Leer el estado antes de decidir:

```powershell
python .agents/skills/tato-calistenia/scripts/crm_tracker.py lead --lead-key <id>
```

Registrar uno o varios eventos mediante JSON por stdin:

```powershell
$json | python .agents/skills/tato-calistenia/scripts/crm_tracker.py record --input -
```

Generar el cierre revisable:

```powershell
python .agents/skills/tato-calistenia/scripts/crm_tracker.py eod --date YYYY-MM-DD --format form
```

## Definiciones EOD

- `mensajes_enviados`: contactos únicos con al menos un outbound `observed` o `verified` ese día.
- `burbujas_enviadas`: cantidad de eventos outbound verificables; se conserva como métrica interna.
- `respondieron`: contactos con inbound verificable posterior a un outbound del mismo día, según el orden temporal registrado. No implica atribución causal confirmada.
- `respuestas_tardias`: contactos cuyo inbound del día sigue a un outbound de un día anterior; si también respondieron después de otro outbound de hoy, se cuentan solo en `respondieron`.
- `seguimientos`: contactos únicos con `followup_sent` verificable.
- `calidad`: distribución `alta`, `media`, `baja` y `sin_clasificar` vigente al cierre entre contactos con inbound u outbound observado o verificado del día; excluye borradores y cambios posteriores.
- `objeciones`: frecuencia de `objection_observed` por categoría.
- `energia` y `como_te_sentiste`: siempre quedan pendientes de Maxi.

## Cierre programado

La automatización genera y presenta el EOD, pide energía y sensación y espera aprobación. No abre, completa ni envía Google Forms sin autorización explícita en ese cierre.

## Registro automático interno y cobertura

- El agente registra internamente, sin pedir a Maxi que prepare JSON ni lleve cuentas. Consultar el lead y enviar en un solo lote los hechos nuevos verificables y el borrador del turno. Reprocesar historial disponible es seguro; no abrir otro chat ni emitir explicaciones en la salida de prospecto.
- Usar exactamente la misma identidad estable del lead en todas las conversaciones. No crear un segundo lead por cambiar nombre visible o formato del handle. Si no hay identidad fiable, no inventarla: mantener el registro pendiente y explicitar cobertura parcial al cierre.
- Para mensajes, preferir `event_id` de plataforma. Sin ID, la huella usa lead, dirección, instante exacto y texto normalizado. Conservar el mismo método entre importaciones. Si dos burbujas tienen idéntico texto e instante, usar sus IDs distintos; no fabricar segundos para separarlas.
- La identidad no incluye actor, fase ni nivel de evidencia. Reobservar un envío como `verified` no crea otra burbuja; `followup_sent` y `outbound_sent` del mismo mensaje se consolidan como seguimiento. Un `dm_drafted` sigue siendo un evento distinto y nunca se promueve por intención.
- `occurred_at` requiere fecha, hora y zona verificables. Guardar el instante real, no la hora de lectura del historial. No inventar medianoche, año ni fecha para capturas incompletas. Esos eventos quedan pendientes fuera de métricas fechadas.
- El día comercial usa `America/Montevideo`; offsets equivalentes identifican el mismo instante. Se requiere una base IANA disponible para Python (`tzdata` en Windows cuando el sistema no la provea); si falta, el comando falla explícitamente, nunca cambia de zona silenciosamente.
- El lote se valida completo antes de escribir y se confirma en una transacción. Un error no deja media carga. Una repetición antigua no retrocede fase ni calidad; las anotaciones corregidas requieren un nuevo evento factual, no editar una burbuja ya importada.
- El EOD siempre indica cobertura parcial: solamente incluye evidencia registrada. Cero no significa que no hubo actividad fuera de los chats observados. El registro automático interno no es una integración ni sincronización con Instagram o ManyChat.
- Si falla el registro, no afirmar que se guardó ni reenviar un DM para repararlo. Mantener el pendiente, revisar el error y comunicar la cobertura incompleta en mantenimiento o cierre.

## Compatibilidad y reconciliación

`lead` y `eod` abren SQLite en modo solo lectura y no crean una base vacía. Una base ausente es un registro no disponible, no un día con cero actividad.

Las bases anteriores al formato 2 admiten registros nuevos sin migración ni modificación de eventos históricos. La primera reobservación puede añadir una copia canónica: las lecturas consolidan solo identidades exactas con mismo lead, dirección, instante y huella, conservando la evidencia más fuerte. No se mezclan IDs de plataforma distintos; cambiar entre ID de plataforma y huella puede requerir conciliación. Mensajes heredados sin huella ni ID estable no se fusionan por suposición. El EOD conserva el aviso de conciliación pendiente, excluye fechas históricas sin zona e informa su cantidad. No migrar, borrar, reemplazar ni reiniciar la base sin aprobación explícita de Maxi; no usar cifras heredadas como cierre definitivo hasta conciliar.
