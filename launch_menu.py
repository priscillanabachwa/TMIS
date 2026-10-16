import os
import sys
import mysql.connector

print("=== Starting TMIS Database & Opening Full Forms Menu ===")

# 1. Connect to MySQL as root
try:
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="root123",
        autocommit=True
    )
    cursor = conn.cursor()
    print("✅ Connected to MySQL as 'root'.")
except Exception as e:
    print(f"❌ Connection failed: {e}")
    sys.exit(1)

# 2. Reset Database Cleanly
cursor.execute("DROP DATABASE IF EXISTS tmis_db;")
cursor.execute("CREATE DATABASE tmis_db CHARACTER SET utf8mb4;")
cursor.execute("USE tmis_db;")

# 3. Load Schema & Seed Data
sql_files = [
    "database/schema.sql",
    "database/seed.sql",
    "database/seed_training.sql",
    "database/seed_payments.sql",
    "database/seed_completion.sql"
]

for filepath in sql_files:
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        statements = [s.strip() for s in content.split(';') if s.strip()]
        for stmt in statements:
            try:
                cursor.execute(stmt)
            except Exception:
                pass
        print(f"✅ Imported {filepath}")

# 4. Verify Tables
cursor.execute("SHOW TABLES;")
tables = [r[0] for r in cursor.fetchall()]
print(f"✅ Loaded {len(tables)} tables into tmis_db: {', '.join(tables)}")

cursor.close()
conn.close()

# 5. Write db_config.py in all necessary folders
cfg = """import mysql.connector

def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="root123",
        database="tmis_db",
        use_pure=True,
    )
"""

os.makedirs("forms", exist_ok=True)
with open("forms/db_config.py", "w") as f:
    f.write(cfg)
with open("db_config.py", "w") as f:
    f.write(cfg)

# 6. Launch the Main Forms Menu
forms_dir = os.path.abspath("forms")
os.environ["PYTHONPATH"] = forms_dir + os.pathsep + os.environ.get("PYTHONPATH", "")

print("\n🚀 Opening TMIS Main Forms Menu...\n")
os.chdir(forms_dir)
os.system(f'"{sys.executable}" tmis_forms.py')