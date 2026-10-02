# Voice evaluation harness

## Objective
Build a paired-run harness that can measure whether retrieved RAG guidance changes a DM
draft toward Tato's voice, replacing the existing `guidance_trigrams` measure which counts
lexical overlap with the card and therefore inverts the signal for a voice-carrying design.

## Scope
New, self-contained modules under `tools/editorial_rag/`. Pure logic plus a synthetic case
bank. No live model calls in this slice; the runner stays injectable so a later slice can
drive it with the existing `create_runner` / `ApiSessionRunner`.

Explicitly out of scope:
- Editing `raw_evaluation.py` or `evaluation/inputs.json` / `expectations.json`. The offline
  no-inference bank must keep its current contract intact.
- Any LLM-as-judge. The project rejects this (`evaluation/README.md`: "sin juez LLM";
  `casos-calibracion.md`: "No hay integración automática de proveedor ni evaluador semántico").
- Real chats, real names, or any private data. Every case is fictional and sanitized
  (`AGENTS.md` privacy rule).
- Changing the normative files under `.agents/skills/tato-calistenia/`.

## Design constraints (grounded in the repo, do not invent metrics)
Every signal must trace to an existing rule:
- `mirror` — `voz-escrita-tato.md` "Control final de voz": "usa palabras del lead".
- `skeleton_reuse` — same section: "no podría reconstruirse reemplazando solamente el nombre
  del lead y su objetivo".
- `repetition` — same section: "no repite una apertura, puente o forma de pregunta usada
  recientemente".
- `structural_fails` — `casos-calibracion.md` "Hard fails": opening punctuation (`¿` `¡`),
  colon in prose outside the approved Cal.com URL, visible price (`USD`, `$`, `300`), more
  than one question mark. Plus `emoji` and single quotes, both from `voz-escrita-tato.md`
  "No usar emojis ni comillas simples en DMs"; those two are not in the "Hard fails" list.

Structural detection is deterministic and must NOT be presented as a semantic verdict.
Diagnosis, pressure, repeated confirmed data and premature call are SEMANTIC and belong to
the human rubric, not to the signal layer. Name that boundary explicitly in the module docstring.

## Acceptance criteria
- A pure signal module with no I/O and no inference, covering the four signals above.
- `mirror` measures overlap between the DRAFT and the LEAD's words, not the card's text.
- A case bank of 6 fictional, sanitized cases, each tagged with the voice failure pattern it
  reproduces: emotional/effort opening, deep personal opening, terse lead, informal register,
  re-entry after days, specific doubt. No real names and no verbatim private text.
- A paired comparison function that takes one case plus a baseline output and a guided output
  and returns signals for both plus a delta. Both outputs must pass `parse_raw_result` first.
- A report builder that is JSON-serializable and leaves an explicit rubric slot for a human
  scorer: `fidelidad`, `fase`, `naturalidad`, `posicionamiento`, `seguridad` (0-2 each) plus
  the `intencion` semantic gate. The report must never emit a pass/fail verdict of its own.
- Tests for the signals, the bank, the comparison and the report. Include a test proving
  `mirror` scores higher when the draft reuses the lead's own words than when it uses a
  generic opening, and a test proving `skeleton_reuse` flags two drafts that differ only by
  the lead's name and objective.
- `ruff` clean on the touched files. Full Python suite still passes.

## Tasks and progress
- [x] Signal module with the four grounded signals and the structural/semantic boundary.
- [x] Synthetic case bank of six tagged voice-failure cases.
- [x] Paired comparison plus JSON-serializable report with a human rubric slot.
- [x] Tests including the mirror and skeleton counterexamples.
- [x] Run focused tests, `ruff`, and the full Python suite.

## Evidence
Six new files under `tools/editorial_rag/`: `voice_signals.py`, `voice_eval.py`,
`evaluation/voice_cases.json`, `test_voice_signals.py`, `test_voice_eval.py` and `conftest.py`.
Nothing pre-existing was edited except `test_voice_eval.py`'s mirrored `intencion` expectation,
which moved in lockstep with the restored source text.

- `C:/Python314/python.exe -m pytest tools/editorial_rag -q`: **272 passed**, 239 subtests,
  0 failed. Baseline before the harness was 233, so the harness added 39 tests and broke none.
- `ruff` clean on all five Python files.
- `conftest.py` replaced the hand-rolled pytest invocation; `python -m pytest tools/editorial_rag`
  now works directly. The deselect scope is exactly `test_api_runner.py::test_provider_connection`,
  an imported production helper, so no real test is dropped.

Independent verification (read-only, separate agent) confirmed:
- **Privacy clean.** No real names and no verbatim fragment of the motivating conversation.
  The `emotional_effort_opening` case is thematically close but independently written, which is
  the sanctioned "patrón generalizable" — worth one human eyeball.
- **`mirror` measures the LEAD's words**, not the card's, at `voice_signals.py:100-112` with the
  lead as reference set. This replaces `prototype.guidance_trigrams`, which overlapped the draft
  with card text and therefore inverted the signal.
- **No live model call and no LLM judge.** AST guard plus a runtime socket/subprocess backstop.
- **No verdict in the report.** Rubric fields are `None`; `RUBRIC_DOCS` is verbatim from
  `casos-calibracion.md` "Rúbrica".

The two mandatory counterexamples were strengthened and confirmed by deliberate sabotage:
- Breaking `_CAPITALIZED_RE` makes `test_capitalized_names_are_masked_before_comparison` fail
  (`0.923 not greater than 0.938`) while the four pre-existing skeleton tests keep passing —
  which proved the old tests never exercised masking at all.
- Pointing `mirror` at a card-like argument makes the strengthened counterexample fail
  (`0.0 not greater than 0.0`) and also breaks `test_mirror_one_when_every_token_comes_from_the_lead`.

Known limitations, documented in the module docstring rather than papered over:
- `skeleton_reuse` only masks capitalized names, so lowercase names are compared as ordinary
  words. Correct for the real use case, where names are capitalized.
- `mirror` is inflated by function words in very short drafts.
- More than one `?` also flags a legitimate re-entry greeting plus its closing question; that
  exception is semantic and named in the boundary note.

## Next action
Task 5: create the app's own lean prompt pack so the 27:1 rules-to-voice ratio can actually
invert. Task 6 (voice cards from Tato's interview) stays blocked until Tato finishes the
Claude session. Task 7 (card size vs the 512-token embedder ceiling) is a latent defect that
must be resolved before any card is seeded.
