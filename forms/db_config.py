import mysql.connector


def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="mysql2004",
        database="tmis_db",
        use_pure=True,
    )
