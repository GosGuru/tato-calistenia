# Conversational draft layout

## Objective
Move the submitted conversation history out of the input and show it as a distinct message above the pending/result response.

## Scope
RAW editorial UI only. Keep one request/one result, existing API payload and privacy boundary, no Instagram send, no persistent chat history. Do not run lint or build per current user preference.

## Acceptance criteria
- On Generate, the exact submitted Unicode history leaves the textarea and appears in a separate, upward-entering message.
- The pending state and final draft or error appear below that message; no fake streaming, stages or delivery claim.
- The history can be restored to edit; long history remains readable without swallowing the composer.
- Enter/IME, connection/Auth, stale response, clipboard and request count guards remain intact.
- Reduced motion disables the transition.

## Tasks and progress
- [x] Inspect current RAW component, CSS, tests and live screenshot.
- [x] Implement submitted-history state and restore/edit path.
- [x] Style message/response hierarchy and restrained animation.
- [x] Update focused tests/docs and run focused tests only.
- [ ] Visually verify the submitted-history motion and long/mobile layouts in the served app.

## Evidence
- Current screenshot shows history still in textarea beneath pending response.
- The original source kept `history` in the textarea during and after `generate()`.
- RAW focused tests: 56/56 passing after the state transition; no lint or build run.
- The browser fixture assertions were adjusted but have not been executed; before the authorized build the server still served older `dist` assets.
- User authorized one build; `npm run build` passed. Fresh localhost tab loads `index-D1fNOLx3.css`; focused input has no inner outline and an outer warm focus ring. The user's populated original tab was not reloaded.

## Next action
Inspect the entry motion, long-history scroll and mobile layout with fictional fixture data only; do not use a real OpenAI call for visual checks.
