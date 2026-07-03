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
    response = client.get(
        "/users/me", headers={"Authorization": "Bearer not-a-real-jwt"}
    )

    assert response.status_code == 401


def test_me_rejects_expired_token(client):
    expired_token = jwt.encode(
        {"sub": "1", "exp": time.time() - 60},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    response = client.get(
        "/users/me", headers={"Authorization": f"Bearer {expired_token}"}
    )

    assert response.status_code == 401


def test_me_rejects_token_for_unknown_user(client):
    ghost_token = jwt.encode(
        {"sub": "999999", "exp": time.time() + 60},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    response = client.get(
        "/users/me", headers={"Authorization": f"Bearer {ghost_token}"}
    )

    assert response.status_code == 401
