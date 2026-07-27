SUMMARY_PROMPT_TEMPLATE = """You are assisting with clinical documentation review. You are not making clinical decisions, diagnoses, or treatment recommendations.

Read the clinical notes below and return a single JSON object, and nothing else, with exactly this shape:

{{
  "medications": [
    {{
      "name": string,
      "dosage": string or null,
      "route": string or null,
      "frequency": string or null,
      "status": string or null,
      "notes": string or null
    }}
  ],
  "possible_inconsistencies": [string],
  "summary": string
}}

Instructions:
1. Identify every medication mentioned by name and add one entry per medication to "medications".
2. For each medication, record dosage, route, frequency, and status where the notes state it. Use null for anything the notes do not state. Do not guess.
3. In "possible_inconsistencies", describe any place where the notes appear to disagree with each other about a medication. Only describe the disagreement. Do not attempt to resolve it or decide which note is correct. Use an empty list if there are none.
4. In "summary", write a short, clinically focused summary of the medication-related information across all notes. Do not include information unrelated to medications.

Return only the JSON object itself. Do not include markdown code fences, explanations, or any text outside the JSON object.

Clinical notes:

{notes}
"""


def build_summary_prompt(clinical_notes: list[str]) -> str:
    if not clinical_notes:
        raise ValueError("At least one clinical note is required")

    joined_notes = "\n\n---\n\n".join(
        f"Note {index}:\n{note}" for index, note in enumerate(clinical_notes, start=1)
    )

    return SUMMARY_PROMPT_TEMPLATE.format(notes=joined_notes)
