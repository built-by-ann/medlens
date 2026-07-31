import pytest

from app.ai.prompts import build_summary_prompt


def test_build_summary_prompt_includes_each_note():
    prompt = build_summary_prompt(["Patient takes Lisinopril 10 mg.", "No known allergies."])

    assert "Patient takes Lisinopril 10 mg." in prompt
    assert "No known allergies." in prompt


def test_build_summary_prompt_numbers_notes_in_order():
    prompt = build_summary_prompt(["First note text.", "Second note text."])

    assert prompt.index("Note 1:") < prompt.index("First note text.")
    assert prompt.index("Note 2:") < prompt.index("Second note text.")
    assert prompt.index("First note text.") < prompt.index("Note 2:")


def test_build_summary_prompt_instructs_identifying_medications():
    prompt = build_summary_prompt(["Some note."])

    assert "medication" in prompt.lower()


def test_build_summary_prompt_instructs_not_reconciling():
    prompt = build_summary_prompt(["Some note."])

    assert "do not attempt to resolve" in prompt.lower()


def test_build_summary_prompt_rejects_empty_list():
    with pytest.raises(ValueError):
        build_summary_prompt([])


def test_build_summary_prompt_instructs_reporting_source_note():
    # Issue #152: the model is asked to report which numbered note each
    # medication came from, using the same "Note N" numbering already
    # tested above (test_build_summary_prompt_numbers_notes_in_order).
    prompt = build_summary_prompt(["Some note."])

    assert "source_note" in prompt
    assert "one entry per medication per note" in prompt.lower()
