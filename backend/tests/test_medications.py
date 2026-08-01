def _register_and_login(client, email, password="correcthorse123"):
    client.post(
        "/auth/register",
        json={"email": email, "password": password, "name": "Med Test User"},
    )

    login_response = client.post("/auth/login", json={"email": email, "password": password})

    return login_response.json()["access_token"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def _create_patient(client, token, **overrides):
    payload = {
        "first_name": "Jane",
        "last_name": "Doe",
        "date_of_birth": "1980-05-14",
    }
    payload.update(overrides)

    return client.post("/patients", json=payload, headers=_auth_headers(token))


def _create_medication(client, token, patient_id, **overrides):
    payload = {
        "medication_name": "Lisinopril",
        "dose": "10 mg",
        "route": "oral",
        "frequency": "once daily",
        "status": "active",
        "source": "patient_reported",
    }
    payload.update(overrides)

    return client.post(
        f"/patients/{patient_id}/medications", json=payload, headers=_auth_headers(token)
    )


def test_create_medication_requires_authentication(client):
    response = client.post(
        "/patients/1/medications",
        json={
            "medication_name": "Lisinopril",
            "dose": "10 mg",
            "route": "oral",
            "frequency": "once daily",
            "status": "active",
            "source": "patient_reported",
        },
    )

    assert response.status_code == 401


def test_create_medication_succeeds(client):
    token = _register_and_login(client, "creator@example.com")
    patient = _create_patient(client, token).json()

    response = _create_medication(client, token, patient["id"], notes="Taken with breakfast")

    assert response.status_code == 201

    body = response.json()
    assert body["medication_name"] == "Lisinopril"
    assert body["dose"] == "10 mg"
    assert body["route"] == "oral"
    assert body["frequency"] == "once daily"
    assert body["status"] == "active"
    assert body["source"] == "patient_reported"
    assert body["notes"] == "Taken with breakfast"
    assert "id" in body
    assert body["patient_id"] == patient["id"]


def test_create_medication_requires_a_patient_owned_by_the_user(client):
    token_a = _register_and_login(client, "owner4@example.com")
    token_b = _register_and_login(client, "intruder4@example.com")
    patient = _create_patient(client, token_a).json()

    response = _create_medication(client, token_b, patient["id"])

    assert response.status_code == 404
    assert response.json()["detail"] == "Patient not found"


def test_create_medication_returns_404_for_unknown_patient(client):
    token = _register_and_login(client, "unknownpatient@example.com")

    response = _create_medication(client, token, 999999)

    assert response.status_code == 404
    assert response.json()["detail"] == "Patient not found"


def test_create_medication_allows_missing_notes(client):
    token = _register_and_login(client, "nonotes@example.com")
    patient = _create_patient(client, token).json()

    response = _create_medication(client, token, patient["id"])

    assert response.status_code == 201
    assert response.json()["notes"] is None


def test_create_medication_rejects_empty_name(client):
    token = _register_and_login(client, "validation@example.com")
    patient = _create_patient(client, token).json()

    response = _create_medication(client, token, patient["id"], medication_name="")

    assert response.status_code == 422


def test_create_medication_rejects_missing_fields(client):
    token = _register_and_login(client, "missingfields@example.com")
    patient = _create_patient(client, token).json()

    response = client.post(
        f"/patients/{patient['id']}/medications", json={}, headers=_auth_headers(token)
    )

    assert response.status_code == 422


def test_create_medication_succeeds_for_an_archived_patient(client):
    token = _register_and_login(client, "archivedcreate@example.com")
    patient = _create_patient(client, token).json()
    client.delete(f"/patients/{patient['id']}", headers=_auth_headers(token))

    response = _create_medication(client, token, patient["id"])

    assert response.status_code == 201


def test_list_medications_returns_only_the_given_patients_medications(client):
    token = _register_and_login(client, "usera@example.com")
    patient_a = _create_patient(client, token, first_name="Patient A").json()
    patient_b = _create_patient(client, token, first_name="Patient B").json()

    _create_medication(client, token, patient_a["id"], medication_name="Med A1")
    _create_medication(client, token, patient_a["id"], medication_name="Med A2")
    _create_medication(client, token, patient_b["id"], medication_name="Med B1")

    response_a = client.get(
        f"/patients/{patient_a['id']}/medications", headers=_auth_headers(token)
    )
    response_b = client.get(
        f"/patients/{patient_b['id']}/medications", headers=_auth_headers(token)
    )

    assert response_a.status_code == 200
    assert response_b.status_code == 200

    names_a = {med["medication_name"] for med in response_a.json()}
    names_b = {med["medication_name"] for med in response_b.json()}

    assert names_a == {"Med A1", "Med A2"}
    assert names_b == {"Med B1"}


def test_list_medications_requires_authentication(client):
    response = client.get("/patients/1/medications")

    assert response.status_code == 401


def test_list_medications_returns_404_for_another_users_patient(client):
    token_a = _register_and_login(client, "listownera@example.com")
    token_b = _register_and_login(client, "listintruderb@example.com")
    patient = _create_patient(client, token_a).json()

    response = client.get(f"/patients/{patient['id']}/medications", headers=_auth_headers(token_b))

    assert response.status_code == 404


def test_get_medication_by_id_succeeds(client):
    token = _register_and_login(client, "getone@example.com")
    patient = _create_patient(client, token).json()
    created = _create_medication(client, token, patient["id"]).json()

    response = client.get(
        f"/patients/{patient['id']}/medications/{created['id']}", headers=_auth_headers(token)
    )

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_medication_returns_404_for_unknown_id(client):
    token = _register_and_login(client, "getunknown@example.com")
    patient = _create_patient(client, token).json()

    response = client.get(
        f"/patients/{patient['id']}/medications/999999", headers=_auth_headers(token)
    )

    assert response.status_code == 404


def test_get_medication_returns_404_for_other_users_patient(client):
    token_a = _register_and_login(client, "owner@example.com")
    token_b = _register_and_login(client, "intruder@example.com")
    patient = _create_patient(client, token_a).json()
    created = _create_medication(client, token_a, patient["id"]).json()

    response = client.get(
        f"/patients/{patient['id']}/medications/{created['id']}", headers=_auth_headers(token_b)
    )

    assert response.status_code == 404


def test_get_medication_returns_404_when_accessed_through_a_different_patient(client):
    # Cross-patient access: both patients are owned by the same user, but
    # the medication belongs to patient_a, not patient_b - the medication
    # id alone must not be enough to reach it through the wrong patient.
    token = _register_and_login(client, "crosspatient@example.com")
    patient_a = _create_patient(client, token, first_name="A").json()
    patient_b = _create_patient(client, token, first_name="B").json()
    created = _create_medication(client, token, patient_a["id"]).json()

    response = client.get(
        f"/patients/{patient_b['id']}/medications/{created['id']}", headers=_auth_headers(token)
    )

    assert response.status_code == 404


def test_get_medication_still_reachable_for_an_archived_patient(client):
    token = _register_and_login(client, "getarchivedmed@example.com")
    patient = _create_patient(client, token).json()
    created = _create_medication(client, token, patient["id"]).json()
    client.delete(f"/patients/{patient['id']}", headers=_auth_headers(token))

    response = client.get(
        f"/patients/{patient['id']}/medications/{created['id']}", headers=_auth_headers(token)
    )

    assert response.status_code == 200


def test_patch_medication_updates_only_provided_fields(client):
    token = _register_and_login(client, "patcher@example.com")
    patient = _create_patient(client, token).json()
    created = _create_medication(client, token, patient["id"]).json()

    response = client.patch(
        f"/patients/{patient['id']}/medications/{created['id']}",
        json={"dose": "20 mg", "status": "discontinued"},
        headers=_auth_headers(token),
    )

    assert response.status_code == 200

    body = response.json()
    assert body["dose"] == "20 mg"
    assert body["status"] == "discontinued"
    assert body["medication_name"] == created["medication_name"]
    assert body["route"] == created["route"]
    assert body["frequency"] == created["frequency"]
    assert body["source"] == created["source"]


def test_patch_medication_rejects_empty_value(client):
    token = _register_and_login(client, "patchvalidation@example.com")
    patient = _create_patient(client, token).json()
    created = _create_medication(client, token, patient["id"]).json()

    response = client.patch(
        f"/patients/{patient['id']}/medications/{created['id']}",
        json={"dose": ""},
        headers=_auth_headers(token),
    )

    assert response.status_code == 422


def test_patch_medication_returns_404_for_unknown_id(client):
    token = _register_and_login(client, "patchunknown@example.com")
    patient = _create_patient(client, token).json()

    response = client.patch(
        f"/patients/{patient['id']}/medications/999999",
        json={"dose": "20 mg"},
        headers=_auth_headers(token),
    )

    assert response.status_code == 404


def test_patch_medication_returns_404_for_other_users_patient(client):
    token_a = _register_and_login(client, "owner2@example.com")
    token_b = _register_and_login(client, "intruder2@example.com")
    patient = _create_patient(client, token_a).json()
    created = _create_medication(client, token_a, patient["id"]).json()

    response = client.patch(
        f"/patients/{patient['id']}/medications/{created['id']}",
        json={"dose": "20 mg"},
        headers=_auth_headers(token_b),
    )

    assert response.status_code == 404


def test_patch_medication_returns_404_when_accessed_through_a_different_patient(client):
    token = _register_and_login(client, "crosspatchpatient@example.com")
    patient_a = _create_patient(client, token, first_name="A").json()
    patient_b = _create_patient(client, token, first_name="B").json()
    created = _create_medication(client, token, patient_a["id"]).json()

    response = client.patch(
        f"/patients/{patient_b['id']}/medications/{created['id']}",
        json={"dose": "20 mg"},
        headers=_auth_headers(token),
    )

    assert response.status_code == 404


def test_patch_medication_requires_authentication(client):
    response = client.patch("/patients/1/medications/1", json={"dose": "20 mg"})

    assert response.status_code == 401


def test_delete_medication_succeeds(client):
    token = _register_and_login(client, "deleter@example.com")
    patient = _create_patient(client, token).json()
    created = _create_medication(client, token, patient["id"]).json()

    delete_response = client.delete(
        f"/patients/{patient['id']}/medications/{created['id']}", headers=_auth_headers(token)
    )
    assert delete_response.status_code == 204

    get_response = client.get(
        f"/patients/{patient['id']}/medications/{created['id']}", headers=_auth_headers(token)
    )
    assert get_response.status_code == 404


def test_delete_medication_returns_404_for_other_users_patient(client):
    token_a = _register_and_login(client, "owner3@example.com")
    token_b = _register_and_login(client, "intruder3@example.com")
    patient = _create_patient(client, token_a).json()
    created = _create_medication(client, token_a, patient["id"]).json()

    response = client.delete(
        f"/patients/{patient['id']}/medications/{created['id']}", headers=_auth_headers(token_b)
    )

    assert response.status_code == 404


def test_delete_medication_returns_404_when_accessed_through_a_different_patient(client):
    token = _register_and_login(client, "crossdeletepatient@example.com")
    patient_a = _create_patient(client, token, first_name="A").json()
    patient_b = _create_patient(client, token, first_name="B").json()
    created = _create_medication(client, token, patient_a["id"]).json()

    response = client.delete(
        f"/patients/{patient_b['id']}/medications/{created['id']}", headers=_auth_headers(token)
    )

    assert response.status_code == 404

    # Untouched: still reachable through the correct patient.
    get_response = client.get(
        f"/patients/{patient_a['id']}/medications/{created['id']}", headers=_auth_headers(token)
    )
    assert get_response.status_code == 200


def test_delete_medication_requires_authentication(client):
    response = client.delete("/patients/1/medications/1")

    assert response.status_code == 401


def _upload_csv(
    client, token, patient_id, content, filename="medications.csv", content_type="text/csv"
):
    encoded = content.encode("utf-8") if isinstance(content, str) else content

    return client.post(
        f"/patients/{patient_id}/medications/import",
        files={"file": (filename, encoded, content_type)},
        headers=_auth_headers(token),
    )


def test_import_csv_succeeds_with_multiple_medications(client):
    token = _register_and_login(client, "importer@example.com")
    patient = _create_patient(client, token).json()

    csv_content = (
        "medication_name,dose,route,frequency,status,source,notes\n"
        "Lisinopril,10 mg,oral,once daily,active,patient_reported,Taken with breakfast\n"
        "Metformin,500 mg,oral,twice daily,active,patient_reported,\n"
    )

    response = _upload_csv(client, token, patient["id"], csv_content)

    assert response.status_code == 201

    body = response.json()
    assert body["rows_processed"] == 2
    assert body["medications_created"] == 2
    assert body["blank_rows_ignored"] == 0


def test_import_csv_succeeds_with_notes_column_omitted(client):
    token = _register_and_login(client, "importnonotes@example.com")
    patient = _create_patient(client, token).json()

    csv_content = (
        "medication_name,dose,route,frequency,status,source\n"
        "Lisinopril,10 mg,oral,once daily,active,patient_reported\n"
    )

    response = _upload_csv(client, token, patient["id"], csv_content)

    assert response.status_code == 201
    assert response.json()["medications_created"] == 1

    list_response = client.get(
        f"/patients/{patient['id']}/medications", headers=_auth_headers(token)
    )
    assert list_response.json()[0]["notes"] is None


def test_import_csv_requires_authentication(client):
    csv_content = (
        "medication_name,dose,route,frequency,status,source\n"
        "Lisinopril,10 mg,oral,once daily,active,patient_reported\n"
    )

    response = client.post(
        "/patients/1/medications/import",
        files={"file": ("medications.csv", csv_content.encode("utf-8"), "text/csv")},
    )

    assert response.status_code == 401


def test_import_csv_returns_404_for_another_users_patient(client):
    token_a = _register_and_login(client, "importownera@example.com")
    token_b = _register_and_login(client, "importintruderb@example.com")
    patient = _create_patient(client, token_a).json()

    csv_content = (
        "medication_name,dose,route,frequency,status,source\n"
        "Lisinopril,10 mg,oral,once daily,active,patient_reported\n"
    )

    response = _upload_csv(client, token_b, patient["id"], csv_content)

    assert response.status_code == 404


def test_import_csv_rejects_invalid_file_type(client):
    token = _register_and_login(client, "importbadtype@example.com")
    patient = _create_patient(client, token).json()

    response = _upload_csv(
        client,
        token,
        patient["id"],
        "not a csv file",
        filename="medications.txt",
        content_type="text/plain",
    )

    assert response.status_code == 422


def test_import_csv_rejects_empty_file(client):
    token = _register_and_login(client, "importempty@example.com")
    patient = _create_patient(client, token).json()

    response = _upload_csv(client, token, patient["id"], "")

    assert response.status_code == 422


def test_import_csv_rejects_file_with_no_header_row(client):
    token = _register_and_login(client, "importnoheader@example.com")
    patient = _create_patient(client, token).json()

    response = _upload_csv(client, token, patient["id"], "\n\n")

    assert response.status_code == 422


def test_import_csv_rejects_missing_required_headers(client):
    token = _register_and_login(client, "importmissingheaders@example.com")
    patient = _create_patient(client, token).json()

    csv_content = "medication_name,dose\nLisinopril,10 mg\n"

    response = _upload_csv(client, token, patient["id"], csv_content)

    assert response.status_code == 422
    assert "route" in response.json()["detail"]


def test_import_csv_ignores_extra_unknown_headers(client):
    token = _register_and_login(client, "importextraheaders@example.com")
    patient = _create_patient(client, token).json()

    csv_content = (
        "medication_name,dose,route,frequency,status,source,notes,insurance_id\n"
        "Lisinopril,10 mg,oral,once daily,active,patient_reported,,12345\n"
    )

    response = _upload_csv(client, token, patient["id"], csv_content)

    assert response.status_code == 201
    assert response.json()["medications_created"] == 1


def test_import_csv_ignores_fully_blank_rows(client):
    token = _register_and_login(client, "importblankrows@example.com")
    patient = _create_patient(client, token).json()

    csv_content = (
        "medication_name,dose,route,frequency,status,source,notes\n"
        "Lisinopril,10 mg,oral,once daily,active,patient_reported,\n"
        ",,,,,,\n"
        "Metformin,500 mg,oral,twice daily,active,patient_reported,\n"
    )

    response = _upload_csv(client, token, patient["id"], csv_content)

    assert response.status_code == 201

    body = response.json()
    assert body["rows_processed"] == 3
    assert body["medications_created"] == 2
    assert body["blank_rows_ignored"] == 1


def test_import_csv_trims_whitespace_from_headers_and_values(client):
    token = _register_and_login(client, "importwhitespace@example.com")
    patient = _create_patient(client, token).json()

    csv_content = (
        " Medication_Name , Dose , Route , Frequency , Status , Source , Notes \n"
        " Lisinopril , 10 mg , oral , once daily , active , patient_reported , Taken with breakfast \n"
    )

    response = _upload_csv(client, token, patient["id"], csv_content)

    assert response.status_code == 201
    assert response.json()["medications_created"] == 1

    list_response = client.get(
        f"/patients/{patient['id']}/medications", headers=_auth_headers(token)
    )
    medication = list_response.json()[0]
    assert medication["medication_name"] == "Lisinopril"
    assert medication["dose"] == "10 mg"
    assert medication["notes"] == "Taken with breakfast"


def test_import_csv_rejects_invalid_field_values(client):
    token = _register_and_login(client, "importinvalidfield@example.com")
    patient = _create_patient(client, token).json()

    csv_content = (
        "medication_name,dose,route,frequency,status,source,notes\n"
        "Lisinopril,,oral,once daily,active,patient_reported,\n"
    )

    response = _upload_csv(client, token, patient["id"], csv_content)

    assert response.status_code == 422

    detail = response.json()["detail"]
    assert detail["row_errors"][0]["row"] == 2
    assert any(error["field"] == "dose" for error in detail["row_errors"][0]["errors"])


def test_import_csv_reports_row_number_for_invalid_row_among_valid_rows(client):
    token = _register_and_login(client, "importonebad@example.com")
    patient = _create_patient(client, token).json()

    csv_content = (
        "medication_name,dose,route,frequency,status,source,notes\n"
        "Lisinopril,10 mg,oral,once daily,active,patient_reported,\n"
        "BadRow,,oral,once daily,active,patient_reported,\n"
        "Metformin,500 mg,oral,twice daily,active,patient_reported,\n"
    )

    response = _upload_csv(client, token, patient["id"], csv_content)

    assert response.status_code == 422

    detail = response.json()["detail"]
    assert detail["row_errors"][0]["row"] == 3


def test_import_csv_creates_no_medications_when_any_row_invalid(client):
    token = _register_and_login(client, "importatomic@example.com")
    patient = _create_patient(client, token).json()

    csv_content = (
        "medication_name,dose,route,frequency,status,source,notes\n"
        "Lisinopril,10 mg,oral,once daily,active,patient_reported,\n"
        "BadRow,,oral,once daily,active,patient_reported,\n"
    )

    response = _upload_csv(client, token, patient["id"], csv_content)

    assert response.status_code == 422

    list_response = client.get(
        f"/patients/{patient['id']}/medications", headers=_auth_headers(token)
    )
    assert list_response.json() == []


def test_import_csv_assigns_medications_to_the_target_patient(client):
    token = _register_and_login(client, "importowner@example.com")
    patient = _create_patient(client, token).json()

    csv_content = (
        "medication_name,dose,route,frequency,status,source,notes\n"
        "Lisinopril,10 mg,oral,once daily,active,patient_reported,\n"
    )

    _upload_csv(client, token, patient["id"], csv_content)

    list_response = client.get(
        f"/patients/{patient['id']}/medications", headers=_auth_headers(token)
    )
    medications = list_response.json()

    assert len(medications) == 1
    assert medications[0]["patient_id"] == patient["id"]


def test_import_csv_does_not_leak_into_another_patients_list(client):
    token = _register_and_login(client, "importusera@example.com")
    patient_a = _create_patient(client, token, first_name="A").json()
    patient_b = _create_patient(client, token, first_name="B").json()

    csv_content = (
        "medication_name,dose,route,frequency,status,source,notes\n"
        "Lisinopril,10 mg,oral,once daily,active,patient_reported,\n"
    )

    _upload_csv(client, token, patient_b["id"], csv_content)

    list_response_a = client.get(
        f"/patients/{patient_a['id']}/medications", headers=_auth_headers(token)
    )
    assert list_response_a.json() == []


def test_imported_medications_appear_through_list_endpoint(client):
    token = _register_and_login(client, "importlist@example.com")
    patient = _create_patient(client, token).json()

    csv_content = (
        "medication_name,dose,route,frequency,status,source,notes\n"
        "Lisinopril,10 mg,oral,once daily,active,patient_reported,Taken with breakfast\n"
    )

    _upload_csv(client, token, patient["id"], csv_content)

    list_response = client.get(
        f"/patients/{patient['id']}/medications", headers=_auth_headers(token)
    )
    assert list_response.status_code == 200

    medications = list_response.json()
    assert len(medications) == 1
    assert medications[0]["medication_name"] == "Lisinopril"
    assert medications[0]["dose"] == "10 mg"
    assert medications[0]["route"] == "oral"
    assert medications[0]["frequency"] == "once daily"
    assert medications[0]["status"] == "active"
    assert medications[0]["source"] == "patient_reported"
    assert medications[0]["notes"] == "Taken with breakfast"
