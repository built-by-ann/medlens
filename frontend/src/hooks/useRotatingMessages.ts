import { useEffect, useState } from 'react'

/**
 * Cycles through a fixed list of messages on a timer, wrapping back to the
 * start. Purely cosmetic - callers use this to keep a waiting UI feeling
 * alive when there is no real incremental progress to report.
 */
export function useRotatingMessages(messages: readonly string[], intervalMs: number): string {
  const [index, setIndex] = useState(0)

  useEffect(() => {
    if (messages.length <= 1) return

    const intervalId = setInterval(() => {
      setIndex((current) => (current + 1) % messages.length)
    }, intervalMs)

    return () => clearInterval(intervalId)
  }, [messages, intervalMs])

  return messages[index % messages.length] ?? ''
}
