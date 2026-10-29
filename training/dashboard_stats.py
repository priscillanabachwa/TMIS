from django.db import connection
from django.db.models import Count
from django.utils import timezone

from .models import (Trainee, Course, Staff, Enrollment, TrainingSession,
                     Attendance, Payment, Certificate, Notification)

BALANCES_SQL = """
    SELECT COALESCE(SUM(c.CourseFee-COALESCE(p.Paid,0)),0), COUNT(*)
    FROM Enrollment e JOIN Course c ON c.CourseID=e.CourseID
    LEFT JOIN (SELECT EnrollmentID,SUM(AmountPaid) AS Paid FROM Payment
               WHERE PaymentStatus='confirmed' GROUP BY EnrollmentID) p
        ON p.EnrollmentID=e.EnrollmentID
    WHERE e.EnrollmentStatus IN ('pending','active','completed')
      AND c.CourseFee>COALESCE(p.Paid,0)
"""

def dashboard_groups():
    """Read live totals without multiplying amounts through attendance joins."""
    def statuses(model, field):
        return {row[field]: row['total'] for row in
                model.objects.values(field).annotate(total=Count('pk'))}

    trainees = statuses(Trainee, 'TraineeStatus')
    courses = statuses(Course, 'CourseStatus')
    enrollments = statuses(Enrollment, 'EnrollmentStatus')
    sessions = statuses(TrainingSession, 'SessionStatus')
    attendance = statuses(Attendance, 'AttendanceStatus')
    payments = statuses(Payment, 'PaymentStatus')
    certificates = statuses(Certificate, 'CertificateStatus')
    notifications = statuses(Notification, 'DeliveryStatus')
    today = timezone.localdate()
    with connection.cursor() as cursor:
        cursor.execute("SELECT COALESCE(SUM(AmountPaid),0) FROM Payment WHERE PaymentStatus='confirmed'")
        revenue = cursor.fetchone()[0]
        cursor.execute(BALANCES_SQL)
        balance, debtors = cursor.fetchone()

    def card(label, value, note, url, money=False):
        status_links = {
            'Active enrollments': '/operations/enrollments/?status=active',
            'Pending enrollments': '/operations/enrollments/?status=pending',
            'Completed enrollments': '/operations/enrollments/?status=completed',
            'Confirmed revenue · UGX': '/operations/payments/?status=confirmed',
            'Pending payments': '/operations/payments/?status=pending',
            'Completed sessions': '/operations/sessions/?status=completed',
            'Postponed sessions': '/operations/sessions/?status=postponed',
            'Absent records': '/operations/attendance/?status=absent',
            'Issued certificates': '/operations/certificates/?status=issued',
            'Failed payments': '/operations/payments/?status=failed',
            'Reversed payments': '/operations/payments/?status=reversed',
        }
        url = status_links.get(label, url)
        return {'label': label, 'value': value, 'note': note, 'url': url, 'money': money}

    def group(title, cards):
        return {'title': title, 'cards': cards}

    return [
        group('People and courses', [
            card('Total trainees', sum(trainees.values()), f"{trainees.get('active', 0):,} active", '/trainees/'),
            card('Total courses', sum(courses.values()), f"{courses.get('active', 0):,} active", '/courses/'),
            card('Active trainers', Staff.objects.filter(Role='trainer', StaffStatus='active', User__AccountStatus='active').count(), 'Active profile and linked account', '/reports/?report=workload'),
            card('Total staff', Staff.objects.count(), 'All staff statuses', '/reports/?report=workload'),
        ]),
        group('Enrollment progress', [
            card('Active enrollments', enrollments.get('active', 0), 'Currently in training', '/operations/enrollments/'),
            card('Pending enrollments', enrollments.get('pending', 0), 'Awaiting confirmation', '/operations/enrollments/'),
            card('Completed enrollments', enrollments.get('completed', 0), 'All-time completions', '/operations/enrollments/'),
            card('Closed enrollments', enrollments.get('cancelled', 0) + enrollments.get('withdrawn', 0), 'Cancelled or withdrawn', '/operations/enrollments/'),
        ]),
        group('Payments and balances', [
            card('Confirmed revenue · UGX', revenue, 'Confirmed transactions only · all time', '/operations/payments/', True),
            card('Outstanding balance · UGX', balance, 'Excludes cancelled / withdrawn enrollments', '/reports/?report=debtors', True),
            card('Enrollments with balances', debtors, 'One count per unpaid enrollment', '/reports/?report=debtors'),
            card('Pending payments', payments.get('pending', 0), 'Transactions awaiting confirmation', '/operations/payments/'),
        ]),
        group('Training sessions', [
            card('Upcoming sessions', TrainingSession.objects.filter(SessionStatus='scheduled', SessionDate__gte=today).count(), 'Scheduled from today onward', '/operations/sessions/'),
            card('Sessions today', TrainingSession.objects.filter(SessionDate=today, SessionStatus__in=['scheduled', 'completed']).count(), today.strftime('%d %b %Y'), '/operations/sessions/'),
            card('Completed sessions', sessions.get('completed', 0), 'All-time completed sessions', '/operations/sessions/'),
            card('Postponed sessions', sessions.get('postponed', 0), 'Awaiting rescheduling', '/operations/sessions/'),
        ]),
        group('Attendance and certificates', [
            card('Attendance recorded', sum(attendance.values()), 'Individual trainee attendance records', '/operations/attendance/'),
            card('Absent records', attendance.get('absent', 0), 'Recorded absences · all time', '/reports/?report=register'),
            card('Issued certificates', certificates.get('issued', 0), 'Currently issued certificates', '/operations/certificates/'),
            card('Revoked / replaced certificates', certificates.get('revoked', 0) + certificates.get('replaced', 0), 'Historical certificate statuses', '/operations/certificates/'),
        ]),
        group('Items needing attention', [
            card('Failed payments', payments.get('failed', 0), 'Failed transactions · all time', '/operations/payments/'),
            card('Reversed payments', payments.get('reversed', 0), 'Excluded from confirmed revenue', '/operations/payments/'),
            card('Pending notifications', notifications.get('pending', 0), 'Awaiting delivery', '/reports/?report=notifications'),
            card('Failed notifications', notifications.get('failed', 0), 'Delivery failures · all time', '/reports/?report=notifications'),
        ]),
    ]
