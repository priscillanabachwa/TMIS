"""TMIS report viewer, filtering, pagination, and CSV export."""
import csv
import html
import re
import sys
import traceback
import tkinter as tk
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import webbrowser

import mysql.connector

FORMS_DIR = Path(__file__).resolve().parent.parent / "forms"
if str(FORMS_DIR) not in sys.path:
    sys.path.insert(0, str(FORMS_DIR))

from db_config import get_connection

PAGE = "#f4f6f2"
INK = "#163b35"
PRIMARY = "#16634e"
DARK_GREEN = "#123d34"
MUTED = "#71817b"
PAGE_SIZE = 100
EXPORT_DIR = Path(__file__).resolve().parent.parent / "exports"


def configure_theme(root):
    root.configure(bg=PAGE)
    root.option_add("*Background", PAGE)
    root.option_add("*Foreground", INK)
    root.option_add("*Button.Background", PRIMARY)
    root.option_add("*Button.Foreground", "white")
    root.option_add("*Button.ActiveBackground", "#0d4939")
    root.option_add("*Button.ActiveForeground", "white")
    root.option_add("*Entry.Background", "white")
    root.option_add("*Entry.Foreground", INK)

    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")
    style.configure("TFrame", background=PAGE)
    style.configure("TLabel", background=PAGE, foreground=INK)
    style.configure("TEntry", fieldbackground="white", foreground=INK)
    style.configure("TCombobox", fieldbackground="white", foreground=INK)
    style.configure(
        "Treeview", background="white", fieldbackground="white",
        foreground=INK, rowheight=26)
    style.configure(
        "Treeview.Heading", background="#f8faf7", foreground=MUTED,
        font=("Segoe UI", 9, "bold"))
    style.map(
        "Treeview", background=[("selected", PRIMARY)],
        foreground=[("selected", "white")])


REPORTS = {
    "Course performance and revenue": "rpt_course_performance_summary",
    "Attendance and certificate eligibility": "rpt_trainee_attendance_eligibility",
    "Outstanding debtors": "rpt_outstanding_debtors",
    "Trainer workload": "rpt_trainer_workload",
    "Session attendance register": "rpt_session_attendance_register",
    "Certificate dispatch": "rpt_certificate_dispatch",
}

DATE_COLUMNS = {
    "sessiondate": "Session date",
    "issuedate": "Issue date",
    "enrollmentdate": "Enrollment date",
    "paymentdate": "Payment date",
    "registrationdate": "Registration date",
    "datesent": "Date sent",
    "datejoined": "Date joined",
    "createdat": "Date created",
    "recordedat": "Date recorded",
}
FILTER_COLUMNS = {
    "certificationeligibility": "Eligibility",
    "paymentstatus": "Payment",
    "coursestatus": "Course",
    "attendancestatus": "Attendance",
    "certificatestatus": "Certificate",
    "enrollmentstatus": "Enrollment",
    "sessionstatus": "Session",
    "traineestatus": "Trainee",
    "staffstatus": "Staff",
    "accountstatus": "Account",
    "deliverystatus": "Delivery",
    "notificationtype": "Type",
    "paymentmethod": "Method",
    "role": "Role",
    "gender": "Gender",
}

# Most rows a table or view can load into the report screen at once
MAX_ROWS = 10000

# Columns that must never be shown in a report
HIDDEN_COLUMNS = {"passwordhash"}

TABLE_LABELS = {
    "trainee": "Trainee", "course": "Course", "trainingsession": "Training session",
    "enrollment": "Enrollment", "attendance": "Attendance", "payment": "Payment",
    "certificate": "Certificate", "staff": "Staff", "useraccount": "User account",
    "notification": "Notification",
}

