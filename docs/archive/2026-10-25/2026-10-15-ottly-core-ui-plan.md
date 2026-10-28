# Ottly Core UI Implementation Plan

> **For agentic workers:** Execute these tasks inline in order. Steps use checkbox syntax for tracking.

**Goal:** Improve the login, level map, coding lesson, and AI chat experience while preserving the existing otter art and API behavior.

**Architecture:** Keep the current React routes and page components. Add semantic page markup and a small set of shared CSS tokens and responsive rules in the existing stylesheet; do not add UI dependencies or change backend contracts.

**Tech Stack:** React 18, React Router 6, Vite 5, Bootstrap 5, CSS.

## Global Constraints

- Preserve current otter image assets and the existing login, level, code submission, and chat API calls.
- Change only `AIGC_Python_learning-local_qwen2_1.5B/frontend` and this design/plan documentation.
- Keep the user's existing backend edits untouched.
- Respect `prefers-reduced-motion` and keep controls keyboard accessible.

---

### Task 1: Shared navigation and visual foundation

**Files:** `frontend/src/components/Layout.jsx`, `frontend/src/styles/index.css`

**Interfaces:** Existing React Router `<Outlet context={{ userId }} />`, `/app/*` links, and logout token removal remain intact.

- [x] Replace generic sidebar heading with an Ottly brand block using the existing sea otter image. Use `NavLink` so the active route receives `aria-current="page"` and an active class. Keep all four existing destinations.
- [x] Add restrained CSS tokens for sea blue, ink, pale backgrounds, borders and focus rings. Give desktop navigation a persistent sidebar and narrow screens a readable horizontal navigation; links should remain at least 40px high.
- [x] Inspect `/app/levels` at desktop and 375px width; verify no navigation link is hidden behind the logout control and tab order is logical.

### Task 2: Login page

**Files:** `frontend/src/pages/Auth.jsx`, `frontend/src/styles/index.css`

**Interfaces:** Keep existing `handleLogin`, `handleRegister`, `validateForm`, status messages, token storage and navigation.

- [x] Replace large inline layout rules with `auth-page`, `auth-welcome`, and `auth-card` classes. Desktop places a sea otter welcome panel beside the form; mobile puts a compact welcome above the form and hides the large otter art. Continue using the existing `loginhaita`, cloud and star assets.
- [x] Add local `showPassword` state and a `type="button"` toggle with `aria-pressed`; bind both password fields to `showPassword ? 'text' : 'password'`. Keep autocomplete and validation attributes.
- [x] Disable submit buttons while `loading` and show their in-progress labels. Check tab switching, password visibility and form focus in the browser.

### Task 3: Responsive level map

**Files:** `frontend/src/pages/LevelSelection.jsx`, `frontend/src/styles/index.css`

**Interfaces:** Keep `getLevels(token)`, status-driven lock rules and `/app/levels/:id` navigation.

- [x] Derive completed count and the first published nonlocked level from `levels` for a compact progress header and continue button. If no level is enterable, omit that button instead of inventing progress.
- [x] Replace absolute 340px-wide level positions and SVG connector with a responsive ordered map. Render each level as a native button with a visible status label; disabled locked levels cannot navigate. CSS creates the connecting path and the staggered desktop rhythm without fixed pixel coordinates.
- [x] Turn the sea otter AI entry into a native button with a clear label. Confirm API errors and loading text are still visible; inspect the map at desktop and 375px.

### Task 4: Coding workbench

**Files:** `frontend/src/components/CodeEditor.jsx`, `frontend/src/pages/Level1.jsx`, `frontend/src/styles/index.css`

**Interfaces:** Keep `runCode`, `submitCode`, draft persistence, hint flow, success callbacks and editor input behavior unchanged.

- [x] Use CSS grid on `level-detail-card`: title/task pane beside editor on wide screens, stacked in document order on narrow screens. Keep code, output, actions and submission feedback in the editor pane.
- [x] Give the existing run and submit buttons visually distinct secondary/primary treatments and minimum touch size; style the Level 1 back button through a class shared with Level 2.
- [x] Change the clickable otter image to a button that opens `/app/ai-chat`, with image alt text treated as decoration inside the labeled control. Inspect code editor, input, output and feedback at desktop and mobile widths.

### Task 5: AI chat and final verification

**Files:** `frontend/src/pages/AIchat.jsx`, `frontend/src/styles/index.css`

**Interfaces:** Keep session fetch, send request, message history, deletion and pagination handlers unchanged.

- [x] Use button tabs with `aria-selected` for chat and history. Add stable classes to the chat shell, message rows and composer for consistent spacing and responsive sizing.
- [x] In a new conversation, keep the sea otter greeting and show three example prompt buttons. Clicking a prompt calls `setQuestion(prompt)` and focuses the input; it must not call `sendMessage`.
- [x] Keep the composer visible above the mobile viewport bottom and provide visible focus/disabled states. Honor `prefers-reduced-motion` for decorative animation.
- [x] Run `node --test tests/submission-flow.test.cjs tests/code-draft.test.cjs` and a Vite build to a fresh output directory from `frontend`. Inspect auth and authenticated pages in the browser at desktop and 375px. Review `git diff` to confirm no backend file changed during this work.
