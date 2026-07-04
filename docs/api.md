# API Reference

## Overview

MedLens exposes a REST API built with FastAPI. This document describes the endpoints that are currently implemented.

All endpoints return JSON.

---

## Base URL

```text
http://localhost:8000
```

This is the local development URL when running the backend directly (`uvicorn app.main:app --reload`) or through Docker Compose (`docker compose up --build` from `infra/`).

---

## Authentication

Authentication uses JSON Web Tokens (JWT).

A token is obtained by calling `POST /auth/login` with valid credentials. The token is a short-lived access token containing the user's id in the `sub` claim, signed with the algorithm and secret configured in the backend settings, and expiring after `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` (30 minutes by default).

Protected endpoints require the token to be sent as a Bearer token in the `Authorization` header:

```http
Authorization: Bearer <access_token>
```

If the header is missing, the token is malformed or expired, or the token references a user that no longer exists, the request is rejected with `401 Unauthorized`.

---

## Endpoints

### GET /

Description

Root endpoint. Confirms the API is running.

Request

No parameters or body.

Response

```json
{
  "message": "Welcome to MedLens API"
}
```

---

### GET /health

Description

Reports API and database connectivity status.

Request

No parameters or body.

Response

```json
{
  "status": "ok",
  "database": "connected"
}
```

If the database connection fails, the response body reflects the failure instead:

```json
{
  "status": "error",
  "database": "disconnected",
  "detail": "<error message>"
}
```

Note: the endpoint currently returns HTTP `200` in both cases. Callers should check the `status` field in the body rather than the HTTP status code.

---

### POST /auth/register

Purpose

Creates a new user account.

Request body

```json
{
  "email": "user@example.com",
  "password": "securepassword",
  "name": "Jane Doe"
}
```

`name` is optional.

Validation rules

- `email` must be a valid email address.
- `password` must be at least 8 characters long.
- `email` must not already belong to a registered user.

Success response

`201 Created`

```json
{
  "id": 1,
  "email": "user@example.com",
  "name": "Jane Doe",
  "created_at": "2026-07-03T19:13:05.755361Z"
}
```

The stored password hash is never included in the response.

Possible error responses

- `409 Conflict` — the email is already registered.
- `422 Unprocessable Entity` — invalid email format, password shorter than 8 characters, or missing required fields.

---

### POST /auth/login

Purpose

Authenticates an existing user and issues an access token.

Request body

```json
{
  "email": "user@example.com",
  "password": "securepassword"
}
```

Success response

`200 OK`

JWT response format

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer"
}
```

The decoded token payload contains:

```json
{
  "sub": "1",
  "exp": 1783108877
}
```

`sub` is the authenticated user's id (as a string); `exp` is the expiration time as a Unix timestamp.

Possible error responses

- `401 Unauthorized` — the email is not registered, or the password is incorrect. The same error message is returned in both cases so that the response does not reveal whether an email is registered.
- `422 Unprocessable Entity` — missing or malformed request body.

---

### GET /users/me

Purpose

Returns the profile of the currently authenticated user.

Authentication requirements

Requires a valid Bearer token in the `Authorization` header, as described above.

Success response

`200 OK`

```json
{
  "id": 1,
  "email": "user@example.com",
  "name": "Jane Doe",
  "created_at": "2026-07-03T19:13:05.755361Z"
}
```

401 responses

- Missing `Authorization` header — `{"detail": "Not authenticated"}`
- Invalid, malformed, or expired token — `{"detail": "Could not validate credentials"}`
- Token is well-formed and correctly signed but references a user id that no longer exists — `{"detail": "Could not validate credentials"}`

---

## Error Responses

### 400 Bad Request

Reserved for malformed requests. No endpoint currently returns this status directly — request body validation failures surface as `422` instead (see below).

### 401 Unauthorized

Returned for failed login attempts and for any request to a protected endpoint that lacks a valid, current access token.

```json
{
  "detail": "Incorrect email or password"
}
```

```json
{
  "detail": "Could not validate credentials"
}
```

### 409 Conflict

Returned by `POST /auth/register` when the given email is already registered.

```json
{
  "detail": "A user with this email is already registered"
}
```

### 422 Unprocessable Entity

Returned when the request body fails validation (invalid email format, password too short, missing required fields, or malformed JSON).

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "email"],
      "msg": "Field required"
    }
  ]
}
```

---

## Notes

This API currently supports authentication and application infrastructure only (`/`, `/health`, `/auth/register`, `/auth/login`, `/users/me`). Clinical document management, medication extraction, and reconciliation endpoints are not yet implemented and will be introduced in future sprints.
