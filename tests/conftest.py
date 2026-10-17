import socket

import pytest


@pytest.fixture(autouse=True)
def _no_sockets(monkeypatch):
    """The suite must not touch the network: recorded fixtures and fakes only."""

    def refuse(*args, **kwargs):
        raise AssertionError("network access attempted during tests")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
