from datetime import date
from django import forms
from .models import Trainee,Course
class TraineeForm(forms.ModelForm):
    Username = forms.CharField(max_length=50,label='Project account username',help_text='Creates a linked project account with this profile. This is not a website sign-in.')
    class Meta:
        model = Trainee
        exclude = ['User']
        labels = {'FullName':'Full name','DateOfBirth':'Date of birth','PhoneNo':'Phone number','RegistrationDate':'Registration date','TraineeStatus':'Status'}
        widgets = {'DateOfBirth':forms.DateInput(attrs={'type':'date'}),'RegistrationDate':forms.DateInput(attrs={'type':'date'})}
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['RegistrationDate'].initial=date.today
        if self.instance.pk:
            self.fields['Username'].initial=self.instance.User.Username
            self.fields['Username'].disabled=True
    def clean_Username(self):
        from .models import UserAccount
        value=self.cleaned_data['Username'].strip()
        if not self.instance.pk and UserAccount.objects.filter(Username=value).exists():
            raise forms.ValidationError('This project username already exists. Choose another.')
        return value
    def clean_DateOfBirth(self):
        value=self.cleaned_data['DateOfBirth']
        if value > date.today(): raise forms.ValidationError('Date of birth cannot be in the future.')
        return value

class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = '__all__'
        labels = {'CourseName':'Course name','ModeOfDelivery':'Delivery mode','CourseFee':'Course fee in UGX','MaximumCapacity':'Maximum capacity','CourseStatus':'Status'}
        widgets = {'Description':forms.Textarea(attrs={'rows':3}),'Prerequisites':forms.Textarea(attrs={'rows':2})}
    def clean_CourseFee(self):
        value = self.cleaned_data['CourseFee']
        if value < 0: raise forms.ValidationError('Fee must be zero or greater.')
        return value
    def clean_MaximumCapacity(self):
        value = self.cleaned_data['MaximumCapacity']
        if value <= 0: raise forms.ValidationError('Capacity must be greater than zero.')
        return value

from django.utils import timezone
from .models import Enrollment,TrainingSession,Attendance,Payment,Certificate

DATE = forms.DateInput(attrs={'type':'date'})
TIME = forms.TimeInput(attrs={'type':'time'},format='%H:%M')
DATETIME = forms.DateTimeInput(attrs={'type':'datetime-local'},format='%Y-%m-%dT%H:%M')

class EnrollmentForm(forms.ModelForm):
    class Meta:
        model = Enrollment
        fields = ['Trainee','Course','EnrollmentDate','EnrollmentStatus']
        labels = {'EnrollmentDate':'Enrollment date','EnrollmentStatus':'Enrollment status'}
        widgets = {'EnrollmentDate':DATE}
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['EnrollmentDate'].initial = timezone.localdate
        if self.instance.pk:
            for name in ['Trainee','Course']: self.fields[name].disabled = True

class SessionForm(forms.ModelForm):
    class Meta:
        model = TrainingSession
        fields = '__all__'
        labels = {'SessionDate':'Session date','StartTime':'Start time','EndTime':'End time','VenuePlatform':'Venue or online platform','SessionStatus':'Session status'}
        widgets = {'SessionDate':DATE,'StartTime':TIME,'EndTime':TIME}
    def clean(self):
        values=super().clean()
        if values.get('StartTime') and values.get('EndTime') and values['EndTime'] <= values['StartTime']:
            self.add_error('EndTime','End time must be later than start time.')
        return values
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['Trainer'].queryset = self.fields['Trainer'].queryset.filter(Role='trainer',StaffStatus='active',User__AccountStatus='active')
        if self.instance.pk: self.fields['Course'].disabled = True

class AttendanceForm(forms.ModelForm):
    class Meta:
        model = Attendance
        fields = ['Session','Trainee','RecordedBy','AttendanceStatus','CheckInTime']
        labels = {'RecordedBy':'Recorded by','AttendanceStatus':'Attendance status','CheckInTime':'Check-in date and time'}
        widgets = {'CheckInTime':DATETIME}
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['RecordedBy'].queryset = self.fields['RecordedBy'].queryset.filter(StaffStatus='active',User__AccountStatus='active')
        if not self.instance._state.adding:
            for name in ['Session','Trainee']: self.fields[name].disabled = True

class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = '__all__'
        labels = {'AmountPaid':'Amount in UGX','PaymentDate':'Payment date and time','PaymentMethod':'Payment method','TransactionReference':'Transaction reference','PaymentStatus':'Payment status','InvoiceNumber':'Invoice number'}
        widgets = {'PaymentDate':DATETIME}
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['PaymentDate'].initial=timezone.now
        if self.instance.pk:
            for name in ['Enrollment','AmountPaid','PaymentDate','PaymentMethod','TransactionReference','InvoiceNumber']:
                self.fields[name].disabled = True
    def clean_AmountPaid(self):
        value=self.cleaned_data['AmountPaid']
        if value <= 0: raise forms.ValidationError('Payment must be greater than zero.')
        return value

class CertificateForm(forms.ModelForm):
    class Meta:
        model = Certificate
        fields = '__all__'
        labels = {'IssuedBy':'Authorized issuing officer','IssueDate':'Issue date','SerialNumber':'Serial number','CertificateStatus':'Certificate status'}
        widgets = {'IssueDate':DATE}
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['IssueDate'].initial=timezone.localdate
        self.fields['IssuedBy'].queryset=self.fields['IssuedBy'].queryset.filter(Role='administrator',StaffStatus='active',User__AccountStatus='active')
        if self.instance.pk:
            for name in ['Enrollment','IssuedBy','IssueDate','SerialNumber']: self.fields[name].disabled=True

from .models import Staff,UserAccount
from django.contrib.auth.models import User as WebsiteUser
from django.contrib.auth.forms import UserCreationForm,SetPasswordForm

class StaffForm(forms.ModelForm):
    Username = forms.CharField(max_length=50,label='Project account username',help_text='Creates the linked Staff/UserAccount records. Website sign-ins are managed separately.')
    class Meta:
        model=Staff
        exclude=['User']
        labels={'FullName':'Full name','PhoneNo':'Phone number','StaffStatus':'Profile status','DateJoined':'Date joined'}
        widgets={'DateJoined':DATE}
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        if self.instance.pk:
            self.fields['Username'].initial=self.instance.User.Username
            self.fields['Username'].disabled=True
    def clean_Username(self):
        value=self.cleaned_data['Username'].strip()
        if not self.instance.pk and UserAccount.objects.filter(Username=value).exists():
            raise forms.ValidationError('This project username already exists. Choose another.')
        return value

class AccountStatusForm(forms.ModelForm):
    class Meta:
        model=UserAccount
        fields=['AccountStatus']
        labels={'AccountStatus':'Project account status'}

class WebsiteUserForm(UserCreationForm):
    email=forms.EmailField(required=True)
    class Meta(UserCreationForm.Meta):
        model=WebsiteUser
        fields=['username','first_name','last_name','email']

class WebsiteUserEditForm(forms.ModelForm):
    class Meta:
        model=WebsiteUser
        fields=['first_name','last_name','email','is_active']
        labels={'is_active':'Allow website sign-in'}
