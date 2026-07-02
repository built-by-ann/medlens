# API Specification

## Overview

MedLens exposes a REST API that allows authenticated users to upload mock clinical notes, manage medication lists, generate AI analyses, and retrieve previous results.

All endpoints return JSON.

---

# Authentication

Authentication uses JSON Web Tokens (JWT).

Protected endpoints require the following header:

```http
Authorization: Bearer <access_token>
```

---

# Authentication Endpoints

## Register

**POST** `/auth/register`

Creates a new user account.

### Request

```json
{
  "email": "user@example.com",
  "password": "securepassword"
}
```

### Response

```json
{
  "id": 1,
  "email": "user@example.com"
}
```

---

## Login

**POST** `/auth/login`

Authenticates an existing user.

### Request

```json
{
  "email": "user@example.com",
  "password": "securepassword"
}
```

### Response

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer"
}
```

---

## Current User

**GET** `/users/me`

Returns information about the authenticated user.

---

# Clinical Notes

## Create Note

**POST** `/notes`

Creates a new clinical note from pasted text.

### Request

```json
{
  "title": "Primary Care Visit",
  "raw_text": "Patient presents with..."
}
```

---

## Upload Note

**POST** `/notes/upload`

Uploads a `.txt` or `.pdf` clinical note.

---

## Get Notes

**GET** `/notes`

Returns all notes belonging to the authenticated user.

---

## Get Note

**GET** `/notes/{note_id}`

Returns a specific clinical note.

---

## Delete Note

**DELETE** `/notes/{note_id}`

Deletes a clinical note.

---

# Medications

## Create Medication

**POST** `/medications`

Adds a medication to the user's medication list.

### Example Request

```json
{
  "name": "Lisinopril",
  "dosage": "10 mg",
  "frequency": "Daily",
  "status": "Active"
}
```

---

## Get Medications

**GET** `/medications`

Returns the user's medication list.

---

## Update Medication

**PUT** `/medications/{medication_id}`

Updates medication information.

---

## Delete Medication

**DELETE** `/medications/{medication_id}`

Removes a medication.

---

## Upload Medication CSV

**POST** `/medications/upload`

Imports medications from a CSV file.

---

# Analyses

## Create Analysis

**POST** `/analyses`

Generates an AI analysis for a clinical note.

---

## Get Analyses

**GET** `/analyses`

Returns all saved analyses.

---

## Get Analysis

**GET** `/analyses/{analysis_id}`

Returns a single saved analysis.

Example response:

```json
{
  "summary": "...",
  "conditions": [],
  "medications": [],
  "flags": [],
  "follow_up_actions": []
}
```

---

## Delete Analysis

**DELETE** `/analyses/{analysis_id}`

Deletes a saved analysis.

---

# Health

## Health Check

**GET** `/health`

Returns the status of the application.

Example response:

```json
{
  "status": "ok",
  "database": "connected",
  "version": "1.0.0"
}
```

---

# Error Responses

Example validation error:

```json
{
  "detail": "Invalid request."
}
```

Authentication error:

```json
{
  "detail": "Not authenticated."
}
```

---

# Future Endpoints

Potential future endpoints include:

- `POST /files/upload`
- `GET /analyses/{id}/export`
- `GET /metrics`
- `GET /search`
- `GET /admin`

---

## Versioning

The current API is considered **v1**.

Future breaking changes may be released under a versioned API path such as:

```
/api/v2/
```