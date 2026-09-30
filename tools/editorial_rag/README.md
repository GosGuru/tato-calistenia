# DM directo, revisión avanzada y comparador editorial local

Aplicación local FastAPI + React, con Codex mediante la suscripción de ChatGPT y biblioteca
editorial opcional. No modifica las fuentes normativas del setter ni conecta CRM o Instagram.
Las pruebas de conversación usan textos ficticios, no historiales reales.

## Banco RAW offline

[Banco ficticio y chequeo sin inferencia](evaluation/README.md): cinco historiales completos,
expectativas separadas y preparación en memoria de salidas existentes para Promptfoo.
El chequeo no escribe ni llama modelos; Promptfoo no se instala ni ejecuta en esta unidad.

## Aviso sonoro en Responder

Al recibir un DM válido de una generación iniciada con clic o Enter, Responder intenta emitir
un único ting suave y breve. No suena al abrir la pantalla, ante errores ni pedidos de contexto.
Es una síntesis local original, no una copia exacta del sonido de ChatGPT; no descarga audio.
El navegador, el sistema operativo o una pestaña silenciada pueden impedir que se escuche.
Podés silenciar la pestaña o el sistema; un bloqueo de audio no afecta el DM ni provoca reintentos.

## Candidato actual — UI y sesión recordada, activación pendiente

RAW usa Enter para **Generar con Codex** y Shift+Enter para nueva línea. Al generar, mueve el historial
íntegro a un bloque superior con entrada ascendente y vacía el input; el resultado o error aparece debajo.
**Editar historial** lo devuelve al mismo input. Se conservan las guardas de conexión, Auth, IME y petición
en curso. El loader tiene marca editorial T y texto contextual,
sin etapas ni streaming; la respuesta completa tiene entrada finita, scroll acotado y copia original
con icono/confirmación solo después del portapapeles. Tipografía sans del sistema y superficies oscuras
redondeadas; privacidad/criterios ampliados en Biblioteca. No se envía a Instagram.

Biblioteca distingue estado desconocido, cantidad disponible verificada y sesión recordada. Conectada
muestra acciones, no un formulario vacío. El store opcional Windows guarda solo el refresh token cifrado
para el usuario actual, con versión/proyecto/dueño, bajo `%LOCALAPPDATA%/TatoEditorialRag/session.dpapi`.
No persiste contraseña, email, access JWT, historial ni borrador; no usa storage/cookies del navegador.
Restauración/renovación acotadas, validación de dueño y lectura autenticada/RLS, rotación atómica y
logout con invalidación de respuestas tardías. Sin fallback plano/no-Windows ni garantía de permanencia
o borrado seguro. Un error de almacenamiento nunca confirma sesión recordada.

**Backend real no reiniciado ni activado.** La UI funciona con el servidor anterior: 404 en el nuevo GET
opcional `/api/auth/persistence` significa persistencia no activada. La función requiere un reinicio
posterior coordinado; no interrumpir una generación para activarla. Bootstrap/status conservan sus
esquemas. `create_app()` por defecto sigue siendo memory-only; solo el launcher compone el store.

No se cambiaron motor, reglas, prompts, RAG, fichas, embeddings, SQL, CRM, dependencias ni CSP.
Arneses actualizados, sin ejecución de navegador por el writer; aprobación visual y eficacia semántica
no demostradas. #59 no utilizado. Incidente del primer RED Auth y evidencia nueva detallados en
[UI_REDESIGN.md](web/UI_REDESIGN.md); no se reutiliza el hash histórico de 58 archivos como prueba nueva.

### Corrección P2 actual — pérdida de transporte en metadata

El GET opcional de persistencia ahora invalida la conexión/nonce mediante `onDisconnect` cuando
falla el transporte vigente, dentro de la guarda existente. Conserva historial RAW y bloquea Generar
hasta reconexión explícita, sin POST automático/reintento. 404, otros HTTP y JSON/formato inválido no
rompen baseline; epochs anteriores de conexión/Auth y desmontaje no desconectan la sesión nueva.
No cambia layout, fuentes ni backend.

RED observado: **1 fallo esperado / 6 pasan / 61 omitidos por filtro**. Primera corrida conjunta:
**78 pasan / 3 fallan**, por fixtures RAW que también rechazaban metadata; se explicitó 404 para ese
GET en dos fixtures sin debilitar aserciones ni conteos. Resultado final: **85/85** en AppAuth/App,
**191/191** frontend (siete archivos), typecheck y build exit 0. Once casos nuevos. Assets nuevos:
`index-HchAyKAx.js`, `index-D1fNOLx3.css`, `highlighted-body-KPVGNVTW-DQ1Q5O5I.js`; anteriores
retenidos. Avisos use-client/sourcemap/chunk grande presentes; typecheck no amplía cobertura JSX.
Comandos exactos y detalle en [UI_REDESIGN.md](web/UI_REDESIGN.md).

Evidencia independiente aportada, anterior al fix: frontend 180/180 y backend cercado 71/71, cero
errores/omisiones/red denegada/FS protegido/fuera de temporal/procesos. RAW
`%TEMP%/tato-raw-fixture-E5mxZO/report.json`: PASS, 13 POST ficticios (11 RAW + 2 Auth), una
intercepción previa al envío, cero modelos reales/producción. FullUI
`%TEMP%/tato-ui-fixture-kGDLk8/report.json`: PASS, 22 checks, tres POST ficticios, cero externos/modelos.
Ambos incluyen capturas de carga; el padre inspeccionó RAW desktop carga/largo y móvil vacío.
Son evidencia previa, no prueba de la nueva regresión. FullUI `profileRetained: true`; no se afirma
eliminación del perfil. Sin rerun Python/navegador, activación ni reinicio. Aprobación visual humana
pendiente, #59 sin uso, probe de socket sin resolver y sin afirmación de calidad de respuestas.
El incidente HTTP 400 externo permanece divulgado; el conteo exacto de intentos sigue desconocido.

### Corrección acotada de tests — verificación previa al P2

`AppAuth.test.jsx` usa planes explícitos por ruta/método para el GET opcional de persistencia y los
POST Auth. Conserva las aserciones de petición pendiente, desmontaje, finalización única y respuestas
obsoletas; agrega contabilidad cerrada, payload/nonce exactos y rechaza requests no planificados.

- `(cd tools/editorial_rag/web && npm test -- --run src/AppAuth.test.jsx)`: **13/13**, exit 0.
- `(cd tools/editorial_rag/web && npm test -- --run)`: **180/180**, siete archivos, exit 0.
- Resuelve los cinco fallos de fixtures anteriores (175 aprobados / 5 fallos). Sin cambios de producto
  o arnés ni rebuild. Se conservan `index-COK9C9Bf.js`, `index-D6_tyvuv.css` y
  `highlighted-body-KPVGNVTW-DgXWFciC.js`.
- Backend 71/71, typecheck, build, sintaxis y runtime son evidencia de la ronda anterior, **no reejecutada**.
  Navegador y aprobación visual siguen pendientes; no se activó ni reinició el servidor.

**Incidente conservado:** el primer RED de
`RememberedAuthTests.test_saving_failure_preserves_baseline_and_never_claims_remembered` mockeó
`sign_in_session`, pero omitió el camino heredado `app_auth.load_config/sign_in`. `AppAuth.login`
leyó la configuración real predeterminada y llegó a `_sign_in`/transporte externo con literales de
credenciales ficticias creados para ese test. Se observó un aviso `HTTPError 400`; el número exacto de
intentos externos es desconocido por falta de instrumentación. No se observó autenticación exitosa.
Se agregaron mocks explícitos y denegación de sockets antes de continuar. Esta corrección no repitió
la petición ni accedió a configuración real. El verde actual no vuelve aislada aquella corrida.

## Evidencia histórica — implementación anterior, no valida el candidato actual

Responder ahora abre como una pantalla conversacional: título centrado, aire y composer de hasta
780 px, sin panel de borrador vacío. La superficie redondeada ahora contiene solo entrada corta y
acciones; los avisos informados y contador quedan visibles inmediatamente debajo. Sin etiqueta visible
duplicada, con label accesible y scroll interno que no recorta texto. Tras generar, el único resultado aparece arriba del mismo
**Historial preparado**, editable y completo, con copia manual e inicio de lectura arriba.
No hay historial de turnos ficticios ni afirmación de envío. Botón circular con nombre accesible
**Generar borrador**; Enter agrega líneas. Avisos de transmisión, consumo, datos sensibles y
**No se envía a Instagram** visibles. Criterios, privacidad ampliada y técnica siguen desplegables.
Canvas casi negro, sidebar de 240 px y superficies neutrales también en revisión, comparador y Biblioteca.
Se mantienen sus flujos opcionales, confirmaciones separadas y dos llamadas explícitas del comparador.
Abrir Biblioteca conserva el historial; cambiar de modo lo descarta como antes. La API solo informa
estado/cantidad: no se inventan títulos, aplicación ni aprobación. No cambia backend/API/Auth/RAG/Codex.

Refinamiento: RED focalizado **1 fallo esperado / 48 pasan**, GREEN **49/49**. Verificación
independiente final: **170 frontend (49 RAW), typecheck/build/sintaxis pasan**. Los **40 HTTP** y
runtime válidos son evidencia independiente anterior, no reejecutada en la última ronda del arnés.
Código de app sin cambios desde el compacto; assets actuales: `index-gGrxjJHi.js`,
`index-DMxX8UdQ.css`, `highlighted-body-KPVGNVTW-D5yRjRZX.js`; anteriores retenidos.
Persisten avisos use-client/sourcemap/chunk grande y exclusión del JSX heredado de TypeScript.

**RAW PASS independiente:** `%TEMP%/tato-raw-fixture-fC7Pa7/report.json` y `gallery.html`,
129 checkpoints; nueve capturas canónicas y tres detalles inspeccionados. Superficie real
780×142 desktop / 358×150 móvil, textarea 88/96 px; disclosure 14 px debajo de la superficie
(29 px debajo de Generar). Desktop 1366×768/1920×1080; móvil viewport 390×844, páginas completas
390×844 vacío, 390×1027 largo, 390×844 error y detalles 390×844. Pasaron historial/copia íntegros,
Enter, aclaración no copiable, identidad con Biblioteca/Auth, disclosure y reconexión. Diez POST HTTP
planificados exactos y una intercepción validada; transporte un fetch/una intercepción/cero entregas,
sin replay. CSP/storage/cookies/style tags/externos/runtime/modelos: cero; contraste no medido.

**FullUI PASS independiente:** `%TEMP%/tato-ui-fixture-cMlFRk/report.json`, 22 checkpoints y diez
PNG inspeccionados, sin galería HTML. Siete desktop 1440×1000 y tres móvil 390×844, todos de viewport.
Pasaron editor/avanzada por Escape, un clic exterior avanzado, Sheet móvil por Escape/backdrop y
retorno al nodo iniciador exacto; foco modal/scroll lock, Biblioteca con borrado de credenciales y
pegado conservado, Markdown/reconexión/recarga. Comparador: demo y consentimiento de dos llamadas
inicialmente deshabilitado, cancelado sin generar. Tres POST fixture (dos RAW + demo); Auth/generate,
modelos reales, externos y runtime: cero. Checkpoints CSP/storage/cookies/styles/overflow horizontal: cero.
El rótulo fixture tapa parcialmente un control inferior del Sheet móvil en PNG: no hay prueba de
visibilidad sin obstrucción para todos los controles ni certificación general de accesibilidad.

