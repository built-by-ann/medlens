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
| `/patients/:patientId/upload` | `UploadPage` | `AppLayout` | yes |
| `/patients/:patientId/analyses` | `PatientAnalysesPage` | `AppLayout` | yes |
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

As of Sprint 3.5 (Issue #130), analyses are scoped to a patient (see Patients below and `docs/data-model.md`), so there is no longer a single "all of this user's recent analyses" feed to show on a global landing page. `DashboardPage` (`src/pages/DashboardPage.tsx`) was simplified accordingly: a welcome header and a single "View patients" action, with no data-fetching of its own. This intentionally does not attempt to rebuild a cross-patient view of recent activity; per-patient analysis history now lives on `PatientAnalysesPage` (see Analyses below).

`useRecentAnalyses`, `RecentAnalysisCard`/`RecentAnalysesList`, and `DashboardEmptyState` (the components this global feed used) were not deleted outright - `RecentAnalysisCard`/`RecentAnalysesList` moved to `src/components/analyses/` and are reused by `PatientAnalysesPage`, since a patient's analysis history needs the exact same card rendering, just scoped data. `DashboardEmptyState` had Dashboard-specific copy and a link to the now-removed global upload route, so it was replaced by a `patientId`-aware `AnalysesEmptyState` in the same `components/analyses/` folder instead of being adapted in place.

---

## Upload

`UploadPage` (`src/pages/UploadPage.tsx`) is nested under a patient: `/patients/:patientId/upload`. It fetches the patient via `usePatient` (the same hook `PatientOverviewPage` and `PatientMedicationsPage` use) to show the patient's name in the heading and a back link, then lets the user supply one or more clinical notes for that patient, either as files or pasted text, and creates an analysis from all of them. This is the same workflow introduced in Issue #41, adapted (not rebuilt) for Sprint 3.5 (Issue #130): `POST /patients/{patientId}/clinical-documents` (pasted text), `/patients/{patientId}/clinical-documents/upload-txt`, `/patients/{patientId}/clinical-documents/upload-pdf` (files), and `POST /patients/{patientId}/analyses` (create the analysis) replaced the old flat routes. `useCreateAnalysis(patientId)` (`src/hooks/useCreateAnalysis.ts`) now takes the patient id and threads it through that same multi-request sequence (upload every file, create every pasted note as a document, then summarize all of them, all against this one patient); `UploadPage` navigates to `analysisDetailPath(patientId, analysisId)` on success. Every document created through this flow belongs to the selected patient only - there is no global document pool to select from or accidentally mix into another patient's analysis.

`src/components/upload/`:

- `FileDropzone`: a `role="button"` drop target that is also click-to-open and keyboard-operable (Enter/Space), since drag-and-drop alone would exclude keyboard users. The actual `<input type="file">` is visually and semantically hidden (`sr-only`, `aria-hidden`, `tabIndex={-1}`) since the outer element is the one interactive control a screen reader or keyboard user sees.
- `UploadedFileList`: name, size, a per-file `DocumentTypeSelect`, and a remove button, one row per selected file.
- `ManualNoteEditor`: the "add a new note" form (optional title, required text, a `DocumentTypeSelect` defaulting to Visit note); clears itself after each add.
- `NoteCard`: a saved note, with in-place edit (including its document type) and remove.
- `DocumentTypeSelect`: a plain labeled `<select>` shared by `UploadedFileList`, `ManualNoteEditor`, and `NoteCard`'s edit mode, over the fixed vocabulary in `DOCUMENT_TYPES` (`api/clinicalDocuments.ts`): Visit note, Progress note, Discharge summary, Medication list, Medication reconciliation form. The backend's `document_type` column has no enum (plain `str`), but this is the same fixed set the reconciliation engine and product docs already use (`medication_list`/`medication_reconciliation_form` specifically get special treatment there); the user always chooses, since automatic classification is out of scope. Every file and note is keyed by a locally generated numeric id, not array index, since it's the only way per-item state (`NoteCard`'s edit mode, and the upload-retry cache below) can't end up attached to the wrong item after a removal shifts array positions.
- `UploadEmptyState`: a plain hint shown when nothing has been added yet; unlike `AnalysesEmptyState` this isn't a full-section replacement, since the upload/paste controls themselves stay visible either way.

