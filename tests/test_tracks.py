"""
Tests for track endpoints.
"""
def test_get_tracks_empty(client):
    """Test GET /songs when DB is empty."""
    response = client.get("/songs")
    assert response.status_code == 200
    assert response.json() == []


def test_get_tracks_alias(client):
    """Test /tracks is aliased to /songs."""
    response = client.get("/tracks")
    assert response.status_code == 200
    assert response.json() == []
