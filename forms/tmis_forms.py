"""TMIS forms: one data-entry form for every table in tmis_db.
Pick a table, then add, edit or delete records. The fields are built
automatically from the table's real columns. Add, update and delete are
routed through the stored procedures in queries.sql (see tmis_actions.py)."""
import csv
import re
import sys
import calendar
import hashlib
import secrets
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import mysql.connector
from db_config import get_connection
import tmis_actions as actions

PURPLE = "#5B3FA6"
TINT = "#EFEAFB"
RED = "#B3261E"
TEAL = "#0F7C80"

FRIENDLY = {
    "trainee": "Trainee", "course": "Course", "trainingsession": "Training session",
    "enrollment": "Enrollment", "attendance": "Attendance", "payment": "Payment",
    "certificate": "Certificate", "staff": "Staff", "useraccount": "User account",
    "notification": "Notification",
}


def friendly(table):
    return FRIENDLY.get(table.lower(), table)


def s(v):
    return v.decode() if isinstance(v, (bytes, bytearray)) else v


def query(sql, params=None):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, params or ())
        rows = [tuple(s(x) for x in r) for r in cur.fetchall()]
        return rows, [d[0] for d in cur.description]
    finally:
        conn.close()


def execute(sql, params):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 600_000)
    return f"pbkdf2_sha256$600000${salt.hex()}${digest.hex()}"


def allowed_values(table, column):
    """Return the list of values a CHECK (column IN (...)) rule allows, or None."""
    rows, _ = query(
        "SELECT cc.CHECK_CLAUSE FROM information_schema.CHECK_CONSTRAINTS cc "
        "JOIN information_schema.TABLE_CONSTRAINTS tc "
        "ON cc.CONSTRAINT_SCHEMA = tc.CONSTRAINT_SCHEMA "
        "AND cc.CONSTRAINT_NAME = tc.CONSTRAINT_NAME "
        "WHERE tc.TABLE_SCHEMA = DATABASE() AND tc.TABLE_NAME = %s "
        "AND tc.CONSTRAINT_TYPE = 'CHECK'", (table,))
    for (clause,) in rows:
        if f"`{column.lower()}` in (" in clause.lower():
            return re.findall(r"'([^']*)'", clause.replace("\\", ""))
    return None


def list_objects():
    """Return (base tables, views) in the current database."""
    rows, _ = query("SHOW FULL TABLES")
    tables = [r[0] for r in rows if str(r[1]).upper() == "BASE TABLE"]
    views = [r[0] for r in rows if str(r[1]).upper() == "VIEW"]
    return tables, views


def pretty_view(name):
    if name.lower().startswith("v_"):
        return name[2:].replace("_", " ").capitalize()
    return name


