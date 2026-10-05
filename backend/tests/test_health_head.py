"""Uptime monitors probe with HEAD; it must not return 405."""
import pytest


@pytest.mark.parametrize("path", ["/health", "/health/ready"])
def test_health_accepts_head_and_get(client, path):
    assert client.head(path).status_code == 200
    assert client.get(path).status_code == 200
