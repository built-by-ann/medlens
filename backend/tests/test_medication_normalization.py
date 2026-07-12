from app.services.medication_normalization import (
    normalize_dose,
    normalize_frequency,
    normalize_medication_name,
    normalize_route,
    normalize_status,
)


def test_normalize_medication_name_trims_whitespace():
    assert normalize_medication_name("  Lisinopril  ") == "lisinopril"


def test_normalize_medication_name_lowercases():
    assert normalize_medication_name("LISINOPRIL") == "lisinopril"
    assert normalize_medication_name("lisinopril") == "lisinopril"
    assert normalize_medication_name("Lisinopril") == "lisinopril"


def test_normalize_medication_name_collapses_internal_whitespace():
    assert normalize_medication_name("Lisinopril   HCl") == "lisinopril hcl"


def test_normalize_medication_name_strips_trailing_period():
    assert normalize_medication_name("Lisinopril.") == "lisinopril"


def test_normalize_medication_name_does_not_merge_unrelated_names():
    assert normalize_medication_name("Lisinopril") != normalize_medication_name("Losartan")


def test_normalize_medication_name_does_not_merge_partial_matches():
    assert normalize_medication_name("Lisinopril") != normalize_medication_name("Lisinopril HCTZ")


def test_normalize_medication_name_returns_none_for_none():
    assert normalize_medication_name(None) is None


def test_normalize_medication_name_returns_none_for_blank_string():
    assert normalize_medication_name("   ") is None


def test_normalize_dose_trims_and_lowercases():
    assert normalize_dose("  10 MG  ") == "10 mg"


def test_normalize_dose_collapses_whitespace():
    assert normalize_dose("10   mg") == "10 mg"


def test_normalize_dose_returns_none_for_none():
    assert normalize_dose(None) is None


def test_normalize_route_applies_known_alias():
    assert normalize_route("PO") == "oral"
    assert normalize_route("po") == "oral"


def test_normalize_route_leaves_unaliased_values_normalized_only():
    assert normalize_route("Oral") == "oral"
    assert normalize_route("Intravenous") == "intravenous"


def test_normalize_route_returns_none_for_none():
    assert normalize_route(None) is None


def test_normalize_frequency_applies_known_alias():
    assert normalize_frequency("QD") == "daily"
    assert normalize_frequency("qd") == "daily"


def test_normalize_frequency_leaves_unaliased_values_normalized_only():
    assert normalize_frequency("Twice Daily") == "twice daily"


def test_normalize_frequency_does_not_merge_unrelated_values():
    assert normalize_frequency("once daily") != normalize_frequency("twice daily")


def test_normalize_status_trims_and_lowercases():
    assert normalize_status("  Discontinued  ") == "discontinued"


def test_normalize_status_returns_none_for_none():
    assert normalize_status(None) is None
