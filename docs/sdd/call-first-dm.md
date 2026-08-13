# Madurez conversacional para llamadas en DMs de Tato Calistenia

Fecha: 2026-08-05
Estado: implementado y validado localmente

## Problema y resultado de usuario

El flujo anterior obligaba a recorrer preguntas sobre traba, tiempo, intentos, prioridad, disposicion y modalidad antes de invitar. La primera correccion elimino esa redundancia, pero llevo el criterio al extremo opuesto: objetivo concreto mas encaje disparaban una llamada casi ante cualquier mensaje.

Maxi probo ese runtime y confirmo la regresion. El resultado buscado es que el agente conserve el ritmo comercial y evite filtros rutinarios, pero lea la etapa, cuanto se hablo y el interes que el lead demostro. La llamada debe sentirse como consecuencia de una conversacion, no como respuesta automatica a la primera mencion de un objetivo.

## Evidencia del estado actual

- El audio de Tato del 2026-08-05 pide reducir las preguntas filtro y aumentar las llamadas cuando exista un objetivo en el que Tato pueda ayudar.
- La primera implementacion tradujo esa instruccion como dos puertas suficientes: objetivo concreto y aporte honesto.
- La prueba real de Maxi mostro que esa regla llevaba a llamada una primera respuesta breve y una consulta tecnica aislada.
- El feedback actual pide criterio segun etapa, historial e interes demostrado, sin volver a un interrogatorio fijo.
- El historial completo sigue siendo necesario para no contradecir una oferta, precio o modalidad presencial previa.

## Objetivos

- Requerir cuatro condiciones para invitar: objetivo concreto, aporte honesto de Tato, interes demostrado y madurez conversacional.
- Diferenciar `inicio`, `desarrollo` y `lista para llamada` usando todo el historial relevante.
- Responder y profundizar naturalmente cuando el objetivo esta claro pero la charla aun es temprana.
- Permitir que un mensaje detallado o de alta intencion acelere la invitacion sin exigir turnos artificiales.
- Evitar una lista fija de preguntas sobre tiempo, intentos, urgencia, pago u online.
- Mantener una sola pregunta por DM y leer cada respuesta antes de decidir el siguiente movimiento.
- Conservar los limites de salud, privacidad, veracidad, agenda y ayuda gratuita.

## No objetivos

- No maximizar llamadas a costa de invitar a todo lead en el primer intercambio.
- No restaurar el embudo largo ni una cantidad obligatoria de preguntas.
- No convertir dos aportes sustantivos en una cuota mecanica.
- No prometer resultados ni un plan gratis en la llamada.
- No inventar precios, horarios, disponibilidad ni una oferta presencial vigente.
- No cerrar la venta por DM ni usar el perfil visual para inferir edad, dinero, ubicacion o modalidad.

## Requisitos funcionales

1. El agente lee todo el historial y recupera datos ya confirmados antes de evaluar el ultimo mensaje.
2. Define el objetivo y decide internamente si Tato puede aportar desde tecnica, progresion, estructura, feedback o control corporal.
3. Ubica la charla en `inicio`, `desarrollo` o `lista para llamada`.
4. Considera interes demostrado cuando el lead se explaya, responde con contenido sobre el mismo objetivo, cuenta una traba o intento, pide ayuda personalizada o pregunta por forma de trabajo, precio o siguiente paso.
5. No considera suficiente por si solo aceptar la guia, nombrar un objetivo, reaccionar, agradecer, decir `si` o hacer una consulta tecnica aislada.
6. Si objetivo y encaje estan claros pero la charla sigue en inicio, responde a lo dicho y hace como maximo una pregunta natural sobre la situacion. No invita todavia.
7. Como referencia, una charla nueva suele madurar con al menos dos aportes sustantivos del lead sobre el mismo objetivo. No se cuentan mensajes mecanicamente.
8. Un unico mensaje que ya desarrolla objetivo, dificultad e intento, o que pide de forma explicita ayuda, seguimiento, precio, forma de trabajo o siguiente paso, puede satisfacer interes y madurez.
9. Una duda tecnica recibe como maximo una correccion puntual. Solo lleva a llamada si el historial tambien satisface las cuatro condiciones.
10. Tiempo, nivel, traba, intentos, prioridad, pago y online pueden aparecer de a uno cuando nacen del contexto, pero ninguno forma un peaje fijo.
11. Cuando estan claras las cuatro condiciones y no existe una excepcion, la invitacion menciona el X real y propone conocer mejor el caso y mostrar como Tato encararia el camino.
12. La llamada puede incluir una propuesta paga y no se disfraza como asesoria neutral.
13. Si el lead acepta, el agente pasa directamente a agenda con dos opciones reales o dos ventanas.
14. Si existe una señal concreta de minoridad, se aclara edad; un menor confirmado no se agenda.
15. Si el historial confirma una oferta o precio presencial previo, el agente no fuerza online ni afirma disponibilidad actual sin confirmacion.

