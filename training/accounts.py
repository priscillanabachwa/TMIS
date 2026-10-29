from functools import wraps
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User as WebsiteUser
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.hashers import make_password
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction,IntegrityError
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404,render,redirect
from django.urls import reverse
from .models import UserAccount,Trainee,Staff,TrainingSession
from .forms import StaffForm,AccountStatusForm,WebsiteUserForm,WebsiteUserEditForm
from .filters import filter_status

def administrator(view):
    @wraps(view)
    @login_required
    def wrapped(request,*args,**kwargs):
        if not request.user.is_superuser: return HttpResponseForbidden('Only a website superuser can manage staff and accounts.')
        return view(request,*args,**kwargs)
    return wrapped

def require(condition,message):
    if not condition: raise ValidationError(message)

def profile_account(obj,username,role):
    if obj._state.adding:
        obj.User=UserAccount.objects.create(Username=username,PasswordHash=make_password(None),Role=role,AccountStatus='active')
    else:
        account=UserAccount.objects.select_for_update().get(pk=obj.User_id)
        require(account.Role==role or isinstance(obj,Staff),'Project account role does not match this profile.')
        account.Role=role
        account.save(update_fields=['Role'])

@transaction.atomic
def save_trainee(obj,username):
    profile_account(obj,username,'trainee')
    obj.save()

@transaction.atomic
def save_staff(obj,username):
    if obj.pk:
        old=Staff.objects.select_for_update().get(pk=obj.pk)
        if old.Role=='trainer' and obj.Role!='trainer':
            require(not TrainingSession.objects.filter(Trainer_id=obj.pk,SessionStatus__in=['scheduled','postponed']).exists(),'Reassign this trainer’s scheduled/postponed sessions before changing their role.')
    profile_account(obj,username,obj.Role)
    obj.save()

@administrator
def staff_records(request):
    q=request.GET.get('q','').strip()
    rows=Staff.objects.select_related('User').order_by('FullName')
    if q: rows=rows.filter(Q(FullName__icontains=q)|Q(Email__icontains=q)|Q(Department__icontains=q))
    rows,filters=filter_status(request,rows,'StaffStatus')
    return render(request,'training/staff.html',{'page':Paginator(rows,12).get_page(request.GET.get('page')),'q':q,'section':'staff','title':'Staff','clear_url':reverse('staff_records'),**filters})

@administrator
def staff_edit(request,pk=None):
    instance=get_object_or_404(Staff,pk=pk) if pk else None
    form=StaffForm(request.POST or None,instance=instance)
    if request.method=='POST' and form.is_valid():
        try: save_staff(form.save(commit=False),form.cleaned_data['Username'])
        except ValidationError as error: form.add_error(None,error)
        except IntegrityError: form.add_error(None,'This username or staff email already exists, or a database rule rejected the record.')
        else:
            messages.success(request,'Staff profile and linked project account saved.')
            return redirect('staff_records')
    return render(request,'training/form.html',{'form':form,'section':'staff','title':'Edit staff' if instance else 'Add staff','cancel_url':reverse('staff_records')})

@administrator
def accounts(request):
    q=request.GET.get('q','').strip()
    rows=UserAccount.objects.order_by('Username')
    if q: rows=rows.filter(Q(Username__icontains=q)|Q(Role__icontains=q))
    rows,filters=filter_status(request,rows,'AccountStatus')
    return render(request,'training/accounts.html',{'page':Paginator(rows,12).get_page(request.GET.get('page')),'q':q,'section':'accounts','title':'Project accounts','clear_url':reverse('accounts'),**filters})

@administrator
def account_status(request,pk):
    account=get_object_or_404(UserAccount,pk=pk)
    form=AccountStatusForm(request.POST or None,instance=account)
    if request.method=='POST' and form.is_valid():
        with transaction.atomic():
            locked=UserAccount.objects.select_for_update().get(pk=pk)
            locked.AccountStatus=form.cleaned_data['AccountStatus']
            locked.save(update_fields=['AccountStatus'])
        messages.success(request,'Project account status updated. Website sign-ins are managed separately.')
        return redirect('accounts')
    return render(request,'training/form.html',{'form':form,'section':'accounts','title':f'Account status · {account.Username}','cancel_url':reverse('accounts')})

@administrator
def website_users(request):
    rows=website_user_accounts().select_related('portal_identity__Account').order_by('username')
    q=request.GET.get('q','').strip()
    if q:
        rows=rows.filter(Q(username__icontains=q)|Q(first_name__icontains=q)|Q(last_name__icontains=q)|Q(email__icontains=q))
    status=request.GET.get('status','')
    if status in ['active','disabled']:
        rows=rows.filter(is_active=status=='active')
    else:
        status=''
    return render(request,'training/website_users.html',{'users':rows,'section':'website_users','title':'Website users','q':q,'status':status,'status_options':[('active','Active'),('disabled','Disabled')],'clear_url':reverse('website_users')})

def website_user_accounts():
    return WebsiteUser.objects.filter(Q(is_superuser=True)|Q(is_staff=True)|Q(portal_identity__isnull=False))

@administrator
def website_user_create(request):
    form=WebsiteUserForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        try:
            with transaction.atomic():
                user=form.save(commit=False)
                user.is_staff=True
                user.is_superuser=False
                user.save()
        except IntegrityError: form.add_error(None,'That website username already exists.')
        else:
            messages.success(request,'Website operator created. This user can manage training operations but cannot manage staff or accounts.')
            return redirect('website_users')
    return render(request,'training/form.html',{'form':form,'section':'website_users','title':'Add website operator','cancel_url':reverse('website_users')})

@administrator
def website_user_edit(request,pk):
    user=get_object_or_404(website_user_accounts(),pk=pk)
    form=WebsiteUserEditForm(request.POST or None,instance=user)
    if request.method=='POST' and form.is_valid():
        if user.pk==request.user.pk and not form.cleaned_data['is_active']:
            form.add_error('is_active','You cannot disable your own sign-in.')
        else:
            with transaction.atomic():
                # The form cannot grant staff or superuser privileges.
                locked=WebsiteUser.objects.select_for_update().get(pk=pk)
                for field in form.Meta.fields: setattr(locked,field,form.cleaned_data[field])
                if locked.is_superuser and not locked.is_active:
                    other_admins=WebsiteUser.objects.filter(is_superuser=True,is_active=True).exclude(pk=pk).count()
                    require(other_admins>0,'Keep at least one active website superuser.')
                locked.save(update_fields=form.Meta.fields)
            messages.success(request,'Website user updated.')
            return redirect('website_users')
    return render(request,'training/form.html',{'form':form,'section':'website_users','title':f'Website access · {user.username}','cancel_url':reverse('website_users')})

@administrator
def website_password(request,pk):
    user=get_object_or_404(website_user_accounts(),pk=pk)
    form=SetPasswordForm(user,request.POST or None)
    if request.method=='POST' and form.is_valid():
        saved=form.save()
        if saved.pk==request.user.pk: update_session_auth_hash(request,saved)
        messages.success(request,'Website password changed. Existing sessions for that user will require the new password.')
        return redirect('website_users')
    return render(request,'training/form.html',{'form':form,'section':'website_users','title':f'Reset website password · {user.username}','cancel_url':reverse('website_users')})
