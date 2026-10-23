"""Transactional rules for website writes. Direct SQL/desktop writes are separate."""
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from .models import Course,Trainee,Staff,Enrollment,TrainingSession,Attendance,Payment,Certificate,Notification
OCCUPYING = ['pending','active','completed']

def require(condition,message):
    if not condition: raise ValidationError(message)

def payment_state(total,fee):
    return 'paid' if total >= fee else 'partially paid' if total > 0 else 'pending'

def attendance_summary(enrollment):
    sessions=TrainingSession.objects.filter(Course_id=enrollment.Course_id,SessionStatus='completed')
    total=sessions.count()
    attended=Attendance.objects.filter(Session__in=sessions,Trainee_id=enrollment.Trainee_id,AttendanceStatus='present').count()
    return total,attended

def completed_requirements(enrollment):
    total,attended=attendance_summary(enrollment)
    require(total > 0,'Complete at least one training session and record attendance first.')
    require(attended * 4 >= total * 3,'Completion requires at least 75% present attendance at completed sessions.')
    require(not TrainingSession.objects.filter(Course_id=enrollment.Course_id,SessionStatus__in=['scheduled','postponed']).exists(),'Complete or cancel the remaining course sessions first.')

def notify(enrollment,message):
    Notification.objects.create(User_id=enrollment.Trainee.User_id,MessageContent=message)

def sync_payment(enrollment):
    total=Payment.objects.filter(Enrollment=enrollment,PaymentStatus='confirmed').aggregate(total=Sum('AmountPaid'))['total'] or Decimal('0')
    status=payment_state(total,enrollment.Course.CourseFee)
    enrollment.PaymentStatus=status
    enrollment.save(update_fields=['PaymentStatus'])
    if status != 'paid':
        Certificate.objects.filter(Enrollment=enrollment,CertificateStatus='issued').update(CertificateStatus='revoked')
    return total

@transaction.atomic
def save_enrollment(obj):
    # Lock the shared course row so simultaneous website enrollments serialize.
    course=Course.objects.select_for_update().get(pk=obj.Course_id)
    trainee=Trainee.objects.select_for_update().get(pk=obj.Trainee_id)
    old=Enrollment.objects.select_for_update().filter(pk=obj.pk).first() if obj.pk else None
    if old:
        require(old.Course_id==obj.Course_id and old.Trainee_id==obj.Trainee_id,'Enrollment links cannot be changed.')
    if obj.EnrollmentStatus in OCCUPYING:
        require(trainee.TraineeStatus=='active' and trainee.User.AccountStatus=='active','Only active trainees can enroll or hold an active enrollment.')
        require(course.CourseStatus=='active','Only active courses accept enrollments.')
        used=Enrollment.objects.filter(Course_id=course.pk,EnrollmentStatus__in=OCCUPYING)
        if obj.pk: used=used.exclude(pk=obj.pk)
        require(used.count() < course.MaximumCapacity,'This course has reached maximum capacity.')
    obj.Course=course
    if obj.EnrollmentStatus=='completed': completed_requirements(obj)
    obj.save()
    sync_payment(obj)
    if obj.EnrollmentStatus!='completed':
        Certificate.objects.filter(Enrollment=obj,CertificateStatus='issued').update(CertificateStatus='revoked')
    if not old: notify(obj,f'Your enrollment in {course.CourseName} has been recorded.')

@transaction.atomic
def save_session(obj):
    Course.objects.select_for_update().get(pk=obj.Course_id)
    trainer=Staff.objects.select_for_update().get(pk=obj.Trainer_id)
    require(trainer.Role=='trainer' and trainer.StaffStatus=='active' and trainer.User.AccountStatus=='active','Choose an active trainer.')
    require(obj.EndTime > obj.StartTime,'End time must be later than start time.')
    if obj.pk:
        old=TrainingSession.objects.select_for_update().get(pk=obj.pk)
        require(old.Course_id==obj.Course_id,'A session cannot be moved to another course.')
    # Freeze session changes after completion/certification so attendance cannot silently change.
    require(not Enrollment.objects.filter(Course_id=obj.Course_id,EnrollmentStatus='completed').exists(),'This course has completed enrollments. Reopen those enrollments before changing sessions.')
    obj.save()

