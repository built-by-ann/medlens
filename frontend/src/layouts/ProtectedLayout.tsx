import { Outlet } from 'react-router-dom'
import { TopNav } from '@/components/layout/TopNav'
import { ProtectedRoute } from '@/components/common/ProtectedRoute'

export function ProtectedLayout() {
  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-background">
        <TopNav />
        <main className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
          <Outlet />
        </main>
      </div>
    </ProtectedRoute>
  )
}
