# TMIS forms setup

Run these commands from the `forms` directory before opening the forms:

```powershell
python -m pip install mysql-connector-python
python --version
python -m tkinter
python -c "import mysql.connector; print('connector OK')"
```

The final command must print:

```text
connector OK
```

`python -m tkinter` should open a small Tkinter test window. Close that
window before continuing.

After the checks pass:

1. Copy `db_config.example.py` to `db_config.py`.
2. Set the MySQL connection values in `db_config.py`.
3. Ensure the `tmis_db` database is running and available.
4. Test the database connection:

   ```powershell
   python test_connection.py
   ```

5. Start the forms:

   ```powershell
   python tmis_forms.py
   ```

`db_config.py` is intentionally ignored by Git because it contains local
database credentials.

## Using reports

From the main TMIS window, click **Open reports**. Select one of the available
reports, then use **Search** or **Refresh** as needed. Click **Export CSV** to
save the currently displayed report rows. Use **Print / HTML** to open a
print-ready version in a browser; from the browser print dialog, choose
**Save as PDF** if a PDF is required.

The report window is implemented separately in `../reports/tmis_reports.py`;
from the project root it can be started directly with:

```powershell
python reports\tmis_reports.py
```

The report views must be imported into `tmis_db` from
`../database/reports.sql` before they can be displayed. Report definitions and
business explanations are documented in `../reports/REPORTS_DOCUMENTATION.md`.
