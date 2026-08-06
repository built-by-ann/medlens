MedLens Demo Case: Dorothy Williams
====================================

Case type: Complex multi-specialty case (atrial fibrillation, chronic
kidney disease, type 2 diabetes, osteoarthritis)

Dorothy Williams, 82, sees three different specialists whose notes, taken
together, surface almost every kind of discrepancy MedLens can detect: a
discontinued medication, a new one that replaced it, and two dose changes
made during a short hospitalization.

What's included
----------------
- medications.csv        Dorothy's current medication list (import this
                          first, as-is, using "Import medications from CSV"
                          on the patient's Medications page)
- 01-office-visit-pcp.txt            Primary care visit - document type: Visit note
- 02-specialist-followup.txt         Nephrology visit - document type: Visit note
- 03-discharge-summary.pdf           Discharge summary - document type: Discharge summary
- 04-hospital-admission.txt          Admission note - document type: Progress note
- 05-medication-reconciliation.txt   Med rec form - document type: Medication reconciliation form

Recommended steps
------------------
1. Create a new patient named Dorothy Williams (or reuse an existing one).
2. Import medications.csv on the Medications page.
3. Upload the five documents above, in the numbered order, selecting the
   document type noted next to each one.
4. Create an analysis using all five documents.
5. Review the findings.

What this case demonstrates
----------------------------
A primary care visit and a nephrology consult establish that ibuprofen was
discontinued for kidney safety. A short cardiology hospitalization then
changes two more doses and adds acetaminophen in ibuprofen's place. The
discharge summary (a real PDF) and reconciliation form both confirm the
full picture - but the medication list was never updated after any of it.

Expected discrepancy types
---------------------------
- Dosage mismatch: Warfarin (5 mg on the list vs. 7.5 mg in the notes) and
  Furosemide (40 mg on the list vs. 20 mg in the notes).
- Medication discontinued in notes: Ibuprofen, still listed as active.
- Missing medication: Acetaminophen, started at discharge, isn't on the
  medication list yet.
