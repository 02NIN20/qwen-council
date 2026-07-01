"""
vulnerable_app.py — Sample web application with intentional bugs across all 6 categories.

SECURITY:      SQL injection, hardcoded secret, XSS, no rate limiting
ARCHITECTURE:  God object pattern, tight coupling, no dependency injection
QUALITY:       Dead code, high cyclomatic complexity, inconsistent naming
PERFORMANCE:   N+1 query pattern, no caching, O(n²) algorithm
UX:            Missing ARIA labels, no keyboard navigation, low contrast colors
VISUAL:        Inline CSS, layout breaking on mobile, no responsive design
"""

import hashlib
import json
import sqlite3
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

# ── HARDCODED SECRET (CWE-798) ──────────────────────────────────────
API_SECRET = "sk-live-AbCdEfGhIjKlMnOpQrStUvWxYz"  # exposed in source

# ── GLOBAL STATE (ARCHITECTURE: tight coupling) ─────────────────────
db_connection = None  # global mutable state


class GodHandler(BaseHTTPRequestHandler):
    """God object — handles ALL routes in one monolithic class."""

    # ── INLINE CSS (VISUAL/UI) ────────────────────
    STYLES = """
    <style>
      body { font-family: Arial; background: #FFE4E1; color: #999999; } /* low contrast */
      .error { color: red; font-weight: bold; }
      input { border: 1px solid #ccc; padding: 8px; }
    </style>
    """

    def do_GET(self):
        if self.path == "/":
            self._serve_html()
        elif self.path.startswith("/user"):
            self._get_user()
        elif self.path == "/search":
            self._search()
        elif self.path == "/dashboard":
            self._dashboard()
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")

    def _get_user(self):
        # ── SQL INJECTION (CWE-89) ─────────────────
        user_id = self.path.split("=")[-1] if "=" in self.path else ""
        query = f"SELECT * FROM users WHERE id = '{user_id}'"  # vulnerable
        conn = self._get_db()
        cursor = conn.execute(query)
        result = cursor.fetchone()

        if result:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps({"id": result[0], "name": result[1]}).encode())
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'{"error": "User not found"}')

    def _search(self):
        # ── XSS (CWE-79) + N+1 PATTERN (PERFORMANCE) ──
        query = self.path.split("?q=")[-1] if "?q=" in self.path else ""
        conn = self._get_db()
        cursor = conn.execute("SELECT id, name FROM users")
        all_users = cursor.fetchall()

        results = []
        for user in all_users:  # N+1: fetching all users then filtering
            if query.lower() in user[1].lower():
                # Also fetch orders for each user (N+1!)
                order_cursor = conn.execute(
                    f"SELECT * FROM orders WHERE user_id = {user[0]}"
                )
                orders = order_cursor.fetchall()
                results.append({"user": user[1], "orders": len(orders)})

        # ── XSS: reflects query without sanitisation ──
        html = f"""
        <html><body>
        <h1>Search results for: {query}</h1>  <!-- XSS! -->
        <ul>
        {''.join(f'<li>{r["user"]}: {r["orders"]} orders</li>' for r in results)}
        </ul>
        </body></html>
        """
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode())

    def _dashboard(self):
        # ── HIGH CYCLOMATIC COMPLEXITY (QUALITY) ──
        conn = self._get_db()
        mode = self.path.split("mode=")[-1] if "mode=" in self.path else "all"

        if mode == "all":
            data = conn.execute("SELECT * FROM users").fetchall()
        elif mode == "active":
            data = conn.execute("SELECT * FROM users WHERE active=1").fetchall()
        elif mode == "inactive":
            data = conn.execute("SELECT * FROM users WHERE active=0").fetchall()
        elif mode == "vip":
            data = conn.execute("SELECT * FROM users WHERE vip=1").fetchall()
        elif mode == "new":
            data = conn.execute("SELECT * FROM users WHERE created_at > date('now', '-7 days')").fetchall()
        elif mode == "old":
            data = conn.execute("SELECT * FROM users WHERE created_at < date('now', '-1 years')").fetchall()
        elif mode == "banned":
            data = conn.execute("SELECT * FROM banned_users").fetchall()
        elif mode == "deleted":
            data = conn.execute("SELECT * FROM deleted_users").fetchall()
        else:
            data = []

        # O(n²) algorithm (PERFORMANCE)
        result = []
        for a in data:          # O(n)
            for b in data:      # O(n) → O(n²)
                if a != b and a[0] == b[0]:
                    result.append(a)

        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps({"count": len(result)}).encode())

    # ── DEAD CODE (QUALITY) ──
    def _unused_helper(self):
        """This method is never called."""
        return "This is dead code"

    def _export_csv(self):
        """Also dead code — never called from any route."""
        conn = self._get_db()
        data = conn.execute("SELECT * FROM users").fetchall()
        import csv
        from io import StringIO
        output = StringIO()
        writer = csv.writer(output)
        writer.writerows(data)
        return output.getvalue()

    # ── NO RATE LIMITING (SECURITY) ──
    # No protection against brute force / DoS

    # ── MISSING ARIA LABELS (UX) ──
    def _serve_html(self):
        html = """
        <html>
        <head><title>App</title>""" + self.STYLES + """</head>
        <body>
        <h1>Welcome</h1>
        <form action="/search" method="GET">
          <input type="text" name="q" placeholder="Search" />  <!-- no aria-label -->
          <button>Go</button>  <!-- not keyboard-accessible -->
        </form>
        <div class="error" id="msg"></div>
        </body>
        </html>
        """
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode())

    def _get_db(self):
        # ── GLOBAL MUTABLE STATE (ARCHITECTURE) ──
        global db_connection
        if db_connection is None:
            db_connection = sqlite3.connect(":memory:")  # no connection pooling
        return db_connection

    def log_message(self, format, *args):
        # Override to suppress default logging
        pass


def run():
    server = HTTPServer(("0.0.0.0", 8080), GodHandler)
    print("Starting server on port 8080...")
    server.serve_forever()


if __name__ == "__main__":
    run()
