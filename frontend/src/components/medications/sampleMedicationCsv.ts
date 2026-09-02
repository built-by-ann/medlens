// Mirrors the example CSV in docs/api.md exactly, using only synthetic
// example data, never anything derived from a real patient's medications.
export const SAMPLE_MEDICATION_CSV = `medication_name,dose,route,frequency,status,source,notes
Lisinopril,10 mg,oral,once daily,active,patient_reported,Taken with breakfast
Metformin,500 mg,oral,twice daily,active,patient_reported,
`

export function downloadSampleMedicationCsv(): void {
  const blob = new Blob([SAMPLE_MEDICATION_CSV], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)

  const link = document.createElement('a')
  link.href = url
  link.download = 'medication-import-sample.csv'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}
