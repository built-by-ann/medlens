import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Input } from '@/components/common/Input'

describe('Input', () => {
  it('associates the label with the input via a generated id', () => {
    render(<Input label="Email" value="" onChange={() => {}} />)

    const input = screen.getByLabelText('Email')
    expect(input.tagName).toBe('INPUT')
  })

  it('generates distinct ids for multiple instances with no explicit id, so labels never collide', () => {
    render(
      <>
        <Input label="First name" value="" onChange={() => {}} />
        <Input label="Last name" value="" onChange={() => {}} />
      </>,
    )

    const firstName = screen.getByLabelText('First name')
    const lastName = screen.getByLabelText('Last name')

    expect(firstName.id).not.toBe('')
    expect(lastName.id).not.toBe('')
    expect(firstName.id).not.toBe(lastName.id)
  })

  it('uses an explicit id instead of generating one when provided', () => {
    render(<Input label="Email" id="signup-email" value="" onChange={() => {}} />)

    expect(screen.getByLabelText('Email')).toHaveAttribute('id', 'signup-email')
  })

  it('has no error styling or ARIA wiring when there is no error', () => {
    render(<Input label="Email" value="" onChange={() => {}} />)

    const input = screen.getByLabelText('Email')
    expect(input).not.toHaveAttribute('aria-invalid')
    expect(input).not.toHaveAttribute('aria-describedby')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('marks the field invalid and links it to an announced error message', () => {
    render(<Input label="Email" value="" onChange={() => {}} error="Email is required." />)

    const input = screen.getByLabelText('Email')
    const error = screen.getByRole('alert')

    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(error).toHaveTextContent('Email is required.')
    expect(input).toHaveAccessibleDescription('Email is required.')
  })

  it('passes through arbitrary input props', () => {
    render(
      <Input
        label="Email"
        type="email"
        placeholder="you@example.com"
        disabled
        value=""
        onChange={() => {}}
      />,
    )

    const input = screen.getByLabelText('Email')
    expect(input).toHaveAttribute('type', 'email')
    expect(input).toHaveAttribute('placeholder', 'you@example.com')
    expect(input).toBeDisabled()
  })
})
