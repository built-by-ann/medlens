import { PageHeader } from '@/components/common/PageHeader'
import { Card } from '@/components/common/Card'
import { ProfileSettings } from '@/components/settings/ProfileSettings'
import { AppearanceSettings } from '@/components/settings/AppearanceSettings'

export function SettingsPage() {
  return (
    <div className="flex flex-col gap-8">
      <PageHeader title="Settings" description="Manage your account and how MedLens looks." />

      <div className="flex flex-col gap-6">
        <ProfileSettings />
        <AppearanceSettings />

        <Card className="flex flex-col gap-2">
          <h2 className="text-lg font-semibold text-foreground">Accessibility</h2>
          <p className="text-sm text-muted">
            Dedicated accessibility controls (e.g. reduced motion, text size) are planned for a
            future release. In the meantime, the High Contrast theme under Appearance already
            targets AAA contrast - see docs/frontend.md.
          </p>
        </Card>

        <Card className="flex flex-col gap-1">
          <h2 className="text-lg font-semibold text-foreground">About</h2>
          <p className="text-sm text-muted">
            MedLens is a clinical documentation reconciliation tool for synthetic data only. It is
            not intended for use with real patient information.
          </p>
        </Card>
      </div>
    </div>
  )
}
