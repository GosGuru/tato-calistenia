# Banco RAW offline

Cinco historiales completos e independientemente ficticios para preparar una revisión pequeña,
no una plataforma de evaluación. No usa chats privados, bases de producto, Auth, navegador,
servidor ni runner vivo. No modifica las reglas del setter. El smoke explícito permite únicamente
SQLite/config nuevos de Promptfoo dentro de su fixture temporal propio.

## Chequeo seguro

Desde la raíz del repositorio:

```text
tools/editorial_rag/.venv/Scripts/python.exe -B -m tools.editorial_rag.raw_evaluation --check
```

Sin argumentos hace exactamente lo mismo: valida el banco e imprime únicamente el manifiesto.
No escribe archivos, genera respuestas, abre procesos ni conecta a la red. No hay opción de
inferencia o exportación a disco. stdout puede ser capturado por la terminal.

El manifiesto declara `guidance: off`, modelo y esfuerzo `unknown`, resultados `not-run`,
SHA-256 y bytes de cada una de las siete fuentes completas de `real_history.RULE_PATHS`,
hash del conjunto de reglas y hash/bytes UTF-8 de cada prompt real. Se usa `load_real_rules()`
sin recortar ni normalizar. Una diferencia entre esa carga y las fuentes leídas aborta.
Los hashes identifican contenido, no prueban consentimiento, calidad ni autoría humana.

## Separación de datos

- `inputs.json`: lista ordenada de objetos con solo `id` e `history`. Sin fases,
  expectativas, orientación editorial ni próximo DM modelo. Se conserva el texto íntegro.
- `expectations.json`: mismos IDs y orden; tipo esperado y criterios para revisión
  independiente. Nunca entra en `RawHistoryPacket`, `raw_prompt` ni variables de generación.
- `no_inference_provider.py`: `call_api` siempre lanza un error, incluso con argumentos vacíos.
  No recupera resultados ni sirve como fallback.

Los casos contrastan continuidad con pregunta directa, apertura significativa, reentrada
fechada, impedimento después de agenda y rechazo después de aceptar llamada. Las intervenciones
anteriores del asistente son contexto ficticio, no respuestas correctas para copiar.

## API pequeña, solo memoria

En `tools.editorial_rag.raw_evaluation`:

| Función | Contrato |
| --- | --- |
| `load_bank()` | Lee rutas fijas; devuelve casos, expectativas y manifiesto. |
| `build_cases(inputs, current_rules)` | Pura; devuelve tupla de `CasePacket(id, packet, prompt, fingerprint)` usando `RawHistoryPacket` y `raw_prompt`, con orientación vacía explícita. |
| `result_record(case, output)` | Pura; valida una salida sintética ya existente con `parse_raw_result` y la vincula al ID/hash del prompt. No genera nada. |
| `export_bundle(cases, expectations, records)` | Pura; verifica casos, cobertura, IDs, orden, fingerprints y todas las salidas antes de devolver el conjunto completo. No escribe. |

Cada registro tiene exactamente `id`, `fingerprint`, `output`. `output` es el string JSON
original, no un objeto ya parseado: conserva la posibilidad de detectar claves duplicadas.
El parser real admite únicamente `{"type":"dm","text":"..."}` o
`{"type":"needs_context","question":"..."}`, sin campos extra, texto vacío ni fences.
Un resultado de aclaración no se convierte en DM. El tipo esperado se revisa por separado:
un desacuerdo semántico debe poder inspeccionarse, no desaparecer como error de transporte.

El conjunto devuelto contiene:

- `config`: un prompt `{{raw_prompt}}`, un proveedor Python que deniega inferencia y un test
  por caso, en el mismo orden. Cada `providerOutput` contiene exactamente el string RAW ya
  validado de ese caso. Solo aserción estructural `is-json`, sin juez LLM.
- `outputs`: **lista de strings**, serializable como JSON `list[str]`, un string de salida
  RAW por caso. No es una lista de objetos de resultados de Promptfoo.
- `expectations`: copia separada de los criterios para quien revisa, nunca parte del prompt.

No hay persistencia automática ni lector de resultados privados. El llamador debe mantener
la correspondencia con el payload realmente usado: crear después un registro con el hash
actual no demuestra que una salida anterior se haya producido con esas reglas.
Los helpers no acreditan que una entrada sea ficticia; esa responsabilidad sigue siendo humana.

## Lanzador fijado: importación ficticia verificada

