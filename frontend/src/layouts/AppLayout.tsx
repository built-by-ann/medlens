import { Outlet } from 'react-router-dom'
import { TopNav } from '@/components/layout/TopNav'

export function AppLayout() {
  return (
    <div className="min-h-screen bg-slate-50">
      <TopNav />
      <main className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
        <Outlet />
      </main>
    </div>
  )
}
