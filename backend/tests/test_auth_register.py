def test_register_creates_user(client):
    response = client.post(
        "/auth/register",
        json={
            "email": "register.success@example.com",
            "password": "supersecret123",
            "username": "register_success",
            "name": "Register Success",
        },
    )

    assert response.status_code == 201

    body = response.json()
    assert body["email"] == "register.success@example.com"
    assert body["username"] == "register_success"
    assert body["name"] == "Register Success"
    assert "id" in body
    assert "created_at" in body
    assert "hashed_password" not in body
    assert "password" not in body


def test_register_rejects_duplicate_email(client):
    payload = {
        "email": "duplicate@example.com",
        "password": "supersecret123",
        "username": "duplicate_email_user",
    }

    first = client.post("/auth/register", json=payload)
    assert first.status_code == 201

    second = client.post(
        "/auth/register",
        json={**payload, "username": "duplicate_email_user2"},
    )
    assert second.status_code == 409


def test_register_rejects_invalid_email(client):
    response = client.post(
        "/auth/register",
        json={"email": "not-an-email", "password": "supersecret123", "username": "valid_user"},
    )

    assert response.status_code == 422


def test_register_rejects_short_password(client):
    response = client.post(
        "/auth/register",
        json={
            "email": "short.password@example.com",
            "password": "short",
            "username": "short_password",
        },
    )

    assert response.status_code == 422


def test_register_allows_missing_name(client):
    response = client.post(
        "/auth/register",
        json={
            "email": "no.name@example.com",
            "password": "supersecret123",
            "username": "no_name_user",
        },
    )

    assert response.status_code == 201
    assert response.json()["name"] is None


# --- username (Issue #191) ---


def test_register_rejects_missing_username(client):
    response = client.post(
        "/auth/register",
        json={"email": "no.username@example.com", "password": "supersecret123"},
    )

    assert response.status_code == 422


def test_register_rejects_duplicate_username(client):
    first = client.post(
        "/auth/register",
        json={
            "email": "first.user@example.com",
            "password": "supersecret123",
            "username": "sharedname",
        },
    )
    assert first.status_code == 201

    second = client.post(
        "/auth/register",
        json={
            "email": "second.user@example.com",
            "password": "supersecret123",
            "username": "sharedname",
        },
    )

    assert second.status_code == 409


def test_register_rejects_duplicate_username_case_insensitively(client):
    first = client.post(
        "/auth/register",
        json={
            "email": "casefirst@example.com",
            "password": "supersecret123",
            "username": "CaseTest",
        },
    )
    assert first.status_code == 201

    second = client.post(
        "/auth/register",
        json={
            "email": "casesecond@example.com",
            "password": "supersecret123",
            "username": "casetest",
        },
    )

    assert second.status_code == 409


def test_register_preserves_username_casing_on_success(client):
    response = client.post(
        "/auth/register",
        json={
            "email": "preservecase@example.com",
            "password": "supersecret123",
            "username": "MixedCase",
        },
    )

    assert response.status_code == 201
    # Case-insensitive uniqueness (checked above) is not the same as
    # case-insensitive storage - the username a user chose to type should
    # still be exactly what's displayed back to them.
    assert response.json()["username"] == "MixedCase"


def test_register_rejects_username_too_short(client):
    response = client.post(
        "/auth/register",
        json={"email": "tooshort@example.com", "password": "supersecret123", "username": "ab"},
    )

    assert response.status_code == 422


def test_register_rejects_username_too_long(client):
    response = client.post(
        "/auth/register",
        json={
            "email": "toolong@example.com",
            "password": "supersecret123",
            "username": "a" * 31,
        },
    )

    assert response.status_code == 422


def test_register_allows_minimum_and_maximum_username_length(client):
    minimum = client.post(
        "/auth/register",
        json={"email": "minlen@example.com", "password": "supersecret123", "username": "abc"},
    )
    maximum = client.post(
        "/auth/register",
        json={
            "email": "maxlen@example.com",
            "password": "supersecret123",
            "username": "a" * 30,
        },
    )

    assert minimum.status_code == 201
    assert maximum.status_code == 201


def test_register_rejects_username_with_spaces(client):
    response = client.post(
        "/auth/register",
        json={
            "email": "spaces@example.com",
            "password": "supersecret123",
            "username": "not a valid name",
        },
    )

    assert response.status_code == 422


def test_register_rejects_username_with_hyphen(client):
    response = client.post(
        "/auth/register",
        json={
            "email": "hyphen@example.com",
            "password": "supersecret123",
            "username": "not-valid",
        },
    )

    assert response.status_code == 422


def test_register_rejects_username_with_special_characters(client):
    response = client.post(
        "/auth/register",
        json={
            "email": "special@example.com",
            "password": "supersecret123",
            "username": "invalid@name!",
        },
    )

    assert response.status_code == 422


def test_register_allows_underscores_and_periods(client):
    response = client.post(
        "/auth/register",
        json={
            "email": "underscoreperiod@example.com",
            "password": "supersecret123",
            "username": "valid_user.name",
        },
    )

    assert response.status_code == 201
    assert response.json()["username"] == "valid_user.name"