Los fallos anteriores `veAjsx`/`RDwPwZ` son históricos. Las correcciones fueron del arnés
(espera de lifecycle/foco y punto interior de backdrop), no de Escape/backdrop del producto;
el PASS no establece su causa exacta. El probe separado `--diagnose-transport` / `adDAry`,
un fetch/dos entregas al destruir el socket, sigue sin resolver ni reejecutar; no se corrigió idempotencia.

Hash agregado del writer antes/después: 58 archivos,
`47163ed2353ea216edc738cf390e6ecb57fc684530ff08b02b820869315eddef`.
El verificador no estableció independientemente esa base/hash; no prueba integridad retroactiva.
**Implementación y verificación funcional no equivalen a aprobación visual de Maxi: #63 pendiente.**
**#59 no utilizado.** Evaluación de eficacia de DMs diferida; sin prueba de Auth/DB/modelos reales ni
mejora de respuestas de leads. Mismo motor, sin Next, chats persistidos, voz/archivos o cambios normativos.

Contexto aportado por el padre: relanzó una vez el servidor tras un rechazo fresco; Pencil integrado
cargó/permitió DOM, pero su captura agotó la espera. No acredita uptime permanente, causa de terminación,
plugin Chrome ni readiness actual. Este cierre solo actualiza documentación, sin comandos ni procesos.
Detalles y límites en [UI_REDESIGN.md](web/UI_REDESIGN.md).

## Evidencia histórica del diseño 45/55 — NO valida el diseño actual

Las secciones hasta «Estado actual del despliegue y mantenimiento manual» conservan evidencia anterior.
Los PASS, capturas, tamaños y assets mencionados allí son históricos, no verificaciones del nuevo diseño.

### Verificación funcional independiente histórica — default PASS

Evidencia independiente: **166 frontend, 40 HTTP, types, build y runtime verdes** sobre el mismo source
de app, sin cambios posteriores; no se reejecutaron en la última ronda de arnés ni en este cierre documental.
Assets actuales: `index-DMmHDA4r.js`, `index-DjIXiPiM.css`, `highlighted-body-KPVGNVTW-DnyU59sl.js`.
Persisten las advertencias de build sobre use-client, sourcemap de diagnóstico y chunk grande.

El default `(cd tools/editorial_rag/web && node scripts/raw-ui-browser-check.mjs)` corrió una vez:
**exit 0, 9,729 s, 129 checkpoints**. Evidencia en `%TEMP%/tato-raw-fixture-4hUcyV/report.json`
y `gallery.html`. **9 capturas canónicas + 3 detalles móviles**, todas inspeccionadas independientemente,
con píxeles del footer consistentes. Cada viewport (1366×768, 1920×1080, 390×844) cubre vacío/largo/error.
PNG móviles completos 390×1385/1626/1518, viewport y detalles 390×844. Sidebar 216 px, padding 24/28 px,
45/55, scroll global desktop 0 e inicio/final de scroll interno con footers verificados.

Pasaron Enter sin POST, historial completo/pending, Markdown hostil, copia original/fallo, needs_context,
disclosures e identidad con Biblioteca/sidebar, malformación, HTTP/transporte y reconexión.
Totales: **10 POST HTTP ficticios + 1 intercepción de transporte**; inesperados, externos, modelos,
errores runtime, CSP, storage, cookies y style: **0**. Contraste no medido; no certifica accesibilidad
completa ni producción. Capturas de demostración ficticia aislada, sin simulaciones en producción.

La corrida previa `tato-raw-fixture-lvEfso` llegó a 9+3 imágenes, pero falló por un POST no planificado;
permanece histórica, no describe el resultado del default actual.

El probe separado `tato-raw-fixture-adDAry/004-diagnose-transport-observed.json` observó **un fetch y
dos entregas HTTP** al destruir el socket. La segunda recibió 409; el mecanismo exacto sigue sin
probarse. No hubo llamadas a modelos ni corrección de backend/idempotencia. No inferir ausencia de
replay a partir de contadores filtrados. La investigación HTTP queda fuera de este alcance UI.

El default **verificado en 4hUcyV** aisló la falla de transporte frontend con
CDP `Fetch.failRequest` antes de enviar el único POST planificado: valida body/token del fixture,
esperó el gate de loading y observó un fetch, una intercepción validada y cero entregas al servidor.
Verificó UI desconectada/generación deshabilitada, historial conservado, sin Copy y GET de reconexión
con nonce fresco sin replay; otros casos conservan HTTP normal. `--diagnose-transport` mantiene
el probe de socket y su rechazo estricto de entregas extra. Son pruebas distintas, no garantía contra
reentregas reales. Detalles y contabilidad en UI_REDESIGN.md.
El PASS default **no resuelve el probe adDAry**: no fue allowlisted ni reparado. Backend/idempotencia
siguen intactos; la investigación futura queda fuera del alcance UI.

### Aprobación visual humana de aquella unidad — pendiente

**#63 sigue ABIERTO y NO aprobado; falta aprobación visual de Maxi; #59 no se utilizó.**
La inspección independiente de capturas no sustituye esa aprobación. Sin Auth, DB o Codex reales;
producción 8765 no se accedió ni se gestionó. Este cierre solo cambia documentación, sin comandos.
El primer recorrido Chrome independiente quedó incompleto por un clic sintético del driver que no
activó la pestaña avanzada. Solo alcanzó Biblioteca y el resultado raw; esto no prueba un fallo de la UI
avanzada. El driver corregido usa eventos CDP reales; las correcciones anteriores del árbol se interrumpieron.
Ese recorrido permanece como evidencia histórica separada del PASS default RAW actual.

- [Alcance, evidencia, CSP, comando offline e incidente Engram separado](web/UI_REDESIGN.md).
- [Fuentes oficiales, SHA256, fechas, licencias y adaptaciones](web/THIRD_PARTY_NOTICES.md).

## Estado actual del despliegue y mantenimiento manual

`002` está desplegada: pgvector **0.8.2** en `extensions`, FORCE RLS y vista SECURITY INVOKER.
Están aprobadas e indexadas únicamente `connect_help_to_concrete_gap` y
`resolve_concrete_doubt_first`, con aprobación `rag-route-477d0773ba554530bd58040ca01d5f79`.
La activación fue atómica y la lectura posterior por la conexión de solo lectura confirmó
textos sin cambios, dos vectores de 384 dimensiones y sus hashes exactos. Las otras tres
fichas conservan `candidate` y aprobación nula. No reejecutar el seed ni las migraciones.

La prueba de roles de PostgreSQL confirmó propietario = 2 filas, otra identidad = 0,
SELECT anónimo denegado y ausencia de permisos de escritura de vectores para `authenticated`.
Esto no sustituye una sesión Auth real. El inicio y chequeo anterior en
`http://127.0.0.1:8765/` son evidencia histórica, no disponibilidad actual. Al comenzar
esta reparación se reportó `connection_refused` y cero listeners en 8765; la causa de
la terminación anterior sigue desconocida. **El ingreso real desde Biblioteca y la
generación viva del flujo principal siguen pendientes**. Login exacto de ChatGPT y
flags aceptados por la ayuda de CLI 0.147.0 no demuestran generación.
Las verificaciones independientes anteriores pasaron 156 tests Python y 121 de frontend.
El chequeo visual de la pantalla principal fue pasivo, con texto ficticio y cero generaciones.
No se evaluó aún la calidad semántica del nuevo flujo con RAG.

Las secciones marcadas como etapas previas conservan evidencia histórica, no el estado
actual del despliegue. El plan offline siguiente explica la operación ya aplicada, no la autoriza
ni debe ejecutarse nuevamente.

`prepare_route_seed.load_snapshot(path)` lee JSON estricto de hasta 64 KiB;
`validate_snapshot(data)` verifica exactamente los dos IDs, dueño, campos y
fingerprints observados en PostgreSQL antes de inferir. `prepare(data)` llama
una sola vez a `local_embedding.embed_passages` con los dos pasajes completos,
sin normalización ni truncamiento. Un exceso de tokens detiene el plan sin retry.
Devuelve SQL y reporte, nunca conecta ni ejecuta SQL. No es una autorización.

El CLI `python -B -m tools.editorial_rag.prepare_route_seed --snapshot <snapshot>
--output-dir <directorio>` crea exclusivamente `route-seed-plan.sql` y
`route-seed-report.json`, sin sobrescribir. Un fallo de escritura puede dejar un
artefacto parcial: no aplicarlo ni reintentar automáticamente. El reporte contiene
IDs, fingerprints, pin del manifest, dimensión, normas y SHA-256 del SQL; stdout
agrega los hashes de ambos archivos, sin vectores ni prosa. Los errores son fijos.

El SQL manual bloquea las tablas durante una única transacción, coteja contenido
y candidatos, aprueba solo los dos IDs e inserta dos vectores con metadatos.
Comprueba conteos, vista, aprobación y hashes antes del commit. El hash del vector
usa `vector_send`: cabecera big-endian dimensión/reservado y floats IEEE754 de
32 bits. Nueve cifras significativas se usan solo si conservan los mismos bytes
float32; en otro caso se conserva `repr`. Requiere revisión/aplicación y readback
independientes por el padre. No prueba permisos vivos ni calidad semántica.
Con solo dos fichas, recuperar hasta dos puede incluir ambas: el orden por coseno
**no significa aplicabilidad ni calidad**.

## App Auth + RAG opcional — integración local

La pantalla principal conserva **pegar → un clic informado → una generación Codex**.
**Biblioteca** es un desplegable opcional: abrirlo no borra el historial ni inicia
inferencia. La cuenta solicitada es la existente de **EDITORIAL SUPABASE**, no ChatGPT
ni Instagram. Sin conectar, la generación usa las siete reglas completas.

- `AppAuth` mantiene el access JWT en memoria. Sin store inyectado conserva el login heredado.
  Con store explícito Windows también recibe un refresh token para cifrado DPAPI y renovación acotada.
  No consulta `.env`; el proyecto y dueño siguen fijados por configuración pública validada.
  `sign_in(email, password, *, transport=None, config=None)` permite un `LibraryConfig`
  validado y confiable; omitirlo conserva el comportamiento ambiental del checker/login
  heredado. Ninguna ruta acepta proyecto, clave, propietario ni JWT del cliente.
- La conexión exige propietario igual al config **y una lectura autenticada exitosa**
  de `read_library`. Decodificar claims no verifica firma: Supabase debe verificarla y
  aplicar RLS. Una biblioteca vacía conecta, pero no aporta criterios. Password/email se
  limpian de la UI tras el intento/cierre. No hay registro ni reset. El launcher habilitado restaura
  una vez al arrancar; un snapshot de generación explícita puede renovar una sesión vencida una vez,
  sin timers, reintentos ni llamadas a modelos desde Auth.
- `GET /api/auth/status` devuelve exactamente `{connected, empty, count, revision}`:
  booleanos/enteros, sin credenciales. `count` corresponde a la lectura de conexión, no
  una garantía de disponibilidad futura. No consulta red ni ejecuta modelos al consultar
  estado. `POST /api/auth/login` acepta solo `{email, password}` (320/4096 caracteres,
  cuerpo máximo 32768 bytes); `POST /api/auth/logout` acepta solo `{}`. Heredan Host,
  Origin, CSRF en POST, no-store y CSP. Los errores son genéricos.
- Los intentos simultáneos de login no se encolan: solo uno puede ejecutarse. Cada intento
  admitido y desconexión cambia la revisión; una desconexión invalida un login tardío.
  Cambios explícitos descartan borradores, no el texto pegado. Solo se admite el dueño
  configurado: no hay transferencia entre cuentas. Sin store la sesión se pierde al reiniciar;
  con store se intenta restaurar y verificar, sin promesa de ingreso permanente. Desconectar quita la
  copia local y frena restauraciones/rotaciones tardías; un fallo de eliminación se informa. No cierra
  otras sesiones Supabase/MCP/Codex.
