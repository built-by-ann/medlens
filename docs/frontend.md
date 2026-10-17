# Frontend

React + TypeScript SPA built with Vite. This doc covers structure, conventions, and the design choices that aren't obvious from reading the code.

## Stack

- React, TypeScript (`strict`, `noUncheckedIndexedAccess`, `noImplicitOverride`)
- Vite, Tailwind CSS v4 (`@tailwindcss/vite`)
- React Router (declarative `<BrowserRouter>`/`<Routes>`, not the data-router API)
- Axios
- ESLint (flat config) + Prettier
- Vitest + React Testing Library

## Folder Structure

```text
frontend/src/
    api/          Backend communication (the only place HTTP calls live)
    components/   common/ (shared UI), layout/, and one folder per feature
    contexts/     AuthContext, ThemeContext and their providers
    hooks/        Data-fetching and shared hooks
    layouts/      Route-level layout wrappers
    lib/          env config, token/theme storage
    pages/        Route-level pages
    styles/       globals.css, themes.css
    types/        Frontend representations of backend models
    utils/        Pure helpers
```

There is no `services/` folder; it would duplicate `api/`.

## Routing

Defined in `src/App.tsx`. Everything except `/login`, `/register`, and the 404 page is wrapped in `ProtectedRoute`, which redirects to `/login` when unauthenticated and shows a loading state while a stored session is being restored.

| Path | Page |
|---|---|
| `/dashboard` | `DashboardPage` |
| `/patients`, `/patients/new` | `PatientsPage`, `NewPatientPage` |
| `/patients/:patientId` | `PatientOverviewPage` |
| `/patients/:patientId/edit` | `EditPatientPage` |
| `/patients/:patientId/medications` | `PatientMedicationsPage` |
| `/patients/:patientId/documents` | `PatientDocumentsPage` |
| `/patients/:patientId/upload` | `UploadPage` |
| `/patients/:patientId/analyses` | `PatientAnalysesPage` |
| `/patients/:patientId/analyses/new` | `CreateAnalysisPage` |
| `/patients/:patientId/analyses/processing` | `AnalysisProcessingPage` |
| `/patients/:patientId/analyses/:analysisId` | `AnalysisDetailPage` |
| `/settings` | `SettingsPage` |

`/` redirects to `/dashboard`. Legacy `/upload` and `/analyses/:id` redirect to `/patients`.

Medications, documents, uploads, and analyses only exist inside a patient's context. There is no global "Medications" or "Upload" page or nav link.

## Navigation

Every patient-nested page renders `PatientPageNav`, which combines a `PatientBreadcrumb` (`Patients / {name} / ...`, with `aria-current="page"` on the last crumb) and a `BackButton`.

`BackButton` always goes to a fixed logical parent rather than calling `navigate(-1)`. Browser-history back was tried and rejected because it can land somewhere other than what the label promises when the user didn't arrive by a straight drill-down.

`AnalysisProcessingPage` deliberately has no Back button, since it has its own recovery links and leaving mid-submission is undesirable.

## API Layer

`src/api/client.ts` exports one Axios instance.

- The base URL comes from `env.apiBaseUrl` and is never hardcoded elsewhere.
- A request interceptor attaches `Authorization: Bearer {token}`. The token lives in a module-level variable set by `AuthProvider`, because interceptors run outside React.
- `toApiError` normalizes every failure into `ApiError { status, message, detail? }`. It handles FastAPI's string `detail`, 422 field-error lists, and the CSV importer's `{ message, row_errors }` shape. When there is no response at all (offline, CORS, timeout), it returns "Unable to reach the server..." instead of leaking Axios's `"Network Error"`.

## Authentication

- `AuthProvider` persists the token in localStorage (`lib/tokenStorage.ts`) and validates it against `GET /users/me` on load.
- A 401 on an authenticated request logs the user out silently and sets `sessionExpiredMessage`, which `LoginPage` shows once via its normal `FormError`.
- `AuthContext.ts` and `AuthProvider.tsx` are separate files so the provider file only exports a component (React Fast Refresh requirement).
- `useAuthForm` shares field/submit plumbing between Login and Signup but leaves validation and error interpretation to each page.

## Error Handling Conventions

