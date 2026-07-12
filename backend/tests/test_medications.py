def _register_and_login(client, email, password="correcthorse123"):
    client.post(
        "/auth/register",
        json={"email": email, "password": password, "name": "Med Test User"},
    )

    login_response = client.post("/auth/login", json={"email": email, "password": password})

    return login_response.json()["access_token"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def _create_medication(client, token, **overrides):
    payload = {
        "medication_name": "Lisinopril",
        "dose": "10 mg",
        "route": "oral",
        "frequency": "once daily",
        "status": "active",
        "source": "patient_reported",
    }
    payload.update(overrides)

    return client.post("/medications", json=payload, headers=_auth_headers(token))


def test_create_medication_requires_authentication(client):
    response = client.post(
        "/medications",
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

    response = _create_medication(client, token, notes="Taken with breakfast")

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
    assert "user_id" in body


def test_create_medication_allows_missing_notes(client):
    token = _register_and_login(client, "nonotes@example.com")

    response = _create_medication(client, token)

    assert response.status_code == 201
    assert response.json()["notes"] is None


def test_create_medication_rejects_empty_name(client):
    token = _register_and_login(client, "validation@example.com")

    response = _create_medication(client, token, medication_name="")

    assert response.status_code == 422


def test_create_medication_rejects_missing_fields(client):
    token = _register_and_login(client, "missingfields@example.com")

    response = client.post("/medications", json={}, headers=_auth_headers(token))

    assert response.status_code == 422


def test_list_medications_returns_only_current_users_medications(client):
    token_a = _register_and_login(client, "usera@example.com")
    token_b = _register_and_login(client, "userb@example.com")

    _create_medication(client, token_a, medication_name="Med A1")
    _create_medication(client, token_a, medication_name="Med A2")
    _create_medication(client, token_b, medication_name="Med B1")

    response_a = client.get("/medications", headers=_auth_headers(token_a))
    response_b = client.get("/medications", headers=_auth_headers(token_b))

    assert response_a.status_code == 200
    assert response_b.status_code == 200

    names_a = {med["medication_name"] for med in response_a.json()}
    names_b = {med["medication_name"] for med in response_b.json()}

    assert names_a == {"Med A1", "Med A2"}
    assert names_b == {"Med B1"}


def test_list_medications_requires_authentication(client):
    response = client.get("/medications")

    assert response.status_code == 401


def test_get_medication_by_id_succeeds(client):
    token = _register_and_login(client, "getone@example.com")
    created = _create_medication(client, token).json()

    response = client.get(f"/medications/{created['id']}", headers=_auth_headers(token))

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_medication_returns_404_for_unknown_id(client):
    token = _register_and_login(client, "getunknown@example.com")

    response = client.get("/medications/999999", headers=_auth_headers(token))

    assert response.status_code == 404


def test_get_medication_returns_404_for_other_users_medication(client):
    token_a = _register_and_login(client, "owner@example.com")
    token_b = _register_and_login(client, "intruder@example.com")

    created = _create_medication(client, token_a).json()

    response = client.get(f"/medications/{created['id']}", headers=_auth_headers(token_b))

    assert response.status_code == 404


def test_patch_medication_updates_only_provided_fields(client):
    token = _register_and_login(client, "patcher@example.com")
    created = _create_medication(client, token).json()

    response = client.patch(
        f"/medications/{created['id']}",
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
    created = _create_medication(client, token).json()

    response = client.patch(
        f"/medications/{created['id']}",
        json={"dose": ""},
        headers=_auth_headers(token),
    )

    assert response.status_code == 422


def test_patch_medication_returns_404_for_unknown_id(client):
    token = _register_and_login(client, "patchunknown@example.com")

    response = client.patch(
        "/medications/999999",
        json={"dose": "20 mg"},
        headers=_auth_headers(token),
    )

    assert response.status_code == 404


def test_patch_medication_returns_404_for_other_users_medication(client):
    token_a = _register_and_login(client, "owner2@example.com")
    token_b = _register_and_login(client, "intruder2@example.com")

    created = _create_medication(client, token_a).json()

    response = client.patch(
        f"/medications/{created['id']}",
        json={"dose": "20 mg"},
        headers=_auth_headers(token_b),
    )

    assert response.status_code == 404


def test_patch_medication_requires_authentication(client):
    response = client.patch("/medications/1", json={"dose": "20 mg"})

    assert response.status_code == 401


def test_delete_medication_succeeds(client):
    token = _register_and_login(client, "deleter@example.com")
    created = _create_medication(client, token).json()

    delete_response = client.delete(
        f"/medications/{created['id']}", headers=_auth_headers(token)
    )
    assert delete_response.status_code == 204

    get_response = client.get(f"/medications/{created['id']}", headers=_auth_headers(token))
    assert get_response.status_code == 404


def test_delete_medication_returns_404_for_other_users_medication(client):
    token_a = _register_and_login(client, "owner3@example.com")
    token_b = _register_and_login(client, "intruder3@example.com")

    created = _create_medication(client, token_a).json()

    response = client.delete(f"/medications/{created['id']}", headers=_auth_headers(token_b))

    assert response.status_code == 404


def test_delete_medication_requires_authentication(client):
    response = client.delete("/medications/1")

    assert response.status_code == 401


def _upload_csv(client, token, content, filename="medications.csv", content_type="text/csv"):
    encoded = content.encode("utf-8") if isinstance(content, str) else content

    return client.post(
        "/medications/import",
        files={"file": (filename, encoded, content_type)},
        headers=_auth_headers(token),
    )


def test_import_csv_succeeds_with_multiple_medications(client):
    token = _register_and_login(client, "importer@example.com")

    csv_content = (
        "medication_name,dose,route,frequency,status,source,notes\n"
        "Lisinopril,10 mg,oral,once daily,active,patient_reported,Taken with breakfast\n"
        "Metformin,500 mg,oral,twice daily,active,patient_reported,\n"
    )

    response = _upload_csv(client, token, csv_content)

    assert response.status_code == 201

    body = response.json()
    assert body["rows_processed"] == 2
    assert body["medications_created"] == 2
    assert body["blank_rows_ignored"] == 0


def test_import_csv_succeeds_with_notes_column_omitted(client):
    token = _register_and_login(client, "importnonotes@example.com")

    csv_content = (
        "medication_name,dose,route,frequency,status,source\n"
        "Lisinopril,10 mg,oral,once daily,active,patient_reported\n"
    )

    response = _upload_csv(client, token, csv_content)

    assert response.status_code == 201
    assert response.json()["medications_created"] == 1

    list_response = client.get("/medications", headers=_auth_headers(token))
    assert list_response.json()[0]["notes"] is None


def test_import_csv_requires_authentication(client):
    csv_content = (
        "medication_name,dose,route,frequency,status,source\n"
        "Lisinopril,10 mg,oral,once daily,active,patient_reported\n"
    )

    response = client.post(
        "/medications/import",
        files={"file": ("medications.csv", csv_content.encode("utf-8"), "text/csv")},
    )

    assert response.status_code == 401


def test_import_csv_rejects_invalid_file_type(client):
    token = _register_and_login(client, "importbadtype@example.com")

    response = _upload_csv(
        client, token, "not a csv file", filename="medications.txt", content_type="text/plain"
    )

    assert response.status_code == 422


def test_import_csv_rejects_empty_file(client):
    token = _register_and_login(client, "importempty@example.com")

    response = _upload_csv(client, token, "")

    assert response.status_code == 422


def test_import_csv_rejects_file_with_no_header_row(client):
    token = _register_and_login(client, "importnoheader@example.com")

    response = _upload_csv(client, token, "\n\n")

    assert response.status_code == 422


def test_import_csv_rejects_missing_required_headers(client):
    token = _register_and_login(client, "importmissingheaders@example.com")

    csv_content = "medication_name,dose\nLisinopril,10 mg\n"

    response = _upload_csv(client, token, csv_content)

    assert response.status_code == 422
    assert "route" in response.json()["detail"]


def test_import_csv_ignores_extra_unknown_headers(client):
    token = _register_and_login(client, "importextraheaders@example.com")

    csv_content = (
        "medication_name,dose,route,frequency,status,source,notes,insurance_id\n"
        "Lisinopril,10 mg,oral,once daily,active,patient_reported,,12345\n"
    )

    response = _upload_csv(client, token, csv_content)

    assert response.status_code == 201
    assert response.json()["medications_created"] == 1


def test_import_csv_ignores_fully_blank_rows(client):
    token = _register_and_login(client, "importblankrows@example.com")

    csv_content = (
        "medication_name,dose,route,frequency,status,source,notes\n"
        "Lisinopril,10 mg,oral,once daily,active,patient_reported,\n"
        ",,,,,,\n"
        "Metformin,500 mg,oral,twice daily,active,patient_reported,\n"
    )

    response = _upload_csv(client, token, csv_content)

    assert response.status_code == 201

    body = response.json()
    assert body["rows_processed"] == 3
    assert body["medications_created"] == 2
    assert body["blank_rows_ignored"] == 1


def test_import_csv_trims_whitespace_from_headers_and_values(client):
    token = _register_and_login(client, "importwhitespace@example.com")

    csv_content = (
        " Medication_Name , Dose , Route , Frequency , Status , Source , Notes \n"
        " Lisinopril , 10 mg , oral , once daily , active , patient_reported , Taken with breakfast \n"
    )

    response = _upload_csv(client, token, csv_content)

    assert response.status_code == 201
    assert response.json()["medications_created"] == 1

    list_response = client.get("/medications", headers=_auth_headers(token))
    medication = list_response.json()[0]
    assert medication["medication_name"] == "Lisinopril"
    assert medication["dose"] == "10 mg"
    assert medication["notes"] == "Taken with breakfast"


def test_import_csv_rejects_invalid_field_values(client):
    token = _register_and_login(client, "importinvalidfield@example.com")

    csv_content = (
        "medication_name,dose,route,frequency,status,source,notes\n"
        "Lisinopril,,oral,once daily,active,patient_reported,\n"
    )

    response = _upload_csv(client, token, csv_content)

    assert response.status_code == 422

    detail = response.json()["detail"]
    assert detail["row_errors"][0]["row"] == 2
    assert any(error["field"] == "dose" for error in detail["row_errors"][0]["errors"])


def test_import_csv_reports_row_number_for_invalid_row_among_valid_rows(client):
    token = _register_and_login(client, "importonebad@example.com")

    csv_content = (
        "medication_name,dose,route,frequency,status,source,notes\n"
        "Lisinopril,10 mg,oral,once daily,active,patient_reported,\n"
        "BadRow,,oral,once daily,active,patient_reported,\n"
        "Metformin,500 mg,oral,twice daily,active,patient_reported,\n"
    )

    response = _upload_csv(client, token, csv_content)

    assert response.status_code == 422

    detail = response.json()["detail"]
    assert detail["row_errors"][0]["row"] == 3


def test_import_csv_creates_no_medications_when_any_row_invalid(client):
    token = _register_and_login(client, "importatomic@example.com")

    csv_content = (
        "medication_name,dose,route,frequency,status,source,notes\n"
        "Lisinopril,10 mg,oral,once daily,active,patient_reported,\n"
        "BadRow,,oral,once daily,active,patient_reported,\n"
    )

    response = _upload_csv(client, token, csv_content)

    assert response.status_code == 422

    list_response = client.get("/medications", headers=_auth_headers(token))
    assert list_response.json() == []


def test_import_csv_assigns_medications_to_authenticated_user(client):
    token = _register_and_login(client, "importowner@example.com")

    csv_content = (
        "medication_name,dose,route,frequency,status,source,notes\n"
        "Lisinopril,10 mg,oral,once daily,active,patient_reported,\n"
    )

    _upload_csv(client, token, csv_content)

    list_response = client.get("/medications", headers=_auth_headers(token))
    medications = list_response.json()

    assert len(medications) == 1
    assert "user_id" in medications[0]


def test_import_csv_does_not_leak_into_other_users_list(client):
    token_a = _register_and_login(client, "importusera@example.com")
    token_b = _register_and_login(client, "importuserb@example.com")

    csv_content = (
        "medication_name,dose,route,frequency,status,source,notes\n"
        "Lisinopril,10 mg,oral,once daily,active,patient_reported,\n"
    )

    _upload_csv(client, token_b, csv_content)

    list_response_a = client.get("/medications", headers=_auth_headers(token_a))
    assert list_response_a.json() == []


def test_imported_medications_appear_through_list_endpoint(client):
    token = _register_and_login(client, "importlist@example.com")

    csv_content = (
        "medication_name,dose,route,frequency,status,source,notes\n"
        "Lisinopril,10 mg,oral,once daily,active,patient_reported,Taken with breakfast\n"
    )

    _upload_csv(client, token, csv_content)

    list_response = client.get("/medications", headers=_auth_headers(token))
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
