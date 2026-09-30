"""Fixed fictional paired probes, preview-only unless explicitly authorized."""
import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .codex_runner import CodexSessionRunner
from .prototype import Card, Conversation, Message, compare, packets

RULE_PATHS = (
    '.agents/skills/tato-calistenia/SKILL.md',
    '.agents/skills/tato-calistenia/references/motor-agentico.md',
    '.agents/skills/tato-calistenia/references/voz-escrita-tato.md',
    '.agents/skills/tato-calistenia/references/operativa-dm.md',
)
CASE_ID = 'synthetic-repeated-opening-brecha'
CASE_OBSERVATION_INFERENCE = 'synthetic-brecha-observation-inference'
CASE_CONTEXTO_MISSING_EVIDENCE = 'synthetic-contexto-missing-evidence'
CASE_DISPOSICION_WITHOUT_PRESSURE = 'synthetic-disposicion-without-pressure'
CASE_RUTA_HELP_TO_GAP = 'synthetic-ruta-help-to-gap'
CASE_RUTA_CONCRETE_DOUBT = 'synthetic-ruta-concrete-doubt'
ELIGIBILITY = ('approved means fixture eligibility only, NOT production approval '
               'or human-approved learning')


def rule_paths(case_id=None):
    """Only route probes add offering and objection references."""
    if case_id in (CASE_RUTA_HELP_TO_GAP, CASE_RUTA_CONCRETE_DOUBT):
        return RULE_PATHS + (
            '.agents/skills/tato-calistenia/references/contexto-maestro.md',
            '.agents/skills/tato-calistenia/references/objeciones-agenda.md',
        )
    return RULE_PATHS


def load_rules(case_id=None):
    """Preserve complete UTF-8 sources including CRLF; default bundle unchanged."""
    root = Path(__file__).resolve().parents[2]
    return '\n\n'.join((root / path).read_bytes().decode('utf-8') for path in rule_paths(case_id))


