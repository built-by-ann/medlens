import time

import jwt

from app.core.config import settings


def _register_and_login(client, email="me.user@example.com", password="correcthorse123"):
    client.post(
        "/auth/register",
        json={"email": email, "password": password, "name": "Me User"},
    )

    login_response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )

    return login_response.json()["access_token"]


def test_me_returns_current_user_with_valid_token(client):
    token = _register_and_login(client)

    response = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200

    body = response.json()
    assert body["email"] == "me.user@example.com"
    assert body["name"] == "Me User"
    assert "hashed_password" not in body


def test_me_rejects_missing_token(client):
    response = client.get("/users/me")

    assert response.status_code == 401


def test_me_rejects_malformed_token(client):
    response = client.get("/users/me", headers={"Authorization": "Bearer not-a-real-jwt"})

    assert response.status_code == 401


def test_me_rejects_expired_token(client):
    expired_token = jwt.encode(
        {"sub": "1", "exp": time.time() - 60},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    response = client.get("/users/me", headers={"Authorization": f"Bearer {expired_token}"})

    assert response.status_code == 401


def test_me_rejects_token_for_unknown_user(client):
    ghost_token = jwt.encode(
        {"sub": "999999", "exp": time.time() + 60},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    response = client.get("/users/me", headers={"Authorization": f"Bearer {ghost_token}"})

    assert response.status_code == 401


# --- PATCH /users/me (profile editing) ---


def test_update_me_updates_name(client):
    token = _register_and_login(client, email="updatename@example.com")

    response = client.patch(
        "/users/me",
        json={"name": "New Name"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "New Name"
    assert body["email"] == "updatename@example.com"


def test_update_me_updates_email(client):
    token = _register_and_login(client, email="oldemail@example.com")

    response = client.patch(
        "/users/me",
        json={"email": "newemail@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == "newemail@example.com"


def test_update_me_persists_across_requests(client):
    token = _register_and_login(client, email="persisted@example.com")

    client.patch(
        "/users/me",
        json={"name": "Persisted Name"},
        headers={"Authorization": f"Bearer {token}"},
    )

    response = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})

    assert response.json()["name"] == "Persisted Name"


def test_update_me_leaves_email_unchanged_when_only_name_is_sent(client):
    token = _register_and_login(client, email="unchanged@example.com")

    response = client.patch(
        "/users/me",
        json={"name": "Only Name Changed"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.json()["email"] == "unchanged@example.com"


def test_update_me_rejects_email_already_registered_to_another_user(client):
    _register_and_login(client, email="taken@example.com")
    token = _register_and_login(client, email="requester@example.com")

    response = client.patch(
        "/users/me",
        json={"email": "taken@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 409


def test_update_me_allows_resubmitting_own_current_email(client):
    token = _register_and_login(client, email="own-email@example.com")

    response = client.patch(
        "/users/me",
        json={"email": "own-email@example.com", "name": "Still Me"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == "own-email@example.com"


def test_update_me_rejects_invalid_email_format(client):
    token = _register_and_login(client, email="badformat@example.com")

    response = client.patch(
        "/users/me",
        json={"email": "not-an-email"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


def test_update_me_rejects_unexpected_field(client):
    token = _register_and_login(client, email="extrafield@example.com")

    response = client.patch(
        "/users/me",
        json={"name": "Fine", "username": "not-a-real-field"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


def test_update_me_rejects_missing_token(client):
    response = client.patch("/users/me", json={"name": "No Auth"})

    assert response.status_code == 401