## Flujos y casos limite

### Ruta normal

`objetivo -> conversacion util -> interes demostrado -> invitacion -> agenda -> seguimiento`

El encaje se evalua internamente durante toda la ruta. La conversacion util no es un checklist: responde a lo que el lead trae y elige un unico dato contextual cuando haga falta.

### Inicio con objetivo claro

Una primera respuesta breve como `quiero sacar el muscle up` o `quiero mis primeras cinco dominadas` no dispara llamada. El agente reconoce el objetivo y pregunta naturalmente por la situacion actual.

### Desarrollo

Cada aporte sustantivo del lead se lee en conjunto con el historial. Si explica una traba, un intento o por que necesita ayuda, puede completar interes y madurez. Si responde con un monosilabo o una reaccion, el agente no inventa disposicion a llamada.

### Alta intencion temprana

Si el primer mensaje es detallado o pregunta expresamente como trabaja Tato, cuanto sale, si puede ayudar o cual es el siguiente paso, no se fuerza otro turno por cumplir una cantidad. Con objetivo y encaje claros puede invitarse.

### Pregunta tecnica

Se entrega una sola correccion util y segura. Una consulta aislada no habilita llamada ni otra ronda gratuita. Si el historial ya era maduro, la continuacion puede ser la invitacion.

### Objetivo vago o adyacente

Se pregunta una vez por el movimiento o puente real con calistenia. Sin puente se cierra; no se inventa encaje.

### Preferencia presencial

Se revisa el historial completo. Un antecedente confirmado se respeta; sin opcion respaldada, se explica online una vez y se valida si puede servir.

### Salud y rechazo

Una molestia ambigua conserva la pregunta neutral de capacidad. Dolor persistente o intenso, sintomas graves, incapacidad para entrenar o pedido clinico mantienen la derivacion. No se presiona despues de un segundo no claro.

## Requisitos no funcionales

- Respuesta breve, rioplatense, humana y adaptable al X.
- Un movimiento y como maximo una pregunta.
- Sin dos puntos en el DM final.
- Sin inferencias por apariencia ni afirmaciones comerciales no verificadas.
- La fuente operativa debe quedar sin reglas del antiguo embudo ni reglas de llamada inmediata por objetivo aislado.
- La heuristica de madurez debe permitir criterio contextual, no una maquina de contar mensajes.

## Datos, API, autenticacion y autorizacion

No hay cambios de base de datos, API, autenticacion, autorizacion ni RLS. Los chats siguen tratandose como informacion privada y no se incorpora la transcripcion cruda del audio al runtime.

## Compatibilidad y migracion

- Se actualizan `SKILL.md`, `operativa-dm.md` y `contexto-maestro.md` como una sola unidad.
- Los filtros antiguos siguen siendo contexto opcional y nunca una secuencia obligatoria.
- La regla intermedia de dos puertas suficientes queda reemplazada por el criterio de cuatro condiciones.
- Precio, agenda, objeciones, limites clinicos y formato de salida se conservan.
- Se guardan backups fechados antes de reemplazar cada archivo critico.

## Criterios de aceptacion

