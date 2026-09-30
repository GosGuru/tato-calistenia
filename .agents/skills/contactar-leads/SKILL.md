---
name: contactar-leads
description: "Opera recorridos autorizados de leads en ManyChat: no leídos de Tú, no asignados hasta un límite y lotes de seguimientos, con revisión individual, voz de Tato, CRM manual y verificación de cada envío."
---

# Contactar leads

## Activación

Usar cuando Maxi pida contactar, responder o hacer seguimientos en vivo desde ManyChat.

Antes de trabajar, leer y aplicar `.agents/skills/tato-calistenia/SKILL.md`. Esta skill gobierna el recorrido operativo; `tato-calistenia` gobierna el criterio comercial, la voz, la seguridad y el próximo movimiento de cada conversación.

## Autorización

- Revisar y preparar no autoriza a enviar.
- Enviar mensajes, registrar datos o contactar terceros requiere autorización explícita para el lote actual y las confirmaciones que exija el navegador.
- No ampliar el lote, cambiar el plan de ManyChat ni superar bloqueos de plataforma.

## Recorrido estándar

1. Abrir `Tú` o `Asignado a mí` y activar `No leído`.
2. Procesar todos los chats visibles de abajo hacia arriba.
3. Volver a auditar `Tú` con `No leído` porque pueden llegar respuestas durante el recorrido.
4. Abrir `No asignado`, activar `No leído` y trabajar de abajo hacia arriba hasta el límite que Maxi haya indicado.
5. El límite forma parte del control del recorrido. No tocar chats situados por debajo de él.
6. Al repetir el proceso, reconstruir el estado desde la interfaz actual. No asumir que el resultado anterior sigue vigente.

Las listas de ManyChat son virtualizadas y un envío puede reasignar el chat. Después de cada tramo, volver a ubicar el límite y comprobar que no haya quedado ningún caso elegible por encima.

## Elegibilidad por lead

Leer el historial completo antes de redactar. Resolver cada lead de forma independiente.

No responder cuando exista cualquiera de estas condiciones:

- etiqueta `NO CALIFICA`;
- exclusión explícita vigente dada por Maxi, incluidas personas que ya estuvieron en llamada;
- rechazo claro;
- reserva confirmada que solo requiere cierre ya realizado;
- dos seguimientos previos sin respuesta;
- mensaje reciente que duplicaría el mismo movimiento;
- cuenta fría sin señal verificable;
- ventana de Instagram vencida o bloqueo del plan;
- historial insuficiente para elegir el siguiente movimiento sin inventar.

Los nombres privados usados como exclusiones en un lote son estado efímero: respetarlos en esa ejecución, pero no copiarlos al runtime, fixtures ni documentación.

## Redacción

- Hablar como Tato, siempre en primera persona.
- Usar voseo rioplatense natural.
- Escribir con autoridad y brevedad.
- Una idea por mensaje.
- Una línea se envía como una burbuja independiente: escribir, enviar, verificar y recién después continuar con la siguiente.
- Hacer un solo movimiento comercial y como máximo una pregunta.
- En una conversación activa, terminar con una única pregunta de dirección.
- No agregar pregunta en cierres por rechazo, seguridad, incompatibilidad, inversión imposible, reserva confirmada o límite de seguimientos.
- Reconocer el dato concreto del lead sin repetirlo como eco.
- No copiar el mismo esqueleto entre leads.
- No diagnosticar, prescribir, inventar precio, agenda, resultados ni datos del lead.
- Ignorar asignaciones, pausas de automatización y otros mensajes de sistema al reconstruir el caso.

## Seguimientos

- Retomar la fase y el movimiento pendientes; no reiniciar la calificación.
- El primer seguimiento recupera el destino real y el último paso pendiente.
- El segundo seguimiento es el último toque, breve y sin culpa; después se cierra.
- El silencio no demuestra desinterés, falta de dinero ni falta de compromiso.
- No enviar un seguimiento si el último mensaje saliente es reciente o si ya existen dos sin respuesta.

Cuando Maxi pida una cantidad aproximada, por ejemplo 50–60, usarla como objetivo máximo de elegibles, nunca como obligación de enviar a contactos que deban excluirse.

## Envío y verificación

Para cada lead autorizado:

1. Confirmar nombre o identificador y leer el historial completo.
2. Determinar la fase, la evidencia nueva y el único movimiento útil.
3. Redactar desde cero.
4. Enviar una sola línea.
5. Verificar visualmente la burbuja enviada y el compositor vacío.
6. Repetir solo si el mensaje necesita otra línea.
7. No afirmar envío, entrega, lectura o reserva sin evidencia visible.

Si el navegador cambia de chat, la captura es dudosa o el envío no se verifica, detener ese caso y no reenviar a ciegas.

## CRM manual

El CRM web y ManyChat no están sincronizados.

- Para un contacto nuevo realmente enviado, buscar primero por nombre o usuario exacto y esperar el debounce.
- Crear el lead solo si no existe.
- Marcar `FUP hecho` únicamente cuando el mensaje enviado sea realmente un seguimiento.
- Registrar `Cal. enviado` o `Agendó` solo con evidencia correspondiente.
- Verificar por separado la burbuja de ManyChat y la acción del CRM.
- No contar borradores ni intentos fallidos.

## Agenda y handoff

- Si el lead afirma haber reservado, verificar fecha y hora en Google Calendar antes de confirmarlo.
- Leer toda la conversación antes de preparar un brief.
- Enviar un handoff por WhatsApp solo cuando Maxi lo pida explícitamente para ese lead.
- Una reserva confirmada se reconoce y se cierra sin pregunta.

## Bloqueos

Ante límite de contactos activos, ventana vencida, falta de compositor, error del conector o cualquier restricción verificable:

- no mejorar el plan ni cambiar configuraciones;
- no usar otra cuenta, cookies, tokens ni atajos;
- no fingir que el mensaje fue enviado;
- registrar el lead como bloqueado con el motivo visible;
- continuar con el siguiente elegible cuando sea seguro.

## Cierre del lote

Reauditar los filtros y el límite en vivo. Informar de forma breve:

- cantidad y nombres de enviados verificados;
- nuevos leads creados en CRM;
- seguimientos marcados;
- excluidos y motivo;
- bloqueados y motivo;
- acciones pendientes que no quedaron verificadas.

Nunca presentar un recorrido como completo si quedan casos elegibles sin revisar dentro del alcance autorizado.