def synthetic_case(case_id=None):
    """Return synthetic case by ID; defaults to CASE_ID for compatibility."""
    target_id = CASE_ID if case_id is None else case_id
    if target_id == CASE_ID:
        conversation = Conversation(
            sanitized=True, phase='brecha', gate='obstacle_missing',
            situation='Destino fuerza en calistenia y dominadas; falta obstáculo concreto.',
            last_assistant_move='clarify_destination',
            messages=(
                Message('assistant', 'entiendo, qué capacidad querés desarrollar?'),
                Message('user', 'fuerza'),
                Message('assistant', 'entiendo, en qué práctica querés desarrollar esa fuerza?'),
                Message('user', 'calistenia'),
                Message('assistant', 'entiendo, qué movimiento querés mejorar?'),
                Message('user', 'las dominadas'),
            ),
        )
        card = Card(
            card_id='synthetic-voice-criteria', provenance_id='synthetic-fixture',
            status='approved', sanitized=True, phase='brecha', gate='obstacle_missing',
            situation='Destino fuerza en calistenia y dominadas; falta obstáculo concreto.',
            last_assistant_move='clarify_destination', proposed_move='clarify_obstacle',
            positive_voice=(
                'Criterio sintético de voz, no plantilla de respuesta. En continuidad con '
                'respuestas breves, priorizar precisión y una pregunta necesaria; omitir '
                'validación genérica si no aporta. Redactar desde el caso sin copiar este texto. '
                'La elegibilidad approved de esta fixture no es aprobación de producción '
                'ni aprendizaje aprobado por una persona.'),
            negative_repetition=(
                'Evaluar la huella de aperturas recientes; no sustituir una muletilla '
                'repetida por otra firma fija ni reformular el destino ya conocido.'),
        )
        return conversation, (card,)

    if target_id == CASE_OBSERVATION_INFERENCE:
        conversation = Conversation(
            sanitized=True, phase='brecha', gate='brecha_interpretation',
            situation=('Aplica cuando una descripción de un intento o una traba permite distinguir '
                       'lo que la persona observó de una posible explicación todavía no confirmada.'),
            last_assistant_move='received_attempt_detail',
            messages=(
                Message('user', 'quiero mejorar las dominadas'),
                Message('assistant', 'qué es lo que más te está costando hoy con las dominadas?'),
                Message('user', 'me balanceo mucho al subir porque seguro me falta fuerza en los brazos'),
            ),
        )
        card = Card(
            card_id='separate_observation_from_inference', provenance_id='skool_016',
            status='approved', sanitized=True, phase='brecha', gate='brecha_interpretation',
            situation=('Aplica cuando una descripción de un intento o una traba permite distinguir '
                       'lo que la persona observó de una posible explicación todavía no confirmada. '
                       'No aplica para sustituir una respuesta concreta, diagnosticar, prescribir '
                       'o reabrir detalles que no cambian la decisión ni la seguridad.'),
            last_assistant_move='received_attempt_detail',
            proposed_move='clarify_evidence_boundary',
            positive_voice=('Nombrar con sencillez el dato disponible y mantener acotada la incertidumbre '
                            'sobre lo que ese dato no demuestra. Orientar solo dentro de lo respaldado y '
                            'enlazar con la evidencia realmente pendiente.'),
            negative_repetition=('No presentar una hipótesis como causa comprobada, borrar calificadores '
                                 'relevantes ni usar incertidumbre genérica como muletilla.'),
        )
        return conversation, (card,)

    if target_id == CASE_CONTEXTO_MISSING_EVIDENCE:
        conversation = Conversation(
            sanitized=True, phase='contexto', gate='contexto_missing_evidence',
            situation=('El contexto actual deja sin resolver un dato que cambiaría el siguiente movimiento '
                       'sobre el punto de partida y la experiencia previa.'),
            last_assistant_move='reviewed_known_context',
            messages=(
                Message('user', 'hola tato, vi tus videos y quiero empezar con calistenia'),
            ),
        )
        card = Card(
            card_id='ask_only_missing_evidence', provenance_id='skool_013',
            status='approved', sanitized=True, phase='contexto', gate='contexto_missing_evidence',
            situation=('Aplica cuando el contexto actual todavía deja sin resolver un dato que cambiaría '
                       'el siguiente movimiento. No aplica si el historial ya aporta contexto suficiente '
                       'ni si otra puerta prioritaria, como seguridad, rechazo, una objeción activa '
                       'o un bloqueo operativo, debe atenderse primero.'),
            last_assistant_move='reviewed_known_context',
            proposed_move='ask_missing_evidence',
            positive_voice=('Elegir la evidencia pendiente que pueda cambiar una decisión; conservar '
                            'lo que ya se sabe y preguntar de forma concreta, natural y proporcionada, '
                            'sin convertir las fases en un formulario.'),
            negative_repetition=('No pedir datos por completar una lista, repetir información conocida '
                                 'ni añadir preguntas cuyo resultado no modificaría el paso siguiente.'),
        )
        return conversation, (card,)

    if target_id == CASE_DISPOSICION_WITHOUT_PRESSURE:
        conversation = Conversation(
            sanitized=True, phase='disposicion', gate='disposition_evidence',
            situation=('Falta evidencia de voluntad para sostener un proceso guiado hacia las dominadas '
                       'y el historial permite una comprobación pertinente sin presión.'),
            last_assistant_move='reviewed_process_readiness',
            messages=(
                Message('user', 'trabajo en oficina 8 horas pero tengo 45 min 3 veces por semana para entrenar'),
                Message('assistant', 'es tiempo más que suficiente si el trabajo está ordenado'),
                Message('user', 'sí, solo que hasta ahora estuve probando cosas sueltas de internet y no veo avances'),
            ),
        )
        card = Card(
            card_id='respond_without_pressure', provenance_id='de0a10_117',
            status='approved', sanitized=True, phase='disposicion', gate='disposition_evidence',
            situation=('Aplica cuando todavía falta evidencia de voluntad para sostener un proceso guiado '
                       'y el historial ya permite una comprobación pertinente, o cuando una duda sobre la decisión '
                       'necesita una respuesta sin presión. No aplica para repetir un compromiso ya expresado, '
                       'tratar constancia o tiempo libre como prueba suficiente, ni prevalecer sobre rechazo, '
                       'imposibilidad explícita o incompatibilidad.'),
            last_assistant_move='reviewed_process_readiness',
            proposed_move='check_readiness_without_pressure',
            positive_voice=('Hablar en criollo llano y cotidiano sobre las circunstancias conocidas, '
                            'reconociendo si el tiempo alcanza sin frases armadas ni rodeos solemnes. '
                            'Preguntar con sencillez si está para meterse en un proceso con seguimiento '
                            'hacia su objetivo, dejando espacio para una respuesta libre y honesta.'),
            negative_repetition=('No usar tono solemne, frases de consultor ni análisis intelectualizado; '
                                 'no hablar de sostener una guía ni de que el punto no es sumar; no hacer un '
                                 'examen moral de compromiso ni usar urgencia, miedo, salud o dinero como palanca.'),
        )
        return conversation, (card,)

    if target_id in (CASE_RUTA_HELP_TO_GAP, CASE_RUTA_CONCRETE_DOUBT):
        messages = (
            Message('user', 'quiero hacer dominadas con más control, sin depender del impulso para subir'),
            Message('assistant', 'qué venís probando y dónde te trabás?'),
            Message('user', 'entreno por mi cuenta hace meses, sigo rutinas de internet pero me balanceo al subir y no sé qué cambiar ni cómo darme cuenta de si mejoro'),
            Message('assistant', 'para ubicar cómo entra esa práctica en tu vida, cómo es tu día a día?'),
            Message('user', 'trabajo por turnos en un taller, entreno en una plaza los días que salgo temprano y voy acomodando la semana cuando me pasan los horarios'),
            Message('assistant', 'estás para trabajar esas dominadas dentro de un proceso guiado?'),
            Message('user', 'sí, quiero recibir correcciones y aplicarlas, no seguir cambiando de rutina a ciegas'),
        )
        if target_id == CASE_RUTA_HELP_TO_GAP:
            card = Card(
                card_id='connect_help_to_concrete_gap', provenance_id='juli_structure',
                phase='ruta', gate='route_fit_to_gap', status='approved', sanitized=True,
                last_assistant_move='confirmed_route_readiness', proposed_move='relate_help_to_gap',
                situation=('Aplica cuando la evidencia permite presentar una ruta y hace falta explicar por qué una forma real de acompañamiento responde a la brecha concreta de esta persona. No aplica antes de conocer suficiente destino, brecha, realidad cotidiana y disposición, antes de resolver un freno activo o si la relación propuesta no está respaldada.'),
                positive_voice=('Explicar con palabras cotidianas cómo una ayuda real responde a la brecha y a la capacidad o autonomía buscada, usando solo mecanismos pertinentes al caso. Cada frase debe aportar algo distinto. Elegir vocabulario según el contexto y la voz de Tato, sin perder precisión. Pedir una reacción con una pregunta natural y esperar antes de convertir. Separar el puente de la pregunta solo si mejora el ritmo; usar el nombre únicamente si consta y resulta natural.'),
                negative_repetition=('No recitar prestaciones, ofrecer una ruta intercambiable, prometer resultados o que cierto tiempo alcanza, ni presentar orden o adaptación como explicación suficiente por sí solos. No reformular una misma idea para alargar el mensaje, imponer aperturas o cierres fijos, prohibir palabras pertinentes al caso ni recortar explicaciones necesarias.'),
            )
            situation = ('Destino dominadas con control; brecha en práctica sin feedback, turnos variables '
                         'y voluntad explícita de aplicar correcciones. Ruta aún no presentada.')
        else:
            messages += (
                Message('assistant', 'con la observación por video puedo ver cómo estás haciendo esas dominadas y darte correcciones sobre lo que aparezca, en vez de que sigas eligiendo cambios a ciegas\nla idea es que aprendas qué mirar en tu movimiento, con un plan que contemple tus turnos\ncómo ves ese camino?'),
                Message('user', 'y si me cambian el turno y ya no puedo entrenar los días que tenía pensados, qué pasa con el plan?'),
            )
            card = Card(
                card_id='resolve_concrete_doubt_first', provenance_id='de0a10_116',
                phase='ruta', gate='route_question_before_progress', status='approved', sanitized=True,
                last_assistant_move='presented_contextual_route', proposed_move='answer_route_doubt',
                situation=('Aplica cuando aparece una duda concreta sobre la ruta o la ayuda propuesta antes de que corresponda avanzar, y puede responderse dentro del alcance respaldado. No aplica para una urgencia, una necesidad fuera de alcance, un rechazo claro u otra excepción que exija frenar; tampoco autoriza a repetir el pitch o reiniciar fases ya resueltas.'),
                positive_voice=('Atender primero la duda específica con claridad, respeto y palabras cotidianas; conservar el estado alcanzado y retomar solo el paso pendiente, si corresponde. Cada frase debe aportar algo distinto, sin reiterar la misma respuesta con otras palabras. Elegir vocabulario según el contexto y la voz de Tato, sin perder precisión. Cuando corresponda pedir una reacción, hacerlo con una pregunta natural. Separar el puente de la pregunta solo si mejora el ritmo; usar el nombre únicamente si consta y resulta natural.'),
                negative_repetition=('No esquivar la pregunta para acelerar la conversión, responder con una defensa genérica, repetir el pitch ni encadenar la aclaración con una invitación no habilitada. No imponer aperturas o cierres fijos, prohibir palabras pertinentes al caso, recortar explicaciones necesarias ni prometer resultados o que cierto tiempo alcanza.'),
            )
            situation = ('Ruta contextual presentada; aceptación pendiente, no confirmada por la duda. '
                         'Pregunta concreta sobre el plan si cambian los turnos y días disponibles.')
        return Conversation(
            sanitized=True, phase='ruta', gate=card.gate, situation=situation,
            last_assistant_move=card.last_assistant_move, messages=messages,
        ), (card,)

    raise ValueError(f'Unknown synthetic case: {target_id}')


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=('Fixed synthetic case comparison. Default PREVIEW '
                     'shows current/editorial packet metadata, no generated drafts. '
                     'Only --run-codex authorizes two subscription Codex calls.'))
    parser.add_argument('--run-codex', action='store_true',
                        help='run the synthetic pair through ChatGPT subscription Codex; no API fallback')
    parser.add_argument('--case', choices=[
        CASE_ID, CASE_OBSERVATION_INFERENCE, CASE_CONTEXTO_MISSING_EVIDENCE, CASE_DISPOSICION_WITHOUT_PRESSURE,
        CASE_RUTA_HELP_TO_GAP, CASE_RUTA_CONCRETE_DOUBT,
    ], default=CASE_ID, help='select synthetic case to probe')
    args = parser.parse_args(argv)
    drafts = []
    try:
        rules = load_rules(args.case)
        conversation, cards = synthetic_case(args.case)
        current, editorial = packets(conversation, cards, rules)
        metadata = {
            'case': args.case, 'phase': conversation.phase,
            'rules_sources': rule_paths(args.case), 'rules_characters': len(rules),
            'messages': len(conversation.messages),
            'packets': [
                {'variant': current.variant, 'guidance': None},
                {'variant': editorial.variant, 'guidance': editorial.guidance.card_id if editorial.guidance else None},
            ],
            'fixture_status': ELIGIBILITY,
            'model': 'unknown (not pinned by runner)',
            'effort': 'unknown (not pinned by runner)',
        }
        if not args.run_codex:
            output = 'PREVIEW — synthetic; no generated drafts\n' + json.dumps(metadata, indent=2)
        else:
            runner = CodexSessionRunner()

            def capture(packet):
                draft = runner(packet)
                if not isinstance(draft, str) or not draft.strip():
                    raise ValueError('Empty draft')
                drafts.append(draft)
                return draft

            report = compare(conversation, cards, rules, capture)
            # Buffer the complete report before exposing either draft.
            output = ('REAL RUN — synthetic paired probe, not voice-quality evidence\n'
                      + json.dumps(metadata, indent=2)
                      + '\nCURRENT DRAFT (synthetic)\n' + drafts[0]
                      + '\nEDITORIAL DRAFT (synthetic)\n' + drafts[1]
                      + '\nsignals (mechanical only; no winner)\n'
                      + json.dumps(asdict(report), indent=2))
    except Exception:
        drafts.clear()
        print('Synthetic comparison failed; no drafts returned.', file=sys.stderr)
        return 1
    drafts.clear()
    print(output)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
