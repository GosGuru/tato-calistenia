# RAG guidance window

## Objective
Replace the hardcoded two-item ceiling on retrieved editorial guidance with one bounded,
single-source constant, so the retrieval window can grow without a code change while
current behavior stays identical.

## Scope
Only the guidance-count ceiling and its four enforcing layers. The default stays 2, so no
response changes today. Nothing changes in `MAX_CRITERIA`, `MAX_BYTES`, rule loading,
retrieval statuses, provider selection, embedding model, card schema or SQL.

The normative files under `.agents/skills/tato-calistenia/` are explicitly out of scope.

Recorded but NOT fixed here:
- The card schema allows 2000 characters per text field while the embedder caps the whole
  concatenated passage at 512 tokens. A card can therefore be approved in Postgres that can
  never be embedded.
- No harness can currently measure a multi-card RAG run: `raw_evaluation.py` rejects any
  packet with `guidance != ()`, and the only existing measure (`guidance_trigrams`) counts
  lexical overlap, which inverts the signal for a voice-carrying design.

## Acceptance criteria
- One authoritative ceiling. No literal `2` remains at any guidance-count enforcement point.
- `MAX_GUIDANCE` (8) and `DEFAULT_GUIDANCE` (2) are defined once and imported by the three
  Python layers. No import cycle is introduced.
- Default behavior is unchanged: a connected library returning two criteria still yields
  `status: supplied, count: 2`, and the request still asks the library for the same rows.
- Values above the ceiling are still rejected at every layer, including the packet.
- The client envelope accepts 1..8 and still rejects anything above 8, plus zero, negatives,
  and non-integers.
- The frontend test pins literal bounds (8 accepted, 9 rejected) rather than importing the
  constant, so the contract is verified independently.
- Existing focused tests pass. New tests cover the widened bound and the retained rejection.

## Tasks and progress
- [ ] Define `MAX_GUIDANCE`/`DEFAULT_GUIDANCE` once and import them in the three Python layers.
- [ ] Widen the packet bound in `raw_history.py`.
- [ ] Widen the ranking bound in `editorial_library.py` and use the named default.
- [ ] Use the named default at the call site in `rag_service.py`.
- [ ] Widen the client envelope in `RawDM.jsx` and repair the test asserting `count: 3` rejected.
- [ ] Run focused Python tests and the full frontend suite.

## Evidence
Pending.

## Next action
Pending.
