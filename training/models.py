from django.db import models
from django.utils import timezone
class UserAccount(models.Model):
    UserID = models.AutoField(primary_key=True)
    Username = models.CharField(max_length=50, unique=True)
    PasswordHash = models.CharField(max_length=255,default='!')
    Role = models.CharField(max_length=20)
    AccountStatus = models.CharField(max_length=20,default='active',choices=[(x,x.title()) for x in ['active','inactive','suspended']])
    CreatedAt = models.DateTimeField(auto_now_add=True)
    LastLogin = models.DateTimeField(null=True,blank=True)
    def __str__(self): return self.Username
    class Meta:
        managed = False
        db_table = 'UserAccount'
class Trainee(models.Model):
    TraineeID = models.AutoField(primary_key=True)
    User = models.OneToOneField(UserAccount,models.PROTECT,db_column='UserID',limit_choices_to={'Role':'trainee','AccountStatus':'active'})
    FullName = models.CharField(max_length=150)
    DateOfBirth = models.DateField()
    Gender = models.CharField(max_length=20)
    NIN = models.CharField(max_length=20,unique=True)
    PhoneNo = models.CharField(max_length=20)
    Email = models.EmailField(max_length=150,unique=True)
    Organization = models.CharField(max_length=150,blank=True,null=True)
    Address = models.CharField(max_length=255,blank=True,null=True)
    RegistrationDate = models.DateField()
    TraineeStatus = models.CharField(max_length=20,choices=[(x,x.title()) for x in ['active','inactive','archived']],default='active')
    class Meta:
        managed = False
        db_table = 'Trainee'
class Course(models.Model):
    CourseID = models.AutoField(primary_key=True)
    CourseName = models.CharField(max_length=150)
    Description = models.TextField(blank=True,null=True)
    Category = models.CharField(max_length=100)
    Duration = models.CharField(max_length=50)
    ModeOfDelivery = models.CharField(max_length=20,choices=[(x,x.title()) for x in ['physical','online','hybrid']])
    CourseFee = models.DecimalField(max_digits=12,decimal_places=2)
    CourseStatus = models.CharField(max_length=20,choices=[(x,x.title()) for x in ['active','inactive','archived']],default='active')
    Prerequisites = models.TextField(blank=True,null=True)
    MaximumCapacity = models.PositiveIntegerField()
    class Meta:
        managed = False
        db_table = 'Course'

class Staff(models.Model):
    StaffID = models.AutoField(primary_key=True)
    User = models.OneToOneField(UserAccount,models.PROTECT,db_column='UserID')
    FullName = models.CharField(max_length=150)
    Role = models.CharField(max_length=20,choices=[(x,x.title()) for x in ['trainer','administrator']])
    Email = models.EmailField(max_length=150,unique=True)
    PhoneNo = models.CharField(max_length=20,null=True,blank=True)
    Department = models.CharField(max_length=100)
    StaffStatus = models.CharField(max_length=20,default='active',choices=[(x,x.title()) for x in ['active','inactive','archived']])
    DateJoined = models.DateField(default=timezone.localdate)
    def __str__(self): return self.FullName
    class Meta:
        managed = False
        db_table = 'Staff'

class Enrollment(models.Model):
    EnrollmentID = models.AutoField(primary_key=True)
    Trainee = models.ForeignKey(Trainee,models.PROTECT,db_column='TraineeID')
    Course = models.ForeignKey(Course,models.PROTECT,db_column='CourseID')
    EnrollmentDate = models.DateField()
    EnrollmentStatus = models.CharField(max_length=20,choices=[(x,x.title()) for x in ['pending','active','completed','cancelled','withdrawn']],default='pending')
    PaymentStatus = models.CharField(max_length=20,default='pending')
    def __str__(self): return f'{self.Trainee.FullName} — {self.Course.CourseName} (#{self.pk})'
    class Meta:
        managed = False
        db_table = 'Enrollment'
        unique_together = [('Trainee','Course')]

