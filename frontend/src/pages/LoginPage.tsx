import { Card } from '@/components/common/Card'
import { PageHeader } from '@/components/common/PageHeader'
import { Input } from '@/components/common/Input'
import { Button } from '@/components/common/Button'

export function LoginPage() {
  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-12">
      <div className="flex w-full max-w-sm flex-col gap-6">
        <PageHeader title="Log in" description="Sign in to your MedLens account." />
        <Card>
          <form
            className="flex flex-col gap-4"
            onSubmit={(event) => {
              // Login is not implemented yet; this route only establishes the
              // page structure and form layout for a future issue to wire up.
              event.preventDefault()
            }}
          >
            <Input label="Email" name="email" type="email" autoComplete="email" required />
            <Input
              label="Password"
              name="password"
              type="password"
              autoComplete="current-password"
              required
            />
            <Button type="submit">Log in</Button>
          </form>
        </Card>
      </div>
    </div>
  )
}
