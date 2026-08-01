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
| `/patients` | `PatientsPage` | `AppLayout` | yes |
| `/patients/new` | `NewPatientPage` | `AppLayout` | yes |
| `/patients/:patientId` | `PatientOverviewPage` | `AppLayout` | yes |
| `/patients/:patientId/edit` | `EditPatientPage` | `AppLayout` | yes |
| `/patients/:patientId/medications` | `PatientMedicationsPage` | `AppLayout` | yes |
| `/patients/:patientId/documents` | `PatientDocumentsPage` | `AppLayout` | yes |
| `/patients/:patientId/upload` | `UploadPage` | `AppLayout` | yes |
| `/patients/:patientId/analyses` | `PatientAnalysesPage` | `AppLayout` | yes |
| `/patients/:patientId/analyses/new` | `CreateAnalysisPage` | `AppLayout` | yes |
| `/patients/:patientId/analyses/processing` | `AnalysisProcessingPage` | `AppLayout` | yes |
| `/patients/:patientId/analyses/:analysisId` | `AnalysisDetailPage` | `AppLayout` | yes |
| `/settings` | `SettingsPage` | `ProtectedLayout` | yes |
| `/upload` | redirects to `/patients` (legacy, Sprint 3.5 Issue #130) | | |
| `/analyses/:id` | redirects to `/patients` (legacy, Sprint 3.5 Issue #130) | | |
| `/` | redirects to `/dashboard` | | |
| `*` | `NotFoundPage` | none | no |

Login and registration are intentionally rendered outside `AppLayout`, since an unauthenticated user has no dashboard or upload links to navigate to. Every route currently renders a placeholder; no page contains real data-fetching or business logic yet.

Protected routes are wrapped in `ProtectedRoute` (`src/components/common/ProtectedRoute.tsx`), which reads `useAuth()` and redirects to `/login` when there is no authenticated user. Since login is not implemented yet, there is currently no way to reach a protected route as an authenticated user; this only establishes the structure a future issue will rely on.

---

## Layout

`AppLayout` (`src/layouts/AppLayout.tsx`) is the shared application shell for authenticated pages: a top navigation bar (`src/components/layout/TopNav.tsx`) plus a responsive, max-width content area that renders the matched child route via `<Outlet />`.

`TopNav` links to Dashboard and Patients, and shows either a "Log in" link or a "Log out" button depending on `useAuth()`'s `user` state. There is deliberately no standalone "Medications" or "Upload" link - as of Sprint 3.5 (Issues #129 and #130), medication management, document upload, and analysis history all only exist within a patient's context (see Patients below), never as a global destination.

### Patient breadcrumb navigation

Sprint 3.5, Issue #131: every page nested under a patient (`PatientOverviewPage`, `UploadPage`, `PatientAnalysesPage`, `AnalysisDetailPage`) renders `PatientBreadcrumb` (`src/components/patients/PatientBreadcrumb.tsx`) above its `PageHeader`, so a provider can never lose track of which patient they're viewing or how to get back. It builds a `Patients / {patient name} / ...trail` `<nav aria-label="Breadcrumb">` with an `<ol>` of crumbs; every crumb is a link except the last, which is the current page and is rendered as plain text with `aria-current="page"` rather than a link to itself. Callers pass only the crumbs *after* the patient name (`trail`, e.g. `[{ label: 'Analyses', to: patientAnalysesPath(id) }, { label: 'Analysis #42' }]` for `AnalysisDetailPage`); `PatientOverviewPage` passes no trail at all, since the patient's own name is already the current page there. `PatientMedicationsPage` and `EditPatientPage` were not touched in this issue - they already had an adequate "← Back to {name}" link and weren't part of this issue's explicit page list.

**Issue #158 standardized the Back action this section warned was inconsistent** - up to this point, most patient-nested pages each hand-rolled their own "← Back to {name}" `<Link>` pointing at a single hardcoded destination (and two pages, `PatientMedicationsPage` and `EditPatientPage`, had no breadcrumb at all, and `PatientDocumentsPage` had a breadcrumb but no Back action). Two new shared components replace all of that:

- **`BackButton`** (`src/components/common/BackButton.tsx`) - a single `<button>` rendering "← Back to {label}" (the arrow is `aria-hidden`, so the accessible name is exactly "Back to {label}"). Rather than a static link to one hardcoded destination, it prefers real browser-history back navigation (`navigate(-1)`) so the user lands exactly where they actually came from, whether that's Dashboard, the Patients list, another patient-related workflow, or anywhere else - and falls back to a given logical-parent route (`to`) only when there's no in-app history to return to (a direct link, a bookmark, or a fresh page load). It distinguishes the two cases via `useLocation().key === 'default'`: React Router assigns that exact key only to the initial entry of a history session, which is the closest reliable signal available from script for "did the user arrive here via in-app navigation, or from outside it" - real `window.history` depth isn't reliably readable. This is a generic, non-patient-specific component (`components/common/`, not `components/patients/`), even though every current caller happens to be patient-related.
- **`PatientPageNav`** (`src/components/patients/PatientPageNav.tsx`) - the shared layout combining `PatientBreadcrumb` and `BackButton` into the one navigation block every patient-nested page now renders identically: `<PatientPageNav patient={patient} trail={...} backTo={...} backLabel={...} />`. Bundling both in one component (rather than each page composing `PatientBreadcrumb` plus its own hand-rolled back link, as before) is what actually eliminates the duplicated navigation markup this issue asked to avoid - it's the "shared page header/navigation layout" component the issue described.

Every page nested under a patient now uses `PatientPageNav` with a `backTo` matching its logical parent in the breadcrumb hierarchy:

| Page | `backTo` | `backLabel` |
| --- | --- | --- |
| `PatientOverviewPage` | `ROUTES.patients` | `"Patients"` |
| `EditPatientPage` | `patientDetailPath(id)` | patient's full name |
| `PatientMedicationsPage` | `patientDetailPath(id)` | patient's full name |
| `PatientDocumentsPage` | `patientDetailPath(id)` | patient's full name |
| `PatientAnalysesPage` | `patientDetailPath(id)` | patient's full name |
| `AnalysisDetailPage` | `patientAnalysesPath(id)` | `"analyses"` |
| `UploadPage` | `patientDetailPath(id)` | patient's full name |
| `CreateAnalysisPage` (renamed from `SelectDocumentsPage` in Issue #160) | `patientDetailPath(id)` | patient's full name |

`EditPatientPage` and `PatientMedicationsPage` gained a breadcrumb for the first time in this issue; `PatientDocumentsPage` gained a Back action for the first time (its existing "View Patient" action inside `<nav aria-label="Document actions">` is left as-is - a purposeful action alongside Upload/Create Analysis, not a substitute for the standard top-of-page Back action every other patient page now has).

**Deliberately left out of this issue's scope:**

- **`AnalysisProcessingPage`** keeps its plain `PatientBreadcrumb` with no `BackButton`. This page is a special-cased, transient, auto-submitting page (see Analysis Processing below) with its own explicit recovery links (`FailureCard`'s "Return to Patient Overview" / "Return to Analysis History", and the no-submission state's "Go to Upload") for exactly the situations where leaving the page makes sense; adding a generic Back action here would either duplicate those or invite navigating away mid-submission, neither of which this issue asked for.
- **`NewPatientPage`** (`/patients/new`) has no existing patient yet, so `PatientPageNav`'s `patient`-shaped props don't apply; its bottom-of-form "Cancel" link (a distinct, existing pattern also used by `EditPatientPage`) is unchanged and out of scope.
- **`PatientsPage`** (`/patients`) is the top of this hierarchy - the issue's own breadcrumb example shows "Patients" alone, with nothing above it to add a Back action for.

---

## API Layer

`src/api/client.ts` exports a single configured Axios instance (`apiClient`), used for all backend requests.

- The base URL comes from `env.apiBaseUrl` (see Environment Variables below); it is never hardcoded elsewhere in the codebase.
- A response interceptor normalizes any failed request into a single `ApiError` shape (`{ status, message }`), collapsing both FastAPI's plain-string `detail` and its list-of-field-errors `detail` (returned on `422` validation failures) into one readable message.
- No authentication header injection exists yet. It is deferred until login is implemented, since there is no token to attach and adding the interceptor now would just be dead code. When login is implemented, the interceptor will read the current token from `AuthContext` (or wherever it ends up being persisted) and attach it to outgoing requests.

`src/types/api.ts` is the initial home for frontend representations of backend response models (starting with `User`), added to incrementally as each backend resource is wired up on the frontend.

---

## Error Handling (Issue #50)

A consolidation pass, not a new system - every pattern below already existed somewhere in the app (`ErrorState`, `Input`'s field-error wiring, `useCreateAnalysis`'s upload-retry cache); this made them consistent and applied them everywhere they were missing, rather than inventing something new.

**`toApiError`** (`src/api/client.ts`, now exported for direct testing - see `client.test.ts`) is the single place every backend failure passes through, and the one place worth understanding before anything else: it normalizes FastAPI's plain-string `detail`, list-of-field-errors `detail` (422s), and `{message, row_errors}`-shaped `detail` (the medication CSV importer) into one `ApiError` (`{status, message, detail?}`). As of this issue, it also special-cases the case with **no response at all** - offline, DNS/CORS failure, the backend down, a timeout - which previously fell through to Axios's own `error.message` (literally `"Network Error"` or `"timeout of Xms exceeded"`, developer-facing text that used to leak into every dialog, form, and card in the app verbatim). That case now always returns `"Unable to reach the server. Check your connection and try again."` instead. No other status code is special-cased (a 403 is treated like any other error with a `detail` string) - the backend's own messages are trusted and shown as-is everywhere except this one case where there is no backend message to show.

**Two new shared presentational components**, replacing what was previously duplicated ad hoc as `<p role="alert" className="text-sm text-red-600">{message}</p>` (or, in one case, no `role` at all) across roughly a dozen call sites:

- **`FormError`** (`src/components/common/FormError.tsx`) - `{message, className?, id?}`. The "this action failed" message: a failed login/signup, a failed patient/medication save, a failed delete, a failed upload. Used by `LoginPage`, `SignupPage`, `PatientForm`, `MedicationForm`, `MedicationCard` (both its edit-save and delete errors), `ClinicalDocumentCard`, `RecentAnalysisCard` (its delete error), `ArchivePatientDialog`, `DeleteAnalysisDialog`, `ManualNoteEditor` and `NoteCard` (see Validation below), `UploadPage`, and `CreateAnalysisPage`. The optional `id` exists for the one case that needs `aria-describedby` linkage from another element (see FileDropzone below); `className` exists for the one case that needs extra layout classes (`RecentAnalysisCard`'s delete error, which sits in a flex row next to the Delete button and needs `min-w-0 break-words`).
- **`AnalysisFailureNotice`** (`src/components/analyses/AnalysisFailureNotice.tsx`) - `{message, className?}`. Distinct from `FormError`: this isn't a failed *action*, it's a fact about a persisted record (a completed-but-`failed` `Analysis`'s own `error_message`), so it always renders its own `"Analysis failed: "` label rather than relying on surrounding context to explain what the red text means. Used by `AnalysisDetailPage` (inside its own bordered `Card`) and `RecentAnalysisCard` (inline, no extra wrapper) - previously these were two different hand-rolled paragraphs with different wording and only one of the two had a `role` at all.

**Validation errors** were already handled correctly by `Input` (`aria-invalid`, `aria-describedby` pointing at a `role="alert"` `<p id={errorId}>`) everywhere a page used it. The one gap was `ManualNoteEditor` and `NoteCard`'s edit mode: both silently `disabled` their Add/Save button when the note text was empty, with no message explaining why - the button just didn't do anything. Both were changed to match every other form in the app instead: the button is always enabled, clicking it with empty text shows a `FormError` ("Note text is required.") wired via `aria-invalid`/`aria-describedby` exactly like an `Input` field error, and the button's own action (`handleAdd`/`saveEdit`) is what validates - not a `disabled` prop with no explanation. Typing anything clears the error immediately, matching the rest of the app's "input is preserved and re-validated live, not reset" convention.

**`FileDropzone`** (`src/components/upload/FileDropzone.tsx`) gained an optional `errorId` prop, included in the dropzone's own `aria-describedby`. Previously, an unsupported-file-type error (`useDocumentQueue`'s `fileError`) rendered as a floating `FormError` paragraph elsewhere on the page with no link back to the control that caused it - a screen reader landing on the dropzone had no way to know why the last selection failed, unlike the medication CSV importer's dropzone, which already wired this correctly. `UploadPage` and `CreateAnalysisPage` now pass a fixed id to both the prop and the paragraph's own `id`.

**Retry, and which item failed**: `useCreateAnalysis`'s upload loop already cached each successfully-uploaded item by a stable queue id and skipped re-uploading it on a subsequent `submit()`/`saveDocuments()` call (see "Retrying a partially failed submission" under Upload) - a real, deliberate, already-good pattern. It also already computed `failedItemLabel` (the name of whichever file/note failed) but no page actually displayed it - the error message a user saw never said *which* file or note the failure was about when several were queued. `UploadPage` and `AnalysisProcessingPage` now compose it in: `` `${failedItemLabel}: ${error}` `` when known, falling back to the plain message otherwise.

`useAnalysisPolling` (`src/hooks/useAnalysisPolling.ts`) gained a `retry()` function, following the same `retryCount`-as-effect-dependency pattern every other data-fetching hook in the app already uses. Previously, a single failed status-check request stopped polling permanently with no way to resume short of leaving and re-entering the page - there was no automatic reschedule on error and no manual retry either. `AnalysisProcessingPage`'s `FailureCard` now offers "Try again" for this case too (calling `retryPolling`, which just re-checks status), distinct from its other "Try again" (calling `runSubmission`, which creates a new analysis) - retrying a poll failure must never re-submit, since the original analysis may already exist and be fine.

`FailureCard` (`AnalysisProcessingPage.tsx`) also switched its hand-rolled retry `<button>` (which duplicated `Button`'s own styling) to the shared `Button` component directly, with `Button`'s missing `focus-visible` outline classes added back via `className` at this one call site - a pre-existing gap in `Button` itself (it has no `focus-visible` styles built in, unlike almost every other interactive element in the app, which each add them inline) that's out of scope to fix everywhere `Button` is used, but not worth reproducing further at a brand-new call site.

**Silent failures**: a background 401 (a request sent with a token that the backend no longer accepts - the session expired or was revoked) already triggered a silent logout with zero user-facing explanation. `AuthContext`/`AuthProvider` gained `sessionExpiredMessage: string | null` and `clearSessionExpiredMessage()`; the unauthorized-handler now sets a message ("Your session has expired. Please log in again.") instead of just clearing state. `LoginPage` reads it once on mount, feeds it through the exact same `formError`/`FormError` mechanism every other login failure already uses (no new banner or toast component), and clears it immediately so it can't reappear on a later visit.

---

## Authentication Foundation

- `AuthContext` (`src/contexts/AuthContext.ts`) defines the context and its value shape: `user`, `token`, `isAuthenticated`, `isLoading`, `login`, `logout`, and (Issue #50) `sessionExpiredMessage`/`clearSessionExpiredMessage` - see Error Handling above.
- `AuthProvider` (`src/contexts/AuthProvider.tsx`) is the real implementation now, not scaffolding: `login()` calls the backend and persists the returned token (`src/lib/tokenStorage.ts`, localStorage); on mount, a stored token is restored and validated against `GET /users/me`, clearing it if invalid; a 401 on an already-authenticated request (registered via `setUnauthorizedHandler` in `api/client.ts`) is treated as the session ending and logs out silently apart from the message described in Error Handling above.
- `useAuth()` (`src/hooks/useAuth.ts`) reads the context and throws if used outside `AuthProvider`.
- `ProtectedRoute` (`src/components/common/ProtectedRoute.tsx`) redirects to `/login` when `isAuthenticated` is `false`, showing a loading state instead while the initial session restore is still in progress (so an already-logged-in user doesn't flash to `/login` on page load).

The context and provider are defined in separate files (`AuthContext.ts` / `AuthProvider.tsx`) rather than one, so that `AuthProvider`'s file only exports a component; a file that exports both a component and a plain object (like the earlier combined version) trips React Fast Refresh's `only-export-components` lint rule.

---

## Form State Management

`useAuthForm` (`src/hooks/useAuthForm.ts`) is a small, shared hook used by both `LoginPage` and `SignupPage`. It owns only what was genuinely duplicated between the two: field values, field/form-level error state, `isSubmitting`, the generic input change handler, and the submit-guard/loading skeleton (`preventDefault`, block a second submit while one is in flight, toggle `isSubmitting` around an async action). It deliberately does not own validation rules or error interpretation: each page still supplies its own `validate` function and its own `onSubmit` callback, which is what keeps Signup's field-specific `409` handling and Login's deliberately-never-field-specific `401` handling fully separate and unaffected by the extraction. This is intentionally scoped to these two forms, not a general-purpose form framework.

---

## Dashboard

As of Sprint 3.5 (Issue #130), analyses are scoped to a patient, so there is no cross-patient "recent activity" feed to show on a landing page - that gap was Issue #130/#131's stopgap ("View patients" and nothing else). **Issue #132 rebuilt `DashboardPage` (`src/pages/DashboardPage.tsx`) around its actual purpose: answering "what patient do I want to work on?" rather than "what analysis recently happened?"** At the time, analyses, documents, and medications remained entirely managed from within a patient's own pages (`PatientOverviewPage` and its children); the Dashboard only led into that workflow, never duplicated it - it explicitly omitted a Recent Analyses section and any way to start an analysis without a patient already open, since no aggregate analyses endpoint existed and adding one was out of that issue's scope.

**Issue #157 revisits both of those calls.** Once `CreateAnalysisPage` existed as one single, patient-scoped destination for starting an analysis (Issue #160) and a cross-patient analyses endpoint became a reasonably small, justified backend addition (see Backend below), the reasons for omitting them no longer held. The Dashboard's actual layout, top to bottom, is now:

1. **Welcome** - unchanged: `PageHeader` with `Welcome back, {name}` (or a generic "Welcome back" when the user has no name).
2. **Quick Actions** - moved to the top of the page (Issue #157; it used to sit at the bottom, after the patient list) and now has three entries in a `<nav aria-label="Quick actions">`: **+ New Analysis** (primary/blue - see below), **+ New patient** (`ROUTES.newPatient`, unchanged wording - already fulfilled the issue's "Add Patient" requirement, so it wasn't renamed for its own sake), and **View all patients** (`ROUTES.patients`, kept from before). Unlike every other section on this page, Quick Actions renders unconditionally - even in the "no patients yet" empty state - since it's meant to be reachable near the top of the Dashboard regardless of what else is going on; only **+ New Analysis** itself is disabled when there's no patient yet to start one for.
3. **Loading / error / empty states** (for the patient list specifically) - `usePatients()` (the same hook `PatientsPage` uses) is still the main data fetch driving this section. `LoadingSpinner`/`ErrorState` handle those states exactly as `PatientsPage` does; `EmptyPatientState` (`hasActivePatients={false}`) shows the same "No patients yet" onboarding CTA reused directly. The search box is still hidden in this state (nothing to search yet), but - as of Issue #157 - Quick Actions is not.
4. **Patient search** - `PatientSearch` (unchanged) feeds the existing `filterPatients` utility (`components/patients/filterPatients.ts`, from Issue #127 - client-side, case-insensitive, over first name/last name/full name/MRN, since the backend's `GET /patients` has no search parameter). Search runs live on every keystroke and searches the *entire* loaded patient list, not just the Recent Patients preview below, so a patient outside the top 3 is still found.
5. **Recent patients / Search results** - a single `<section>` whose heading switches between "Recent patients" (search box empty) and "Search results" (search box non-empty), backed by two different views over the one `patients` array `usePatients()` already loaded - never two separate requests. Rendered with the same `PatientList`/`PatientCard` `PatientsPage` uses (see "Recent patient strategy" below for the sort). An empty result set reuses `EmptyPatientState` again, this time with `hasActivePatients={true}` (its "No patients match your search." branch).
6. **Recent Analyses** (Issue #157) - see its own subsection below. Renders independently of the patient-list state above it (it has its own loading/error/empty states, from its own hook), including in the "no patients yet" case, where it shows its own empty message rather than being hidden.

Items 4-6 (patient search + Recent patients/Search results, and Recent Analyses) sit in a two-column CSS grid (`grid-cols-1 lg:grid-cols-2`) - a single column on phone and tablet portrait, patients on the left and analyses on the right from `lg:` (1024px) up. This is a purely visual rearrangement: the DOM order is unchanged (patients column first, analyses column second), so tab order and screen-reader reading order match what they were before the grid and match the stacked mobile layout exactly - there's no separate "desktop navigation path" to keep in sync.

### Starting an analysis from the Dashboard (Issue #157)

**+ New Analysis** can't go anywhere by itself - unlike every other patient-scoped entry point into `CreateAnalysisPage`, the Dashboard doesn't already have a patient in its URL. Clicking it opens `StartAnalysisDialog` (`src/components/dashboard/StartAnalysisDialog.tsx`), a searchable patient picker, and selecting a patient there does the actual handoff: `navigate(createAnalysisPath(patient.id))`, landing on the exact same `CreateAnalysisPage` every other entry point already uses (Overview's Quick Actions, `PatientAnalysesPage`'s "+ Start analysis," `PatientDocumentsPage`'s "Create Analysis" - see Create Analysis above). Nothing about analysis creation itself is reimplemented here; this is purely a "pick a patient first" prompt in front of an unchanged destination.

`StartAnalysisDialog` reuses the same native `<dialog>` pattern as `ArchivePatientDialog`/`DeleteAnalysisDialog` (`showModal()`/`close()`, `fixed inset-0 m-auto` centering, backdrop-click-to-cancel), but differs from both in two ways:

- There's no single "target" object that can double as the dialog's own open/closed flag (the content is a searchable list, not one confirm message), so `isOpen` is an explicit boolean prop instead.
- Selecting a patient - a single click on their row, no separate "confirm" step - *is* the confirmation. There's no destructive action here to guard against, so unlike the Archive/Delete dialogs, initial focus isn't deliberately steered anywhere in particular; the search input reasonably being first in tab order is enough.

The picker reuses `PatientSearch` and `filterPatients` directly (per the issue's own "reuse existing search functionality" instruction) over the full `patients` array `usePatients()` already loaded on the page - the same list Recent Patients and the main search box already work from, not a second fetch. Each matching patient renders as a plain `<button>` (name, MRN if present), fully keyboard-operable (Tab, Enter/Space) without needing a second component like `PatientCard`, which carries View/Edit/Archive actions this picker has no use for.

### Recent Analyses (Issue #157)

A cross-patient feed, unlike everything else `DashboardPage` shows - the one place in the whole app an analysis is displayed outside its own patient's pages. Backed by a new hook, `useRecentAnalyses(limit = 3)` (`src/hooks/useRecentAnalyses.ts`), calling a new API function, `getRecentAnalyses(limit)` (`src/api/analyses.ts`), against a new backend endpoint - see Backend below. The hook mirrors `usePatientAnalyses`'s shape (`{ analyses, isLoading, error, retry }`) minus `removeAnalysis`: this feed is read-only, since deleting an analysis remains a patient-page action (`AnalysisDetailPage`'s own delete workflow, Issue #48), not something this glance-and-go preview offers.

Each analysis renders with `RecentAnalysisCard` - the exact same component `PatientOverviewPage`/`PatientAnalysesPage` already use, extended with one new optional prop, `patientName?: string` (default unset, so every existing caller's rendering is unchanged). When present, it renders the patient's name above the status badge, and folds into the link's own `aria-label` ("View analysis for {patientName} from {date}, status: {status}"), so a screen reader user gets the same "which patient is this" context sighted users get from the visible name. `DashboardPage` passes it as `` `${analysis.patient.first_name} ${analysis.patient.last_name}` ``, using the `patient` object the new endpoint nests on each row; no other caller passes it at all, since they're already on that patient's own page.

### Backend: a cross-patient analyses endpoint (Issue #157)

Every existing analyses endpoint is nested under `/patients/{patient_id}/analyses` - Recent Analyses is the first thing in this app that needs analyses spanning *every* patient a user owns, and no such query existed. This is the one backend change Issue #157 required, and it's deliberately narrow: a new read-only endpoint, `GET /analyses/recent` (see `docs/api.md`), scoped to the current user via the same `get_current_user` dependency every other endpoint already uses - not a new `/me`-style prefix, matching how `GET /patients` is already implicitly "my patients" with no user id in the URL.

- **Route**: lives in a second `APIRouter` in the same `app/api/routes/analyses.py` file (`recent_analyses_router`, prefix `/analyses` - the existing `router`'s prefix, `/patients/{patient_id}/analyses`, can't accommodate a cross-patient path), registered alongside the existing one in `app/main.py`. No collision: `/analyses/recent` and `/patients/{patient_id}/analyses/{analysis_id}` share no path segments.
- **Service**: `list_recent_analyses_for_user(db, user_id, limit)` (`app/services/analysis_service.py`) joins `Analysis` to `Patient` to filter by `Patient.user_id` and exclude archived patients (`Patient.status != ARCHIVED_STATUS`, the same constant and exclusion `list_patients` already applies), ordered by `Analysis.id.desc()` - the same tie-breaking reasoning as every other analyses listing in this codebase (Postgres's `now()` is constant within a transaction, so `created_at` alone can't be trusted to break ties).
- **Schema**: `RecentAnalysisResponse` (`app/schemas/analysis.py`) extends `AnalysisSummaryResponse` with one field, `patient: PatientSummaryResponse` - a new minimal schema (`app/schemas/patient.py`: `id`, `first_name`, `last_name`) added for this, the same "citation, not the full resource" shape `ClinicalDocumentSummaryResponse` already established for nesting evidence elsewhere.

No migration, no new table, no change to any existing endpoint's behavior - this is a new query and a new response shape over data that already existed.

### Recent patient strategy

Patient access is not tracked anywhere in this app (no "last opened by this provider" timestamp), so the ideal "recently accessed" ordering isn't available. `sortPatientsByRecentActivity` (`components/patients/sortPatientsByRecentActivity.ts`, a pure function alongside `filterPatients`) instead sorts by `updated_at ?? created_at` descending: a patient's most recent edit if it's ever been edited (`Patient.updated_at` is set on `PATCH`, `app/services/patient_service.py`), falling back to its creation time if it hasn't. This satisfies the issue's documented fallback chain (access timestamps → recently updated → creation date descending) using the two signals that actually exist. The result is sliced to `RECENT_PATIENTS_LIMIT` (3) - a glance-and-go preview, not the full history that `PatientsPage` already provides.

`PatientCard` gained two new optional props to show what this preview needs beyond what `PatientsPage`'s own list shows - `showStatus` and `showUpdatedAt` (both default `false`, so `PatientsPage`'s existing cards render exactly as before). `DashboardPage` passes both as `true`; `updated_at` being `null` for a never-edited patient simply omits that one stat rather than showing an empty value. `PatientList` threads both through to every `PatientCard` it renders. This is the same card everywhere - reusing `PatientCard`/`PatientList` for the Dashboard rather than building a second, near-identical "recent patient" card design.

`patientStatusLabel` (`src/utils/patientStatus.ts`) is a small extraction - the `{ active: 'Active', archived: 'Archived' }` lookup previously lived only inside `PatientDetails`; it's now shared so `PatientCard`'s new status display and `PatientDetails` use the identical mapping instead of two copies.

---

## Upload

`UploadPage` (`src/pages/UploadPage.tsx`) is nested under a patient: `/patients/:patientId/upload`. It fetches the patient via `usePatient` (the same hook `PatientOverviewPage` and `PatientMedicationsPage` use) to show the patient's name in the heading, a breadcrumb, and a back link, then lets the user supply one or more clinical notes for that patient, either as files or pasted text. This is the same workflow introduced in Issue #41, adapted (not rebuilt) repeatedly since: Sprint 3.5 (Issue #130 - patient-scoping), Issue #131 (breadcrumb/back-link chrome), Issue #44 (moved analysis creation itself off this page onto Analysis Processing - see below), Issue #158 (added "Save documents" alongside "Start Analysis"), and **Issue #160**, which is the point at which analysis creation left this page entirely.

**As of Issue #160, `UploadPage` only saves documents - it no longer starts an analysis.** "Start Analysis" has been removed; **Save documents** is now the page's only action. This is a direct consequence of Issue #160 unifying analysis creation onto one page (`CreateAnalysisPage`, see below) - keeping a second, independent "upload and analyze in one step" path here would have recreated exactly the "separate upload and existing-document workflows" that issue asked to eliminate. `UploadPage` is now purely a document-management utility: add files/notes, click Save documents, land back on `PatientDocumentsPage` with them already on file - building an analysis from them (alone or combined with anything else already on file) happens on `CreateAnalysisPage` afterward, whenever the provider is ready.

`src/components/upload/`:

- `FileDropzone`: a `role="button"` drop target that is also click-to-open and keyboard-operable (Enter/Space), since drag-and-drop alone would exclude keyboard users. The actual `<input type="file">` is visually and semantically hidden (`sr-only`, `aria-hidden`, `tabIndex={-1}`) since the outer element is the one interactive control a screen reader or keyboard user sees.
- `UploadedFileList`: name, size, a per-file `DocumentTypeSelect`, and a remove button, one row per selected file.
- `ManualNoteEditor`: the "add a new note" form (optional title, required text, a `DocumentTypeSelect` defaulting to Visit note); clears itself after each add.
- `NoteCard`: a saved note, with in-place edit (including its document type) and remove.
- `DocumentTypeSelect`: a plain labeled `<select>` shared by `UploadedFileList`, `ManualNoteEditor`, and `NoteCard`'s edit mode, over the fixed vocabulary in `DOCUMENT_TYPES` (`api/clinicalDocuments.ts`): Visit note, Progress note, Discharge summary, Medication list, Medication reconciliation form. The backend's `document_type` column has no enum (plain `str`), but this is the same fixed set the reconciliation engine and product docs already use (`medication_list`/`medication_reconciliation_form` specifically get special treatment there); the user always chooses, since automatic classification is out of scope. Every file and note is keyed by a locally generated numeric id, not array index, since it's the only way per-item state (`NoteCard`'s edit mode, and the upload-retry cache below) can't end up attached to the wrong item after a removal shifts array positions.
- `UploadEmptyState`: a plain hint shown when nothing has been added yet; unlike `AnalysesEmptyState` this isn't a full-section replacement, since the upload/paste controls themselves stay visible either way.

Selected files are validated against the backend's actual supported types (`.txt`/`text/plain`, `.pdf`/`application/pdf`, `.csv`/`text/csv`, mirrored exactly from `app/api/routes/clinical_documents.py`) and de-duplicated by name+size; no file size limit is enforced, since the backend does not define one either. A pasted note's title is genuinely optional in the UI, but the backend requires a non-empty title, so an untitled note is given a generated fallback (`Note 1`, `Note 2`, ...) at submission time - numbered by the note's current position in the queue, not a never-reused counter, so removing a note and adding another doesn't skip numbers.

### CSV medication list uploads (Issue #164)

A CSV is just a fourth supported file format alongside `.txt`/`.pdf` - there is no separate "CSV mode." `isCsv(file)` (`api/clinicalDocuments.ts`, mirroring the existing `isPdf`) picks `upload-csv` as the third branch in `uploadClinicalDocumentFile`'s endpoint selection; the file is stored as an ordinary `ClinicalDocument` (`file_type: "csv"`) and flows through AI extraction and reconciliation exactly like any other document's `raw_text`.

**This is deliberately unrelated to the existing CSV medication *import* feature** (`MedicationCsvUpload`, `PatientMedicationsPage`, `POST /patients/{patientId}/medications/import`, under Medications below), which parses a CSV into rows and directly creates `Medication` records. Uploading a CSV during analysis creation never calls that pipeline, never touches the medications table, and performs no row/column validation at all (`upload-csv` only checks that the file decodes as non-empty UTF-8, same as `upload-txt`) - a CSV that `parse_medication_csv` would reject outright is still accepted here, since it's stored as evidence text for the AI, not parsed into structured data. See `docs/api.md`'s Notes section for the same distinction from the backend's side.

`useDocumentQueue.handleFilesSelected` defaults a queued CSV file's document type to Medication list (`DEFAULT_CSV_DOCUMENT_TYPE`) rather than the usual Visit note default - a CSV in this app is overwhelmingly a medication list, so this saves a manual dropdown change in the common case; it's still freely changeable via the same `DocumentTypeSelect` every other file uses. A CSV is otherwise indistinguishable in the UI from any other queued file - its filename (with `.csv` extension) is enough to identify it before upload, and `ClinicalDocumentCard`'s existing `FILE_TYPE_LABELS` map (see Clinical Documents > Patients below) gained a `csv: "Uploaded .csv file"` entry so it's identified the same text-based way `.txt`/`.pdf` uploads already are, once saved.

### Retrying a partially failed submission

`useCreateAnalysis` caches each item's resulting document id (`fileItemKey(id)`/`noteItemKey(id)` to a `Map`, held in a ref) as soon as it uploads successfully. If a later item then fails, calling `submit()` again with the same queue skips re-uploading whatever already succeeded and only retries what didn't, rather than creating duplicate ClinicalDocument rows. The cache lives inside the hook, not in the caller's own state, since nothing outside a submission attempt needs to read it. The cache is also cleared automatically the moment an analysis is actually created, since any submission after that is a new attempt, not a retry. `failedItemLabel` (the failing file's name, or the note's title/fallback) is exposed alongside the error message so a multi-item failure is attributable to a specific item, not just "something failed" - as of Issue #50, `UploadPage` and `AnalysisProcessingPage` actually compose it into the displayed message (`` `${failedItemLabel}: ${error}` ``); previously the hook computed it but no page read it. As of Issue #44, `invalidateItem` and this retry cache live entirely on `AnalysisProcessingPage` (see below) rather than `UploadPage` - editing a file or note now only ever happens *before* any submission attempt exists, so there is nothing yet to invalidate on the upload page itself; the "Try again" action on the processing page is what re-runs `submit()` against the same queue and benefits from the cache.

### Saving documents without starting an analysis

Originally added in Issue #158 alongside "Start Analysis" (uploading a document and starting an analysis had been inseparable in the UI until then, even though the backend has always treated document creation and analysis creation as two independent operations - `POST /patients/{patientId}/clinical-documents*` vs. `POST /patients/{patientId}/analyses`). **Issue #160 removed "Start Analysis" from this page entirely** (see Upload's opening paragraph above), leaving **Save documents** as `UploadPage`'s only action - styled blue/primary now that it's the only one, rather than the secondary/outline styling it had while sharing the page with "Start Analysis."

Clicking Save documents uploads the queued files/notes as real `ClinicalDocument`s and stops there - no analysis is created - then navigates to `PatientDocumentsPage` (`patientDocumentsPath`), where the newly saved documents are immediately visible, the same "the list update is the feedback" pattern this codebase already uses instead of a toast (see Patients > Archiving below).

`useCreateAnalysis` has two entry points: `saveDocuments({ files, notes }): Promise<number[]>` (used here) and `submit` (used by `CreateAnalysisPage`, via `AnalysisProcessingPage` - see below). Both share one internal helper, `uploadQueuedItems`, that does the actual per-file/per-note upload loop and cache bookkeeping described above; `submit` calls it and then also calls `createAnalysisFromDocuments`, while `saveDocuments` calls it and stops, returning the resulting document ids.

The button is labeled "Save documents," not the shorter "Save" - `NoteCard`'s own in-place note editor already has its own "Save" button (for saving a note's edited text) that can be visible on the very same page at the same time, and two identically-labeled but functionally unrelated "Save" buttons on one page would be genuinely ambiguous for sighted users, not just an accessible-name collision to work around.

**Issue #160** also extracted the file/note queueing itself - state, file-type validation, de-duplication, edit, remove - into a shared hook, `useDocumentQueue` (`src/hooks/useDocumentQueue.ts`), since `CreateAnalysisPage`'s new "Upload Additional Documents" section needed to behave identically to `UploadPage`'s own upload section. Both pages now call this one hook rather than maintaining separate, could-drift-apart copies of the same logic; `isDuplicateFile` (same-name-and-size de-duplication) moved out to `src/utils/queuedFiles.ts` for the same reason. Neither page calls any upload API directly from this state any more than before - the hook only manages the local queue; `saveDocuments`/`submit` (both on `useCreateAnalysis`) are what actually persist it.

---

## Create Analysis

Issue #145 first added a second way into analysis creation, alongside Upload: `SelectDocumentsPage` let a provider pick from a patient's *already-uploaded* clinical documents instead of supplying new ones, entirely separate from `UploadPage`'s "supply new documents" flow. **Issue #160 unified the two** into one page, `CreateAnalysisPage` (`src/pages/CreateAnalysisPage.tsx`, renamed from `SelectDocumentsPage.tsx`, at a renamed route: `/patients/:patientId/analyses/new`, was `/analyses/select-documents`): a provider can now select existing documents, upload new ones, and combine both into the same analysis, all on one page, rather than being forced to pick one workflow or the other. The backend investigation from Issue #145 still holds and needed no revisiting: `POST /patients/{patientId}/analyses` (`create_analysis`, `app/services/analysis_service.py`) has never distinguished a newly uploaded document from one already on file - it only validates that every requested id belongs to the given patient - so combining both kinds of ids in one request already worked before this issue existed; **Issue #160 required no backend changes**, exactly as it asked for. See `docs/api.md`.

The page has three sections, top to bottom:

- **Existing Documents** - fetches the patient's documents (`usePatientClinicalDocuments(patientId)`, the same hook the Clinical Documents section on `PatientOverviewPage` uses) and renders each as a `<label>` wrapping a real `<input type="checkbox">` plus the document's title, `documentTypeLabel(document_type)`, and upload date - the label wrapping means clicking anywhere in the row toggles it, and gives each checkbox a correct accessible name (the title, from the label's own text content) for free, with no separate `aria-label` needed. This section has its own scoped loading/error state (`ErrorState` with retry) - a failure to load existing documents doesn't block the Upload Additional Documents or Selected Documents sections below, which don't depend on it.
- **Upload Additional Documents** - `FileDropzone` and `ManualNoteEditor`, the exact same components `UploadPage` uses, both driven by the same shared `useDocumentQueue()` hook (see Upload above). A file or note added here is immediately reflected in the Selected Documents count below and in the page's overall selection - there is no separate "confirm upload" step, matching the issue's explicit "uploaded documents should immediately become part of the current analysis selection" requirement.
- **Selected Documents** - the single combined summary of everything that will be included: selected existing documents (each removable by unchecking it from this list too, via a "Remove {title} from selection" button - not just from the checkbox list above), queued files (`UploadedFileList`, with its own per-file document-type editor and remove button), and queued notes (`NoteCard`s, with edit and remove). When nothing is selected, a plain sentence replaces the three subsections rather than showing three empty sub-headings.

Selected existing document ids live in local `Set<number>` state (`selectedExistingIds`), separate from the queued-files/notes state `useDocumentQueue` owns; the **Create Analysis** button is disabled until `selectedExistingIds.size + queuedCount > 0`, next to an `aria-live="polite"` "`N` document(s) selected" count combining both sources so sighted and screen-reader users alike can tell the total, not just one source's count. When the patient has no existing documents at all, the Existing Documents section reuses `EmptyDocumentsState` (`components/documents/EmptyDocumentsState.tsx`) as-is - but unlike the old `SelectDocumentsPage`, this is no longer a dead end: the Upload Additional Documents section right below it still works, so a brand-new patient with zero documents can still build their first analysis on this same page.

Clicking Create Analysis does **not** call `useCreateAnalysis` itself here - exactly as `SelectDocumentsPage` didn't before it - it navigates to `analysisProcessingPath(patientId)` with `{ files, notes, existingDocumentIds: Array.from(selectedExistingIds) }` as router state, the same `SubmitInput` shape `AnalysisProcessingPage` (see below) already handles; `useCreateAnalysis`'s `submit()` already combines uploaded and existing ids in one `createAnalysisFromDocuments` call (`existingDocumentIds` was added for this in Issue #145), so no changes were needed there either.

The entry point lives in three places now: `PatientOverviewPage`'s Quick Actions (a new "Create Analysis" action, primary/blue - see "Quick Actions and the 'Create Analysis' question" under Patients, which this issue directly resolves), `PatientAnalysesPage`'s "+ Start analysis" action, and `PatientDocumentsPage`'s "Create Analysis" action (`createAnalysisPath`) - all three previously pointed at either `UploadPage` or the old `SelectDocumentsPage`; all three now point here.

### Searching and paging Existing Documents

Follow-up to Issue #160: a patient with a long document history turned the plain checkbox list into exactly the "content overload" the unified page was meant to avoid. The Existing Documents section now adds, above the checklist:

- **A search box** (`Input type="search"`, labeled "Search existing documents") filtering client-side by title or document type label, via a new pure function `filterClinicalDocuments` (`src/components/documents/filterClinicalDocuments.ts`) - the same "no backend search parameter, so filter what's already fetched" reasoning as `filterPatients.ts`, and tested the same way (its own dedicated test file, not just through the page). When the patient has no documents to filter and matching yields nothing, a plain sentence ("No documents match your search.") replaces the checklist - the same "empty-search vs. truly-empty" distinction `EmptyPatientState` already established, rather than showing `EmptyDocumentsState`'s upload CTA over documents that do exist, just unmatched.
- **A "Show more" / "Show less" cap** (`EXISTING_DOCUMENTS_PREVIEW_LIMIT = 3`, matching every other preview limit in the app - see Dashboard and Clinical Documents): only the first 3 matching documents render at once, with a "Show `N` more" button revealing the rest, and "Show less" to re-collapse. Changing the search query always resets back to the collapsed view - showing every match immediately for a broad query would just recreate the same overload the cap exists to prevent.

Both are local UI state (`existingDocumentsQuery`, `showAllExisting`) scoped to this page; they filter/cap only which existing documents are *displayed*, never which are *selected* - a document stays selected even while hidden by the current search or cap, since selection state (`selectedExistingIds`) and display state are intentionally independent.

Writing this feature's tests surfaced a real, pre-existing accessibility bug in the checklist rows: the title and metadata `<span>`s had no separator between them, so the checkbox's computed accessible name concatenated them with no space (`"Document 1Visit note..."`) - harmless visually (the two live in a `flex flex-col`), but a screen reader would run them together as one word-like string. Fixed with a literal `{' '}` between the two spans, which a Flexbox `display: flex` container collapses away visually (whitespace-only text between block-level flex children generates no visible box) while still giving the accessible-name computation the space separator it needs.

---

## Analysis Processing

Issue #44 added a dedicated page bridging analysis creation and `AnalysisDetailPage`: `AnalysisProcessingPage` (`src/pages/AnalysisProcessingPage.tsx`, `/patients/:patientId/analyses/processing`). Issue #145 gave it a second entry point (`SelectDocumentsPage`'s "Create Analysis", alongside `UploadPage`'s "Start Analysis"); **Issue #160 collapsed both back down to a single entry point**, `CreateAnalysisPage` (see above) - `UploadPage` no longer navigates here at all, since it only saves documents now. Either way, this page itself has never needed to know or care which entry point sent it: it just `navigate()`s here with a `SubmitInput`-shaped router state, reading `files`/`notes`/`existingDocumentIds` from `useLocation().state` rather than the URL, since a File object can't round-trip through a path or query string; visiting the route directly or reloading it loses that in-memory state, so the page detects a missing/empty `state` and shows a "Nothing to process" recovery card linking back to Upload instead of hanging on a spinner forever.

On mount, the page itself calls `useCreateAnalysis(patientId).submit({ files, notes, existingDocumentIds })` (the same hook and multi-request sequence `UploadPage` used to drive directly) and shows a loading card for the duration: a spinner (`LoadingSpinner`), a rotating headline cycling through fixed, cosmetic progress messages ("Preparing analysis...", "Extracting medication mentions...", "Reconciling medication list...", "Comparing documentation...", "Generating clinical summary...", "Finalizing analysis...", via `useRotatingMessages`, `src/hooks/useRotatingMessages.ts`, one every 3.5s), and static supporting copy ("AI is reviewing uploaded clinical documents.", "Estimated time: 10-30 seconds", "Please keep this page open."). The whole card is `aria-live="polite"` so both the rotating headline and any later status change are announced to assistive tech.

**Why polling, given the backend call is synchronous**: `POST /patients/{patientId}/analyses` (`summarize_clinical_documents`) does not return until the entire AI call and persistence step finishes - there is no way to observe an intermediate `pending`/`processing` state from a separate request today. Rather than add backend work to make analysis creation asynchronous (out of scope for a loading-page issue, and the issue explicitly asked to avoid backend changes unless unavoidable), the page still polls the real, existing `GET /patients/{patientId}/analyses/{analysisId}` via a new `useAnalysisPolling(patientId, analysisId, intervalMs = 2000)` hook (`src/hooks/useAnalysisPolling.ts`) once `submit()` resolves with an id: it fetches immediately, and re-fetches every `intervalMs` for as long as `status` is `pending` or `processing`, stopping the moment it sees `completed` or `failed`. In practice the very first fetch already observes a terminal status, since the backend has nothing left to do by the time an id exists - but the polling loop is correct and will keep working with no frontend changes if analysis creation ever becomes genuinely asynchronous later.

Once `analysis.status === 'completed'`, an effect calls `navigate(analysisDetailPath(patientId, analysisId), { replace: true })` automatically - `replace` so the transient processing page never sits in browser history between Upload and the results page. There are three distinct ways this page can end in failure instead, each rendered through the same `FailureCard` (clear explanation, "Return to Patient Overview", "Return to Analysis History"):

- `submit()` itself throws (an upload or the create call failed before an analysis id ever existed) - `FailureCard` also gets a "Try again" button that re-runs `submit()` with the same queued files/notes, reusing `useCreateAnalysis`'s own retry cache.
- Polling observes `status === 'failed'` (the analysis was created but the AI call failed) - same "Try again", since retrying here just means creating a fresh analysis from the same input; there is no backend endpoint to "retry" one specific failed analysis by id.
- `useAnalysisPolling` itself returns an `error` (the status-check request failed, independent of the analysis's own status) - also gets a "Try again" (Issue #50, via the hook's own `retry()`), but this one only re-checks status rather than resubmitting: resubmitting would create a duplicate analysis, since the original one may already exist and be fine. The user can also go to Analysis History instead, where the analysis (whatever its real status turns out to be) will already be listed.

No changes were needed to `AnalysisDetailPage` itself - building out its discrepancy/findings content remains explicitly out of scope for this issue.

---

## Analyses

Sprint 3.5, Issue #130: analysis history moved from a global Dashboard feed to a per-patient page, `PatientAnalysesPage` (`src/pages/PatientAnalysesPage.tsx`, `/patients/:patientId/analyses`). It fetches the patient via `usePatient` (for the heading, breadcrumb, and back link) and the patient's analyses via `usePatientAnalyses(patientId, 50)` (`src/hooks/usePatientAnalyses.ts`) - Issue #131 raised this page's own limit from the hook's default of 10 to the backend's maximum of 50, since this page is the full browsable history, not a preview. The hook calls `listAnalyses(patientId, limit)` (`src/api/analyses.ts`, `GET /patients/{patientId}/analyses`) and exposes `{ analyses, isLoading, error, retry, removeAnalysis }`, the same shape `usePatientMedications` and the other patient-scoped hooks use; `removeAnalysis` (added in Issue #131) calls `deleteAnalysis(patientId, id)` (`DELETE /patients/{patientId}/analyses/{analysisId}`) and removes the row from local state on success.

`src/components/analyses/` (moved here from `components/dashboard/` when the Dashboard's global feed was retired):

- `RecentAnalysisCard`: one analysis, with a status badge (`AnalysisStatusBadge`, extracted in Issue #131 so `AnalysisDetailPage` could reuse the exact same label/color mapping instead of a second copy), created/completed timestamps, the AI summary text, document count, and finding counts via `SummaryStat` (`components/common/SummaryStat`), provider/model if present. The whole card is a single `Link` to `analysisDetailPath(analysis.patient_id, analysis.id)` (using the `patient_id` now present on `AnalysisSummary` itself, rather than a prop threaded down from the page), with an explicit `aria-label` describing the date and status. An optional `onDelete` prop (Issue #131) renders a "Delete" button in a separate footer row *outside* the `Link` (a button nested inside an anchor would be invalid, keyboard-unreachable markup) - `PatientAnalysesPage` passes `removeAnalysis`; `PatientOverviewPage`'s Recent Analyses preview does not, since delete belongs to the full history page, not the glance-and-go preview.
- `RecentAnalysesList`: a semantic `<ul>` of cards, threading the optional `onDelete` through to each.
- `AnalysesEmptyState`: explains what MedLens does and links to this patient's Upload page, shown when the patient has no analyses yet.
- `AnalysisStatusBadge` (Issue #131): the status-to-label/color mapping, extracted out of `RecentAnalysisCard` so `AnalysisDetailPage` renders an identical badge rather than a near-duplicate. The label lookup itself (`analysisStatusLabel`) lives in `src/utils/analysisStatus.ts`, not this component file - keeping a plain function out of a component file avoids tripping the `react-refresh/only-export-components` lint rule.
- `DeleteAnalysisDialog` (Issue #48): the confirmation dialog `AnalysisDetailPage`'s "Delete analysis" action opens - see Issue #48 below.

`AnalysisDetailPage` (`src/pages/AnalysisDetailPage.tsx`, `/patients/:patientId/analyses/:analysisId`) fetches real data as of Issue #131, via a new `useAnalysisDetail(patientId, analysisId)` hook (`src/hooks/useAnalysisDetail.ts`) calling `getAnalysisDetail` (`api/analyses.ts`, `GET /patients/{patientId}/analyses/{analysisId}`, added in this issue - the route existed since #130 but nothing on the frontend called it yet). It shows a breadcrumb (Patients / patient name / Analyses / Analysis #N), the same `AnalysisStatusBadge`, the sanitized `error_message` for a failed run, the `summary` text, and whatever of `created_at`/`started_at`/`completed_at`/`provider`/`model_name` the backend actually populated (an item is omitted rather than shown as empty when its value is `null`). One thing was deliberately still out of scope and was **not** added, because the backend didn't expose it and adding it would have meant changing the API, which this issue explicitly forbade:

- **Finding/severity counts.** Only on `AnalysisSummaryResponse`, not the detail response.

(A document count *was* later added to the detail response too - see Issue #47 below.)

`medication_mentions` and `possible_inconsistencies` (the AI's raw, unstructured observations) were not rendered here at the time - the frontend's `AnalysisDetail` type (`types/api.ts`) omitted both fields entirely, even though the backend response included them, so it was structurally impossible to accidentally render that particular UI. Issue #47 (below) is what lifts that restriction.

**Issue #148** wired the existing medication reconciliation engine into analysis creation (see `docs/architecture.md`'s Analysis Creation Pipeline), so completed analyses can have real `MedicationDiscrepancy` findings - `AnalysisDetail` gained a `medication_discrepancies` field. That issue rendered them minimally (a plain-text list, deliberately, since it was a backend integration task); **Issue #46** is the redesign of that presentation:

- **Summary** - a `Card` directly under the "Medication Reconciliation Findings" heading with `SummaryStat`s for Total/High/Medium/Low, computed client-side from `medication_discrepancies` (`.length` and a per-severity filter) rather than from `Analysis.total_findings`/`*_severity_findings` - both are the same underlying reconciliation output, but counting the exact array being rendered guarantees the summary can never drift from what's actually shown, with no backend request needed to get them.
- **Grouping and sorting** - `groupBySeverity` (`AnalysisDetailPage.tsx`) buckets findings into high/medium/low groups, in that order, dropping empty groups; within a group, findings are sorted by ascending `id` (stable, matching the order the backend already returns them in). Each non-empty group renders under its own `<h3>` ("High severity (2)"). There is no "critical" tier: the issue's own example ordering mentions one, but `DiscrepancySeverity` (the backend enum, unchanged by this issue) only has `high`/`medium`/`low` - inventing a 4th tier would have meant a backend change this issue's own "reuse existing enums" instruction ruled out.
- **`MedicationDiscrepancyCard`** (`components/analyses/MedicationDiscrepancyCard.tsx`) - the reusable card, one per finding: medication name (falling back to "Unknown medication" if neither piece of evidence below is present - a purely defensive case the real reconciliation engine never actually produces, since every finding type sets at least one), `discrepancyTypeLabel` (discrepancy type), `DiscrepancySeverityBadge` and `ResolutionStatusBadge` (both `components/analyses/`), `ai_explanation`, an `expected_value`/`observed_value` pair via `SummaryStat` when present, `recommendation` when present, and a "Supporting evidence" subsection: the mention's source document + `context_text` snippet when `medication_mention` is present, a one-line current-medication-list summary when only `medication` is present, or an explicit "No supporting evidence was recorded for this finding." when neither is - never a blank gap. A colored left border repeats the severity badge's signal (never color-only, per the issue's own accessibility requirement).
- **`DiscrepancySeverityBadge`** / **`ResolutionStatusBadge`** - the same visible-text-label-always pattern `AnalysisStatusBadge` already established; label lookups live in `utils/discrepancy.ts`, not the component files, for the same `react-refresh/only-export-components` reason `analysisStatusLabel` does. `ResolutionStatusBadge`'s label for `reviewed` is shown as "In Review" (matching this issue's own suggested wording) even though the underlying enum value is unchanged.
- **Empty state** - a positive `Card` ("No medication inconsistencies were detected.") replacing the earlier "No medication discrepancies were found for this analysis." wording, shown when `medication_discrepancies` is empty.
- **Heading hierarchy** - h1 (page) > h2 ("Medication Reconciliation Findings") > h3 (severity group) > h4 (medication name, per card) > h5 ("Supporting evidence", per card) - deliberately non-skipping, so screen-reader users can navigate the findings list by heading level at whatever granularity they need.

Backend change: `MedicationDiscrepancyResponse` (used inside `medication_discrepancies`) gained nested `medication`/`medication_mention` evidence - see docs/api.md and docs/data-model.md. Nothing about how or when discrepancies are created changed.

**Issue #47** rebuilt the top of `AnalysisDetailPage` into a dedicated "AI Summary" section, so the AI's raw output is no longer mixed in with (or absent from) the page:

- **AI Summary section** - an `<h2 id="ai-summary-heading">AI Summary</h2>` next to a violet "AI-generated" pill (`AiGeneratedBadge`, defined in `AnalysisDetailPage.tsx` - a static, page-local label used once, not extracted into `components/analyses/` since there's no second enum-driven caller for it the way `DiscrepancySeverityBadge` has). The section's `Card` carries a `border-l-4 border-l-violet-400` left accent, the same "never rely on color alone" pattern the severity cards use, just in a color reserved for AI content specifically (violet doesn't collide with the red/amber/slate/blue/green already used by severity, status, and resolution badges elsewhere).
- **Summary** - an `<h3>` rendering `analysis.summary`, or "No AI summary is available for this analysis." when it's `null` - the empty state this issue asked for. Reconciliation findings below are unaffected either way; a missing AI summary never hides them.
- **Medications Mentioned** - an `<h3>` rendering `medication_mentions` (now exposed on the frontend's `AnalysisDetail` type, previously deliberately omitted - see above) as a compact list of name / dosage / route / frequency / status / notes. The heading and list are omitted entirely when the array is empty, the same "no placeholder content" rule this issue set for follow-up questions, applied consistently here too.
- **Follow-up Questions** - an `<h3>` rendering `possible_inconsistencies` as a checklist (`FollowUpQuestionsChecklist`): one checkbox + label per inconsistency, keyed by `id`. Checked state is local-only `useState<Set<number>>`, intentionally not persisted anywhere - there is no backend field to persist it to, and this issue didn't ask for one. Omitted entirely (no heading, no empty-state text) when the array is empty, per this issue's explicit instruction.
- **Summary Metadata** - a `<h3>` labeled sub-block reusing `SummaryStat` for `created_at`/`started_at`/`completed_at`/`provider`/`model_name` (each omitted when `null`, same as before this issue) plus the new `document_count`, labeled "Documents analyzed".
- **No "Key clinical observations", "Mentioned conditions", or "Notable findings" sections.** The issue's own example wording names these, but `app/ai/schemas.py`'s `ClinicalSummary` has only `summary`, `medications`, and `possible_inconsistencies` - no structured field corresponds to conditions or "notable findings" as a concept distinct from the summary text itself. Rather than fabricate content or repurpose an existing field under a misleading heading, these sections are simply not present - the same "never invent data" decision this codebase already made for the "critical" severity tier in Issue #46.
- **"Deterministic" badge** - added next to "Medication Reconciliation Findings" (`DeterministicBadge`, same page-local pattern as `AiGeneratedBadge`), so the AI/deterministic distinction reads at both ends of the page, not just at the top.
- **Heading hierarchy** - h1 (page) > h2 ("AI Summary") > h3 (Summary / Medications Mentioned / Follow-up Questions / Summary Metadata) > h2 ("Medication Reconciliation Findings") > h3 (severity group) > h4 (medication name) > h5 ("Supporting evidence") - still non-skipping; the two h2 sections are siblings, not nested.

Backend change: `Analysis` gained a `document_count` property (`len(self.clinical_documents)`, the same computed-property pattern as `ClinicalDocument.analysis_count`), exposed as a new field on `AnalysisDetailResponse`; `get_analysis_for_patient` gained a `selectinload(Analysis.clinical_documents)` to compute it without an N+1 query. `medication_mentions` and `possible_inconsistencies` were already returned by the backend (see above) - only the frontend type and page were changed to render them. No AI extraction, prompt, or reconciliation logic was touched - see docs/api.md and docs/data-model.md.

### Deleting an analysis from the Analysis Results page (Issue #48)

`DELETE /patients/{patient_id}/analyses/{analysis_id}` already existed (Sprint 3.5, Issue #131 wired `deleteAnalysis`/`removeAnalysis` into `PatientAnalysesPage`'s list - see Analyses above) and its route, service function, and cascading-delete test coverage were reviewed and found to need no changes; this issue is purely a second frontend entry point onto the same endpoint, with a confirmation step the list page's inline delete never had.

- **`DeleteAnalysisDialog`** (`src/components/analyses/DeleteAnalysisDialog.tsx`) - a second dialog built on the same native `<dialog>` pattern `ArchivePatientDialog` established (see Patients > Archiving below): `showModal()`/`close()` for the overlay, backdrop-click-to-cancel, and `onClose` as the single place that syncs React state back to "closed." Its `target: { id, patientName } | null` prop is both the dialog's content and its open/closed flag, the same shape `ArchivePatientDialog`'s `patient` prop plays. Shown: "Analysis #{id} for {patientName}" and the issue's own suggested permanent-deletion wording verbatim.
- **Explicit initial focus on Cancel.** The HTML spec has `showModal()` auto-focus the first focusable descendant, which would already be Cancel here (it's listed first) - but this project's own jsdom `<dialog>` polyfill (`src/test/setup.ts`) only toggles the `open` attribute and wires up Escape/backdrop events, it does *not* replicate that auto-focus step (a documented gap in the polyfill, not of jsdom itself), so relying on the browser default would have been untestable and, in the one browser tested here (jsdom), simply wrong. `DeleteAnalysisDialog` instead calls `cancelButtonRef.current?.focus()` itself right after `showModal()`, making the "land on the safest action" requirement explicit and verified by a real regression test, rather than an assumption about default browser behavior.
- **Placement.** The delete action is a plain text button (not the bold blue primary-`Button` style) in `AnalysisDetailPage`'s `PageHeader` `actions` slot, next to `AnalysisStatusBadge` - a page-level action, not something living inside the findings content below, and visually secondary (red text on transparent/hover background, no fill) next to the page's other actions.
- **Workflow state** (`isDeleteDialogOpen`/`isDeleting`/`deleteError`) lives on `AnalysisDetailPage` itself, the same "page-local UI state, not a hook" choice `PatientsPage`/`PatientOverviewPage` already made for `ArchivePatientDialog`. On confirm: calls `deleteAnalysis(id, analysis.id)` directly (not through `usePatientAnalyses`, which is scoped to the *list* page and isn't mounted here) with `isDeleting` guarding against duplicate submissions and disabling both dialog buttons while in flight; a caught `ApiError` is shown inside the dialog via `role="alert"` and leaves the dialog open with the confirm button re-enabled, so the user can retry without re-opening it or losing their place.
- **Success navigation.** On success, `navigate(patientAnalysesPath(id), { state: { flashMessage: \`Analysis #${analysis.id} was deleted.\` } })` - the user is never left on a detail page for a resource that no longer exists. `id` (from `useParams`), not `patient.id`, is used inside this handler: they're the same patient once loaded, but `id` needs no null-narrowing of `patient` inside a nested closure (a plain TypeScript control-flow limitation, not a behavior difference).
- **The final-analysis empty state needed no work.** `PatientAnalysesPage` re-mounts `usePatientAnalyses` fresh on navigation and re-fetches from the server, so if the deleted analysis was the patient's last one, `AnalysesEmptyState` already renders automatically - exactly the "no additional work required" the issue predicted.

**The app's first real toast-style notification.** Previously, "no toast/notification component exists anywhere in this codebase" (see Patients > Archiving below) and every delete/remove action's only feedback was the immediate UI change itself (a card disappearing, a redirect). This issue's explicit "temporary success notification" requirement is the first case that pattern didn't cover, since the confirming page (`AnalysisDetailPage`) is gone by the time the user lands on `PatientAnalysesPage`. Rather than build a general-purpose toast system for a single caller, `PatientAnalysesPage` reads an optional `flashMessage` off `useLocation().state` in a `useEffect`, shows it in a dismissible `role="status"` banner, and immediately replaces the location's state with `null` (`navigate(location.pathname, { replace: true, state: null })`) so refreshing or navigating back to that history entry can't redisplay a notification for an action that already happened. It also auto-clears after 6 seconds (`FLASH_MESSAGE_DURATION_MS`) via a plain `setTimeout` effect. If a second caller ever needs the same pattern, this is the point to extract a shared hook - one caller doesn't justify that abstraction yet.

---

## Patients

Sprint 3.5, Issue #127: the first patient management UI, built directly against the Patient CRUD API from Issue #126 (`docs/api.md`'s `/patients` endpoints).

Five routes, five pages:

- `PatientsPage` (`/patients`): search, a "+ New patient" action, and the full active patient list. `usePatients` (`src/hooks/usePatients.ts`) fetches the list on mount (`{ patients, isLoading, error, retry, archivePatient }`, the same shape `usePatientMedications`/`usePatientAnalyses`/`usePatientClinicalDocuments` all use) and exposes `archivePatient`, which updates local state directly on success rather than refetching. As of Sprint 3.5 (Issue #132), `DashboardPage` calls this exact same hook - see Dashboard above - rather than adding a second patient-fetching hook or duplicating the request.
- `NewPatientPage` (`/patients/new`): renders `PatientForm`, calls `createPatient` (`api/patients.ts`) directly on submit, and navigates to the new patient's overview on success.
- `PatientOverviewPage` (`/patients/:patientId`): the patient's central workspace. Top to bottom: a breadcrumb, identity/demographic display (`PatientDetails`) with Edit/Archive actions, a Quick Actions bar ("Upload document", "Manage medications"), a Clinical Documents section, a Recent Analyses preview, and the Medications section (see Medications below). The Clinical Documents and Recent Analyses sections were added/restructured in Sprint 3.5 Issue #131 - see Clinical Documents below and Analyses above. `usePatient(patientId)` (`src/hooks/usePatient.ts`) fetches the single record; a 404 for a nonexistent or not-owned patient surfaces through the normal `error` state; there's no separate "not found" UI, since the backend's `"Patient not found"` detail already reads correctly as an error message.
- `EditPatientPage` (`/patients/:patientId/edit`): the same `usePatient` fetch, `PatientForm` prepopulated via a `toPayload(patient)` conversion, calls `updatePatient` on submit, and navigates back to the overview on success. `status` is never read from or written to the form - the backend already ignores it on `PATCH`, so this is enforced by `PatientPayload` simply not including the field, not by any extra client-side guard.
- `PatientMedicationsPage` (`/patients/:patientId/medications`): the full medication list and add-form for one patient - see Medications below.

`NewPatientPage` and `EditPatientPage` don't use `usePatients`' list state at all: each is a full route change away from `/patients`, so there is nothing to keep in sync with a list array that's about to unmount anyway. Create/update are one-shot calls to `api/patients.ts`, matching how `MedicationForm`/`MedicationCard` own their own submit/error state per action.

`src/components/patients/`:

- `PatientForm`: shared by Create and Edit. Unlike `MedicationForm`, it never clears itself after success, since both callers navigate away entirely rather than staying on the page to add another.
- `PatientFields`: the shared input set (first name, last name, date of birth, MRN, notes), rendered by `PatientForm`. Date of birth uses a native `<input type="date">`, whose value is already an ISO `YYYY-MM-DD` string, exactly what the backend expects, with no conversion needed.
- `patientFormValidation.ts`: mirrors `schemas/patient.py` exactly - first name, last name, and date of birth are required; MRN and notes are optional.
- `PatientCard` / `PatientList`: one row per patient (name, DOB, MRN if present) with View/Edit/Archive actions; unlike `MedicationCard`, there's no inline edit mode, since Edit is a full route here. Two optional props added in Sprint 3.5 (Issue #132), both defaulting to `false` so `PatientsPage`'s own cards are unaffected - `showStatus` (adds a `patientStatusLabel`-driven "Status: Active" stat) and `showUpdatedAt` (adds an "Updated: {date}" stat, omitted entirely when `updated_at` is `null`) - used by `DashboardPage`'s Recent Patients preview; see Dashboard above.
- `PatientSearch` / `filterPatients.ts`: the backend's `GET /patients` has no search parameter, so filtering is client-side, case-insensitive, over first name, last name, full name, and MRN. `filterPatients` is a pure function (returns a new array, never mutates `patients`), kept separate from the page so it's unit-testable on its own. Reused as-is by `DashboardPage`'s search box - see Dashboard above.
- `sortPatientsByRecentActivity.ts` (Issue #132): the "recent patients" sort - see "Recent patient strategy" under Dashboard above.
- `EmptyPatientState`: distinguishes "no patients yet" (a create CTA) from "a search matched nothing" (a plain sentence, no CTA) via a boolean prop rather than being two separate components.
- `PatientDetails`: the Overview page's identity/demographic card, reusing `SummaryStat` for each label/value pair exactly as `RecentAnalysisCard` does.
- `ArchivePatientDialog`: the app's first dialog. Built on the native `<dialog>` element (`showModal()`/`close()`) rather than a hand-rolled overlay - see Accessibility below.
- `PatientBreadcrumb` / `PatientPageNav` (Issue #158): see Patient breadcrumb navigation, above.

### Clinical Documents

Sprint 3.5, Issue #131 first added a real document management section on `PatientOverviewPage`, replacing the placeholder line that used to sit there. `usePatientClinicalDocuments(patientId)` (`src/hooks/usePatientClinicalDocuments.ts`) fetches the patient's documents via `listClinicalDocuments` (`api/clinicalDocuments.ts`, `GET /patients/{patientId}/clinical-documents`) and exposes `{ documents, isLoading, error, retry, removeDocument }`, the same shape as the other patient-scoped hooks; `removeDocument` calls `deleteClinicalDocument` (`DELETE /patients/{patientId}/clinical-documents/{documentId}`).

**Issue #146 split this into two distinct views**, matching how Analyses already works (a glance-and-go preview on Overview, a full browsable history on its own page):

- **Recent Clinical Documents** (`PatientOverviewPage`, unchanged route): a compact preview - the 3 most recent documents (`documents.slice(0, RECENT_DOCUMENTS_PREVIEW_LIMIT)`), each a `RecentDocumentCard`/`RecentDocumentsList` (`src/components/documents/`) showing title/type/date, clickable to expand inline and read the document's extracted text (the same interaction `ClinicalDocumentCard`'s "View" offers, just without a separate Delete action here - see below). The backend's `GET /patients/{patientId}/clinical-documents` has no `limit` query parameter (unlike analyses' `?limit=`), so the 3-most-recent cut is applied client-side against the same full list the hook already fetches, rather than a backend change - see Backend below. A "View All" link to `patientDocumentsPath(patientId)` appears next to the section heading, but only once there is at least one document to view (an empty patient shows `EmptyDocumentsState` instead, with nothing to page through).
- **Clinical Documents page** (new, `PatientDocumentsPage`, `src/pages/PatientDocumentsPage.tsx`, `/patients/:patientId/documents`): the complete, unpaginated document history, sorted most-recent-first (the backend's own `ORDER BY created_at DESC`, not re-sorted client-side). This is where full document management (including delete) actually happens - the full `ClinicalDocumentCard`/`ClinicalDocumentList` that used to live directly on Overview now lives here instead. Three page-level actions sit in a `<nav aria-label="Document actions">`: "Upload Documents" (`patientUploadPath`), "Create Analysis" (`createAnalysisPath` - see Create Analysis above), and "View Patient" (`patientDetailPath`).

`src/components/documents/`:

- `ClinicalDocumentCard`: title, document type label (`documentTypeLabel`, moved from a private helper inside `NoteCard` into `api/clinicalDocuments.ts` so both consumers share one lookup instead of two copies), creation date, a file-type label ("Pasted note" / "Uploaded .txt file" / "Uploaded .pdf file" / "Uploaded .csv file" (Issue #164), read off `file_type`), and, as of Issue #146, an analysis-count label ("Not yet analyzed" / "Used in `N` analyses") in the subtitle. "View" toggles an inline expand/collapse (`aria-expanded`, `aria-controls`) showing the document's `raw_text` - not a modal, and not a PDF preview: the backend only ever stores the extracted text (`raw_text`), never the original uploaded file bytes, so there is no file to preview or download, and no real byte size to show either (see Backend below). Building a fake "Download original PDF" action would be exactly the invented functionality the issue warns against; showing the real extracted text is the honest equivalent. "Delete" mirrors `MedicationCard`'s pattern (own loading/error state, calls `onDelete`, parent hook updates local state on success).
- `ClinicalDocumentList`: a semantic `<ul>` of `ClinicalDocumentCard`s - used only by `PatientDocumentsPage` now.
- `RecentDocumentCard` / `RecentDocumentsList` (Issue #146): the compact preview cards for Overview, mirroring `RecentAnalysisCard`/`RecentAnalysesList`'s "preview card, not the full one" relationship. The whole card is a `<button aria-expanded aria-controls>` (not a `<Link>`, since there is no separate document-detail route) toggling the same inline `raw_text` view `ClinicalDocumentCard` shows, with no Delete action - that stays on `PatientDocumentsPage`.
- `EmptyDocumentsState`: "No documents uploaded" plus a link to this patient's Upload page - mirrors `AnalysesEmptyState`'s shape rather than `EmptyMedicationState`'s plain-text form, since (unlike Medications) there is no inline add-form directly below it to point at instead. Reused as-is by `PatientOverviewPage`'s preview, `PatientDocumentsPage`'s full view (Issue #146), and `CreateAnalysisPage`'s Existing Documents section (Issue #145, renamed in Issue #160 - see Create Analysis above) - the one place it's now reused alongside a working alternative (the same page's own Upload Additional Documents section) rather than as a dead end.

#### Backend (Issue #146)

The issue asked for an analysis count and file size per document. Reviewing the existing `ClinicalDocument` model found an `analyses` relationship already present (the same many-to-many `analysis_clinical_documents` table `Analysis.clinical_documents` uses) but never exposed over the API - so a small, additive change was made: an `analysis_count` property on the model (`len(self.analyses)`, the same pattern as `Analysis.document_count` from Issue #45) and a matching `analysis_count: int` field on `ClinicalDocumentResponse`. `get_clinical_documents_for_patient`/`get_clinical_document` now `selectinload(ClinicalDocument.analyses)` to avoid an N+1 query. No route code changed - both routes already return the ORM object directly under a Pydantic `response_model`, which picks up the new property automatically. See `docs/api.md`.

File size is **not** included, and never will be without a larger, unrelated change: the backend has never stored the original uploaded file's bytes, only the extracted `raw_text` (already noted above and in Issue #45's own investigation) - there is no byte count anywhere to expose honestly, so the UI simply omits it rather than substituting `len(raw_text)` or another number that isn't actually "file size."

### Quick Actions and the "Create Analysis" question

`PatientOverviewPage`'s Quick Actions bar (a `<nav aria-label="Quick actions">`) has two entries: "Upload document" (`patientUploadPath`) and "Manage medications" (`patientMedicationsPath`). The issue's own recommended layout listed a third, separate "Create Analysis" action - deliberately not added, because at the time it would have had nowhere distinct to go: creating an analysis only happened by selecting documents on `UploadPage` (see Upload above), the same destination "Upload document" already linked to. A second button with a different label pointing at the identical route would have been exactly the "duplicate button" the issue warns against, not two real actions. Building a second, independent "create an analysis from documents already on file" flow (which would need its own document-selection UI) was treated as new functionality beyond that issue's "connect what exists" scope, not a gap it asked to close.

**Issue #145 closed that gap** with `SelectDocumentsPage`, and **Issue #146 moved its entry point again**: first added to the Clinical Documents section header on Overview (Issue #145), then relocated to `PatientDocumentsPage`'s own action row once that dedicated page existed (Issue #146), keeping the Overview preview compact and putting every document-related action in one place - see Clinical Documents above. Quick Actions itself remained unchanged through both of those issues, still just "Upload document" and "Manage medications" - the original reasoning above (a second button pointing at the same destination is not two real actions) still held, because "Create Analysis" and "Upload document" still led to two genuinely different, non-overlapping destinations (`SelectDocumentsPage` vs. `UploadPage`) rather than one page that could do both.

**Issue #160 is what finally resolves this.** Once analysis creation was unified onto one page (`CreateAnalysisPage` - see Create Analysis above) that can build an analysis from existing documents, newly uploaded ones, or both, "Create Analysis" and "Upload document" stopped being two paths to the same thing and became two genuinely different actions again - upload document now only saves documents (see Upload above), while Create Analysis is the actual "build and start an analysis" action. Quick Actions now has three entries: **Create Analysis** (`createAnalysisPath`, primary/blue - the main value-generating action), **Upload document** (`patientUploadPath`, now secondary/outline), and **Manage medications** (unchanged). This is the same non-duplication principle the original issue set, just re-evaluated now that the underlying pages are no longer identical destinations.

### Archiving

`DELETE /patients/{patient_id}` is a soft delete (sets `status: "archived"`, never removes the row), and the UI's copy is deliberate about that: the confirmation dialog says the patient is "removed from your active patient list," never "deleted." Archiving is reachable from both `PatientsPage` (removes the card from view) and `PatientOverviewPage` (navigates back to `/patients` on success, since there's nothing left to show). Both pages own their own `patientPendingArchive`/`isArchiving`/`archiveError` state around the one shared `ArchivePatientDialog`, rather than that state living in a hook - it's page-local UI state, not data the rest of the app needs.

No toast/notification component exists anywhere in this codebase yet, so "success feedback" (per the issue) is the immediate UI change itself - the card disappearing from the list, or the redirect back to a list that no longer contains the archived patient - the same feedback pattern every other remove/delete action in this app already uses (`MedicationCard`, `NoteCard`, `UploadedFileList`). This is a deliberate reading of the issue's "if one exists" hedge, not an oversight. Note that archiving a patient never touches their medications, documents, or analyses - it only changes the patient's own `status`, and every one of those child resources stays fully reachable directly, exactly as before.

### Not Implemented Yet (Patients)

- Searching or viewing archived patients (once archived, a patient is only reachable by its direct URL, not through any list).
- Un-archiving.

---

## Medications

Sprint 3.5, Issue #129: medication management moved from a standalone `/medications` page to living entirely within a patient's context - `POST/GET/PATCH/DELETE /medications` became `POST/GET/PATCH/DELETE /patients/{patient_id}/medications` on the backend (`docs/api.md`), and there is no longer any route, page, or nav link that lists medications without a patient already selected.

Two places medications now appear:

- `PatientMedicationsPage` (`/patients/:patientId/medications`): the full CRUD experience - reads `:patientId` from the route, fetches the patient (`usePatient`, for the page title and a "← Back to {name}" link) and their medications (`usePatientMedications`), and renders the add form plus the full list. This is almost exactly the old `MedicationsPage`, just patient-scoped.
- `PatientOverviewPage`'s Medications section: the same list (view/edit/delete inline, reusing `MedicationList`/`MedicationCard` directly, `usePatientMedications` called a second time with the same `patientId`) plus a "+ Add medication" link into `PatientMedicationsPage`. Deliberately does *not* embed `MedicationForm` a second time - having two separate places a medication could be created would fragment the UI, so Overview only ever links out to the one page that owns the add form.

`usePatientMedications(patientId)` (`src/hooks/usePatientMedications.ts`, renamed from `useMedications`) fetches on mount and re-fetches whenever `patientId` changes, so navigating from one patient's medications to another's never shows stale data. It exposes `addMedication`/`editMedication`/`removeMedication`, each threading `patientId` through to `api/medications.ts` and then updating local state directly from the response rather than refetching - the same shape `useMedications` always had, just parameterized. These three functions still don't catch their own errors; the calling component owns its own submitting/error UI, unchanged from before. A fourth function, `importMedicationsCsv`, was added for CSV import - see below.

Every component in `src/components/medications/` (`MedicationForm`, `MedicationFields`, `MedicationCard`, `MedicationList`, `EmptyMedicationState`, `medicationFormValidation.ts`) is reused completely unchanged in behavior - none of them ever knew about `user_id` or ownership at all, so threading `patientId` through the hook and API layer was enough on its own. The one small addition is an optional `message` prop on `EmptyMedicationState` (default preserves its original copy), so `PatientOverviewPage` can show "No medications recorded yet." instead of the original "...use the form below" copy, which would otherwise be inaccurate there (the add form lives on a different page in that context).

Validation (`medicationFormValidation.ts`) is unchanged: mirrors `schemas/medication.py` exactly - `medication_name`, `dose`, `route`, `frequency`, and `status` must all be non-empty; `notes` is optional. `source` is still hardcoded to `"patient_reported"` in `api/medications.ts`, never user-facing.

### CSV import

Built directly against the patient-scoped `POST /patients/{patient_id}/medications/import` endpoint from Issue #129 (`docs/api.md`). `MedicationCsvUpload` (`src/components/medications/MedicationCsvUpload.tsx`) is a dedicated, always-visible section on `PatientMedicationsPage`, between the medication list and the single-add `MedicationForm` - not a modal or collapsible, since the page already establishes "always-visible form below the list" as its interaction pattern (`MedicationForm`), and CSV import is just another way of adding medications. It is not shown on `PatientOverviewPage`.

The page passes it `importMedicationsCsv` (from `usePatientMedications(patientId)`) as a prop, the same way it passes `addMedication` to `MedicationForm` - the component never calls the hook itself, so there is exactly one medication-list state per page, not two.

Required headers (`app/services/medication_import_service.py`): `medication_name`, `dose`, `route`, `frequency`, `status`, `source`; `notes` is optional. The component states these inline and offers "Download a sample CSV" (`sampleMedicationCsv.ts`), which generates the file entirely client-side (`Blob` + `URL.createObjectURL`, no backend request) using only synthetic example rows - the same two-row example already used in `docs/api.md`.

Client-side validation is intentionally lightweight: require a file, reject anything that isn't `.csv`/`text/csv`, reject an empty file. The backend's actual row-by-row CSV parsing and validation is never reproduced in the browser - it remains the sole source of truth for whether a given row is valid.

Not to be confused with CSV support in Create Analysis (Issue #164, see "CSV medication list uploads" under Upload above): `MedicationCsvUpload` here imports rows directly into the medication list through its own dedicated drop target (deliberately not the shared `FileDropzone`), while `CreateAnalysisPage`/`UploadPage`'s `FileDropzone` accepting a `.csv` stores it as an ordinary analysis document instead. The two components, hooks, and API calls are entirely separate - nothing is shared beyond both accepting a `.csv` file.

**Import result handling**: the response (`MedicationImportSummary`: `rows_processed`, `medications_created`, `blank_rows_ignored`) has no created-medication objects to merge into local state, so `usePatientMedications`'s `importMedicationsCsv` triggers a refetch (bumping the same internal `retryCount` `retry()` already uses) rather than trying to synthesize new rows locally. A successful import shows a `role="status"` message with the counts and clears the selected file; a failed one keeps the file selected (so the user doesn't have to reselect it to retry) and shows a `role="alert"`.

**File-level vs. row-level errors**: the CSV import endpoint is the only one in this app whose `422` `detail` is neither a plain string nor FastAPI's usual list of field errors, but a nested object (`{ message, row_errors }`). The shared `ApiError` normalization (`api/client.ts`) previously discarded this - it fell through to a generic "Request failed" message. Fixed by adding one more case to `toApiError` that recognizes an object-shaped `detail` with a `message` field and preserves the *whole* raw `detail` on a new optional `ApiError.detail`. `importMedicationsCsv` (`api/medications.ts`) checks `detail` for `row_errors` and, if present, attaches them as `rowErrors` on the thrown error, letting `MedicationCsvUpload` render a summary message plus a per-row list (row number preserved) distinctly from a plain file-level error - which has no `rowErrors` and renders as just the message.

Only one file at a time: the file input has no `multiple` attribute, which is sufficient on its own (no extra code needed). No drag-and-drop - a plain `<input type="file">` is already fully keyboard-operable, and the issue this was built from explicitly calls for drag-and-drop only where it's "genuinely simpler," which a single required file input isn't.

---

## Settings

`SettingsPage` (`/settings`, `src/pages/SettingsPage.tsx`) is the account-level counterpart to the patient-scoped pages above: a single page under `ProtectedLayout`, linked from `TopNav`, with no patient context. It renders four `Card`s in a vertical stack - Profile, Appearance, Accessibility, About - each a self-contained section, not a tab set, so there's nothing to route or deep-link to within the page itself.

### Profile

`ProfileSettings` (`src/components/settings/ProfileSettings.tsx`) edits First Name, Last Name, and Email Address against the real backend, and shows (but disables) a Username field the backend has no concept of - see "Backend gap: Username and a real first/last name split" below.

The backend `User` model (`backend/app/models/user.py`) has only `email` and a single optional `name` string - no `first_name`/`last_name` columns. `profileFormValidation.ts`'s `splitName`/`joinName` bridge that gap entirely client-side: `splitName` takes the first whitespace-separated word as "First name" and everything after it as "Last name" (so "Ann Marie Mathew" round-trips as `firstName: "Ann"`, `lastName: "Marie Mathew"`, not silently dropping the middle name); `joinName` reverses it with a single space before saving. This is a deliberate, disclosed heuristic over one real column, not two real fields - the alternative (adding real `first_name`/`last_name` columns) was treated as backend work out of scope for this issue (see below), consistent with "if backend endpoints don't exist, build the frontend and document what's required, don't invent fake persistence."

Saving calls the new `PATCH /users/me` (`updateUser`, `src/api/auth.ts`) and, on success, pushes the returned `User` into `AuthContext` via a new `setUser` (`AuthProvider.tsx`) - the same context `TopNav`'s "Welcome back, {name}" and the Dashboard's `PageHeader` already read, so a name change is reflected everywhere immediately, with no second `GET /users/me` and no page reload. A changed email that collides with another account surfaces the backend's `409` attached to the Email field specifically (mirroring `SignupPage`'s existing 409-to-field pattern); every other failure is a generic form-level `FormError`. Validation (`validateProfileForm`) mirrors the app's established per-form pattern (`patientFormValidation.ts`, `SignupPage`'s inline `validate`): First Name, Last Name, and Email are required, Email must additionally pass `isValidEmail` (`src/utils/validation.ts`).

**Backend gap: Username and a real first/last name split.** There is no `username` column, uniqueness constraint, or route anywhere in the backend - accounts are identified by email only. `ProfileSettings` renders the field anyway (disabled, `placeholder="Not available yet"`, with an inline caption explaining why) rather than omitting it, since the issue's field list explicitly asked for it; nothing is submitted for it, and no request pretends it was saved. To make Username and a real (non-heuristic) first/last name split actually work would require: two new `User` columns (`first_name`, `last_name`) or one (`username`) with a uniqueness constraint mirroring `email`'s, an Alembic migration, `UserUpdate`/`UserResponse` schema updates (`backend/app/schemas/user.py`), and a small service-layer change to `update_user` (`backend/app/services/user_service.py`) to validate and persist the new column(s) the same way it already does for `email`. None of that exists today.

### Appearance

`AppearanceSettings` (`src/components/settings/AppearanceSettings.tsx`) is a two-step picker over `useTheme()` (see Theming below): a **Palette** grid (7 options - `PALETTE_OPTIONS`, `ThemeContext.ts`) and, independently, a **Mode** toggle (Light / Dark / High Contrast / System - `MODE_OPTIONS`). The two are genuinely independent state (`palette`, `modePreference`) - picking a different palette never changes the current mode and vice versa, so "Twilight, but in Dark" and "Twilight, but High Contrast" are just two clicks from any starting point, not two separate named themes to hunt for in one long list.

Each palette card's swatch (`PALETTE_PREVIEWS`, a small hardcoded lookup table in the component - the one deliberate exception to "consume tokens, not raw colors," since a picker's whole job is showing colors that are *not* currently active) re-renders using whichever mode is presently selected, so the grid always shows what choosing that palette would actually look like right now, not a fixed thumbnail.

### Accessibility

Currently a placeholder `Card` pointing at the High Contrast mode under Appearance (see Theming's Accessibility notes below) as the accessibility control that exists today. No reduced-motion or text-size controls are implemented; the section exists so Settings has a stable place to add them later without restructuring the page.

### About

A static `Card` restating the application's synthetic-data-only scope. No data, no props, nothing to test beyond that it renders.

---

## Theming

Every color in the app is a CSS custom property, switched by setting `data-theme="{palette}-{mode}"` on `<html>`. No component ever branches on which theme is active (`if (theme === ...)`) - everything flows through Tailwind utility classes generated from those custom properties, so adding a theme never touches component code, and the ~60 components across the app that render color at all consume exactly the same token vocabulary regardless of which of the 21 themes is currently applied.

### The token system

Tailwind v4 has no JS config file; tokens are declared with an `@theme inline` block in `src/styles/themes.css`:

```css
@theme inline {
  --color-background: var(--background);
  --color-surface: var(--surface);
  /* ...one line per token */
}
```

`inline` is what makes this dynamic: it tells Tailwind to generate each utility (`bg-surface`, `text-foreground`, `outline-focus-ring`, ...) as a direct reference to the underlying custom property (`background-color: var(--surface)`) rather than resolving it once at build time. The custom properties themselves are defined separately, under `:root` (the default theme) and one `:root[data-theme="..."]` block per other theme, each redefining the same fixed set of names to different values. Switching `data-theme` therefore changes what every already-generated utility class resolves to, with no re-render, no class-name swapping, and no JS-driven style computation anywhere.

### Semantic tokens

| Token | Utility classes | Used for |
|---|---|---|
| `background` / `foreground` | `bg-background`, `text-foreground` | Page background; primary body/heading text |
| `surface` / `surface-hover` | `bg-surface`, `bg-surface-hover` | Card and control backgrounds; their hover state |
| `border` | `border-border` | Card, input, and divider borders |
| `muted` | `text-muted` | Secondary/description text |
| `primary` / `primary-hover` / `primary-foreground` | `bg-primary`, `hover:bg-primary-hover`, `text-primary-foreground` | The solid-fill `Button`, the "+ New Analysis" action, active nav state |
| `secondary` / `secondary-foreground` | `bg-secondary`, `text-secondary-foreground` | The "AI-generated" badge (`AnalysisDetailPage`) - the one place today that reaches for a second accent distinct from `primary` |
| `link` / `link-hover` | `text-link`, `hover:text-link-hover` | Inline text links (may differ from `primary` - e.g. Dark/Twilight need a brighter shade to read directly on a dark background than a button fill does) |
| `focus-ring` | `outline-focus-ring` | Every `:focus-visible` state, including the one global rule in `globals.css` |
| `success` / `warning` / `danger` / `info` (+ `-foreground`) | `text-success`, `bg-success/10`, ... | Plain-text status usage: form/API errors (`FormError`), success confirmations, "Remove"/"Archive" action links - anywhere the color has to stay legible directly against the page/card background |
| `success-badge` / `warning-badge` / `danger-badge` / `info-badge` / `badge-foreground` | `bg-success-badge text-badge-foreground`, ... | Solid-fill status badges (`AnalysisStatusBadge`, `DiscrepancySeverityBadge`, `ResolutionStatusBadge`) - see below for why these are separate from `success`/`warning`/`danger`/`info` above |
| `header` / `header-foreground` | `bg-header`, `text-header-foreground` | `TopNav` |
| `sidebar` / `sidebar-foreground` | `bg-sidebar`, `text-sidebar-foreground` | Reserved - nothing in the app renders a literal sidebar today; defined for every theme so a future layout change doesn't need a theming pass of its own |

"Cards," "Buttons," and "Inputs" from the original token wishlist aren't separate values - a card is `surface` + `border`, a button is `primary` + `primary-foreground`, an input is `surface` + `border` + `foreground` + `focus-ring`. "Badges" *is* a separate pair of tokens (`*-badge` + `badge-foreground`) - see the next section for why a single `success`/`bg-success/15` pattern (the original approach) couldn't serve both a badge and plain text at once.

**Why badges need their own tokens.** `success`/`warning`/`danger`/`info` are also used as plain inline text (`FormError`, success confirmations, "Remove"/"Archive" links) directly against each palette's own page or card background - so their exact shade is constrained by "must stay legible as text on 9 different backgrounds," which forces them dark and comparatively muted in every Light and every High Contrast theme (a genuinely bright, saturated green literally cannot pass 4.5:1 as text on a near-white background - the two facts are physically incompatible, not a design oversight). A badge is different: its fill only ever has to contrast against its own paired text (`badge-foreground`), never against the page, so it's free to be as saturated as it likes. `success-badge`/`warning-badge`/`danger-badge`/`info-badge` reuse the exact same bright colors Dark mode's `success`/`warning`/`danger`/`info` already used (`#4ade80`/`#fbbf24`/`#f87171`/`#38bdf8`), paired with black `badge-foreground` text - verified to clear AA (and comfortably AAA) with black text in every mode, including Light and High Contrast, which is what makes it possible for these five tokens to hold the exact same value in all 27 themes with no per-mode variation at all, unlike every other token in the system. `src/styles/themes.test.ts` asserts this directly from the CSS source, not just by having written it that way once.

### Palettes and modes

A theme is a `(palette, mode)` pair. 9 palettes x 3 modes = 27 themes, all defined in `src/styles/themes.css`:

| Palette | Feel | Source |
|---|---|---|
| Default | The application's own original look | - |
| Blossom | Elegant, warm, soft | Satin Sheen Gold, Burnt Umber, Silver Pink, Old Rose, Shiny Shamrock |
| Sage | Healthcare, calm, natural, minimal | Axolotl, Morning Blue, Jet Stream, Dark Vanilla, Opal |
| Twilight | Modern, calm, professional | YInMn Blue, Pale Cerulean, Languid Lavender, Ceil, Chinese Black |
| Terracotta | Warm, confident, editorial | Burnt Umber, Medium Vermilion, Sandy Brown, New York Pink, Raisin Black |
| Coastal | Fresh, modern, creative | Moonstone, English Violet, Mountbatten Pink, Ruddy Pink, Deep Taupe |
| Lavender | Relaxed, friendly, soft | Liberty, Lavender Purple, Cadet Blue, Dark Vanilla, Parrot Pink |
| Aurora | Modern, energetic, colorful, AI/technology, creative - the most vibrant palette while staying professional | Celtic Blue, Byzantine, Old Gold, Gainsboro, a lightened-from-Gainsboro background |
| Botanical | A rose/olive garden palette | Crushed Rose, Spring Olive, Tulip Bloom, Blush Petal, Deep Garden |

Each non-Default palette uses more than the one or two colors a first pass reached for: the source board's own "Surface"/"Background Accent" swatch became that palette's `surface-hover` (e.g. Sage's `surface-hover` is literally Jet Stream, Coastal's is Mountbatten Pink, Aurora's is Gainsboro itself), a different swatch became `header` (a color distinct from `surface`, so `TopNav` reads as part of the palette rather than blending into the page - Aurora's header is a pale Old Gold tint, giving its third source hue real presence even though nothing else in the token set uses it), and Terracotta's Light and Dark modes use two *different* given colors as `text`/`background` respectively (Raisin Black as the light mode's dark text; Raisin Black again, unchanged, as the dark mode's actual background - the board's own "Dark Surface" swatch used exactly as labeled) rather than deriving both computationally. Where a palette's own accent was already legible as-is against its dark-mode background (Terracotta's Sandy Brown, Twilight's YInMn Blue in High Contrast, Aurora's brightened Old Gold as its Dark-mode link color), it's used unadjusted rather than recolored to match a formula. Coastal's `primary` was shifted from a first-pass sky-blue toward teal, specifically so it stays visually distinct from `info` (also blue) rather than the two looking like the same color at different tints.

`success`/`warning`/`danger`/`info` are **identical across every palette within a mode** - one fixed value for light, one for dark, one for high-contrast, shared by all 9 palettes with zero per-palette exceptions. This was tightened after an early version let Default Light run slightly brighter than the rest, and let Blossom and Terracotta each tint one status color to match their own palette (a source-board color literally labeled "Success," a warning shifted toward gold so it wouldn't blend into Terracotta's orange-browns) - reasonable-looking in isolation, but it meant a discrepancy's severity or "Completed" badge could subtly change shade depending on which palette happened to be active. All three exceptions were removed in favor of one shared value per mode.

That still left every Light and every High Contrast theme's badges looking noticeably duller than Dark mode's, for a real reason, not an inconsistency: `success`/`warning`/`danger` also had to stay legible as *plain text* against each palette's own light background, which structurally caps how bright they can be (see "Why badges need their own tokens" above). `success-badge`/`warning-badge`/`danger-badge`/`info-badge` fix this the rest of the way: since a badge's fill never has to contrast against the page, these five tokens hold the *exact same value in all 27 themes*, not just within a mode - "Completed," and every discrepancy severity badge, now render as the literal same bright color everywhere, verified by `src/styles/themes.test.ts` rather than by eye.

Each palette's Dark and High Contrast modes were designed, not mechanically derived from Light: Dark backgrounds are the palette's own darkest given color where the board provided one dark enough to use directly (Terracotta's Raisin Black, Twilight's Chinese Black), or a new near-black tinted toward the palette's hue where it didn't; every Dark mode's `primary`/`secondary`/`link` are brightened versions of the same source colors (never the Light mode's darker shades, which would fail contrast against a dark background) - and where a palette's given accent was already light (Sage's Morning Blue, Coastal's Ruddy Pink, Lavender's Parrot Pink), that color's `-foreground` pairing is dark text, not the white every other family uses, since a light color needs dark text to read as a solid fill. High Contrast modes across every palette share the same white background/black text/AAA status-color base as Default High Contrast, so the mode's actual promise (maximum readability) never varies by palette - only `primary`/`secondary`/`link`/`focus-ring` change per palette, each darkened until white text on it clears 7:1, so High Contrast still visually reads as "that palette," just at its most legible.

### `ThemeProvider` and persistence

`ThemeProvider` (`src/contexts/ThemeProvider.tsx`) owns two independent pieces of state:

- `palette` (`PaletteName`, defaults to `'default'`)
- `modePreference` (`Mode | 'system'`, defaults to `'system'`)

`resolvedMode` is derived at render time, never stored separately: `modePreference === 'system' ? systemMode : modePreference`. `systemMode` is tracked by one permanent `matchMedia('(prefers-color-scheme: dark)')` subscription for the lifetime of the provider (not one that's added/removed as `modePreference` changes), updated only through its `change` event callback - this is what keeps the provider's effects free of the "calling setState synchronously in an effect body" pattern React's `eslint-plugin-react-hooks` purity rule flags: `resolvedMode`/`resolvedTheme` are plain derived values recomputed on every render, not state kept in sync by an effect reacting to `palette`/`modePreference`. `'system'` only ever resolves to `'light'` or `'dark'` - there is no OS-level signal for "high contrast," so that mode is always an explicit user choice.

`src/lib/themeStorage.ts` persists the two independently under separate `localStorage` keys (`medlens.theme.palette`, `medlens.theme.mode`), mirroring the minimal get/set/clear-per-value shape `tokenStorage.ts` already established for the access token. On load, each key that has a valid stored value wins; a missing or unrecognized value (e.g. a key from a since-renamed palette) falls back to the same defaults as first load, never throws.

### Accessibility

- Every theme targets WCAG AA (4.5:1 for text, 3:1 for large text/UI components); every High Contrast mode targets AAA (7:1) and was verified against it, not just AA.
- Contrast was verified computationally (a small WCAG relative-luminance script, not eyeballed) for every text/background and button-fill/text pairing in every theme before it was written into `themes.css` - not simply plausible-looking colors.
- Borders are the one consistent exception: light-mode borders sit around 1.5-2.6:1 against their surface, short of the 3:1 non-text-contrast guideline. This is a deliberate, app-wide tradeoff (already true of the pre-theming app, unchanged here) rather than an oversight - card and input borders are backed by additional cues (surrounding padding, the surface/background color difference, the label above an input), and the one boundary WCAG cares about most for keyboard/assistive-tech users, the focus ring, is held to the full 3:1+ standard in every theme (see below), not relaxed like decorative borders are.
- `focus-ring` clears 3:1 against both `background` and `surface` in every theme - verified, not assumed - since focus visibility was called out explicitly as something no theme may compromise on.
- Status colors (`success`/`warning`/`danger`/`info`) come from a small set of shared, pre-verified ramps (see Palettes and modes above) specifically so severity/status meaning never depends on which theme happens to be active; the badge-specific tokens (`success-badge`, etc.) go further and hold one literal value across all 27 themes with no per-mode variation at all.

---

## Shared Components

`src/components/common/`: `Button`, `Input`, `Card`, `PageHeader`, `LoadingSpinner`, `ErrorState`, `SummaryStat`, `ProtectedRoute`, `PublicOnlyRoute`, `BackButton` (Issue #158 - see Patient breadcrumb navigation above).

These are intentionally minimal, plain-props components with no variant system (no `variant`/`size` enums, no `class-variance-authority` or similar). Introducing a design system is left until there's a real, recurring need for one.

---

## Styling

Tailwind CSS v4 is used throughout, configured via the `@tailwindcss/vite` plugin (no separate PostCSS config file needed). Global styles live in `src/styles/globals.css`, which imports Tailwind and sets a small number of base styles (body background/text color, a consistent `:focus-visible` outline).

The layout (`AppLayout`, `TopNav`) uses a max-width, responsive container (`mx-auto max-w-5xl`).

---

## Responsive Design (Issue #49)

A dedicated pass to make the existing interface work well at mobile/tablet/desktop widths - deliberately not a redesign: every fix below reuses Tailwind utilities and responsive patterns already established elsewhere in the app (see Dashboard's two-column `grid grid-cols-1 lg:grid-cols-2` and `PatientCard`'s `flex flex-col sm:flex-row` card, both predating this issue), rather than introducing a new layout system.

Reusable patterns, now applied consistently app-wide:

- **Stack on mobile, row from `sm:` up**: `flex flex-col gap-N sm:flex-row sm:items-center sm:justify-between` - the app's default shape for anything pairing a label/heading with actions (`PageHeader`, `PatientCard`, the existing-document rows on `CreateAnalysisPage`). Below `sm:`, everything stacks full-width; at `sm:` and above, it goes inline.
- **`flex-wrap` on every button/action row**, rather than assuming a row of buttons always fits one line. Applied to `TopNav`'s nav row, `PageHeader`'s `actions` slot, `PatientOverviewPage`'s Edit/Archive actions and its three section "View All" rows, every card's edit-mode Save/Cancel row (`MedicationCard`, `NoteCard`), both confirmation dialogs' Cancel/Confirm row, and `RecentAnalysisCard`'s delete-error row.
- **`min-w-0` on the text side of a `heading + actions` row, paired with either `truncate` (single-line, e.g. `MedicationCard`'s medication name, `ClinicalDocumentCard`/`NoteCard`'s title, next to their Edit/Delete buttons) or `break-words` (allowed to wrap to multiple lines, e.g. `PageHeader`'s title/description, `MedicationDiscrepancyCard`'s medication name).** Flex items default to `min-width: auto` (content-based), which silently defeats both `truncate` and normal wrapping by letting the item overflow its container instead of shrinking - `min-w-0` is what actually makes either strategy work. Which of the two to use is a judgment call: `truncate` where one line is the established look and the row shouldn't grow taller (list-style cards); `break-words` where the content is already free text that's expected to span multiple lines (AI summaries, explanations, evidence quotes, form-field values).
- **`break-words` on every unbounded free-text block**, independent of the row-overflow case above - AI-generated content especially, since nothing constrains its length or guarantees spaces at convenient intervals: `AnalysisDetailPage`'s AI summary, `MedicationMentionItem`'s fields, `FollowUpQuestionsChecklist`'s descriptions, and every field on `MedicationDiscrepancyCard` (explanation, recommendation, evidence quote, "currently on the medication list" line). `SummaryStat`'s `<dd>` got the same treatment, since it renders arbitrary stat values (dose/frequency/status strings, AI counts) inside a `grid-cols-2` cell that's only ~150px wide on a phone.
- **Dialogs get an explicit gutter on narrow screens.** `ArchivePatientDialog`, `DeleteAnalysisDialog`, and `StartAnalysisDialog` are native `<dialog>` elements centered via `fixed inset-0 m-auto h-fit` (see Accessibility below) with a `max-w-sm`/`max-w-md` cap. They previously combined that cap with `w-full`, which resolves to 100% of the viewport whenever the viewport is narrower than the cap (any phone ≤384px/448px wide) - with `m-auto` centering having no leftover space to distribute, the dialog touched both edges of the screen. Changed to `w-[calc(100%-2rem)]`, which guarantees a 1rem gutter on every side no matter how narrow the viewport is, while the `max-w-*` cap still applies unchanged on larger screens.
- **Every raw form control fills its container.** `Input`'s base `<input>` and `DocumentTypeSelect`'s `<select>` gained `w-full`, and the same was added directly to every raw `<textarea>` in the app (`PatientFields`, `MedicationFields`, `ManualNoteEditor`, `NoteCard`'s edit mode) - previously none of them had it, so every form control in the app rendered at the browser's intrinsic control width (effectively fixed, ~170-200px) regardless of its container, unless a page happened to wrap it in something that forced a width. This was the single most widespread gap: fixing the shared base components fixed every form at once, with no page-level changes needed.

No page was redesigned and no new components were introduced - every change above is a className addition (wrapping div/span elements already existed; nothing new was added to the DOM tree except where noted). `AnalysisProcessingPage`'s 2-stat `grid-cols-2` was reviewed and left as-is (unlike `AnalysisDetailPage`'s 3/4-stat grids, which already scale via `sm:grid-cols-3`/`sm:grid-cols-4`) - two short stats side by side don't need a breakpoint variant to stay usable at any width.

---

## Accessibility

This issue establishes baseline practices, not full WCAG compliance:

- Semantic HTML (`<header>`, `<nav>`, `<main>`, heading elements) instead of generic `<div>`s for structural roles.
- `Input` always renders an associated `<label htmlFor>`, generating an id via `useId()` when one isn't provided.
- Every interactive element (nav links, buttons) is a native `<a>`/`<button>` element, so it's keyboard-reachable and operable by default.
- A visible `:focus-visible` outline is defined once in `globals.css` and reused on custom components, rather than relying on (or removing) each browser's default.
- `LoadingSpinner` uses `role="status"` with visible text, rather than an icon-only spinner, for screen reader support.
- `ArchivePatientDialog` uses the native `<dialog>` element via `showModal()`/`close()` rather than a hand-rolled overlay, so focus trapping, Escape-to-dismiss, and focus restoration on close all come from the browser rather than custom code. `onClose` (fired for every close path) is the single place that syncs React state back to "closed," so the DOM and React state can't disagree.
- Every native-`<dialog>` component (`ArchivePatientDialog`, `DeleteAnalysisDialog`, `StartAnalysisDialog`) explicitly centers itself with `fixed inset-0 m-auto h-fit` on the `<dialog>` element itself, rather than relying on the browser's own centering. Browsers normally center a modal `<dialog>` via a UA-stylesheet `margin: auto`, but Tailwind's Preflight reset (`@import 'tailwindcss'` in `globals.css`) zeroes `margin` on every element including `<dialog>`, silently overriding that default - without this explicit centering, the dialog renders pinned to the viewport's top-left corner instead of centered (caught visually in Issue #48; `ArchivePatientDialog` had the identical latent bug and was fixed at the same time).
- `BackButton` (Issue #158) is a real `<button>`, not a styled `<span>` or `<div>`, so it's keyboard-focusable and activatable with Enter/Space by default. Its decorative "←" is wrapped in its own `aria-hidden="true"` span so the button's accessible name is exactly "Back to {label}," not "left arrow Back to {label}." `PatientBreadcrumb`'s `<nav aria-label="Breadcrumb">` plus `aria-current="page"` on the final crumb (unchanged by this issue) together satisfy "breadcrumbs use appropriate semantic navigation" and "current page is identified correctly."

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
npm run lint:fix       # eslint . --fix
npm run typecheck      # tsc -b (project-references build, no emit - see below)
npm run format         # prettier --write .
npm run format:check   # prettier --check .
npm run test           # vitest run
npm run preview        # preview a production build
```

### Quality pipeline (Issue #53): linting, type checking, formatting

Before opening a PR, run:

```bash
cd frontend
npm run lint            # ESLint - react-hooks, react-refresh, typescript-eslint recommended rules
npm run typecheck       # TypeScript - strict, no emit
npm run format:check    # Prettier - fails if any file isn't already formatted
npm run test            # Vitest
npm run build           # tsc -b && vite build - the final, authoritative check
```

`npm run lint:fix` and `npm run format` apply the auto-fixable subset of the first two (formatting and the handful of ESLint rules that support `--fix`); everything else has to be fixed by hand. These are the exact commands CI runs (see "Continuous Integration" below) - passing them locally is the same bar CI holds the branch to.

### Continuous Integration (Issue #55)

`.github/workflows/frontend.yml` runs the pipeline above automatically on every push and pull request to `main` or `develop` that touches `frontend/**` (or the workflow file itself) - a backend-only or docs-only change doesn't trigger it. It's a single `ubuntu-latest` job that checks out the repo, sets up Node 20 with `actions/setup-node`'s built-in npm cache (keyed off `frontend/package-lock.json`), runs `npm ci`, and then runs `npm run lint`, `npm run typecheck`, `npm run format:check`, `npm test`, and `npm run build` in that order - the same five package.json scripts documented above, never the underlying tools invoked directly, so there is exactly one place (`package.json`) that defines what each check does. Any one of those five failing fails the whole workflow (a step failure stops the job by default - no special configuration needed for that). There's no matrix (a single Node version is enough for an application, not a published library that needs to support a range of runtimes) and no separate cache-restore action (`actions/setup-node`'s own `cache: npm` covers it).

A red check on a PR always reproduces locally with the exact command named in that step's log - `npm run lint`, `npm run typecheck`, etc. - run from `frontend/`, per the Quality pipeline section above.

**ESLint** (`eslint.config.js`, flat config) extends `@eslint/js`'s recommended rules, `typescript-eslint`'s recommended rules, `eslint-plugin-react-hooks`'s recommended rules, and `eslint-plugin-react-refresh` (Vite's Fast Refresh boundary rule), then layers `eslint-config-prettier` last so Prettier owns 100% of formatting - ESLint never argues with Prettier over a stylistic call, and there are no formatting-motivated `eslint-disable` comments anywhere in the codebase to eliminate. There's no separate "Vite" ESLint plugin to add: `eslint-plugin-react-refresh`'s `only-export-components` rule *is* the Vite-specific check (it catches files that break Fast Refresh by exporting something other than components), and it was already configured. No `eslint-plugin-react` (the older, pre-React-17 plugin providing rules like `react/jsx-uses-react`) is installed or needed - this app uses the automatic JSX runtime (`"jsx": "react-jsx"` in `tsconfig.app.json`), which is exactly the case that plugin's own docs say to skip it for.

**TypeScript** was already configured strictly before this issue - `strict`, `noUncheckedIndexedAccess`, `noImplicitOverride`, `noUnusedLocals`, `noUnusedParameters`, and `noFallthroughCasesInSwitch` in `tsconfig.app.json`, mirrored (minus the DOM-specific settings) in `tsconfig.node.json` for `vite.config.ts`. Nothing about that strictness changed for this issue - `tsc -b` already ran clean, so `npm run typecheck` is that same project-references build made runnable on its own instead of only as half of `npm run build`. Both sub-configs already set `noEmit: true`, so this genuinely only type-checks; it writes no `.js` output (it does still write its `.tsbuildinfo` incremental-build cache to `node_modules/.tmp/`, same as `build` already did).

**Prettier** (`.prettierrc.json`: no semicolons, single quotes, 100-char print width, trailing commas) was already configured and already wired into ESLint via `eslint-config-prettier`; this issue's only formatting work was running `npm run format` once to bring every source file up to date; every file was already in agreement on style since `eslint-config-prettier` and Prettier had no material rules to add.

No new dependencies were added - every tool `lint`/`typecheck`/`format` needs was already a `devDependency`.

Tests use Vitest, React Testing Library, and `@testing-library/user-event`, configured directly in `vite.config.ts` (reusing the same `@` alias as the app) rather than a separate Vitest config file. `test.globals` is deliberately left off, matching the rest of the codebase's explicit-import convention; since that also disables React Testing Library's automatic per-test DOM cleanup (it relies on detecting a global `afterEach`), `src/test/setup.ts` wires `afterEach(cleanup)` by hand instead.

`src/test/setup.ts` also polyfills `HTMLDialogElement.showModal()`/`close()` and Escape-triggers-a-cancel-event, none of which jsdom implements (a documented jsdom limitation, not an application gap - real browsers already support all of it natively). The polyfill only toggles the `open` attribute and dispatches the same `close`/`cancel` events a real browser would, so `ArchivePatientDialog`'s own logic is exercised as-is in tests, not bypassed.

The frontend does not yet have a Docker Compose service; it currently runs directly via `npm run dev` against a backend started separately (see the root `README.md` and `infra/docker-compose.yml`).

---

## Known Dependency Advisory

`react-router-dom` currently has one open high-severity advisory ([GHSA-qwww-vcr4-c8h2](https://github.com/advisories/GHSA-qwww-vcr4-c8h2)), affecting React Router's RSC (React Server Components) mode with server actions. This application uses only the classic client-side `<BrowserRouter>`/`<Routes>` API, with no RSC, no server actions, and no data-router loaders, so this advisory's attack surface does not apply here. The installed version was chosen deliberately: every earlier `react-router-dom` release (up to 7.17.0) carries a much larger set of already-patched high-severity advisories (XSS, open redirects, unauthenticated DoS, and an arbitrary-constructor-invocation issue), all fixed by the version in use.

---

## Not Implemented Yet

The following are explicitly out of scope and left for future issues:

- Changing a finding's `resolution_status` from the UI. Issue #46 displays it (`ResolutionStatusBadge`) but added no action to change it - there is no backend endpoint to update a `MedicationDiscrepancy` today; see Analyses above.
- Persisting a follow-up question's checked state (Issue #47's `FollowUpQuestionsChecklist`) - it's local-only `useState`, reset on reload; there is no backend field to persist it to.
- A "Key clinical observations", "Mentioned conditions", or "Notable findings" section on `AnalysisDetailPage`'s AI Summary (Issue #47) - the AI response schema (`app/ai/schemas.py`) has no structured field for any of these; see Analyses above.
- A Docker Compose service for the frontend.
- Access-timestamp tracking for a truer "recently accessed" patient ordering on the Dashboard - `sortPatientsByRecentActivity` uses `updated_at`/`created_at` instead (see Dashboard above), since there is no "last opened by this provider" timestamp anywhere in this app, unrelated to Issue #157's separate Recent *Analyses* feed (which does now exist, see Dashboard above).
- Provider-level analytics or notifications (none requested, none built). Settings now exists (see Settings and Theming above).
- A real backend `username` field or a `first_name`/`last_name` column split - `ProfileSettings`' Username field is disabled and its First/Last Name split is a client-side heuristic over the single `name` column; see Settings above for exactly what backend work this needs.
- Accessibility controls beyond the High Contrast theme (reduced motion, adjustable text size) - `SettingsPage`'s Accessibility section is a placeholder for these.
