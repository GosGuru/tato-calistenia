# Espacio editorial local — implementación de UI

## Candidato actual — controles conversacionales y sesión cifrada

Este candidato cambia presentación y persistencia Auth, no motor, reglas, prompts, RAG, embeddings,
CRM ni oferta. Las mediciones, capturas, PASS y hash de 58 archivos que aparecen **más abajo son
históricos** y no verifican este candidato.

- RAW conserva una columna y el nodo del textarea al generar o abrir Biblioteca, pero mueve el historial
  enviado a una burbuja superior con animación breve; el input queda vacío y **Editar historial** lo restaura.
  No se crea un historial persistente ni turnos ficticios. Enter ejecuta la
  misma acción guardada que **Generar con Codex**; Shift+Enter agrega línea. Composición/IME,
  keyCode 229 y repetición no generan. Pegado, edición, montado y navegación tampoco.
- El loader compacto representa solo una petición pendiente: marca editorial T, pulso CSS y texto contextual,
  sin etapas, reloj ni streaming. El mensaje completo entra con una animación finita de 180 ms.
  Movimiento reducido desactiva todas las animaciones. Respuesta redondeada, altura según contenido y scroll acotado.
- Copiar usa el texto original; éxito e icono Check solo después de resolver la promesa vigente.
  Una copia anterior no reemplaza un fallo más nuevo. Una aclaración no ofrece Copiar.
- Sistema sans explícito en controles y Markdown, sidebar flotante redondeada, cabecera agrupada e
  iconos accesibles. Sin fuentes externas ni cambios de CSP/dependencias.
- Privacidad ampliada y criterios pasan a Biblioteca. Queda una autorización concisa junto a Generar,
  límites/errores visibles y confirmaciones avanzadas/comparador intactas. El detalle de costos informa
  que la llamada consume límites de Codex; nada se envía a Instagram.
- Biblioteca muestra cantidad realmente observada (disponible, no aplicada), desconocido sin señal
  verde y sesión conectada sin formulario de ingreso vacío. Una instancia Auth permanece montada
  al cambiar de modo; sus campos se limpian al intentar/cerrar. Cambiar de modo sigue descartando
  el historial RAW; abrir Biblioteca conserva su nodo. La reconexión nunca reproduce un POST.

### Sesión recordada y activación por etapas

`production_auth()` es la única composición que habilita el store al iniciar el launcher Windows.
Importar módulos o llamar `create_app()` sin inyección no descubre ni lee almacenamiento/configuración.
`%LOCALAPPDATA%/TatoEditorialRag/session.dpapi` contiene solamente la credencial de renovación con
versión, proyecto y dueño, cifrada por DPAPI del usuario actual (no máquina). Sin contraseña, email,
access JWT, historial o borrador persistidos, ni almacenamiento del navegador. No hay fallback en texto
plano o para otro sistema. Máximo 32 KiB cifrados y 4096 caracteres ASCII visibles de refresh token.

Restauración: un intento al arranque; renovación: un intento al tomar snapshot para una generación
explícita después de expirar. Ambas requieren dueño exacto y GET autenticado/RLS antes de aceptar o
rotar. No hay timers, bucles de reintentos ni modelos automáticos. La actualización cifrada es atómica.
Logout y revisiones impiden que una respuesta en vuelo reponga una sesión desconectada. Si guardar o
quitar falla, la API informa problema, nunca confirma recordada; el borrador baseline sigue disponible.
No se promete ingreso permanente, revocación remota ni borrado seguro.

Bootstrap conserva cinco claves y Auth status cuatro. `GET /api/auth/persistence` agrega únicamente
`enabled`, `remembered`, `problem`. Un archivo existente no equivale a sesión validada. El frontend
acepta un backend viejo que responde 404 y muestra **Persistencia no activada**, sin romper RAW.
**No se reinició ni activó el backend real.** Para activarlo hace falta coordinar un reinicio posterior,
fuera de esta tarea y después de terminar cualquier generación en curso.

### Corrección P2 actual — transporte de metadata

`loadPersistence` llama `onDisconnect` solo ante transporte fallido dentro de la guarda `current()`
existente. Invalida nonce/disponibilidad de generación y conserva el historial RAW; metadata queda
desconocida. 404, otros HTTP y JSON/formato inválido siguen siendo inocuos. Respuestas de epochs de
conexión/Auth anteriores o tras desmontaje no desconectan la sesión nueva. Sin cambios de layout,
fuentes, backend, instancia Auth, guardas ni política de POST/reintentos.

- RED focalizado: **1 fallo esperado / 6 pasan / 61 omitidos por filtro**; Generar seguía habilitado
  tras rechazar solo persistencia con TypeError, con status 200.
- Primera corrida conjunta: **78 pasan / 3 fallan**. Dos fixtures antiguos aplicaban el error RAW
  también al GET opcional; se agregó 404 explícito en ese endpoint, sin quitar aserciones ni modificar
  conteos de POST. Resueltos los fallos TypeError, AbortError e invalidación de biblioteca.
- `(cd tools/editorial_rag/web && npm test -- --run src/AppAuth.test.jsx src/App.test.jsx)`: **85/85**.
- `(cd tools/editorial_rag/web && npm test -- --run)`: **191/191**, siete archivos, exit 0.
- `(cd tools/editorial_rag/web && npm run typecheck)`: exit 0; no amplía cobertura del JSX heredado.
- `(cd tools/editorial_rag/web && npm run build)`: exit 0, 2330 módulos. Nuevos assets
  `index-HchAyKAx.js`, `index-D1fNOLx3.css`, `highlighted-body-KPVGNVTW-DQ1Q5O5I.js`;
  anteriores retenidos. Persisten avisos use-client/sourcemap/chunk grande.
- Once casos nuevos cubren callback vigente/obsoleto/desmontado, pérdida solo de metadata, historial
  conservado, bloqueo sin POST, reconexión explícita con nonce fresco, HTTP/JSON y epochs.

