# Using the reports

The Report dropdown lists the six built-in reports, every table and every view.

Exports (CSV, PDF, HTML) are saved to the exports/ folder in the project. Tick Choose save location to pick another folder.
PDF export needs the reportlab package.



# Problem	Fix

No module named 'mysql'	Activate the virtual environment, then pip install mysql-connector-python

No module named 'tkinter'	sudo apt install python3-tk

No module named 'reportlab'	pip install reportlab

Access denied for user	Check the user and password in forms/db_config.py

Unknown database 'tmis_db'	Run database/schema.sql first

"Report is not installed"	Run database/reports.sql

PROCEDURE ... does not exist	Run database/queries.sql

Nothing shows in tables or reports	Run the seed files, or add records through the forms

Dialogs open behind the window	Use the latest tmis_forms.py and tmis_reports.py

# run instructions

python forms/tmis_forms.py       

 # data entry forms and read-only views

python reports/tmis_reports.py    
# reports, filters and exports