`promptfoo_smoke.py` usa solamente Promptfoo **0.123.1** y Node portable **22.23.3**, ya
instalados bajo `%LOCALAPPDATA%/TatoEditorialEval`. No instala ni repara dependencias. Antes
de ejecutar verifica versión del paquete, pin exacto del manifiesto y SHA-256 de Node y lock.
No modifica el Node compartido. Los hashes fijados son:

- Node: `9c9245166b4a8e182e0b797da9c20136117ff24368eaff1fec8343a123c8db0e`.
- Lock: `a6b9733d7fd66248c2ac2bfeac6913163f62321c921f8ff3d7f140746b77e391`.

Desde la raíz, chequeo sin procesos, escrituras ni red; también es el comportamiento sin argumentos:

```text
tools/editorial_rag/.venv/Scripts/python.exe -B -m tools.editorial_rag.evaluation.promptfoo_smoke --check
```

Solo con autorización explícita, cada comando ejecuta un único proceso fijado, sin reintentos:

```text
tools/editorial_rag/.venv/Scripts/python.exe -B -m tools.editorial_rag.evaluation.promptfoo_smoke --probe-startup
tools/editorial_rag/.venv/Scripts/python.exe -B -m tools.editorial_rag.evaluation.promptfoo_smoke --smoke
```

El primero prueba `--version` con 120 segundos; el segundo tiene 180 segundos e importa
cinco strings etiquetados `MOCK_IMPORT_ONLY`. **No son respuestas observadas de un modelo.**
No admite comandos arbitrarios, archivos externos, historiales privados ni jueces.

### Mecanismo y límites

- `providerOutput` aprovecha la rama verificada de `callProviderForRunEval` en
  `evaluator-DlYW7Rgb.js`: conserva proveedor, prompt y variables, pero usa la salida existente.
  **No se usa `--model-outputs`**: en esta versión depende de `--assertions` y reemplaza el banco
  por tests con `echo` y `{{output}}`. La lista `outputs` sigue disponible por compatibilidad.
- La guarda `deny_network.cjs` se precarga mediante `node --require`, antes del SDK.
  Rechaza fetch, HTTP(S), HTTP2, TCP/TLS, UDP y DNS, incluidas promesas y resolvers; además
  rechaza procesos, Workers y arranque de servidores. No permite excepciones para Python.
  Sin marcadores de inicio/salida, o ante intento de proceso/Worker/listen, falla cerrada.
- El entorno hijo no hereda claves, proxies, `NODE_OPTIONS` ni `PYTHONPATH`. HOME, perfiles,
  temporales, config, cache, logs y cwd quedan bajo un directorio nuevo propio en
  `%LOCALAPPDATA%/TatoEditorialEval/tmp/`. Los opt-outs conocidos se fijan antes del import.
  Se limpia solo ese fixture; nunca configuraciones, bases o cachés previos.
- El eval usa concurrencia 1, `sharing: false`, aserción `is-json`, `--no-write`, `--no-cache`,
  `--no-table`, `--no-progress-bar` y `--no-share`. El reporte queda dentro del fixture y se
  valida con límite de tamaño, cinco filas ordenadas, salidas exactas, prompt cuando está
  presente y conteos 5/0/0. SQLite de arranque nueva puede existir aun con `--no-write`.
- Diagnósticos acotados muestran API, origen/host y archivo/línea de paquete, nunca payloads,
  credenciales ni rutas de pipes. Un bloqueo es un **intento rechazado**, no una solicitud enviada.
  Esta instrumentación de APIs Node **no es un sandbox del SO**, ni contención de código nativo,
  ni garantía de ausencia de rastros o auditoría de seguridad.

### Evidencia observada en esta intervención

| Etapa de verificación | Resultado |
| --- | --- |
| `--check` | Pins y banco válidos; no ejecución. |
| Arranque `--probe-startup` | Versión 0.123.1 validada; 2 `net.createConnection` rechazados; 0 intentos de proceso/Worker/listen registrados. |
| Smoke inicial | Lanzador terminó con código 1, sin clasificar la causa. 2 conexiones y 1 fetch rechazados; 0 intentos de proceso/Worker/listen registrados. |
| Smoke con diagnóstico mejorado | CLI 0; lanzador 1 por `Report identity or output mismatch`. Conteos 5/0/0 y cinco filas; importación todavía no acreditada. |
| Smoke tras corregir los mocks | **CLI 0 y `transport: passed`**. Cinco casos, conteos 5/0/0, orden, variables, salidas y prompts reportados exactos. Tres intentos rechazados; `forbidden: 0`. |

