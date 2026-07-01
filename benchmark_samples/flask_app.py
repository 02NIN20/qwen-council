"""
flask_app.py — Small but realistic Flask web application (~180 lines) with intentional bugs.
This simulates a real-world production app with common vulnerabilities.

BUG CATEGORIES:
1. SQL Injection - Unsafe direct query construction
2. Hardcoded Secrets - Internal API keys exposed
3. XSS Vulnerability - Unescaped user input in templates
4. Missing CSRF Protection - No CSRF tokens on forms
5. No Input Validation - Direct use of untrusted data
6. Missing Error Handling - Unhandled exceptions expose stack traces
7. Dead Code - Unused routes and imports
8. Performance Issues - N+1 query pattern
"""

from flask import Flask, render_template_string, request, redirect, url_for, abort, jsonify, session
from flask_session import Session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import json
from functools import wraps
import hashlib
from datetime import datetime, timedelta

app = Flask(__name__)

# ---- BUG 1: Hardcoded Secret (CWE-798) ----------------------------------
# Real production apps would store these in environment variables
app.config['SECRET_KEY'] = 'flask-secret-key-dev-only-evil!@#'

# ---- BUG 2: Missing Proper Session Security -----------------------------------
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_COOKIE_HTTPONLY'] = False  # Should be True to prevent XSS
app.config['SESSION_COOKIE_SECURE'] = False    # Should be True in production (HTTPS)
Session(app)

# ---- DATABASE SETUP -----------------------------------------------------------

