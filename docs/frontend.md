# Frontend

## Overview

The MedLens frontend is a React and TypeScript single-page application built with Vite. This issue establishes the application's infrastructure only: project tooling, folder structure, routing, layout, the API client, and an authentication foundation. No product features (login, registration, upload, dashboard data, AI analysis) are implemented yet; each of those is deferred to a later issue and currently renders as a placeholder page.

---

## Technology Stack

- React
- TypeScript (`strict` mode, plus `noUncheckedIndexedAccess` and `noImplicitOverride`)
- Vite
- React Router (`react-router-dom`, declarative `<BrowserRouter>`/`<Routes>`, not the data-router/loader API)
- Axios, for backend HTTP requests
- Tailwind CSS (v4, via `@tailwindcss/vite`)
- ESLint (flat config, `typescript-eslint`) and Prettier

---

## Folder Structure

```text
frontend/src/
    api/            Backend communication (Axios client, request/response handling)
    assets/         Static assets (images, icons)
    components/
        common/     Shared, reusable UI components
        layout/     Layout-specific components (e.g. top navigation)
    contexts/       React Context definitions and providers
    hooks/          Shared custom hooks
    layouts/        Route-level layout components (wrap groups of pages)
    lib/            Small framework-adjacent utilities (e.g. environment config)
    pages/          Route-level page components
    styles/         Global stylesheet
    types/          Shared TypeScript types, including frontend representations of backend response models
    utils/          General-purpose utility functions
```

`api/` is the single location for backend communication. A separate `services/` folder was deliberately omitted, since it would only duplicate `api/`'s purpose and create ambiguity about which one new code should use.

---

## Routing

Routing is configured in `src/App.tsx` using `react-router-dom`.

| Path | Page | Layout | Protected |
|---|---|---|---|
| `/login` | `LoginPage` | none | no |
| `/register` | `RegisterPage` | none | no |
| `/dashboard` | `DashboardPage` | `AppLayout` | yes |
| `/analyses/:id` | `AnalysisDetailPage` | `AppLayout` | yes |
| `/upload` | `UploadPage` | `AppLayout` | yes |
| `/` | redirects to `/dashboard` | | |
| `*` | `NotFoundPage` | none | no |

Login and registration are intentionally rendered outside `AppLayout`, since an unauthenticated user has no dashboard or upload links to navigate to. Every route currently renders a placeholder; no page contains real data-fetching or business logic yet.

Protected routes are wrapped in `ProtectedRoute` (`src/components/common/ProtectedRoute.tsx`), which reads `useAuth()` and redirects to `/login` when there is no authenticated user. Since login is not implemented yet, there is currently no way to reach a protected route as an authenticated user; this only establishes the structure a future issue will rely on.

---

## Layout

`AppLayout` (`src/layouts/AppLayout.tsx`) is the shared application shell for authenticated pages: a top navigation bar (`src/components/layout/TopNav.tsx`) plus a responsive, max-width content area that renders the matched child route via `<Outlet />`.

`TopNav` links to Dashboard and Upload, and shows either a "Log in" link or a "Log out" button depending on `useAuth()`'s `user` state.

---

## API Layer

`src/api/client.ts` exports a single configured Axios instance (`apiClient`), used for all backend requests.

- The base URL comes from `env.apiBaseUrl` (see Environment Variables below); it is never hardcoded elsewhere in the codebase.
- A response interceptor normalizes any failed request into a single `ApiError` shape (`{ status, message }`), collapsing both FastAPI's plain-string `detail` and its list-of-field-errors `detail` (returned on `422` validation failures) into one readable message.
- No authentication header injection exists yet. It is deferred until login is implemented, since there is no token to attach and adding the interceptor now would just be dead code. When login is implemented, the interceptor will read the current token from `AuthContext` (or wherever it ends up being persisted) and attach it to outgoing requests.

`src/types/api.ts` is the initial home for frontend representations of backend response models (starting with `User`), added to incrementally as each backend resource is wired up on the frontend.

---

## Authentication Foundation

- `AuthContext` (`src/contexts/AuthContext.ts`) defines the context and its value shape (`user`, `isLoading`, `login`, `logout`).
- `AuthProvider` (`src/contexts/AuthProvider.tsx`) holds this state in memory via `useState`. It does not call the backend, restore a session, or persist a token anywhere; `login()` simply sets the in-memory user.
- `useAuth()` (`src/hooks/useAuth.ts`) reads the context and throws if used outside `AuthProvider`.
- `ProtectedRoute` (`src/components/common/ProtectedRoute.tsx`) redirects to `/login` when `user` is `null`.

The context and provider are defined in separate files (`AuthContext.ts` / `AuthProvider.tsx`) rather than one, so that `AuthProvider`'s file only exports a component; a file that exports both a component and a plain object (like the earlier combined version) trips React Fast Refresh's `only-export-components` lint rule.

Real login and registration requests, token persistence, and session restoration are left to the issues that implement those flows.

---

## Form State Management

