from db_config import get_connection

conn = get_connection()
cur = conn.cursor()
cur.execute("SHOW TABLES")
print(cur.fetchall())
conn.close()