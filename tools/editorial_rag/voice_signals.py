"""Deterministic voice signals for DM drafts. Pure logic: no I/O, no inference, no verdicts.

Every signal traces to an existing rule; none is invented here.

- ``mirror`` comes from ``voz-escrita-tato.md`` "Control final de voz": "usa palabras del
  lead". It measures lexical overlap between the DRAFT tokens and the LEAD's tokens. It
  deliberately replaces ``prototype.guidance_trigrams``, which overlaps the draft with the
  CARD text and therefore inverts the signal for a voice-carrying design. Tokenization
  matches ``prototype._tokens`` (``re.findall(r"\\w+", text.casefold())``) so counts stay
  comparable with that prototype.
- ``skeleton_reuse`` comes from the same section: "no podría reconstruirse reemplazando
  solamente el nombre del lead y su objetivo". This is a deterministic APPROXIMATION of
  that rule, not the rule itself: both drafts are normalized by masking capitalized words
  (names or emphasis), digit runs and quoted objective phrases, then compared as token
  sequences. It can show that two drafts share a skeleton; it cannot prove the rule, and an
  unquoted objective swap is only masked when capitalized or quoted.
- ``repetition`` comes from the same section: "no repite una apertura, puente o forma de
  pregunta usada recientemente", measured against the earlier assistant messages.
- ``structural_fails`` are deterministic format violations from ``casos-calibracion.md``
  "Hard fails" and the rules of ``voz-escrita-tato.md``. ``emoji`` and ``single_quotes``
  come from ``voz-escrita-tato.md`` "No usar emojis ni comillas simples en DMs."; neither
  is in the ``casos-calibracion.md`` "Hard fails" list.

Structural/semantic boundary
----------------------------

Structural detection is deterministic and must NOT be presented as a semantic verdict.

Detectable here: "signo de apertura" (``¿``, ``¡``); "dos puntos en prosa" outside the
approved ``https://cal.com/tato-ramon/reunion-auditoria`` URL; "precio visible por DM"
(``USD``, ``$`` or a bare ``300``); more than one ``?``, which is a deterministic proxy for
"más de una pregunta sustantiva"; emoji; and "comillas simples" (single quotes), the
last two from ``voz-escrita-tato.md`` "No usar emojis ni comillas simples en DMs.".

NOT detectable here. These hard fails are SEMANTIC and belong to the human rubric
("Rúbrica") and the human hard-fail review: "llamada antes de ruta aceptada" (needs
conversation state); "diagnóstico, prescripción o promesa"; "presión mediante edad,
familia, salud, vergüenza o urgencia falsa"; "repetir un dato confirmado"; "mezclar brief
y DM"; "afirmar reserva sin confirmación". Also semantic: the re-entry social greeting
exception to "más de una pregunta sustantiva", the exceptional closings without a
question, and the ``intencion`` gate. A structural flag asks a human to look; it is never
a pass/fail verdict, and a clean structural result never certifies voice.
"""
import difflib
import re
from dataclasses import dataclass

APPROVED_URL = 'https://cal.com/tato-ramon/reunion-auditoria'

_TOKEN_RE = re.compile(r'\w+')
_QUOTED_RE = re.compile(r'"[^"\n]*"|\'[^\'\n]*\'|«[^»\n]*»|“[^”\n]*”|‘[^’\n]*’')
_CAPITALIZED_RE = re.compile(r'\b[ÁÉÍÓÚÜÑA-Z]\w*')
_DIGITS_RE = re.compile(r'\d+')
_QUESTION_MARK_RE = re.compile(r'\?')
_OPENING_PUNCTUATION_RE = re.compile(r'[¿¡]')
_PRICE_RE = re.compile(r'\busd\b|\$|(?<!\d)300(?!\d)', re.IGNORECASE)
_EMOJI_RE = re.compile(
    '[\U0001F1E6-\U0001F1FF\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F\u200D\u20E3]+')

_MASK_NAME = 'xnom'
_MASK_OBJECTIVE = 'xobj'
_MASK_NUMBER = 'xnum'


@dataclass(frozen=True)
class RepetitionSignals:
    """One field per shape named in "no repite una apertura, puente o forma de pregunta"."""

    opening_reused: bool
    question_reused: bool
    shared_trigrams: int