class App:
    def __init__(self, root, table=None):
        self.root = root
        root.title("TMIS - " + (friendly(table) + " form" if table else "Data entry forms"))
        root.geometry("1000x780")

        self.fields = {}
        self.required = set()
        self.nullable = {}
        self.data_types = {}
        self.foreign_keys = {}
        self.fk_labels = {}
        self.fk_choices = {}
        self.unique_groups = []
        self.check_bounds = {}
        self.cols = []
        self.pk = []
        self.rows = {}
        self.editing = None
        self.editing_row = {}
        self.page = 0
        self.page_size = 100
        self.mode = tk.StringVar(value="Adding a new record")

        head = tk.Frame(root, bg=PURPLE)
        head.pack(fill="x")
        title = (friendly(table) + " form") if table else "TMIS - Training Management Information System"
        tk.Label(head, text=title, bg=PURPLE, fg="white",
                 font=("Segoe UI", 15, "bold"), pady=12).pack(side="left", padx=16)

        if table:
            self.table = tk.StringVar(value=table)
            tk.Frame(root, height=10).pack()
        else:
            top = tk.Frame(root)
            top.pack(fill="x", padx=16, pady=10)
            tk.Label(top, text="Form for table:", font=("Segoe UI", 11)).pack(side="left")
            tables = list_objects()[0]
            self.table = tk.StringVar(value="payment" if "payment" in tables else tables[0])
            picker = ttk.Combobox(top, textvariable=self.table, values=tables,
                                  state="readonly", width=24)
            picker.pack(side="left", padx=8)
            picker.bind("<<ComboboxSelected>>", lambda e: self.load_form())

        form_box = tk.Frame(root, height=260)
        form_box.pack(fill="x", padx=16)
        form_box.pack_propagate(False)
        self.form_canvas = tk.Canvas(form_box, bg=TINT, highlightthickness=0)
        form_scroll = ttk.Scrollbar(form_box, orient="vertical",
                                   command=self.form_canvas.yview)
        self.form_canvas.configure(yscrollcommand=form_scroll.set)
        form_scroll.pack(side="right", fill="y")
        self.form_canvas.pack(side="left", fill="both", expand=True)
        self.form = tk.Frame(self.form_canvas, bg=TINT, padx=16, pady=14)
        self.form_window = self.form_canvas.create_window(
            (0, 0), window=self.form, anchor="nw")
        self.form_scroll_tag = f"TMISFormScroll{id(self)}"
        self.form_canvas.bind_class(
            self.form_scroll_tag, "<MouseWheel>", self.scroll_form_wheel)
        self.form_canvas.bind_class(
            self.form_scroll_tag, "<Button-4>", self.scroll_form_wheel)
        self.form_canvas.bind_class(
            self.form_scroll_tag, "<Button-5>", self.scroll_form_wheel)
        self.attach_form_scroll(self.form_canvas)
        self.form.bind("<Configure>", self.update_form_scroll)
        self.form_canvas.bind("<Configure>", self.resize_form)

        bar = tk.Frame(root)
        bar.pack(fill="x", padx=16, pady=10)
        tk.Label(bar, text="* required", fg=RED).pack(side="left")
        tk.Label(bar, textvariable=self.mode, fg=PURPLE,
                 font=("Segoe UI", 10, "bold")).pack(side="left", padx=18)
        tk.Button(bar, text="Add record", bg=PURPLE, fg="white", padx=16, pady=4,
                  font=("Segoe UI", 10, "bold"), command=self.add).pack(side="right")
        self.update_button = tk.Button(
            bar, text="Update", bg=TEAL, fg="white", padx=16, pady=4,
            activeforeground="white", disabledforeground="white",
            font=("Segoe UI", 10, "bold"), command=self.update)
        self.update_button.pack(side="right", padx=6)
        self.delete_button = tk.Button(
            bar, text="Delete", bg=RED, fg="white", activeforeground="white",
            disabledforeground="white", padx=16, pady=4,
            font=("Segoe UI", 10, "bold"),
            command=self.delete)
        self.delete_button.pack(side="right")
        tk.Button(bar, text="Clear", padx=16, pady=4,
                  command=self.clear).pack(side="right", padx=6)

        browse = tk.Frame(root)
        browse.pack(fill="x", padx=16, pady=(2, 0))
        tk.Label(browse, text="Find:", fg="#555").pack(side="left")
        self.search = tk.StringVar()
        search_entry = ttk.Entry(browse, textvariable=self.search, width=32)
        search_entry.pack(side="left", padx=(6, 4))
        search_entry.bind("<Return>", lambda event: self.search_records())
        tk.Button(browse, text="Search", command=self.search_records).pack(side="left")
        tk.Button(browse, text="Clear search",
                  command=self.clear_search).pack(side="left", padx=6)
        self.page_label = tk.StringVar(value="")
        tk.Label(browse, textvariable=self.page_label, fg="#555").pack(side="left", padx=12)
        self.next_button = tk.Button(browse, text="Next", command=self.next_page)
        self.next_button.pack(side="right")
        self.previous_button = tk.Button(
            browse, text="Previous", command=self.previous_page, state="disabled")
        self.previous_button.pack(side="right", padx=6)
        tk.Label(root, text="Select a row to load it into the form.",
                 fg="#555").pack(anchor="w", padx=16, pady=(4, 0))
        box = tk.Frame(root)
        box.pack(fill="both", expand=True, padx=16, pady=(4, 16))
        self.tree = ttk.Treeview(box, show="headings", selectmode="browse")
        ys = ttk.Scrollbar(box, orient="vertical", command=self.tree.yview)
        xs = ttk.Scrollbar(box, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        ys.pack(side="right", fill="y")
        xs.pack(side="bottom", fill="x")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        self.load_form()

    def load_form(self):
        for w in self.form.winfo_children():
            w.destroy()
        t = self.table.get()
        cols, _ = query(
            "SELECT COLUMN_NAME, DATA_TYPE, COLUMN_TYPE, IS_NULLABLE, "
            "COLUMN_DEFAULT, EXTRA, COLUMN_KEY FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s "
            "ORDER BY ORDINAL_POSITION", (t,))
        fk_rows, _ = query(
            "SELECT COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME "
            "FROM information_schema.KEY_COLUMN_USAGE "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s "
            "AND REFERENCED_TABLE_NAME IS NOT NULL", (t,))
        fks = {r[0]: (r[1], r[2]) for r in fk_rows}
        unique_rows, _ = query(
            "SELECT INDEX_NAME, SEQ_IN_INDEX, COLUMN_NAME "
            "FROM information_schema.STATISTICS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s "
            "AND NON_UNIQUE = 0 AND COLUMN_NAME IS NOT NULL "
            "ORDER BY INDEX_NAME, SEQ_IN_INDEX", (t,))
        unique_indexes = {}
        for index_name, seq, column in unique_rows:
            unique_indexes.setdefault(index_name, []).append((seq, column))
        unique_groups = []
        for columns in unique_indexes.values():
            group = [column for _, column in sorted(columns)]
            if group:
                unique_groups.append(group)

        check_rows, _ = query(
            "SELECT cc.CHECK_CLAUSE FROM information_schema.CHECK_CONSTRAINTS cc "
            "JOIN information_schema.TABLE_CONSTRAINTS tc "
            "ON cc.CONSTRAINT_SCHEMA = tc.CONSTRAINT_SCHEMA "
            "AND cc.CONSTRAINT_NAME = tc.CONSTRAINT_NAME "
            "WHERE tc.TABLE_SCHEMA = DATABASE() AND tc.TABLE_NAME = %s "
            "AND tc.CONSTRAINT_TYPE = 'CHECK'", (t,))
        check_bounds = {}
        for (clause,) in check_rows:
            for match in re.finditer(
                    r"`?([A-Za-z_]\w*)`?\s*(>=|<=|>|<)\s*(-?\d+(?:\.\d+)?)",
                    clause):
                check_bounds.setdefault(match.group(1).lower(), []).append(
                    (match.group(2), Decimal(match.group(3))))

        self.fields = {}
        self.required = set()
        self.nullable = {}
        self.data_types = {}
        self.foreign_keys = fks
        self.fk_labels = {}
        self.fk_choices = {name: {} for name in fks}
        self.unique_groups = unique_groups
        self.check_bounds = check_bounds
        self.cols = [c[0] for c in cols]
        self.pk = [c[0] for c in cols if c[6] == "PRI"]
        self.editing = None
        self.editing_row = {}
        self.page = 0
        self.mode.set(
            "Adding a new record" if self.pk
            else "Adding a new record (no primary key; add only)")
        self.update_button.configure(state="disabled")
        self.delete_button.configure(state="disabled")

        managed = actions.auto_fields(t)
        optional = actions.optional_fields(t)

        for i, (name, dtype, ctype, nullable, default, extra, key) in enumerate(cols):
            auto = "auto_increment" in (extra or "").lower() or name in managed
            req = (nullable == "NO" and default is None
                   and not auto and name not in optional)
            self.nullable[name] = nullable == "YES"
            self.data_types[name] = dtype.lower()
            if req:
                self.required.add(name)
            hint = ""
            if dtype == "date":
                hint = " (YYYY-MM-DD)"
            elif dtype in ("datetime", "timestamp"):
                hint = " (YYYY-MM-DD HH:MM:SS)"
            elif name.lower() == "passwordhash":
                hint = " (new password; stored as a secure hash)"
            elif name in optional:
                hint = " (leave blank to auto-generate)"
            label = name + hint + (" *" if req else "")
            r, c = divmod(i, 2)
            tk.Label(self.form, text=label, bg=TINT, anchor="w",
                     font=("Segoe UI", 10)).grid(row=r * 2, column=c, sticky="w",
                                                 padx=8, pady=(6, 0))
            var = tk.StringVar()
            if auto:
                var.set("(auto)")
                w = ttk.Entry(self.form, textvariable=var, state="readonly", width=36)
            elif name.lower() == "passwordhash":
                w = ttk.Entry(self.form, textvariable=var, show="*", width=36)
            elif dtype in ("date", "datetime", "timestamp"):
                date_field = tk.Frame(self.form, bg=TINT)
                w = ttk.Entry(date_field, textvariable=var, width=27)
                w.pack(side="left")
                tk.Button(
                    date_field, text="Calendar", padx=6,
                    command=lambda value=var, include_time=dtype != "date":
                    self.open_calendar(value, include_time)
                ).pack(side="left", padx=(5, 0))
                w = date_field
            elif dtype == "time":
                time_field = tk.Frame(self.form, bg=TINT)
                w = ttk.Entry(time_field, textvariable=var, width=27)
                w.pack(side="left")
                tk.Button(
                    time_field, text="Choose time", padx=6,
                    command=lambda value=var: self.open_time_picker(value)
                ).pack(side="left", padx=(5, 0))
                w = time_field
            elif name in fks:
                rt, rc = fks[name]
                ref_cols, _ = query(
                    "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s",
                    (rt,))
                available = {row[0].lower(): row[0] for row in ref_cols}
                display_col = next(
                    (available[candidate] for candidate in (
                        "fullname", "coursename", "username", "email", "title")
                     if candidate in available and available[candidate] != rc),
                    rc)
                self.fk_labels[name] = (rt, rc, display_col)
                fk_field = tk.Frame(self.form, bg=TINT)
                w = ttk.Entry(fk_field, textvariable=var, width=27)
                w.pack(side="left")
                tk.Button(
                    fk_field, text="Find...", padx=6,
                    command=lambda field=name, value=var:
                    self.open_fk_picker(field, value)
                ).pack(side="left", padx=(5, 0))
                w = fk_field
            elif dtype == "enum":
                vals = [v.strip("'") for v in ctype[5:-1].split(",")]
                w = ttk.Combobox(self.form, textvariable=var, values=vals,
                                 state="readonly", width=34)
            elif (opts := allowed_values(t, name)):
                w = ttk.Combobox(self.form, textvariable=var, values=opts,
                                 state="readonly", width=34)
            else:
                w = ttk.Entry(self.form, textvariable=var, width=36)
            w.grid(row=r * 2 + 1, column=c, sticky="w", padx=8, pady=(0, 4))
            self.attach_form_scroll(w)
            self.fields[name] = (var, auto)
        self.attach_form_scroll(self.form)
        self.refresh_grid()
        self.update_form_scroll()

    def _msg(self, kind, title, message, parent=None):
        return getattr(messagebox, kind)(title, message, parent=parent or self.root)

    def _modal(self, popup):
        popup.update_idletasks()
        popup.wait_visibility()
        popup.lift()
        popup.focus_force()
        popup.grab_set()

    def update_form_scroll(self, event=None):
        self.form_canvas.configure(scrollregion=self.form_canvas.bbox("all"))

    def resize_form(self, event):
        self.form_canvas.itemconfigure(self.form_window, width=event.width)

    def attach_form_scroll(self, widget):
        tags = widget.bindtags()
        if self.form_scroll_tag not in tags:
            widget.bindtags((self.form_scroll_tag,) + tags)
        for child in widget.winfo_children():
            self.attach_form_scroll(child)

    def scroll_form_wheel(self, event):
        if event.num == 4:
            units = -1
        elif event.num == 5:
            units = 1
        else:
            units = -int(event.delta / 120)
            if units == 0:
                units = -1 if event.delta > 0 else 1
        self.form_canvas.yview_scroll(units, "units")
        return "break"

    def open_calendar(self, variable, include_time=False):
        current = variable.get().strip()
        time_value = "00:00:00"
        if include_time:
            try:
                current_datetime = datetime.fromisoformat(current.replace(" ", "T"))
                selected = current_datetime.date()
                time_value = current_datetime.time().isoformat()
            except ValueError:
                selected = date.today()
        else:
            try:
                selected = date.fromisoformat(current)
            except ValueError:
                selected = date.today()
        month_state = [selected.year, selected.month]

        popup = tk.Toplevel(self.root)
        popup.title("Choose date")
        popup.transient(self.root)
        popup.resizable(False, False)
        body = tk.Frame(popup, padx=10, pady=10)
        body.pack()

        def show_month():
            for child in body.winfo_children():
                child.destroy()
            header = tk.Frame(body)
            header.grid(row=0, column=0, columnspan=7, sticky="ew")
            tk.Button(header, text="<", width=3,
                      command=lambda: change_month(-1)).pack(side="left")
            tk.Label(header, text=f"{calendar.month_name[month_state[1]]} "
                     f"{month_state[0]}", width=18,
                     font=("Segoe UI", 10, "bold")).pack(side="left")
            tk.Button(header, text=">", width=3,
                      command=lambda: change_month(1)).pack(side="right")
            for column, weekday in enumerate(("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")):
                tk.Label(body, text=weekday, width=4).grid(
                    row=1, column=column, pady=(6, 2))
            for row, week in enumerate(calendar.monthcalendar(*month_state), start=2):
                for column, day in enumerate(week):
                    if day:
                        tk.Button(
                            body, text=str(day), width=4,
                            command=lambda day=day: choose_day(day)
                        ).grid(row=row, column=column, padx=1, pady=1)

        def change_month(offset):
            if (month_state == [1, 1] and offset < 0) or (
                    month_state == [9999, 12] and offset > 0):
                return
            month_state[1] += offset
            if month_state[1] == 0:
                month_state[1] = 12
                month_state[0] -= 1
            elif month_state[1] == 13:
                month_state[1] = 1
                month_state[0] += 1
            show_month()

        def choose_day(day):
            selected_date = (
                f"{month_state[0]:04d}-{month_state[1]:02d}-{day:02d}")
            variable.set(
                f"{selected_date} {time_value}" if include_time else selected_date)
            popup.destroy()

        show_month()
        self._modal(popup)

    def open_time_picker(self, variable):
        try:
            current = datetime.strptime(variable.get().strip(), "%H:%M:%S")
        except ValueError:
            current = datetime.now().replace(microsecond=0)

        popup = tk.Toplevel(self.root)
        popup.title("Choose time")
        popup.transient(self.root)
        popup.resizable(False, False)
        body = tk.Frame(popup, padx=12, pady=12)
        body.pack()
        hour = tk.StringVar(value=f"{current.hour:02d}")
        minute = tk.StringVar(value=f"{current.minute:02d}")
        second = tk.StringVar(value=f"{current.second:02d}")
        for column, (label, spin_var, maximum) in enumerate((
                ("Hour", hour, 23), ("Minute", minute, 59), ("Second", second, 59))):
            tk.Label(body, text=label).grid(row=0, column=column, padx=4)
            tk.Spinbox(body, from_=0, to=maximum, width=4, wrap=True,
                       textvariable=spin_var, format="%02.0f").grid(
                           row=1, column=column, padx=4, pady=(2, 10))

        def choose_time():
            try:
                picked = datetime(
                    2000, 1, 1, int(hour.get()), int(minute.get()), int(second.get()))
            except ValueError:
                self._msg("showwarning", "Invalid time", "Choose a valid time.", parent=popup)
                return
            variable.set(picked.strftime("%H:%M:%S"))
            popup.destroy()

        tk.Button(body, text="Use this time", command=choose_time).grid(
            row=2, column=0, columnspan=3, pady=(4, 0))
        self._modal(popup)

    def open_fk_picker(self, name, variable):
        table, key_col, label_col = self.fk_labels[name]
        quoted_table = table.replace("`", "``")
        quoted_key = key_col.replace("`", "``")
        quoted_label = label_col.replace("`", "``")

        popup = tk.Toplevel(self.root)
        popup.title(f"Choose {name}")
        popup.transient(self.root)
        popup.geometry("520x400")
        top = tk.Frame(popup, padx=10, pady=10)
        top.pack(fill="x")
        tk.Label(top, text="Search by ID or name:").pack(side="left")
        search = tk.StringVar()
        entry = ttk.Entry(top, textvariable=search)
        entry.pack(side="left", fill="x", expand=True, padx=(8, 0))

        listing = tk.Frame(popup, padx=10)
        listing.pack(fill="both", expand=True, pady=(0, 10))
        tree = ttk.Treeview(
            listing, columns=("id", "label"), show="headings", selectmode="browse")
        tree.heading("id", text=key_col)
        tree.heading("label", text=label_col if label_col != key_col else "Value")
        tree.column("id", width=110, stretch=False)
        tree.column("label", width=340)
        scrollbar = ttk.Scrollbar(listing, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)
        matches = {}

        def refresh_choices(event=None):
            term = search.get().strip()
            sql = (f"SELECT `{quoted_key}`, `{quoted_label}` "
                   f"FROM `{quoted_table}`")
            params = []
            if term:
                sql += (f" WHERE CAST(`{quoted_key}` AS CHAR) LIKE %s "
                        f"OR CAST(`{quoted_label}` AS CHAR) LIKE %s")
                pattern = f"%{term}%"
                params.extend((pattern, pattern))
            sql += f" ORDER BY `{quoted_label}`, `{quoted_key}` LIMIT 100"
            try:
                rows, _ = query(sql, params)
            except mysql.connector.Error as error:
                self._msg("showerror", "Database error", str(error), parent=popup)
                return
            tree.delete(*tree.get_children())
            matches.clear()
            for key, label in rows:
                key_text = str(key)
                display = key_text if key_text == str(label) else f"{key_text} - {label}"
                item = tree.insert("", "end", values=(key_text, label))
                matches[item] = (key_text, display)

        def choose(event=None):
            selection = tree.selection()
            if not selection or selection[0] not in matches:
                return
            key, display = matches[selection[0]]
            self.fk_choices[name][display] = key
            variable.set(display)
            popup.destroy()

        search.trace_add("write", refresh_choices)
        entry.bind("<Return>", refresh_choices)
        tree.bind("<Double-1>", choose)
        tk.Button(popup, text="Select", command=choose).pack(pady=(0, 10))
        refresh_choices()
        entry.focus_set()
        self._modal(popup)

    def foreign_key_display(self, name, value):
        table, key_col, label_col = self.fk_labels[name]
        sql = (f"SELECT `{key_col.replace('`', '``')}`, "
               f"`{label_col.replace('`', '``')}` "
               f"FROM `{table.replace('`', '``')}` "
               f"WHERE `{key_col.replace('`', '``')}` = %s LIMIT 1")
        rows, _ = query(sql, (value,))
        if not rows:
            return str(value)
        key, label = rows[0]
        key_text = str(key)
        display = key_text if key_text == str(label) else f"{key_text} - {label}"
        self.fk_choices[name][display] = key_text
        return display

    def clear(self):
        for var, auto in self.fields.values():
            var.set("(auto)" if auto else "")
        self.editing = None
        self.editing_row = {}
        self.mode.set(
            "Adding a new record" if self.pk
            else "Adding a new record (no primary key; add only)")
        self.tree.selection_remove(self.tree.selection())
        self.update_button.configure(state="disabled")
        self.delete_button.configure(state="disabled")

    def on_select(self, event=None):
        sel = self.tree.selection()
        if not sel or sel[0] not in self.rows:
            return
        row = self.rows[sel[0]]
        self.editing_row = dict(zip(self.cols, row))
        for name, v in zip(self.cols, row):
            if name.lower() == "passwordhash":
                self.fields[name][0].set("")
            elif name in self.foreign_keys and v is not None:
                try:
                    self.fields[name][0].set(self.foreign_key_display(name, v))
                except mysql.connector.Error as error:
                    self._msg("showerror", "Database error", str(error))
                    self.fields[name][0].set(str(v))
            else:
                self.fields[name][0].set("" if v is None else str(v))
        if self.pk:
            self.editing = tuple(row[self.cols.index(k)] for k in self.pk)
            shown = ", ".join(f"{k} = {v}" for k, v in zip(self.pk, self.editing))
            self.mode.set(f"Editing record: {shown}")
            self.update_button.configure(state="normal")
            self.delete_button.configure(state="normal")
        else:
            self.editing = None
            self.mode.set("No primary key: add records only")

    def collect(self, for_update):
        cols, vals, missing, invalid = [], [], [], []
        for name, (var, auto) in self.fields.items():
            if auto:
                continue
            v = var.get().strip()
            if name.lower() == "passwordhash" and for_update and not v:
                continue
            if v == "":
                if name in self.required:
                    missing.append(name)
                elif for_update and self.nullable[name]:
                    cols.append(name)
                    vals.append(None)
                continue
            if name.lower() == "passwordhash":
                if len(v) < 12:
                    invalid.append("Password must be at least 12 characters.")
                    continue
                v = hash_password(v)
            elif name in self.foreign_keys:
                value_map = self.fk_choices.get(name, {})
                if v in value_map:
                    v = value_map[v]
                else:
                    id_match = re.match(r"(\d+)(?:\s*-.*)?$", v, re.S)
                    if not id_match:
                        invalid.append(
                            f"Type a valid ID number for {name}, or choose one with Find.")
                        continue
                    v = id_match.group(1)
            error = self.validate_value(name, v)
            if error:
                invalid.append(error)
                continue
            cols.append(name)
            vals.append(v)
        return cols, vals, missing, invalid

    def validate_value(self, name, value):
        dtype = self.data_types[name]
        try:
            if dtype == "date":
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                    raise ValueError
                date.fromisoformat(value)
            elif dtype in ("datetime", "timestamp"):
                if not re.fullmatch(
                        r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d+)?",
                        value):
                    raise ValueError
                parsed = datetime.fromisoformat(value.replace(" ", "T"))
                if parsed.tzinfo is not None:
                    raise ValueError
            elif dtype in ("tinyint", "smallint", "mediumint", "int",
                           "integer", "bigint", "year"):
                if not re.fullmatch(r"[+-]?\d+", value):
                    raise ValueError
                int(value)
            elif dtype in ("decimal", "numeric", "float", "double", "real"):
                number = Decimal(value)
                if not number.is_finite():
                    raise InvalidOperation
            elif dtype == "time":
                match = re.fullmatch(r"-?\d{1,3}:(\d{2}):(\d{2})", value)
                hours = int(value.split(":")[0].lstrip("-")) if match else 0
                if (not match or hours > 838
                        or int(match.group(1)) > 59 or int(match.group(2)) > 59):
                    raise ValueError
        except (ValueError, InvalidOperation):
            formats = {
                "date": "YYYY-MM-DD",
                "datetime": "YYYY-MM-DD HH:MM:SS",
                "timestamp": "YYYY-MM-DD HH:MM:SS",
                "time": "HH:MM:SS",
            }
            if dtype in formats:
                return f"{name} must use {formats[dtype]}."
            return f"{name} must be a valid {dtype} value."

        if (dtype == "time" and self.table.get().lower() == "trainingsession"
                and name in ("StartTime", "EndTime")):
            try:
                datetime.strptime(value, "%H:%M:%S")
            except ValueError:
                return f"{name} must be a 24-hour time from 00:00:00 to 23:59:59."

        if dtype in ("tinyint", "smallint", "mediumint", "int", "integer",
                     "bigint", "year", "decimal", "numeric", "float", "double",
                     "real"):
            number = Decimal(value)
            for operator, limit in self.check_bounds.get(name.lower(), []):
                invalid = {
                    ">": number <= limit,
                    ">=": number < limit,
                    "<": number >= limit,
                    "<=": number > limit,
                }[operator]
                if invalid:
                    return f"{name} must be {operator} {limit}."

        if name in self.foreign_keys:
            table, column = self.foreign_keys[name]
            sql = (f"SELECT 1 FROM `{table.replace('`', '``')}` "
                   f"WHERE `{column.replace('`', '``')}` = %s LIMIT 1")
            try:
                found, _ = query(sql, (value,))
            except mysql.connector.Error as error:
                return f"Could not validate {name}: {error}"
            if not found:
                return (f"{name} {value} does not exist. There is no {table} with "
                        f"{column} = {value}.\nPick an existing one with Find, or "
                        f"create it first in the {friendly(table)} form.")
        return None

    def validate_record(self, cols, vals, for_update):
        values = dict(zip(cols, vals))
        errors = []
        if self.table.get().lower() == "trainingsession":
            start, end = values.get("StartTime"), values.get("EndTime")
            if start is not None and end is not None:
                start_time = datetime.strptime(str(start), "%H:%M:%S").time()
                end_time = datetime.strptime(str(end), "%H:%M:%S").time()
                if end_time <= start_time:
                    errors.append("EndTime must be later than StartTime.")

        table = self.table.get().replace("`", "``")
        for group in self.unique_groups:
            if not all(column in values and values[column] is not None
                       for column in group):
                continue
            conditions = " AND ".join(
                f"`{column.replace('`', '``')}` = %s" for column in group)
            params = [values[column] for column in group]
            sql = f"SELECT 1 FROM `{table}` WHERE {conditions}"
            if for_update and self.editing is not None and self.pk:
                pk_conditions = " AND ".join(
                    f"`{key.replace('`', '``')}` = %s" for key in self.pk)
                sql += f" AND NOT ({pk_conditions})"
                params.extend(self.editing)
            sql += " LIMIT 1"
            try:
                duplicates, _ = query(sql, params)
            except mysql.connector.Error as error:
                errors.append(f"Could not check unique values: {error}")
                continue
            if duplicates:
                errors.append(
                    "This record already exists: " + " + ".join(group)
                    + " must be unique.\nTo change it, select the row in the table "
                    "below and press Update.")
        return errors

    def where_clause(self):
        return " AND ".join(f"`{k}` = %s" for k in self.pk)

    def add(self):
        cols, vals, missing, invalid = self.collect(False)
        invalid.extend(self.validate_record(cols, vals, False))
        if missing:
            self._msg("showwarning", "Missing fields",
                                   "Please fill in: " + ", ".join(missing))
            return
        if invalid:
            self._msg("showwarning", "Check field values", "\n".join(invalid))
            return
        if not cols:
            self._msg("showwarning", "Nothing to save", "Enter some values first.")
            return
        handler = actions.ADD.get(self.table.get().lower())
        if handler:
            values = dict(zip(cols, vals))
            self.run_action(lambda: handler(values), "Record saved.")
            return
        names = ", ".join(f"`{c}`" for c in cols)
        marks = ", ".join(["%s"] * len(vals))
        self.run(f"INSERT INTO `{self.table.get()}` ({names}) VALUES ({marks})",
                 vals, "Record saved.")

    def update(self):
        if self.editing is None:
            self._msg("showwarning", "Select a record",
                                   "Click a row in the table below first, then change it and press Update.")
            return
        cols, vals, missing, invalid = self.collect(True)
        invalid.extend(self.validate_record(cols, vals, True))
        if missing:
            self._msg("showwarning", "Missing fields",
                                   "Please fill in: " + ", ".join(missing))
            return
        if invalid:
            self._msg("showwarning", "Check field values", "\n".join(invalid))
            return
        if not cols:
            self._msg("showwarning", "Nothing to update", "There is nothing to change.")
            return
        handler = actions.UPDATE.get(self.table.get().lower())
        if handler:
            values = dict(zip(cols, vals))
            old, key = dict(self.editing_row), tuple(self.editing)
            self.run_action(lambda: handler(values, old, key), "Record updated.")
            return
        sets = ", ".join(f"`{c}` = %s" for c in cols)
        self.run(f"UPDATE `{self.table.get()}` SET {sets} WHERE {self.where_clause()}",
                 vals + list(self.editing), "Record updated.")

    def delete(self):
        if self.editing is None:
            self._msg("showwarning", "Select a record",
                                   "Click the row you want to delete first.")
            return
        table = self.table.get().lower()
        rule = actions.ARCHIVE.get(table)
        if rule:
            if not self._msg("askyesno", "Please confirm", rule[2]):
                return
            record_id = self.editing[0]
            self.run_action(lambda: actions.archive(table, record_id), rule[3])
            return
        if not self._msg("askyesno", "Delete record",
                                   "Delete the selected record? This can't be undone."):
            return
        self.run(f"DELETE FROM `{self.table.get()}` WHERE {self.where_clause()}",
                 list(self.editing), "Record deleted.")

    def run_action(self, action, done_message):
        try:
            message = action()
        except actions.ActionError as e:
            self._msg("showwarning", "Not allowed", str(e))
            return
        except mysql.connector.Error as e:
            self._msg("showerror", "Could not save",
                                 e.msg if e.errno == 1644 else str(e))
            return
        self._msg("showinfo", "Done", message or done_message)
        self.clear()
        self.refresh_grid()

    def run(self, sql, params, done_message):
        try:
            execute(sql, params)
        except mysql.connector.Error as e:
            if e.errno == 1451:
                self._msg("showerror", 
                    "Can't delete",
                    "Other records depend on this one (for example payments for an "
                    "enrollment). Delete or change those first.")
            else:
                self._msg("showerror", "Database error",
                                     e.msg if e.errno == 1644 else str(e))
            return
        self._msg("showinfo", "Done", done_message)
        self.clear()
        self.refresh_grid()

    def search_records(self):
        self.page = 0
        self.clear()
        self.refresh_grid()

    def clear_search(self):
        self.search.set("")
        self.page = 0
        self.clear()
        self.refresh_grid()

    def previous_page(self):
        if self.page > 0:
            self.page -= 1
            self.clear()
            self.refresh_grid()

    def next_page(self):
        self.page += 1
        self.clear()
        self.refresh_grid()

    def refresh_grid(self):
        term = self.search.get().strip()
        where = ""
        params = []
        searchable_cols = [
            name for name in self.cols if name.lower() != "passwordhash"]
        if term and searchable_cols:
            where = " WHERE " + " OR ".join(
                f"CAST(`{name.replace('`', '``')}` AS CHAR) LIKE %s ESCAPE '!'"
                for name in searchable_cols)
            pattern = term.replace("!", "!!").replace("%", "!%").replace("_", "!_")
            params.extend([f"%{pattern}%"] * len(searchable_cols))
        start = self.page * self.page_size
        table = self.table.get().replace("`", "``")
        ordering = self.pk or self.cols
        order_by = ", ".join(f"`{name.replace('`', '``')}`" for name in ordering)
        sql = (f"SELECT * FROM `{table}`{where} ORDER BY {order_by} "
               "LIMIT %s OFFSET %s")
        params.extend((self.page_size + 1, start))
        rows, names = query(sql, params)
        has_next = len(rows) > self.page_size
        rows = rows[:self.page_size]
        self.tree.delete(*self.tree.get_children())
        self.rows = {}
        self.tree["columns"] = names
        for n in names:
            self.tree.heading(n, text=n)
            self.tree.column(n, width=120, anchor="w")
        for r in rows:
            display_values = [
                "(stored securely)" if name.lower() == "passwordhash"
                else "" if value is None else value
                for name, value in zip(names, r)]
            iid = self.tree.insert("", "end", values=display_values)
            self.rows[iid] = r
        self.page_label.set(
            f"Page {self.page + 1} - {len(rows)} record(s) shown")
        self.previous_button.configure(
            state="normal" if self.page > 0 else "disabled")
        self.next_button.configure(state="normal" if has_next else "disabled")


