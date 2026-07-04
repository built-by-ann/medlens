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


def _upload_txt(client, token, filename="note.txt", content=b"Patient reports improvement.", content_type="text/plain", **form_overrides):
    form = {"document_type": "visit_note", "title": "Uploaded Note"}
    form.update(form_overrides)

    return client.post(
        "/clinical-documents/upload-txt",
        data=form,
        files={"file": (filename, content, content_type)},
        headers=_auth_headers(token),
    )


def test_upload_txt_succeeds(client):
    token = _register_and_login(client, "uploader@example.com")

    response = _upload_txt(client, token)

    assert response.status_code == 201

    body = response.json()
    assert body["document_type"] == "visit_note"
    assert body["title"] == "Uploaded Note"
    assert body["raw_text"] == "Patient reports improvement."
    assert body["file_name"] == "note.txt"
    assert body["file_type"] == "txt"


def test_upload_txt_requires_authentication(client):
    response = client.post(
        "/clinical-documents/upload-txt",
        data={"document_type": "visit_note", "title": "Uploaded Note"},
        files={"file": ("note.txt", b"Patient reports improvement.", "text/plain")},
    )

    assert response.status_code == 401


def test_upload_txt_rejects_invalid_file_type(client):
    token = _register_and_login(client, "badfiletype@example.com")

    response = _upload_txt(
        client,
        token,
        filename="note.pdf",
        content=b"%PDF-1.4 fake pdf content",
        content_type="application/pdf",
    )

    assert response.status_code == 422


def test_upload_txt_rejects_empty_file(client):
    token = _register_and_login(client, "emptyfile@example.com")

    response = _upload_txt(client, token, content=b"")

    assert response.status_code == 422


def test_upload_txt_rejects_invalid_encoding(client):
    token = _register_and_login(client, "badencoding@example.com")

    response = _upload_txt(client, token, content=b"\xff\xfe\x00invalid")

    assert response.status_code == 422


def _text_pdf_bytes(text="Patient presents with hypertension."):
    from io import BytesIO

    from reportlab.pdfgen import canvas

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(72, 700, text)
    pdf.save()

    return buffer.getvalue()


def _blank_pdf_bytes():
    from io import BytesIO

    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)

    buffer = BytesIO()
    writer.write(buffer)

    return buffer.getvalue()


def _upload_pdf(client, token, filename="note.pdf", content=None, content_type="application/pdf", **form_overrides):
    if content is None:
        content = _text_pdf_bytes()

    form = {"document_type": "visit_note", "title": "Uploaded PDF Note"}
    form.update(form_overrides)

    return client.post(
        "/clinical-documents/upload-pdf",
        data=form,
        files={"file": (filename, content, content_type)},
        headers=_auth_headers(token),
    )


def test_upload_pdf_succeeds(client):
    token = _register_and_login(client, "pdfuploader@example.com")

    response = _upload_pdf(client, token)

    assert response.status_code == 201

    body = response.json()
    assert body["document_type"] == "visit_note"
    assert body["title"] == "Uploaded PDF Note"
    assert "Patient presents with hypertension." in body["raw_text"]
    assert body["file_name"] == "note.pdf"
    assert body["file_type"] == "pdf"


def test_upload_pdf_requires_authentication(client):
    response = client.post(
        "/clinical-documents/upload-pdf",
        data={"document_type": "visit_note", "title": "Uploaded PDF Note"},
        files={"file": ("note.pdf", _text_pdf_bytes(), "application/pdf")},
    )

    assert response.status_code == 401


def test_upload_pdf_rejects_invalid_file_type(client):
    token = _register_and_login(client, "pdfbadfiletype@example.com")

    response = _upload_pdf(
        client,
        token,
        filename="note.txt",
        content=b"Patient presents with hypertension.",
        content_type="text/plain",
    )

    assert response.status_code == 422


def test_upload_pdf_rejects_empty_file(client):
    token = _register_and_login(client, "pdfemptyfile@example.com")

    response = _upload_pdf(client, token, content=b"")

    assert response.status_code == 422


def test_upload_pdf_rejects_pdf_with_no_extractable_text(client):
    token = _register_and_login(client, "pdfnotext@example.com")

    response = _upload_pdf(client, token, content=_blank_pdf_bytes())

    assert response.status_code == 422


def test_upload_pdf_rejects_malformed_pdf(client):
    token = _register_and_login(client, "pdfmalformed@example.com")

    response = _upload_pdf(client, token, content=b"this is not a real pdf file")

    assert response.status_code == 422