def _text(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('Expected nonempty text')


def tokens(text: str) -> tuple[str, ...]:
    """Same tokenization as ``prototype._tokens`` so results stay comparable."""
    _text(text)
    return tuple(_TOKEN_RE.findall(text.casefold()))


def _trigrams(text: str) -> set[tuple[str, ...]]:
    word = tokens(text)
    return {word[i:i + 3] for i in range(len(word) - 2)}


def _mask(text: str) -> tuple[str, ...]:
    """Mask names/emphasis, digits and quoted objective phrases, then tokenize.

    Quoted spans are masked first so capitalized words inside an objective phrase do not
    fragment it. Mask placeholders are shared tokens: two drafts that differ only in those
    spans normalize to the same sequence.
    """
    masked = _QUOTED_RE.sub(' ' + _MASK_OBJECTIVE + ' ', text)
    masked = _CAPITALIZED_RE.sub(' ' + _MASK_NAME + ' ', masked)
    masked = _DIGITS_RE.sub(' ' + _MASK_NUMBER + ' ', masked)
    return tuple(_TOKEN_RE.findall(masked.casefold()))


def mirror(draft: str, lead: str) -> float:
    """Share of the draft's distinct tokens that also appear in the lead's words.

    "usa palabras del lead" (Control final de voz). 0.0 means the draft borrows no
    vocabulary from the lead; 1.0 means every distinct draft token appears in the lead's
    messages. Function words inflate short drafts; length and proportionality stay with
    the human rubric.
    """
    _text(draft)
    _text(lead)
    draft_tokens = set(tokens(draft))
    lead_tokens = set(tokens(lead))
    return round(len(draft_tokens & lead_tokens) / len(draft_tokens), 3)


def skeleton_reuse(draft_a: str, draft_b: str) -> float:
    """Token-sequence similarity of two drafts after masking; APPROXIMATION, not the rule.

    Approximates "no podría reconstruirse reemplazando solamente el nombre del lead y su
    objetivo" (Control final de voz). A high value means the two drafts differ only in
    masked spans (capitalized names or emphasis, digits, quoted objective phrases), so one
    could be reconstructed from the other by such a substitution. Deterministic
    (difflib.SequenceMatcher), symmetric, and never a verdict on its own.
    """
    _text(draft_a)
    _text(draft_b)
    return round(difflib.SequenceMatcher(None, _mask(draft_a), _mask(draft_b)).ratio(), 3)


def _question_shapes(text: str) -> tuple[tuple[str, ...], ...]:
    """First three masked tokens of every question span; the deterministic form shape."""
    shapes = []
    for match in _QUESTION_MARK_RE.finditer(text):
        end = match.start()
        begin = max(text.rfind('?', 0, end), text.rfind('\n', 0, end),
                    text.rfind('.', 0, end)) + 1
        shape = _mask(text[begin:end])[:3]
        if shape:
            shapes.append(shape)
    return tuple(shapes)


def repetition(draft: str, earlier) -> RepetitionSignals:
    """Reuse of a recent opening, bridge or question shape against earlier assistant texts.

    "no repite una apertura, puente o forma de pregunta usada recientemente" (Control
    final de voz). Approximations: the opening is the first two tokens (the shape already
    used by ``prototype.Same_opening``); the question form is the first three masked tokens
    of each question; bridge reuse is verbatim phrase reuse counted as shared trigrams,
    matching ``prototype.shared_trigrams``.
    """
    _text(draft)
    if type(earlier) not in (list, tuple) or any(not isinstance(item, str) for item in earlier):
        raise ValueError('Expected a sequence of earlier assistant texts')
    draft_opening = tokens(draft)[:2]
    opening_reused = len(draft_opening) == 2 and any(
        tokens(item)[:2] == draft_opening for item in earlier)
    draft_shapes = {shape for shape in _question_shapes(draft) if shape}
    earlier_shapes = {shape for item in earlier for shape in _question_shapes(item) if shape}
    earlier_grams: set[tuple[str, ...]] = set()
    for item in earlier:
        earlier_grams |= _trigrams(item)
    return RepetitionSignals(opening_reused,
                             bool(draft_shapes & earlier_shapes),
                             len(_trigrams(draft) & earlier_grams))


def structural_fails(draft: str) -> dict[str, bool]:
    """Deterministic format violations; flags for a human to look at, never a verdict.

    Names follow ``casos-calibracion.md`` "Hard fails" and ``voz-escrita-tato.md``:
    ``opening_punctuation`` = "signo de apertura"; ``colon_in_prose`` = "dos puntos en
    prosa" outside the approved Cal.com URL; ``visible_price`` = "precio visible por DM";
    ``multiple_questions`` = more than one ``?`` (proxy for "más de una pregunta
    sustantiva"); ``emoji`` = emoji and ``single_quotes`` = "comillas simples", both from
    ``voz-escrita-tato.md`` "No usar emojis ni comillas simples en DMs." and not from the
    ``casos-calibracion.md`` "Hard fails" list. See the module docstring for the semantic
    hard fails that this function cannot detect.
    """
    _text(draft)
    body = draft.replace(APPROVED_URL, ' ')
    return {
        'opening_punctuation': bool(_OPENING_PUNCTUATION_RE.search(draft)),
        'colon_in_prose': ':' in body,
        'visible_price': bool(_PRICE_RE.search(body)),
        'multiple_questions': draft.count('?') > 1,
        'emoji': bool(_EMOJI_RE.search(draft)),
        'single_quotes': "'" in draft,
    }