- La UI mantiene en `App` una barrera síncrona compartida con `RawDM`: cada login/logout
  explícito bloquea el botón y el handler de generación hasta que todos los intentos pendientes
  terminen. Inicio y finalización (éxito o fallo) invalidan resultados, errores y copias tardías,
  sin borrar el historial pegado. Cerrar Biblioteca no cancela Auth; navegar cierra sus
  controles sin remontar la instancia Auth y cada petición conserva su finalización en el padre. Navegar conserva el
  descarte de historial existente. Desmontar el padre evita actualizaciones tardías de React.
  Una GET de estado no activa esta barrera. El epoch local es solo invalidación de UI, **no**
  la `revision` del servidor; se valida el formato del sobre sin igualar ambos contadores.
  Un nuevo clic tras finalizar o vencer naturalmente la sesión puede generar baseline,
  incluso con una revisión del servidor mayor. No hay cancelación, timeout ni retry nuevos;
  una petición Auth que siga pendiente mantiene el bloqueo hasta terminar.
- `rag_service.retrieve(auth, history)` obtiene criterios frescos mediante GET fija con
  JWT de dueño; **jamás envía historial ni vectores de consulta a Supabase**. Sin caché de
  orientación. `embed_query` y `ranklocal` trabajan localmente, sin descarga automática;
  ranking aporta hasta dos criterios y nunca confianza o fase confirmada. `_FLIGHT` cubre
  lectura, embedding y la única llamada del runner existente, compartido con los otros flujos.
- `RawHistoryPacket(..., guidance=())` agrega solo fase/puerta/situación/movimientos y
  criterios positivo/negativo acotados. Son **condiciones, nunca hechos de este lead**.
  El estado se infiere exclusivamente del historial; aplicabilidad, seguridad, motor y
  oferta prevalecen. No envía vectores, IDs, hashes, JWT, claves ni citas de fuentes a Codex.
- `/api/raw-draft` conserva el request exacto y devuelve el sobre estricto
  `{result: {type: 'dm', text} | {type: 'needs_context', question}, retrieval: {status, count}, revision}`.
  `status` es `supplied` (1–2 criterios aportados, no necesariamente aplicados), `off`,
  `empty`, `expired` o `unavailable` (todos con cero). Los cuatro últimos son resultados
  explícitos de solo reglas, sin retries, candidatos ni fallback de proveedor.
  Malformaciones fallan cerradas, sin salida parcial. Cambiar/desconectar sesión o vencer
  durante una solicitud descarta éxito/error tardío con 409. Un clic nuevo tras vencimiento
  sí puede generar baseline: no se confunde con validar una solicitud vieja.
- El loader público separa lectura/parseo de su excepción final para no retener datos
  rechazados en los locales del traceback. Esto **no acredita borrado seguro de memoria**.

El despliegue de 002, los dos embeddings CPU, la activación exacta, el readback y la
comprobación de roles/RLS ya fueron ejecutados por separado. El acceso Auth real del usuario
y una evaluación semántica con Codex siguen pendientes; los tests simulados no los sustituyen.
No se afirma una instancia permanente ni una sesión Auth conectada. El comparador heredado conserva sus
**dos llamadas explícitamente informadas**.

## Biblioteca vectorial editorial — foundation sin activación (etapa previa)

Esta unidad agrega contratos locales y una migración candidata, **no despliega SQL,
activa fichas, inicia Auth ni integra RAG con la app o Codex**. No acredita mejora de
DMs. La app de un clic y el comparador con dos llamadas informadas siguen iguales.
Los casos de prueba son ficticios. Las referencias a ausencia de vectores más abajo
corresponden al lector/esquema heredados; `002` es una extensión separada ya aplicada.

### APIs y límites

- `library_config.load_config(path=DEFAULT_PATH) -> LibraryConfig`: JSON público de
  hasta 8192 bytes en `C:/Users/Maxim/AppData/Local/TatoEditorialRag/library-config.json`.
  Claves exactas `version` (entero 1), `project_url`, `publishable_key`, `owner_id`.
  Origen HTTPS fijo del proyecto, publishable moderna y UUID canónico no nulo.
  Rechaza duplicados, extras y formatos inválidos; no lee ni modifica entorno,
  credenciales o configuración global. El override de ruta es para tests confiables.
  El lector heredado y el default de Auth conservan su comportamiento ambiental previo.
- `fingerprint(owner_id, card)` y `criterion_passage(card)` aceptan contenido candidato
  actual sin aprobarlo. El pasaje incluye fase, puerta, situación, movimiento previo,
  propuesto y criterios positivo/negativo; no agrega ejemplos ni historial.
  `embed_passages` agrega el prefijo, no el helper. Más de 512 tokens sigue rechazado.
- `parse_criterion(row, expected_owner) -> Criterion`: conserva `owner_id`, `card`
  (todos los campos originales), `approval_id`, `fingerprint` y `EmbeddingRecord`.
  Exige aprobación, sanitización, propietario, hash vigente, pin completo, 384 valores
  finitos y norma L2 con tolerancia 1e-4. Declaraciones no prueban sanitización semántica
  ni consentimiento. La coincidencia con la aprobación **actual** la aporta la vista.
- `read_library(access_jwt, config, *, transport=None) -> tuple[Criterion, ...]`:
  una única GET a `/rest/v1/editorial_runtime_library`; no acepta historial ni vectores
  de consulta. Reutiliza claims/JSON/transporte estrictos heredados. Claims son solo
  preflight; Supabase debe verificar firma. Propietario igual al config; filtros exactos
  para todos los metadatos del modelo, orden por `card_id`, solicita 51 y rechaza más
  de 50 sin paginación silenciosa. Hasta 2 MiB; timeout de socket 10 s, no deadline total.
  Sin proxies ambientales, redirects, retries, refresh, logs ni escrituras. Errores fijos
  fuera del handler sin encadenar excepciones de HTTP. El test hook es código confiable.
- `ranklocal(criteria, queryvectors, max_results=2) -> tuple[RankedCriterion, ...]`:
  hasta 50 criterios, 1–64 chunks completos y máximo dos resultados. Coseno exacto
  dividido por ambas normas; toma el **máximo sobre todos los chunks** para no diluir
  una condición localizada. Puede sobreponderar menciones viejas o irrelevantes:
  semejanza no decide aplicabilidad. Desempate por ID ascendente, sin umbral 0.8,
  filtro de fase heredado ni fase inferida. `rank`, `similarity`, `criterion`, `advisory`
  no son confianza ni permiso para convertir. Reglas y condiciones siguen mandando.

### Esquema y ABI del hash

`002_editorial_embeddings.sql` es one-shot aditiva; **no reaplicar 001**. Colisiones
con tabla, vista o función abortan. Instala `vector` en `extensions` si falta;
rechaza una extensión existente en otro esquema, sin relocalizarla.

`public.editorial_card_embeddings` tiene PK/FK compuesta `owner_id, card_id` hacia
`editorial_cards`; columnas `approval_id`, `fingerprint`, `model`, `revision`,
`spec_version`, `preprocessing_version`, `runtime_version`, `graph_sha256`,
`dimensions`, `embedding extensions.vector(384)`. Norma acotada y metadatos con límites.
No toca la tabla original ni su trigger revocador. ENABLE/FORCE RLS, SELECT de dueño
para authenticated solamente; sin INSERT/UPDATE/DELETE de app ni acceso anon/public.

`public.editorial_runtime_library` usa SECURITY INVOKER. Une por dueño, ficha,
aprobación actual y hash; exige `approved` y `sanitized`. Exporta todos los campos
Card más dueño, aprobación, hash y metadatos anteriores, con `embedding::text`.
RLS aplica en ambas tablas; revocación, edición o reaprobación invalidan la unión.
No hay RPC de similitud: la base guarda vectores de criterio, jamás consultas.

`public.editorial_content_fingerprint(c public.editorial_cards)` usa SHA-256 nativo
con search_path vacío, sin SECURITY DEFINER. EXECUTE solo authenticated; devuelve
hex minúscula. Orden fijo compartido con `CONTENT_FIELDS`:

1. owner_id (UUID canónico), card_id, provenance_id
2. phase, gate, situation, last_assistant_move, proposed_move
3. positive_voice, negative_repetition, sanitized (`true`/`false`)

Cada campo es `longitud_decimal_en_bytes_UTF8:bytes_UTF8_originales`, concatenados
sin otro separador. No normaliza Unicode ni depende de serialización JSON. Estado y
aprobación no se hashean: `approval_id` se vincula por separado. NUL y sustitutos Unicode
se rechazan en Python como incompatibles con texto PostgreSQL/UTF-8.

`MODEL_METADATA` deriva de `embedding_node/model_manifest.json`, no de copias Python:
model, revision, spec_version, preprocessing_version, runtime_version, dimensions y
SHA-256 del grafo q8. SQL admite metadatos acotados; el lector exige el pin exacto del
manifest vigente y por eso no mezcla modelos. Un cambio de manifest exige reindexación
explícita, nunca reutilización silenciosa.

### Plan administrativo pendiente, no ejecutado

1. Completado por el padre: 002 aplicada, pgvector 0.8.2 en `extensions`,
   FORCE RLS y vista invoker. No reaplicar.
2. Obtener solo las dos fichas de ruta autorizadas y su contenido actual; calcular
   fingerprint/pasaje sobre esos candidatos, sin inventar aprobación. Embedding offline
   por pasaje completo usando el manifest; si excede tokens, detenerse, no truncar.
3. En transacción administrativa posterior, bloquear las filas y cotejar el hash actual
   con el indexado. Solo con aprobación exacta vigente asignar `status=approved` e IDs
   opacos reales. Insertar en la tabla separada dueño/ficha, esos IDs, hash, los siete
   metadatos del manifest y cada vector. Un cambio concurrente exige volver a revisar.
4. Readback administrativo y luego GET autenticada autorizada: comprobar exactamente
   esos dos IDs, aprobación, hash y pin. Probar revocación/reaprobación y edición, anon,
   otro dueño y ausencia de permisos de escritura con fixtures de prueba separados.
   Los tests SQL aquí son estáticos: **no prueban RLS ni ejecución PostgreSQL real**.
5. Integración con LLM/app y evaluación semántica quedan separadas. No hay login real,
   despliegue, seeds ni activación en esta entrega.

Validación observada de esta unidad: 8 tests focalizados y 126 tests Python completos
pasan; validador de runtime pasa. RED previo: tres imports faltantes de las APIs nuevas.
No reapareció Windows 10053 en esta ejecución, sin afirmar que esté reparado. La suite
emitió una deprecación existente de Starlette/httpx; no se cambiaron dependencias.
Las pruebas usan transportes simulados y no ejecutan inferencia ni SQL.

## Base de embeddings locales — etapa previa aislada

Se agregó una unidad opt-in separada. **No cambia la app de un clic ni conecta SQL,
Auth, UI, Codex, fichas o recuperación editorial.** No hay servicio de fondo, llamadas
pagas, fallback de red, lectura de historiales ni activación de las dos fichas.

### Preparación explícita

```bash
(cd tools/editorial_rag/embedding_node && npm install --ignore-scripts --no-audit --no-fund --cache C:/Users/Maxim/AppData/Local/TatoEditorialRag/npm-cache)
tools/editorial_rag/.venv/Scripts/python.exe -B -m tools.editorial_rag.model_setup
node tools/editorial_rag/embedding_node/smoke.mjs
```

