# App prompt pack

## Objective
Create a separate, lean runtime prompt pack for the Railway DM app so the rules-to-voice ratio
can invert, while the seven normative references of the local Pi setter stay untouched.

## Motivation, measured
`load_real_rules()` currently injects 108,801 characters of rules per call and the retrieval
window delivers at most 4,000 characters of guidance. That is a 27.2:1 rules-to-voice ratio,
which explains the observed symptom of a correct, stiff, inhuman draft.

Moving `voz-escrita-tato.md` (16,362) and `biblioteca-tecnica-tato.md` (31,685) out of the
always-on prompt leaves 60,754 characters of base. With eight realistic cards the ratio is
about 5.1:1.

## Scope
New files only. The app gets its own pack and its own loader. The seven skill references and
`load_real_rules()` are not modified, so the offline bank's rule-snapshot hash stays valid.

## Scope boundary — the reason this is not a file move
The two files that move out mix two kinds of content:
- **Invariants**: prohibitions and hard contracts. Punctuation rules, one question, first
  person, no invented price or agenda, no diagnosis, no prescriptions by DM, no video
  requests. These must remain ALWAYS present in the base prompt.
- **Expressiveness and knowledge**: register mirroring, proportional recognition, rhythm,
  connective bridges, how to react to an emotional opening, technique orientation. These are
  what belong in retrievable cards.

Split by type of content, not by file. If an invariant ends up only in a card, a case that
recovers no relevant card regresses. That is unacceptable.

## Acceptance criteria
- A base prompt file containing every safety, format, offer and sequence invariant from the
  seven references. Verified by explicit inventory: each invariant is listed with the source
  file and line range it came from, so nothing is silently dropped.
- A card inventory whose entries follow the `Card` schema in `tools/editorial_rag/prototype.py`
  and `editorial_criteria.CARD_FIELDS`: `card_id`, `provenance_id`, `status`, `sanitized`,
  `phase`, `gate`, `situation`, `last_assistant_move`, `proposed_move`, `positive_voice`,
  `negative_repetition`.
- Each card's combined text must be sized to fit the embedder's 512-token passage ceiling
  (`embedding_node/model_manifest.json` `max_tokens`). Report the character count per card and
  state the conservative bound used. `criterion_passage()` in `editorial_criteria.py` defines
  the concatenated passage that must fit.
- A loader module that reads the app pack WITHOUT touching `load_real_rules` or `RULE_PATHS`.
- A short README in the pack stating what moved where and why, and naming the invariant
  inventory as the safety guarantee.
- Tests that pin the invariant inventory against the source files: if a source line holding a
  listed invariant changes, the test must notice.

## Tasks and progress
- [x] Inventory the invariants from the seven references with source line ranges.
- [x] Write the base prompt containing all of them and nothing expressive.
- [x] Write the card inventory from the expressive and technique content.
- [x] Write the separate loader and the pack README.
- [x] Tests: invariant inventory pinned to sources, loader isolation from `load_real_rules`,
      card schema validity, and per-card size bounds.
- [x] Run focused tests, `ruff`, and the full Python suite.

## Evidence
Six new files under `tools/editorial_rag/`: `app_rules/base.md`, `app_rules/cards.json`,
`app_rules/invariants.md`, `app_rules/README.md`, `app_rules.py`, `test_app_rules.py`.
Nothing pre-existing was edited.

- `C:/Python314/python.exe -m pytest tools/editorial_rag -q`: **282 passed**, 426 subtests,
  0 failed. Baseline before the pack was 272, so the pack added 10 tests and broke none.
- `ruff` clean.
- `load_real_rules()` is byte-identical before and after: 108,813 characters,
  `sha256 f2ab75dcec77efc172ca19be9a883e2b2955cfc7495f1c54e3ef21d66511a4c0`.
  The offline bank's rule-snapshot hash stays valid.
- **63 invariants** captured with source file and line range (format 9, voice contract 12,
  offer/agenda 12, safety/health 10, sequence/conversion 20), plus 12 expressive groups that
  became the 12 cards. `app_rules/invariants.md` is the safety guarantee.
- Base prompt `app_rules/base.md`: 10,966 characters. All 19 critical invariants verified
  present by direct check, including USD 300 staying internal and the Cal.com URL going out
  only after the call is accepted.

### The defect that mattered
The first card draft set every `situation` to an opaque slug such as
`apertura-emocional-importante`. That is wrong: `prototype.Card.__post_init__` validates
`situation` with `_text` (prose) and not `_identifier`, and `prototype.retrieve()` ranks by
lexical overlap of `situation` against the conversation and then does `if not overlap: continue`.
With a slug, **every card would have been silently unretrievable**. All 12 `situation` values
were rewritten to the `Aplica cuando ... . No aplica cuando ... .` convention used by the
approved cards in `synthetic_compare.py`.

Confirmed by deliberate sabotage: reverting one `situation` to a slug makes
`test_card_situations_are_descriptive_prose` fail with `AssertionError: ' ' not found in
'apertura-emocional-importante'`. The regression is now pinned.

### Measured ratio
Recomputed from the real pack contents, not assumed:

| Window | Rules : voice |
|---|---|
| Before the pack (108,801 rules vs 4,000 ceiling) | 27.2 : 1 |
| Pack + 2 cards (`DEFAULT_GUIDANCE`) | 6.2 : 1 |
| Pack + 8 cards (`MAX_GUIDANCE`) | **1.5 : 1** |

12 card passages, average 887 characters, maximum 977 — all under the 1,200-character
conservative bound chosen because the 512-token embedder ceiling cannot be verified without
running the tokenizer.

### Known limitations
- Token counts were not measured; the character bound is a conservative proxy. Task 7 is the
  real alignment of the card size ceiling with the embedder.
- The `sentido-personal` gate has no card yet.
- `base.md` spells one conversion gate with a hyphen in its table; corrected to the underscore
  used by `motor-agentico.md` and by the cards.

## Next action
Task 6 (voice cards distilled from Tato's interview) stays blocked until Tato finishes the
Claude session. Task 7 (card size vs the 512-token embedder ceiling) is a latent defect that
must be resolved before any card is seeded. Task 8: rebuild `web/dist` so the widened guidance
ceiling reaches the served bundle.
