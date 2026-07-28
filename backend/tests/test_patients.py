def _register_and_login(client, email, password="correcthorse123"):
    client.post(
        "/auth/register",
        json={"email": email, "password": password, "name": "Patient Test User"},
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


def test_create_patient_requires_authentication(client):
    response = client.post(
        "/patients",
        json={"first_name": "Jane", "last_name": "Doe", "date_of_birth": "1980-05-14"},
    )

    assert response.status_code == 401


def test_create_patient_succeeds(client):
    token = _register_and_login(client, "creator@example.com")

    response = _create_patient(
        client, token, external_mrn="MRN-001", notes="Prefers morning appointments"
    )

    assert response.status_code == 201

    body = response.json()
    assert body["first_name"] == "Jane"
    assert body["last_name"] == "Doe"
    assert body["date_of_birth"] == "1980-05-14"
    assert body["external_mrn"] == "MRN-001"
    assert body["notes"] == "Prefers morning appointments"
    assert body["status"] == "active"
    assert "id" in body
    assert "user_id" in body


def test_create_patient_allows_missing_optional_fields(client):
    token = _register_and_login(client, "nooptional@example.com")

    response = _create_patient(client, token)

    assert response.status_code == 201
    body = response.json()
    assert body["external_mrn"] is None
    assert body["notes"] is None


def test_create_patient_rejects_empty_first_name(client):
    token = _register_and_login(client, "emptyfirst@example.com")

    response = _create_patient(client, token, first_name="")

    assert response.status_code == 422


def test_create_patient_rejects_empty_last_name(client):
    token = _register_and_login(client, "emptylast@example.com")

    response = _create_patient(client, token, last_name="")

    assert response.status_code == 422


def test_create_patient_rejects_missing_fields(client):
    token = _register_and_login(client, "missingfields@example.com")

    response = client.post("/patients", json={}, headers=_auth_headers(token))

    assert response.status_code == 422


def test_create_patient_rejects_invalid_date_of_birth(client):
    token = _register_and_login(client, "baddob@example.com")

    response = _create_patient(client, token, date_of_birth="not-a-date")

    assert response.status_code == 422


def test_list_patients_returns_only_current_users_patients(client):
    token_a = _register_and_login(client, "usera@example.com")
    token_b = _register_and_login(client, "userb@example.com")

    _create_patient(client, token_a, first_name="A1")
    _create_patient(client, token_a, first_name="A2")
    _create_patient(client, token_b, first_name="B1")

    response_a = client.get("/patients", headers=_auth_headers(token_a))
    response_b = client.get("/patients", headers=_auth_headers(token_b))

    assert response_a.status_code == 200
    assert response_b.status_code == 200

    names_a = {patient["first_name"] for patient in response_a.json()}
    names_b = {patient["first_name"] for patient in response_b.json()}

    assert names_a == {"A1", "A2"}
    assert names_b == {"B1"}


def test_list_patients_requires_authentication(client):
    response = client.get("/patients")

    assert response.status_code == 401


def test_list_patients_excludes_archived_patients(client):
    token = _register_and_login(client, "archivedlist@example.com")

    kept = _create_patient(client, token, first_name="Kept").json()
    archived = _create_patient(client, token, first_name="Archived").json()

    client.delete(f"/patients/{archived['id']}", headers=_auth_headers(token))

    response = client.get("/patients", headers=_auth_headers(token))

    assert response.status_code == 200
    names = {patient["first_name"] for patient in response.json()}
    assert names == {"Kept"}
    assert kept["id"] in {patient["id"] for patient in response.json()}


def test_get_patient_by_id_succeeds(client):
    token = _register_and_login(client, "getone@example.com")
    created = _create_patient(client, token).json()

    response = client.get(f"/patients/{created['id']}", headers=_auth_headers(token))

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_patient_returns_404_for_unknown_id(client):
    token = _register_and_login(client, "getunknown@example.com")

    response = client.get("/patients/999999", headers=_auth_headers(token))

    assert response.status_code == 404
    assert response.json()["detail"] == "Patient not found"


def test_get_patient_returns_404_for_other_users_patient(client):
    token_a = _register_and_login(client, "owner@example.com")
    token_b = _register_and_login(client, "intruder@example.com")

    created = _create_patient(client, token_a).json()

    response = client.get(f"/patients/{created['id']}", headers=_auth_headers(token_b))

    assert response.status_code == 404


def test_get_patient_requires_authentication(client):
    response = client.get("/patients/1")

    assert response.status_code == 401


def test_get_patient_still_reachable_after_archiving(client):
    token = _register_and_login(client, "getarchived@example.com")
    created = _create_patient(client, token).json()

    client.delete(f"/patients/{created['id']}", headers=_auth_headers(token))

    response = client.get(f"/patients/{created['id']}", headers=_auth_headers(token))

    assert response.status_code == 200
    assert response.json()["status"] == "archived"


def test_patch_patient_updates_only_provided_fields(client):
    token = _register_and_login(client, "patcher@example.com")
    created = _create_patient(client, token, external_mrn="MRN-100").json()

    response = client.patch(
        f"/patients/{created['id']}",
        json={"last_name": "Smith", "notes": "Moved to a new address"},
        headers=_auth_headers(token),
    )

    assert response.status_code == 200

    body = response.json()
    assert body["last_name"] == "Smith"
    assert body["notes"] == "Moved to a new address"
    assert body["first_name"] == created["first_name"]
    assert body["date_of_birth"] == created["date_of_birth"]
    assert body["external_mrn"] == "MRN-100"


def test_patch_patient_rejects_empty_first_name(client):
    token = _register_and_login(client, "patchvalidation@example.com")
    created = _create_patient(client, token).json()

    response = client.patch(
        f"/patients/{created['id']}",
        json={"first_name": ""},
        headers=_auth_headers(token),
    )

    assert response.status_code == 422


def test_patch_patient_ignores_status_field(client):
    token = _register_and_login(client, "patchstatus@example.com")
    created = _create_patient(client, token).json()

    response = client.patch(
        f"/patients/{created['id']}",
        json={"status": "archived"},
        headers=_auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "active"

    list_response = client.get("/patients", headers=_auth_headers(token))
    assert created["id"] in {patient["id"] for patient in list_response.json()}


def test_patch_patient_returns_404_for_unknown_id(client):
    token = _register_and_login(client, "patchunknown@example.com")

    response = client.patch(
        "/patients/999999",
        json={"last_name": "Smith"},
        headers=_auth_headers(token),
    )

    assert response.status_code == 404


def test_patch_patient_returns_404_for_other_users_patient(client):
    token_a = _register_and_login(client, "owner2@example.com")
    token_b = _register_and_login(client, "intruder2@example.com")

    created = _create_patient(client, token_a).json()

    response = client.patch(
        f"/patients/{created['id']}",
        json={"last_name": "Smith"},
        headers=_auth_headers(token_b),
    )

    assert response.status_code == 404


def test_patch_patient_requires_authentication(client):
    response = client.patch("/patients/1", json={"last_name": "Smith"})

    assert response.status_code == 401


def test_archive_patient_succeeds(client):
    token = _register_and_login(client, "archiver@example.com")
    created = _create_patient(client, token).json()

    response = client.delete(f"/patients/{created['id']}", headers=_auth_headers(token))
    assert response.status_code == 204

    get_response = client.get(f"/patients/{created['id']}", headers=_auth_headers(token))
    assert get_response.status_code == 200
    assert get_response.json()["status"] == "archived"


def test_archive_patient_returns_404_for_other_users_patient(client):
    token_a = _register_and_login(client, "owner3@example.com")
    token_b = _register_and_login(client, "intruder3@example.com")

    created = _create_patient(client, token_a).json()

    response = client.delete(f"/patients/{created['id']}", headers=_auth_headers(token_b))

    assert response.status_code == 404


def test_archive_patient_returns_404_for_unknown_id(client):
    token = _register_and_login(client, "archiveunknown@example.com")

    response = client.delete("/patients/999999", headers=_auth_headers(token))

    assert response.status_code == 404


def test_archive_patient_requires_authentication(client):
    response = client.delete("/patients/1")

    assert response.status_code == 401