class TrainingSession(models.Model):
    SessionID = models.AutoField(primary_key=True)
    Course = models.ForeignKey(Course,models.PROTECT,db_column='CourseID')
    Trainer = models.ForeignKey(Staff,models.PROTECT,db_column='TrainerID')
    SessionDate = models.DateField()
    StartTime = models.TimeField()
    EndTime = models.TimeField()
    VenuePlatform = models.CharField(max_length=255)
    SessionStatus = models.CharField(max_length=20,choices=[(x,x.title()) for x in ['scheduled','completed','postponed','cancelled']],default='scheduled')
    def __str__(self): return f'{self.Course.CourseName} — {self.SessionDate} {self.StartTime} (#{self.pk})'
    class Meta:
        managed = False
        db_table = 'TrainingSession'

class Attendance(models.Model):
    pk = models.CompositePrimaryKey('Session_id','Trainee_id')
    Session = models.ForeignKey(TrainingSession,models.PROTECT,db_column='SessionID')
    Trainee = models.ForeignKey(Trainee,models.PROTECT,db_column='TraineeID')
    RecordedBy = models.ForeignKey(Staff,models.PROTECT,db_column='RecordedBy',blank=True,null=True)
    AttendanceStatus = models.CharField(max_length=20,choices=[(x,x.title()) for x in ['present','absent','late','excused']])
    CheckInTime = models.DateTimeField(blank=True,null=True)
    RecordedAt = models.DateTimeField(auto_now_add=True)
    class Meta:
        managed = False
        db_table = 'Attendance'

class Payment(models.Model):
    PaymentID = models.AutoField(primary_key=True)
    Enrollment = models.ForeignKey(Enrollment,models.PROTECT,db_column='EnrollmentID')
    AmountPaid = models.DecimalField(max_digits=12,decimal_places=2)
    PaymentDate = models.DateTimeField()
    PaymentMethod = models.CharField(max_length=20,choices=[(x,x.title()) for x in ['cash','bank transfer','card','mobile money']])
    TransactionReference = models.CharField(max_length=100,unique=True)
    PaymentStatus = models.CharField(max_length=20,choices=[(x,x.title()) for x in ['pending','confirmed','failed','reversed']],default='pending')
    InvoiceNumber = models.CharField(max_length=100,unique=True)
    class Meta:
        managed = False
        db_table = 'Payment'

class Certificate(models.Model):
    CertificateID = models.AutoField(primary_key=True)
    Enrollment = models.OneToOneField(Enrollment,models.PROTECT,db_column='EnrollmentID')
    IssuedBy = models.ForeignKey(Staff,models.PROTECT,db_column='IssuedBy')
    IssueDate = models.DateField()
    SerialNumber = models.CharField(max_length=100,unique=True)
    CertificateStatus = models.CharField(max_length=20,choices=[(x,x.title()) for x in ['issued','revoked','replaced']],default='issued')
    class Meta:
        managed = False
        db_table = 'Certificate'

class Notification(models.Model):
    NotificationID = models.AutoField(primary_key=True)
    User = models.ForeignKey(UserAccount,models.PROTECT,db_column='UserID')
    NotificationType = models.CharField(max_length=20,default='in-app')
    MessageContent = models.TextField()
    DateSent = models.DateTimeField(auto_now_add=True)
    DeliveryStatus = models.CharField(max_length=20,default='delivered')
    IsRead = models.BooleanField(default=False)
    class Meta:
        managed = False
        db_table = 'Notification'

# Friendly names appear in relationship selectors throughout the website.
Trainee.__str__ = lambda self: f'{self.FullName} (#{self.pk})'
Course.__str__ = lambda self: self.CourseName

class PortalIdentity(models.Model):
    """Explicitly maps a Django sign-in to a project account; names need not match."""
    Login = models.OneToOneField('auth.User',models.CASCADE,related_name='portal_identity')
    Account = models.OneToOneField(UserAccount,models.PROTECT,db_column='AccountID',related_name='website_identity')
    CreatedAt = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = 'tmis_web_identity'
