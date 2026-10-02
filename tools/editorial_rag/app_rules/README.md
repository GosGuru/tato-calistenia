# Pack de prompts de la app DM — `app_rules`

Pack de runtime separado y liviano para la app DM de Railway. Existe para invertir la
proporción reglas–voz sin tocar las siete referencias normativas del setter local: esas
fuentes siguen intactas y el hash de `load_real_rules()` que usa el banco offline
(`raw_evaluation.py`) se mantiene válido.

## Por qué: la proporción medida

Todos los números de esta sección se miden sobre el contenido real de este pack con
`len()`: el texto de `base.md` y los pasajes de `criterion_passage()` de las 20 cards.

- `base.md` pesa **12,019 caracteres** (techo duro: 25,000).
- Los 20 pasajes de las cards suman **17,910 caracteres** y promedian **896 caracteres**
  cada uno (895.5 exactos).
- Ventana de 2 cards (`DEFAULT_GUIDANCE`, la ventana actual de recuperación):
  12,019 / (2 × 895.5) = proporción base–guía de **6.7:1**.
- Ventana de 8 cards (`MAX_GUIDANCE`, el nuevo techo de recuperación):
  12,019 / (8 × 895.5) = proporción base–guía de **1.7:1**.

La ventana de 8 cards acerca la guía recuperada a la base siempre activa; con 2 cards la
guía que llega al modelo sigue siendo una fracción chica del contexto.

## Qué se movió y dónde

El corte es por **tipo de contenido**, no por archivo: `voz-escrita-tato.md` y
`biblioteca-tecnica-tato.md` mezclan invariantes con expresividad y conocimiento.

| Tipo de contenido | Destino | Ejemplos |
|---|---|---|
| Prohibiciones y contratos duros (formato, voz–contrato, oferta y agenda, seguridad y salud, secuencia y conversión) | `base.md`, siempre activo | sin signos de apertura, sin dos puntos en prosa, una sola pregunta de dirección, primera persona, USD 300 interno, sin diagnóstico ni prescripción, sin pedir videos |
| Expresividad y conocimiento | `cards.json`, recuperables | espejo de registro, reconocimiento proporcional, puentes conectivos, reacción a una apertura emocional, orientar sin corregir, traducción corporal de la técnica |

Si un invariante quedara solo en una card, un caso que no recupere ninguna card
regresaría. Por eso todo invariante vive en `base.md`, y eso está probado.

## `invariants.md` es la garantía de seguridad

`app_rules/invariants.md` inventaría **cada invariante** con su archivo fuente y su rango
de líneas, tomados literalmente de las siete referencias. El test
`test_app_rules.py::InvariantInventoryTests` parsea ese inventario y verifica que cada
cita siga apareciendo en el rango citado: si cambia una línea fuente que sostiene un
invariante listado, el test falla. También verifica que cada `base_anchor` esté en
`base.md`. Conteos: **65 invariantes capturados** (formato 9, voz–contrato 13, oferta y
agenda 12, seguridad y salud 10, secuencia y conversión 21) y **20 grupos juzgados
expresivos**, repartidos en 20 cards.

## Cards y tamaño por pasaje

Cada card pasa el esquema `Card` de `prototype.py` y los límites de campo de
`editorial_criteria.py`. `criterion_passage()` concatena `phase`, `gate`, `situation`,
`last_assistant_move`, `proposed_move`, `positive_voice` y `negative_repetition`; el
embedder rechaza pasajes de más de **512 tokens** (`embedding_node/model_manifest.json`
`max_tokens`).

Ese techo ya se mide con tokens reales: la tokenización corre localmente sobre el
`tokenizer.json` fijado del cache del modelo (el mismo archivo que carga el embedder de
transformers.js) y las cuentas fueron verificadas una por una contra el tokenizer real de
transformers.js, con resultados idénticos. El conteo usa `passage: ` + pasaje con tokens
especiales, igual que el `tokenLength` de `embedding_node/embed.mjs`. Conteos exactos de
hoy:

| Card | Caracteres del pasaje | Tokens del pasaje |
|---|---|---|
| `voice-reconocimiento-proporcional` | 916 | 210 |
| `voice-espejo-vocabulario` | 901 | 227 |
| `voice-puente-conectivo` | 910 | 220 |
| `voice-pregunta-directa` | 844 | 203 |
| `voice-escucha-visible` | 865 | 203 |
| `voice-autoridad-hecho` | 890 | 205 |
| `voice-reentrada-saludo` | 772 | 189 |
| `voice-ruta-contextual` | 902 | 215 |
| `tech-orientar-sin-corregir` | 898 | 219 |
| `tech-traduccion-corporal` | 880 | 204 |
| `voice-invitacion-calida` | 977 | 229 |
| `voice-objecion-dignidad` | 889 | 223 |
| `voice-humor-calibrado` | 944 | 231 |
| `voice-apertura-coloquial-cadencia` | 929 | 240 |
| `values-filtro-indiferencia` | 939 | 217 |
| `voice-estas-a-tiempo` | 907 | 225 |
| `voice-punto-b` | 876 | 213 |
| `voice-cambio-fisico-proceso` | 832 | 198 |
| `voice-followup-concreto` | 878 | 210 |
| `voice-sondeo-evasion-serena` | 961 | 234 |

