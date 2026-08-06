// Synthetic demo datasets under public/demo/ - see each patient's own
// README.txt (included in its ZIP) for the full recommended upload order
// and what the case demonstrates. Static data, not an API concern, so it
// lives here rather than in src/api/ - nothing here calls the backend.

export interface DemoPatient {
  slug: string
  name: string
  age: number
  caseType: string
  history: string
  highlight: string
  expectedFindings: string[]
  fileCount: number
  downloadUrl: string
}

export const DEMO_PATIENTS: DemoPatient[] = [
  {
    slug: 'margaret-chen',
    name: 'Margaret Chen',
    age: 68,
    caseType: 'Chronic disease management',
    history: 'Hypertension and type 2 diabetes, managed in primary care.',
    highlight:
      'Her medication list has fallen slightly behind two real changes made during a routine hypertension follow-up: a dose increase and a medication she quietly stopped taking.',
    expectedFindings: [
      'Dosage mismatch: Lisinopril (10 mg on the list vs. 20 mg in the notes)',
      'Medication discontinued in notes: Amlodipine, still listed as active',
    ],
    fileCount: 6,
    downloadUrl: '/demo/margaret-chen/margaret-chen-demo.zip',
  },
  {
    slug: 'robert-alvarez',
    name: 'Robert Alvarez',
    age: 74,
    caseType: 'Cardiology hospitalization',
    history: 'Heart failure, hospitalized for an acute exacerbation.',
    highlight:
      'Several of his medications were changed during a heart failure hospitalization. None of it has made it onto his outpatient medication list yet.',
    expectedFindings: [
      'Missing medication: Lisinopril and metoprolol succinate, started in the hospital',
      'Dosage mismatch: Furosemide (20 mg on the list vs. 40 mg in the notes)',
      'Medication discontinued in notes: metoprolol tartrate and amlodipine',
    ],
    fileCount: 6,
    downloadUrl: '/demo/robert-alvarez/robert-alvarez-demo.zip',
  },
  {
    slug: 'jasmine-patel',
    name: 'Jasmine Patel',
    age: 9,
    caseType: 'Asthma / outpatient management',
    history: 'Pediatric asthma, managed between primary care and pulmonology.',
    highlight:
      "Her rescue inhaler frequency and controller dose have both quietly drifted away from what's recorded on her medication list after a flare-up.",
    expectedFindings: [
      'Dosage mismatch: fluticasone propionate (44 mcg on the list vs. 110 mcg in the notes)',
      'Frequency conflict: albuterol ("as needed" on the list vs. daily use in the notes)',
    ],
    fileCount: 6,
    downloadUrl: '/demo/jasmine-patel/jasmine-patel-demo.zip',
  },
  {
    slug: 'dorothy-williams',
    name: 'Dorothy Williams',
    age: 82,
    caseType: 'Complex multi-specialty case',
    history: 'Atrial fibrillation, chronic kidney disease, type 2 diabetes, and osteoarthritis.',
    highlight:
      'Three specialists, one short hospitalization, and almost every kind of discrepancy MedLens can detect in a single case.',
    expectedFindings: [
      'Dosage mismatch: warfarin and furosemide, both changed during a hospitalization',
      'Medication discontinued in notes: ibuprofen, stopped for kidney safety',
      'Missing medication: acetaminophen, started in its place',
    ],
    fileCount: 6,
    downloadUrl: '/demo/dorothy-williams/dorothy-williams-demo.zip',
  },
]
