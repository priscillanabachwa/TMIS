from datetime import date,time
from unittest import skipUnless
from decimal import Decimal
from django.test import TransactionTestCase
from django.db import connection
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.utils import timezone
from .models import UserAccount,Trainee,Staff,Course,Enrollment,TrainingSession,Attendance,Payment,Certificate,Notification
from .services import save_enrollment,save_session,save_attendance,save_payment,save_certificate,save_course
MODELS=[UserAccount,Trainee,Staff,Course,Enrollment,TrainingSession,Attendance,Payment,Certificate,Notification]
@skipUnless(connection.vendor=='sqlite','Use TMIS_TEST_SQLITE=1 for disposable workflow tests.')
class OperationsTests(TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with connection.schema_editor() as editor:
            for model in MODELS:
                if model is Attendance:
                    # Match the existing MySQL composite key, rather than the
                    # single-column PK Django 4.2 uses to represent this table.
                    editor.execute('''CREATE TABLE Attendance (
                        SessionID INTEGER NOT NULL REFERENCES TrainingSession(SessionID),
                        TraineeID INTEGER NOT NULL REFERENCES Trainee(TraineeID),
                        RecordedBy INTEGER NULL REFERENCES Staff(StaffID),
                        AttendanceStatus VARCHAR(20) NOT NULL,
                        CheckInTime DATETIME NULL, RecordedAt DATETIME NOT NULL,
                        PRIMARY KEY (SessionID, TraineeID))''')
                else:
                    editor.create_model(model)
    @classmethod
    def tearDownClass(cls):
        with connection.schema_editor() as editor:
            for model in reversed(MODELS): editor.delete_model(model)
        super().tearDownClass()
    def tearDown(self):
        from .models import PortalIdentity
        PortalIdentity.objects.all().delete()
        with connection.cursor() as cursor:
            for model in reversed(MODELS): cursor.execute('DELETE FROM "'+model._meta.db_table+'"')
        super().tearDown()
    def setUp(self):
        self.user=UserAccount.objects.create(Username='sample',Role='trainee',AccountStatus='active')
        self.trainee=Trainee.objects.create(User=self.user,FullName='Sample Trainee',DateOfBirth=date(2000,1,1),Gender='female',NIN='TEST1',PhoneNo='0700000000',Email='sample@example.com',RegistrationDate=date.today())
        self.course=Course.objects.create(CourseName='Food Safety',Category='Safety',Duration='1 day',ModeOfDelivery='physical',CourseFee=100,MaximumCapacity=1)
        self.trainer=Staff.objects.create(User=UserAccount.objects.create(Username='trainer',Role='trainer',AccountStatus='active'),FullName='Trainer',Role='trainer',StaffStatus='active',Email='trainer@example.com',Department='Training')
        self.admin=Staff.objects.create(User=UserAccount.objects.create(Username='admin',Role='administrator',AccountStatus='active'),FullName='Admin',Role='administrator',StaffStatus='active',Email='admin@example.com',Department='Administration')
        self.enrollment=Enrollment(Trainee=self.trainee,Course=self.course,EnrollmentDate=date.today(),EnrollmentStatus='active')
        save_enrollment(self.enrollment)
        self.webuser=User.objects.create_user('webadmin',password='testpassword',is_staff=True)
        self.client.force_login(self.webuser)
    def session(self,status='completed'):
        obj=TrainingSession(Course=self.course,Trainer=self.trainer,SessionDate=date.today(),StartTime=time(9),EndTime=time(12),VenuePlatform='Room A',SessionStatus=status)
        save_session(obj)
        return obj
    def attendance(self,session,status='present'):
        obj=Attendance(Session=session,Trainee=self.trainee,RecordedBy=self.trainer,AttendanceStatus=status)
        save_attendance(obj)
        return obj
    def payment(self,amount,reference='PAY1'):
        obj=Payment(Enrollment=self.enrollment,AmountPaid=amount,PaymentDate=timezone.now(),PaymentMethod='cash',TransactionReference=reference,InvoiceNumber=reference,PaymentStatus='confirmed')
        save_payment(obj)
        return obj
    def complete(self):
        self.attendance(self.session())
        self.enrollment.EnrollmentStatus='completed'
        save_enrollment(self.enrollment)
    def certificate(self):
        obj=Certificate(Enrollment=self.enrollment,IssuedBy=self.admin,IssueDate=date.today(),SerialNumber='CERT1',CertificateStatus='issued')
        save_certificate(obj)
        return obj
    def test_module_lists_and_reports(self):
        self.session()
        for kind in ['enrollments','sessions','attendance','payments','certificates']:
            self.assertEqual(self.client.get('/operations/'+kind+'/').status_code,200)
            self.assertEqual(self.client.get('/operations/'+kind+'/new/').status_code,200)
        for report in ['courses','debtors','attendance','workload','register','certificates']:
            self.assertEqual(self.client.get('/reports/',{'report':report}).status_code,200)
        self.assertEqual(self.client.get('/reports/?export=csv').status_code,200)
        self.assertEqual(self.client.get('/reports/?print=1').status_code,200)
    def test_attendance_list_edit_links_include_both_ids(self):
        row=self.attendance(self.session())
        url=f'/operations/attendance/{row.Session_id}-{row.Trainee_id}/edit/'
        self.assertContains(self.client.get('/operations/attendance/'),url)
        self.assertEqual(self.client.get(url).status_code,200)
        self.assertEqual(self.client.get('/operations/attendance/not-a-number/edit/').status_code,404)

    def test_attendance_saves_multiple_trainees_in_one_session(self):
        self.course.MaximumCapacity=2;self.course.save()
        other=self.second_trainee()
        save_enrollment(Enrollment(Trainee=other,Course=self.course,
                                  EnrollmentDate=date.today(),EnrollmentStatus='active'))
        session=self.session()
        for trainee in [self.trainee,other]:
            response=self.client.post('/operations/attendance/new/',{
                'Session':session.pk,'Trainee':trainee.pk,'RecordedBy':self.trainer.pk,
                'AttendanceStatus':'present','CheckInTime':''})
            self.assertEqual(response.status_code,302)
        self.assertEqual(Attendance.objects.filter(Session=session).count(),2)
        self.assertIsNotNone(Attendance.objects.filter(Session=session).first().RecordedAt)
        response=self.client.post('/operations/attendance/new/',{
            'Session':session.pk,'Trainee':other.pk,'RecordedBy':self.trainer.pk,
            'AttendanceStatus':'present','CheckInTime':''})
        self.assertEqual(response.status_code,200)
        self.assertEqual(Attendance.objects.filter(Session=session).count(),2)

    def test_course_create_edit_search_and_validation_buttons(self):
        data={'CourseName':'Practical Hygiene','Description':'Practical skills',
              'Category':'Safety','Duration':'2 days','ModeOfDelivery':'hybrid',
              'CourseFee':'150000','MaximumCapacity':'20','CourseStatus':'active',
              'Prerequisites':''}
        self.assertEqual(self.client.post('/courses/new/',data).status_code,302)
        course=Course.objects.get(CourseName='Practical Hygiene')
        data['CourseName']='Updated Hygiene'
        self.assertEqual(self.client.post(f'/courses/{course.pk}/edit/',data).status_code,302)
        self.assertContains(self.client.get('/courses/?q=Updated'),'Updated Hygiene')
        self.assertNotContains(self.client.get('/courses/?q=NoSuchCourse'),'Updated Hygiene')
        data['CourseFee']='-1'
        self.assertContains(self.client.post(f'/courses/{course.pk}/edit/',data),'Fee must be zero or greater.')
        course.refresh_from_db();self.assertEqual(course.CourseFee,150000)

    def test_session_create_edit_and_enrollment_status_buttons(self):
        data={'Course':self.course.pk,'Trainer':self.trainer.pk,'SessionDate':date.today().isoformat(),
              'StartTime':'09:00','EndTime':'12:00','VenuePlatform':'Room B','SessionStatus':'scheduled'}
        self.assertEqual(self.client.post('/operations/sessions/new/',data).status_code,302)
        session=TrainingSession.objects.get()
        data['SessionStatus']='postponed'
        self.assertEqual(self.client.post(f'/operations/sessions/{session.pk}/edit/',data).status_code,302)
        session.refresh_from_db();self.assertEqual(session.SessionStatus,'postponed')
        self.assertEqual(self.client.post(f'/operations/enrollments/{self.enrollment.pk}/edit/',{
            'Trainee':self.trainee.pk,'Course':self.course.pk,'EnrollmentDate':date.today().isoformat(),
            'EnrollmentStatus':'withdrawn'}).status_code,302)
        self.enrollment.refresh_from_db();self.assertEqual(self.enrollment.EnrollmentStatus,'withdrawn')

    def test_logout_requires_post_and_clears_signin(self):
        response=self.client.post('/logout/')
        self.assertEqual(response.status_code,302)
        self.assertEqual(self.client.get('/courses/').status_code,302)

    def test_empty_form_submissions_keep_validation_on_screen(self):
        self.as_admin()
        for path in ['/courses/new/','/trainees/new/','/staff/new/','/website-users/new/',
                     '/portal-access/new/'] + [f'/operations/{k}/new/' for k in
                     ['enrollments','sessions','attendance','payments','certificates']]:
            with self.subTest(path=path):
                response=self.client.post(path,{'invalid':'value'})
                self.assertContains(response,'This field is required.')

    def test_record_status_filters_and_search(self):
        self.as_admin()
        for path,model,field in [('/trainees/',Trainee,'TraineeStatus'),
                                 ('/courses/',Course,'CourseStatus'),
                                 ('/staff/',Staff,'StaffStatus'),
                                 ('/accounts/',UserAccount,'AccountStatus')]:
            with self.subTest(path=path):
                response=self.client.get(path,{'status':'inactive'})
                self.assertEqual(response.context['page'].paginator.count,0)
                self.assertEqual(response.context['status'],'inactive')
                response=self.client.get(path,{'status':'active'})
                self.assertGreater(response.context['page'].paginator.count,0)
                self.assertEqual(response.context['status'],'active')
                response=self.client.get(path,{'status':'not-a-status'})
                self.assertEqual(response.context['status'],'')

    def test_operation_status_filters_and_enrollment_payment_filter(self):
        self.session()
        for kind,status in [('enrollments','active'),('sessions','completed'),
                            ('attendance','absent'),('payments','pending'),('certificates','revoked')]:
            response=self.client.get('/operations/'+kind+'/',{'status':status})
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.context['status'],status)
            self.assertContains(response,'Apply filters')
        response=self.client.get('/operations/enrollments/',{'q':'Safety','status':'active','payment_status':'pending'})
        self.assertEqual(response.context['page'].paginator.count,1)
        response=self.client.get('/operations/enrollments/',{'status':'active','payment_status':'paid'})
        self.assertEqual(response.context['page'].paginator.count,0)

    def test_pagination_preserves_search_and_status_filters(self):
        Course.objects.bulk_create([Course(CourseName=f'Filter course {i}',Category='Safety',
            Duration='1 day',ModeOfDelivery='online',CourseFee=100,MaximumCapacity=10,
            CourseStatus='inactive') for i in range(15)])
        response=self.client.get('/courses/',{'q':'Filter','status':'inactive'})
        self.assertContains(response,'q=Filter&amp;status=inactive&amp;page=2')
        response=self.client.get('/courses/',{'q':'Filter','status':'inactive','page':2})
        self.assertEqual(len(response.context['page']),3)
        self.assertContains(response,'q=Filter&amp;status=inactive&amp;page=1')

    def test_website_user_search_and_status_filters(self):
        self.as_admin()
        disabled=User.objects.create_user('filtered_operator',email='filtered@example.com',is_staff=True,is_active=False)
        response=self.client.get('/website-users/',{'q':'filtered','status':'disabled'})
        self.assertContains(response,disabled.username)
        self.assertNotContains(response,'>'+self.webuser.username+'</td>')
        response=self.client.get('/website-users/',{'q':'filtered','status':'active'})
        self.assertNotContains(response,disabled.username+'</td>')

    def test_dashboard_prioritizes_eight_cards_and_retains_all_groups(self):
        response=self.client.get('/')
        self.assertEqual(len(response.context['key_stats']),8)
        self.assertEqual(len(response.context['stat_groups']),6)
        self.assertContains(response,'<details class="metric-group">',count=6)
        self.assertContains(response,'Recent enrollments')
    def test_capacity_rejects_another_trainee(self):
        u=UserAccount.objects.create(Username='two',Role='trainee',AccountStatus='active')
        t=Trainee.objects.create(User=u,FullName='Two',DateOfBirth=date(2000,1,1),Gender='male',NIN='TEST2',PhoneNo='0700000001',Email='two@example.com',RegistrationDate=date.today())
        with self.assertRaises(ValidationError): save_enrollment(Enrollment(Trainee=t,Course=self.course,EnrollmentDate=date.today(),EnrollmentStatus='active'))
        self.assertEqual(Enrollment.objects.count(),1)
    def test_inactive_course_rejects_enrollment_update(self):
        self.course.CourseStatus='inactive';self.course.save()
        with self.assertRaises(ValidationError): save_enrollment(self.enrollment)
    def test_payment_balance_and_certificate_reversal(self):
        self.complete()
        p=self.payment(40)
        self.enrollment.refresh_from_db();self.assertEqual(self.enrollment.PaymentStatus,'partially paid')
        second=self.payment(60,'PAY2')
        self.enrollment.refresh_from_db();self.assertEqual(self.enrollment.PaymentStatus,'paid')
        cert=self.certificate()
        second.PaymentStatus='reversed';save_payment(second)
        self.enrollment.refresh_from_db();cert.refresh_from_db()
        self.assertEqual(self.enrollment.PaymentStatus,'partially paid')
        self.assertEqual(cert.CertificateStatus,'revoked')
        self.assertEqual(Notification.objects.count(),5)
    def test_unpaid_certificate_rejected(self):
        self.complete()
        with self.assertRaises(ValidationError): self.certificate()
        self.assertEqual(Certificate.objects.count(),0)
    def test_completion_rejects_insufficient_attendance(self):
        self.attendance(self.session(),'absent')
        self.enrollment.EnrollmentStatus='completed'
        with self.assertRaises(ValidationError): save_enrollment(self.enrollment)
        self.enrollment.refresh_from_db();self.assertEqual(self.enrollment.EnrollmentStatus,'active')
    def test_completion_rejects_remaining_sessions(self):
        self.attendance(self.session())
        self.session('scheduled')
        self.enrollment.EnrollmentStatus='completed'
        with self.assertRaises(ValidationError): save_enrollment(self.enrollment)
    def test_attendance_duplicate_and_composite_edit(self):
        row=self.attendance(self.session())
        with self.assertRaises(ValidationError): self.attendance(row.Session)
        row.AttendanceStatus='late';save_attendance(row)
        row.refresh_from_db();self.assertEqual(row.AttendanceStatus,'late')
        self.assertEqual(self.client.get(f'/operations/attendance/{row.Session_id}-{row.Trainee_id}/edit/').status_code,200)
    def test_cancelled_session_rejects_attendance(self):
        with self.assertRaises(ValidationError): self.attendance(self.session('cancelled'))
    def test_completed_enrollment_blocks_attendance_edits(self):
        self.complete()
        row=Attendance.objects.get()
        row.AttendanceStatus='absent'
        with self.assertRaises(ValidationError): save_attendance(row)
    def test_session_requires_active_trainer(self):
        self.trainer.StaffStatus='inactive';self.trainer.save()
        with self.assertRaises(ValidationError): self.session()
    def test_payment_fields_and_transition_protected(self):
        p=self.payment(40)
        p.AmountPaid=50
        with self.assertRaises(ValidationError): save_payment(p)
        p.refresh_from_db();self.assertEqual(p.AmountPaid,40)
        p.PaymentStatus='reversed';save_payment(p)
        p.PaymentStatus='confirmed'
        with self.assertRaises(ValidationError): save_payment(p)
    def test_course_fee_cannot_change_after_enrollment(self):
        self.course.CourseFee=200
        with self.assertRaises(ValidationError): save_course(self.course)
    def test_cancelled_session_excluded_from_eligibility(self):
        self.session('cancelled')
        self.complete();self.payment(100)
        response=self.client.get('/reports/?report=attendance')
        self.assertContains(response,'Eligible')
    def test_csv_formula_escaping(self):
        self.course.CourseName='=1+1';self.course.save()
        response=self.client.get('/reports/?export=csv')
        self.assertIn(b"'=1+1",response.content)
    def test_attendance_form_post_and_edit(self):
        s=self.session()
        data={'Session':s.pk,'Trainee':self.trainee.pk,'RecordedBy':self.trainer.pk,'AttendanceStatus':'present','CheckInTime':''}
        response=self.client.post('/operations/attendance/new/',data)
        self.assertEqual(response.status_code,302)
        row=Attendance.objects.get()
        data['AttendanceStatus']='late'
        response=self.client.post(f'/operations/attendance/{s.pk}-{self.trainee.pk}/edit/',data)
        self.assertEqual(response.status_code,302)
        row.refresh_from_db();self.assertEqual(row.AttendanceStatus,'late')
    def test_payment_form_post(self):
        data={'Enrollment':self.enrollment.pk,'AmountPaid':'100.00','PaymentDate':timezone.localtime().strftime('%Y-%m-%dT%H:%M'),'PaymentMethod':'cash','TransactionReference':'WEB1','PaymentStatus':'confirmed','InvoiceNumber':'WEBINV1'}
        response=self.client.post('/operations/payments/new/',data)
        self.assertEqual(response.status_code,302)
        self.enrollment.refresh_from_db();self.assertEqual(self.enrollment.PaymentStatus,'paid')
    def test_certificate_form_post(self):
        self.complete();self.payment(100)
        data={'Enrollment':self.enrollment.pk,'IssuedBy':self.admin.pk,'IssueDate':date.today().isoformat(),'SerialNumber':'WEB-CERT','CertificateStatus':'issued'}
        response=self.client.post('/operations/certificates/new/',data)
        self.assertEqual(response.status_code,302)
        self.assertTrue(Certificate.objects.filter(SerialNumber='WEB-CERT').exists())
    def trainee_data(self,**overrides):
        data={'Username':'new_trainee','FullName':'New Trainee','DateOfBirth':'2001-01-01','Gender':'female','NIN':'NEWNIN','PhoneNo':'0700000010','Email':'new@example.com','Organization':'','Address':'','RegistrationDate':date.today().isoformat(),'TraineeStatus':'active'}
        data.update(overrides);return data
    def as_admin(self):
        self.webuser.is_superuser=True;self.webuser.save()
    def test_create_trainee_creates_linked_account(self):
        from django.contrib.auth.hashers import is_password_usable
        response=self.client.post('/trainees/new/',self.trainee_data())
        self.assertEqual(response.status_code,302)
        trainee=Trainee.objects.get(Email='new@example.com')
        self.assertEqual(trainee.User.Username,'new_trainee')
        self.assertEqual(trainee.User.Role,'trainee')
        self.assertFalse(is_password_usable(trainee.User.PasswordHash))
    def test_trainee_failure_no_orphan_account(self):
        from .accounts import save_trainee
        from django.db import IntegrityError
        trainee=Trainee(FullName='Duplicate',DateOfBirth=date(2000,1,1),Gender='female',NIN=self.trainee.NIN,PhoneNo='0700000011',Email='duplicate@example.com',RegistrationDate=date.today())
        with self.assertRaises(IntegrityError): save_trainee(trainee,'rollback_account')
        self.assertFalse(UserAccount.objects.filter(Username='rollback_account').exists())
    def test_trainee_username_locked_on_edit(self):
        response=self.client.post(f'/trainees/{self.trainee.pk}/edit/',self.trainee_data(Username='tampered',Email=self.trainee.Email,NIN=self.trainee.NIN,FullName='Changed'))
        self.assertEqual(response.status_code,302)
        self.trainee.refresh_from_db();self.assertEqual(self.trainee.User.Username,'sample')
        self.assertEqual(self.trainee.FullName,'Changed')
    def test_duplicate_project_username_rejected(self):
        response=self.client.post('/trainees/new/',self.trainee_data(Username='sample'))
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'already exists')
        self.assertFalse(Trainee.objects.filter(Email='new@example.com').exists())
    def test_operator_cannot_manage_accounts(self):
        for path in ['/staff/','/staff/new/','/accounts/','/website-users/','/website-users/new/',f'/website-users/{self.webuser.pk}/edit/',f'/website-users/{self.webuser.pk}/password/']:
            self.assertEqual(self.client.get(path).status_code,403)
            self.assertEqual(self.client.post(path,{}).status_code,403)
    def test_staff_creation_and_lists(self):
        self.as_admin()
        data={'Username':'newtrainer','FullName':'New Trainer','Role':'trainer','Email':'newtrainer@example.com','PhoneNo':'','Department':'Training','StaffStatus':'active','DateJoined':date.today().isoformat()}
        response=self.client.post('/staff/new/',data)
        self.assertEqual(response.status_code,302)
        staff=Staff.objects.get(Email='newtrainer@example.com')
        self.assertEqual(staff.User.Role,'trainer')
        self.assertEqual(staff.User.Username,'newtrainer')
        for path in ['/staff/','/accounts/','/website-users/',f'/staff/{staff.pk}/edit/',f'/accounts/{staff.User_id}/status/']:
            self.assertEqual(self.client.get(path).status_code,200)
    def test_staff_role_change_updates_project_account(self):
        from .accounts import save_staff
        self.trainer.Role='administrator';save_staff(self.trainer,'ignored')
        self.trainer.User.refresh_from_db();self.assertEqual(self.trainer.User.Role,'administrator')
    def test_suspended_account_rejects_new_work(self):
        self.as_admin()
        response=self.client.post(f'/accounts/{self.user.pk}/status/',{'AccountStatus':'suspended'})
        self.assertEqual(response.status_code,302)
        with self.assertRaises(ValidationError): save_enrollment(self.enrollment)
    def test_create_website_operator_and_signin(self):
        self.as_admin()
        data={'username':'operator2','email':'operator2@example.com','first_name':'Test','last_name':'Operator','password1':'LemonRiver!7845','password2':'LemonRiver!7845','is_superuser':'on'}
        response=self.client.post('/website-users/new/',data)
        self.assertEqual(response.status_code,302)
        operator=User.objects.get(username='operator2')
        self.assertTrue(operator.is_staff)
        self.assertFalse(operator.is_superuser)
        self.assertTrue(operator.check_password('LemonRiver!7845'))
        self.client.logout()
        self.assertTrue(self.client.login(username='operator2',password='LemonRiver!7845'))
        self.assertEqual(self.client.get('/operations/enrollments/').status_code,200)
        self.assertEqual(self.client.get('/website-users/').status_code,403)
    def test_superuser_cannot_disable_self(self):
        self.as_admin()
        response=self.client.post(f'/website-users/{self.webuser.pk}/edit/',{'email':'web@example.com','first_name':'','last_name':''})
        self.assertEqual(response.status_code,200)
        self.webuser.refresh_from_db();self.assertTrue(self.webuser.is_active)
    def test_disable_operator_blocks_next_request(self):
        self.as_admin()
        operator=User.objects.create_user('disabled',password='LemonRiver!7845',is_staff=True)
        response=self.client.post(f'/website-users/{operator.pk}/edit/',{'email':'disabled@example.com','first_name':'','last_name':''})
        self.assertEqual(response.status_code,302)
        self.client.logout();self.assertFalse(self.client.login(username='disabled',password='LemonRiver!7845'))
    def test_password_reset(self):
        self.as_admin()
        operator=User.objects.create_user('resetme',password='OldPass!9845',is_staff=True)
        response=self.client.post(f'/website-users/{operator.pk}/password/',{'new_password1':'FreshRiver!7845','new_password2':'FreshRiver!7845'})
        self.assertEqual(response.status_code,302)
        operator.refresh_from_db();self.assertTrue(operator.check_password('FreshRiver!7845'))
    def test_sidebar_hides_admin_links_from_operator(self):
        self.assertNotContains(self.client.get('/courses/'),'href="/website-users/"')
        self.as_admin()
        self.assertContains(self.client.get('/courses/'),'href="/website-users/"')
    def link_portal(self,account,username='portaluser'):
        from .models import PortalIdentity
        login=User.objects.create_user(username,password='LemonRiver!7845',is_staff=False)
        PortalIdentity.objects.create(Login=login,Account=account)
        return login
    def second_trainee(self):
        account=UserAccount.objects.create(Username='othertrainee',Role='trainee',AccountStatus='active')
        trainee=Trainee.objects.create(User=account,FullName='Private Other Trainee',DateOfBirth=date(2001,1,1),Gender='female',NIN='PRIVATE',PhoneNo='0700000012',Email='private@example.com',RegistrationDate=date.today())
        return trainee
    def test_portal_login_provisioning(self):
        self.as_admin()
        data={'ProjectAccount':self.user.pk,'username':'learner','email':'learner@example.com','first_name':'Learner','last_name':'','password1':'LemonRiver!7845','password2':'LemonRiver!7845','is_staff':'on','is_superuser':'on'}
        response=self.client.post('/portal-access/new/',data)
        self.assertEqual(response.status_code,302)
        from .models import PortalIdentity
        identity=PortalIdentity.objects.get(Account=self.user)
        self.assertFalse(identity.Login.is_staff)
        self.assertFalse(identity.Login.is_superuser)
        self.client.logout()
        self.assertTrue(self.client.login(username='learner',password='LemonRiver!7845'))
        self.assertRedirects(self.client.get('/'),'/portal/')
        self.assertContains(self.client.get('/portal/'),'Sample Trainee')
    def test_portal_pages_reject_operator(self):
        for path in ['/portal/','/portal/enroll/','/portal/notifications/','/portal-access/new/']:
            self.assertEqual(self.client.get(path).status_code,403)
    def test_trainee_blocked_from_all_staff_routes(self):
        self.client.force_login(self.link_portal(self.user))
        for path in ['/trainees/','/courses/','/reports/?export=csv','/operations/payments/','/staff/','/accounts/','/website-users/','/portal-access/new/']:
            self.assertEqual(self.client.get(path).status_code,403)
            self.assertEqual(self.client.post(path,{}).status_code,403)
        self.assertNotContains(self.client.get('/portal/'),'href="/operations/payments/"')
    def test_trainee_sees_only_own_records(self):
        other=self.second_trainee()
        enrollment=Enrollment.objects.create(Trainee=other,Course=self.course,EnrollmentDate=date.today(),EnrollmentStatus='active')
        Payment.objects.create(Enrollment=enrollment,AmountPaid=10,PaymentDate=timezone.now(),PaymentMethod='cash',TransactionReference='PRIVATEPAYMENT',InvoiceNumber='PRIVATEINV',PaymentStatus='confirmed')
        self.payment(40,'OWNPAYMENT')
        self.client.force_login(self.link_portal(self.user))
        response=self.client.get('/portal/')
        self.assertContains(response,'OWNPAYMENT')
        self.assertNotContains(response,'PRIVATEPAYMENT')
        self.assertNotContains(response,'Private Other Trainee')
    def test_notification_read_is_scoped_and_post_only(self):
        other=self.second_trainee()
        own=Notification.objects.create(User=self.user,MessageContent='OWN NOTICE')
        private=Notification.objects.create(User=other.User,MessageContent='PRIVATE NOTICE')
        self.client.force_login(self.link_portal(self.user))
        page=self.client.get('/portal/notifications/')
        self.assertContains(page,'OWN NOTICE');self.assertNotContains(page,'PRIVATE NOTICE')
        self.assertEqual(self.client.get(f'/portal/notifications/{own.pk}/read/').status_code,405)
        self.assertEqual(self.client.post(f'/portal/notifications/{private.pk}/read/').status_code,404)
        self.assertEqual(self.client.post(f'/portal/notifications/{own.pk}/read/').status_code,302)
        own.refresh_from_db();private.refresh_from_db()
        self.assertTrue(own.IsRead);self.assertFalse(private.IsRead)
    def test_suspended_portal_account_loses_access(self):
        self.client.force_login(self.link_portal(self.user))
        self.user.AccountStatus='suspended';self.user.save()
        self.assertEqual(self.client.get('/portal/').status_code,403)
        self.assertEqual(self.client.get('/portal/').status_code,302)
    def test_portal_self_enrollment_uses_own_identity(self):
        course=Course.objects.create(CourseName='New Course',Category='Safety',Duration='1 day',ModeOfDelivery='online',CourseFee=50,MaximumCapacity=5)
        other=self.second_trainee()
        self.client.force_login(self.link_portal(self.user))
        response=self.client.post('/portal/enroll/',{'Course':course.pk,'Trainee':other.pk,'EnrollmentStatus':'completed','PaymentStatus':'paid'})
        self.assertEqual(response.status_code,302)
        enrolled=Enrollment.objects.get(Course=course)
        self.assertEqual(enrolled.Trainee,self.trainee)
        self.assertEqual(enrolled.EnrollmentStatus,'pending')
        self.assertEqual(enrolled.PaymentStatus,'pending')
        self.assertEqual(self.client.post('/portal/enroll/',{'Course':course.pk}).status_code,200)
        self.assertEqual(Enrollment.objects.filter(Course=course).count(),1)
    def test_trainer_sees_only_assigned_sessions(self):
        assigned=self.session()
        otheruser=UserAccount.objects.create(Username='anothertrainer',Role='trainer',AccountStatus='active')
        other=Staff.objects.create(User=otheruser,FullName='Other Trainer',Role='trainer',StaffStatus='active',Email='othertrainer@example.com',Department='Training')
        session=TrainingSession.objects.create(Course=self.course,Trainer=other,SessionDate=date.today(),StartTime=time(13),EndTime=time(15),VenuePlatform='PRIVATE VENUE',SessionStatus='scheduled')
        self.client.force_login(self.link_portal(self.trainer.User))
        page=self.client.get('/portal/')
        self.assertContains(page,'Room A');self.assertNotContains(page,'PRIVATE VENUE')
        self.assertEqual(self.client.get(f'/portal/sessions/{session.pk}/attendance/').status_code,404)
        self.assertEqual(self.client.post(f'/portal/sessions/{session.pk}/attendance/',{}).status_code,404)
        self.assertEqual(self.client.get(f'/portal/sessions/{assigned.pk}/attendance/').status_code,200)
        self.assertEqual(self.client.get('/portal/enroll/').status_code,403)
    def test_trainer_attendance_pins_session_and_officer(self):
        session=self.session()
        self.client.force_login(self.link_portal(self.trainer.User))
        response=self.client.post(f'/portal/sessions/{session.pk}/attendance/',{'Trainee':self.trainee.pk,'AttendanceStatus':'present','CheckInTime':'','Session':999,'RecordedBy':self.admin.pk})
        self.assertEqual(response.status_code,302)
        record=Attendance.objects.get()
        self.assertEqual(record.Session,session);self.assertEqual(record.RecordedBy,self.trainer)
        response=self.client.post(f'/portal/sessions/{session.pk}/attendance/{self.trainee.pk}/',{'Trainee':self.trainee.pk,'AttendanceStatus':'late','CheckInTime':''})
        self.assertEqual(response.status_code,302)
        record.refresh_from_db();self.assertEqual(record.AttendanceStatus,'late')
    def test_trainer_cannot_record_unenrolled_trainee(self):
        session=self.session();other=self.second_trainee()
        self.client.force_login(self.link_portal(self.trainer.User))
        response=self.client.post(f'/portal/sessions/{session.pk}/attendance/',{'Trainee':other.pk,'AttendanceStatus':'present','CheckInTime':''})
        self.assertEqual(response.status_code,200)
        self.assertFalse(Attendance.objects.filter(Trainee=other).exists())
    def test_certificate_print_scoped_to_owner_and_issued(self):
        self.complete();self.payment(100);cert=self.certificate()
        self.client.force_login(self.link_portal(self.user))
        self.assertContains(self.client.get(f'/portal/certificates/{cert.pk}/'),'Certificate of Completion')
        other=self.second_trainee()
        self.client.force_login(self.link_portal(other.User,'otherportal'))
        self.assertEqual(self.client.get(f'/portal/certificates/{cert.pk}/').status_code,404)
        self.client.force_login(User.objects.get(username='portaluser'))
        cert.CertificateStatus='revoked';cert.save()
        self.assertEqual(self.client.get(f'/portal/certificates/{cert.pk}/').status_code,404)
    def test_portal_account_cannot_be_linked_twice(self):
        self.link_portal(self.user)
        self.as_admin()
        response=self.client.post('/portal-access/new/',{'ProjectAccount':self.user.pk,'username':'duplicateportal','email':'dup@example.com','password1':'LemonRiver!7845','password2':'LemonRiver!7845'})
        self.assertEqual(response.status_code,200)
        self.assertFalse(User.objects.filter(username='duplicateportal').exists())
    def test_trainer_assignment_rechecked_on_save(self):
        session=self.session()
        row=Attendance(Session=session,Trainee=self.trainee,RecordedBy=self.trainer,AttendanceStatus='present')
        with self.assertRaises(ValidationError): save_attendance(row,trainer_id=self.admin.pk)
        self.assertEqual(Attendance.objects.count(),0)
    def test_trainee_upcoming_schedule_scoped_to_enrollments(self):
        own=self.session('scheduled')
        othercourse=Course.objects.create(CourseName='PRIVATE COURSE',Category='Safety',Duration='1 day',ModeOfDelivery='online',CourseFee=50,MaximumCapacity=5)
        TrainingSession.objects.create(Course=othercourse,Trainer=self.trainer,SessionDate=date.today(),StartTime=time(13),EndTime=time(15),VenuePlatform='PRIVATE LOCATION',SessionStatus='scheduled')
        self.client.force_login(self.link_portal(self.user))
        response=self.client.get('/portal/')
        self.assertContains(response,'Room A')
        self.assertNotContains(response,'PRIVATE LOCATION')