La instalación ya observada agregó 53 paquetes. Transformers.js **3.8.1**,
ONNX Runtime Node **1.21.0** y sharp **0.34.5** cargaron en Windows con Node
**22.21.1**, sin ejecutar postinstall. `node_modules` ocupa **391.553.345 bytes**;
ese tamaño instalado no es el total transferido por npm, que no fue medido.
No ejecutar scripts nativos automáticamente si otra instalación falla.

El setup descarga únicamente cinco assets de `Xenova/multilingual-e5-small`, revisión
`3acb1fa45c83e69002b1641b37f3cccc132cdd63`: **135.392.183 bytes** verificados.
Cache fija de esta instalación:
`C:/Users/Maxim/AppData/Local/TatoEditorialRag/models/Xenova/multilingual-e5-small/3acb1fa45c83e69002b1641b37f3cccc132cdd63/`.
No utiliza `main`, autenticación, proxies ambientales ni el repositorio completo.
Cada archivo se valida por longitud y hash publicado antes de publicación atómica;
los JSON pequeños usan identidad Git blob SHA-1, no SHA-1 plano. Tokenizer y ONNX
usan SHA-256. Reutiliza assets válidos; un asset existente corrupto falla cerrado y
requiere mantenimiento explícito, no se sobrescribe ni carga. Los parciales propios
se limpian ante fallo. No hay descarga automática durante inferencia.

### API y contrato

```python
from tools.editorial_rag.local_embedding import embed_query, embed_passages

# Solo entrada efímera aportada explícitamente por el llamador.
query_vectors = embed_query(history)
criterion_vectors = embed_passages(texts)
```

- `embed_query(str) -> list[list[float]]`: 1–24.000 caracteres Unicode, hasta 64
  chunks. Tokeniza con prefijo inglés `query: ` y tokens especiales incluidos;
  divide recursivamente por puntos de código hasta un máximo real de 512 tokens.
  Verifica que concatenar los chunks reconstruya exactamente el input. No recorta,
  normaliza, deduplica, reescribe ni infiere fase. Exceder 64 chunks falla cerrado.
- `embed_passages(list[str] | tuple[str, ...]) -> list[list[float]]`: 1–8 criterios,
  hasta 24.000 caracteres por entrada, prefijo `passage: `, un vector por criterio.
  **Rechaza** más de 512 tokens; no divide ni trunca pasajes.
- 384 dimensiones, attention-mask mean pooling y normalización L2. Valida valores
  finitos y norma unitaria. Se usa AutoModel/AutoTokenizer directamente: el pipeline
  genérico de feature extraction habilita truncamiento internamente y aquí se evita.
- Una ejecución Node por batch, CPU `q8`, stdin JSON; ningún texto en argv, archivos,
  caché o logs del adaptador. Entorno hijo con lista permitida de variables del SO,
  sin API keys, Auth, proxies ni `NODE_OPTIONS`. Timeout de 180 segundos y stdout
  limitado a 1 MiB; stderr descartado. Errores públicos fijos sin contenido recibido.
- `embedding_node/model_manifest.json` es la especificación compartida para futuros
  fingerprints: `spec_version=multilingual-e5-small-q8-mean-l2-v1`,
  `preprocessing_version=e5-prefix-lossless-codepoint-split-v1`. Conserva revisión,
  hashes, dimensiones, prefijos, límites y pooling. El fingerprint SQL candidato se
  describe en la unidad de biblioteca anterior; no está desplegado.

El smoke real verificó CPU, `env.allowRemoteModels=false`, cachés automáticas
inhabilitadas, dimensión/norma de una query y dos pasajes **inventados**, y cobertura
completa de 24.000 caracteres sintéticos repartidos en 16 chunks usando el tokenizer
real. No acredita calidad semántica ni aislamiento hermético de red del sistema
operativo. La partición de 24.000 caracteres se probó con tokenizer; no se ejecutó
inferencia de los 16 chunks en ese smoke. No hay borrado seguro de memoria/swap.
Ver licencias y procedencia en `embedding_node/THIRD_PARTY_NOTICES.md`.

Los cosenos altos habituales del modelo no son probabilidad de fase, calidad ni
aplicabilidad. La selección local y los contratos de biblioteca se describen arriba;
quedan pendientes despliegue, aprobación/activación exacta de dos fichas e integración
con el flujo actual. El historial original completo del flujo de un clic sigue sin
cambios; este módulo no modifica lo que se transmite al generar con Codex.

### Validación observada

- 11 tests Python focalizados y 4 tests Node con datos sintéticos: pasan, sin descargas.
- Setup y smoke CPU reales: pasan. Validador estático del runtime: pasa.
- Suite Python completa: 118 tests, un error en
  `test_browser_login.BrowserTests.test_reject_boundaries` por Windows `10053`
  (`ConnectionAbortedError`). No se modificó ese código ni se acredita toda la
  suite verde; la entrega queda parcial hasta resolver/verificar ese fallo aparte.

## Responder conversación — pegar y generar

La pantalla principal **Responder conversación** permite pegar el historial completo y
pulsar **Generar borrador**. El aviso adyacente explica que ese clic autoriza **una** llamada a
Codex: transmite el historial y las siete reglas actuales completas a OpenAI, con consumo
de límites de la suscripción. No exige casillas, asignación de roles ni diálogos previos.
Quitá datos sensibles innecesarios antes de generar y revisá el resultado antes de copiarlo.
No hay anonimización automática, envíos a Instagram/ManyChat ni garantía de retención cero.
La cabecera principal es compacta y las herramientas avanzadas quedan en navegación secundaria.
La transmisión a OpenAI y el consumo de una generación permanecen visibles junto al botón;
los detalles de privacidad, retención, aislamiento, modelo y cancelación están en
**Privacidad y límites**, un desplegable nativo cerrado inicialmente, sin confirmación adicional.

- `GET /api/bootstrap` entrega `{app: 'tato-local', protocol: 1, csrf_token, model: 'unknown', effort: 'unknown'}`;
  no carga el caso sintético, fichas ni reglas y no invoca Codex. El comparador solicita
  `/api/context` solo al abrir su pestaña; su fallo no bloquea la pantalla principal.
- `POST /api/raw-draft` acepta exactamente `{history: string, consent: true}`. No acepta
  reglas, roles, fase, fichas ni otros campos del cliente. `consent` es booleano estricto
  y una declaración del cliente, no prueba de consentimiento humano o privacidad.
- `RawHistoryPacket` conserva el string recibido sin parsear, dividir, normalizar CR/LF,
  deduplicar ni asignar autores. El navegador puede normalizar saltos en su textarea;
  la app transmite el valor disponible allí sin reorganizarlo. Máximo **24.000 caracteres
  Unicode**, cuerpo UTF-8 de **300.000 bytes**. No se trunca; rechaza vacío, controles
  salvo CR/LF/tabulación y sustitutos Unicode aislados. No impone límites por mensaje.
- El prompt aporta íntegros los mismos siete archivos enumerados más abajo, desde
  `load_real_rules()`, nunca fichas candidatas ni ejemplos recuperados. El historial es
  JSON no confiable, no instrucciones. El modelo debe interpretar evidencia de autores
  sin inventarla desde nombres, alternancia sola o avisos de interfaz. Razona con cautela
  desde contenido y contexto: etiquetas ausentes o autoría histórica irrelevante incierta
  no justifican aclaración. `needs_context` se reserva para ambigüedad que cambia materialmente
  el próximo DM seguro y no puede resolverse con una respuesta conversacional normal;
  los datos ordinarios pendientes de calificación se preguntan en el DM.
  Un posible pegado duplicado del export completo no acredita más contactos, follow-ups
  ni recencia nueva. Se conserva todo el texto y no se descartan mensajes genuinamente repetidos.
  Los tests verifican estas instrucciones y preservación, no su cumplimiento semántico por el modelo.
- El campo `result` del sobre de respuesta contiene una unión cerrada: `{"type":"dm","text":"..."}` o
  `{"type":"needs_context","question":"..."}`. Sin claves extra/duplicadas, fences ni
  salidas parciales; el texto es no vacío y acotado. La aclaración es para quien opera:
  **no se presenta como DM ni ofrece Copiar DM**. Completá el historial y generá de nuevo
  solo si querés autorizar otra llamada. No hay reintentos automáticos ni encadenamiento.
- Reutiliza Host/Origin/CSRF, CSP, no-store y `_FLIGHT` compartido con todos los flujos.
  Formato inválido falla antes del runner; concurrencia devuelve 409; fallo de reglas,
  proceso o salida devuelve 502 fijo sin eco del historial o diagnóstico.
- Editar, limpiar o navegar invalida resultados y errores tardíos. No garantiza cancelar
  una llamada iniciada ni recuperar cuota. Copiar requiere un clic separado; no envía.

**Revisión avanzada** conserva opcionalmente el flujo anterior de organización por roles,
revisión y confirmaciones. **Comparador sintético** conserva su demo manual y confirmación
de dos llamadas. La integración opcional de biblioteca se limita a la pantalla principal;
no activa candidatos ni cambia fuentes normativas. La nota anterior de despliegue/activación pendiente
correspondía a una etapa histórica y queda reemplazada por el estado documentado al comienzo:
las dos fichas ya fueron activadas por separado. La evaluación semántica y Auth/Codex vivos siguen
pendientes; este rediseño no prueba disponibilidad de producción.

## Revisión avanzada — flujo opcional

Los pasos, parsers y límites por mensaje de esta sección corresponden únicamente a la
pestaña **Revisión avanzada**, no al pegado directo de la pantalla principal.

### Abrir o actualizar la app ya preparada

Abrí normalmente `tools/editorial_rag/start_app.cmd` desde el Explorador, fuera del
agente. También podés ejecutarlo desde la raíz en CMD:

```cmd
tools\editorial_rag\start_app.cmd
```

El launcher resuelve la raíz desde su ubicación, comprueba el Python del venv y el
índice del build existente, y ejecuta síncronamente
`tools/editorial_rag/.venv/Scripts/python.exe -B -m tools.editorial_rag.local_web`.
**Mantené esa ventana abierta**. Ctrl+C cierra tu instancia; al terminar o fallar,
la ventana espera una tecla para que puedas leer el aviso. No instala, compila,
abre navegador, reinicia ni configura servicios o tareas.

Abrí **http://127.0.0.1:8765/** manualmente, sin proxy ni servidor de Vite. En Windows,
`main()` reserva exclusivamente ese socket con `SO_EXCLUSIVEADDRUSE` y entrega el
mismo socket a Uvicorn en primer plano, cerrándolo al salir. No hay probe/cierre/rebind,
adopción ni eliminación de listeners ajenos. Puerto ocupado, permisos o requisitos
faltantes requieren revisión humana, no un segundo puerto o reinicio automático.
Los tests simulados no demuestran la duración de una ventana abierta manualmente.
Vite conserva assets anteriores (`emptyOutDir=false`); el índice apunta al build nuevo.

### Reconectar sin perder el pegado

Ante pérdida conocida de transporte, la UI invalida síncronamente nonce, resultados,
confirmaciones y la presentación de biblioteca conectada, sin desmontar el historial.
**Reconectar** hace solamente GET `/api/bootstrap` y luego GET `/api/auth/status`.
Valida `app=tato-local` y `protocol=1`, usa el nonce nuevo en todos los flujos y descarta
respuestas de epochs anteriores. El marcador identifica el esquema, no autentica al
servidor ni demuestra propiedad del puerto. No repite POST, credenciales ni generaciones.
Bootstrap no depende de reglas, fixtures, Auth externo, RAG ni inferencia; una consulta
de estado pendiente no bloquea el baseline después de bootstrap válido.

