"""One+ test per endpoint, through the real app against a real Postgres."""

import httpx
from fastapi import FastAPI
from sqlalchemy import text

PASSWORD = "correct horse battery"


def body(email: str = "alice@example.com", password: str = PASSWORD) -> dict[str, str]:
    return {"email": email, "password": password}


async def test_health(client: httpx.AsyncClient) -> None:
    resp = await client.get("/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"message": "OK", "code": "ok", "data": {"status": "ok"}}


async def test_docs_served_by_scalar(client: httpx.AsyncClient) -> None:
    resp = await client.get("/docs")
    assert resp.status_code == 200
    assert "scalar" in resp.text.lower()
    assert "/docs" not in (await client.get("/openapi.json")).json()["paths"]


async def test_signup(client: httpx.AsyncClient) -> None:
    resp = await client.post("/v1/auth/signup", json=body("Alice@Example.com"))
    assert resp.status_code == 201
    envelope = resp.json()
    assert set(envelope) == {"message", "code", "data"}
    assert envelope["code"] == "ok"
    data = envelope["data"]
    assert data["email"] == "alice@example.com"
    assert data["user_id"]
    assert "password" not in data


async def test_signup_stores_only_a_hash(client: httpx.AsyncClient, app: FastAPI) -> None:
    await client.post("/v1/auth/signup", json=body())
    async with app.state.engine.connect() as conn:
        stored = (await conn.execute(text("SELECT password_hash FROM users"))).scalar_one()
    assert PASSWORD not in stored
    assert stored.startswith("pbkdf2_sha256$")


async def test_signup_duplicate_returns_error_envelope(client: httpx.AsyncClient) -> None:
    await client.post("/v1/auth/signup", json=body())
    resp = await client.post("/v1/auth/signup", json=body())
    assert resp.status_code == 409
    assert resp.json() == {
        "message": "Email is already registered",
        "code": "email_taken",
        "data": None,
    }


async def test_signup_invalid_input(client: httpx.AsyncClient) -> None:
    for payload in (body("nope"), body(password="short")):
        resp = await client.post("/v1/auth/signup", json=payload)
        assert resp.status_code == 422
        assert resp.json()["code"] == "invalid_input"

    schema = await client.post("/v1/auth/signup", json={"email": "a@example.com"})
    assert schema.status_code == 422
    data = schema.json()
    assert data["code"] == "invalid_input"
    assert {d["field"] for d in data["data"]} == {"password"}


async def test_login(client: httpx.AsyncClient) -> None:
    signup = await client.post("/v1/auth/signup", json=body())
    resp = await client.post("/v1/auth/login", json=body())
    assert resp.status_code == 200
    envelope = resp.json()
    assert set(envelope) == {"message", "code", "data"}
    data = envelope["data"]
    assert data["token_type"] == "bearer"
    assert data["access_token"]
    assert data["user_id"] == signup.json()["data"]["user_id"]


async def test_login_bad_credentials(client: httpx.AsyncClient) -> None:
    await client.post("/v1/auth/signup", json=body())
    for payload in (body(password="wrong password"), body("ghost@example.com")):
        resp = await client.post("/v1/auth/login", json=payload)
        assert resp.status_code == 401
        assert resp.json()["code"] == "invalid_credentials"


async def test_unknown_route_uses_error_envelope(client: httpx.AsyncClient) -> None:
    resp = await client.get("/v1/nope")
    assert resp.status_code == 404
    assert resp.json() == {"message": "Route not found", "code": "not_found", "data": None}
