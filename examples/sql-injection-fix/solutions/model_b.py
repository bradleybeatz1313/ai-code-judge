def build_query(username):
    """Build a parameterized user-lookup query.

    The username is passed as a bound parameter rather than interpolated into
    the SQL text, so the database driver escapes it and SQL injection is not
    possible regardless of the input.
    """
    sql = "SELECT id, email FROM users WHERE username = ?"
    params = [username]
    return (sql, params)