# What the summary line above each report shows: (column, mode, argument)
#   sum   - total of the column
#   avg   - average of the column
#   count - number of rows where the column equals the argument
SUMMARY_COLUMNS = {
    "rpt_course_performance_summary": [
        ("TotalEnrolled", "sum", None),
        ("TotalRevenueCollected", "sum", None),
        ("OutstandingBalance", "sum", None),
    ],
    "rpt_trainee_attendance_eligibility": [
        ("CertificationEligibility", "count", "ELIGIBLE"),
        ("AttendancePercentage", "avg", None),
    ],
    "rpt_outstanding_debtors": [
        ("TotalAmountPaid", "sum", None),
        ("BalanceDue", "sum", None),
    ],
    "rpt_trainer_workload": [
        ("TotalSessionsAssigned", "sum", None),
        ("CompletedSessions", "sum", None),
        ("UpcomingSessions", "sum", None),
    ],
    "rpt_session_attendance_register": [
        ("AttendanceStatus", "count", "present"),
        ("AttendanceStatus", "count", "not recorded"),
    ],
    "rpt_certificate_dispatch": [
        ("CertificateStatus", "count", "issued"),
    ],
    "Payment": [
        ("AmountPaid", "sum", None),
    ],
    "Course": [
        ("MaximumCapacity", "sum", None),
    ],
}

# All valid statuses defined in schema.sql CHECK constraints
SCHEMA_STATUSES = {
    "coursestatus": ("active", "inactive", "archived"),
    "enrollmentstatus": ("pending", "active", "completed", "cancelled", "withdrawn"),
    "paymentstatus": ("pending", "partially paid", "paid"),
    "attendancestatus": ("present", "absent", "late", "excused", "not recorded"),
    "certificatestatus": ("issued", "revoked", "replaced"),
    "sessionstatus": ("scheduled", "completed", "postponed", "cancelled"),
    "certificationeligibility": (
        "ELIGIBLE",
        "INELIGIBLE (Low Attendance)",
        "INELIGIBLE (Pending Payment)",
        "INELIGIBLE (Attendance & Payment Deficit)",
        "PENDING (No Sessions Scheduled)",
        "NOT APPLICABLE (Enrollment Ended)",
    ),
    "traineestatus": ("active", "inactive", "archived"),
    "staffstatus": ("active", "inactive", "archived"),
    "accountstatus": ("active", "inactive", "suspended"),
    "deliverystatus": ("pending", "sent", "delivered", "failed"),
}

WIDTH_HINTS = {
    "email": 220,
    "organization": 200,
    "traineename": 160,
    "trainername": 160,
    "coursename": 180,
    "venueplatform": 220,
    "serialnumber": 160,
    "transactionreference": 160,
    "invoicenumber": 150,
    "phoneno": 130,
    "paymentstatus": 130,
    "enrollmentstatus": 130,
    "certificatestatus": 130,
    "certificationeligibility": 210,
    "traineeid": 90,
    "courseid": 90,
    "staffid": 90,
    "sessionid": 90,
    "certificateid": 100,
    "coursefee": 130,
    "totalamountpaid": 140,
    "balancedue": 140,
    "totalrevenuecollected": 170,
    "outstandingbalance": 170,
    "maximumcapacity": 140,
    "totalenrolled": 130,
    "capacityutilizationpercent": 200,
    "attendancepercentage": 160,
    "totalsessionsscheduled": 160,
    "sessionsattended": 150,
    "totalsessionsassigned": 160,
    "completedsessions": 160,
    "upcomingsessions": 160,
    "distinctcoursestaught": 150,
}

CUSTOM_LABELS = {
    "courseid": "Course ID",
    "coursename": "Course Name",
    "category": "Category",
    "duration": "Duration",
    "coursefee": "Course Fee",
    "maximumcapacity": "Max Capacity",
    "totalenrolled": "Total Enrolled",
    "capacityutilizationpercent": "Capacity Utilization (%)",
    "totalrevenuecollected": "Revenue Collected",
    "outstandingbalance": "Outstanding Balance",
    "coursestatus": "Course Status",
    "traineeid": "Trainee ID",
    "traineename": "Trainee Name",
    "phoneno": "Phone No",
    "email": "Email",
    "organization": "Organization",
    "paymentstatus": "Payment Status",
    "enrollmentstatus": "Enrollment Status",
    "enrollmentdate": "Enrollment Date",
    "totalamountpaid": "Amount Paid",
    "balancedue": "Balance Due",
    "totalsessionsscheduled": "Sessions Scheduled",
    "sessionsattended": "Sessions Attended",
    "attendancepercentage": "Attendance (%)",
    "certificationeligibility": "Certification Eligibility",
    "staffid": "Staff ID",
    "trainername": "Trainer Name",
    "department": "Department",
    "totalsessionsassigned": "Sessions Assigned",
    "completedsessions": "Completed Sessions",
    "upcomingsessions": "Upcoming Sessions",
    "distinctcoursestaught": "Courses Taught",
    "sessionid": "Session ID",
    "sessiondate": "Session Date",
    "starttime": "Start Time",
    "endtime": "End Time",
    "venueplatform": "Venue / Platform",
    "attendancestatus": "Attendance Status",
    "checkintime": "Check-In Time",
    "certificateid": "Certificate ID",
    "serialnumber": "Serial Number",
    "issuedate": "Issue Date",
    "certificatestatus": "Certificate Status",
    "issuedbyofficer": "Issued By",
    "officerrole": "Officer Role",
    "nin": "NIN",
}


