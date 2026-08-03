import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import useAuthStore from './store/authStore'
import AppLayout from './components/layout/AppLayout'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import DashboardPage from './pages/DashboardPage'
import WorkflowCreatorPage from './pages/WorkflowCreatorPage'
import WorkflowEditorPage from './pages/WorkflowEditorPage'
import WorkflowLibraryPage from './pages/WorkflowLibraryPage'
import RunMonitorPage from './pages/RunMonitorPage'
import ScheduledPage from './pages/ScheduledPage'
import ProfilePage from './pages/ProfilePage'
import LeetCodePage from './pages/LeetCodePage'

function RequireAuth({ children }) {
  const token = useAuthStore(s => s.token)
  return token ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/" element={<RequireAuth><AppLayout /></RequireAuth>}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="workflows/new" element={<WorkflowCreatorPage />} />
          <Route path="workflows/:id/edit" element={<WorkflowEditorPage />} />
          <Route path="workflows" element={<WorkflowLibraryPage />} />
          <Route path="runs/:runId" element={<RunMonitorPage />} />
          <Route path="scheduled" element={<ScheduledPage />} />
          <Route path="profile" element={<ProfilePage />} />
          <Route path="leetcode" element={<LeetCodePage />} />
        </Route>
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