class ViewWindow:
    """Read-only window for a database view: search, page, refresh, export."""

    def __init__(self, win, view):
        self.win = win
        self.view = view
        self.page = 0
        self.page_size = 100
        self.cols = []
        win.title("TMIS - " + pretty_view(view))
        win.geometry("1000x600")

        head = tk.Frame(win, bg=PURPLE)
        head.pack(fill="x")
        tk.Label(head, text=pretty_view(view), bg=PURPLE, fg="white",
                 font=("Segoe UI", 15, "bold"), pady=12).pack(side="left", padx=16)
        tk.Label(head, text="Read-only report", bg=PURPLE,
                 fg="#D9CEF5").pack(side="right", padx=16)

        bar = tk.Frame(win)
        bar.pack(fill="x", padx=16, pady=10)
        tk.Label(bar, text="Find:", fg="#555").pack(side="left")
        self.search = tk.StringVar()
        entry = ttk.Entry(bar, textvariable=self.search, width=30)
        entry.pack(side="left", padx=(6, 4))
        entry.bind("<Return>", lambda event: self.run_search())
        tk.Button(bar, text="Search", command=self.run_search).pack(side="left")
        tk.Button(bar, text="Clear search",
                  command=self.clear_search).pack(side="left", padx=6)
        tk.Button(bar, text="Refresh", command=self.load).pack(side="left")
        tk.Button(bar, text="Export CSV", bg=TEAL, fg="white",
                  activeforeground="white", command=self.export).pack(side="left", padx=6)
        self.next_button = tk.Button(bar, text="Next", command=self.next_page)
        self.next_button.pack(side="right")
        self.previous_button = tk.Button(
            bar, text="Previous", command=self.previous_page, state="disabled")
        self.previous_button.pack(side="right", padx=6)
        self.page_label = tk.StringVar(value="")
        tk.Label(bar, textvariable=self.page_label, fg="#555").pack(side="right", padx=10)

        box = tk.Frame(win)
        box.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.tree = ttk.Treeview(box, show="headings", selectmode="browse")
        ys = ttk.Scrollbar(box, orient="vertical", command=self.tree.yview)
        xs = ttk.Scrollbar(box, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        ys.pack(side="right", fill="y")
        xs.pack(side="bottom", fill="x")
        self.tree.pack(fill="both", expand=True)
        self.load()

    def where(self):
        term = self.search.get().strip()
        if not term or not self.cols:
            return "", []
        pattern = term.replace("!", "!!").replace("%", "!%").replace("_", "!_")
        clause = " WHERE " + " OR ".join(
            f"CAST(`{c.replace('`', '``')}` AS CHAR) LIKE %s ESCAPE '!'"
            for c in self.cols)
        return clause, [f"%{pattern}%"] * len(self.cols)

    def load(self):
        view = self.view.replace("`", "``")
        try:
            if not self.cols:
                self.cols = query(f"SELECT * FROM `{view}` LIMIT 1")[1]
            clause, params = self.where()
            sql = f"SELECT * FROM `{view}`{clause} ORDER BY 1 LIMIT %s OFFSET %s"
            rows, names = query(
                sql, params + [self.page_size + 1, self.page * self.page_size])
        except mysql.connector.Error as error:
            messagebox.showerror("Database error", str(error), parent=self.win)
            return
        has_next = len(rows) > self.page_size
        rows = rows[:self.page_size]
        self.tree.delete(*self.tree.get_children())
        self.tree["columns"] = names
        for n in names:
            self.tree.heading(n, text=n)
            self.tree.column(n, width=130, anchor="w")
        for r in rows:
            self.tree.insert("", "end",
                             values=["" if v is None else v for v in r])
        self.page_label.set(f"Page {self.page + 1} - {len(rows)} row(s) shown")
        self.previous_button.configure(state="normal" if self.page > 0 else "disabled")
        self.next_button.configure(state="normal" if has_next else "disabled")

    def run_search(self):
        self.page = 0
        self.load()

    def clear_search(self):
        self.search.set("")
        self.page = 0
        self.load()

    def previous_page(self):
        if self.page > 0:
            self.page -= 1
            self.load()

    def next_page(self):
        self.page += 1
        self.load()

    def export(self):
        path = filedialog.asksaveasfilename(
            parent=self.win, defaultextension=".csv",
            initialfile=f"{self.view}.csv", filetypes=[("CSV file", "*.csv")])
        if not path:
            return
        view = self.view.replace("`", "``")
        try:
            clause, params = self.where()
            rows, names = query(f"SELECT * FROM `{view}`{clause} ORDER BY 1", params)
            with open(path, "w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.writer(handle)
                writer.writerow(names)
                writer.writerows(rows)
        except (mysql.connector.Error, OSError) as error:
            messagebox.showerror("Could not export", str(error), parent=self.win)
            return
        messagebox.showinfo("Exported", f"Saved {len(rows)} row(s) to\n{path}",
                            parent=self.win)


def open_form(root, table):
    win = tk.Toplevel(root)
    try:
        App(win, table=table)
    except Exception as e:
        win.destroy()
        messagebox.showerror("Could not open form", str(e), parent=root)


def open_view(root, view):
    win = tk.Toplevel(root)
    try:
        ViewWindow(win, view)
    except Exception as e:
        win.destroy()
        messagebox.showerror("Could not open report", str(e), parent=root)


def open_menu(root):
    root.title("TMIS - Forms menu")
    root.geometry("600x780")
    head = tk.Frame(root, bg=PURPLE)
    head.pack(fill="x")
    tk.Label(head, text="TMIS - Training Management Information System",
             bg=PURPLE, fg="white", font=("Segoe UI", 14, "bold"),
             pady=12).pack(side="left", padx=16)
    tables, views = list_objects()

    tk.Label(root, text="Data entry forms", font=("Segoe UI", 12, "bold")).pack(pady=(14, 4))
    grid = tk.Frame(root)
    grid.pack(padx=24, pady=4)
    for i, t in enumerate(tables):
        tk.Button(grid, text=friendly(t), width=22, pady=8, bg=TINT, fg="#222",
                  font=("Segoe UI", 10, "bold"),
                  command=lambda t=t: open_form(root, t)).grid(
                      row=i // 2, column=i % 2, padx=8, pady=5)

    if views:
        tk.Label(root, text="Reports and views (read-only)",
                 font=("Segoe UI", 12, "bold")).pack(pady=(14, 4))
        vgrid = tk.Frame(root)
        vgrid.pack(padx=24, pady=4)
        for i, v in enumerate(views):
            tk.Button(vgrid, text=pretty_view(v), width=22, pady=8, bg="#DDF0F0",
                      fg="#222", font=("Segoe UI", 10, "bold"),
                      command=lambda v=v: open_view(root, v)).grid(
                          row=i // 2, column=i % 2, padx=8, pady=5)


if __name__ == "__main__":
    root = tk.Tk()
    try:
        if len(sys.argv) > 1:
            App(root, table=sys.argv[1])
        else:
            open_menu(root)
    except Exception as e:
        messagebox.showerror("Could not start", str(e))
        raise SystemExit(1)
    root.mainloop()