Selected files are validated against the backend's actual supported types (`.txt`/`text/plain`, `.pdf`/`application/pdf`, mirrored exactly from `app/api/routes/clinical_documents.py`) and de-duplicated by name+size; no file size limit is enforced, since the backend does not define one either. A pasted note's title is genuinely optional in the UI, but the backend requires a non-empty title, so an untitled note is given a generated fallback (`Note 1`, `Note 2`, ...) at submission time.

### Retrying a partially failed submission

`useCreateAnalysis` caches each item's resulting document id (`fileItemKey(id)`/`noteItemKey(id)` to a `Map`, held in a ref) as soon as it uploads successfully. If a later item then fails, calling `submit()` again with the same queue skips re-uploading whatever already succeeded and only retries what didn't, rather than creating duplicate ClinicalDocument rows. The cache lives inside the hook, not in `UploadPage`'s own state, since nothing outside a submission attempt needs to read it; `UploadPage` only ever calls `invalidateItem(key)`, and only when the user edits a note's text/title/document type or changes a file's document type (a cached id would otherwise silently point at now-stale content) or removes an item outright. The cache is also cleared automatically the moment an analysis is actually created, since any submission after that is a new attempt, not a retry. `failedItemLabel` (the failing file's name, or the note's title/fallback) is shown alongside the error message so a multi-item failure is attributable to a specific item, not just "something failed."

---

## Analyses

Sprint 3.5, Issue #130: analysis history moved from a global Dashboard feed to a per-patient page, `PatientAnalysesPage` (`src/pages/PatientAnalysesPage.tsx`, `/patients/:patientId/analyses`). It fetches the patient via `usePatient` (for the heading and back link) and the patient's analyses via `usePatientAnalyses(patientId)` (`src/hooks/usePatientAnalyses.ts`), which calls `listAnalyses(patientId, limit)` (`src/api/analyses.ts`, `GET /patients/{patientId}/analyses`) and exposes the same `{ analyses, isLoading, error, retry }` shape `usePatientMedications` and the other patient-scoped hooks use.

