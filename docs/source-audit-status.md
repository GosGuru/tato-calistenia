# Cobertura de fuentes — solo mantenimiento

La auditoría no convierte fuentes históricas en instrucciones. Se mantienen las traducciones vigentes; nuevas conclusiones requieren el ciclo de [correcciones controladas](../.agents/skills/tato-calistenia/references/feedback-controlado.md). Este informe resume evidencia remitida por el padre, no una nueva lectura de material privado por el implementador.

## Cobertura reportada

| Material | Cobertura real | Límite |
|---|---|---|
| 429 transcripciones de audios salientes | Padre y tres auditores cubrieron todo el conjunto; rangos de líneas 1–431, 432–860 y 861–1289 | Los rangos son líneas, no cantidades de audios. Salientes de propósitos mixtos, ASR y ofertas antiguas. |
| Informe agregado | 840 líneas leídas | Frecuencias contaminadas por automatización; no prueban voz limpia ni escucha. |
| Chat local | 60 líneas leídas | No demuestra un patrón general ni autoriza persistir conversaciones. |
| Documentos históricos de Julio | Cinco Markdown leídos | Otro agente/nicho contiene contradicciones; no heredar sus instrucciones. |
| Cursos en Markdown limpio | 353 archivos, aproximadamente 10,6 MB, solo inventariados | NO leídos en esta auditoría. No atribuir hallazgos ni aprobaciones nuevas. |
| Fuentes JSON anunciadas | 6048 no localizadas | Sin lectura ni cobertura verificable. |

Los salientes no reconstruyen por sí solos la conversación bilateral ni permiten medir escucha. Separar mensajes manuales, automatizados, campañas, soporte, enseñanza y venta antes de medir estilo. Excluir ASR defectuoso, ofertas y enlaces viejos, presiones, métricas económicas ajenas e instrucciones contradictorias del agente histórico. No trasladar cuotas, urgencia, guiones o inferencias de dinero de otro nicho.

La matriz curada conserva aprobaciones históricas acotadas de traducciones; eso no acredita lectura total de cursos ni aprobación del corpus original. `source-governance.json` separa traducciones aprobadas de fuentes históricas, pendientes, rechazadas y candidatas. Ningún archivo fuente privado se carga desde ese mapa.

## Próxima auditoría propuesta, todavía no ejecutada

1. Con autorización de acceso específica, formar un inventario estable de los 353 Markdown por identificadores sanitizados, ordenarlo y congelar su versión. No publicar rutas privadas.
2. Asignar particiones sin solapamiento por ordinal: 1–118, 119–236 y 237–353. Registrar cobertura efectiva y faltantes, no inferir lectura por tamaño o título.
3. Cada lector entrega solo Rescatar, Rechazar, traducción candidata, dominio y límites. El integrador contrasta duplicados y conflictos, sin inventar aprobación.
4. Tratar la localización de los 6048 JSON como tarea separada que requiere alcance de acceso explícito. No usarla para inflar cobertura del Markdown.
5. Para voz y escucha, proponer una muestra independiente y autorizada con contexto bilateral, exclusión de automatización y evaluación separada; no reconstruir ni guardar chats en este repositorio.

No se ejecutó ese plan ni se auditaron cursos durante esta implementación. No se cambian oferta, precio, duración, seguridad ni agenda por hallazgos históricos.