`useAuthForm` (`src/hooks/useAuthForm.ts`) is a small, shared hook used by both `LoginPage` and `SignupPage`. It owns only what was genuinely duplicated between the two: field values, field/form-level error state, `isSubmitting`, the generic input change handler, and the submit-guard/loading skeleton (`preventDefault`, block a second submit while one is in flight, toggle `isSubmitting` around an async action). It deliberately does not own validation rules or error interpretation: each page still supplies its own `validate` function and its own `onSubmit` callback, which is what keeps Signup's field-specific `409` handling and Login's deliberately-never-field-specific `401` handling fully separate and unaffected by the extraction. This is intentionally scoped to these two forms, not a general-purpose form framework.

---

## Dashboard

`DashboardPage` (`src/pages/DashboardPage.tsx`) is kept to page composition only: a header with the primary "Start new analysis" action, and a "Recent analyses" section that renders one of four states. All data-fetching lives in `useRecentAnalyses` (`src/hooks/useRecentAnalyses.ts`), which calls `listRecentAnalyses()` (`src/api/analyses.ts`, `GET /ai/analyses`) and exposes `{ analyses, isLoading, error, retry }`; the page never calls the API layer directly.

`src/components/dashboard/`:

- `RecentAnalysisCard`: one analysis, with a status badge (label text, never color alone), created/completed timestamps, the AI summary text, document count, and finding counts via `SummaryStat`, provider/model if present. The whole card is a single `Link` to `analysisDetailPath(analysis.id)`, with an explicit `aria-label` describing the date and status, since a screen reader would otherwise read every nested stat as part of the link's name.
- `RecentAnalysesList`: a semantic `<ul>` of cards.
- `SummaryStat`: a single `<dt>`/`<dd>` label-value pair (used inside a `<dl>`).
- `DashboardEmptyState`: explains what MedLens does and links to Upload, shown when the user has no analyses yet.
- `DashboardErrorState`: `role="alert"`, the error message, and a retry button, shown when the fetch fails.

Authentication loading (session restore) and dashboard loading (fetching analyses) are two separate, sequential states. `ProtectedRoute` already renders `LoadingSpinner` and blocks rendering until `AuthContext` confirms a session, so `DashboardPage` never has to check auth itself; its own loading state only ever covers the analyses fetch.

`GET /ai/analyses` did not exist before this feature; it was added as the smallest secure addition needed, documented in `docs/api.md`. It returns each analysis's own `document_count` (computed from the existing `clinical_documents` relationship) alongside fields the API already exposed elsewhere (status, timestamps, finding counts, provider/model, summary); nothing was invented that the data model didn't already support.

---

## Upload

`UploadPage` (`src/pages/UploadPage.tsx`) lets a user supply one or more clinical notes, either as files or pasted text, then creates an analysis from all of them. No new backend endpoints were needed here: `POST /clinical-documents` (pasted text), `/clinical-documents/upload-txt`, `/clinical-documents/upload-pdf` (files), and `POST /ai/summarize` (create the analysis) all already existed. `useCreateAnalysis` (`src/hooks/useCreateAnalysis.ts`) runs that multi-request sequence (upload every file, create every pasted note as a document, then summarize all of them) and returns the new analysis's id; `UploadPage` navigates to `analysisDetailPath(analysisId)` on success, reusing the same route `RecentAnalysisCard` links to.

`src/components/upload/`:

- `FileDropzone`: a `role="button"` drop target that is also click-to-open and keyboard-operable (Enter/Space), since drag-and-drop alone would exclude keyboard users. The actual `<input type="file">` is visually and semantically hidden (`sr-only`, `aria-hidden`, `tabIndex={-1}`) since the outer element is the one interactive control a screen reader or keyboard user sees.
- `UploadedFileList`: name, size, a per-file `DocumentTypeSelect`, and a remove button, one row per selected file.
- `ManualNoteEditor`: the "add a new note" form (optional title, required text, a `DocumentTypeSelect` defaulting to Visit note); clears itself after each add.
- `NoteCard`: a saved note, with in-place edit (including its document type) and remove.
- `DocumentTypeSelect`: a plain labeled `<select>` shared by `UploadedFileList`, `ManualNoteEditor`, and `NoteCard`'s edit mode, over the fixed vocabulary in `DOCUMENT_TYPES` (`api/clinicalDocuments.ts`): Visit note, Progress note, Discharge summary, Medication list, Medication reconciliation form. The backend's `document_type` column has no enum (plain `str`), but this is the same fixed set the reconciliation engine and product docs already use (`medication_list`/`medication_reconciliation_form` specifically get special treatment there); the user always chooses, since automatic classification is out of scope. Every file and note is keyed by a locally generated numeric id, not array index, since it's the only way per-item state (`NoteCard`'s edit mode, and the upload-retry cache below) can't end up attached to the wrong item after a removal shifts array positions.
- `UploadEmptyState`: a plain hint shown when nothing has been added yet; unlike `DashboardEmptyState` this isn't a full-section replacement, since the upload/paste controls themselves stay visible either way.

