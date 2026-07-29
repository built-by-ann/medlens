import { Navigate, Route, Routes } from 'react-router-dom'
import { PublicLayout } from '@/layouts/PublicLayout'
import { ProtectedLayout } from '@/layouts/ProtectedLayout'
import { PublicOnlyRoute } from '@/components/common/PublicOnlyRoute'
import { HomePage } from '@/pages/HomePage'
import { LoginPage } from '@/pages/LoginPage'
import { SignupPage } from '@/pages/SignupPage'
import { DashboardPage } from '@/pages/DashboardPage'
import { AnalysisDetailPage } from '@/pages/AnalysisDetailPage'
import { AnalysisProcessingPage } from '@/pages/AnalysisProcessingPage'
import { PatientAnalysesPage } from '@/pages/PatientAnalysesPage'
import { UploadPage } from '@/pages/UploadPage'
import { PatientsPage } from '@/pages/PatientsPage'
import { NewPatientPage } from '@/pages/NewPatientPage'
import { PatientOverviewPage } from '@/pages/PatientOverviewPage'
import { EditPatientPage } from '@/pages/EditPatientPage'
import { PatientMedicationsPage } from '@/pages/PatientMedicationsPage'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { ROUTES } from '@/routes/paths'

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<PublicLayout />}>
        <Route path={ROUTES.home} element={<HomePage />} />
        <Route
          path={ROUTES.login}
          element={
            <PublicOnlyRoute>
              <LoginPage />
            </PublicOnlyRoute>
          }
        />
        <Route
          path={ROUTES.signup}
          element={
            <PublicOnlyRoute>
              <SignupPage />
            </PublicOnlyRoute>
          }
        />
      </Route>

      <Route element={<ProtectedLayout />}>
        <Route path={ROUTES.dashboard} element={<DashboardPage />} />
        <Route path={ROUTES.patients} element={<PatientsPage />} />
        <Route path={ROUTES.newPatient} element={<NewPatientPage />} />
        <Route path={ROUTES.patientEdit} element={<EditPatientPage />} />
        <Route path={ROUTES.patientMedications} element={<PatientMedicationsPage />} />
        <Route path={ROUTES.patientUpload} element={<UploadPage />} />
        <Route path={ROUTES.patientAnalyses} element={<PatientAnalysesPage />} />
        <Route path={ROUTES.patientAnalysisProcessing} element={<AnalysisProcessingPage />} />
        <Route path={ROUTES.patientAnalysisDetail} element={<AnalysisDetailPage />} />
        <Route path={ROUTES.patientDetail} element={<PatientOverviewPage />} />

        {/* Pre-Sprint-3.5 global routes: redirected rather than left as a
            bare 404, since upload and analysis detail are now nested under
            a specific patient and there is no globally-correct destination
            to render directly. */}
        <Route path={ROUTES.legacyUpload} element={<Navigate to={ROUTES.patients} replace />} />
        <Route
          path={ROUTES.legacyAnalysisDetail}
          element={<Navigate to={ROUTES.patients} replace />}
        />
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
