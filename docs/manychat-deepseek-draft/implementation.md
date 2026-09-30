# ManyChat + DeepSeek draft implementation

Status: INACTIVE DRAFT. Prepared 2026-09-15. No live sends, API requests, credentials, CRM access, production runtime changes or deployment are authorized by this package. User approved draft construction; activation remains a separate approval. This package is a new adaptation, not a replacement for the operational skill.

## Verified evidence versus proposals

Local operational authority inspected: SKILL.md; motor-agentico.md; voz-escrita-tato.md; operativa-dm.md; objeciones-agenda.md; contexto-maestro.md, under .agents/skills/tato-calistenia/. Maintenance references and technical-library scope were also inspected. Existing modified files were preserved.

Root operator's current UI inspection reports a draft named `TATO · DeepSeek · BORRADOR NO ACTIVAR`, with no trigger or publication. The Actions picker exposes standard categories and an integrations unlock link, but not DeepSeek while disconnected. The account banner states new contacts are not receiving automations because the plan limit has been reached. No API key was entered and no plan upgrade was performed. Those are blockers, not an invitation to bypass limits or enable billing.

The screenshot supplied by the user shows a DeepSeek beta integration account connection. It does NOT prove automatic full-Inbox history, conversational memory, structured output, webhook/export access, output size, concurrency semantics, model choice, retries, multimodal interpretation or send safety. Earlier conversation claims about documented capabilities must be independently verified before configuring a live flow. Do not treat this package as evidence that those capabilities exist.

## Files

- system-prompt.md: portable Spanish response-generation instructions; operator input binding is still required. Metadata/header is not prospect-facing.
- acceptance-cases.json: synthetic scenarios and decision criteria, not copied DMs or model execution results.
- implementation.md: this proposal and release gates.

## Proposed minimal draft path

1. Keep the existing draft unpublished and without an inbound/default-reply trigger. Do not modify current live flows.
2. Have the user connect the DeepSeek key through the authenticated integration field; never paste credentials into chat, files, prompts or reports. Separately resolve the account limit with explicit billing authorization if necessary.
3. Inspect the newly unlocked action: exact inputs, provider/model, token bounds, output field mapping, history support and error behavior. Record observed field names, not assumed ones.
4. Use synthetic test contacts/context only. Bind complete chronological context and the current message exactly once. Do not assume the `last message` includes a multi-message burst or old Inbox history.
5. Map generated content to a DRAFT field or review surface only. There is no verified draft-output mapping yet. If the UI cannot support a no-send trial, test outside the live flow after separate API-test authorization, not by sending to existing leads.
6. Obtain independent semantic scoring for multi-turn cases before any activation request.

## Context design — proposed, not configured fields

The following are logical names, not verified ManyChat built-ins. Separate per-contact storage design requires review; the current Tato runtime expressly forbids automatic CRM/event recording. This draft neither reads nor implements any tracker. A future bot's necessary conversation context must have explicit scope, retention and access controls before real personal data is persisted or sent to DeepSeek.

| Logical input | Purpose |
|---|---|
| contact_key | Stable per-contact routing, never display name alone |
| conversation_revision / inbound_event_id | Detect stale replies and duplicate events |
| history_complete / ordered_messages | Explicit context; sender and order; no shared global history |
| confirmed_facts / supporting_message_refs | Preserve qualifications and uncertainty |
| current_message | New input exactly once, not mixed with trusted system instructions |
| route_status / call_status | Unknown, offered, accepted, declined with evidence |
| booking_evidence | Explicit confirmation source; clicking is not booking |
| human_paused / automation_enabled | Hard application gate checked again before any send |
| followups_sent / rejection_state | Actual verified events, not generated drafts |
| operational_facts | Approved modality/location facts and validity |
| approved_technical_excerpt | Only curated applicable technical rule, if needed |
| candidate_reply | Draft isolated from the send action |

Do not set factual state from a keyword such as "yes" without the preceding question. Do not let generated state overwrite external send or booking evidence. Missing context should stop drafting rather than reconstruct private chats from prohibited databases.

## Separate control channel and handoff

The system prompt emits plain DM text only. It is NOT a JSON-mode specification. No native structured-output or classifier capability is claimed. An eventual controller or human reviewer must produce a separate, non-outbound decision with fields such as `status`, `reason`, `evidence_refs` and `draft_id`. These are a proposed application contract, not strings to send to a lead.

Proposed decisions:

- `review_draft`: context sufficient; show draft to reviewer, still no sends.
- `needs_context`: incomplete or contradictory history, unresolved modality, unsupported media.
- `human_handoff`: technical/personalized request beyond supplied criteria, resource failure, request for a person or automation-disclosure question.
- `safety_handoff`: urgent/out-of-scope need; prioritize human review and appropriate noncommercial guidance. Do not use queue delay as a reason to withhold urgent care guidance.
- `closed`: rejection, minor, explicit impossibility, incompatibility or confirmed reservation; appropriate one-time closing draft only if not already sent. No further automated follow-ups.
- `stop_no_send`: paused, disabled, duplicate/stale event, exhausted follow-ups, unavailable provider, output validation failure or unknown send outcome.

Never put a raw model response directly into a message block without a verified gate. Never rely solely on a sentinel string inside the generated reply: it could leak, be spoofed or fail. If native actions cannot isolate controls from text, keep review manual; an external controller is a possible fallback, not an installed service.

## Required send-safety design before activation

Serialize handling per contact; buffer message bursts; deduplicate events; invalidate an in-flight answer when a newer message or human intervention arrives. Recheck pause, latest revision, channel permission/window and approval immediately before sending. Send one line at a time and verify each bubble. An uncertain send must reconcile visible state, not blindly retry. Cap generated length to verified platform limits and fail closed on truncation or empty/error output. Test loops, simultaneous replies and reopening after closure. No follow-up scheduling has been created.

Current platform messaging-window policies, relevant plan limits and retry behavior have NOT been verified by this package. No numerical limit is assumed. No external controller has been built. An unconditional loop from reply back to collection is not an acceptable substitute for those gates.

## Fidelity gaps / release blockers

1. DeepSeek disconnected; exact beta action parameters and memory behavior unknown.
2. ManyChat account limit banner blocks new-contact automation; do not claim production readiness or resolve via unauthorized upgrade.
3. Full-history assembly and validated no-send output routing unproven.
4. Local references retain online-only wording, while user-provided workspace context includes a Durazno in-person correction. Do not silently expand geography or declare incompatibility. Operator must confirm current facts before activation; no source-of-truth file changed here.
5. Technical patterns are not embedded in full. Prompt requires an operator-selected approved excerpt; technical coverage is partial until tested. No autonomous medical or technical knowledge retrieval is implemented.
6. Privacy, retention, provider disclosure and authorization for processing real lead conversations remain gates. This package uses synthetic data only.
7. No DeepSeek semantic eval, independent scoring, model/version pinning or live end-to-end test has run. Structural file checks are not behavior proof.
8. Prompt-only controls cannot guarantee deterministic behavior. Adversarial content, context loss, errors and human takeover need application-level enforcement.

## Test and release procedure

Use acceptance-cases.json as scenarios, not expected copy. For each, supply the full synthetic history, run the actual configured model after test authorization, save only nonprivate test evidence in an approved location and score decision/voice/safety separately. Repeat multi-turn cases at fixed observed model/settings; test short and long context. All safety, rejection, memory-separation, price and agenda gates must pass consistently; variation in wording is expected. Obtain the user's approval of the finished draft and exact activation scope after blockers are resolved. This draft does not approve activation, publication, billing changes or real-lead sends.