Después del reinicio coordinado que active el nuevo launcher, una sesión recordada puede restaurarse
solo tras renovar y verificar propietario/RLS. Si no existe o falla, conectá manualmente desde
**Biblioteca**. No se reenvía la contraseña y un archivo existente no acredita conexión. Sin biblioteca se conservan las siete reglas; con biblioteca se aportan
hasta dos criterios condicionales, no necesariamente aplicables. Generar nuevamente
siempre requiere otro clic deliberado. Desconexión no demuestra cancelación ni ausencia
de una ejecución Codex previa. HTTP 403 no demuestra por sí solo CSRF vencido, ni HTTP
502 demuestra un fallo del modelo. JSON/sobre inválido y rechazo HTTP se distinguen de
una imposibilidad de contactar el servidor; ningún fallo se presenta como éxito.

### Diagnósticos acotados del flujo principal

`POST /api/raw-draft` conserva el sobre exitoso exacto `{result, retrieval, revision}`
y los cuerpos fijos de error. Agrega cabeceras de metadatos por solicitud:

- `X-Tato-Diagnostics: 1`.
- `X-Tato-Exec-Attempts`: `0` o `1`, intentos de iniciar el proceso exec, **no** facturación,
  uso de proveedor ni garantía de que una generación ocurrió.
- `X-Tato-Total-Ms` y `X-Tato-Total-Outcome`.
- `X-Tato-{Retrieval|Rules|Packet|Login|Exec|Stream|Raw-Result}-{Ms|Outcome}`.

Duraciones finitas en milisegundos, acotadas a 86.400.000. Outcomes cerrados `ok`,
`not_run`, `timeout`, `unavailable`, `rejected`, `nonzero`, `invalid`, `internal`.
`Stream` mide el parseo del JSONL ya capturado, **no** tiempo al primer token. La
recuperación que retorna baseline válido puede tener outcome `ok`; `retrieval.status`
sigue indicando si aportó criterios. No hay logs, archivos ni último-request global,
excepciones crudas, stdout/stderr, prompts, historial, JWT, claves, IDs, argv o texto
modelo en estas cabeceras. Rechazos de frontera, solicitudes incompletas o desconectadas
pueden no traerlas; su ausencia no demuestra que no hubo ejecución. El runner acepta
diagnósticos opcionales sin exigirlos a sus llamadores anteriores. No agrega retries,
flags, cambios de timeout/modelo ni relajación de los parsers.

La verificación independiente, el lanzamiento manual y el ingreso de Biblioteca preceden
la única generación sintética viva autorizada al padre/verificador. No ejecutarla desde
el worker ni repetirla automáticamente si falla; los tests mock no la reemplazan.

1. **Pegar:** pegá el historial cronológico y elegí **Revisar conversación**. La separación
   por párrafos y fechas es local y no hace llamadas. No hace falta escribir etiquetas.
2. **Revisar:** mirá las burbujas, fechas originales y roles pendientes. **Ver avisos separados**
   permite inspeccionar y restaurar avisos, reacciones y encabezados. Los textos ambiguos
   permanecen como mensajes. Editá textos solo cuando haga falta, en un diálogo; también
   podés dividir en el cursor o separar un mensaje reversiblemente.
3. Opcionalmente, revisá los datos que permitís transmitir y abrí **Organizar con Codex**.
   Una confirmación explícita autoriza **una** llamada que propone autores para los IDs
   existentes, sin reescribir, quitar ni reordenar mensajes. Nunca encadena generación de DM.
   Los roles inciertos requieren confirmación o corrección individual; las propuestas
   seguras también requieren tu revisión global y no son atribuciones de plataforma.
   Podés omitir este paso, en particular para etiquetas explícitas ya reconocidas.
4. **Responder:** revisá la conversación completa, marcá su casilla y elegí **Generar respuesta**.
   Una confirmación independiente autoriza **una** llamada con las siete reglas completas.
   Cancelar o Escape no transmite. Sin organización opcional son una llamada total; con
   organización y generación son dos. La separación local siempre cuesta cero llamadas.
5. Revisá el DM y usá **Copiar DM** solo cuando quieras escribir al portapapeles. No se envía.

Quitá identificadores, contacto y datos sensibles innecesarios antes de cualquier transmisión.
No hay anonimización automática ni detector semántico de privacidad. El servidor valida
`reviewed=true` y `consent=true` como declaraciones del cliente, no como prueba de revisión humana.
El contador muestra solicitudes confirmadas, no consumo verificado de cuota: un rechazo
HTTP puede ocurrir antes de invocar el modelo. Reintentos manuales suman nuevas solicitudes.

Cada generación, regeneración o reintento exige otra confirmación. Editar invalida
revisión y borrador; limpiar o cambiar al comparador descarta el historial de la
pantalla. Una respuesta tardía no repone un resultado invalidado. **Limpiar, salir o
cerrar no garantiza cancelar una llamada ya iniciada**, ni recuperar cuota consumida.

### Formato soportado y límites

Ejemplo enteramente ficticio, no una transcripción privada:

```text
Prospecto: quiero empezar
con más control
Tato: qué venís haciendo hoy?
```

- Etiquetas exactas `Prospecto:` y `Tato:` al inicio de línea, sin indentación;
  mayúsculas/minúsculas son indistintas. Se permite comenzar con cualquiera, repetir
  un rol y usar varias líneas por mensaje. No se infieren nombres como roles.
- Se conserva el orden. CRLF/CR se normalizan a LF; las etiquetas reconocidas y un
  espacio opcional se separan del mensaje. Líneas en blanco delimitan párrafos. Los
  saltos internos, puntuación y URLs permanecen; no se visitan enlaces. Cada bloque
  conserva una referencia `source_id` al fragmento original. Al dividir, solo el primer
  descendiente conserva el literal `source`; los otros comparten la referencia sin duplicarlo.
  Esto permite reconstruir la fuente normalizada exactamente una vez incluso tras editar
  y volver a dividir. No se afirman offsets entre texto editado y fuente original.
  El pegado sigue disponible en memoria; la procedencia nunca se transmite.
- Se reconocen líneas completas de interfaz: activación de automatización, etiqueta
  añadida, cambio de estado, asignación, pausa temporal, respuesta a historia, contenido
  no disponible y expiración en horas. Sus valores variables no aportan hechos ni autores.
  Las menciones parciales o entre comillas permanecen como contenido. Todo aviso y reacción
  separado es inspeccionable y restaurable.
- El encabezado inicial `Todo el historial de canales`, nombre y `Yo` admite líneas
  vacías intermedias; conserva ese fragmento fuente completo como metadata reversible.
  No se reconoce esa estructura en mitad del chat.
  Nombres aislados, alternancia, pausas y texto parecido a automatización no prueban autor.
  El catálogo es conservador, no un parser universal de todas las variantes ManyChat.
- Las fechas numéricas, fechas con mes inglés abreviado o completo (`3 Oct 2025, 09:20`),
  días ingleses/españoles y horarios independientes reconocidos
  conservan su texto literal, sin resolver días relativos ni inventar anclas. Se muestran
  en las burbujas y se proyectan como `[Fecha/hora original: ...]` dentro del texto revisado
  enviado a `/api/draft`; el API original no cambia. Ese contexto también cuenta en límites.
  Las fechas reconocidas también se pueden restaurar como mensajes desde **Ver avisos separados**.
  Restaurar una falsa fecha recalcula el contexto posterior usando solo las fechas restantes,
  sin mantener el ancla descartada ni inventar fechas.
- Editar permite corregir prosa, URLs y saltos. Dividir conserva ambos lados del cursor
  y crea IDs nuevos con roles pendientes; no divide pares Unicode. Separar no borra:
  mueve el bloque a avisos restaurables en su posición original. No hay reordenamiento.
- El comparador sintético también invalida resultados, errores y confirmaciones al cambiar
  de pestaña o limpiar. Las respuestas tardías no repueblan resultados. La solicitud en curso
  sigue bloqueando duplicados hasta terminar; navegar no garantiza cancelar el proveedor.
- Editar el pegado original reconstruye los bloques y reemplaza sus ediciones. Solo
  los bloques revisados se transmiten, nunca el pegado original ni identificadores extra.
  Toda edición de texto, rol, división o eliminación invalida revisión, modal y borrador.
- Máximo **24.000 caracteres Unicode** sumados entre textos revisados; **100 mensajes**,
  **4.000 caracteres** por mensaje. Se rechazan controles salvo tabulación/saltos
  admitidos y Unicode inválido. No se trunca el pegado: dividí o editá antes de generar.
- `POST /api/draft` admite dos formas cerradas y mutuamente excluyentes:
  `{messages: [{role: 'user'|'assistant', text: string}], reviewed: true, consent: true}`
  o la forma heredada `{history: string, reviewed: true, consent: true}`. No admite
  campos extra, roles pendientes ni tipos coercionados. La forma heredada conserva
  el parser estricto original y su límite de 24.000 caracteres con etiquetas:
  requiere etiquetas desde la primera línea y prosa con dos puntos indentada, salvo URLs.
  Exige las fronteras Host, Origin y CSRF existentes.
  Cuerpo JSON UTF-8 de hasta **300.000 bytes**, igual que `/api/organize` y `/api/raw-draft`.
  Las otras rutas conservan su límite de 256 bytes.
  Rechazos de formato/esquema devuelven error fijo antes de construir el runner.
  Comparte el lock de generación sintética: concurrencia devuelve 409. Fallo de
  generación devuelve 502 fijo, sin excepción, historial ni borrador parcial.
  Éxito contiene únicamente `{"draft": "..."}`. No hay reintentos automáticos.

### Organización opcional y componentes

`POST /api/organize` acepta exclusivamente `{blocks, reviewed: true, consent: true}`.
Cada bloque tiene exactamente `{id, text, role, time_context}`; rol `user`, `assistant`
o `unknown`, fecha literal string o null. El prompt define `user` como prospecto entrante
 y `assistant` como Tato saliente; conserva `unknown` si falta evidencia y no atribuye
 autor por nombres, avisos ni alternancia. Son 1–100 bloques, IDs únicos de 1–64 caracteres
ASCII alfanuméricos/guion/guion bajo, 4.000 caracteres por texto, 200 por fecha y 24.000
sumados entre textos y fechas. El pegado local también tiene límite de 24.000 caracteres.
No hay truncamiento silencioso. Se exige editar o reducir al excederlo.

La respuesta tiene exclusivamente `{assignments: [{id, role, uncertain}]}`. El servidor
exige cobertura completa y ordenada, booleanos estrictos, preservación de roles conocidos
y `unknown` siempre incierto; rechaza claves duplicadas, campos de contenido, fences,
reescrituras y JSON parcial. Errores fijos antes del runner para entradas inválidas;
una invocación sin reintentos para entradas válidas. Comparte `_FLIGHT` con draft y
comparación; conserva Host/Origin/CSRF, CSP y no-store. El runner sigue validando JSONL,
herramientas, autenticación y warnings exactos como antes. No carga reglas de DM para
organizar. El cliente valida nuevamente todos los IDs y descarta respuestas de otra revisión.

