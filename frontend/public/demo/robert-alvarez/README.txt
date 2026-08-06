MedLens Demo Case: Robert Alvarez
==================================

Case type: Cardiology hospitalization (heart failure exacerbation)

Robert Alvarez, 74, was hospitalized for a heart failure exacerbation.
Several of his medications were changed during that admission - two doses
increased, one medication swapped for a different formulation, one
discontinued, and one new medication started - and none of it has made it
onto his outpatient medication list yet.

What's included
----------------
- medications.csv        Robert's outpatient medication list, unchanged
                          since before the admission (import this first,
                          as-is, using "Import medications from CSV" on the
                          patient's Medications page)
- 01-emergency-department.txt        ED note - document type: Visit note
- 02-hospital-admission.txt          Admission note - document type: Progress note
- 03-discharge-summary.pdf           Discharge summary - document type: Discharge summary
- 04-specialist-followup.txt         Cardiology follow-up - document type: Visit note
- 05-medication-reconciliation.txt   Med rec form - document type: Medication reconciliation form

Recommended steps
------------------
1. Create a new patient named Robert Alvarez (or reuse an existing one).
2. Import medications.csv on the Medications page.
3. Upload the five documents above, in the numbered order, selecting the
   document type noted next to each one.
4. Create an analysis using all five documents.
5. Review the findings.

What this case demonstrates
----------------------------
The ED note establishes his home medications at baseline. The admission
note and discharge summary (a real PDF) document a busy hospitalization:
Furosemide was increased, Lisinopril was newly started, Metoprolol
tartrate was switched to Metoprolol succinate, and Amlodipine was
discontinued for edema. The follow-up visit and reconciliation form
confirm all of it independently - but the outpatient medication list
still reflects his pre-admission regimen.

Expected discrepancy types
---------------------------
- Missing medication: Lisinopril and Metoprolol succinate, started during
  the hospitalization, aren't on the medication list.
- Dosage mismatch: Furosemide (20 mg on the list vs. 40 mg in the notes).
- Medication discontinued in notes: Metoprolol tartrate and Amlodipine,
  both still listed as active.