Evidencia independiente aportada por el padre, **anterior a esta corrección**: frontend 180/180;
backend cercado 71/71, cero errores/omisiones/red denegada/FS protegido/fuera de temporal/procesos.
No se reejecutó Python ni se modificó backend. RAW `%TEMP%/tato-raw-fixture-E5mxZO/report.json`
pasó con 13 POST ficticios (11 RAW + 2 Auth), una intercepción previa al envío y cero modelos reales
/producción. FullUI `%TEMP%/tato-ui-fixture-kGDLk8/report.json` pasó 22 checks, tres POST ficticios,
cero externos/modelos. Ambos tienen capturas nuevas de carga; el padre inspeccionó RAW desktop
carga/largo y móvil vacío. Evidencia visual/funcional previa, **no prueba de esta regresión**.
FullUI conserva `profileRetained: true`; no se afirma eliminación del perfil. Sin rerun de navegador.
Aprobación visual humana pendiente, backend persistente no activado, #59 sin uso y probe de socket
sin resolver. El incidente externo HTTP 400 del primer RED Auth sigue divulgado abajo, con cantidad
exacta de intentos desconocida; el aislamiento posterior no lo borra. Sin afirmación de calidad semántica.

### Verificación previa a la corrección P2

RED de comportamiento observado: teclado (2 fallos), loader (1), estado Biblioteca/404 (3), copia
concurrente (1), store (1), intercambio refresh (1), Auth recordada (2), endpoint opcional (1).
#### Incidente de aislamiento del primer RED Auth

El test `RememberedAuthTests.test_saving_failure_preserves_baseline_and_never_claims_remembered`
invocó `AppAuth.login` cuando todavía usaba `load_config()` → `sign_in()` → `_sign_in()` → transporte
del reader. Se había mockeado la futura función `sign_in_session`, pero faltaban los mocks del camino
heredado `app_auth.load_config` y `app_auth.sign_in`. Ese camino leyó la configuración real predeterminada
e intentó autenticación externa por contraseña. La evidencia registrada es un aviso `HTTPError 400`;
no hubo contador de requests, por lo que el número exacto de intentos externos es **desconocido**.
Email/contraseña eran literales ficticios creados para el test, no credenciales aportadas por el usuario.
No se observó autenticación exitosa. Esa corrida **no fue aislada** y no debe presentarse como tal.

Antes de continuar se agregaron mocks explícitos de ambos símbolos y denegación de `socket.socket`
en `RememberedAuthTests.setUp`; los tests mockean además intercambios de sesión y lectura de biblioteca.
La corrección posterior de fixtures frontend inspeccionó este incidente sin repetir la petición ni abrir
configuración o almacenamiento reales. No se tocó el proceso de la app.

#### Cierre acotado de fixtures frontend

La suite previa tuvo **175 aprobados / 5 fallos**: mocks posicionales de `AppAuth.test.jsx` consumían
incorrectamente el nuevo GET opcional. Con autorización explícita de ese archivo, se reemplazaron por
planes cerrados por ruta/método, incluyendo metadata 404 y cantidad exacta de lecturas. Se verifican
payload, nonce, no-store, ausencia de requests imprevistos y consumo completo de planes. Las aserciones
sobre barrera pendiente, finalización única tras desmontaje, error de transporte y login tardío se mantienen.
Las verificaciones de requests se ejecutan fuera del mock para que el sanitizador no pueda ocultarlas.

- `(cd tools/editorial_rag/web && npm test -- --run src/AppAuth.test.jsx)`: **13/13**, exit 0.
- `(cd tools/editorial_rag/web && npm test -- --run)`: **180/180**, siete archivos, exit 0.
- No quedan fallos en esas suites. Solo se corrigieron tests y documentación; producto y arneses intactos.
- Python **71/71**, typecheck, build, sintaxis y runtime corresponden a la verificación anterior;
  **no se reejecutaron** en esta corrección. No hubo navegador, modelos, activación ni reinicio.
- Assets conservados sin rebuild: `index-COK9C9Bf.js`, `index-D6_tyvuv.css` y
  `highlighted-body-KPVGNVTW-DgXWFciC.js`. La verificación visual independiente sigue pendiente.

El arnés RAW prepara 12 capturas (vacío, loader, largo, error por viewport), Enter y Shift+Enter,
GET opcional 404, login/logout ficticios con planes cerrados, payload y nonce exactos. Conserva
conteo de todo intento y transporte default previo al envío. `--diagnose-transport` no se ejecutó
ni cambió su significado. Los dos arneses esperan solo animaciones finitas y mantienen foco,
CSP, storage/cookies, externos y hit testing. Rótulos de fixture en cabecera, no sobre controles.
**El writer verifica únicamente sintaxis; navegador, geometría y aprobación visual pendientes.**
No se usó #59 ni se afirma mejora semántica de DMs. Las siete reglas y los cuatro módulos protegidos
se comparan por hashes nuevos de esta unidad; los archivos Auth autorizados no pertenecen a esa base.

## Archivo histórico — diseño anterior, no evidencia de este candidato

La dirección aprobada reemplaza los paneles 45/55, no el motor ni los flujos opcionales.
Responder abre con un título de 24 px, aire y un composer AI Elements centrado de hasta 780 px,
radio 26 px. El refinamiento compacto usa textarea de dos filas (88 px desktop) y acciones dentro
de la superficie; elimina la etiqueta visible duplicada y conserva su nombre accesible. Aviso informado,
retiro de datos sensibles y contador quedan inmediatamente debajo, fuera del borde redondeado.
Medición independiente: superficie redondeada de 780×142 px desktop y 358×150 px móvil;
textarea de 88/96 px. El disclosure empieza 14 px debajo de la superficie y 29 px debajo de Generar.
No monta un panel de borrador vacío. Tras la acción explícita, muestra un único
resultado encima del mismo textarea controlado: **Historial preparado**, no un mensaje enviado
ni un historial de turnos inventado. El borrador comienza arriba, con scroll acotado y copia manual.
El texto completo se conserva tras éxito/error; editar invalida el resultado como antes.