def get_db_connection():
    """Get database connection with no connection pooling."""
    conn = sqlite3.connect('app.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database with sample data - called once."""
    conn = get_db_connection()
    
    # Create users table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            email TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create orders table  
    conn.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    
    # Insert sample users only if empty
    cursor = conn.execute('SELECT COUNT(*) as count FROM users')
    if cursor.fetchone()['count'] == 0:
        users = [
            ('alice', 'alice@example.com', generate_password_hash('password123')),
            ('bob', 'bob@example.com', generate_password_hash('password456')),
            ('charlie', 'charlie@example.com', generate_password_hash('password789')),
        ]
        conn.executemany(
            'INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
            users
        )
        conn.commit()
    
    conn.close()

# Initialize database
init_db()

# ---- BUG 3: Missing CSRF Protection -------------------------------------------
def csrf_protect(f):
    """Decorator to add CSRF protection (but NOT used)."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method == 'POST':
            # CSRF token validation would go here
            # But this IS buggy - missing CSRF validation
            pass
        return f(*args, **kwargs)
    return decorated_function

# ---- BUG 4: Insecure Password Handling ----------------------------------------
def insecure_password_comparison(stored_hash, provided_password):
    """BUG: Direct string comparison of hashes instead of using check_password_hash."""
    # Should use: return check_password_hash(stored_hash, provided_password)
    # But instead uses vulnerable comparison
    return generate_password_hash(provided_password) == stored_hash

# ---- ROUTES -------------------------------------------------------------

@app.route('/')
def index():
    """Homepage - no authentication required."""
    return render_template_string('''
        <html>
        <head><title>Flask App</title></head>
        <body>
            <h1>Welcome</h1>
            <p>Demo application with intentional bugs</p>
            <ul>
                <li><a href="/login">Login</a></li>
                <li><a href="/users">View Users</a></li>
                <li><a href="/orders">View Orders</a></li>
                <li><a href="/admin/dashboard">Admin Dashboard</a></li>
                <li><a href="/debug" style="color: red;">(Debug endpoint)</a></li>
            </ul>
        </body>
        </html>
    ''')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login route - bugs: no rate limiting, insecure password handling, no validation."""
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        
        # BUG 5: No input validation - empty strings allowed
        # BUG 6: Missing error handling - could throw exceptions
        
        conn = get_db_connection()
        try:
            # BUG 1: SQL injection vulnerability
            query = f"SELECT id, username, email, password_hash FROM users WHERE username = '{username}'"
            user = conn.execute(query).fetchone()
            
            if user and insecure_password_comparison(user['password_hash'], password):
                # Successful login
                session['user_id'] = user['id']
                session['username'] = user['username']
                return redirect(url_for('profile'))
            else:
                # Generic error message - could leak info via timing attacks
                return "Invalid credentials", 401
        except Exception as e:
            # BUG 6: Unhandled exception - could expose stack trace
            # Should catch and return generic error
            return f"Database error: {str(e)}", 500
        finally:
            conn.close()
    
    return render_template_string('''
        <form method="POST">
            <h2>Login</h2>
            <input type="text" name="username" placeholder="Username" required>
            <input type="password" name="password" placeholder="Password" required>
            <button type="submit">Login</button>
        </form>
    ''')

@app.route('/profile')
def profile():
    """User profile - no authorization check."""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    conn = get_db_connection()
    
    # BUG 7: Dead code route (never used)
    # This function defines but never calls get_user_stats()
    def get_user_stats(user_id):
        """Dead code - defined but never called."""
        stats = conn.execute('SELECT COUNT(*) as order_count FROM orders WHERE user_id = ?', (user_id,)).fetchone()
        return stats['order_count']
    
    # BUG 8: Performance issue - N+1 query pattern
    # Instead of JOIN, makes separate queries for each user's orders
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    
    # BUG 8: Performance issue - N+1 pattern (looks fine but hides in loop)
    orders = []
    for order in conn.execute('SELECT * FROM orders WHERE user_id = ?', (user_id,)).fetchall():
        # Could join in single query instead
        orders.append(dict(order))
    
    conn.close()
    
    return render_template_string('''
        <h2>Profile: {{ username }}</h2>
        <p>Email: {{ email }}</p>
        <p>Orders count: {{ order_count }}</p>
        <a href="/logout">Logout</a>
    ''', username=user['username'], email=user['email'], order_count=len(orders))

@app.route('/users')
def users_list():
    """List all users - bug: exposes sensitive data (password hashes)."""
    conn = get_db_connection()
    
    # BUG: Exposes password hashes in response
    users = conn.execute('SELECT id, username, email FROM users').fetchall()
    conn.close()
    
    html = '<h1>All Users</h1><ul>'
    for user in users:
        # BUG 3: XSS vulnerability - user data not escaped in HTML
        html += f'<li>{user["username"]} ({user["email"]})</li>'
    html += '</ul>'
    return html

@app.route('/orders')
def orders_list():
    """List orders - bug: poor error handling and output encoding."""
    try:
        conn = get_db_connection()
        
        # BUG: No input validation for limit parameter
        limit = int(request.args.get('limit', 10))
        if limit > 100:  # Arbitrary limit
            limit = 100
            
        # BUG: SQL injection via direct string formatting
        query = f"SELECT * FROM orders WHERE status = 'completed' LIMIT {limit}"
        orders = conn.execute(query).fetchall()
        conn.close()
        
        # BUG 3: XSS - orders data not escaped when rendered
        result = '<h1>Orders</h1><ul>'
        for order in orders:
            result += f'<li>Order {order["id"]}: User {order["user_id"]} - ${order["amount"]}</li>'
        result += '</ul>'
        return result
        
    except Exception as e:
        # BUG 6: Unhandled exception - stack trace would be exposed
        return f"Error: {str(e)}", 500

@app.route('/search')
def search():
    """Search endpoint - multiple bugs including SQL injection and XSS."""
    query = request.args.get('q', '')
    
    conn = get_db_connection()
    try:
        # BUG 1: SQL injection in search
        # BUG 8: Performance issue - could use LIMIT/offset
        users = conn.execute(f"SELECT id, username, email FROM users WHERE username LIKE '%{query}%' OR email LIKE '%{query}%'").fetchall()
        
        # BUG 3: XSS - query reflected without escaping in HTML
        html = f"<h1>Search Results for: {query}</h1><ul>"
        for user in users:
            # BUG 3: XSS - user data not escaped
            html += f"<li>{user['username']}: {user['email']}</li>"
        html += "</ul>"
        return html
        
    finally:
        conn.close()

# ---- ADMIN ENDPOINTS (ONLY FOR BUG DEMONSTRATION) ---------------------------

@app.route('/admin/dashboard')
def admin_dashboard():
    """Admin dashboard with sensitive data exposure."""
    # BUG: No authorization check - anyone can access admin endpoint
    
    conn = get_db_connection()
    try:
        # BUG: Exposes internal database structure and secrets
        users = conn.execute('SELECT * FROM users').fetchall()
        orders = conn.execute('SELECT * FROM orders').fetchall()
        
        # BUG: Insecure debug endpoint
        result = "<h1>Admin Dashboard</h1>"
        result += f"<p>Users: {len(users)}</p>"
        result += f"<p>Orders: {len(orders)}</p>"
        
        # BUG: Exposes SQL schema
        result += "<h2>Database Schema</h2><pre>"
        result += "CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, email TEXT, password_hash TEXT);\n"
        result += "CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER, amount REAL);\n"
        result += "</pre>"
        
        # BUG: Debug endpoint exposing internal state
        result += "<h2>Environment</h2><pre>"
        result += json.dumps(dict(os.environ), indent=2)
        result += "</pre>"
        
        return result
        
    finally:
        conn.close()

@app.route('/debug')
def debug():
    """Debug endpoint - exposes stack traces and internal state."""
    # BUG 6: Missing error handling - would expose full traceback
    # BUG: Sensitive data exposure
    
    error_msg = request.args.get('error', '')
    if error_msg:
        # BUG 6: Unhandled exception simulation
        raise Exception(f"Simulated error: {error_msg}")
    
    return json.dumps({
        'app_config': dict(app.config),
        'session': dict(session),
        'server_info': {
            'python_version': '3.8+',
            'flask_version': '2.x',
            'database_path': 'app.db'
        }
    }, indent=2)

@app.route('/logout')
def logout():
    """Logout endpoint."""
    session.clear()
    return redirect(url_for('index'))

# ---- UTILITY FUNCTIONS --------------------------------------------------

def format_currency(amount):
    """Format currency - has unreachable code after return."""
    if amount < 0:
        return "-${:.2f}".format(-amount)
    return "${:.2f}".format(amount)
    # Dead code - this never executes (unreachable)
    print("This never prints!")

# ---- CREATE TABLES IF NOT EXISTS (RUNS ON IMPORT) ---------------------------
# Tables are created in init_db() function above

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
