def _register_and_login(client, email, password="correcthorse123"):
    client.post(
        "/auth/register",
        json={"email": email, "password": password, "name": "Doc Test User"},
    )

    login_response = client.post("/auth/login", json={"email": email, "password": password})

    return login_response.json()["access_token"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def _create_document(client, token, **overrides):
    payload = {
        "document_type": "visit_note",
        "title": "Initial Visit",
        "raw_text": "Patient presents with hypertension.",
    }
    payload.update(overrides)

    return client.post("/clinical-documents", json=payload, headers=_auth_headers(token))


def test_create_document_requires_authentication(client):
    response = client.post(
        "/clinical-documents",
        json={
            "document_type": "visit_note",
            "title": "Initial Visit",
            "raw_text": "Patient presents with hypertension.",
        },
    )

    assert response.status_code == 401


def test_create_document_succeeds(client):
    token = _register_and_login(client, "creator@example.com")

    response = _create_document(client, token)

    assert response.status_code == 201

    body = response.json()
    assert body["document_type"] == "visit_note"
    assert body["title"] == "Initial Visit"
    assert body["raw_text"] == "Patient presents with hypertension."
    assert body["file_name"] is None
    assert body["file_type"] == "manual_entry"
    assert "id" in body
    assert "user_id" in body


def test_create_document_rejects_empty_title(client):
    token = _register_and_login(client, "validation@example.com")

    response = _create_document(client, token, title="")

    assert response.status_code == 422


def test_create_document_rejects_missing_fields(client):
    token = _register_and_login(client, "missingfields@example.com")

    response = client.post(
        "/clinical-documents", json={}, headers=_auth_headers(token)
    )

    assert response.status_code == 422


def test_list_documents_returns_only_current_users_documents(client):
    token_a = _register_and_login(client, "usera@example.com")
    token_b = _register_and_login(client, "userb@example.com")

    _create_document(client, token_a, title="A1")
    _create_document(client, token_a, title="A2")
    _create_document(client, token_b, title="B1")

    response_a = client.get("/clinical-documents", headers=_auth_headers(token_a))
    response_b = client.get("/clinical-documents", headers=_auth_headers(token_b))

    assert response_a.status_code == 200
    assert response_b.status_code == 200

    titles_a = {doc["title"] for doc in response_a.json()}
    titles_b = {doc["title"] for doc in response_b.json()}

    assert titles_a == {"A1", "A2"}
    assert titles_b == {"B1"}


def test_list_documents_requires_authentication(client):
    response = client.get("/clinical-documents")

    assert response.status_code == 401


def test_get_document_by_id_succeeds(client):
    token = _register_and_login(client, "getone@example.com")
    created = _create_document(client, token).json()

    response = client.get(
        f"/clinical-documents/{created['id']}", headers=_auth_headers(token)
    )

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_document_returns_404_for_unknown_id(client):
    token = _register_and_login(client, "getunknown@example.com")

    response = client.get("/clinical-documents/999999", headers=_auth_headers(token))

    assert response.status_code == 404


def test_get_document_returns_404_for_other_users_document(client):
    token_a = _register_and_login(client, "owner@example.com")
    token_b = _register_and_login(client, "intruder@example.com")

    created = _create_document(client, token_a).json()

    response = client.get(
        f"/clinical-documents/{created['id']}", headers=_auth_headers(token_b)
    )

    assert response.status_code == 404


def test_delete_document_succeeds(client):
    token = _register_and_login(client, "deleter@example.com")
    created = _create_document(client, token).json()

    delete_response = client.delete(
        f"/clinical-documents/{created['id']}", headers=_auth_headers(token)
    )
    assert delete_response.status_code == 204

    get_response = client.get(
        f"/clinical-documents/{created['id']}", headers=_auth_headers(token)
    )
    assert get_response.status_code == 404


def test_delete_document_returns_404_for_other_users_document(client):
    token_a = _register_and_login(client, "owner2@example.com")
    token_b = _register_and_login(client, "intruder2@example.com")

    created = _create_document(client, token_a).json()

    response = client.delete(
        f"/clinical-documents/{created['id']}", headers=_auth_headers(token_b)
    )

    assert response.status_code == 404


def test_delete_document_requires_authentication(client):
    response = client.delete("/clinical-documents/1")

    assert response.status_code == 401