Canvas #121212, sidebar #191919 de 240 px y composer #222; tipografía del sistema y navegación
sobria. La misma paleta, espaciado y superficies sin tarjetas anidadas pesadas cubren revisión,
comparador y Biblioteca. Sus controles, confirmaciones, roles y contabilidad no cambian.
El botón circular conserva el nombre accesible **Generar borrador**. Enter sigue agregando líneas.
Transmisión, consumo, retiro de datos sensibles y **No se envía a Instagram** quedan visibles;
privacidad ampliada, criterios y técnica continúan en disclosures. No hay nuevas capacidades,
instalaciones, fuentes externas, persistencia ni cambios de CSP.

### Refinamiento compacto y sincronización del arnés — candidato actual

- `npm test -- --run src/RawDM.test.jsx`: RED **1 fallo esperado / 48 pasan** por metadata dentro
  de la superficie; GREEN **49/49**. Se mantienen las aserciones previas de privacidad y nodo/texto.
- `npm test -- --run`: **170/170**. `npm run typecheck`: exit 0, sin nueva cobertura de JSX heredado.
- `npm run build`: exit 0, 2330 módulos. Assets: `index-gGrxjJHi.js` (872,17 kB),
  `index-DMxX8UdQ.css` (69,21 kB), `highlighted-body-KPVGNVTW-D5yRjRZX.js` (0,46 kB).
  Assets anteriores conservados; mismos avisos use-client/sourcemap/chunk grande.
- `node --check scripts/raw-ui-browser-check.mjs && node --check scripts/ui-browser-check.mjs`:
  exit 0. No Chrome ni backend reejecutados en este refinamiento.
- RAW añade límites de altura real y cercanía/visibilidad del disclosure junto a las acciones,
  también en el detalle móvil. Conserva cuentas de peticiones, estado y seguridad.
- El arnés general registra el nodo iniciador de Generar como referencia observacional y devuelve
  solo un booleano serializable. Distingue Escape, desaparición, espera acotada del foco exacto y
  visibilidad/hit test. No fuerza foco ni modifica RealDM/Radix. Diagnóstico de fallo: booleanos,
  tag/rol de conjunto cerrado y PNG de viewport acotado, sin volcado DOM/texto/credenciales.

Verificación independiente final aportada por el padre: **170 frontend (49 RAW), typecheck,
build y sintaxis pasan**. El código de la app no cambió desde el refinamiento compacto; las rondas
posteriores modificaron solo el arnés. Los **40 HTTP y runtime válidos** son evidencia independiente
anterior, no reejecutada en la última ronda del arnés ni en este cierre documental.

Historial conservado: RAW `5JszTT` validó el candidato anterior. FullUI `veAjsx` se detuvo en
«advanced Escape» y `RDwPwZ` en «advanced outside-click dismissal»; comparador/móvil posteriores
no fueron alcanzados en esas corridas. Se corrigieron límites de espera y selección del punto en el
arnés, sin cambios de Escape/backdrop en el producto. El PASS actual no demuestra cuál fue la
instrucción fallida ni la causa exacta de aquellos fallos. Evidencia final de navegador más abajo.

### Evidencia de la implementación anterior a este refinamiento

- Baseline `npm test -- --run`: **166/166**.
- RED `npm test -- --run src/RawDM.test.jsx`: **4 fallos esperados / 44 pasan**, por inicio y orden
  conversacional ausentes. La iteración siguiente pasó 47/48; se restauró el aviso visible de retiro
  de datos sensibles, sin debilitar esa aserción.
- GREEN `npm test -- --run`: **169/169**, siete archivos. Los casos nuevos cubren DM, aclaración y
  error antes del mismo textarea, preservación literal Unicode/duplicados y descarte al editar.
  Siguen pasando single-flight, consentimiento, epochs/nonce, Auth pendiente y settlement,
  respuestas/errores/copias obsoletos, Markdown seguro, parser y par sintético completo.
- `npm run typecheck`: exit 0; no migra ni declara cubierto el JSX heredado.
- `npm run build`: exit 0, 2330 módulos, `emptyOutDir=false` intacto y assets anteriores retenidos.
  Assets nuevos: `index-B94g8e6m.js` (872,22 kB), `index-POxmwDHs.css` (69,41 kB),
  `highlighted-body-KPVGNVTW-BqdLmjUG.js` (0,46 kB). Persisten avisos use-client/sourcemap/chunk grande.
- `node --check scripts/raw-ui-browser-check.mjs && node --check scripts/ui-browser-check.mjs`: exit 0,
  **solo sintaxis**. Chrome no fue ejecutado por el writer.
- `tools/editorial_rag/.venv/Scripts/python.exe -B -m unittest tools.editorial_rag.test_local_web`:
  **40/40**; socket y Server.run mockeados, mensajes de arranque solo de tests. Aviso Starlette/httpx.
- `tools/editorial_rag/.venv/Scripts/python.exe -B .agents/skills/tato-calistenia/scripts/validate_runtime.py`:
  runtime válido, validación estática, no evaluación semántica.

### Integridad de esta unidad

Snapshot del writer agregado SHA-256 antes/después de su trabajo: **58 archivos, igualdad exacta**,
`47163ed2353ea216edc738cf390e6ecb57fc684530ff08b02b820869315eddef`.
Incluye Python/SQL del directorio backend, launcher, manifest/lock frontend, configuraciones Vite/TS,
.npmrc/index fuente, manychatHistory.js y las siete reglas. Se ordenan rutas y se agrega cada ruta,
NUL y digest SHA-256 de sus bytes. No se volcaron contenidos privados. Esta base prueba únicamente
la conservación durante esa unidad, no la integridad retroactiva del árbol previamente modificado.
El verificador no estableció independientemente esa base ni ese hash; no se recalcularon en este cierre.

