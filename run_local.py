"""Run the local website using the existing desktop database configuration."""
import ast
import os
from pathlib import Path
import sys

tree = ast.parse(Path('forms/db_config.py').read_text())
call = next(n for n in ast.walk(tree) if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute) and n.func.attr == 'connect')
mapping = {'host': 'HOST', 'user': 'USER', 'password': 'PASSWORD',
           'database': 'NAME', 'port': 'PORT'}
for keyword in call.keywords:
    if keyword.arg in mapping:
        os.environ['TMIS_DB_' + mapping[keyword.arg]] = str(ast.literal_eval(keyword.value))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from django.core.management import execute_from_command_line

if '--refresh-data' in sys.argv:
    from django.db import connection, transaction
    with transaction.atomic(), connection.cursor() as cursor:
        for filename in ['seed_sample.sql', 'refresh_catalogue.sql']:
            sql = '\n'.join(line for line in Path('database', filename).read_text().splitlines()
                            if not line.lstrip().startswith('--'))
            for statement in sql.split(';'):
                statement = statement.strip()
                if statement and not statement.upper().startswith(('USE ', 'START TRANSACTION', 'COMMIT')):
                    cursor.execute(statement)
            print(filename, 'applied', flush=True)
else:
    execute_from_command_line(['manage.py', 'runserver', '127.0.0.1:8000', '--noreload'])
