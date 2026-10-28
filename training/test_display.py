from decimal import Decimal

from django.template import Context, Template
from django.test import SimpleTestCase

from .templatetags.training_display import STATUSES, display_cell


class DisplayTests(SimpleTestCase):
    def test_website_users_template_renders(self):
        from django.template.loader import render_to_string
        html = render_to_string('training/website_users.html', {'users': []})
        self.assertIn('Website users', html)
        self.assertIn('No website users found.', html)

    def test_money_grouping_preserves_cents(self):
        self.assertEqual(display_cell(Decimal('1250000.50')), '1,250,000.50')

    def test_every_lifecycle_status_has_a_badge(self):
        for status in STATUSES:
            with self.subTest(status=status):
                self.assertIn('class="badge badge-', str(display_cell(status)))
                self.assertIn(status.title(), str(display_cell(status)))

    def test_untrusted_text_remains_escaped(self):
        template = Template('{% load training_display %}{{ value|display_cell }}')
        self.assertEqual(template.render(Context({'value': '<script>alert(1)</script>'})),
                         '&lt;script&gt;alert(1)&lt;/script&gt;')