@transaction.atomic
def save_attendance(obj,trainer_id=None):
    course_id=TrainingSession.objects.values_list('Course_id',flat=True).get(pk=obj.Session_id)
    Course.objects.select_for_update().get(pk=course_id)
    session=TrainingSession.objects.select_for_update().get(pk=obj.Session_id)
    if trainer_id is not None:
        require(session.Trainer_id==trainer_id,'This session is no longer assigned to you.')
    require(session.SessionStatus not in ['cancelled','postponed'],'Attendance requires a scheduled or completed session.')
    enrollment=Enrollment.objects.select_for_update().filter(Trainee_id=obj.Trainee_id,Course_id=session.Course_id,EnrollmentStatus__in=OCCUPYING).first()
    require(enrollment is not None,'The trainee must be enrolled in this session’s course.')
    require(enrollment.EnrollmentStatus!='completed','Reopen the completed enrollment before changing attendance.')
    if obj.RecordedBy_id:
        require(Staff.objects.filter(pk=obj.RecordedBy_id,StaffStatus='active',User__AccountStatus='active').exists(),'Select an active staff member.')
    if obj.CheckInTime:
        require(timezone.localtime(obj.CheckInTime).date()==session.SessionDate,'Check-in date must match the training session date.')
    if obj._state.adding:
        require(not Attendance.objects.filter(Session_id=obj.Session_id,Trainee_id=obj.Trainee_id).exists(),'Attendance has already been recorded for this trainee and session.')
        obj.save(force_insert=True)
    else: obj.save(force_update=True)

@transaction.atomic
def save_payment(obj):
    course_id=Enrollment.objects.values_list('Course_id',flat=True).get(pk=obj.Enrollment_id)
    Course.objects.select_for_update().get(pk=course_id)
    enrollment=Enrollment.objects.select_for_update().select_related('Course','Trainee').get(pk=obj.Enrollment_id)
    require(obj.AmountPaid > 0,'Payment must be greater than zero.')
    old=Payment.objects.select_for_update().filter(pk=obj.pk).first() if obj.pk else None
    if old:
        for field in ['Enrollment_id','AmountPaid','PaymentDate','PaymentMethod','TransactionReference','InvoiceNumber']:
            require(getattr(old,field)==getattr(obj,field),'Recorded payment details are immutable. Reverse the transaction and enter a new payment.')
        allowed={'pending':['pending','confirmed','failed'],'confirmed':['confirmed','reversed'],'failed':['failed'],'reversed':['reversed']}
        require(obj.PaymentStatus in allowed[old.PaymentStatus],'Invalid payment status transition. Reversed and failed transactions cannot be reconfirmed.')
    obj.save()
    sync_payment(enrollment)
    if obj.PaymentStatus=='confirmed' and (not old or old.PaymentStatus!='confirmed'):
        notify(enrollment,f'Payment of UGX {obj.AmountPaid:,.2f} confirmed for {enrollment.Course.CourseName}.')
    if obj.PaymentStatus=='reversed' and old and old.PaymentStatus!='reversed':
        notify(enrollment,f'Payment {obj.TransactionReference} was reversed. Your payment balance has been recalculated.')

@transaction.atomic
def save_certificate(obj):
    course_id=Enrollment.objects.values_list('Course_id',flat=True).get(pk=obj.Enrollment_id)
    Course.objects.select_for_update().get(pk=course_id)
    enrollment=Enrollment.objects.select_for_update().select_related('Course','Trainee').get(pk=obj.Enrollment_id)
    sync_payment(enrollment)
    if obj.CertificateStatus=='issued':
        require(enrollment.EnrollmentStatus=='completed','A certificate requires a completed enrollment.')
        require(enrollment.PaymentStatus=='paid','A certificate requires full confirmed payment.')
        completed_requirements(enrollment)
        require(obj.IssueDate>=enrollment.EnrollmentDate,'Issue date cannot be earlier than enrollment date.')
        require(obj.IssueDate<=timezone.localdate(),'Issue date cannot be in the future.')
        require(Staff.objects.filter(pk=obj.IssuedBy_id,Role='administrator',StaffStatus='active',User__AccountStatus='active').exists(),'Choose an active administrator to authorize the certificate.')
    is_new=obj._state.adding
    obj.save()
    if is_new and obj.CertificateStatus=='issued': notify(enrollment,f'Your certificate for {enrollment.Course.CourseName} has been issued: {obj.SerialNumber}.')

@transaction.atomic
def save_course(obj):
    if obj.pk:
        old=Course.objects.select_for_update().get(pk=obj.pk)
        existing=Enrollment.objects.filter(Course_id=obj.pk)
        if existing.exists(): require(old.CourseFee==obj.CourseFee,'Course fees cannot change after enrollment. Create a new course for a different fee.')
        require(existing.filter(EnrollmentStatus__in=OCCUPYING).count()<=obj.MaximumCapacity,'Capacity cannot be lower than existing occupied places.')
    obj.save()
