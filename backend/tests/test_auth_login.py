import jwt

from app.core.config import settings


def _register(client, email="login.user@example.com", password="correcthorse123"):
    response = client.post(
        "/auth/register",
        json={"email": email, "password": password, "name": "Login User"},
    )
    assert response.status_code == 201
    return response.json()


def test_login_returns_access_token(client):
    user = _register(client)

    response = client.post(
        "/auth/login",
        json={"email": "login.user@example.com", "password": "correcthorse123"},
    )

    assert response.status_code == 200

    body = response.json()
    assert body["token_type"] == "bearer"
    assert "access_token" in body

    payload = jwt.decode(
        body["access_token"],
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    assert payload["sub"] == str(user["id"])


def test_login_rejects_wrong_password(client):
    _register(client)

    response = client.post(
        "/auth/login",
        json={"email": "login.user@example.com", "password": "wrongpassword"},
    )

    assert response.status_code == 401


def test_login_rejects_unknown_email(client):
    response = client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "whatever123"},
    )

    assert response.status_code == 401
