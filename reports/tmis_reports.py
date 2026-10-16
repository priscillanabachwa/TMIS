"""TMIS report viewer, filtering, pagination, and CSV export."""
import csv
import html
import sys
import tkinter as tk
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import webbrowser

import mysql.connector

FORMS_DIR = Path(__file__).resolve().parent.parent / "forms"
if str(FORMS_DIR) not in sys.path:
    sys.path.insert(0, str(FORMS_DIR))

from db_config import get_connection

PURPLE = "#5B3FA6"
PAGE_SIZE = 100

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
}
FILTER_COLUMNS = (
    "paymentstatus", "enrollmentstatus", "certificatestatus",
    "certificationeligibility", "sessionstatus",
)


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


class ReportsApp:
    def __init__(self, root):
        self.root = root
        self.root.title("TMIS - Reports")
        self.root.geometry("1200x760")
        self.report_names = list(REPORTS)
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

        head = tk.Frame(root, bg=PURPLE)
        head.pack(fill="x")
        tk.Label(
            head, text="TMIS - Reports", bg=PURPLE, fg="white",
            font=("Segoe UI", 15, "bold"), pady=12
        ).pack(side="left", padx=16)

        controls = tk.Frame(root, padx=16, pady=10)
        controls.pack(fill="x")
        tk.Label(controls, text="Report:").grid(row=0, column=0, sticky="w")
        picker = ttk.Combobox(
            controls, textvariable=self.report, values=self.report_names,
            state="readonly", width=38
        )
        picker.grid(row=0, column=1, padx=(8, 18), sticky="w")
        picker.bind("<<ComboboxSelected>>", lambda event: self.refresh())
        tk.Label(controls, text="Search:").grid(row=0, column=2, sticky="w")
        search_entry = ttk.Entry(controls, textvariable=self.search, width=28)
        search_entry.grid(row=0, column=3, padx=(8, 6), sticky="w")
        search_entry.bind("<Return>", lambda event: self.refresh())
        tk.Label(controls, text="Status:").grid(row=0, column=4, sticky="w")
        self.status_picker = ttk.Combobox(
            controls, textvariable=self.status_filter,
            values=("All statuses",), state="readonly", width=24
        )
        self.status_picker.grid(row=0, column=5, padx=(8, 6), sticky="w")
        self.status_picker.bind("<<ComboboxSelected>>", lambda event: self.refresh())

        date_controls = tk.Frame(root, padx=16, pady=(0, 10))
        date_controls.pack(fill="x")
        tk.Label(date_controls, text="Date from (YYYY-MM-DD):").pack(side="left")
        ttk.Entry(date_controls, textvariable=self.date_from, width=14).pack(
            side="left", padx=(8, 16))
        tk.Label(date_controls, text="Date to (YYYY-MM-DD):").pack(side="left")
        ttk.Entry(date_controls, textvariable=self.date_to, width=14).pack(
            side="left", padx=(8, 16))
        tk.Button(date_controls, text="Apply filters",
                  command=self.refresh).pack(side="left")
        tk.Button(date_controls, text="Clear filters",
                  command=self.clear_filters).pack(side="left", padx=6)
        tk.Button(date_controls, text="Export CSV",
                  command=self.export_csv).pack(side="right")
        tk.Button(date_controls, text="Print / HTML",
                  command=self.export_html).pack(side="right", padx=6)

        self.summary = tk.StringVar(value="")
        tk.Label(root, textvariable=self.summary, fg=PURPLE,
                 font=("Segoe UI", 10, "bold")).pack(
                     anchor="w", padx=16, pady=(0, 2))
        self.status = tk.StringVar(value="")
        tk.Label(root, textvariable=self.status, fg="#555").pack(
            anchor="w", padx=16, pady=(0, 4))
        self.empty_message = tk.StringVar(value="")
        tk.Label(root, textvariable=self.empty_message, fg="#777").pack(
            anchor="w", padx=16)

        box = tk.Frame(root)
        box.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        self.tree = ttk.Treeview(box, show="headings")
        ys = ttk.Scrollbar(box, orient="vertical", command=self.tree.yview)
        xs = ttk.Scrollbar(box, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        ys.pack(side="right", fill="y")
        xs.pack(side="bottom", fill="x")
        self.tree.pack(fill="both", expand=True)

        paging = tk.Frame(root, padx=16, pady=(0, 12))
        paging.pack(fill="x")
        self.previous_button = tk.Button(
            paging, text="Previous", command=self.previous_page, state="disabled")
        self.previous_button.pack(side="left")
        self.page_status = tk.StringVar(value="")
        tk.Label(paging, textvariable=self.page_status, fg="#555").pack(
            side="left", padx=12)
        self.next_button = tk.Button(
            paging, text="Next", command=self.next_page, state="disabled")
        self.next_button.pack(side="left")

        self.refresh()

    def clear_filters(self):
        self.search.set("")
        self.date_from.set("")
        self.date_to.set("")
        self.status_filter.set("All statuses")
        self.page = 0
        self.refresh()

    def check_view(self, view):
        rows, _ = query(
            "SELECT COUNT(*) FROM information_schema.VIEWS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s", (view,))
        return rows[0][0] == 1

    def refresh(self):
        view = REPORTS[self.report.get()]
        self.page = 0
        try:
            self.view_ready = self.check_view(view)
            if not self.view_ready:
                self.all_rows = []
                self.columns = []
                self.show_rows([])
                messagebox.showerror(
                    "Report is not installed",
                    f"The view {view} does not exist in tmis_db.\n\n"
                    "Import reports.sql from the database folder first.",
                    parent=self.root,
                )
                return
            self.all_rows, self.columns = query(f"SELECT * FROM `{view}`")
        except mysql.connector.Error as error:
            messagebox.showerror(
                "Could not load report",
                f"The report could not be loaded.\n\n{error}",
                parent=self.root,
            )
            return

        self.update_filter_options()
        try:
            filtered = self.filtered_rows()
        except ValueError as error:
            messagebox.showwarning("Invalid filter", str(error), parent=self.root)
            return
        self.show_rows(filtered)

    def update_filter_options(self):
        lower_columns = {column.lower(): column for column in self.columns}
        values = {"All statuses"}
        for column in FILTER_COLUMNS:
            if column in lower_columns:
                index = list(lower_columns).index(column)
                values.update(
                    str(row[index]) for row in self.all_rows
                    if row[index] is not None
                )
                break
        current = self.status_filter.get()
        options = sorted(values)
        self.status_picker["values"] = options
        self.status_filter.set(current if current in options else "All statuses")

    def filtered_rows(self):
        lower_columns = [column.lower() for column in self.columns]
        rows = list(self.all_rows)
        term = self.search.get().strip().lower()
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
        if status_column and selected_status != "All statuses":
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
            self.tree.heading(column, text=column)
            self.tree.column(column, width=130, anchor="w")
        for row in page_rows:
            self.tree.insert(
                "", "end",
                values=["" if value is None else value for value in row],
            )
        self.summary.set(self.summary_text(rows))
        self.status.set(
            f"{self.report.get()} - {len(rows)} matching record(s)")
        self.empty_message.set(
            "" if rows else self.empty_text(self.report.get()))
        total_pages = max(1, (len(rows) + PAGE_SIZE - 1) // PAGE_SIZE)
        self.page_status.set(f"Page {self.page + 1} of {total_pages}")
        self.previous_button.configure(
            state="normal" if self.page > 0 else "disabled")
        self.next_button.configure(
            state="normal" if start + PAGE_SIZE < len(rows) else "disabled")

    def summary_text(self, rows):
        numeric_totals = []
        for index, column in enumerate(self.columns):
            if any(value is not None and isinstance(value, (int, float, Decimal))
                   for value in (row[index] for row in rows)):
                total = sum(
                    value for value in (row[index] for row in rows)
                    if isinstance(value, (int, float, Decimal))
                )
                numeric_totals.append(f"{column}: {total:,.2f}")
        return f"Records: {len(rows)}" + (
            " | " + " | ".join(numeric_totals[:3]) if numeric_totals else "")

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

    def export_csv(self):
        if not self.columns:
            messagebox.showwarning(
                "Nothing to export", "Load a report before exporting it.",
                parent=self.root,
            )
            return
        path = filedialog.asksaveasfilename(
            parent=self.root, title="Export report as CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=self.report.get().lower().replace(" ", "_") + ".csv",
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as output:
                writer = csv.writer(output)
                writer.writerow(self.columns)
                writer.writerows(self.rows)
        except OSError as error:
            messagebox.showerror(
                "Export failed", f"Could not save the report:\n{error}",
                parent=self.root,
            )
            return
        messagebox.showinfo("Export complete", f"Report saved to:\n{path}",
                            parent=self.root)

    def export_html(self):
        if not self.columns:
            messagebox.showwarning(
                "Nothing to print", "Load a report before printing it.",
                parent=self.root,
            )
            return
        path = filedialog.asksaveasfilename(
            parent=self.root, title="Save print-ready report",
            defaultextension=".html",
            filetypes=[("HTML files", "*.html"), ("All files", "*.*")],
            initialfile=self.report.get().lower().replace(" ", "_") + ".html",
        )
        if not path:
            return
        title = html.escape(self.report.get())
        header = "".join(f"<th>{html.escape(str(column))}</th>"
                         for column in self.columns)
        body = "".join(
            "<tr>" + "".join(
                f"<td>{html.escape('' if value is None else str(value))}</td>"
                for value in row
            ) + "</tr>"
            for row in self.rows
        )
        document = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{title}</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 24px; }}
h1 {{ color: #5B3FA6; }} table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #bbb; padding: 6px; text-align: left; }}
th {{ background: #EFEAFB; }} @media print {{ button {{ display: none; }} }}
</style></head><body><h1>{title}</h1>
<p>{html.escape(self.summary.get())}</p>
<button onclick="window.print()">Print / Save as PDF</button>
<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>
</body></html>"""
        try:
            Path(path).write_text(document, encoding="utf-8")
            webbrowser.open(Path(path).as_uri())
        except OSError as error:
            messagebox.showerror(
                "Print export failed", f"Could not save the report:\n{error}",
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
    open_reports(root)
    root.mainloop()
