"""Routes the generic TMIS form through the stored procedures in queries.sql.
Tables without an entry here (UserAccount, Trainee, Staff, Notification updates)
keep using the form's normal INSERT/UPDATE."""
import re
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from db_config import get_connection

MIN_ATTENDANCE_PCT = 75


class ActionError(Exception):
    """A rule the user broke; shown as a warning, not a database error."""


AUTO_FIELDS = {
    "attendance": {"RecordedAt"},
    "enrollment": {"EnrollmentDate", "PaymentStatus"},
    "payment": {"PaymentDate"},
    "certificate": {"IssueDate", "SerialNumber"},
}

OPTIONAL_FIELDS = {
    "payment": {"TransactionReference", "InvoiceNumber"},
}


def auto_fields(table):
    return AUTO_FIELDS.get(table.lower(), set())


def optional_fields(table):
    return OPTIONAL_FIELDS.get(table.lower(), set())


class Tx:
    def __enter__(self):
        self.conn = get_connection()
        return self

    def call(self, proc, *args):
        cur = self.conn.cursor()
        try:
            cur.callproc(proc, args)
            rows = []
            for result in cur.stored_results():
                rows.extend(result.fetchall())
            return rows
        finally:
            cur.close()

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type:
                self.conn.rollback()
            else:
                self.conn.commit()
        finally:
            self.conn.close()
        return False


def norm(value):
    if value is None:
        return ""
    if isinstance(value, timedelta):
        total = int(value.total_seconds())
        return f"{total // 3600:02d}:{total % 3600 // 60:02d}:{total % 60:02d}"
    text = str(value).strip()
    if re.fullmatch(r"\d{1,3}:\d{2}:\d{2}", text):
        hours, rest = text.split(":", 1)
        return f"{int(hours):02d}:{rest}"
    return text


def changed(new, old, names):
    return any(norm(new.get(n)) != norm(old.get(n)) for n in names)


def same_amount(a, b):
    try:
        return Decimal(norm(a) or "0") == Decimal(norm(b) or "0")
    except InvalidOperation:
        return False


def first(rows):
    return rows[0][0] if rows else None


def enrollment_status(tx, enrollment_id, status):
    if status == "completed":
        tx.call("sp_complete_enrollment", enrollment_id, MIN_ATTENDANCE_PCT)
    else:
        tx.call("sp_set_enrollment_status", enrollment_id, status)


def add_course(v):
    with Tx() as tx:
        course_id = first(tx.call(
            "sp_add_course", v.get("CourseName"), v.get("Description"), v.get("Category"),
            v.get("Duration"), v.get("ModeOfDelivery"), v.get("CourseFee"),
            v.get("Prerequisites"), v.get("MaximumCapacity")))
        status = v.get("CourseStatus")
        if status and status != "active":
            tx.call("sp_set_course_status", course_id, status)
    return f"Course #{course_id} saved."


def add_enrollment(v):
    status = v.get("EnrollmentStatus")
    if status == "completed":
        raise ActionError("A new enrollment cannot start as completed.")
    with Tx() as tx:
        enrollment_id = first(tx.call("sp_enroll_trainee", v["TraineeID"], v["CourseID"]))
        if status and status != "pending":
            enrollment_status(tx, enrollment_id, status)
    return f"Enrollment #{enrollment_id} saved and the trainee was notified."


def add_session(v):
    with Tx() as tx:
        session_id = first(tx.call(
            "sp_schedule_session", v["CourseID"], v["TrainerID"], v["SessionDate"],
            v["StartTime"], v["EndTime"], v["VenuePlatform"]))
        status = v.get("SessionStatus")
        if status and status != "scheduled":
            tx.call("sp_set_session_status", session_id, status)
    return f"Session #{session_id} scheduled."


def save_attendance(v, old=None, pk=None):
    with Tx() as tx:
        tx.call("sp_record_attendance", v["SessionID"], v["TraineeID"],
                v["AttendanceStatus"], v.get("CheckInTime"), v.get("RecordedBy"))
    return "Attendance saved."


def update_attendance(v, old, pk):
    if changed(v, old, ("SessionID", "TraineeID")):
        raise ActionError("Session and trainee cannot be changed on an existing record. "
                          "Add a new attendance record instead.")
    return save_attendance(v)


def add_payment(v):
    with Tx() as tx:
        rows = tx.call(
            "sp_record_payment", v["EnrollmentID"], v["AmountPaid"], v["PaymentMethod"],
            v.get("TransactionReference"), v.get("PaymentStatus"), v.get("InvoiceNumber"))
    payment_id, invoice, _, pay_status = rows[0]
    return (f"Payment #{payment_id} saved.\nInvoice: {invoice}\n"
            f"Enrollment payment status is now: {pay_status}")


def add_certificate(v):
    with Tx() as tx:
        rows = tx.call("sp_issue_certificate", v["EnrollmentID"], v["IssuedBy"])
        certificate_id, serial = rows[0]
        status = v.get("CertificateStatus")
        if status and status != "issued":
            tx.call("sp_set_certificate_status", certificate_id, status)
    return f"Certificate #{certificate_id} issued.\nSerial number: {serial}"


