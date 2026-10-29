from django.contrib.auth.models import User
from django.test import TestCase

from .accounts import website_user_accounts


class WebsiteAccountTests(TestCase):
    def test_superusers_visible_without_staff_flag(self):
        admin = User.objects.create(username='admin_without_staff', is_superuser=True,
                                    is_staff=False, is_active=False)
        operator = User.objects.create(username='operator', is_staff=True)
        User.objects.create(username='unlinked_user')
        self.assertSetEqual(set(website_user_accounts().values_list('pk', flat=True)),
                            {admin.pk, operator.pk})
