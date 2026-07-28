interface EmptyMedicationStateProps {
  message?: string
}

export function EmptyMedicationState({
  message = 'No medications added yet. Use the form below to add the first one.',
}: EmptyMedicationStateProps) {
  return <p className="text-sm text-slate-500">{message}</p>
}
