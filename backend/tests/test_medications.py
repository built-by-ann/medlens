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