- **`FormError`**: "this action failed" (login, save, delete, upload).
- **`AnalysisFailureNotice`**: a persisted analysis whose status is `failed`. Always labeled "Analysis failed:".
- **Field validation**: `Input` wires `aria-invalid` and `aria-describedby` to a `role="alert"` message. Buttons are not silently disabled for empty input; clicking shows why.
- **Retries**: data hooks expose `retry()` via a `retryCount` effect dependency. `useCreateAnalysis` caches successfully uploaded items by queue id, so retrying a partially failed submission doesn't create duplicate documents, and it reports which item failed (`failedItemLabel`).

## Dashboard

Answers "which patient do I want to work on?" rather than showing a global activity feed.

- **Quick Actions**: New Analysis, New patient, View all patients. New Analysis opens `StartAnalysisDialog` (a patient picker) and then hands off to that patient's `CreateAnalysisPage`.
- **Patient search**: client-side (`filterPatients`) because `GET /patients` has no search parameter.
- **Recent patients**: sorted by `updated_at ?? created_at` and capped at 3. Access time isn't tracked.
- **Recent Analyses**: the only cross-patient view in the app, backed by `GET /analyses/recent`. Read-only.

On `lg:` and up, patients and analyses sit in two columns. DOM order is unchanged, so tab order matches mobile.

## Documents and Analysis Creation

**`UploadPage` only saves documents.** It never starts an analysis. All analysis creation goes through `CreateAnalysisPage`, so there is a single workflow.

**`CreateAnalysisPage`** has three sections:

1. **Existing Documents**: a searchable checklist capped at 3 with "Show more". Search and the cap affect only what is displayed, never what is selected.
2. **Upload Additional Documents**: the same `FileDropzone`/`ManualNoteEditor` as `UploadPage`, sharing the `useDocumentQueue` hook.
3. **Selected Documents**: a combined summary with an `aria-live` count.

Submitting navigates to `AnalysisProcessingPage` with the files in router state, because `File` objects can't go in a URL. A reload loses that state, so the page shows a "Nothing to process" recovery card.

**`AnalysisProcessingPage`** calls `submit()`, then polls `GET .../analyses/{id}` until the status is terminal, and finally redirects with `replace: true`. The backend call is currently synchronous, so the first poll already sees the final state. Polling keeps the frontend correct if creation becomes async later. Retrying a *polling* error only re-checks status; it never resubmits, which would create a duplicate.

Supported upload types: `.txt`, `.pdf`, and `.csv`. A CSV uploaded here is stored as an ordinary document for the AI to read. This is unrelated to the medication **CSV import** feature (see Medications). Untitled notes get `Note 1`, `Note 2`, and so on. Document type is always user-chosen; CSVs default to "Medication list".

## Analysis Results

`AnalysisDetailPage` has two clearly separated sections:

- **AI Summary** (violet "AI-generated" badge): summary text, mentioned medications, and run metadata. There are no "conditions" or "notable findings" sections because the AI schema has no such fields, and the page never invents data.
- **Medication Reconciliation Findings** ("Deterministic" badge): summary counts computed from the rendered array, then findings grouped by severity (high/medium/low; there is no "critical" tier) and rendered as `MedicationDiscrepancyCard`s with evidence.

Headings never skip levels (h1 > h2 > h3 > h4 > h5) so screen-reader users can navigate by level.

A "Follow-up Questions" checklist built from `possible_inconsistencies` was removed. The content wasn't questions, and its checkboxes had no persisted state, which undermined trust in the real resolution actions.

### Resolving discrepancies

`getDiscrepancyActions(discrepancy)` (`utils/discrepancyResolutionActions.ts`) maps each discrepancy type to its allowed actions. The card renders whatever that function returns and never branches on type itself.

| `discrepancy_type` | Actions |
|---|---|
| `missing_from_medication_list` | Add Medication, Dismiss |
| `dose_` / `route_` / `frequency_conflict` | Update Medication (one-click accept), Edit Manually, Dismiss |
| `discontinued_status_conflict` / `status_conflict` | Mark Discontinued, Mark Active, Edit Manually, Dismiss |
| `unsupported_medication_list_entry` | Edit Manually, Dismiss |

Every action opens `ResolveDiscrepancyDialog`, including Dismiss. That dialog focuses Cancel first and accepts an optional note. On success, the updated discrepancy is spliced into local state without a refetch. Resolved cards show an audit line ("Resolved by {username ?? name ?? email} on {date}") instead of action buttons.

### Deleting an analysis

Deleting from the detail page goes through `DeleteAnalysisDialog`, which focuses Cancel first. On success it navigates to the history page with a `flashMessage` in router state. That flash banner is the app's only toast-style notification. It is cleared from history state immediately so a refresh won't replay it.

## Patients

