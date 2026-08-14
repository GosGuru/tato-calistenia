# Arquitectura agentica para DMs de Tato Calistenia

Fecha: 2026-08-14
Estado: implementado localmente

## Objetivo

Producir el mejor siguiente DM posible para cada conversacion sin depender de un embudo fijo. El agente debe leer historial, objetivo, interes, madurez, tecnica y excepciones como un solo sistema; aportar valor con la voz de Tato y llevar a llamada solamente cuando sea consecuencia natural del intercambio.

## Problemas resueltos

- La primera version preguntaba demasiados filtros antes de invitar.
- La version call-first corrigio ese exceso, pero podia invitar apenas aparecia un objetivo.
- La operativa crecio hasta mezclar orquestacion, conocimiento, excepciones y ejemplos en un unico archivo largo.
- El conocimiento tecnico inicial era demasiado chico para reflejar una traba concreta antes de la llamada.
- Las transcripciones nuevas podian tentar a copiar rutinas o explicaciones individuales sin distinguir certeza ni alcance.

La arquitectura actual separa motor, reglas comerciales, contexto maestro y conocimiento tecnico.

## Componentes del runtime

### `SKILL.md`

Punto de entrada. Mantiene el contrato, las invariantes y las reglas de carga progresiva. No contiene el detalle de todas las ramas.

### `motor-agentico.md`

Se carga para todo chat. Define:

- orden de autoridad;
- estado interno;
- puertas prioritarias;
- ciclo de decision;
- condiciones de llamada;
- seleccion de un solo gol del turno;
- composicion y revision silenciosa.

### `operativa-dm.md`

Referencia detallada para objeciones, precio, agenda, seguimiento, modalidad, minoridad, salud, ejemplos y dudas comerciales.

### `contexto-maestro.md`

Fuente de identidad, oferta, metodo, seguridad, privacidad y limites comerciales. Los datos internos no quedan autorizados para el DM por el solo hecho de existir en este archivo.

### `biblioteca-tecnica-tato.md`

Patrones curados desde LOOM reales. Separa hecho, hipotesis y personalizacion; contiene señales de uso, cue, para que, informacion faltante, limite y casos de calibracion.

## Estado interno

Antes de redactar, el agente resuelve sin mostrar:

- instruccion actual de Maxi;
- hechos confirmados y datos no confirmados;
- X del lead;
- encaje real;
- etapa conversacional;
- evidencia de interes;
- rama tecnica y certeza;
- excepciones activas;
- gol del turno;
- siguiente movimiento.

El historial completo tiene memoria dentro de la conversacion: un dato confirmado no se repregunta ni se contradice.

## Precedencia de ramas

1. Riesgo clinico que exige derivacion.
2. Minoridad confirmada.
3. Llamada ya aceptada.
4. Objecion activa.
5. Segundo rechazo o incompatibilidad confirmada.
6. Pregunta operativa.
7. Rama tecnica, comercial o conversacional normal.

Esta precedencia evita seguir calificando despues de una aceptacion, vender durante una derivacion o ignorar una objecion para abrir otra pregunta.

## Madurez e invitacion

La llamada requiere cuatro condiciones:

1. objetivo concreto;
2. aporte honesto de Tato;
3. interes demostrado;
4. madurez conversacional.

Aceptar la guia, nombrar un objetivo, agradecer o hacer una consulta tecnica aislada no alcanzan por si solos. Una respuesta detallada, una traba sostenida, un pedido de ayuda o una pregunta comercial pueden acelerar la madurez sin cumplir una cantidad fija de mensajes.

La ruta normal es:

`objetivo -> conversacion util -> interes demostrado -> invitacion -> agenda`

Tiempo, intentos, urgencia, prioridad, pago y online son datos opcionales, nunca un formulario obligatorio.

## Integracion tecnica y comercial

Ante una mencion tecnica, el agente:

1. identifica movimiento y hecho observable;
2. elige un solo patron respaldado;
3. distingue causa posible de hecho confirmado;
4. aporta una lectura o cue breve;
5. decide la salida por madurez, no por el mero hecho de hablar de tecnica.

Una charla temprana recibe ayuda puntual y, si hace falta, una pregunta natural. Una charla madura recibe esa misma muestra de valor y una invitacion conectada con lo que falta personalizar.

La ayuda gratuita termina antes de analizar videos, prescribir ejercicios, asistencia, series, repeticiones, frecuencia, progresiones o cambios de rutina.

## Primeras cinco dominadas

El agente distingue entre:

- entorno o seteo;
- control escapular;
- fuerza de traccion;
- coordinacion;
- practica especifica;
- fatiga.

Entiende la secuencia general de sentir, construir fuerza, integrar la primera dominada y consolidar repeticiones limpias. La goma puede servir para practicar tecnica aun despues de la primera repeticion libre. Estos principios orientan la lectura; no autorizan a entregar la rutina general del LOOM por DM.

## Contrato de salida

- Solo el DM listo para enviar.
- Un movimiento y como maximo una pregunta.
- Lineas cortas, voseo rioplatense y tono humano.
- Sin signos de apertura de pregunta o exclamacion.
- Sin dos puntos.
- Sin analisis, etiquetas, alternativas ni placeholders.
- Sin datos inventados, diagnosticos, promesas o programacion personalizada.

## Criterios de aceptacion

- Una respuesta breve con objetivo claro no dispara llamada automatica.
- Un mensaje detallado de alta intencion puede invitar sin filtros extra.
- Una consulta tecnica recibe una sola prioridad y no una clase.
- Una causa no observada aparece como hipotesis prudente.
- Una barra baja se reconoce como limitacion del entorno sin diagnosticar escapulas.
- Una pausa entre retraccion y tiron recibe un cue de continuidad.
- Una tercera dominada deformada se interpreta como calidad que no resiste la fatiga, sin regalar programacion.
- Una llamada aceptada pasa directamente a agenda.
- Precio, modalidad, minoridad, salud y rechazos usan su rama especifica.
- El DM final conserva una pregunta maxima, ningun signo de apertura y ningun dos puntos.

## Validacion

La validacion tiene tres capas:

1. `scripts/validate_runtime.py` comprueba estructura, UTF-8, frontmatter, rutas y marcadores obligatorios.
2. Busquedas de privacidad comprueban que la biblioteca no contenga timestamps ni transcripciones crudas.
3. Casos forward independientes ejercitan inicio, desarrollo, tecnica, madurez, objeciones y agenda sin compartir la respuesta esperada.

La validacion local demuestra coherencia, no conversion. La efectividad comercial debe observarse con chats reales: invitaciones menos prematuras, respuestas mas especificas y llamadas que nazcan de interes real.

## Compatibilidad y limites

- No cambian oferta, precio, duracion, agenda ni formato de salida.
- No se versionan backups ni datos privados.
- No se introduce base de datos, API, autenticacion ni automatizacion de envios.
- Si Maxi pide enviar por Instagram, se mantiene el envio linea por linea con verificacion entre lineas.

## Registro de decisiones

- 2026-08-05: se reemplazo el embudo largo por criterio de madurez y cuatro condiciones de llamada.
- 2026-08-14: se incorporo la biblioteca tecnica curada desde devoluciones y clases de Tato.
- 2026-08-14: se separaron hechos, hipotesis y personalizacion.
- 2026-08-14: se incorporo el mapa de las primeras cinco dominadas sin trasladar rutinas o dosis al DM.
- 2026-08-14: se agrego un motor agentico obligatorio y carga progresiva de referencias.
