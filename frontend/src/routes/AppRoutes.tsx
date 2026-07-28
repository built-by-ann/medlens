import { Route, Routes } from 'react-router-dom'
import { PublicLayout } from '@/layouts/PublicLayout'
import { ProtectedLayout } from '@/layouts/ProtectedLayout'
import { PublicOnlyRoute } from '@/components/common/PublicOnlyRoute'
import { HomePage } from '@/pages/HomePage'
import { LoginPage } from '@/pages/LoginPage'
import { SignupPage } from '@/pages/SignupPage'
import { DashboardPage } from '@/pages/DashboardPage'
import { AnalysisDetailPage } from '@/pages/AnalysisDetailPage'
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
        <Route path={ROUTES.analysisDetail} element={<AnalysisDetailPage />} />
        <Route path={ROUTES.upload} element={<UploadPage />} />
        <Route path={ROUTES.patients} element={<PatientsPage />} />
        <Route path={ROUTES.newPatient} element={<NewPatientPage />} />
        <Route path={ROUTES.patientEdit} element={<EditPatientPage />} />
        <Route path={ROUTES.patientMedications} element={<PatientMedicationsPage />} />
        <Route path={ROUTES.patientDetail} element={<PatientOverviewPage />} />
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