`src/components/analyses/` (moved here from `components/dashboard/` when the Dashboard's global feed was retired):

- `RecentAnalysisCard`: one analysis, with a status badge (label text, never color alone), created/completed timestamps, the AI summary text, document count, and finding counts via `SummaryStat` (`components/common/SummaryStat`), provider/model if present. The whole card is a single `Link` to `analysisDetailPath(analysis.patient_id, analysis.id)` (using the `patient_id` now present on `AnalysisSummary` itself, rather than a prop threaded down from the page), with an explicit `aria-label` describing the date and status, since a screen reader would otherwise read every nested stat as part of the link's name.
- `RecentAnalysesList`: a semantic `<ul>` of cards.
- `AnalysesEmptyState`: explains what MedLens does and links to this patient's Upload page, shown when the patient has no analyses yet.

`AnalysisDetailPage` (`src/pages/AnalysisDetailPage.tsx`, `/patients/:patientId/analyses/:analysisId`) remains a placeholder, per Issue #130's explicit scope (no analysis results, inconsistency display, or AI summary UI) - it now reads both `patientId` and `analysisId` from the route and links back to `patientAnalysesPath(patientId)`, but otherwise renders the same "content will be added in a future issue" placeholder it did before.

---

## Patients

Sprint 3.5, Issue #127: the first patient management UI, built directly against the Patient CRUD API from Issue #126 (`docs/api.md`'s `/patients` endpoints).

Five routes, five pages:

- `PatientsPage` (`/patients`): search, a "+ New patient" action, and the active patient list. `usePatients` (`src/hooks/usePatients.ts`) fetches the list on mount (`{ patients, isLoading, error, retry }`, the same shape as `useRecentAnalyses`) and exposes `archivePatient`, which updates local state directly on success rather than refetching.
- `NewPatientPage` (`/patients/new`): renders `PatientForm`, calls `createPatient` (`api/patients.ts`) directly on submit, and navigates to the new patient's overview on success.
- `PatientOverviewPage` (`/patients/:patientId`): identity/demographic display (`PatientDetails`), a Medications section (see below), a Clinical documents and analyses section (Upload documents / View analysis history links, added in Sprint 3.5 Issue #130 - real links, not placeholders, since both destination pages exist), and Edit/Archive actions. `usePatient(patientId)` (`src/hooks/usePatient.ts`) fetches the single record; a 404 for a nonexistent or not-owned patient surfaces through the normal `error` state; there's no separate "not found" UI, since the backend's `"Patient not found"` detail already reads correctly as an error message.
- `EditPatientPage` (`/patients/:patientId/edit`): the same `usePatient` fetch, `PatientForm` prepopulated via a `toPayload(patient)` conversion, calls `updatePatient` on submit, and navigates back to the overview on success. `status` is never read from or written to the form - the backend already ignores it on `PATCH`, so this is enforced by `PatientPayload` simply not including the field, not by any extra client-side guard.
- `PatientMedicationsPage` (`/patients/:patientId/medications`): the full medication list and add-form for one patient - see Medications below.

`NewPatientPage` and `EditPatientPage` don't use `usePatients`' list state at all: each is a full route change away from `/patients`, so there is nothing to keep in sync with a list array that's about to unmount anyway. Create/update are one-shot calls to `api/patients.ts`, matching how `MedicationForm`/`MedicationCard` own their own submit/error state per action.

`src/components/patients/`:

- `PatientForm`: shared by Create and Edit. Unlike `MedicationForm`, it never clears itself after success, since both callers navigate away entirely rather than staying on the page to add another.
- `PatientFields`: the shared input set (first name, last name, date of birth, MRN, notes), rendered by `PatientForm`. Date of birth uses a native `<input type="date">`, whose value is already an ISO `YYYY-MM-DD` string, exactly what the backend expects, with no conversion needed.
- `patientFormValidation.ts`: mirrors `schemas/patient.py` exactly - first name, last name, and date of birth are required; MRN and notes are optional.
- `PatientCard` / `PatientList`: one row per patient (name, DOB, MRN if present) with View/Edit/Archive actions; unlike `MedicationCard`, there's no inline edit mode, since Edit is a full route here.
- `PatientSearch` / `filterPatients.ts`: the backend's `GET /patients` has no search parameter, so filtering is client-side, case-insensitive, over first name, last name, full name, and MRN. `filterPatients` is a pure function (returns a new array, never mutates `patients`), kept separate from the page so it's unit-testable on its own.
- `EmptyPatientState`: distinguishes "no patients yet" (a create CTA, like `DashboardEmptyState`) from "a search matched nothing" (a plain sentence, no CTA) via a boolean prop rather than being two separate components.
- `PatientDetails`: the Overview page's identity/demographic card, reusing `SummaryStat` for each label/value pair exactly as `RecentAnalysisCard` does.
- `ArchivePatientDialog`: the app's first dialog. Built on the native `<dialog>` element (`showModal()`/`close()`) rather than a hand-rolled overlay - see Accessibility below.

### Archiving

`DELETE /patients/{patient_id}` is a soft delete (sets `status: "archived"`, never removes the row), and the UI's copy is deliberate about that: the confirmation dialog says the patient is "removed from your active patient list," never "deleted." Archiving is reachable from both `PatientsPage` (removes the card from view) and `PatientOverviewPage` (navigates back to `/patients` on success, since there's nothing left to show). Both pages own their own `patientPendingArchive`/`isArchiving`/`archiveError` state around the one shared `ArchivePatientDialog`, rather than that state living in a hook - it's page-local UI state, not data the rest of the app needs.

No toast/notification component exists anywhere in this codebase yet, so "success feedback" (per the issue) is the immediate UI change itself - the card disappearing from the list, or the redirect back to a list that no longer contains the archived patient - the same feedback pattern every other remove/delete action in this app already uses (`MedicationCard`, `NoteCard`, `UploadedFileList`). This is a deliberate reading of the issue's "if one exists" hedge, not an oversight. Note that archiving a patient never touches their medications, documents, or analyses - it only changes the patient's own `status`, and every one of those child resources stays fully reachable directly, exactly as before.

### Not Implemented Yet (Patients)

- A document list view on `PatientOverviewPage` (Upload and analysis history links are there as of Issue #130; browsing/viewing a patient's individual clinical documents is a future issue).
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

`src/components/common/`: `Button`, `Input`, `Card`, `PageHeader`, `LoadingSpinner`, `ErrorState`, `SummaryStat`, `ProtectedRoute`, `PublicOnlyRoute`.

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

The following are explicitly out of scope for this issue and left for future issues:

- Real analysis detail display (`AnalysisDetailPage` is still a placeholder; `UploadPage` already navigates to it by id after creating an analysis)
- A Docker Compose service for the frontend
- A document list/selection UI on `PatientOverviewPage` or `PatientAnalysesPage` (Sprint 3.5, Issue #130 patient-scoped Upload and Analyses; a "View documents" list, the analysis results UI, and the inconsistency display UI remain future issues)