Total 17,910 caracteres y **4,315 tokens**; máximo observado **240 tokens**
(`voice-apertura-coloquial-cadencia`), menos de la mitad del techo real de 512. La relación
observada es de unos **4.2 caracteres por token** (rango por card 3.87–4.36), muy por
debajo de la suposición conservadora anterior. El proxy de **1,200 caracteres** queda solo
como guardia barata del loader (`app_rules.py`, que no tokeniza en runtime) y equivale a
unos 289 tokens al ratio observado; el límite que gobierna es el real de 512 tokens.

La validación contra el techo real vive en `test_prepare_card_seed.py`, que cuenta tokens
reales de las 20 cards, y `prepare_card_seed.py` rechaza cualquier pasaje sobre el techo
antes de planificar el seed. Ninguna card del pack necesita acortarse hoy.

## Flujo de dos pasos hacia la base: candidatos y luego aprobación con embedding

Los planes de SQL de este pack se aplican en dos pasos, siempre con revisión manual previa.
Ninguna herramienta se conecta a la base ni a la red: leen un snapshot local y escriben un
plan y un reporte. Un plan no es autorización.

1. **Insertar candidatos** — `prepare_card_insert.py`:
   `python -B -m tools.editorial_rag.prepare_card_insert --snapshot <snapshot.json>
   --output-dir <dir>` genera `card-insert-plan.sql` y `card-insert-report.json`. El plan
   inserta las filas como `candidate` y **omite `status` y `approval_id`** a propósito: el
   grant de insert es por columnas y no los incluye, y los defaults de la tabla (`candidate`,
   `NULL`) satisfacen la policy `editorial_insert`. Verifica las huellas contra
   `public.editorial_content_fingerprint(c)` antes del `COMMIT` y aborta si algo no cierra.
2. **Aprobar y calcular embeddings** — `prepare_card_seed.py`:
   genera `card-seed-plan.sql` y `card-seed-report.json`, que aprueban las mismas filas y las
   insertan en `public.editorial_card_embeddings`. Los guards de contenido del seed plan
   verifican en la base la misma huella que el paso 1 insertó, así que los dos planes
   comparten el mismo contrato de snapshot y las mismas huellas derivadas del contenido.

   Con `--per-card`, en lugar del plan batch emite **un plan autocontenido por card**
   (`card-seed-<card_id>.sql`, cada uno con su `BEGIN`/`COMMIT`, su `LOCK` y todos los guards
   escalados a 1) más un índice `card-seed-per-card-report.json`. Las veinte huellas y los
   hashes de wire coinciden con el reporte batch para el mismo snapshot, pero cada plan es
   atómico y se aplica de a uno: si uno falla, el fallo se aísla en esa card. El plan batch
   sin el flag sigue saliendo byte a byte igual. Las veinte cards comparten un único
   `approval_id` porque el batch es un solo evento de aprobación.

Contrato compartido por ambos artefactos:

- son **de un solo uso**: se crean con apertura exclusiva (`xb`) y jamás se sobrescriben;
- **llevan un UUID de aprobación** generado al prepararse: `rag-card-insert-<uuid>` en el
  encabezado del plan de inserción (solo identificador; las filas conservan los defaults) y
  `rag-card-<uuid>` como `approval_id` en el plan seed;
- **no se versionan**: son artefactos de trabajo, no fuentes;
- exigen revisión manual y ejecución en el SQL editor de Supabase con un rol **con
  BYPASSRLS** (`postgres` o `service_role`): la tabla tiene `force row level security` y la
  policy de insert es `to authenticated`, así que cualquier otro rol queda denegado y una
  corrida sin JWT deja `auth.uid()` en NULL y falla la policy;
- el reporte nunca lleva prosa de las cards: solo `card_id`, `fingerprint` y metadatos.

## Loader

`tools/editorial_rag/app_rules.py` lee solo este pack:

- `load_app_rules()` devuelve el texto de `base.md`;
- `load_app_cards()` devuelve instancias `Card` validadas y **rechaza con `ValueError`**
  cualquier card malformada (campos de más o de menos, identificadores inválidos, status o
  fase inválidos, textos vacíos, byte nul, campos de más de 2,000 caracteres, ids
  duplicados).

No importa ni toca el loader de reglas del setter local; el test
`LoaderIsolationTests` lo verifica por AST y además fija el sha256 de
`load_real_rules()` al snapshot previo a la creación de este pack.

## Pruebas

```
cd "C:/Users/Maxim/OneDrive/Escritorio/TODO/TATO CALISTENIA"
C:/Python314/python.exe -m pytest tools/editorial_rag -q
```

Cuatro contratos: inventario de invariantes fijado a las fuentes, aislamiento del loader
(`real_history` intacto), esquema de cards con `criterion_passage`, y tamaño por pasaje.
`test_prepare_card_seed.py` agrega la validación del techo real de 512 tokens por pasaje.
`test_prepare_card_insert.py` cubre el plan de inserción: columnas del `INSERT`, guards que
escalan con N, escape de comillas, artefactos de un solo uso y el enlace de huellas con
`seed-plan/card-seed-report.json`.
