MedLens Demo Case: Jasmine Patel
=================================

Case type: Asthma / outpatient management (pediatric)

Jasmine Patel, 9, has well-documented asthma, but her rescue inhaler
frequency and controller dose have both quietly drifted away from what's
recorded on her medication list after a flare-up and a step-up in therapy.

What's included
----------------
- medications.csv        Jasmine's current medication list (import this
                          first, as-is, using "Import medications from CSV"
                          on the patient's Medications page)
- 01-office-visit-annual.txt         Well-child visit - document type: Visit note
- 02-urgent-care.txt                 Urgent care visit - document type: Visit note
- 03-specialist-followup.txt         Pulmonology visit - document type: Visit note
- 04-school-nurse-note.txt           School health note - document type: Progress note
- 05-medication-reconciliation.txt   Med rec form - document type: Medication reconciliation form

Recommended steps
------------------
1. Create a new patient named Jasmine Patel (or reuse an existing one).
2. Import medications.csv on the Medications page.
3. Upload the five documents above, in the numbered order, selecting the
   document type noted next to each one.
4. Create an analysis using all five documents.
5. Review the findings.

What this case demonstrates
----------------------------
The annual visit establishes her baseline regimen. An asthma flare
documented at urgent care leads to more frequent rescue inhaler use, which
a pulmonology follow-up addresses by increasing her controller dose. The
school nurse note and reconciliation form both confirm the new dose and
frequency - but the medication list still reflects the original values.

Expected discrepancy types
---------------------------
- Dosage mismatch: Fluticasone propionate (44 mcg on the list vs. 110 mcg
  in the notes).
- Frequency conflict: Albuterol HFA ("as needed" on the list vs. "once
  daily" in the notes).
