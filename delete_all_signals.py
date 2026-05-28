import database as db

db.init_db()
with db.get_conn() as conn:
    conn.execute("DELETE FROM signals")
    conn.execute("DELETE FROM sqlite_sequence WHERE name='signals'")
    conn.commit()

print("All signals deleted.")