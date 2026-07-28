import { act, renderHook } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { ChangeEvent, FormEvent } from 'react'
import { useAuthForm } from '@/hooks/useAuthForm'

interface Values {
  email: string
  password: string
}

const initialValues: Values = { email: '', password: '' }

function noErrors(): Partial<Record<keyof Values, string>> {
  return {}
}

function fakeChangeEvent(value: string) {
  return { target: { value } } as ChangeEvent<HTMLInputElement>
}

function fakeSubmitEvent() {
  return { preventDefault: vi.fn() } as unknown as FormEvent<HTMLFormElement>
}

describe('useAuthForm', () => {
  it('starts with the given initial values and no errors', () => {
    const { result } = renderHook(() =>
      useAuthForm<Values>({ initialValues, validate: noErrors, onSubmit: vi.fn() }),
    )

    expect(result.current.values).toEqual(initialValues)
    expect(result.current.errors).toEqual({})
    expect(result.current.formError).toBeNull()
    expect(result.current.isSubmitting).toBe(false)
  })

  it('updateField updates only the targeted field', () => {
    const { result } = renderHook(() =>
      useAuthForm<Values>({ initialValues, validate: noErrors, onSubmit: vi.fn() }),
    )

    act(() => {
      result.current.updateField('email')(fakeChangeEvent('a@example.com'))
    })

    expect(result.current.values).toEqual({ email: 'a@example.com', password: '' })
  })

  it('calls preventDefault on submit', async () => {
    const { result } = renderHook(() =>
      useAuthForm<Values>({ initialValues, validate: noErrors, onSubmit: vi.fn() }),
    )
    const event = fakeSubmitEvent()

    await act(async () => {
      await result.current.handleSubmit(event)
    })

    expect(event.preventDefault).toHaveBeenCalledTimes(1)
  })

  it('does not call onSubmit when validation fails, and exposes the errors', async () => {
    const onSubmit = vi.fn()
    const validate = () => ({ email: 'Email is required.' })
    const { result } = renderHook(() => useAuthForm<Values>({ initialValues, validate, onSubmit }))

    await act(async () => {
      await result.current.handleSubmit(fakeSubmitEvent())
    })

    expect(onSubmit).not.toHaveBeenCalled()
    expect(result.current.errors).toEqual({ email: 'Email is required.' })
  })

  it('calls onSubmit with the current values when validation passes', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined)
    const { result } = renderHook(() =>
      useAuthForm<Values>({ initialValues, validate: noErrors, onSubmit }),
    )

    act(() => {
      result.current.updateField('email')(fakeChangeEvent('a@example.com'))
      result.current.updateField('password')(fakeChangeEvent('correcthorse123'))
    })

    await act(async () => {
      await result.current.handleSubmit(fakeSubmitEvent())
    })

    expect(onSubmit).toHaveBeenCalledWith({ email: 'a@example.com', password: 'correcthorse123' })
  })

  it('sets isSubmitting to true during onSubmit and false after it resolves', async () => {
    let resolveSubmit: () => void = () => {}
    const onSubmit = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          resolveSubmit = resolve
        }),
    )
    const { result } = renderHook(() =>
      useAuthForm<Values>({ initialValues, validate: noErrors, onSubmit }),
    )

    let submitPromise!: Promise<void>
    act(() => {
      submitPromise = result.current.handleSubmit(fakeSubmitEvent())
    })

    expect(result.current.isSubmitting).toBe(true)

    await act(async () => {
      resolveSubmit()
      await submitPromise
    })

    expect(result.current.isSubmitting).toBe(false)
  })

  it('resets isSubmitting to false even if onSubmit throws', async () => {
    const onSubmit = vi.fn().mockRejectedValue(new Error('boom'))
    const { result } = renderHook(() =>
      useAuthForm<Values>({ initialValues, validate: noErrors, onSubmit }),
    )

    await act(async () => {
      await expect(result.current.handleSubmit(fakeSubmitEvent())).rejects.toThrow('boom')
    })

    expect(result.current.isSubmitting).toBe(false)
  })

  it('ignores a second submit while one is already in flight', async () => {
    let resolveSubmit: () => void = () => {}
    const onSubmit = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          resolveSubmit = resolve
        }),
    )
    const { result } = renderHook(() =>
      useAuthForm<Values>({ initialValues, validate: noErrors, onSubmit }),
    )

    let firstSubmit!: Promise<void>
    act(() => {
      firstSubmit = result.current.handleSubmit(fakeSubmitEvent())
    })

    await act(async () => {
      await result.current.handleSubmit(fakeSubmitEvent())
    })

    expect(onSubmit).toHaveBeenCalledTimes(1)

    await act(async () => {
      resolveSubmit()
      await firstSubmit
    })
  })

  it('setFormError sets a form-level error message', () => {
    const { result } = renderHook(() =>
      useAuthForm<Values>({ initialValues, validate: noErrors, onSubmit: vi.fn() }),
    )

    act(() => {
      result.current.setFormError('Incorrect email or password')
    })

    expect(result.current.formError).toBe('Incorrect email or password')
  })

  it('setFieldError attaches a message to one field without touching others', () => {
    const { result } = renderHook(() =>
      useAuthForm<Values>({ initialValues, validate: noErrors, onSubmit: vi.fn() }),
    )

    act(() => {
      result.current.setFieldError('email', 'This email is already registered.')
    })

    expect(result.current.errors).toEqual({ email: 'This email is already registered.' })
  })

  it('clears the previous form-level error at the start of a new submit attempt', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined)
    const { result } = renderHook(() =>
      useAuthForm<Values>({ initialValues, validate: noErrors, onSubmit }),
    )

    act(() => {
      result.current.setFormError('Some earlier error')
    })
    expect(result.current.formError).toBe('Some earlier error')

    await act(async () => {
      await result.current.handleSubmit(fakeSubmitEvent())
    })

    expect(result.current.formError).toBeNull()
  })
})