Selected files are validated against the backend's actual supported types (`.txt`/`text/plain`, `.pdf`/`application/pdf`, mirrored exactly from `app/api/routes/clinical_documents.py`) and de-duplicated by name+size; no file size limit is enforced, since the backend does not define one either. A pasted note's title is genuinely optional in the UI, but the backend requires a non-empty title, so an untitled note is given a generated fallback (`Note 1`, `Note 2`, ...) at submission time.

### Retrying a partially failed submission

`useCreateAnalysis` caches each item's resulting document id (`fileItemKey(id)`/`noteItemKey(id)` to a `Map`, held in a ref) as soon as it uploads successfully. If a later item then fails, calling `submit()` again with the same queue skips re-uploading whatever already succeeded and only retries what didn't, rather than creating duplicate ClinicalDocument rows. The cache lives inside the hook, not in `UploadPage`'s own state, since nothing outside a submission attempt needs to read it; `UploadPage` only ever calls `invalidateItem(key)`, and only when the user edits a note's text/title/document type or changes a file's document type (a cached id would otherwise silently point at now-stale content) or removes an item outright. The cache is also cleared automatically the moment an analysis is actually created, since any submission after that is a new attempt, not a retry. `failedItemLabel` (the failing file's name, or the note's title/fallback) is shown alongside the error message so a multi-item failure is attributable to a specific item, not just "something failed."

---

## Shared Components

`src/components/common/`: `Button`, `Input`, `Card`, `PageHeader`, `LoadingSpinner`, `ProtectedRoute`, `PublicOnlyRoute`.

These are intentionally minimal, plain-props components with no variant system (no `variant`/`size` enums, no `class-variance-authority` or similar). Introducing a design system is left until there's a real, recurring need for one.

---

## Styling

Tailwind CSS v4 is used throughout, configured via the `@tailwindcss/vite` plugin (no separate PostCSS config file needed). Global styles live in `src/styles/globals.css`, which imports Tailwind and sets a small number of base styles (body background/text color, a consistent `:focus-visible` outline).

The layout (`AppLayout`, `TopNav`) uses a max-width, responsive container that works down to tablet widths; no attempt has been made to optimize for small mobile screens yet, since the issue only requires desktop and tablet support.

---

## Accessibility

This issue establishes baseline practices, not full WCAG compliance:

- Semantic HTML (`<header>`, `<nav>`, `<main>`, heading elements) instead of generic `<div>`s for structural roles.
- `Input` always renders an associated `<label htmlFor>`, generating an id via `useId()` when one isn't provided.
- Every interactive element (nav links, buttons) is a native `<a>`/`<button>` element, so it's keyboard-reachable and operable by default.
- A visible `:focus-visible` outline is defined once in `globals.css` and reused on custom components, rather than relying on (or removing) each browser's default.
- `LoadingSpinner` uses `role="status"` with visible text, rather than an icon-only spinner, for screen reader support.

---

## State Management

Global state uses React Context (`AuthContext` today). No Redux or other state library is introduced; the issue's scope doesn't yet include state complex enough to justify one.

---

## Environment Variables

| Variable | Required | Purpose |
|---|---|---|
| `VITE_API_BASE_URL` | Yes | Base URL of the backend API |

`VITE_API_BASE_URL` has no fallback and must be set explicitly; `src/lib/env.ts` throws a clear error at startup if it's missing, rather than silently defaulting to `localhost`. Copy `.env.example` to `.env` and adjust it for your environment before running the dev server or building.

---

## Development Setup

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

Other scripts:

```bash
npm run build         # tsc -b && vite build
npm run lint           # eslint .
npm run format         # prettier --write .
npm run format:check   # prettier --check .
npm run test           # vitest run
npm run preview        # preview a production build
```

Tests use Vitest, React Testing Library, and `@testing-library/user-event`, configured directly in `vite.config.ts` (reusing the same `@` alias as the app) rather than a separate Vitest config file. `test.globals` is deliberately left off, matching the rest of the codebase's explicit-import convention; since that also disables React Testing Library's automatic per-test DOM cleanup (it relies on detecting a global `afterEach`), `src/test/setup.ts` wires `afterEach(cleanup)` by hand instead.

The frontend does not yet have a Docker Compose service; it currently runs directly via `npm run dev` against a backend started separately (see the root `README.md` and `infra/docker-compose.yml`).

---

## Known Dependency Advisory

`react-router-dom` currently has one open high-severity advisory ([GHSA-qwww-vcr4-c8h2](https://github.com/advisories/GHSA-qwww-vcr4-c8h2)), affecting React Router's RSC (React Server Components) mode with server actions. This application uses only the classic client-side `<BrowserRouter>`/`<Routes>` API, with no RSC, no server actions, and no data-router loaders, so this advisory's attack surface does not apply here. The installed version was chosen deliberately: every earlier `react-router-dom` release (up to 7.17.0) carries a much larger set of already-patched high-severity advisories (XSS, open redirects, unauthenticated DoS, and an arbitrary-constructor-invocation issue), all fixed by the version in use.

---

## Not Implemented Yet

The following are explicitly out of scope for this issue and left for future issues:

- Real analysis detail display (`AnalysisDetailPage` is still a placeholder; `UploadPage` already navigates to it by id after creating an analysis)
- A Docker Compose service for the frontend