**Nota histórica de la revisión avanzada anterior, reemplazada por el rediseño de UI:**
React/Vite y CSS local usaban componentes reales [Radix Primitives](https://www.radix-ui.com/primitives/docs/overview/introduction):
[Dialog](https://www.radix-ui.com/primitives/docs/components/dialog) para edición/consentimiento
y Tabs para separar conversación y comparador. Se instaló ScrollArea junto al conjunto autorizado,
pero el historial usa desplazamiento nativo CSS, sin necesitar estilos dinámicos de ScrollArea.
En aquella etapa no se habían incorporado Tailwind ni código AI Elements. Esa descripción ya no
representa la UI actual: ahora incorpora Tailwind 4, shadcn/ui Radix y subsets oficiales AI Elements
según [UI_REDESIGN.md](web/UI_REDESIGN.md), con versiones en manifest/lock y procedencia documentada.
No se adoptaron Next.js, transporte AI SDK, backend externo, claves nuevas ni fuentes remotas.

Los tests de DOM validan diálogos por nombre accesible, foco/Escape y Tabs. No constituyen
una auditoría completa de accesibilidad o CSP en navegador real. Para una prueba visual segura,
la recomendación histórica de usar `create_app()` queda reemplazada por el arnés Node aislado
`scripts/ui-browser-check.mjs`: sirve únicamente fixtures ficticios y build en un puerto propio,
sin importar backend ni acceder a cuentas. El primer recorrido fue incompleto; la ejecución
independiente posterior `tato-ui-fixture-cMlFRk` pasó 22 checkpoints y sus diez capturas fueron
inspeccionadas. El alcance, las limitaciones y la aprobación visual pendiente se detallan en
[UI_REDESIGN.md](web/UI_REDESIGN.md).

### Reglas y privacidad del modo real

El servidor lee completos, sin truncar y sin selección del cliente, estos siete
archivos actuales bajo `.agents/skills/tato-calistenia/` en cada generación:

1. `SKILL.md`
2. `references/motor-agentico.md`
3. `references/voz-escrita-tato.md`
4. `references/operativa-dm.md`
5. `references/contexto-maestro.md`
6. `references/objeciones-agenda.md`
7. `references/biblioteca-tecnica-tato.md`

`real_history.py` usa un paquete separado de mensajes ordenados `role`/`text`, reglas
actuales y declaraciones de revisión/consentimiento. No inventa fase, puerta,
situación, sanitización ni orientación editorial. El prompt pide razonar desde todo
el historial, tratarlo como JSON no confiable —nunca instrucciones— y devolver un
solo próximo DM sin herramientas ni lecturas adicionales. No carga corpus,
mantenimiento, fuentes externas, ledger ni fichas. Esa instrucción no demuestra
resistencia semántica a inyección ni calidad del resultado: revisá siempre el DM.

La app no guarda historial o resultado en archivos, bases, caché, logs ni storage del
navegador. Permanecen transitorios en memoria y viajan al servidor local solo al
confirmar. El prompt se transmite por stdin al CLI y luego a OpenAI. No es inferencia
offline ni una garantía de retención cero: proveedor/CLI pueden conservar datos según
sus controles y políticas. El runner `read-only` **no es hermético** y puede acceder
a archivos del host; rechazar eventos de herramientas no revierte accesos ocurridos.
Los límites del navegador, extensiones, sistema operativo, swap, dumps y portapapeles
siguen fuera del control de la app. No hay borrado seguro de memoria ni limpieza del
portapapeles al limpiar la pantalla. Usá un navegador/host confiable y revisá los
controles de datos del proveedor antes de autorizar cada transmisión.

Esta implementación se verifica con datos ficticios y runner/fetch simulados, incluyendo
capturas inspeccionadas en un navegador real aislado. Esa evidencia no acredita uso de chats
privados, éxito de Codex en vivo, aprobación visual de Maxi ni calidad semántica de producción.

## Contrato de entrada del comparador sintético

La interfaz llamadora construye `Card`, `Conversation` y `Message` de
`tools.editorial_rag.prototype`. El núcleo comparador no tiene CLI, lectores de archivos, rutas de chats,
importadores CRM, recuperación de fuentes ni acceso a memoria persistente.

- Cada ficha contiene ID opaco, ID de procedencia (no cita ni ruta), estado,
  declaración `sanitized=True`, fase, puerta, situación, movimiento previo,
  movimiento propuesto, orientación positiva de voz y orientación negativa de
  repetición. No existe campo de respuesta modelo, cita cruda ni ejemplo para copiar.
- Solo `approved` puede recuperarse. Otros estados son válidos para filtrarlos,
  pero nunca llegan como orientación al paquete del modelo.
- La conversación exige declaración de sanitización y una tupla inmutable de
  mensajes de un solo caso. La interfaz aporta fase, puerta, situación y movimiento
  previo ya interpretados; el prototipo no los infiere ni habilita llamadas.
- `sanitized=True` y `approved` son declaraciones del llamador, no prueba de
  anonimización o consentimiento. Una revisión humana debe verificar ambas antes
  de construir estos objetos. No hay detector semántico de datos privados, citas
  encubiertas o instrucciones maliciosas. Nunca pasar entradas crudas a esta API.

## Recuperación reproducible

1. Excluir fichas no aprobadas y exigir coincidencia exacta de puerta y fase.
2. Exigir al menos un token compartido entre situaciones (Unicode, minúsculas).
3. Puntuar `10 × tokens distintos compartidos + 3` si coincide el movimiento previo.
4. Restar 20 si el movimiento propuesto repite el último movimiento del asistente
   y existe un mensaje anterior del asistente.
5. Elegir mayor puntaje; desempatar por ID ascendente. IDs duplicados son error.

Sin elegibles devuelve `None`, sin fallback global. La penalización es relativa:
no prohíbe toda repetición ni garantiza la mejor elección editorial. Los pesos
son heurísticos sin calibración; no hay embeddings, stemming ni umbral semántico.

## Consumo desde una interfaz experimental

```python
from tools.editorial_rag.prototype import packets, compare

# Objetos sanitizados y revisados, construidos por la interfaz, no desde archivos.
current, editorial = packets(conversation, cards, current_rules)
# La interfaz puede presentar ambos paquetes para inspección, sin ejecutarlos.
report = compare(conversation, cards, current_rules, runner)
```

`current_rules` es el mismo texto de reglas actuales aportado explícitamente por
el llamador para ambas variantes. El paquete editorial agrega únicamente criterio,
no respuestas recuperadas. La interfaz debe preservar esas reglas como autoridad
y tratar mensajes y orientación como datos delimitados, no instrucciones superiores.
No cambiar fase, seguridad, oferta ni secuencia a partir de una ficha.

`runner(packet) -> str` admite un callback externo o el adaptador local opcional
`CodexSessionRunner` descrito abajo. El comparador no ejecuta modelos por defecto.
Para una comparación real, ejecutar cada variante en una sesión fresca, con mismo
modelo y esfuerzo registrados por la interfaz. El callback debe ser independiente
entre llamadas y no persistir borradores ni transmitir datos sin autorización.
El prototipo no puede aislar o controlar los efectos laterales de código externo.

El informe devuelve solo ID seleccionado y señales mecánicas por variante:
igualdad tokenizada con el asistente inmediatamente anterior, mismos dos tokens
iniciales, cantidad de trigramas compartidos con ese mensaje y con la orientación.
No devuelve ni guarda borradores, no elige ganador y nunca declara aprobación
semántica, seguridad, intención o calidad de voz. La ausencia de coincidencias no
prueba originalidad. No se garantiza que un modelo externo no copie frases:
el paquete lo prohíbe y los trigramas ayudan a detectar coincidencias, nada más.

## Privacidad y despliegue

- El comparador puro no realiza escrituras, logs, red, caché ni registro de leads.
  El adaptador opcional invoca un proceso con red y autenticación propios de Codex;
  sus límites se detallan abajo.
- Sin envíos a Instagram, ManyChat, CRM ni cambios en el runtime.
- No se verificó remotamente Supabase desde este código. La unidad de persistencia
  agrega SQL para revisión humana, un lector y un chequeo manual opt-in; no hay uploads.
- Un archivo privado de originales es solo conceptual: **no hay raw vault**,
  importación ni implementación de archivo. No subir datos crudos ni fuentes.
- Tampoco se accedió a fuentes privadas para desarrollar este prototipo.

## Adaptador local Codex — ejecución manual

```python
from tools.editorial_rag.codex_runner import CodexSessionRunner

# Solo tras revisión humana de sanitización y autorización de transmisión.
report = compare(conversation, cards, current_rules, CodexSessionRunner(timeout=120))
```

No se invoca desde tests, importaciones, runtime ni endpoint público. La UI local
permite invocarlo con el clic informado en **Generar DM**, las confirmaciones de
**Revisión avanzada** o la confirmación del par sintético. No es
producción. Cada variante consume una ejecución independiente; no hay reintentos.
El llamador aporta reglas actuales completas y ambos paquetes sanitizados; el
adaptador no lee el repositorio ni recupera reglas, transcripciones o memoria.
La declaración de sanitización no detecta datos privados ni prompt injection.

Requiere Codex CLI local compatible con los flags indicados y login de **ChatGPT**
realizado manualmente fuera de este módulo. No instala ni inicia login. Comprueba
`codex login status` y exige la respuesta `Logged in using ChatGPT`; versiones que
cambien ese formato fallan cerradas. No lee credenciales desde Python. Se eliminan
claves API y overrides del entorno hijo mediante lista permitida y se fuerza
`forced_login_method="chatgpt"`. No hay fallback a OpenAI API ni facturación API
adicional por este adaptador. El uso consume los límites de Codex de la suscripción
ChatGPT, sujetos al plan, disponibilidad y políticas vigentes. No compra créditos,
no amplía límites ni garantiza uso ilimitado o ausencia de otros cargos del plan.

Cada llamada crea y elimina un directorio temporal vacío fuera del repositorio,
y ejecuta desde allí, sin shell:

```text
codex exec --json --ephemeral --ignore-user-config --sandbox read-only --skip-git-repo-check -c 'forced_login_method="chatgpt"' -C <temporal-vacío> -
```

El prompt viaja por stdin, no por argumentos ni archivos. No hay `resume`, historial
ambiental aportado, logs del adaptador ni persistencia de borradores. Devuelve solo
el último `agent_message` completado después de validar todo el JSONL y el cierre
del turno. Rechaza herramientas (incluso eventos de inicio), errores salvo la
excepción exacta siguiente, eventos desconocidos, JSON inválido, ausencia de salida,
estado no cero y timeout. Los
mensajes de error son fijos, sin stdout/stderr, prompt ni excepciones encadenadas.
El timeout se aplica por separado al chequeo de login y a la generación.

La única excepción son los dos avisos oficiales `SKILL_DESCRIPTION_TRUNCATED_WARNING`
y `SKILL_DESCRIPTION_TRUNCATED_WARNING_WITH_PERCENT` de
[Codex core-skills](https://github.com/openai/codex/blob/914c8eeb/codex-rs/core-skills/src/render.rs):
solo acortan descripciones del catálogo de skills, no instrucciones de la tarea ni
conversaciones. Se exige igualdad textual exacta, sin normalización, en
`item.completed` con un item de exactamente `id` (string no vacío), `type=error`
y `message` (string). El [SDK oficial](https://github.com/openai/codex/blob/35aaa5d9/sdk/typescript/src/items.ts)
describe ErrorItem como no fatal, pero eso no autoriza ignorar otros errores.
Pérdida de eventos, avisos desconocidos, variantes del texto, errores de nivel superior
y eventos posteriores al cierre siguen rechazados. Se conserva la exigencia de
salida final no vacía, turno completo y proceso exitoso, sin reintentos ni borradores
parciales. Los avisos no se exponen ni registran; la redacción fija de errores protege
los datos que pudieran contener otros diagnósticos del proceso. La regresión se
verifica con JSONL y HTTP simulados; no demuestra reparación en vivo.

**Límite de aislamiento:** Codex es un agente de programación. `read-only` no
significa que no pueda leer otros archivos accesibles; un directorio vacío y una
instrucción de no usar herramientas no son una frontera de seguridad del sistema
operativo. Rechazar un evento de herramienta ocurre después de que el proceso pudo
actuar, no revierte lecturas. El entorno conserva rutas de usuario necesarias para
la autenticación; el CLI puede acceder a ellas. `--ignore-user-config` y
`--ephemeral` reducen configuración y persistencia de sesión, pero este adaptador
no demuestra ausencia de telemetría, logs internos, configuración de máquina o
retención del proveedor. No afirmar aislamiento hermético. El modo real requiere
consentimiento informado por transmisión (clic directo o confirmación avanzada) y revisión
del resultado; no elimina estos riesgos.
Si necesitás garantizar que el proceso no lea el host, **no usar este adaptador**:
hace falta un entorno aislado auditado por separado.

Las entradas se transmiten al proveedor con los controles de datos de la cuenta
ChatGPT/Codex. Revisá esos controles y las políticas vigentes antes de autorizar
una ejecución; el adaptador no los configura ni promete retención cero. No guardar
prompts/resultados en logs de la interfaz. Las pruebas de desarrollo usan
exclusivamente casos sintéticos, nunca chats reales. Como antecedente, se verificó la CLI local
con entradas sintéticas: una ejecución del adaptador funcionó y otra rechazó
un evento interno de error aunque Codex terminó el turno. No se probó con
conversaciones privadas ni se demostró confiabilidad de producción.

## CLI de comparación sintética — opt-in

```text
python -B -m tools.editorial_rag.synthetic_compare
python -B -m tools.editorial_rag.synthetic_compare --help
# Solo con autorización explícita para transmitir el caso sintético:
python -B -m tools.editorial_rag.synthetic_compare --run-codex
```

Por defecto muestra PREVIEW con ID del caso, fase y metadatos de ambos paquetes;
no genera borradores ni consulta red o autenticación. No acepta chats, archivos,
rutas de entrada/salida ni fuentes del usuario. No contacta Supabase, importa
originales, sube fichas ni inicia un servidor. La UI local opcional se describe al final.

Usa una conversación ficticia multi-turno con aperturas repetidas y respuestas
breves sobre fuerza, calistenia y dominadas. El destino está suficientemente claro;
falta el obstáculo concreto en brecha. La única ficha contiene criterios de voz,
no una respuesta modelo. Su estado `approved` significa únicamente elegibilidad
de fixture: **no es aprobación de producción ni aprendizaje aprobado por humanos**.

Lee completos y sin alterar su texto UTF-8 los archivos actuales `SKILL.md`,
`references/motor-agentico.md`, `references/voz-escrita-tato.md` y
`references/operativa-dm.md` bajo `.agents/skills/tato-calistenia/`. Resuelve esas
rutas fijas desde el módulo, no desde el directorio de trabajo; une los textos
con dos saltos de línea y aporta exactamente las mismas reglas a ambos paquetes.
No lee archivos de autenticación ni cambia reglas del setter.

`--run-codex` autoriza dos llamadas síncronas mediante `CodexSessionRunner` y una
única ejecución de `compare()`, sin reintentos ni fallback API. Usa exclusivamente
el login ChatGPT del adaptador, con los límites de la suscripción Pro/Codex; no
cambia autenticación ni habilita facturación API. Conserva los límites de
aislamiento y retención del proveedor detallados arriba. El adaptador no fija
modelo ni esfuerzo: ambos se reportan desconocidos, sin afirmar mismo modelo.

Solo después de completar ambas llamadas imprime REAL RUN, bloques current y
editorial de borradores sintéticos y señales mecánicas, nunca un ganador. Ante
fallo devuelve código no cero y diagnóstico genérico, sin primer borrador ni
excepción cruda. Los resultados quedan transitorios; el CLI no los guarda en
archivos, pero **stdout puede ser capturado por la terminal o una redirección**.
Un único probe pareado sintético no prueba calidad de voz, confiabilidad general
ni cumplimiento semántico. Los tests simulan Codex; no ejecutan inferencia real.

### Dos casos de ruta — solo CLI

Los casos fijos `synthetic-ruta-help-to-gap` y `synthetic-ruta-concrete-doubt`
no se agregan a la UI ni al runtime. Ambos incluyen destino explícito de dominadas
con control, brecha, realidad cotidiana con turnos y voluntad de recibir y aplicar
correcciones. El primero permite evaluar una ruta vinculada a esa brecha, sin llamada
ni lista de prestaciones. El segundo agrega una ruta contextual y una duda sobre
cambios de días disponibles; la duda **no confirma aceptación**. Evalúa responderla
antes de avanzar, sin repetir pitch ni calificación conocida y sin inventar tiempos,
frecuencias de servicio o garantías. No contienen un próximo DM modelo.

Solo estos dos casos cargan además los textos completos de
`references/contexto-maestro.md` y `references/objeciones-agenda.md`. Las dos variantes
reciben exactamente el mismo historial y bundle actual; la orientación editorial es
la única diferencia de contenido. Los casos anteriores y `load_rules()` sin argumentos
conservan sus cuatro fuentes. PREVIEW informa las fuentes efectivas y cantidad de
caracteres del bundle completo.

```text
python -B -m tools.editorial_rag.synthetic_compare --case synthetic-ruta-help-to-gap
python -B -m tools.editorial_rag.synthetic_compare --case synthetic-ruta-concrete-doubt
```

Las fichas aisladas `connect_help_to_concrete_gap` y `resolve_concrete_doubt_first`
conservan el contenido editorial candidato aportado para esta prueba. `approved`
solo habilita recuperación en la fixture; **no aprueba las fichas en la base ni
promueve aprendizaje o reglas de producción**. No hay consultas ni escrituras de base.

El refinamiento autorizado se limita a los dos campos de voz de estas fichas candidatas
y sus pruebas locales: palabras cotidianas según el contexto, información distinta en
cada frase y reacción natural, sin perder precisión ni explicaciones necesarias. No
prohíbe `turnos` ni otras palabras pertinentes, no exige puente, nombre o cierre fijo,
ni elimina información útil distinta. Conserva las funciones comerciales y la espera
de aceptación. Sigue inactivo en producción; el dueño general de voz permanece en
`voz-escrita-tato.md`, sin cambios. Una actualización de Supabase se gestiona por separado;
esta edición no confirma que haya ocurrido ni demuestra calidad de modelo aprobada.

Para más adelante, únicamente tras autorización explícita nueva para cada par y con
cuota disponible (estos comandos no se ejecutaron al preparar los casos):

```text
python -B -m tools.editorial_rag.synthetic_compare --case synthetic-ruta-help-to-gap --run-codex
python -B -m tools.editorial_rag.synthetic_compare --case synthetic-ruta-concrete-doubt --run-codex
```

No hay generador de lotes, bucle automático, reintentos ni fallback. Los tests mockean
toda inferencia y comprueban recuperación, fuentes completas idénticas, preview sin
runner y buffering del par sin exposición parcial ante errores. No prueban calidad
semántica o de voz, no puntúan DMs y no permiten declarar un ganador.

## Persistencia Supabase — unidad offline, sin despliegue

`001_editorial_cards.sql` es una migración revisable; este código no la ejecuta.
`supabase_reader.py` es un cliente stdlib opt-in, solo GET. El propietario informa
su aplicación, pero el esquema remoto y RLS siguen sin comprobarse aquí. No hay
conexión automática, JWT disponible, UI persistente, importador, bucket, vector ni integración al setter. El SQL no incorpora todavía el modelo ni las dimensiones de la nueva unidad local;
la migración vectorial 002 descrita arriba es candidata y no fue ejecutada.

### Aplicación exclusivamente humana, una sola vez

1. Confirmar personalmente en el dashboard el proyecto separado. La referencia
   debe coincidir exactamente con `cgoosfuwohjupcbwdaty`; si no coincide, detenerse.
   No aplicar en el CRM ni en otro proyecto. El SQL no verifica la referencia.
2. Revisar el SQL completo y los permisos con quien administra ese proyecto.
   Es una transacción de una sola aplicación, no una actualización de esquema.
   Exige que no existan `public.editorial_cards` ni la función sin argumentos
   `public.editorial_invalidate_approval()`. No reutiliza objetos ni permisos previos.
3. Solo esa persona puede ejecutar la transacción completa en el SQL Editor del
   proyecto confirmado, con autorización separada. Este repositorio no ejecuta SQL,
   MCP ni comandos de despliegue. Una reaplicación falla: las declaraciones `CREATE`
   simples abortan ante objetos existentes, sin reemplazar tablas, funciones o
   triggers; la transacción debe revertirse íntegramente. Si el cliente deja una
   transacción abortada abierta, finalizarla con `ROLLBACK`, nunca continuar por partes.
   Ante una colisión, detenerse y revisar; no borrar objetos para forzar la aplicación.
4. Verificar allí RLS con dos usuarios de prueba: anon sin acceso; cada usuario
   solo puede seleccionar, insertar, modificar y borrar sus propias filas; no
   puede cambiar propietario ni aprobar; un intento sobre otra cuenta no avanza.
   Esa prueba remota NO se ejecutó ni está autorizada por esta unidad offline.
   Tampoco se verificó el comportamiento de la migración en PostgreSQL real.

La tabla almacena únicamente criterio editorial curado. `owner_id` referencia
Supabase Auth, no una identidad de lead. IDs de ficha, procedencia y aprobación
son opacos, nunca rutas, nombres, handles ni citas. `sanitized=true` es una
declaración; SQL no detecta privacidad semántica ni instrucciones encubiertas.
No cargar conversaciones, fuentes históricas, audios, citas ni originales.

Las inserciones autenticadas quedan `candidate`. Los permisos por columna
impiden escribir `status` y `approval_id`; la aprobación exige revisión humana
del contenido exacto y una transacción administrativa separada que asigne
`status=approved` y un ID opaco de aprobación. No usar una service-role key.
Cualquier modificación editorial devuelve la ficha a `candidate` y elimina
su aprobación; debe revisarse nuevamente. Una aprobación no modifica reglas
actuales del runtime. Administradores/BYPASSRLS siguen siendo una frontera de
confianza; los metadatos no prueban por sí solos consentimiento humano.

### Uso futuro del lector, solo con autorización separada

El proceso llamador configura en su entorno temporal `EDITORIAL_SUPABASE_URL`
con el origen HTTPS canónico del proyecto confirmado, sin barra final, ruta,
puerto ni parámetros, y `EDITORIAL_SUPABASE_PUBLISHABLE_KEY` con la clave
**publishable** de ese mismo proyecto. No pegar valores en código, Git, logs,
documentación, argumentos de shell ni archivos `.env` del repositorio.
La publishable key no identifica al usuario ni sustituye RLS; se rechazan
claves secret/service-role y claves JWT legacy en ese campo.

```python
from tools.editorial_rag.supabase_reader import read_approved

# Solo cuando exista una sesión de usuario obtenida fuera de este módulo.
# user_access_token es una variable en memoria, nunca un literal en el código.
cards = read_approved(user_access_token, limit=20)
```

El JWT se pasa explícitamente: no se busca en archivos o variables de entorno.
El preflight comprueba formato, emisor ligado al proyecto, expiración, audience,
rol y UUID de usuario, pero NO verifica criptográficamente la firma. Supabase
verifica firma y autorización mediante TLS; un 401/403 falla cerrado, sin
fallback. Un token bien formado pero falsificado requiere esa verificación del
servidor. Una publishable key opaca no permite inferir localmente su proyecto;
el endpoint está fijado y el servidor debe rechazar una clave ajena.

Lee solo `approved`, con filtro de propietario, campos explícitos y orden por
ID. Máximo 50 fichas, 512 KiB por respuesta, timeout de socket de 10 segundos,
una solicitud sin reintentos ni paginación. No es un deadline global frente a
un servidor que transmita lentamente. Bloquea redirects y proxies ambientales.
Rechaza cualquier fila inesperada, incompleta, duplicada, no aprobada o ajena
antes de devolver la tupla de `Card`. No devuelve resultados parciales ni cuerpos
de error. No escribe, persiste, imprime ni registra credenciales o fichas.
El callback `transport(request, timeout)` permite tests sin red; es código
confiable del llamador, no un sandbox ni validación real de firma.

## Chequeo local manual con Supabase Auth

La cuenta propietaria de **Supabase Dashboard no es automáticamente un usuario
de `auth.users`**. No uses la contraseña del Dashboard para este chequeo.

1. En el Dashboard del proyecto `cgoosfuwohjupcbwdaty`, abrí Authentication →
   Users → Add user / Create new user y creá un usuario Auth dedicado con un
   correo bajo tu control y una contraseña propia. Las opciones pueden variar.
   Este CLI no crea usuarios ni envía invitaciones.
2. Verificá el correo y el estado de confirmación en Authentication. Si corresponde
   un correo de confirmación o invitación, completá el enlace y configurá la
   contraseña. Un proyecto gratuito puede exigir confirmación de email antes del
   login. Resolvelo personalmente en Dashboard sin desactivar RLS ni compartir
   contraseñas o enlaces de confirmación.
3. Configurá localmente y solo para el proceso `EDITORIAL_SUPABASE_URL` y
   `EDITORIAL_SUPABASE_PUBLISHABLE_KEY` como se describe arriba. No uses service-role,
   claves secret ni JWT legacy. No se cargan archivos `.env`.
4. Desde la raíz, ejecutá manualmente en una terminal local confiable:

   ```text
   python -B -m tools.editorial_rag.check_connection
   ```

   Ingresá el email Auth localmente y la contraseña únicamente en el prompt oculto
   de `getpass`, nunca por argumentos, entorno, archivos o logs. Si no se puede
   ocultar la contraseña, falla antes de usar entrada visible. No uses grabación
   de terminal, depuración con variables locales ni wrappers que registren tráfico.
   Nunca pegues email, contraseña o JWT en el chat; comunicá solo éxito/fallo y conteo.

`supabase_auth.py` hace un único POST al endpoint oficial
`/auth/v1/token?grant_type=password` con email y contraseña en JSON sobre TLS.
Devuelve solo el access JWT en memoria y descarta refresh token y datos de usuario.
Valida claims como preflight, **no la firma**: el posterior GET de `read_approved`
requiere que Supabase verifique firma y autorización. Ambos pasos usan origen
exacto, sin redirects, proxies ambientales ni reintentos. Auth limita el JSON a
64 KiB y timeout de socket a 10 segundos; el lector conserva 512 KiB y 50 fichas.
No es un deadline global frente a un servidor lento.

La salida contiene solo éxito genérico y fichas aprobadas **devueltas, máximo 50**,
no el total de la tabla. Cero es válido. El fallo es genérico, sin excepciones,
cuerpos del servidor ni secretos. No imprime fichas, genera DMs ni escribe en
`editorial_cards`. El login sí puede crear sesión y auditoría en Supabase Auth;
no se refresca ni revoca automáticamente. No se persiste nada localmente, pero
Python no garantiza borrado seguro de secretos de la memoria del proceso.

**Esquema, triggers y aislamiento RLS entre usuarios siguen sin verificarse**.
Un GET exitoso o vacío no demuestra integralmente esas propiedades ni permisos de
aprobación. No se ejecutó este chequeo contra el proyecto vivo durante el desarrollo;
todos los tests de Auth y conexión usan HTTP simulado.

## Chequeo opcional en navegador local — una sola vez

Desde la raíz, en una terminal local confiable:

```text
python -B -m tools.editorial_rag.browser_login
```

1. Usá el usuario **Auth dedicado** creado y confirmado según los pasos anteriores,
   nunca la cuenta ni contraseña del Dashboard. No hay registro desde esta pantalla.
2. Si falta `EDITORIAL_SUPABASE_PUBLISHABLE_KEY`, ingresá la clave publishable en
   el prompt oculto local. Sin terminal que permita ocultarla, se cancela sin eco.
   Nunca pases claves por argumentos, archivos, logs o chat. No se leen `.env`.
   El origen está fijado a `https://cgoosfuwohjupcbwdaty.supabase.co`; una variable
   `EDITORIAL_SUPABASE_URL` diferente se rechaza, no se redirige.
3. Se abre el navegador en `http://127.0.0.1:<puerto-efímero>/`. Ingresá allí email
   y contraseña Auth. Solo se muestra éxito y cantidad devuelta (0 es válido,
   máximo 50), o fallo genérico. Tras un fallo, volvé a la página raíz para reintentar.
4. El servidor cierra tras éxito, tres intentos válidos fallidos o 180 segundos;
   podés cancelar con Ctrl+C. Cerrá la pestaña después. No es una app persistente.
   El proceso devuelve código 0 solo después de enviar una respuesta exitosa de Auth
   y lectura. Timeout, cancelación, error o tres intentos rechazados terminan con
   código no cero y un mensaje genérico; cerrar la pestaña sin completar el chequeo
   termina por timeout, no cuenta como éxito.

La escucha es exclusivamente IPv4 loopback, nunca LAN. Rechaza Host ajeno,
Origin ausente/ajeno en POST, CSRF inválido, otras rutas/métodos, tipos de contenido
no permitidos y cuerpos mayores a 16 KiB. GET admite navegación inicial sin Origin;
si lo recibe, exige el origen exacto. No usa JavaScript, recursos externos, cookies,
redirects, logs ni almacenamiento del navegador. Las respuestas usan no-store,
CSP restrictiva, protección contra frames, no-referrer y nosniff. El formulario no
reproduce credenciales. Reutiliza Auth y lectura aprobada sin cambios; no invoca
Codex, genera DMs, importa originales ni escribe fichas en la base.

**Límites:** localhost usa HTTP, no TLS, y no protege contra procesos locales
maliciosos, otras cuentas con acceso al host, inspección del sistema, extensiones
ni un navegador comprometido. Usá un perfil confiable sin extensiones y desactivá
el guardado/autocompletado de contraseñas; `autocomplete=off` no obliga a gestores
ni extensiones. No captures tráfico ni uses depuradores que guarden variables.
No se garantiza borrado seguro de memoria, historial de formularios, swap o dumps.
El JWT queda solo en memoria del proceso, sin refresh ni persistencia. Supabase
puede registrar sesión/auditoría Auth; no se revoca automáticamente al cerrar.
El límite temporal cierra el listener incluso con un cliente lento; un trabajo de
red en hilo daemon puede seguir hasta salir del proceso si el proveedor se demora.

Este chequeo verifica únicamente login y lectura, **no el esquema ni RLS completo**.
Durante desarrollo solo se probó HTTP loopback con credenciales sintéticas y
Auth/lector simulados; no se contactó Supabase ni Codex.

## Verificación

Desde la raíz:

```text
python -B -m unittest discover -s tools/editorial_rag -p "test_*.py" -v
```

Las pruebas del comparador cubren respuesta corta con validación repetida, exclusión por estado,
puerta y fase, ausencia de coincidencia, desempate estable, aislamiento entre casos,
rechazo de campos de citas/rutas de procedencia y de entradas sin declaración,
paquetes sin ficha y señales contra el asistente inmediatamente anterior.
La comparación sintética se ejecuta con apertura de archivos y sockets bloqueada;
esto verifica el prototipo, no constituye sandbox del runner externo.

## Primera pantalla local — React + FastAPI

La sección **Comparador sintético** usa el caso ficticio fijo, sin chats reales ni uploads.
El modo real separado se describe al principio. **Ver demo
simulada** muestra borradores manuales, no inferencia ni evidencia de mejora. **Generar
con Codex Pro** abre una confirmación nueva para cada par; no verifica cuenta ni plan.
Abrir la app, consultar contexto, ver demo y limpiar resultados no invoca Codex.

### Preparar y abrir en Windows / Git Bash

Desde la raíz, con Python 3.14 y Node 22.21.1:

```bash
python -m venv tools/editorial_rag/.venv
tools/editorial_rag/.venv/Scripts/python.exe -m pip install --no-cache-dir -r tools/editorial_rag/requirements.lock.txt
(cd tools/editorial_rag/web && npm ci)
(cd tools/editorial_rag/web && npm run build)
tools/editorial_rag/.venv/Scripts/python.exe -B -m tools.editorial_rag.local_web
```

Abrí **http://127.0.0.1:8765/**. No usar `localhost`, otro puerto, un proxy ni el
servidor de desarrollo de Vite. Sin build, la raíz devuelve 503. Ctrl+C detiene la
app; no hay cambio de host por CLI. El acceso y los errores de Uvicorn no se registran.
El lock Python proviene de `pip freeze` del entorno aislado; el lock npm fija el árbol.
Las cachés npm quedan dentro de `web/node_modules`; `.venv`, dependencias y `dist`
están ignorados. No hay instalación global ni carga de `.env`.

### Qué autoriza la confirmación

- Dos llamadas independientes al runner existente, sin reintentos ni fallback API.
  Transmite a OpenAI el caso sintético, las cuatro reglas actuales completas y el
  criterio editorial; consume los límites de la suscripción ChatGPT/Codex.
- Modelo y esfuerzo permanecen desconocidos, no fijados. No se modifica login.
  Los errores del CLI se rechazan salvo los dos avisos exactos de descripciones
  documentados arriba. Los timeouts originales se conservan.
- Las dos salidas se retienen en memoria hasta completar el par; un fallo devuelve
  solo un error fijo, nunca un borrador parcial. Un pedido simultáneo recibe 409,
  incluso desde otra pestaña. Cerrar la pestaña no cancela una llamada ya autorizada.
- No hay envío a Instagram/ManyChat, Supabase, historial, feedback persistente ni
  cambio del runtime. Las señales son conteos/banderas mecánicas, no puntajes de calidad.

### Frontera local y límites

FastAPI sirve únicamente el índice compilado y assets JS/CSS de `dist`, sin fuentes,
mapas, documentación API ni exposición del repositorio. Todas las rutas validan Host
exacto; POST exige Origin exacto, token CSRF aleatorio por proceso, JSON acotado y
esquema cerrado. La generación exige `consent=true` booleano. No hay CORS permisivo,
cookies, localStorage, fuentes remotas ni telemetría de la app. Las respuestas usan
no-store, CSP de mismo origen, no-referrer, nosniff y bloqueo de frames.

**Localhost no es un sandbox del host.** Procesos locales o extensiones maliciosas,
inspección del navegador, swap y dumps siguen fuera de esta frontera. No se garantiza
borrado seguro de memoria ni se controla retención, telemetría o logs del proveedor
ni del CLI. Usá un navegador confiable. El comparador admite solo el caso sintético;
el modo real exige autorización de cada transmisión según lo explicado al principio.

### Verificar sin proveedor

```bash
(cd tools/editorial_rag/web && npm test -- --run)
(cd tools/editorial_rag/web && npm run build)
tools/editorial_rag/.venv/Scripts/python.exe -B -m unittest tools.editorial_rag.test_local_web -v
tools/editorial_rag/.venv/Scripts/python.exe -B -m unittest discover -s tools/editorial_rag -p 'test_*.py' -v
```

Los tests simulan Codex y fetch. El test de assets comprueba el build vía TestClient,
sin iniciar un listener; se omite si no se compiló. No constituyen una revisión visual
en navegador ni una prueba de calidad de voz o de disponibilidad del proveedor.
