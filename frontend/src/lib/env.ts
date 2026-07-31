function requireEnvVar(name: string, value: string | undefined): string {
  if (!value) {
    throw new Error(
      `Missing required environment variable: ${name}. Set it in your .env file (see .env.example).`,
    )
  }

  return value
}

export const env = {
  apiBaseUrl: requireEnvVar('VITE_API_BASE_URL', import.meta.env.VITE_API_BASE_URL),
}
