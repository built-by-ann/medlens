import { cn } from '@/utils/cn'

interface FormErrorProps {
  message: string
  className?: string
  // Set when another control's aria-describedby needs to point at this
  // message (e.g. FileDropzone's file-selection error), so assistive tech
  // reading that control also reads why the last action failed.
  id?: string
}

/**
 * The single shared "this form/action failed" message, previously
 * duplicated ad hoc as `<p role="alert" className="text-sm text-red-600">`
 * across Login, Signup, PatientForm, MedicationForm, MedicationCard,
 * ClinicalDocumentCard, RecentAnalysisCard, ArchivePatientDialog,
 * DeleteAnalysisDialog, UploadPage, and CreateAnalysisPage; same wording
 * convention everywhere now: role="alert" so assistive tech announces it as
 * soon as it appears, without a title (unlike ErrorState, which is for a
 * failed *page load* with something to retry; this is for a failed
 * *action*, shown right next to whatever failed).
 */
export function FormError({ message, className, id }: FormErrorProps) {
  return (
    <p id={id} role="alert" className={cn('text-sm text-danger', className)}>
      {message}
    </p>
  )
}
