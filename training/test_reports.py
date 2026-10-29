from datetime import date
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import RequestFactory, SimpleTestCase
from pypdf import PdfReader

from .pdf import report_pdf
from .reports import REPORTS, report


class ReportActionTests(SimpleTestCase):
    def test_pdf_wraps_long_text_repeats_headers_and_includes_all_rows(self):
        rows = [(f'Learner {i:03}', 'Food safety and compliance ' * 4,
                 Decimal('125000.50'), date(2026, 10, 29)) for i in range(100)]
        response = report_pdf('Training report', ['Trainee', 'Course', 'FeeUGX', 'Date'],
                              rows, 'training', '<Food & Safety>')
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('training.pdf', response['Content-Disposition'])
        pdf = PdfReader(BytesIO(response.content))
        self.assertGreater(len(pdf.pages), 1)
        text = '\n'.join(page.extract_text() for page in pdf.pages)
        self.assertIn('Learner 099', text)
        self.assertIn('125,000.50', text)
        self.assertIn('<Food & Safety>', text)
        for page in pdf.pages:
            self.assertIn('Trainee', page.extract_text())

    @patch('training.reports.connection')
    def test_every_report_supports_apply_csv_pdf_and_print(self, connection):
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.description = [('Trainee',), ('FeeUGX',)]
        cursor.fetchall.return_value = [('Person '+str(i), Decimal('150000')) for i in range(30)]
        for name in REPORTS:
            for action in ['', '&export=csv', '&export=pdf', '&print=1']:
                with self.subTest(report=name, action=action):
                    request = RequestFactory().get(f'/reports/?report={name}'+action)
                    request.user = User(username='operator', is_staff=True)
                    response = report(request)
                    self.assertEqual(response.status_code, 200)
                    if 'pdf' in action:
                        self.assertTrue(response.content.startswith(b'%PDF-'))
                        text = ''.join(p.extract_text() for p in PdfReader(BytesIO(response.content)).pages)
                        self.assertIn('Person 29', text)
                    elif 'csv' in action:
                        self.assertIn(b'Person 29', response.content)
                    elif 'print' in action:
                        self.assertIn(b'Person 29', response.content)
                        self.assertIn(b"window.addEventListener('load'", response.content)
                    else:
                        self.assertIn(b'Download PDF', response.content)
                        self.assertNotIn(b'Person 29', response.content)

    @patch('training.reports.connection')
    def test_exports_keep_filters_and_handle_no_matches(self, connection):
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.description = [('Trainee',)]
        cursor.fetchall.return_value = [('Alice',), ('Bob',)]
        for query in ['Alice', 'No matching name']:
            request = RequestFactory().get('/reports/', {'q': query, 'export': 'pdf'})
            request.user = User(username='operator', is_staff=True)
            response = report(request)
            text = ''.join(p.extract_text() for p in PdfReader(BytesIO(response.content)).pages)
            self.assertNotIn('Bob', text)
            self.assertIn('Alice' if query == 'Alice' else 'No matching records.', text)
