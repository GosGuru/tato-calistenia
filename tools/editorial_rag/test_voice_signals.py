"""Signal tests on synthetic strings only; no I/O, no inference and no model calls."""
import difflib
import unittest

from .voice_signals import (
    RepetitionSignals,
    mirror,
    repetition,
    skeleton_reuse,
    structural_fails,
    tokens,
)

LEAD = ('llego al quinto intento de dominada y me quedo colgado sin poder subir. '
        'entreno tres veces por semana con banda')


class MirrorTests(unittest.TestCase):
    def test_reusing_lead_words_scores_higher_than_generic_opening(self):
        # MANDATORY counterexample: both drafts are built here, only one borrows lead words.
        reusing = ('tres veces por semana con banda no alcanza para subir la dominada. '
                   'contáme cómo son tus intentos')
        generic = 'hola, cómo estás? te quería consultar una cosa sobre tu entrenamiento'
        self.assertGreater(mirror(reusing, LEAD), mirror(generic, LEAD))
        # The second argument is the LEAD's text and is used as such: the value is pinned
        # against this known lead vocabulary (8 of the draft's 17 distinct tokens).
        self.assertEqual(mirror(reusing, LEAD), 0.471)
        # A card-like second argument with entirely different vocabulary changes the result
        # to zero, so the second argument cannot be ignored or read as card text.
        card = 'ficha técnica progresión asistida y control del esfuerzo'
        self.assertEqual(mirror(reusing, card), 0.0)
        self.assertLess(mirror(reusing, card), mirror(reusing, LEAD))

    def test_mirror_zero_without_lead_vocabulary(self):
        self.assertEqual(mirror('xylofono quetzal?', LEAD), 0.0)

    def test_mirror_one_when_every_token_comes_from_the_lead(self):
        self.assertEqual(mirror('dominada con banda', LEAD), 1.0)

    def test_mirror_rejects_empty_text(self):
        with self.assertRaises(ValueError):
            mirror('', LEAD)
        with self.assertRaises(ValueError):
            mirror('dominada?', '')


class SkeletonReuseTests(unittest.TestCase):
    def test_flags_drafts_that_differ_only_by_name_and_objective(self):
        # MANDATORY counterexample: both drafts are built here.
        first = ('maría, para "subir la dominada completa" armemos una forma de practicarla '
                 'que te ordene la semana?')
        second = ('julio, para "recuperar el equilibrio sentándome" armemos una forma de '
                  'practicarla que te ordene la semana?')
        self.assertGreater(skeleton_reuse(first, second), 0.9)

    def test_capitalized_names_are_masked_before_comparison(self):
        # MANDATORY counterexample: the drafts differ only in their capitalized names, so
        # the masking must raise the similarity above the unmasked token comparison.
        first = ('María, para "subir la dominada completa" armemos una forma de practicarla '
                 'que te ordene la semana?')
        second = ('Julio, para "subir la dominada completa" armemos una forma de practicarla '
                  'que te ordene la semana?')
        unmasked = round(difflib.SequenceMatcher(None, tokens(first), tokens(second)).ratio(), 3)
        self.assertGreater(skeleton_reuse(first, second), unmasked)
        self.assertEqual(skeleton_reuse(first, second), 1.0)

    def test_scores_lower_when_structure_differs(self):
        first = ('maría, para "subir la dominada completa" armemos una forma de practicarla '
                 'que te ordene la semana?')
        other = 'contáme qué cambiaste en tu práctica desde la última vez que hablamos'
        self.assertLess(skeleton_reuse(first, other), 0.6)

    def test_masks_digits_between_otherwise_identical_drafts(self):
        self.assertGreater(skeleton_reuse('entrenás 3 veces por semana?',
                                          'entrenás 8 veces por semana?'), 0.9)

    def test_skeleton_reuse_rejects_empty_text(self):
        with self.assertRaises(ValueError):
            skeleton_reuse('', 'dominada?')


class RepetitionTests(unittest.TestCase):
    EARLIER = ('cómo viene tu práctica?', 'para la dominada, probemos algo más estable?')

    def test_flags_reused_opening_and_question_shape(self):
        signals = repetition('cómo viene tu práctica esta semana?', self.EARLIER)
        self.assertIsInstance(signals, RepetitionSignals)
        self.assertTrue(signals.opening_reused)
        self.assertTrue(signals.question_reused)

    def test_does_not_flag_a_fresh_shape(self):
        signals = repetition('contáme qué cambiaste en la banda?', self.EARLIER)
        self.assertFalse(signals.opening_reused)
        self.assertFalse(signals.question_reused)
        self.assertEqual(signals.shared_trigrams, 0)

    def test_counts_phrase_reuse_as_bridge_trigrams(self):
        signals = repetition('lo pensamos y probemos algo más estable para tu dominada?',
                             self.EARLIER)
        self.assertGreaterEqual(signals.shared_trigrams, 1)

    def test_repetition_rejects_bad_input(self):
        with self.assertRaises(ValueError):
            repetition('', self.EARLIER)
        with self.assertRaises(ValueError):
            repetition('dominada?', ['ok?', 3])


class StructuralFailsTests(unittest.TestCase):
    def test_detects_opening_punctuation(self):
        # MANDATORY counterexample: both opening signs must be detected.
        self.assertTrue(structural_fails('¿hola, cómo estás?')['opening_punctuation'])
        self.assertTrue(structural_fails('¡dale, vamos!')['opening_punctuation'])
        self.assertFalse(structural_fails('hola, cómo estás?')['opening_punctuation'])

    def test_approved_cal_com_url_colon_is_not_flagged_as_prose(self):
        # MANDATORY counterexample: the approved URL keeps its colon.
        draft = ('te dejo el enlace\nhttps://cal.com/tato-ramon/reunion-auditoria\n'
                 'elegí el día que te sirva?')
        self.assertFalse(structural_fails(draft)['colon_in_prose'])

    def test_prose_colon_is_flagged(self):
        self.assertTrue(
            structural_fails('vamos con esto: armamos la próxima práctica?')['colon_in_prose'])

    def test_detects_visible_price(self):
        for draft in ('el valor es usd 300', 'cuesta $300', 'sale 300 por mes'):
            self.assertTrue(structural_fails(draft)['visible_price'], draft)
        self.assertFalse(structural_fails('hace 3000 repeticiones?')['visible_price'])

    def test_detects_more_than_one_question_mark(self):
        self.assertTrue(structural_fails('cómo estás? y tu trabajo?')['multiple_questions'])
        self.assertFalse(structural_fails('cómo estás?')['multiple_questions'])

    def test_detects_emoji(self):
        self.assertTrue(structural_fails('dale 💪 vamos?')['emoji'])
        self.assertFalse(structural_fails('dale, vamos?')['emoji'])

    def test_detects_single_quotes(self):
        # "No usar emojis ni comillas simples en DMs." (voz-escrita-tato.md).
        self.assertTrue(
            structural_fails("armemos 'una forma' de practicarla?")['single_quotes'])
        self.assertFalse(structural_fails('armemos una forma de practicarla?')['single_quotes'])
        # The approved URL carries no quote, so it needs no exemption.
        draft = 'te dejo el enlace\nhttps://cal.com/tato-ramon/reunion-auditoria\nelegí el día?'
        self.assertFalse(structural_fails(draft)['single_quotes'])

    def test_clean_draft_has_no_structural_fails(self):
        self.assertFalse(any(structural_fails('contáme cómo viene tu práctica?').values()))

    def test_structural_fails_rejects_empty_text(self):
        with self.assertRaises(ValueError):
            structural_fails('')


if __name__ == '__main__':
    unittest.main()
