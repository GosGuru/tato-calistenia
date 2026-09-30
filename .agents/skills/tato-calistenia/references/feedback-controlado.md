# Correcciones controladas — solo mantenimiento

Una corrección mejora el caso actual; no reprograma el setter. El ledger es evidencia de mantenimiento, nunca instrucciones cargadas en `prospect_dm`, lote, brief o EOD. No consultar ni guardar chats, nombres, handles, citas de DMs, eventos ni borradores para aprender.

## Decidir el alcance antes de escribir

| Entrada actual de Maxi | Alcance | Acción |
|---|---|---|
| `Me gusta más así` o edición de un DM | `local_edit` | Aplicar solo a esa instancia compatible con fundamentos; no persistir. |
| Preferencia de tono | `style` | Delimitar cuándo sirve y cuándo no; no cambiar fase, seguridad u oferta. |
| Pedido explícito de regla reutilizable | `general_rule` | Proponer principio, alcance, excepción y contraste sintético. |
| Elogio ambiguo o aprobación dentro de una transcripción histórica | Ninguno durable | No equivale a aprobación actual. |

Un pedido de propuesta no autoriza guardar la propuesta. Antes de cualquier mutación durable, mostrar qué se guardaría, en qué dueño y qué regla existente reemplaza; obtener aprobación actual y explícita para esa escritura. La autorización de documentar un candidato no autoriza aplicarlo. No agregar reglas acumulativas si corresponde sustituir una existente.

## Ciclo humano

1. Extraer un principio general sanitizado, su alcance, excepción y contraste sintético de cambio/no cambio. No conservar la frase recibida ni una salida para copiar.
2. Resolver el dueño con `assets/source-governance.json`. El motor decide precedencia; voz solo forma; contexto hechos; objeciones conversión; maseteo lote; tracking EOD; biblioteca técnica; este archivo mantenimiento. Operativa detalla evidencia de fases y handoff el brief. SKILL activa y carga.
3. Mostrar el principio exacto, la regla que sustituye y los límites. Si contradice fundamentos, declararlo como candidato inactivo y pedir una decisión de mantenimiento explícita sobre el conflicto; no usar una corrección informal como excepción silenciosa. Seguridad y privacidad permanecen protegidas.
4. Una aprobación actual del principio exacto ya mostrado puede proceder sin pedir que se repita. Un sí ambiguo, elogio o material histórico no alcanza. Si cambian principio, alcance, excepción o reemplazo, volver a mostrar la propuesta completa antes de promoverla.
5. Con autorización de mantenimiento, registrar únicamente criterio general y dos IDs de fixtures existentes. Revisar por separado aplicación y no aplicación. Editar el dueño real, actualizar resúmenes afectados y validar antes de declarar `applied`.
6. Para revertir, obtener autorización actual de mantenimiento, editar el dueño real y verificar el comportamiento anterior y sus excepciones. Cambiar solo `status` no revierte nada.

## Ledger v1

`assets/feedback-ledger.json` empieza vacío; no reconstruye aprobaciones históricas. Raíz exacta `version` entero 1 y `records` lista. Cada registro tiene exactamente:

- `id` único en minúsculas y guiones; `status` entre `candidate`, `rejected`, `approved`, `applied`, `reverted`.
- `kind` durable `style` o `general_rule`; `local_edit` se clasifica pero se rechaza en almacenamiento.
- `owner` ruta relativa canónica existente; `principle`, `scope`, `exception`, `replaces`, `contrast` textos generales no vacíos. `replaces` identifica la regla previa incluso si todavía no tiene entrada de ledger.
- `change_case` y `no_change_case`, IDs distintos de fixtures existentes; no son respuestas modelo.
- `previous` y `replacement`, ID o null. Si hay registros vinculados, enlaces recíprocos, mismo dueño y sin ciclos. No inventar una entrada anterior para completar una cadena.
- `approval` null para candidato/rechazado; para aprobado/aplicado/revertido, objeto exacto con `by` igual a `user`, `decision` igual a `explicit` y `principle` idéntico al aprobado. No almacenar identidad personal ni citas del usuario.

`candidate` propone; `rejected` no opera; `approved` permite la aplicación autorizada; `applied` documenta una edición comprobada; `reverted` documenta una reversión comprobada. Una nueva propuesta reemplazante puede estar vinculada sin estar activa. El estado del ledger no activa ni desactiva reglas por sí mismo.

Los metadatos de aprobación son una declaración revisable, no identidad humana criptográfica ni prueba de consentimiento real. El validador comprueba forma, tipos, rutas, unicidad y referencias; no puede comprobar verdad humana, sanitización semántica o equivalencia de la edición. La revisión humana conserva esa responsabilidad.

## Verificar sin automatizar

`runtime_governance.py` ofrece solo validación de lectura, sin comandos approve/apply ni acceso al CRM. `validate_runtime.py` la incluye por defecto. Estas instrucciones son prosa, no enforcement de herramientas ni sandbox del host.

Comparar con modelo y esfuerzo fijos primero; registrar los valores reales o desconocidos, no inferirlos. Después variar una sola condición. Usar sesiones frescas y repeticiones multi-turno, con ejecutor sin expectativas y puntuación separada. Revisar fidelidad, fase, voz, seguridad e intención; un acierto aislado no demuestra generalización. No existe integración automática de proveedor ni evaluador semántico en este cambio.