### Verificación funcional independiente — PASS; aprobación visual pendiente

**RAW:** `%TEMP%/tato-raw-fixture-fC7Pa7/report.json` y `gallery.html`, **129 checkpoints**.
Se inspeccionaron las nueve capturas canónicas y tres detalles inferiores. Desktop: viewports
1366×768 y 1920×1080. Móvil: viewport 390×844; páginas completas 390×844 vacío,
390×1027 largo y 390×844 error; detalles 390×844. Las medidas compactas indicadas arriba son
observadas, no estimadas. Pasaron disclosure adyacente visible, copia, historial completo, nueva línea,
needs_context, identidad del textarea con Biblioteca/Auth y reconexión.
**10 POST HTTP planificados con payload exacto + una intercepción validada de transporte**.
Transporte: un fetch, una intercepción previa al envío, cero entregas y sin replay.
CSP/storage/cookies/style tags/externos/runtime/modelos: cero. Contraste no medido.

**FullUI:** `%TEMP%/tato-ui-fixture-cMlFRk/report.json`, **22 checkpoints, diez PNG sin galería HTML**.
Todas inspeccionadas, únicamente viewport: siete desktop 1440×1000 (vacío, sidebar colapsado,
Biblioteca, resultado, avanzada, consentimiento, comparador) y tres móvil 390×844 (navegación,
Biblioteca, composer). Pasaron Escape del editor, Escape y un único clic de backdrop avanzado,
foco de retorno por identidad exacta y ausencia de POST; contención de foco y bloqueo de scroll
modal/Sheet; demo del comparador y consentimiento de dos llamadas inicialmente deshabilitado,
cancelado con Escape sin generación; Sheet móvil por Escape/backdrop y foco exacto; limpieza de
credenciales de Biblioteca, conservación del pegado y foco tras cierre/Escape; Markdown seguro,
reconexión y recarga. **Tres POST fixture: dos RAW y una demo; cero POST Auth/generate**.
Modelos reales, externos y runtime: cero; checkpoints CSP/storage/cookies/style tags/overflow
horizontal: cero. El rótulo inferior del fixture tapa parcialmente un control inferior del Sheet móvil
en el PNG: no demuestra que todos los controles estén libres de obstrucción ni certifica accesibilidad.

La sincronización del arnés espera modal visible/estable y foco inicial, un macrotask y dos frames;
selecciona un punto interior del overlay fuera del diálogo, verifica hit test y hace un solo clic.
Luego espera desaparición y foco exacto del iniciador, sin forzar foco ni alterar producto.
Estos resultados son evidencia independiente aportada; este cierre no ejecuta comandos ni navegador.

`--diagnose-transport` conserva el probe separado `adDAry`: **un fetch / dos entregas** al destruir
el socket, todavía sin resolver y no reejecutado. No hubo corrección de backend/idempotencia.
El PASS del transporte frontend aislado no resuelve esa limitación HTTP.

**#63 abierto: aprobación visual humana de Maxi PENDIENTE. #59 no usado.** La selección de toda
la UI con el mismo motor no aprueba resultados visuales ni eficacia de DMs, cuya evaluación se difirió.
Sin Next, chats persistidos, voz/archivos, menús ficticios ni cambios normativos. Los fixtures no prueban
Auth, DB o modelos reales ni mejora de respuestas de leads.

Contexto operativo aportado por el padre, separado de los fixtures: relanzó una vez el servidor real
tras un rechazo de conexión fresco. Pencil integrado cargó y permitió DOM, pero la captura agotó
su espera. No demuestra uptime permanente, causa de terminación ni plugin Chrome verificado.
No se inventa un resultado de readiness actual. Este cierre no toca producción ni procesos.

## Archivo histórico — evidencia anterior, NO valida este diseño

Todas las secciones siguientes describen unidades anteriores y sus respectivos builds. En particular,
las capturas y el PASS de `4hUcyV` corresponden a la composición 45/55 reemplazada, no a esta interfaz.

## Verificación funcional independiente histórica — default PASS

Evidencia aportada por el verificador: `(cd tools/editorial_rag/web && node scripts/raw-ui-browser-check.mjs)`
ejecutado una vez, **exit 0, 9,729 s, 129 checkpoints**. Artefactos:
`%TEMP%/tato-raw-fixture-4hUcyV/report.json` y `gallery.html` en el mismo directorio.

- **9 capturas canónicas**: vacío/largo/error para 1366×768, 1920×1080 y 390×844; más **3 detalles móviles**.
  Las 12 fueron inspeccionadas independientemente y los píxeles del footer son consistentes.
- PNG móviles completos: 390×1385, 390×1626 y 390×1518; viewport 390×844; detalles 390×844.
- Sidebar 216 px, padding 24/28 px, proporción 45/55, scroll global desktop 0; inicio/final internos
  y footers verificados.
- Pasaron Enter sin POST, historial completo, pending, Markdown hostil, copia original/fallo,
  needs_context, disclosures, identidad del textarea con Biblioteca/sidebar, malformación,
  error HTTP/transporte y reconexión.
- Transporte default: **1 fetch / 1 intercepción CDP validada antes del envío / 0 entregas al servidor**.
  UI desconectada, generación deshabilitada, historial conservado y sin Copy; GET de reconexión con
  nonce fresco sin replay.
- Totales: **10 intentos HTTP POST ficticios + 1 intercepción de transporte**; inesperados 0,
  externos/modelos 0, errores runtime/CSP/storage/cookies/style 0.

El contraste **no fue medido**. No es una certificación general de accesibilidad ni prueba de producción.
Las capturas son demostraciones ficticias aisladas, no datos o resultados simulados dentro de producción.

## Aprobación visual humana — pendiente

**#63 sigue ABIERTO y NO aprobado**: falta aprobación visual de Maxi. Verificación funcional e inspección
independiente de capturas no la reemplazan. #59 no usado; sin Auth, DB o Codex reales ni acceso/gestión
de producción 8765. Este cierre solo cambia documentación, sin ejecutar comandos.

