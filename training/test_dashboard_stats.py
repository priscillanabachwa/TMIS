import sqlite3

from django.test import SimpleTestCase

from .dashboard_stats import BALANCES_SQL


class BalanceStatisticsTests(SimpleTestCase):
    def test_balances_ignore_unconfirmed_and_closed_enrollments(self):
        with sqlite3.connect(':memory:') as db:
            db.executescript('''
                CREATE TABLE Course (CourseID INTEGER, CourseFee NUMERIC);
                CREATE TABLE Enrollment (EnrollmentID INTEGER, CourseID INTEGER, EnrollmentStatus TEXT);
                CREATE TABLE Payment (EnrollmentID INTEGER, AmountPaid NUMERIC, PaymentStatus TEXT);
                INSERT INTO Course VALUES (1,100000);
                INSERT INTO Enrollment VALUES (1,1,'active'),(2,1,'pending'),
                    (3,1,'cancelled'),(4,1,'withdrawn'),(5,1,'completed');
                INSERT INTO Payment VALUES (1,20000,'confirmed'),(1,30000,'confirmed'),
                    (1,50000,'pending'),(1,10000,'reversed'),(1,20000,'failed'),
                    (5,120000,'confirmed');
            ''')
            self.assertEqual(db.execute(BALANCES_SQL).fetchone(), (150000, 2))

    def test_empty_database_has_zero_balance(self):
        with sqlite3.connect(':memory:') as db:
            db.executescript('''
                CREATE TABLE Course (CourseID INTEGER, CourseFee NUMERIC);
                CREATE TABLE Enrollment (EnrollmentID INTEGER, CourseID INTEGER, EnrollmentStatus TEXT);
                CREATE TABLE Payment (EnrollmentID INTEGER, AmountPaid NUMERIC, PaymentStatus TEXT);
            ''')
            self.assertEqual(db.execute(BALANCES_SQL).fetchone(), (0, 0))
