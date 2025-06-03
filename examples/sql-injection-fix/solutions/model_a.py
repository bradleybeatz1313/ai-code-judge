def build_query(username):
    # Interpolates the username straight into the SQL text. This both produces
    # the wrong shape (no bound params) and opens a SQL injection hole.
    sql = f"SELECT id, email FROM users WHERE username = '{username}'"
    params = []
    return (sql, params)