- `PatientOverviewPage` is the patient's workspace: details, Quick Actions (Create Analysis, Upload document, Manage medications), recent documents (3), recent analyses, and medications.
- Archiving (`DELETE /patients/{id}`) is a soft delete. The UI says "removed from your active list", never "deleted". Archived patients are reachable only by direct URL, and there is no un-archive.
- There are no toasts. Success feedback is the UI change itself (the card disappears or the page redirects).

## Medications

- `PatientMedicationsPage` owns the add form, search, and CSV import. The Overview page lists medications but only links to the add form so creation lives in one place.
- Client validation mirrors `schemas/medication.py`. `source` is always `"patient_reported"`.
- **CSV import** (`MedicationCsvUpload`) posts to `/medications/import`. Client-side checks are minimal (file present, `.csv`, not empty); the backend is the source of truth. Row-level errors from `detail.row_errors` are listed per row. A successful import refetches the list.

## Settings

Profile, Appearance, Accessibility (placeholder), and About.

- The backend has a single `name` field. First/Last name is a client-side split on the first space.
- Username is optional, validated live, and sent as `null` when blank.
- A 409 is attached to the email or username field based on the message text.

## Theming

Every color is a CSS custom property. `data-theme="{palette}-{mode}"` on `<html>` switches themes, and no component branches on the active theme.

- Tokens are declared in `src/styles/themes.css` via Tailwind v4 `@theme inline`, so utilities like `bg-surface` resolve to `var(--surface)` at runtime.
- There are 9 palettes and 3 modes (light, dark, high contrast), giving 27 themes. "System" resolves to light or dark via `matchMedia`.
- Palette and mode are independent state, persisted under separate localStorage keys.
- Status text colors (`success`, `warning`, `danger`, `info`) are identical across palettes within a mode. Badge fills (`*-badge` with black `badge-foreground`) are identical across all 27 themes. They are separate tokens because a badge only has to contrast with its own text, while status text has to stay legible on every background. `themes.test.ts` asserts this.
- All themes target WCAG AA, and high contrast targets AAA, verified computationally. The focus ring clears 3:1 everywhere. Decorative borders are a known exception at roughly 1.5 to 2.6:1.

## Accessibility and Responsive Patterns

- Semantic landmarks, labeled inputs (`useId`), and native `<a>`/`<button>` everywhere.
- Dialogs use native `<dialog>` with `showModal()`. They are explicitly centered with `fixed inset-0 m-auto h-fit` because Tailwind Preflight removes the browser's default centering, and sized `w-[calc(100%-2rem)]` to keep a gutter on phones.
- Severity is never conveyed by color alone (text badges plus a colored border).
- Layout patterns: `flex-col sm:flex-row` for heading-plus-actions rows, `flex-wrap` on button rows, `min-w-0` with `truncate` or `break-words` on text in flex rows, `break-words` on all AI text, and `w-full` on all form controls.

## Shared Components and State

`components/common/` holds plain-props components (`Button`, `Input`, `Card`, `PageHeader`, `LoadingSpinner`, `ErrorState`, `SummaryStat`, `FormError`, `BackButton`, route guards) with no variant system.

Global state is React Context only (auth, theme). There is no client-side cache; hooks refetch on mount.

## Environment

| Variable | Purpose |
|---|---|
| `VITE_API_BASE_URL` | Backend base URL. Required; `lib/env.ts` throws if missing. |

`frontend/.env.example` uses `http://localhost:8000` for `npm run dev`. Docker and production use `/api` behind nginx (see [design-decisions.md](design-decisions.md), Decision 24).

## Development

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

Before a PR (CI runs the same commands from `.github/workflows/frontend.yml`, followed by a `docker build`):

```bash
npm run lint && npm run typecheck && npm run format:check && npm test && npm run build
```

Notes:

- `src/test/setup.ts` wires `afterEach(cleanup)` manually (Vitest globals are off) and polyfills `<dialog>`, which jsdom lacks. The polyfill doesn't auto-focus, which is why dialogs focus Cancel explicitly.
- Local dev uses `npm run dev`. The Compose `frontend` service serves the production nginx image on port 8080.

## Known Advisory

`react-router-dom` has an open advisory (GHSA-qwww-vcr4-c8h2) affecting RSC mode with server actions. This app uses neither.

## Not Implemented

- Viewing or un-archiving archived patients
- Access-time tracking for "recent patients"
- Reduced-motion and text-size settings
- Real `first_name`/`last_name` columns on `User`
