import { useId, type InputHTMLAttributes } from 'react'
import { cn } from '@/utils/cn'

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string
}

export function Input({ label, id, className, ...props }: InputProps) {
  const generatedId = useId()
  const inputId = id ?? generatedId

  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={inputId} className="text-sm font-medium text-slate-700">
        {label}
      </label>
      <input
        id={inputId}
        className={cn(
          'rounded-md border border-slate-300 px-3 py-2 text-sm',
          'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600',
          className,
        )}
        {...props}
      />
    </div>
  )
}
