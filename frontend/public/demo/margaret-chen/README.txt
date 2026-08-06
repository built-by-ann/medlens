MedLens Demo Case: Margaret Chen
=================================

Case type: Chronic disease management (hypertension and type 2 diabetes)

Margaret Chen, 68, is a stable primary care patient whose medication list
has fallen slightly behind two real changes made over the course of a
routine hypertension follow-up: a dose increase and a medication she
quietly stopped taking.

What's included
----------------
- medications.csv        Margaret's current medication list (import this
                          first, as-is, using "Import medications from CSV"
                          on the patient's Medications page)
- 01-office-visit-march.txt          Visit note - document type: Visit note
- 02-office-visit-june.txt           Visit note - document type: Visit note
- 03-lab-followup.txt                Phone follow-up - document type: Progress note
- 04-specialist-followup.txt         Endocrinology visit - document type: Visit note
- 05-medication-reconciliation.txt   Med rec form - document type: Medication reconciliation form

Recommended steps
------------------
1. Create a new patient named Margaret Chen (or reuse an existing one).
2. Import medications.csv on the Medications page.
3. Upload the five documents above, in the numbered order, selecting the
   document type noted next to each one.
4. Create an analysis using all five documents.
5. Review the findings.

What this case demonstrates
----------------------------
The documents describe a June office visit where Lisinopril was increased
from 10 mg to 20 mg and Amlodipine was discontinued due to leg swelling.
Two later documents (a phone follow-up and a medication reconciliation
form) independently confirm both changes. The medication list, however,
still reflects the original 10 mg Lisinopril dose and lists Amlodipine as
active - exactly the kind of drift MedLens is built to catch.

Expected discrepancy types
---------------------------
- Dosage mismatch: Lisinopril (10 mg on the list vs. 20 mg in the notes)
- Medication discontinued in notes: Amlodipine (active on the list vs.
  discontinued in the notes)
