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
      "notes": string or null,
      "source_note": integer
    }}
  ],
  "possible_inconsistencies": [string],
  "summary": string
}}

Instructions:
1. Identify every medication mentioned by name. Add one entry per medication per note it is mentioned in - if the same medication appears in more than one note, include a separate entry for each note it appears in, each with its own "source_note".
2. For each medication entry, record dosage, route, frequency, and status exactly as that specific note states them. Use null for anything that note does not state. Do not guess, and do not fill in a value from a different note.
3. Set "source_note" to the integer number of the note (as labeled below, e.g. 1, 2, 3) that this medication entry came from.
4. In "possible_inconsistencies", describe any place where the notes appear to disagree with each other about a medication. Only describe the disagreement. Do not attempt to resolve it or decide which note is correct. Use an empty list if there are none.
5. In "summary", write a short, clinically focused summary of the medication-related information across all notes. Do not include information unrelated to medications.

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
