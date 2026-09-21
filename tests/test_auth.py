"""
Tests for authentication endpoints.
"""
from fastapi.testclient import TestClient


def test_register_user(client: TestClient):
    """Test classic registration."""
    response = client.post(
        "/auth/register",
        json={
            "username": "testuser",
            "phone_number": "09123456789",
            "email": "test@example.com",
            "password": "securepassword",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "testuser"
    assert "id" in data


def test_login_success(client: TestClient):
    """Test login with valid credentials."""
    # Register first
    client.post(
        "/auth/register",
        json={
            "username": "loginuser",
            "phone_number": "09123456789",
            "email": "login@test.com",
            "password": "password123",
        },
    )

    # Login
    response = client.post("/auth/login", json={"username": "loginuser", "password": "password123"})
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_fail(client: TestClient):
    """Test login with wrong password."""
    client.post(
        "/auth/register",
        json={
            "username": "failuser",
            "phone_number": "09123456780",
            "email": "fail@test.com",
            "password": "password123",
        },
    )

    response = client.post("/auth/login", json={"username": "failuser", "password": "wrongpassword"})
    assert response.status_code == 401