## Limitación separada de transporte e historial

La corrida previa `tato-raw-fixture-lvEfso` produjo 9 capturas canónicas y 3 detalles móviles inspeccionados:
geometría correcta y footer visible. El arnés terminó fallando por una entrega POST no planificada;
**no fue una corrida completamente verde**. Contar únicamente POST planificados no probaba ausencia de replay.

El probe separado `tato-raw-fixture-adDAry/004-diagnose-transport-observed.json` observó
**un fetch del cliente y dos entregas al servidor** al destruir el socket POST. La segunda recibió 409,
por lo que la UI quedó conectada con alerta HTTP; ese caso no aislaba su rama de fallo de transporte.
El mecanismo exacto sigue sin demostrarse. Cero llamadas a modelos; no se cambió backend ni idempotencia.
Investigar entregas HTTP reales queda fuera de este alcance UI. `--diagnose-transport` conserva la
destrucción de socket, conteo de todas las entregas y rechazo estricto de intentos extra; no se declara verde.

Para el modo default únicamente, el plan de transporte se valida en `Fetch.requestPaused` antes de
reenviar: método/ruta exactos, body íntegro/consentimiento y token/origen del fixture. Conserva su gate
para verificar loading real; después de release usa `Fetch.failRequest`, cuya falla nativa llega a la UI.
Exige **un fetch, una intercepción explícita y cero entregas al servidor** para ese caso, desconexión visible,
historial conservado, ausencia de copia y reconexión GET con nonce nuevo sin repetir POST.
Éxito, HTTP error y malformación siguen usando el servidor HTTP. Intentos inesperados siguen siendo errores,
no una allowlist. Reporta `posts`, `interceptions`, fases y deltas cliente/servidor/intercepción por separado.
Esto prueba una rama frontend, **no garantiza que HTTP nunca pueda entregar una solicitud otra vez**.

El default pasó en `4hUcyV`, según la evidencia anterior; **ese PASS no resuelve el probe adDAry** ni
reclasifica corridas fallidas históricas como verdes. La limitación no fue permitida por allowlist ni
reparada. Backend/idempotencia siguen intactos; una investigación futura requiere otro alcance.

## Evidencia histórica — estado veraz y preparación inicial del arnés RAW

Las afirmaciones de navegador pendiente en esta sección describen aquella unidad, no el estado actual.

Único cambio de producto en esta unidad: `needs_context` anuncia **Falta contexto. No se generó un DM.**,
no «Borrador disponible». `dm` conserva su éxito real. No se tocaron peticiones, validación, guardas ni epochs.
RED observado: **1 fallo esperado / 165 pasan**; GREEN: **166/166**, 7 archivos. Typecheck y build pasan
(2330 módulos; mismas advertencias use-client, sourcemap de diagnóstico y chunk grande).

Nuevo `scripts/raw-ui-browser-check.mjs`: **Chrome NO EJECUTADO todavía para esta matriz**.
Preparado exclusivamente para revisión y ejecución del verificador independiente:

```bash
(cd tools/editorial_rag/web && node scripts/raw-ui-browser-check.mjs)
```

Timeout externo del verificador: **210 s**. Trabajo acotado a 140 s, espera CDP hasta 7 s,
polling hasta 6,5 s, cierre CDP hasta 7 s. Finalmente cierra únicamente su servidor y Chrome propio.
Usa Node 22 integrado, perfil nuevo `mkdtemp`, servidor `127.0.0.1:0` que rechaza 8765,
assets dist con rutas restringidas y CSP/no-store iguales a producción. No importa backend ni permite
POST distintos de `/api/raw-draft`; bootstrap y Auth status son metadatos ficticios fijos (nonce local
renovado al bootstrap). Cada solicitud tiene su propia compuerta de respuesta; no hay temporizadores
que simulen streaming. Red de página ajena al fixture bloqueada; clipboard sustituido solo en CDP
para comparar texto original y fallo sin tocar el portapapeles del sistema. Sin instalaciones, login,
logout, DB, CLI, modelos ni recorrido de avanzada/comparador. Producción 8765 no se accedió ni gestionó.

La matriz preparada exige vacío, historial de 20.000 Unicode/borrador largo y error HTTP fixture en
1366×768, 1920×1080 y 390×844: **9 capturas**, no nueve resultados ya observados.
Desktop captura viewport exacto sin scroll de página; móvil admite página completa. Reporta tamaños
viewport/PNG reales, rectángulos, padding, opacidad, hit testing, overflow y dueño del scroll.
No mide contraste y no lo declara aprobado. El rótulo **DEMOSTRACIÓN LOCAL — SIN IA REAL** se inserta
como pequeño hijo de `.header-title`, no como overlay ni alteración del CSS de producto; usa 14 px de
línea y 2 px de margen, con tamaño real registrado en cada checkpoint.

También prepara pruebas de Enter/montado/recarga sin POST, solicitud única íntegra, pending real,
needs_context no copiable, copia original/fallo, disclosures, Biblioteca/sidebar sin remontar textarea,
error/malformación/transporte/reconexión sin replay, Markdown hostil, CSP, storage/cookies y errores runtime.
Las aserciones geométricas no se relajan si falla la app: detiene y conserva evidencia alcanzada.

Artefactos futuros exclusivos: `%TEMP%/tato-raw-fixture-<aleatorio>/`, con
`NNN-<checkpoint>.json`, `<ancho>x<alto>-{empty,long,error}.png`, `report.json` o `failure.json`,
`gallery.html` con imágenes relativas y `chrome-profile/` retenido. Sin servidor persistente ni publicación.
Errores solo incluyen fase/conteos/metadatos seguros, nunca historial, tokens ni HTML de la página.
`node --check scripts/raw-ui-browser-check.mjs` es la comprobación de sintaxis, no ejecución del arnés.