- Un primer mensaje breve sobre muscle-up recibe una pregunta contextual y no una llamada.
- Un primer mensaje breve sobre las primeras cinco dominadas recibe una pregunta contextual y no una llamada.
- Una consulta tecnica aislada recibe una correccion puntual y no una llamada automatica.
- Una conversacion con objetivo, traba o intento y al menos otro aporte sustantivo puede llevar a llamada sin filtros adicionales.
- Un unico mensaje detallado que pide ayuda o pregunta como trabaja Tato puede llevar a llamada con encaje claro.
- El runtime no exige tiempo, intentos, prioridad, pago ni online antes de invitar.
- Preguntar por precio con objetivo y encaje ya conocidos cuenta como interes explicito y puede llevar a llamada.
- La aceptacion de llamada lleva directamente a agenda.
- Una preferencia presencial usa primero el historial completo y un menor confirmado no se agenda.
- Permanecen los limites de salud, no promesa, no precio inventado y una sola pregunta.

## Estrategia de prueba

- Validacion estructural de UTF-8, tamaño, ausencia de bytes nulos y marcadores obligatorios.
- Busqueda de contradicciones tanto del embudo antiguo como de la llamada inmediata por objetivo aislado.
- Revision automatica de los DMs de calibracion para ausencia de dos puntos y maximo una pregunta.
- Casos forward independientes para inicio, desarrollo maduro, alta intencion, duda tecnica, presencial y minoridad.
- Revision del diff completo contra los backups y reemplazo atomico de los cuatro archivos.

## Evidencia de validacion

- `quick_validate.py` del skill-creator sobre el candidato: `Skill is valid!`.
- Validador estatico: cuatro archivos en UTF-8 estricto, sin bytes nulos, marcadores obligatorios presentes y frases de llamada inmediata ausentes.
- Calibracion: 13 ejemplos y 45 bloques de DM revisados, sin dos puntos y con como maximo una pregunta por bloque.
- Diez casos forward independientes: tres inicios sin llamada, conversacion madura, alta intencion, historial presencial, objetivo vago, precio, minoridad y aceptacion de llamada.
- La revision adversarial detecto una contradiccion entre precio y agenda; se corrigio para que precio habilite invitacion, pero las opciones de agenda aparezcan solo despues de aceptar. La revalidacion dio `GO`.
- Los backups coincidieron byte a byte con los archivos activos previos y se reviso el diff completo de los cuatro candidatos.
- Esta evidencia prueba coherencia del runtime local; no prueba una mejora de conversion ni agendas reales.

## Rollout y rollback

- Rollout: activar el criterio de madurez conversacional en toda respuesta nueva del workspace.
- Señales a observar: invitaciones menos prematuras, conversaciones que no vuelvan al interrogatorio y agendas que surjan despues de interes real.
- La mejora en agendamiento solo puede probarse con conversaciones reales; la validacion local demuestra coherencia del runtime, no conversion.
- Rollback: restaurar los backups `*.20260805-181629847.before-readiness.bak` si la validacion falla o Maxi revierte el criterio.

## Riesgos

- Un umbral demasiado alto puede reintroducir filtros y enfriar leads. Se mitiga con la via rapida para mensajes detallados o interes explicito.
- Un umbral demasiado bajo puede volver a la llamada automatica. Se mitiga exigiendo una conducta observable, no solo un objetivo.
- La madurez tiene un componente contextual. Se mitiga con señales positivas, contraejemplos y casos de calibracion, sin convertirlos en cuotas.
- El contexto presencial puede quedar desactualizado. Se usa solo lo confirmado en el historial y no se promete disponibilidad.
- La edad no siempre esta disponible. Se pregunta solo ante una señal concreta y nunca se infiere por apariencia.

## Registro de decisiones

- 2026-08-05: el embudo obligatorio de filtros se reemplazo inicialmente por una regla call-first de dos puertas.
- 2026-08-05: la prueba de Maxi mostro que dos puertas disparaban llamadas prematuras; esa regla queda reemplazada por cuatro condiciones: objetivo, encaje, interes y madurez.
- 2026-08-05: dos aportes sustantivos se usan como referencia para chats nuevos, no como requisito mecanico; la alta intencion puede acelerar.
- 2026-08-05: voluntad de pago y formato online siguen sin ser requisitos previos fijos.
- 2026-08-05: lectura de historial completo, minoridad, salud, privacidad y limites comerciales se conservan.
