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

As of Sprint 3.5 (Issue #130), analyses are scoped to a patient, so there is no cross-patient "recent activity" feed to show on a landing page - that gap was Issue #130/#131's stopgap ("View patients" and nothing else). **Issue #132 rebuilds `DashboardPage` (`src/pages/DashboardPage.tsx`) around its actual purpose: answering "what patient do I want to work on?" rather than "what analysis recently happened?"** Analyses, documents, and medications remain entirely managed from within a patient's own pages (`PatientOverviewPage` and its children); the Dashboard never duplicates that workflow, only leads into it.

Layout, top to bottom:

1. **Welcome** - unchanged from before: `PageHeader` with `Welcome back, {name}` (or a generic "Welcome back" when the user has no name), kept lightweight.
2. **Loading / error / empty states** - `usePatients()` (the same hook `PatientsPage` already uses - see Patients below) is the *only* data fetch this page makes. A `LoadingSpinner` and `ErrorState` handle those states exactly as `PatientsPage` does; when the provider has no patients at all, `EmptyPatientState` (`hasActivePatients={false}`) shows the same "No patients yet" onboarding CTA `PatientsPage` shows - reused directly, not a second empty-state component. Search box and Quick Actions are hidden in this state, since there is nothing yet to search or act on beyond creating the first patient.
3. **Patient search** - `PatientSearch` (unchanged) feeds the existing `filterPatients` utility (`components/patients/filterPatients.ts`, from Issue #127 - client-side, case-insensitive, over first name/last name/full name/MRN, since the backend's `GET /patients` has no search parameter and this issue does not add one). Search runs live on every keystroke (no debounce needed - `filterPatients` is a synchronous, cheap array filter) and searches the *entire* loaded patient list, not just the Recent Patients preview below, so a patient outside the top 3 is still found.
4. **Recent patients / Search results** - a single `<section>` whose heading switches between "Recent patients" (search box empty) and "Search results" (search box non-empty), backed by two different views over the one `patients` array `usePatients()` already loaded - never two separate requests. Rendered with the same `PatientList`/`PatientCard` `PatientsPage` uses (see "Recent patient strategy" below for the sort, and Patients below for the components). An empty result set reuses `EmptyPatientState` again, this time with `hasActivePatients={true}` (its "No patients match your search." branch).
5. **Quick Actions** - a `<nav aria-label="Quick actions">` with two links: "+ New patient" (`ROUTES.newPatient`) and "View all patients" (`ROUTES.patients`). "Upload Document" was deliberately **not** added - every upload route is patient-scoped (`/patients/:patientId/upload`), so there is no patient-less destination for it to point at; per the issue's own instruction, the Dashboard instead encourages opening a patient first (both the search results above and "View all patients" here lead there).
6. **Recent Activity** - **omitted entirely.** No cross-patient activity feed exists in this API and this issue explicitly forbids adding an aggregate endpoint to create one; per the issue's own fallback rule ("if meaningful activity cannot be shown, omit the section entirely"), there is nothing built here, not a placeholder.

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

Selected files are validated against the backend's actual supported types (`.txt`/`text/plain`, `.pdf`/`application/pdf`, mirrored exactly from `app/api/routes/clinical_documents.py`) and de-duplicated by name+size; no file size limit is enforced, since the backend does not define one either. A pasted note's title is genuinely optional in the UI, but the backend requires a non-empty title, so an untitled note is given a generated fallback (`Note 1`, `Note 2`, ...) at submission time.

### Retrying a partially failed submission

`useCreateAnalysis` caches each item's resulting document id (`fileItemKey(id)`/`noteItemKey(id)` to a `Map`, held in a ref) as soon as it uploads successfully. If a later item then fails, calling `submit()` again with the same queue skips re-uploading whatever already succeeded and only retries what didn't, rather than creating duplicate ClinicalDocument rows. The cache lives inside the hook, not in the caller's own state, since nothing outside a submission attempt needs to read it. The cache is also cleared automatically the moment an analysis is actually created, since any submission after that is a new attempt, not a retry. `failedItemLabel` (the failing file's name, or the note's title/fallback) is exposed alongside the error message so a multi-item failure is attributable to a specific item, not just "something failed." As of Issue #44, `invalidateItem` and this retry cache live entirely on `AnalysisProcessingPage` (see below) rather than `UploadPage` - editing a file or note now only ever happens *before* any submission attempt exists, so there is nothing yet to invalidate on the upload page itself; the "Try again" action on the processing page is what re-runs `submit()` against the same queue and benefits from the cache.

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
- `useAnalysisPolling` itself returns an `error` (the status-check request failed, independent of the analysis's own status) - no "Try again" here, since resubmitting would create a duplicate analysis; the user is pointed at Analysis History instead, where the analysis (whatever its real status turns out to be) will already be listed.

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

- `ClinicalDocumentCard`: title, document type label (`documentTypeLabel`, moved from a private helper inside `NoteCard` into `api/clinicalDocuments.ts` so both consumers share one lookup instead of two copies), creation date, a file-type label ("Pasted note" / "Uploaded .txt file" / "Uploaded .pdf file", read off `file_type`), and, as of Issue #146, an analysis-count label ("Not yet analyzed" / "Used in `N` analyses") in the subtitle. "View" toggles an inline expand/collapse (`aria-expanded`, `aria-controls`) showing the document's `raw_text` - not a modal, and not a PDF preview: the backend only ever stores the extracted text (`raw_text`), never the original uploaded file bytes, so there is no file to preview or download, and no real byte size to show either (see Backend below). Building a fake "Download original PDF" action would be exactly the invented functionality the issue warns against; showing the real extracted text is the honest equivalent. "Delete" mirrors `MedicationCard`'s pattern (own loading/error state, calls `onDelete`, parent hook updates local state on success).
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

**Import result handling**: the response (`MedicationImportSummary`: `rows_processed`, `medications_created`, `blank_rows_ignored`) has no created-medication objects to merge into local state, so `usePatientMedications`'s `importMedicationsCsv` triggers a refetch (bumping the same internal `retryCount` `retry()` already uses) rather than trying to synthesize new rows locally. A successful import shows a `role="status"` message with the counts and clears the selected file; a failed one keeps the file selected (so the user doesn't have to reselect it to retry) and shows a `role="alert"`.

**File-level vs. row-level errors**: the CSV import endpoint is the only one in this app whose `422` `detail` is neither a plain string nor FastAPI's usual list of field errors, but a nested object (`{ message, row_errors }`). The shared `ApiError` normalization (`api/client.ts`) previously discarded this - it fell through to a generic "Request failed" message. Fixed by adding one more case to `toApiError` that recognizes an object-shaped `detail` with a `message` field and preserves the *whole* raw `detail` on a new optional `ApiError.detail`. `importMedicationsCsv` (`api/medications.ts`) checks `detail` for `row_errors` and, if present, attaches them as `rowErrors` on the thrown error, letting `MedicationCsvUpload` render a summary message plus a per-row list (row number preserved) distinctly from a plain file-level error - which has no `rowErrors` and renders as just the message.

Only one file at a time: the file input has no `multiple` attribute, which is sufficient on its own (no extra code needed). No drag-and-drop - a plain `<input type="file">` is already fully keyboard-operable, and the issue this was built from explicitly calls for drag-and-drop only where it's "genuinely simpler," which a single required file input isn't.

---

## Shared Components

`src/components/common/`: `Button`, `Input`, `Card`, `PageHeader`, `LoadingSpinner`, `ErrorState`, `SummaryStat`, `ProtectedRoute`, `PublicOnlyRoute`, `BackButton` (Issue #158 - see Patient breadcrumb navigation above).

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
- `ArchivePatientDialog` uses the native `<dialog>` element via `showModal()`/`close()` rather than a hand-rolled overlay, so focus trapping, Escape-to-dismiss, and focus restoration on close all come from the browser rather than custom code. `onClose` (fired for every close path) is the single place that syncs React state back to "closed," so the DOM and React state can't disagree.
- Both native-`<dialog>` components (`ArchivePatientDialog`, `DeleteAnalysisDialog`) explicitly center themselves with `fixed inset-0 m-auto h-fit` on the `<dialog>` element itself, rather than relying on the browser's own centering. Browsers normally center a modal `<dialog>` via a UA-stylesheet `margin: auto`, but Tailwind's Preflight reset (`@import 'tailwindcss'` in `globals.css`) zeroes `margin` on every element including `<dialog>`, silently overriding that default - without this explicit centering, the dialog renders pinned to the viewport's top-left corner instead of centered (caught visually in Issue #48; `ArchivePatientDialog` had the identical latent bug and was fixed at the same time).
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
npm run format         # prettier --write .
npm run format:check   # prettier --check .
npm run test           # vitest run
npm run preview        # preview a production build
```

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
- A Dashboard entry point into `CreateAnalysisPage` that lets a provider pick the patient first (Issue #160 explicitly excluded this - "design the component architecture so patient selection can be added later without redesigning this page," not build it now). Today the page only reads `patientId` from the URL (`useParams`), assuming the patient is already known, which is true for every current entry point (Overview, Analyses, Documents, all nested under `/patients/:patientId/...`). A future Dashboard-launched version would only need a patient-picker step *before* this page, not a change to the page itself - `CreateAnalysisPage` never assumes *how* `patientId` was chosen, only that it has one.
- A Docker Compose service for the frontend.
- A cross-patient "Recent Activity" feed on `DashboardPage` (Sprint 3.5, Issue #132 - no aggregate endpoint exists to back one, and this issue explicitly does not add one; see Dashboard above). Access-timestamp tracking for a truer "recently accessed" patient ordering is the same kind of gap - Dashboard's "recent patients" uses `updated_at`/`created_at` instead, since neither access tracking nor an aggregate activity API exist today.
- Provider-level analytics, settings, or notifications (none requested, none built).
