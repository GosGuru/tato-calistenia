# Cierre EOD y registro manual

Cargar solo para `eod_review` o mantenimiento explícito del registro. El registro automático del agente está eliminado. El CRM web es manual y no está conectado al agente, Instagram ni ManyChat.

## Privacidad y almacenamiento

- No consultar ni escribir bases locales o remotas, crear leads, reconstruir eventos persistentes ni guardar borradores durante conversaciones, lotes, briefs o cierres EOD.
- Usar solo evidencia aportada para ese cierre. No recuperar automáticamente chats, exportaciones ni el ledger histórico.
- No persistir chats crudos ni versionar bases, exportaciones o identificadores privados.
- Conservar intactos bases históricas, exportaciones, `../scripts/crm_tracker.py` y `../assets/crm-event.schema.json`. Son utilidades históricas/manuales, no requisitos del agente. Solo un pedido explícito de mantenimiento con alcance definido autoriza su uso; no migrar ni borrar datos sin autorización.

## Evidencia y cobertura

- Distinguir borrador, intención y envío observado o verificado. Solo los últimos aportan métricas de contacto.
- Identificar personas por handle de Instagram o ID estable de ManyChat aportado; un nombre visible solo no permite deduplicar identidades con certeza.
- Contar una persona una sola vez aunque haya varias burbujas o se repita una captura. No asumir que dos identidades de plataformas distintas son la misma persona.
- Usar fechas verificables en `America/Montevideo`; no inventar fecha, hora ni zona. Sin evidencia fechada, marcar pendiente y excluir del recuento fechado.
- Declarar siempre cobertura parcial de la evidencia aportada, no sincronización ni totalidad de la actividad real. Falta de evidencia no significa cero.
- Separar el mínimo comprobable de lo pendiente. No ejecutar el agregador ni leer la base como alternativa automática.

## Definiciones EOD

- `Personas distintas contactadas hoy`: identidades únicas con al menos un envío observado o verificado ese día; varias burbujas cuentan una persona.
- `mensajes_enviados`: clave heredada del formulario; conserva la métrica de personas distintas, no cantidad de burbujas.
- `respondieron`: personas con respuesta verificable posterior a un outbound del mismo día. No implica causalidad comercial.
- `respuestas_tardias`: personas que respondieron hoy a un outbound anterior; no duplicar si también respondieron después de otro outbound de hoy.
- `seguimientos`: personas con seguimiento enviado verificable, nunca un seguimiento solamente redactado.
- `calidad`: alta, media, baja o sin clasificar, únicamente cuando la evidencia permite esa clasificación, sin inferir dinero por perfil.
- `objeciones`: objeciones observadas por categoría, sin atribuir motivos inventados.
- `energia` y `como_te_sentiste`: pendientes de Maxi.

## Nueve campos del cierre

Abrir el borrador con `Personas distintas contactadas hoy` y mantener los nueve campos del formulario, sin añadir burbujas como métrica cotidiana:

1. FECHA DE HOY
2. ¿Cuántos mensajes enviaste?
3. ¿Cuántos respondieron?
4. ¿Cuántos seguimientos realizaste?
5. CALIDAD de los LEADS de hoy
6. Objeciones comunes por las cuales no agendas llamada
7. ¿Cómo estás de energía hoy?
8. Comentarios extras - referidos al setteo
9. extra… (cómo te sentiste hoy?)

Anotar cobertura parcial, respuestas tardías y datos pendientes en comentarios. Un dato no comprobado queda pendiente, no se convierte en cero. Pedir energía y sensación a Maxi, presentar el borrador y esperar aprobación.

## Cierre programado

Preparar el EOD solo por pedido explícito o cuando lo active una programación ya autorizada. Si falta evidencia aportada para ese cierre, solicitarla sin consultar bases automáticamente ni inventar cifras. No modificar la programación existente.

No abrir, completar ni enviar Google Forms sin autorización explícita para ese cierre. La autorización para preparar no autoriza a enviar ni a leer o escribir el CRM histórico.
