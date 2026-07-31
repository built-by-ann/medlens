import { AxiosError, AxiosHeaders } from 'axios'
import { describe, expect, it } from 'vitest'
import { toApiError } from '@/api/client'

function makeError(overrides: Partial<AxiosError> = {}): AxiosError {
  const error = new AxiosError('Network Error')
  return Object.assign(error, overrides)
}

describe('toApiError', () => {
  it('gives a friendly message when there is no response at all (network failure, timeout, server unreachable)', () => {
    const error = makeError({ response: undefined })

    expect(toApiError(error)).toEqual({
      status: null,
      message: 'Unable to reach the server. Check your connection and try again.',
    })
  })

  it('does not leak the raw Axios message ("Network Error") for a network failure', () => {
    const error = makeError({ message: 'Network Error', response: undefined })

    expect(toApiError(error).message).not.toBe('Network Error')
  })

  it('extracts a string detail from a normal error response', () => {
    const error = makeError({
      response: {
        status: 404,
        statusText: 'Not Found',
        headers: {},
        config: { headers: new AxiosHeaders() },
        data: { detail: 'Patient not found' },
      },
    })

    expect(toApiError(error)).toEqual({
      status: 404,
      message: 'Patient not found',
      detail: 'Patient not found',
    })
  })

  it('joins a FastAPI validation-error list into one message', () => {
    const detail = [
      { loc: ['body', 'email'], msg: 'field required', type: 'value_error.missing' },
      { loc: ['body', 'password'], msg: 'ensure this value has at least 8 characters' },
    ]
    const error = makeError({
      response: {
        status: 422,
        statusText: 'Unprocessable Entity',
        headers: {},
        config: { headers: new AxiosHeaders() },
        data: { detail },
      },
    })

    expect(toApiError(error)).toEqual({
      status: 422,
      message: 'field required, ensure this value has at least 8 characters',
      detail,
    })
  })

  it('extracts a structured {message} detail (e.g. the medication CSV importer)', () => {
    const detail = { message: 'CSV import failed validation.', row_errors: [] }
    const error = makeError({
      response: {
        status: 422,
        statusText: 'Unprocessable Entity',
        headers: {},
        config: { headers: new AxiosHeaders() },
        data: { detail },
      },
    })

    expect(toApiError(error)).toEqual({
      status: 422,
      message: 'CSV import failed validation.',
      detail,
    })
  })

  it('falls back to a generic message when the response has no usable detail', () => {
    const error = makeError({
      message: 'Request failed with status code 500',
      response: {
        status: 500,
        statusText: 'Internal Server Error',
        headers: {},
        config: { headers: new AxiosHeaders() },
        data: {},
      },
    })

    expect(toApiError(error)).toEqual({
      status: 500,
      message: 'Request failed with status code 500',
    })
  })
})
