import { Card } from '@/components/common/Card'
import { PageHeader } from '@/components/common/PageHeader'
import { Input } from '@/components/common/Input'
import { Button } from '@/components/common/Button'

export function RegisterPage() {
  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-12">
      <div className="flex w-full max-w-sm flex-col gap-6">
        <PageHeader title="Create an account" description="Register for MedLens." />
        <Card>
          <form
            className="flex flex-col gap-4"
            onSubmit={(event) => {
              // Registration is not implemented yet; this route only
              // establishes the page structure for a future issue to wire up.
              event.preventDefault()
            }}
          >
            <Input label="Name" name="name" type="text" autoComplete="name" />
            <Input label="Email" name="email" type="email" autoComplete="email" required />
            <Input
              label="Password"
              name="password"
              type="password"
              autoComplete="new-password"
              required
            />
            <Button type="submit">Create account</Button>
          </form>
        </Card>
      </div>
    </div>
  )
}