Assets del build de esta unidad: `index-DMmHDA4r.js` (872,43 kB), `index-DjIXiPiM.css` (70,94 kB),
`highlighted-body-KPVGNVTW-DnyU59sl.js` (0,46 kB). Assets anteriores retenidos; sourcemap false.
**#63 permanece abierto y sin aprobación visual; solo Maxi aprueba. #59 no se usó.**
El recorrido Chrome histórico parcial descrito abajo permanece como evidencia anterior, no se reemplaza.

## Estado de la unidad anterior — recomposición RAW solamente

Maxi rechazó la composición anterior. Esta unidad modifica únicamente **Responder conversación**:
paneles simultáneos Conversación/Borrador (45/55), sidebar de 216px, espacio restante completo,
scroll interno y pies de acción no encogibles. En móvil se apilan con scroll vertical normal.
Se reutilizan PromptInput, Button, EmptyState y StaticMarkdown, sin wrapper de chat ni scroll al fondo.
La región del borrador se monta de nuevo al llegar un resultado para comenzar desde arriba; el textarea
no se remonta al abrir navegación, Biblioteca ni disclosures. Criterios y privacidad tienen cuerpo acotado;
diagnóstico sigue en Detalles técnicos. No se cambiaron lógica de peticiones, Auth, backend ni dependencias.

**Implementación no equivale a aprobación visual. #63 sigue abierto; #59 no se utilizó.**
Solo Maxi puede aprobar la composición. Pendientes navegador fixture y capturas a 1366×768,
1920×1080 y 390×844; jsdom no demuestra geometría, contraste ni CSP.
No se accedió, reinició ni detuvo producción 8765. No hubo red real, modelos, Auth ni DB en esta unidad.

Evidencia de esta unidad:
- Baseline: 165/165 tests, 7 archivos.
- RED: 46 fallos / 120 pasan (166), por paneles/heading ausentes y nuevo label aún no implementado.
- GREEN: 166/166, 7 archivos; incluye guardas previas y visibilidad de retrieval con disclosure abierto.
- `npm run typecheck`: exit 0, dos proyectos TypeScript sin emitir.
- `npm run build`: exit 0, 2330 módulos; conserva assets anteriores, sourcemap false.
- `node --check scripts/ui-browser-check.mjs`: exit 0; solo sintaxis. Driver cambiado solo en label RAW.
- Advertencias del build: use-client ignorado, ubicación de sourcemap de diagnóstico y chunk >500 kB.

Assets actuales de `dist/index.html`: `index-BB0B_WQF.js` (872,37 kB),
`index-DjIXiPiM.css` (70,94 kB); chunk `highlighted-body-KPVGNVTW-3omzpf5G.js` (0,46 kB).

Selectores para la siguiente unidad fixture: `[data-workspace="raw"]`, `.raw-composer`,
`.raw-input-panel`, `#raw-history`, `.raw-draft-panel`, `.raw-draft-scroll`, `.raw-support`,
`.raw-action-footer`, `.raw-copy-footer`. Regiones accesibles: Conversación, Borrador, Borrador completo.
Botones: Generar borrador, Limpiar, Copiar DM (solo resultado dm). Vacío exacto: El borrador aparecerá aquí.
Disclosures: Criterios y fuentes, Privacidad y límites, Detalles técnicos.

El recorrido Chrome anterior **sí corrió parcialmente**: llegó a Biblioteca y resultado RAW, pero no
completó avanzada. Las correcciones posteriores del árbol fueron interrumpidas. No se reejecutó Chrome
en esta unidad; el recorrido/capturas nuevo es otra unidad, no evidencia implícita de este build.

## Evidencia histórica de la implementación anterior (diseño rechazado)

Lo siguiente describe la unidad anterior, no pruebas reejecutadas ni aprobación del diseño actual.
Implementación local de todas las vistas, sin activar producción ni ejecutar generación viva.
**#63 permanece pendiente de verificación independiente y revisión visual. #59 no se usó.**
No se hicieron llamadas reales a Codex, Auth, Supabase, modelos ni DB; tampoco cambios de backend,
reglas normativas, fichas, embeddings o configuración global. El arnés no se ejecutó en aquella
unidad de implementación; posteriormente tuvo el recorrido parcial descrito arriba.
La conservación se basa en el alcance de escrituras de esta tarea, no en una comparación de hashes
antes/después de los archivos ajenos.

## Qué cambió

- **Navegación:** sidebar shadcn/ui Radix colapsable, sin cookie; sheet móvil con foco modal,
  Escape, cierre explícito y devolución de foco al botón. Tres modos reales, sin capacidades ficticias.
- **Responder conversación:** columna de lectura central, composer AI Elements de texto controlado,
  aviso de transmisión visible, botón informado, estado vacío/cargando/error y DM completo con Markdown estático.
  Enter agrega líneas. No hay adjuntos, reset automático, streaming, razonamiento ni descarga de historial.
- **Revisión avanzada:** composer compartido y área de conversación/respuesta, paso opcional para autores,
  revisión de roles, fechas, edición, separación, filtro y restauración intactos. Confirmaciones separadas.
- **Comparador:** caso explícitamente ficticio, variantes completas con Message/Conversation y señales mecánicas,
  sin puntaje inventado. Demo manual y generación con dos llamadas siguen siendo acciones distintas.
- **Biblioteca:** panel secundario no modal desde la cabecera. Abrir/cerrar conserva el nodo y texto del composer.
  Una sola instancia Auth por modo; cambiar de modo mantiene el descarte anterior y desmonta los controles.
  Muestra únicamente cantidad observada al consultar estado, no IDs/títulos/citas fabricadas.
  Selección y aprobación se declaran no disponibles, sin checkboxes simulados.
- **Privacidad y técnica:** paneles desplegables, aviso visible antes de transmitir, modelo/esfuerzo desconocidos,
  estado de servidor separado de la disponibilidad del modelo. Fuentes del sistema; ningún recurso gráfico remoto.
