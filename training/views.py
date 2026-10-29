from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import connection,IntegrityError,transaction
from django.db.models import Q
from django.shortcuts import render,redirect,get_object_or_404
from .models import Trainee,Course
from .forms import TraineeForm,CourseForm
from .filters import filter_status
@login_required
def dashboard(request):
    from .dashboard_stats import dashboard_groups
    groups = dashboard_groups()
    priority = ['Total trainees', 'Total courses', 'Active enrollments', 'Pending enrollments',
                'Confirmed revenue · UGX', 'Outstanding balance · UGX',
                'Upcoming sessions', 'Issued certificates']
    cards = {card['label']: card for group in groups for card in group['cards']}
    key_stats = [cards[label] for label in priority if label in cards]
    with connection.cursor() as cursor:
        cursor.execute('SELECT t.FullName,c.CourseName,e.EnrollmentStatus,e.PaymentStatus FROM Enrollment e JOIN Trainee t ON t.TraineeID=e.TraineeID JOIN Course c ON c.CourseID=e.CourseID ORDER BY e.EnrollmentID DESC LIMIT 6')
        recent=cursor.fetchall()
    return render(request,'training/dashboard.html',{'key_stats':key_stats,'stat_groups':groups,'recent':recent,'section':'dashboard'})
@login_required
def records(request,kind):
    model,form,title = config(kind)
    q=request.GET.get('q','').strip()
    rows=model.objects.all().order_by('-'+model._meta.pk.name)
    if q:
        rows=rows.filter(Q(FullName__icontains=q)|Q(Email__icontains=q)) if kind=='trainees' else rows.filter(Q(CourseName__icontains=q)|Q(Category__icontains=q))
    rows,filters=filter_status(request,rows,'TraineeStatus' if kind=='trainees' else 'CourseStatus')
    return render(request,'training/records.html',{'page':Paginator(rows,12).get_page(request.GET.get('page')),'section':kind,'title':title,'q':q,'clear_url':reverse('records',kwargs={'kind':kind}),**filters})
def config(kind):
    from django.http import Http404
    if kind=='trainees': return Trainee,TraineeForm,'Trainees'
    if kind=='courses': return Course,CourseForm,'Courses'
    raise Http404
@login_required
def edit(request,kind,pk=None):
    model,form_class,title=config(kind)
    instance=get_object_or_404(model,pk=pk) if pk is not None else None
    form=form_class(request.POST or None,instance=instance)
    if request.method=='POST' and form.is_valid():
        try:
            with transaction.atomic():
                if kind=='courses':
                    from .services import save_course
                    save_course(form.save(commit=False))
                else:
                    from .accounts import save_trainee
                    save_trainee(form.save(commit=False),form.cleaned_data['Username'])
        except ValidationError as error:
            form.add_error(None,error)
        except IntegrityError:
            form.add_error(None,'The database rejected this record. Check account links and unique values, then try again.')
        else:
            messages.success(request,'Record saved successfully.')
            return redirect('records',kind=kind)
    return render(request,'training/form.html',{'form':form,'section':kind,'title':('Edit ' if instance else 'Add ')+title[:-1]})

from django.http import Http404
from django.core.exceptions import ValidationError
from django.urls import reverse
from functools import reduce
from operator import or_
from .modules import MODULES

def module_config(kind):
    if kind not in MODULES: raise Http404
    return MODULES[kind]

def record_key(row):
    if row.__class__.__name__ == 'Attendance':
        return f'{row.Session_id}-{row.Trainee_id}'
    return '-'.join(str(v) for v in row.pk) if isinstance(row.pk,tuple) else str(row.pk)

def resolve_key(model,key):
    try:
        if model.__name__=='Attendance':
            parts=key.split('-')
            if len(parts)!=2: raise ValueError
            return tuple(int(p) for p in parts)
        return int(key)
    except ValueError: raise Http404

def display_value(row,path):
    value=row
    for part in path.split('.'):
        value=getattr(value,part,None)
        if value is None: return '—'
    return value

@login_required
def module_records(request,kind):
    cfg=module_config(kind)
    q=request.GET.get('q','').strip()
    records=cfg['model'].objects.select_related(*cfg['related']).order_by('-pk')
    if q: records=records.filter(reduce(or_,[Q(**{field+'__icontains':q}) for field in cfg['search']]))
    status_field=next(field.name for field in cfg['model']._meta.fields if field.name.endswith('Status'))
    records,filters=filter_status(request,records,status_field)
    payment_status=request.GET.get('payment_status','')
    if kind=='enrollments' and payment_status in ['pending','partially paid','paid']:
        records=records.filter(PaymentStatus=payment_status)
    else:
        payment_status=''
    page=Paginator(records,12).get_page(request.GET.get('page'))
    rows=[{'values':[display_value(row,path) for path,label in cfg['columns']],'key':record_key(row)} for row in page]
    return render(request,'training/module_records.html',{'section':kind,'title':cfg['title'],'singular':cfg['singular'],'headers':[label for path,label in cfg['columns']],'rows':rows,'page':page,'q':q,'payment_status':payment_status,'clear_url':reverse('module_records',kwargs={'kind':kind}),**filters})

@login_required
def module_edit(request,kind,key=None):
    cfg=module_config(kind)
    if key and cfg['model'].__name__=='Attendance':
        session_id,trainee_id=resolve_key(cfg['model'],key)
        instance=get_object_or_404(cfg['model'],Session_id=session_id,Trainee_id=trainee_id)
    else:
        instance=get_object_or_404(cfg['model'],pk=resolve_key(cfg['model'],key)) if key else None
    form=cfg['form'](request.POST or None,instance=instance)
    if request.method=='POST' and form.is_valid():
        try: cfg['save'](form.save(commit=False))
        except ValidationError as error: form.add_error(None,error)
        except IntegrityError: form.add_error(None,'The database rejected this change. Check unique values, account links and business rules.')
        else:
            messages.success(request,'Record saved successfully.')
            return redirect('module_records',kind=kind)
    return render(request,'training/form.html',{'form':form,'section':kind,'title':('Edit ' if instance else 'Add ')+cfg['singular'],'cancel_url':reverse('module_records',kwargs={'kind':kind})})