Cada invocación ejecutó la CLI una sola vez, sin reintentos automáticos. Las corridas posteriores
se realizaron después de añadir diagnóstico y luego de corregir la serialización, respectivamente.

Los dos callsites actuales son `node_modules/tsx/dist/client-XItNFmsq.cjs:1` y
`node_modules/tsx/dist/require-CBjy4Foe.mjs:8`. La lectura de esos archivos muestra conexión
al pipe del proceso padre; la ruta no se imprime. No se atribuyen retrospectivamente los dos
bloqueos históricos sin destinos a partir de esta observación nueva.

El fetch actual apunta a `https://r.promptfoo.app`, desde
`node_modules/promptfoo/dist/src/fetch-DpK1Rb6J.js:900`. La fuente de telemetría muestra que
`recordTelemetryDisabled()` también llama `sendEvent()` y este usa ese endpoint. Esto explica
una ruta compatible con el intento observado; no se capturaron cuerpo ni evento específico.
Cambiar el booleano de `1` a `true` no elimina esa rama. Todo permanece denegado.

El diagnóstico original del smoke conservó los bloqueos pero no distinguió error de CLI de
rechazo del reporte. Se agregaron motivos estáticos seguros y cobertura DNS TLSA en las unidades.
La ejecución diagnóstica posterior clasificó el rechazo; la tabla conserva ambos fallos previos.

### Corrección acotada de serialización y cierre independiente

El verificador independiente informó una ejecución posterior con retorno CLI 0, conteos
5/0/0 y cinco filas aprobadas, pero el lanzador rechazó el reporte con
`Report identity or output mismatch`. Ese error compuesto no identificó el primer campo
diferente. La fuente del SDK sí establece una incompatibilidad determinista: serializa
`testCase.providerOutput` con parseJSON y JSON.stringify compacto, mientras el mock usaba
los espacios predeterminados de `json.dumps`.

`prepare_bundle` ahora crea únicamente sus mocks ASCII `MOCK_IMPORT_ONLY` con separadores
compactos antes de vincularlos y exportarlos. No normaliza salidas aportadas ni modifica
`export_bundle`, el proveedor o las comparaciones exactas de `validate_report`.
La prueba pura reproduce esa serialización solo en una copia profunda de `testCase`,
conserva `response.output` crudo y mantiene los siete casos negativos. Falló antes del
cambio con el mismo rechazo y pasó después, junto con la prueba de importación inerte.

El verificador independiente ejecutó después **un smoke corregido** y validó el reporte completo.
Pasaron también 23 pruebas Python del banco/lanzador, 5 de la guarda Node y 26 regresiones
RAW/historial/runner. Se mantuvieron iguales los 25 hashes seleccionados antes/después de esa
verificación y el inventario superior del directorio temporal; no quedó un fixture nuevo propio.
Esta actualización documental es posterior a aquella medición, no parte de su igualdad de hashes.

El alcance aprobado es únicamente el transporte de los cinco mocks fijados. No certifica
importación arbitraria, visor, integración con Codex, chats privados ni calidad de respuestas.
Los seis chequeos LSP quedaron inconclusos; la evaluación nativa no estuvo disponible y RDD
permaneció desactivado. No se repararon esas herramientas. Los fallos históricos se conservan;
IPC rechazado no equivale a tráfico de Internet enviado. Nuevas ejecuciones requieren autorización.

## Pruebas y perfil

```text
tools/editorial_rag/.venv/Scripts/python.exe -B -m unittest tools.editorial_rag.test_raw_evaluation tools.editorial_rag.test_promptfoo_smoke
```

Las unidades Python mockean subprocess; las Node reemplazan capacidades reales por sentinelas
inertes **antes** de cargar la guarda, incluso en RED. Cubren conservación del banco, fallos de
esquema/orden, pins, entorno, timeout, limpieza, redacción y familias de APIs. Todos los fixtures
nuevos se dirigen al `tmp` administrado, no a perfiles o bases existentes.

Modelo y esfuerzo siguen `unknown`, orientación `off`, calidad `not-evaluated`. La validez
JSON no puntúa voz, seguridad semántica, intención, conversión ni naturalidad. No hay resultados
reales, modelos ganadores ni autorización para transmitir datos.