- **Presentación:** fondo grafito, acento verde/teal, bordes discretos, foco visible, anchos adaptativos y reducción
  de movimiento. Biblioteca admite Escape y cierre explícito, borrando las credenciales locales al cerrar.

## Contratos conservados

Los controladores JSX siguen siendo dueños de peticiones, validación y autorización; los componentes TSX son
presentación. No se agregó SDK de transporte, useChat, Gateway ni backend Next.

- Raw conserva POST `/api/raw-draft` exacto `{history, consent:true}`: historial Unicode completo hasta 24.000,
  sin parsear, recortar, deduplicar ni limpiar tras éxito/error. Una acción explícita, sin retry.
- `needs_context` sigue siendo aclaración para quien opera; no es un DM copiable.
- Avanzado conserva `/api/organize` con `{blocks, reviewed:true, consent:true}` y `/api/draft` con
  `{messages, reviewed:true, consent:true}`; nunca encadena ambas peticiones.
- Comparador conserva GET contexto, POST demo `{}` y POST generate `{consent:true}`, con dos llamadas informadas
  y presentación solamente del par completo.
- Todos los POST usan el nonce actual del padre. Se conservaron epoch de conexión, barrera síncrona Auth,
  inicio/finalización de cada transición y descarte de resultados, errores y confirmaciones obsoletos.
- Se conservaron la distinción TypeError/AbortError de transporte frente a SyntaxError de JSON, la reconciliación
  de estado Auth al finalizar y la dependencia de epoch/token en contexto sintético.
- Copiar sigue usando **el texto original**, nunca el DOM formateado. La invalidación de una copia tardía impide
  anunciar éxito/error obsoleto, pero no puede retirar del portapapeles una escritura ya iniciada.
- Email/password se vacían tras intento y cierre; JWT permanece exclusivamente en memoria del servidor.
  Sin localStorage, sessionStorage, cookies de sidebar ni persistencia nueva.

## Componentes oficiales y adaptaciones

Fuentes exactas, fechas UTC, SHA256 de cada registro consultado, licencias y archivos copiados en
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). El registro no ofrece versión semántica del source:
la identificación reproducible es el hash de su JSON, no una versión inventada del CLI.

`scripts/ui-registry.mjs` hizo una instalación manual de una lista cerrada: nueve primitives shadcn
(button, input, textarea, input-group, sidebar, sheet, separator, tooltip, skeleton), hook use-mobile y
Conversation/Message/PromptInput de AI Elements. Solo HTTPS oficial allowlisted, sin ejecutar comandos remotos.
Valida la salida dentro de UI/hooks y **rechaza sobrescribir archivos existentes**; no es un actualizador.
No se ejecutó shadcn CLI ni el instalador AI Elements que agrega toda la biblioteca.

Las reducciones conservan código upstream utilizado:

- Conversation, Content y EmptyState sin export de descarga; movimiento instantáneo.
- Message, Content y Response sin ramas, herramientas ni cuatro plugins Streamdown innecesarios.
  El tipo de rol usa una unión local en lugar de instalar AI SDK solo por un tipo.
- PromptInput conserva InputGroup/Body/Footer y Textarea. Su shell está adaptado a un div de texto controlado,
  sin form-submit/reset, provider, archivos, blobs, screenshots ni teclas que transmitan. No se presenta como
  la API completa upstream. El botón real permanece en el controlador, con sus guardas originales.
- Sidebar sin cookie, anchos en CSS compilado y textos accesibles en español. La devolución de foco móvil
  se agregó porque el trigger global no pertenece al Root interno de Sheet.
- `DraftMessage.tsx` configura Streamdown 2.6.0 en `mode="static"`, sin animación, controles ni plugins externos.
  Un plugin remark convierte nodos HTML en texto antes de renderizar, sin doble escape de código.
  Los componentes de enlaces e imágenes omiten URLs y no crean recursos ni navegación. `rehypePlugins=[]`,
  `skipHtml` y una lista cerrada de elementos limitan la superficie. Saltos de línea conservados por CSS.

### Dependencias directas nuevas, fijadas

| Paquete | Versión | Uso |
| --- | --- | --- |
| radix-ui | 1.6.7 | Imports oficiales Radix de primitives; no Base UI |
| class-variance-authority | 0.7.1 | Variantes shadcn |
| clsx / tailwind-merge | 2.1.1 / 3.7.0 | cn local |
| lucide-react | 1.48.0 | Iconos declarados por el registro |
| streamdown | 2.6.0 | Markdown estático real |
| use-stick-to-bottom | 1.1.6 | Conversation upstream |
| tailwindcss / @tailwindcss/vite | 4.3.3 / 4.3.3 | CSS local compilado |
| typescript | 5.9.3 | Chequeo estricto sin emitir |
| @types/react / @types/react-dom | 19.3.0 / 19.3.0 | Componentes React TSX |
| @types/node | 22.19.0 | Configuración Vite |

React/DOM 19.3.0 coinciden con la instalación previa informada; Vite 7.2.2, Vitest 4.0.9 y los Radix directos
previos se conservaron. Manifest y lock fijan versiones. Instalación observada: 185 paquetes agregados,
1 removido y 4 cambiados; scripts npm deshabilitados, sin audit/fund ni force/legacy-peer-deps.
`npm ls --depth=0` terminó sin dependencias inválidas.

## CSP y límites de navegador

No se editó la política del backend:

```text
default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'; object-src 'none'
```

El Overlay upstream de Radix incorpora RemoveScroll, que inyecta un `<style>` incompatible con esa política.
Los dialogs de revisión y Sheet usan un backdrop HTML con CSS estático; conservan Content/Portal/Root Radix,
focus trap, hideOthers, Escape y cierre externo. El bloqueo de scroll vive en CSS `body:has(...)`.
No se usa el token CSRF como nonce ni se habilita unsafe-inline. Algunas librerías usan propiedades CSSOM;
esto no equivale a permitir tags style inyectados. jsdom no demuestra compatibilidad CSP: el arnés preparado
la mide en Chrome y falla si recibe `securitypolicyviolation` o encuentra style tags.