def add_notification(v):
    with Tx() as tx:
        tx.call("sp_send_notification", v["UserID"], v["NotificationType"], v["MessageContent"])
    return "Notification queued."


def update_course(v, old, pk):
    with Tx() as tx:
        tx.call("sp_update_course", pk[0], v.get("CourseName"), v.get("Description"),
                v.get("Category"), v.get("Duration"), v.get("ModeOfDelivery"),
                v.get("CourseFee"), v.get("Prerequisites"), v.get("MaximumCapacity"))
        status = v.get("CourseStatus")
        if status and norm(status) != norm(old["CourseStatus"]):
            tx.call("sp_set_course_status", pk[0], status)
    return "Course updated."


def update_enrollment(v, old, pk):
    if changed(v, old, ("TraineeID", "CourseID")):
        raise ActionError("Trainee and course cannot be changed. "
                          "Cancel this enrollment and enroll again.")
    status = v.get("EnrollmentStatus")
    if status and norm(status) != norm(old["EnrollmentStatus"]):
        with Tx() as tx:
            enrollment_status(tx, pk[0], status)
        return "Enrollment status updated."
    return "Nothing was changed."


def update_session(v, old, pk):
    if changed(v, old, ("CourseID",)):
        raise ActionError("A session cannot be moved to another course. "
                          "Cancel it and schedule a new one.")
    schedule_fields = ("TrainerID", "SessionDate", "StartTime", "EndTime", "VenuePlatform")
    status = v.get("SessionStatus")
    with Tx() as tx:
        if changed(v, old, schedule_fields):
            tx.call("sp_update_session", pk[0], v.get("TrainerID"), v.get("SessionDate"),
                    v.get("StartTime"), v.get("EndTime"), v.get("VenuePlatform"))
        if status and norm(status) != norm(old["SessionStatus"]):
            tx.call("sp_set_session_status", pk[0], status)
    return "Session updated. Enrolled trainees were notified of any change."


def update_payment(v, old, pk):
    if (changed(v, old, ("EnrollmentID", "PaymentMethod", "TransactionReference", "InvoiceNumber"))
            or not same_amount(v.get("AmountPaid"), old["AmountPaid"])):
        raise ActionError("A recorded payment cannot be edited. Set it to reversed "
                          "and record a new payment.")
    status = v.get("PaymentStatus")
    if status and norm(status) != norm(old["PaymentStatus"]):
        with Tx() as tx:
            tx.call("sp_set_payment_status", pk[0], status)
        return "Payment status updated and the enrollment balance recalculated."
    return "Nothing was changed."


def update_certificate(v, old, pk):
    if changed(v, old, ("EnrollmentID", "IssuedBy")):
        raise ActionError("Enrollment and issuer cannot be changed on a certificate.")
    status = v.get("CertificateStatus")
    if status and norm(status) != norm(old["CertificateStatus"]):
        with Tx() as tx:
            tx.call("sp_set_certificate_status", pk[0], status)
        return "Certificate status updated."
    return "Nothing was changed."


ADD = {
    "course": add_course,
    "enrollment": add_enrollment,
    "trainingsession": add_session,
    "attendance": save_attendance,
    "payment": add_payment,
    "certificate": add_certificate,
    "notification": add_notification,
}

UPDATE = {
    "course": update_course,
    "enrollment": update_enrollment,
    "trainingsession": update_session,
    "attendance": update_attendance,
    "payment": update_payment,
    "certificate": update_certificate,
}

ARCHIVE = {
    "useraccount": ("sp_set_account_status", "inactive",
                    "Deactivate this account? It will no longer be able to sign in.",
                    "Account deactivated."),
    "trainee": ("sp_set_trainee_status", "archived",
                "Archive this trainee? Payments and certificates are kept.",
                "Trainee archived."),
    "staff": ("sp_set_staff_status", "archived",
              "Archive this staff member? Their history is kept.",
              "Staff member archived."),
    "course": ("sp_set_course_status", "archived",
               "Archive this course? Existing enrollments are kept.",
               "Course archived."),
    "enrollment": ("sp_set_enrollment_status", "cancelled",
                   "Cancel this enrollment? Payments are kept.",
                   "Enrollment cancelled."),
    "trainingsession": ("sp_set_session_status", "cancelled",
                        "Cancel this session? Enrolled trainees will be notified.",
                        "Session cancelled and trainees notified."),
    "payment": ("sp_set_payment_status", "reversed",
                "Reverse this payment? The record is kept and the balance is recalculated.",
                "Payment reversed and the enrollment balance recalculated."),
    "certificate": ("sp_set_certificate_status", "revoked",
                    "Revoke this certificate? The record is kept.",
                    "Certificate revoked."),
}


def archive(table, record_id):
    proc, status, _, done = ARCHIVE[table.lower()]
    with Tx() as tx:
        tx.call(proc, record_id, status)
    return done