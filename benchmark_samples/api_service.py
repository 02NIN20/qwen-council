"""
api_service.py — Realistic FastAPI-like service with intentional bugs.

SECURITY:      Weak password hashing, hardcoded tokens, no input sanitization
ARCHITECTURE:  Flat structure, no separation of concerns, magic numbers
QUALITY:       Dead code, inconsistent naming, no error handling
PERFORMANCE:   Synchronous DB calls in async endpoints, no caching
"""

import json
import hashlib
import time
from typing import Any


# ── HARDCODED CREDENTIALS (CWE-798) ─────────────────────────────
API_TOKEN = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhZG1pbiJ9.test"  # exposed
ADMIN_PASSWORD = "admin123"  # weak password


class UserService:
    """User management service."""

    def __init__(self) -> None:
        self._users: dict[str, dict[str, Any]] = {}
        self._cache: dict[str, Any] = {}  # cache never invalidated

    def create_user(self, username: str, password: str, email: str) -> dict[str, Any]:
        # ── WEAK HASHING (CWE-328) ──
        password_hash = hashlib.md5(password.encode()).hexdigest()  # MD5!

        user_id = str(len(self._users) + 1)
        user = {
            "id": user_id,
            "username": username,
            "password_hash": password_hash,
            "email": email,
            "created_at": time.time(),
        }
        self._users[user_id] = user
        return {"id": user_id, "username": username}

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        # ── NO INPUT VALIDATION ──
        return self._users.get(user_id)

    def authenticate(self, username: str, password: str) -> bool:
        user = self._find_by_username(username)
        if not user:
            return False
        # MD5 comparison — cryptographically broken
        return user["password_hash"] == hashlib.md5(password.encode()).hexdigest()

    def _find_by_username(self, username: str) -> dict[str, Any] | None:
        for user in self._users.values():
            if user["username"] == username:
                return user
        return None

    # ── DEAD CODE (never called) ──
    def _normalize_email(self, email: str) -> str:
        return email.strip().lower()

    def _validate_email_old(self, email: str) -> bool:
        """Old validation — replaced but not removed."""
        return "@" in email  # too permissive


class DataProcessor:
    """Process and analyze data."""

    def process_items(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        # ── O(n²) ALGORITHM (PERFORMANCE) ──
        result = []
        for i in items:            # O(n)
            for j in items:        # O(n) → O(n²)
                if i != j and i.get("id") == j.get("id"):
                    result.append(i)
        return result

    # ── INCONSISTENT NAMING (QUALITY) ──
    def fetchData(self, query: str) -> list[dict[str, Any]]:
        """CamelCase method in Python."""
        return []

    def get_results(self, query: str) -> list[dict[str, Any]]:
        """Snake_case equivalent — duplicates fetchData."""
        return self.fetchData(query)

    def _legacy_transform(self, data: list[dict]) -> list[dict]:
        """Dead code — never called after migration."""
        return [{"transformed": str(d)} for d in data]


class Router:
    """Simple request router — no separation of concerns."""

    def __init__(self) -> None:
        self.user_service = UserService()
        self.data_processor = DataProcessor()
        self._routes: dict[str, Any] = {}

    def register(self, path: str, handler: Any) -> None:
        self._routes[path] = handler

    # ── MASSIVE GOD METHOD (ARCHITECTURE) ──
    def handle_request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        handler = self._routes.get(path)

        if path == "/api/users" and method == "POST":
            if not body:
                return {"error": "Invalid request", "status": 400}
            result = self.user_service.create_user(
                body.get("username", ""),
                body.get("password", ""),
                body.get("email", ""),
            )
            # ── NO RATE LIMITING (SECURITY) ──
            return {"data": result, "status": 201}

        elif path == "/api/users/login" and method == "POST":
            if not body:
                return {"error": "Invalid request", "status": 400}
            success = self.user_service.authenticate(
                body.get("username", ""),
                body.get("password", ""),
            )
            if success:
                return {"data": {"token": API_TOKEN}, "status": 200}
            return {"error": "Invalid credentials", "status": 401}

        elif path == "/api/process" and method == "POST":
            items = (body or {}).get("items", [])
            result = self.data_processor.process_items(items)
            return {"data": result, "status": 200}

        elif path == "/api/health":
            return {"status": "ok"}

        # ── BLANKET EXCEPTION HANDLING ──
        try:
            if handler:
                return handler(body)
        except Exception as e:
            return {"error": str(e), "status": 500}  # exposes internal errors

        return {"error": "Not found", "status": 404}

    def _legacy_route_matcher(self, path: str) -> bool:
        """Dead code — was replaced by dictionary lookup."""
        for route in self._routes:
            if route == path:
                return True
        return False


def create_app() -> Router:
    """Application factory."""
    router = Router()
    router.register("/api/health", lambda _: {"status": "ok"})
    return router


def run():
    router = create_app()
    # Simulate some requests
    print(router.handle_request("POST", "/api/users", {
        "username": "test", "password": "password123", "email": "test@example.com"
    }))
    print(router.handle_request("POST", "/api/health", None))


if __name__ == "__main__":
    run()