## Evidencia ejecutada

Comandos desde la raíz del repositorio, en primer plano:

| Comando | Resultado observado |
| --- | --- |
| `(cd tools/editorial_rag/web && npm test -- --run)` | Base: 153/153. RED: 2 fallos esperados, 154 pasan (156 total), sidebar ausente y Markdown sin formato. Iteración: 155/156 por strong representado con span; se adaptó a HTML semántico. Triangulación RED: 158/159 por doble escape en inline code; corregido mediante AST remark. GREEN: 159/159; final con pruebas de credenciales/copia tardía: **162/162**, 7 archivos. Ninguna de las 153 aserciones previas de autorización fue retirada. |
| `(cd tools/editorial_rag/web && node scripts/ui-registry.mjs)` | Completó instalación allowlisted y notices, antes de adaptaciones locales posteriores. No reejecutar sobre archivos existentes. |
| `(cd tools/editorial_rag/web && npm install --ignore-scripts --no-audit --no-fund --registry=https://registry.npmjs.org)` | Exit 0; advertencia de dependencia transitiva whatwg-encoding obsoleta. |
| `(cd tools/editorial_rag/web && npm ls --depth=0)` | Exit 0; árbol válido con versiones fijadas. |
| `(cd tools/editorial_rag/web && npm run typecheck)` | Exit 0. TypeScript estricto para todos los nuevos TS/TSX y config Vite; JSX heredado no se declara migrado a TS. `skipLibCheck` omite d.ts ajenos, no source local. Sin any ni ts-nocheck agregados. |
| `(cd tools/editorial_rag/web && npm run build)` | Exit 0; sourcemap false y emptyOutDir false. Advertencias de directivas use-client ignoradas, mapeo de diagnóstico y chunk >500 kB, no ocultadas. |
| `tools/editorial_rag/.venv/Scripts/python.exe -B -m unittest discover -s tools/editorial_rag -p 'test_*.py'` | 165/165, sin generación real. |
| `tools/editorial_rag/.venv/Scripts/python.exe -B -m unittest tools.editorial_rag.test_local_web` | 40/40; Server.run/socket mockeados. Los mensajes de arranque impresos por tests no significan servidor activo. |
| `tools/editorial_rag/.venv/Scripts/python.exe -B .agents/skills/tato-calistenia/scripts/validate_runtime.py` | Runtime válido; comprobación estática, no calidad semántica. |
| `(cd tools/editorial_rag/web && node --check scripts/ui-browser-check.mjs)` | Exit 0; únicamente sintaxis, sin lanzar Chrome. |

Python emitió StarletteDeprecationWarning sobre httpx; no se modificaron dependencias Python.
No se ejecutó la alternativa opcional npx: se eligió instalación manual.

Build final referenciado por `dist/index.html`:

- `assets/index-BNPtIkgg.js`: 871,55 kB (274,43 kB gzip).
- `assets/index-DXUMqFoq.css`: 66,49 kB (13,28 kB gzip).
- `assets/highlighted-body-KPVGNVTW-BcLO858Y.js`: 0,46 kB; chunk transitivo Streamdown, sin plugins instalados.

Los assets anteriores se retuvieron deliberadamente. No se realizaron limpiezas destructivas.

## Verificación visual independiente pendiente

Comando del arnés histórico (recorrido parcial posterior; nueva ejecución pendiente y fuera de esta unidad):

```bash
(cd tools/editorial_rag/web && node scripts/ui-browser-check.mjs)
```

Solo usa Node integrado, WebSocket/CDP y Chrome en `C:/Program Files/Google/Chrome/Application/chrome.exe`.
Falla si falta Chrome/build; no instala nada. Crea un servidor exclusivo en loopback con puerto efímero,
rechaza 8765 y sirve build + fixtures ficticios, con banner explícito y CSP idéntica. No importa backend,
lee credenciales ni toca servicios. Intercepta peticiones de página y bloquea destinos ajenos al fixture;
además deshabilita servicios de fondo/extensiones y resolución externa de Chrome. Esto no es una auditoría
OS de tráfico ajeno a la página.

Verifica montado/Enter/recarga sin POST, clic raw informado, historial intacto, cantidad de biblioteca,
Markdown hostil, error/reconexión sin replay, revisión/consentimiento avanzado, comparador/demo y cancelación,
sidebar móvil/foco/Escape, ausencia de storage/style tags/overflow y violaciones CSP. Los POST se registran
como **fixtures**, jamás como generaciones. No ejecuta generate ni login/logout durante el recorrido.
Capturas desktop/mobile, biblioteca, revisión, consentimiento y comparador se guardan solamente dentro de
un nuevo `tato-ui-fixture-*` bajo OS Temp. Deadline acotado; finally cierra únicamente el servidor/proceso
creados por el script. Conserva el perfil temporal propio sin borrar nada; nunca abre un perfil personal.
Un fallo escribe failure.json y devuelve exit 1. No hay toggle de fixtures en la aplicación productiva.

Pendientes: correr ese arnés, inspeccionar capturas/contraste/layout en Chrome real y revisar tamaño del bundle.
No se afirma que CSP o visuales ya hayan sido verificados en navegador. Tampoco se afirma producción activa,
Auth real, funcionamiento vivo de Codex ni mejora semántica de DMs.

## Incidente operativo Engram — separado de la app

Evidencia aportada por el padre, no reejecutada por este writer: `mem_doctor` falla al resolver identidad del
servidor local `127.0.0.1:7437`; `ENGRAM_URL` y `ENGRAM_BIN` no definidos, ejecutable en PATH presente,
conexión TCP a 7437 exit 0. **TCP accesible no demuestra identidad, salud ni estado de DB.**
No se hizo reset, borrado, arranque ni cambio de configuración. La UI continúa sin depender de Engram y no
muestra esta incidencia como advertencia de runtime.
