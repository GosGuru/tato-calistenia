# Shadow checks de Tato — optativos y manuales

Esta herramienta aislada está fuera de la carga automática del skill. No cambia
el comportamiento actual de Tato, modelos, esfuerzo, configuración, runtime,
validadores ni hooks. No se integra con producción ni concede permisos del host.
Usala solo por decisión explícita, como segunda lectura de un borrador.

## Uso desde la raíz (ejemplo sintético, Bash)

```sh
printf '%s' '{"version":1,"text":"qué querés mejorar?","closure":"active","call_accepted":false}' | python -B tools/tato_checks/dm_guard.py
python -B tools/tato_checks/test_dm_guard.py
```

Entrada exclusivamente JSON UTF-8 por STDIN, máximo 16384 bytes. No acepta rutas,
argumentos de entrada, historial ni campos adicionales. Las cuatro claves son
obligatorias; se rechazan duplicados, tipos incorrectos, versiones desconocidas,
JSON malformado y constantes no JSON. `version` es el entero `1` (no booleano);
`text` es una cadena no vacía de hasta 4096 caracteres; `call_accepted` es booleano.
`closure` es uno de estos valores declarados por quien llama:

- `active`: conversación activa, exactamente un `?` al final tras quitar espacios.
- `minor`: menor confirmado; `rejection`: rechazo claro.
- `investment_impossible`: inversión imposible; `incompatibility`: incompatibilidad real.
- `safety`: emergencia o fuera de alcance; `followup_limit`: límite alcanzado.
- `booking_confirmed`: reserva confirmada sin otro freno activo.

Los siete cierres excepcionales exigen cero `?`. Son declaraciones, **no hechos
verificados**: el script no decide si corresponde cerrar ni interpreta palabras
para inferir seguridad, aceptación, disposición, fases o estado del lead.

## Resultado y límites

STDOUT contiene únicamente JSON genérico sin repetir el texto. Códigos de salida:
`0` = `mechanical_pass`; `1` = `mechanical_findings`; `2` = `invalid_input`;
`3` = `manual_review` por contexto no soportado. Hallazgos mecánicos prevalecen
si coinciden con uno manual. Siempre incluye `semantic_review_required: true`
y `enforcement: "manual_shadow"`. **Cero no aprueba semántica ni autoriza envío.**

Comprueba signos de apertura, cercas de código, cantidad/posición literal de `?`
y dos puntos fuera del enlace. La única agenda admitida es exactamente
`https://cal.com/tato-ramon/reunion-auditoria`, en línea propia y con aceptación
de llamada declarada. Agenda en un cierre terminal requiere revisión manual.
Detecta algunas formas monetarias de 300 (USD, US$, $, dólares); 300 repeticiones
no falla por el número. No es un detector exhaustivo de precios o enlaces.

Otros recursos con sintaxis de URL reconocible van a revisión manual, no se
prohíben como nueva política: las promesas requieren contexto. Controles no
imprimibles y sustitutos Unicode también quedan fuera de alcance. Un contexto
complejo que no entra en este esquema se revisa manualmente **sin ejecutarlo**;
el programa no puede detectar complejidad semántica ausente de sus datos.

No evalúa intención, voz, primera persona, una idea por línea, cantidad real de
preguntas sin `?`, veracidad, fase, precedencia de objeciones, ruta, seguridad,
contador de follow-ups, reserva real ni cumplimiento de recursos prometidos.
No reescribe, envía, llama proveedores, abre archivos, guarda entradas/salidas,
registra logs, consulta CRM, usa red o ejecuta subprocesos. Solo los tests usan
subprocesos CLI con entradas sintéticas y leen el pack local. Ejecutá con `-B`
para evitar bytecode. Los límites de tamaño son del harness, no reglas del DM.

## Comparación posterior, separada

`tools/tato_checks/stability_cases.json` contiene cinco pares sintéticos de
criterios y contraejemplos, no frases modelo ni chats reales. Unittest comprueba
su estructura, **no ejecuta modelos ni demuestra estabilidad semántica**.
Si después decidís comparar, usá el MISMO modelo real, esfuerzo y ajustes de tu
Codex, en conversaciones frescas y cargadas de correcciones. Evaluá decisiones
por separado de estos checks mecánicos, sin elegir ni cambiar modelo ahora.
No hay ejecución automática, resultados de modelo ni efectos en Tato.
