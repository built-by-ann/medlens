def test_register_creates_user(client):
    response = client.post(
        "/auth/register",
        json={
            "email": "register.success@example.com",
            "password": "supersecret123",
            "name": "Register Success",
        },
    )

    assert response.status_code == 201

    body = response.json()
    assert body["email"] == "register.success@example.com"
    assert body["name"] == "Register Success"
    assert "id" in body
    assert "created_at" in body
    assert "hashed_password" not in body
    assert "password" not in body


def test_register_rejects_duplicate_email(client):
    payload = {"email": "duplicate@example.com", "password": "supersecret123"}

    first = client.post("/auth/register", json=payload)
    assert first.status_code == 201

    second = client.post("/auth/register", json=payload)
    assert second.status_code == 409


def test_register_rejects_invalid_email(client):
    response = client.post(
        "/auth/register",
        json={"email": "not-an-email", "password": "supersecret123"},
    )

    assert response.status_code == 422


def test_register_rejects_short_password(client):
    response = client.post(
        "/auth/register",
        json={"email": "short.password@example.com", "password": "short"},
    )

    assert response.status_code == 422


def test_register_allows_missing_name(client):
    response = client.post(
        "/auth/register",
        json={"email": "no.name@example.com", "password": "supersecret123"},
    )

    assert response.status_code == 201
    assert response.json()["name"] is None