def format_header(column_name):
    col_lower = str(column_name).lower()
    if col_lower in CUSTOM_LABELS:
        return CUSTOM_LABELS[col_lower]
    spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", str(column_name))
    return re.sub(r"\bId\b", "ID", spaced)


def format_time(value):
    total = int(value.total_seconds())
    return f"{total // 3600:02d}:{total % 3600 // 60:02d}:{total % 60:02d}"


def format_cell(column_name, value):
    if value is None:
        return ""
    if isinstance(value, timedelta):
        return format_time(value)
    col_lower = column_name.lower()
    # Identifier columns (TraineeID, CourseID ...) are shown as plain numbers
    if str(column_name).endswith("ID") and not isinstance(value, str):
        return str(value)
    # Percentages
    if "percent" in col_lower or "percentage" in col_lower or "utilization" in col_lower:
        try:
            return f"{float(value):.1f}%"
        except (ValueError, TypeError):
            return str(value)
    # Currency and financial amounts (use 2 decimal places)
    if any(k in col_lower for k in ("fee", "paid", "balance", "revenue", "amount")):
        try:
            return f"{float(value):,.2f}"
        except (ValueError, TypeError):
            return str(value)
    # Whole-number counts (sessions, courses, capacities, trainees)
    if any(k in col_lower for k in ("session", "capacity", "enrolled", "attended", "count", "slots", "taught")) or (
        isinstance(value, (int, float, Decimal)) and float(value).is_integer()
    ):
        try:
            return f"{int(round(float(value))):,d}"
        except (ValueError, TypeError):
            return str(value)
    # Any other decimal or float
    if isinstance(value, (Decimal, float)):
        val_float = float(value)
        return f"{int(val_float):,d}" if val_float.is_integer() else f"{val_float:,.2f}"
    return str(value)


def query(sql, params=()):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        return cursor.fetchall(), [
            description[0] for description in cursor.description
        ]
    finally:
        conn.close()


def discover_sources():
    """Map every dropdown label to a database object: reports first, then all
    tables, then the other views."""
    sources = dict(REPORTS)
    try:
        rows, _ = query("SHOW FULL TABLES")
    except mysql.connector.Error:
        return sources
    tables = sorted(r[0] for r in rows if str(r[1]).upper() == "BASE TABLE")
    views = sorted(r[0] for r in rows
                   if str(r[1]).upper() == "VIEW"
                   and not r[0].lower().startswith("rpt_"))
    for name in tables:
        sources[f"Table: {TABLE_LABELS.get(name.lower(), name)}"] = name
    for name in views:
        label = name[2:].replace("_", " ").capitalize() if name.lower().startswith("v_") else name
        sources[f"View: {label}"] = name
    return sources


def safe_action(func):
    """Show any error in a message box (and the terminal) instead of failing silently."""
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except Exception as error:
            traceback.print_exc()
            messagebox.showerror(
                "Something went wrong",
                f"{type(error).__name__}: {error}", parent=self.root)
    wrapper.__name__ = func.__name__
    return wrapper


