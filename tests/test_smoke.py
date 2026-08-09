"""Minimal smoke tests -- also gives the CI pytest step something to collect
(it was previously failing with exit code 5 / "no tests collected", separate
from and masked by the flake8 step failing first)."""
import os

os.environ.setdefault("DATA_DIR", "/tmp")

import app  # noqa: E402  (import after DATA_DIR is set)


def test_app_imports():
    assert app.app is not None
    assert app.socketio is not None


def test_flask_routes_registered():
    rules = {r.rule for r in app.app.url_map.iter_rules()}
    assert "/" in rules
    assert "/api/profile/avatar" in rules
