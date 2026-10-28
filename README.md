# TMIS website first version

A Django website for your existing NFSI MySQL database. Includes staff login,
a dashboard with live enrollment/payment totals, trainee and course search,
pagination, and create/edit forms. Uses your exact table and column names.
Trainee and course tables are unmanaged: Django does not recreate them.
The original desktop application is separate and remains unchanged.

## Windows setup in VS Code

Back up your current database using MySQL Workbench before setup. Extract this
folder and open it in VS Code. In the PowerShell terminal:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:TMIS_DB_NAME="tmis_db"
$env:TMIS_DB_USER="root"
$env:TMIS_DB_PASSWORD="MySql123"
$env:TMIS_DB_HOST="127.0.0.1"
$env:TMIS_DB_PORT="3306"
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver
```

Open http://127.0.0.1:8000/ and sign in using the superuser you just created.
Set connection variables again when you open a new terminal. They are read from
the environment, not a .env file. No real database password is included here.
MySQL 8 or newer is recommended for the supplied schema constraints. If you
use MariaDB 10.4, this project uses Django 4.2 because newer Django versions
require MariaDB 10.5 or later.

`migrate` ADDS Django authentication/session tables to your existing database;
it does not replace the ten project tables. The DB account needs privileges
for those migrations and for reading/inserting/updating the project records.
Use the exact table capitalization from database/schema.sql.

## Existing database versus a fresh installation

If your tables and data already exist, DO NOT rerun schema.sql or seed scripts.
The SQL scripts are reference copies of your supplied project, not migrations.
For a completely empty database only, import in this order using Workbench:
schema.sql, triggers.sql, seed.sql, seed_training.sql, seed_payments.sql,
seed_completion.sql, reports.sql. Then run the Django commands above.
These seed scripts are not safe to run repeatedly.

## What this first version does

- Staff-only website access, Django password hashing, CSRF protection and escaped templates.
- Inactive Django accounts cannot sign in; sessions expire after 15 minutes without requests.
- Dashboard: active trainees/courses/enrollments and confirmed payment revenue.
- Trainees: search by name/email, add/edit and archive through status.
- Courses: search by name/category, add/edit; nonnegative fees and positive capacity.
- Required fields, unique values, account links and future birth dates are checked.
- No permanent-delete button, so staff retain historical records.

When adding a trainee, choose an EXISTING active UserAccount with role trainee
that has no trainee profile yet. This first version does not create UserAccount
records. Your seed data already includes one trainee profile, so adding another
trainee requires first adding a new trainee account using your existing tools.
Django staff logins are SEPARATE from UserAccount. Placeholder seed passwords
cannot be used to sign in. `createsuperuser` creates the website administrator.

## Remaining conversion work

This is the first website increment, not the complete TMIS implementation.
Enrollment/session/attendance/payment/certificate/notification management,
web reports, trainee self-service, trainer-specific permissions, account
provisioning and administrator MFA remain to be implemented. Existing SQL
triggers and report limitations from the desktop project remain unchanged.
Do not publicly deploy using the development defaults or runserver. Configure
a private secret key, DEBUG=0, HTTPS and production hosting first.

## Checks

`python manage.py check` validates Django configuration. `python manage.py test`
runs form-validation and route/access/template tests without needing MySQL when
TMIS_TEST_SQLITE=1 is set. Real MySQL integration still needs verification against
your database; this package has not connected to your computer.
