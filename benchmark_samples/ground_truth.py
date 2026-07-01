"""
ground_truth.py — Ground truth findings for benchmark comparison.

Contains expected findings for each test file so precision/recall can be calculated.
For vulnerable_app.py:
- 8 specific vulnerabilities, 6 bug categories
- All marked with exact line numbers and CWE identifiers where applicable

For flask_app.py:
- 13 specific vulnerabilities, 8+ bug categories
- Mix of security, architecture, quality, and performance issues

Use this to evaluate single-agent vs multi-agent performance.
"""

# Ground truth for vulnerable_app.py (192 lines, 8 known bugs)
ground_truth_vulnerable_app = [
    {
        "title": "Hardcoded secret API key",
        "detail": "vulnerable_app.py line 19: API_SECRET = \"sk-live-AbCdEfGhIjKlMnOpQrStUvWxYz\" - exposed in source code (CWE-798)",
        "impact": "Critical",
        "proposal": "Remove hardcoded secret. Use environment variables or secure secret management system."
    },
    {
        "title": "SQL injection in user endpoint",
        "detail": "vulnerable_app.py line 54: query = f\"SELECT * FROM users WHERE id = '{user_id}'\" - user input directly interpolated (CWE-89)",
        "impact": "Critical",
        "proposal": "Use parameterized queries: cursor.execute(\"SELECT * FROM users WHERE id = ?\", (user_id,))"
    },
    {
        "title": "XSS vulnerability in search endpoint",
        "detail": "vulnerable_app.py line 86-93: html = f\"... Search results for: {query}...\" - query reflected without sanitization (CWE-79)",
        "impact": "High",
        "proposal": "Escape HTML special characters: html = f\"... Search results for: {html.escape(query)}...\""
    },
    {
        "title": "Missing CSRF protection",
        "detail": "vulnerable_app.py line 150-151: No CSRF tokens on forms - vulnerable to Cross-Site Request Forgery",
        "impact": "Medium",
        "proposal": "Add CSRF tokens to all state-changing forms using Flask-WTF or similar."
    },
    {
        "title": "N+1 query pattern in search",
        "detail": "vulnerable_app.py line 75-83: Loop over users then executes separate query for each user's orders (performance issue)",
        "impact": "Medium",
        "proposal": "Use JOINs: SELECT users.id, users.name, COUNT(orders.id) as order_count FROM users LEFT JOIN orders ON users.id = orders.user_id GROUP BY users.id"
    },
    {
        "title": "Dead code - unused helper method",
        "detail": "vulnerable_app.py line 135-137: _unused_helper() method defined but never called",
        "impact": "Low",
        "proposal": "Remove unused method or implement it if needed."
    },
    {
        "title": "Global mutable state",
        "detail": "vulnerable_app.py line 22: db_connection = None - global mutable state creates tight coupling and thread safety issues",
        "impact": "Medium",
        "proposal": "Use dependency injection or Flask's g object for request-local storage."
    },
    {
        "title": "High cyclomatic complexity",
        "detail": "vulnerable_app.py line 100-132: _dashboard() method has 8+ branching paths and O(n²) algorithm",
        "impact": "High",
        "proposal": "Extract methods, use lookup tables, avoid nested loops."
    }
]

