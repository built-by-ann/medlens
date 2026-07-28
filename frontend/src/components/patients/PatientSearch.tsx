import { Input } from '@/components/common/Input'

interface PatientSearchProps {
  value: string
  onChange: (value: string) => void
}

export function PatientSearch({ value, onChange }: PatientSearchProps) {
  return (
    <Input
      type="search"
      label="Search patients"
      value={value}
      onChange={(event) => onChange(event.target.value)}
      placeholder="Search by name or MRN"
      className="sm:max-w-xs"
    />
  )
}