class ReportsApp:
    def __init__(self, root):
        configure_theme(root)
        self.root = root
        self.root.title("Training Management Information System (TMIS) - Reports")
        self.root.geometry("1200x760")
        self.sources = discover_sources()
        self.report_names = list(self.sources)
        self.report = tk.StringVar(value=self.report_names[0])
        self.search = tk.StringVar()
        self.date_from = tk.StringVar()
        self.date_to = tk.StringVar()
        self.status_filter = tk.StringVar(value="All statuses")
        self.columns = []
        self.all_rows = []
        self.rows = []
        self.page = 0
        self.view_ready = False
        self.ask_location = tk.BooleanVar(value=False)

        head = tk.Frame(root, bg=DARK_GREEN)
        head.pack(fill="x")
        tk.Label(
            head, text="Training Management Information System (TMIS) - Reports", bg=DARK_GREEN, fg="white",
            font=("Segoe UI", 15, "bold"), pady=12
        ).pack(side="left", padx=16)

        controls = tk.Frame(root, padx=16, pady=10)
        controls.pack(fill="x")
        tk.Label(controls, text="Report:").grid(row=0, column=0, sticky="w")
        picker = ttk.Combobox(
            controls, textvariable=self.report, values=self.report_names,
            state="readonly", width=44
        )
        picker.grid(row=0, column=1, padx=(8, 18), sticky="w")
        picker.bind("<<ComboboxSelected>>", lambda event: self.refresh())
        self.placeholder = "Search name, course, phone, etc..."
        tk.Label(controls, text="Search:").grid(row=0, column=2, sticky="w")
        self.search_entry = tk.Entry(controls, width=32, fg="#888", font=("Segoe UI", 9))
        self.search_entry.insert(0, self.placeholder)
        self.search_entry.grid(row=0, column=3, padx=(8, 12), sticky="w")
        self.search_entry.bind("<FocusIn>", self.on_search_focus_in)
        self.search_entry.bind("<FocusOut>", self.on_search_focus_out)
        self.search_entry.bind("<KeyRelease>", lambda event: self.on_search_key())
        self.status_label = tk.Label(controls, text="Status:")
        self.status_label.grid(row=0, column=4, sticky="w")
        self.status_picker = ttk.Combobox(
            controls, textvariable=self.status_filter,
            values=("All statuses",), state="readonly", width=24
        )
        self.status_picker.grid(row=0, column=5, padx=(8, 6), sticky="w")
        self.status_picker.bind("<<ComboboxSelected>>", lambda event: self.refresh())

        date_controls = tk.Frame(root, padx=16, pady=10)
        date_controls.pack(fill="x")
        self.date_label = tk.Label(date_controls, text="Date from (YYYY-MM-DD):")
        self.date_label.pack(side="left")
        self.date_from_entry = ttk.Entry(date_controls, textvariable=self.date_from, width=14)
        self.date_from_entry.pack(side="left", padx=(8, 16))
        self.date_to_label = tk.Label(date_controls, text="to:")
        self.date_to_label.pack(side="left")
        self.date_to_entry = ttk.Entry(date_controls, textvariable=self.date_to, width=14)
        self.date_to_entry.pack(side="left", padx=(8, 16))
        tk.Button(date_controls, text="Apply filters",
                  command=self.refresh).pack(side="left")
        tk.Button(date_controls, text="Clear filters",
                  command=self.clear_filters).pack(side="left", padx=6)
        tk.Button(date_controls, text="Export CSV",
                  command=self.export_csv).pack(side="right")
        tk.Checkbutton(date_controls, text="Choose save location",
                       variable=self.ask_location).pack(side="right", padx=10)
        tk.Button(date_controls, text="Print / HTML",
                  command=self.export_html).pack(side="right", padx=6)
        tk.Button(date_controls, text="Export PDF",
                  command=self.export_pdf, bg=PRIMARY, fg="white",
                  font=("Segoe UI", 9, "bold")).pack(side="right", padx=6)

        self.summary = tk.StringVar(value="")
        tk.Label(root, textvariable=self.summary, fg=PRIMARY,
                 font=("Segoe UI", 10, "bold")).pack(
                     anchor="w", padx=16, pady=2)
        self.status = tk.StringVar(value="")
        tk.Label(root, textvariable=self.status, fg=MUTED).pack(
            anchor="w", padx=16, pady=4)
        self.empty_message = tk.StringVar(value="")
        tk.Label(root, textvariable=self.empty_message, fg=MUTED).pack(
            anchor="w", padx=16)

        box = tk.Frame(root)
        box.pack(fill="both", expand=True, padx=16, pady=8)
        self.tree = ttk.Treeview(box, show="headings")
        ys = ttk.Scrollbar(box, orient="vertical", command=self.tree.yview)
        xs = ttk.Scrollbar(box, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        ys.pack(side="right", fill="y")
        xs.pack(side="bottom", fill="x")
        self.tree.pack(fill="both", expand=True)

        paging = tk.Frame(root, padx=16, pady=12)
        paging.pack(fill="x")
        self.previous_button = tk.Button(
            paging, text="Previous", command=self.previous_page, state="disabled")
        self.previous_button.pack(side="left")
        self.page_status = tk.StringVar(value="")
        tk.Label(paging, textvariable=self.page_status, fg=MUTED).pack(
            side="left", padx=12)
        self.next_button = tk.Button(
            paging, text="Next", command=self.next_page, state="disabled")
        self.next_button.pack(side="left")

        self.refresh()

    def on_search_focus_in(self, event):
        if self.search_entry.get() == self.placeholder:
            self.search_entry.delete(0, "end")
            self.search_entry.config(fg="#222")

    def on_search_focus_out(self, event):
        if not self.search_entry.get().strip():
            self.search_entry.delete(0, "end")
            self.search_entry.insert(0, self.placeholder)
            self.search_entry.config(fg="#888")

    def on_search_key(self):
        self.page = 0
        try:
            filtered = self.filtered_rows()
            self.show_rows(filtered)
        except Exception:
            pass

    def clear_filters(self):
        self.search_entry.delete(0, "end")
        self.search_entry.insert(0, self.placeholder)
        self.search_entry.config(fg="#888")
        self.date_from.set("")
        self.date_to.set("")
        self.status_filter.set("All statuses")
        self.page = 0
        self.refresh()

    def check_view(self, view):
        rows, _ = query(
            "SELECT COUNT(*) FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s", (view,))
        return rows[0][0] == 1

    def refresh(self):
        view = self.sources[self.report.get()]
        self.page = 0
        self.truncated = False
        try:
            self.view_ready = self.check_view(view)
            if not self.view_ready:
                self.all_rows = []
                self.columns = []
                self.show_rows([])
                if view.lower().startswith("rpt_"):
                    advice = "Import reports.sql from the database folder first."
                else:
                    advice = "Check that the database is up to date."
                messagebox.showerror(
                    "Report is not installed",
                    f"{view} does not exist in tmis_db.\n\n{advice}",
                    parent=self.root,
                )
                return
            order = "" if view.lower().startswith("rpt_") else " ORDER BY 1"
            rows, columns = query(
                f"SELECT * FROM `{view}`{order} LIMIT {MAX_ROWS + 1}")
            self.truncated = len(rows) > MAX_ROWS
            rows = rows[:MAX_ROWS]
            keep = [i for i, name in enumerate(columns)
                    if name.lower() not in HIDDEN_COLUMNS]
            self.columns = [columns[i] for i in keep]
            self.all_rows = [tuple(row[i] for i in keep) for row in rows]
        except mysql.connector.Error as error:
            messagebox.showerror(
                "Could not load report",
                f"The report could not be loaded.\n\n{error}",
                parent=self.root,
            )
            return

        self.update_filter_options()
        self.update_date_controls()
        try:
            filtered = self.filtered_rows()
        except ValueError as error:
            messagebox.showwarning("Invalid filter", str(error), parent=self.root)
            return
        self.show_rows(filtered)

    def update_date_controls(self):
        lower_columns = [column.lower() for column in self.columns]
        date_col = next((c for c in DATE_COLUMNS if c in lower_columns), None)
        if date_col:
            friendly_name = DATE_COLUMNS[date_col]
            self.date_label.config(
                text=f"Filter by {friendly_name} (YYYY-MM-DD): from",
                fg="#222"
            )
            self.date_to_label.config(text="to:", fg="#222")
            self.date_from_entry.config(state="normal")
            self.date_to_entry.config(state="normal")
        else:
            self.date_label.config(
                text="Date filter: Not applicable for this report",
                fg="#888"
            )
            self.date_from.set("")
            self.date_to.set("")
            self.date_to_label.config(text="", fg="#888")
            self.date_from_entry.config(state="disabled")
            self.date_to_entry.config(state="disabled")

    def update_filter_options(self):
        lower_columns = {column.lower(): column for column in self.columns}
        status_col = next((c for c in FILTER_COLUMNS if c in lower_columns), None)
        if status_col:
            friendly_name = FILTER_COLUMNS[status_col]
            self.status_label.config(text=f"Status ({friendly_name}):", fg="#222")
            self.status_picker.config(state="readonly")

            # Include 'All statuses' plus every official status defined in schema.sql
            options = ["All statuses"]
            for val in SCHEMA_STATUSES.get(status_col, ()):
                if val not in options:
                    options.append(val)

            # Include any other status found in the actual database rows
            index = list(lower_columns).index(status_col)
            for row in self.all_rows:
                if row[index] is not None:
                    val = str(row[index])
                    if val and val not in options:
                        options.append(val)

            self.status_picker["values"] = options
            current = self.status_filter.get()
            self.status_filter.set(current if current in options else "All statuses")
        else:
            self.status_label.config(text="Status (N/A):", fg="#888")
            self.status_filter.set("Not applicable")
            self.status_picker["values"] = ("Not applicable",)
            self.status_picker.config(state="disabled")

    def filtered_rows(self):
        lower_columns = [column.lower() for column in self.columns]
        rows = list(self.all_rows)
        raw_term = self.search_entry.get().strip()
        term = "" if raw_term == self.placeholder else raw_term.lower()
        if term:
            rows = [
                row for row in rows
                if term in " ".join("" if value is None else str(value)
                                    for value in row).lower()
            ]

        status_column = next(
            (column for column in FILTER_COLUMNS if column in lower_columns),
            None,
        )
        selected_status = self.status_filter.get()
        if status_column and selected_status not in ("All statuses", "Not applicable"):
            index = lower_columns.index(status_column)
            rows = [row for row in rows if str(row[index]) == selected_status]

        date_column = next(
            (column for column in DATE_COLUMNS if column in lower_columns), None)
        start = self.parse_date(self.date_from.get(), "Date from")
        end = self.parse_date(self.date_to.get(), "Date to")
        if start and end and start > end:
            raise ValueError("Date from cannot be later than Date to.")
        if date_column and (start or end):
            index = lower_columns.index(date_column)
            rows = [
                row for row in rows
                if self.row_date(row[index], start, end)
            ]
        return rows

    @staticmethod
    def parse_date(value, label):
        value = value.strip()
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError as error:
            raise ValueError(f"{label} must use YYYY-MM-DD format.") from error

    @staticmethod
    def row_date(value, start, end):
        if value is None:
            return False
        try:
            current = value.date() if hasattr(value, "date") else datetime.strptime(
                str(value)[:10], "%Y-%m-%d").date()
        except ValueError:
            return False
        return (start is None or current >= start) and (end is None or current <= end)

    def show_rows(self, rows):
        self.rows = rows
        start = self.page * PAGE_SIZE
        page_rows = rows[start:start + PAGE_SIZE]
        self.tree.delete(*self.tree.get_children())
        self.tree["columns"] = self.columns
        for column in self.columns:
            header_text = format_header(column)
            self.tree.heading(column, text=header_text)
            col_lower = column.lower()
            min_width = len(header_text) * 9 + 40
            width = min(max(WIDTH_HINTS.get(col_lower, 100), min_width), 180)
            width = max(width, 75)
            anchor = "e" if any(k in col_lower for k in ("fee", "paid", "balance", "revenue", "amount", "percent")) else "w"
            self.tree.column(column, width=width, minwidth=75, anchor=anchor)
        for row in page_rows:
            self.tree.insert(
                "", "end",
                values=[format_cell(col, val) for col, val in zip(self.columns, row)],
            )
        self.summary.set(self.summary_text(rows))
        note = (f"  (only the first {MAX_ROWS:,d} rows are loaded)"
                if getattr(self, "truncated", False) else "")
        self.status.set(
            f"{self.report.get()} - {len(rows)} matching record(s){note}")
        self.empty_message.set(
            "" if rows else self.empty_text(self.report.get()))
        total_pages = max(1, (len(rows) + PAGE_SIZE - 1) // PAGE_SIZE)
        self.page_status.set(f"Page {self.page + 1} of {total_pages}")
        self.previous_button.configure(
            state="normal" if self.page > 0 else "disabled")
        self.next_button.configure(
            state="normal" if start + PAGE_SIZE < len(rows) else "disabled")

    def summary_text(self, rows):
        parts = [f"Records: {len(rows)}"]
        view = self.sources.get(self.report.get(), "")
        lower_columns = [column.lower() for column in self.columns]
        for column, mode, argument in SUMMARY_COLUMNS.get(view, []):
            if column.lower() not in lower_columns:
                continue
            index = lower_columns.index(column.lower())
            label = format_header(column)
            values = [row[index] for row in rows]
            if mode == "count":
                parts.append(f"{label} = {argument}: "
                             f"{sum(1 for v in values if str(v) == argument):,d}")
                continue
            numbers = [float(v) for v in values
                       if isinstance(v, (int, float, Decimal))]
            if not numbers:
                continue
            if mode == "avg":
                parts.append(f"Average {label}: {sum(numbers) / len(numbers):.1f}%")
            else:
                parts.append(f"Total {label}: {format_cell(column, sum(numbers))}")
        return " | ".join(parts)

    @staticmethod
    def empty_text(report):
        messages = {
            "Outstanding debtors": "No outstanding debtors match the current filters.",
            "Certificate dispatch": "No certificates have been issued yet.",
            "Attendance and certificate eligibility":
                "No attendance eligibility records match the current filters.",
        }
        return messages.get(report, "No records match the current filters.")

    def previous_page(self):
        if self.page > 0:
            self.page -= 1
            self.show_rows(self.rows)

    def next_page(self):
        if (self.page + 1) * PAGE_SIZE < len(self.rows):
            self.page += 1
            self.show_rows(self.rows)

    def pick_path(self, extension, title, filetypes):
        name = (re.sub(r"[^a-z0-9]+", "_", self.report.get().lower()).strip("_") + "_"
                + datetime.now().strftime("%Y%m%d_%H%M%S") + extension)
        if self.ask_location.get():
            return filedialog.asksaveasfilename(
                parent=self.root, title=title, defaultextension=extension,
                filetypes=filetypes, initialfile=name) or None
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        return str(EXPORT_DIR / name)

    @safe_action
    def export_csv(self):
        if not self.columns:
            messagebox.showwarning(
                "Nothing to export", "Load a report before exporting it.",
                parent=self.root,
            )
            return
        path = self.pick_path(".csv", "Export report as CSV",
                              [("CSV files", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as output:
                writer = csv.writer(output)
                writer.writerow(self.columns)
                writer.writerows(
                    [format_time(v) if isinstance(v, timedelta) else v for v in row]
                    for row in self.rows)
        except OSError as error:
            messagebox.showerror(
                "Export failed", f"Could not save the report:\n{error}",
                parent=self.root,
            )
            return
        messagebox.showinfo("Export complete", f"Report saved to:\n{path}",
                            parent=self.root)

    @safe_action
    def export_html(self):
        if not self.columns:
            messagebox.showwarning(
                "Nothing to print", "Load a report before printing it.",
                parent=self.root,
            )
            return
        path = self.pick_path(".html", "Save print-ready report",
                              [("HTML files", "*.html"), ("All files", "*.*")])
        if not path:
            return
        title = html.escape(self.report.get())
        full_title = f"Training Management Information System (TMIS) - {title}"
        header = "".join(f"<th>{html.escape(format_header(str(column)))}</th>"
                         for column in self.columns)
        body = "".join(
            "<tr>" + "".join(
                f"<td>{html.escape(format_cell(col, val))}</td>"
                for col, val in zip(self.columns, row)
            ) + "</tr>"
            for row in self.rows
        )
        document = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{full_title}</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 24px; }}
h1 {{ color: #16634e; font-size: 20px; }} table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #dde5df; padding: 6px; text-align: left; }}
th {{ background: #e7eee0; }} @media print {{ button {{ display: none; }} }}
</style></head><body><h1>{full_title}</h1>
<p>{html.escape(self.summary.get())}</p>
<button onclick="window.print()">Print / Save as PDF</button>
<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>
</body></html>"""
        try:
            Path(path).write_text(document, encoding="utf-8")
            messagebox.showinfo("Report saved",
                                f"Print-ready report saved to:\n{path}",
                                parent=self.root)
            webbrowser.open(Path(path).as_uri())
        except OSError as error:
            messagebox.showerror(
                "Print export failed", f"Could not save the report:\n{error}",
                parent=self.root,
            )

    @safe_action
    def export_pdf(self):
        if not self.columns:
            messagebox.showwarning(
                "Nothing to export", "Load a report before exporting it.",
                parent=self.root,
            )
            return

        try:
            from reportlab.lib.pagesizes import A4, landscape, portrait
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib import colors
        except ImportError:
            messagebox.showerror(
                "PDF export needs one more package",
                "The reportlab package is not installed.\n\n"
                "Run this in the terminal, then try again:\n"
                "pip install reportlab",
                parent=self.root,
            )
            return

        path = self.pick_path(".pdf", "Export report as PDF",
                              [("PDF files", "*.pdf"), ("All files", "*.*")])
        if not path:
            return

        try:
            is_landscape = len(self.columns) > 5
            pagesize = landscape(A4) if is_landscape else portrait(A4)

            doc = SimpleDocTemplate(
                path,
                pagesize=pagesize,
                leftMargin=24,
                rightMargin=24,
                topMargin=24,
                bottomMargin=24,
            )

            styles = getSampleStyleSheet()
            title_style = ParagraphStyle(
                "ReportTitle",
                parent=styles["Heading1"],
                fontName="Helvetica-Bold",
                fontSize=16,
                textColor=colors.HexColor("#16634e"),
                spaceAfter=4,
            )
            meta_style = ParagraphStyle(
                "ReportMeta",
                parent=styles["Normal"],
                fontName="Helvetica",
                fontSize=8.5,
                textColor=colors.HexColor("#71817b"),
                spaceAfter=10,
            )
            th_style = ParagraphStyle(
                "TableHeader",
                parent=styles["Normal"],
                fontName="Helvetica-Bold",
                fontSize=8,
                textColor=colors.HexColor("#123d34"),
                alignment=0,
            )
            td_style = ParagraphStyle(
                "TableCell",
                parent=styles["Normal"],
                fontName="Helvetica",
                fontSize=7.5,
                leading=9,
                textColor=colors.HexColor("#163b35"),
                alignment=0,
            )

            story = []
            full_pdf_title = f"Training Management Information System (TMIS) - {self.report.get()}"
            story.append(Paragraph(html.escape(full_pdf_title), title_style))

            summary_info = self.summary.get()
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            story.append(Paragraph(
                html.escape(f"Generated: {timestamp} | {summary_info}"), meta_style))
            story.append(Spacer(1, 6))

            table_data = []
            header_row = [Paragraph(html.escape(format_header(str(col))), th_style)
                          for col in self.columns]
            table_data.append(header_row)

            for row in self.rows:
                row_cells = []
                for col_name, val in zip(self.columns, row):
                    formatted_val = format_cell(col_name, val)
                    row_cells.append(Paragraph(html.escape(formatted_val), td_style))
                table_data.append(row_cells)

            table_style = TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e7eee0")),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                ("TOPPADDING", (0, 0), (-1, 0), 6),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dde5df")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 1), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
            ])

            for r in range(1, len(table_data)):
                if r % 2 == 0:
                    table_style.add("BACKGROUND", (0, r), (-1, r), colors.HexColor("#f4f6f2"))

            report_table = Table(table_data, repeatRows=1)
            report_table.setStyle(table_style)
            story.append(report_table)

            doc.build(story)
            messagebox.showinfo(
                "PDF Export Complete",
                f"Report successfully saved to:\n{path}",
                parent=self.root,
            )
            webbrowser.open(Path(path).as_uri())
        except Exception as error:
            messagebox.showerror(
                "PDF Export Failed",
                f"Could not generate PDF:\n{error}",
                parent=self.root,
            )


def open_reports(root):
    win = tk.Toplevel(root)
    try:
        ReportsApp(win)
    except Exception as error:
        win.destroy()
        messagebox.showerror("Could not open reports", str(error), parent=root)


if __name__ == "__main__":
    root = tk.Tk()
    ReportsApp(root)
    root.mainloop()