# Ground truth for flask_app.py (180 lines, 14+ bugs)
ground_truth_flask_app = [
    {
        "title": "Hardcoded secret Flask config",
        "detail": "flask_app.py line 18: app.config['SECRET_KEY'] = 'flask-secret-key-dev-only-evil!@#' - exposed in source code",
        "impact": "Critical",
        "proposal": "Use environment variables: app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')"
    },
    {
        "title": "SQL injection in login endpoint",
        "detail": "flask_app.py line 60: query = f\"SELECT id, username, email, password_hash FROM users WHERE username = '{username}'\" - direct string interpolation (CWE-89)",
        "impact": "Critical",
        "proposal": "Use parameterized queries: cursor.execute(\"SELECT ... WHERE username = ?\", (username,))"
    },
    {
        "title": "XSS vulnerability in users list",
        "detail": "flask_app.py line 104-105: html += f'<li>{user[\"username\"]}: {user[\"email\"]}</li>' - user data not escaped (CWE-79)",
        "impact": "High",
        "proposal": "Escape HTML: from html import escape; html += f'<li>{escape(user[\"username\"])}: {escape(user[\"email\"])}</li>'"
    },
    {
        "title": "XSS vulnerability in search results",
        "detail": "flask_app.py line 121-122: html = f\"<h1>Search Results for: {query}</h1><ul>\" - query reflected unsafely (CWE-79)",
        "impact": "High",
        "proposal": "Escape user input: from html import escape; html = f'<h1>Search Results for: {escape(query)}</h1><ul>'"
    },
    {
        "title": "Missing input validation in login",
        "detail": "flask_app.py line 62-66: No validation of username/password - empty strings allowed",
        "impact": "Medium",
        "proposal": "Add validation: require non-empty strings, validate length and format."
    },
    {
        "title": "Missing error handling - exception exposure",
        "detail": "flask_app.py line 70: return f\"Database error: {str(e)}\", 500 - exposes stack trace",
        "impact": "Medium",
        "proposal": "Catch and log exception, return generic error: return \"Internal server error\", 500"
    },
    {
        "title": "XSS vulnerability in orders list",
        "detail": "flask_app.py line 135: result += f'<li>Order {order[\"id\"]}: User {order[\"user_id\"]} - ${order[\"amount\"]}</li>' - data not escaped",
        "impact": "Medium",
        "proposal": "Use escape function or Jinja2 templates to properly escape HTML."
    },
    {
        "title": "SQL injection in search",
        "detail": "flask_app.py line 133: query = f\"SELECT * FROM orders WHERE status = 'completed' LIMIT {limit}\" - direct interpolation",
        "impact": "High",
        "proposal": "Use parameterized queries: cursor.execute(\"SELECT * FROM orders WHERE status = ? LIMIT ?\", ('completed', limit))"
    },
    {
        "title": "SQL injection in advanced search",
        "detail": "flask_app.py line 132: query = f\"SELECT id, username, email FROM users WHERE username LIKE '%{query}%' OR email LIKE '%{query}%'\" - direct interpolation",
        "impact": "Critical",
        "proposal": "Use parameterized queries: cursor.execute(\"SELECT ... WHERE username LIKE ? OR email LIKE ?\", (f'%{query}%', f'%{query}%'))"
    },
    {
        "title": "Missing authorization - admin dashboard",
        "detail": "flask_app.py line 165-167: /admin/dashboard accessible without authentication - no authorization check",
        "impact": "High",
        "proposal": "Add authorization: if 'user_id' not in session or user is not admin: abort(403)"
    },
    {
        "title": "Insecure session configuration",
        "detail": "flask_app.py line 22-23: app.config['SESSION_COOKIE_HTTPONLY'] = False; app.config['SESSION_COOKIE_SECURE'] = False - security vulnerabilities",
        "impact": "Medium",
        "proposal": "Set HTTPONLY=True and SECURE=True (when using HTTPS)."
    },
    {
        "title": "Debug endpoint exposing sensitive data",
        "detail": "flask_app.py line 181-189: /debug exposes app config, session, environment variables",
        "impact": "Critical",
        "proposal": "Remove debug endpoint or restrict to localhost: if request.remote_addr != '127.0.0.1': abort(404)"
    },
    {
        "title": "Inconsistent password comparison",
        "detail": "flask_app.py line 66: uses compare_strings instead of check_password_hash - vulnerable to timing attacks",
        "impact": "High",
        "proposal": "Use werkzeug.security.check_password_hash for secure password comparison."
    },
    {
        "title": "Dead code - unused utility function",
        "detail": "flask_app.py line 180-182: format_currency() has unreachable code after return statement",
        "impact": "Low",
        "proposal": "Remove unreachable code or restructure function."
    }
]

# Default ground truth - use ground_truth_vulnerable_app for vulnerable_app.py
ground_truth = ground_truth_vulnerable_app

# Mapping of which ground truth to use for each file
FILE_GROUND_TRUTH = {
    "vulnerable_app.py": ground_truth_vulnerable_app,
    "flask_app.py": ground_truth_flask_app,
}