from datetime import date,timedelta
from decimal import Decimal
from unittest.mock import patch
from django.test import SimpleTestCase,RequestFactory
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from .forms import CourseForm,TraineeForm
from .middleware import StaffOnlyMiddleware
from .views import dashboard
class WebsiteTests(SimpleTestCase):
    def test_anonymous_redirect(self):
        r=self.client.get('/')
        self.assertEqual(r.status_code,302)
        self.assertIn('/login/',r.url)
    def test_login_page(self):
        self.assertContains(self.client.get('/login/'),'Welcome to TMIS')
    def test_non_staff_blocked(self):
        req=RequestFactory().get('/')
        req.user=User(username='trainee',is_staff=False)
        self.assertEqual(StaffOnlyMiddleware(lambda r:None)(req).status_code,403)
    def test_course_validation(self):
        form=CourseForm()
        form.cleaned_data={'CourseFee':Decimal('-1'),'MaximumCapacity':0}
        with self.assertRaises(ValidationError): form.clean_CourseFee()
        with self.assertRaises(ValidationError): form.clean_MaximumCapacity()
        form.cleaned_data={'CourseFee':Decimal('0'),'MaximumCapacity':1}
        self.assertEqual(form.clean_CourseFee(),0)
        self.assertEqual(form.clean_MaximumCapacity(),1)
    def test_birth_date(self):
        form=TraineeForm()
        form.cleaned_data={'DateOfBirth':date.today()+timedelta(days=1)}
        with self.assertRaises(ValidationError): form.clean_DateOfBirth()
    @patch('training.views.connection')
    def test_dashboard_and_escaping(self,connection):
        cursor=connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value=(1,3,2,Decimal('190000'))
        cursor.fetchall.return_value=[('<script>bad</script>','Food Safety','active','paid')]
        req=RequestFactory().get('/')
        req.user=User(username='staff',is_staff=True)
        response=dashboard(req)
        self.assertEqual(response.status_code,200)
        self.assertIn(b'190,000',response.content)
        self.assertNotIn(b'<script>bad</script>',response.content)
        self.assertIn(b'&lt;script&gt;',response.content)
    def test_templates_compile(self):
        from django.template.loader import get_template
        for name in ['base','dashboard','records','form','login']:
            self.assertIsNotNone(get_template('training/'+name+'.html'))
