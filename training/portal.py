from datetime import date
from functools import wraps
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError,transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404,redirect,render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from .models import PortalIdentity,UserAccount,Trainee,Staff,Course,Enrollment,TrainingSession,Attendance,Payment,Certificate,Notification
from .forms import WebsiteUserForm,AttendanceForm
from .accounts import administrator
from .services import save_enrollment,save_attendance

def scoped(role=None):
    def decorate(view):
        @wraps(view)
        @login_required
        def wrapped(request,*args,**kwargs):
            if request.portal_role is None or (role and request.portal_role!=role):
                return HttpResponseForbidden('This portal is not available for your account.')
            return view(request,*args,**kwargs)
        return wrapped
    return decorate

class PortalAccessForm(WebsiteUserForm):
    ProjectAccount=forms.ModelChoiceField(queryset=UserAccount.objects.none(),label='Project account',help_text='Choose an existing active trainee or trainer. One website login can link to each account.')
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        from django.db.models import Q
        self.fields['ProjectAccount'].queryset=UserAccount.objects.filter(AccountStatus='active',website_identity__isnull=True).filter(Q(Role='trainee',trainee__TraineeStatus='active')|Q(Role='trainer',staff__Role='trainer',staff__StaffStatus='active')).order_by('Username')
        self.fields['ProjectAccount'].label_from_instance=lambda account:f'{account.Username} ({account.Role})'
        self.order_fields(['ProjectAccount','username','first_name','last_name','email','password1','password2'])

@transaction.atomic
def create_portal_identity(form):
    account=UserAccount.objects.select_for_update().get(pk=form.cleaned_data['ProjectAccount'].pk)
    if account.AccountStatus!='active' or PortalIdentity.objects.filter(Account=account).exists():
        raise ValidationError('This project account is inactive or already linked.')
    valid=(account.Role=='trainee' and Trainee.objects.filter(User=account,TraineeStatus='active').exists()) or (account.Role=='trainer' and Staff.objects.filter(User=account,Role='trainer',StaffStatus='active').exists())
    if not valid: raise ValidationError('Select an active trainee or trainer profile.')
    login=form.save(commit=False)
    login.is_staff=False
    login.is_superuser=False
    login.save()
    return PortalIdentity.objects.create(Login=login,Account=account)

@administrator
def provision(request):
    form=PortalAccessForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        try: create_portal_identity(form)
        except ValidationError as error: form.add_error(None,error)
        except IntegrityError: form.add_error(None,'The username or project account is already linked. Choose another.')
        else:
            messages.success(request,'Portal login created. The user can sign in at the normal login page.')
            return redirect('website_users')
    return render(request,'training/form.html',{'form':form,'section':'website_users','title':'Add trainee or trainer login','cancel_url':reverse('website_users')})

@scoped()
def home(request):
    profile=request.portal_profile
    if request.portal_role=='trainee':
        enrollments=Enrollment.objects.filter(Trainee=profile).select_related('Course').order_by('-EnrollmentDate','-pk')
        payments=Payment.objects.filter(Enrollment__Trainee=profile).select_related('Enrollment__Course').order_by('-PaymentDate')
        certificates=Certificate.objects.filter(Enrollment__Trainee=profile).select_related('Enrollment__Course').order_by('-IssueDate')
        return render(request,'training/trainee_portal.html',{'section':'portal','title':'My training','profile':profile,'enrollments':enrollments,'payments':payments[:20],'certificates':certificates,'upcoming':TrainingSession.objects.filter(Course__enrollment__Trainee=profile,Course__enrollment__EnrollmentStatus__in=['pending','active'],SessionStatus='scheduled',SessionDate__gte=timezone.localdate()).select_related('Course','Trainer').order_by('SessionDate','StartTime')[:10],'unread':Notification.objects.filter(User_id=profile.User_id,NotificationType='in-app',IsRead=False).count()})
    sessions=TrainingSession.objects.filter(Trainer=profile).select_related('Course').order_by('-SessionDate','StartTime')
    return render(request,'training/trainer_portal.html',{'section':'portal','title':'My sessions','profile':profile,'page':Paginator(sessions,12).get_page(request.GET.get('page'))})

class SelfEnrollmentForm(forms.Form):
    Course=forms.ModelChoiceField(queryset=Course.objects.filter(CourseStatus='active'),label='Course')
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['Course'].label_from_instance=lambda course:f'{course.CourseName} — UGX {course.CourseFee:,.0f}'

@scoped('trainee')
def enroll(request):
    form=SelfEnrollmentForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        obj=Enrollment(Trainee=request.portal_profile,Course=form.cleaned_data['Course'],EnrollmentDate=date.today(),EnrollmentStatus='pending')
        try: save_enrollment(obj)
        except ValidationError as error: form.add_error(None,error)
        except IntegrityError: form.add_error(None,'You are already enrolled in this course or the database rejected the enrollment.')
        else:
            messages.success(request,'Your enrollment was recorded. Contact the training office about payment and scheduling.')
            return redirect('portal_home')
    return render(request,'training/form.html',{'form':form,'section':'portal','title':'Enroll in a course','cancel_url':reverse('portal_home')})

@scoped()
def notifications(request):
    rows=Notification.objects.filter(User_id=request.portal_profile.User_id,NotificationType='in-app').order_by('-DateSent','-pk')
    return render(request,'training/portal_notifications.html',{'section':'notifications','title':'My notifications','page':Paginator(rows,15).get_page(request.GET.get('page'))})

@scoped()
@require_POST
def mark_read(request,pk):
    notice=get_object_or_404(Notification,pk=pk,User_id=request.portal_profile.User_id,NotificationType='in-app')
    notice.IsRead=True
    notice.save(update_fields=['IsRead'])
    return redirect('portal_notifications')

class TrainerAttendanceForm(AttendanceForm):
    def __init__(self,*args,session,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields.pop('Session')
        self.fields.pop('RecordedBy')
        self.fields['Trainee'].queryset=Trainee.objects.filter(enrollment__Course_id=session.Course_id,enrollment__EnrollmentStatus__in=['pending','active','completed']).distinct()

@scoped('trainer')
def session_attendance(request,session_id,trainee_id=None):
    session=get_object_or_404(TrainingSession,pk=session_id,Trainer=request.portal_profile)
    instance=get_object_or_404(Attendance,Session=session,Trainee_id=trainee_id) if trainee_id else None
    form=TrainerAttendanceForm(request.POST or None,instance=instance,session=session)
    if request.method=='POST' and form.is_valid():
        obj=form.save(commit=False)
        obj.Session=session
        obj.RecordedBy=request.portal_profile
        try: save_attendance(obj,trainer_id=request.portal_profile.pk)
        except ValidationError as error: form.add_error(None,error)
        except IntegrityError: form.add_error(None,'Attendance already exists for this trainee and session. Edit the existing record.')
        else:
            messages.success(request,'Attendance saved.')
            return redirect('trainer_attendance',session_id=session.pk)
    records=Attendance.objects.filter(Session=session).select_related('Trainee').order_by('Trainee__FullName')
    return render(request,'training/trainer_attendance.html',{'section':'portal','title':'Session attendance','session':session,'form':form,'records':records})

@scoped('trainee')
def certificate(request,pk):
    obj=get_object_or_404(Certificate.objects.select_related('Enrollment__Trainee','Enrollment__Course','IssuedBy'),pk=pk,Enrollment__Trainee=request.portal_profile,CertificateStatus='issued')
    return render(request,'training/portal_certificate.html',{'certificate':obj,'title':'Training certificate'})
