-- ============================================================
-- seed_sample.sql : extra SAMPLE data for the TMIS database
-- ------------------------------------------------------------
-- Load this LAST, after: schema.sql, seed.sql, seed_training.sql,
-- seed_payments.sql, seed_completion.sql
-- It only ADDS rows (all IDs start at 101 or 201) and never changes
-- the existing demo rows. Running it twice is safe: rows that already
-- exist are skipped.
--
-- All names, emails, phone numbers and NINs are made up.
-- Every sample account uses the same demo password: SamplePass#2026
-- (demo only; never use it for a real account).
-- Plain ASCII characters only, because the database uses a cp850 charset.
-- ============================================================
USE tmis_db;
SET @pw = 'pbkdf2_sha256$600000$4e18237bbe06e253774a2d42553f2030$2402785ebf85d9502774d9f01da3f5df1fd9f0893bf341d2d2cad5a7161b1216';

-- 1. User accounts: 15 trainees (101-115) and 5 staff (201-205) ----------
INSERT INTO useraccount (UserID, Username, PasswordHash, Role, AccountStatus, CreatedAt, LastLogin) VALUES
(101, 'akellobrenda',   @pw, 'trainee',       'active',   '2026-07-20 09:00:00', '2026-10-15 08:30:00'),
(102, 'mukasadaniel',   @pw, 'trainee',       'active',   '2026-07-20 09:05:00', '2026-10-14 17:45:00'),
(103, 'namatovuruth',   @pw, 'trainee',       'active',   '2026-07-22 10:10:00', '2026-09-30 12:00:00'),
(104, 'okellosamuel',   @pw, 'trainee',       'active',   '2026-08-15 11:00:00', '2026-10-01 09:15:00'),
(105, 'nakatoesther',   @pw, 'trainee',       'active',   '2026-08-15 11:05:00', '2026-10-16 10:40:00'),
(106, 'ssemakulapaul',  @pw, 'trainee',       'active',   '2026-08-18 14:00:00', NULL),
(107, 'atimjuliet',     @pw, 'trainee',       'active',   '2026-09-10 08:20:00', '2026-10-12 15:05:00'),
(108, 'katomoses',      @pw, 'trainee',       'active',   '2026-09-10 08:25:00', '2026-10-13 11:30:00'),
(109, 'nabiryejoan',    @pw, 'trainee',       'inactive', '2026-09-12 13:00:00', '2026-09-28 16:00:00'),
(110, 'opiohenry',      @pw, 'trainee',       'active',   '2026-10-05 09:30:00', '2026-10-17 07:50:00'),
(111, 'nansubugagrace', @pw, 'trainee',       'active',   '2026-10-20 09:00:00', NULL),
(112, 'mugabijoseph',   @pw, 'trainee',       'active',   '2026-10-20 09:10:00', NULL),
(113, 'nakimulirita',   @pw, 'trainee',       'active',   '2026-10-21 10:00:00', NULL),
(114, 'okurutbrian',    @pw, 'trainee',       'active',   '2026-10-21 10:15:00', NULL),
(115, 'namanyasusan',   @pw, 'trainee',       'active',   '2026-10-22 08:45:00', NULL),
(201, 'namukasaflorence',@pw, 'trainer',      'active',   '2026-07-01 08:00:00', '2026-10-16 08:05:00'),
(202, 'byaruhangaivan', @pw, 'trainer',       'active',   '2026-07-01 08:05:00', '2026-10-15 07:55:00'),
(203, 'achiengpatricia',@pw, 'trainer',       'active',   '2026-07-02 08:10:00', '2026-10-17 08:20:00'),
(204, 'mugisharobert',  @pw, 'administrator', 'active',   '2026-07-01 07:45:00', '2026-10-17 07:30:00'),
(205, 'tumusiimealex',  @pw, 'trainer',       'inactive', '2026-07-02 08:15:00', '2026-08-30 10:00:00')
ON DUPLICATE KEY UPDATE UserID = UserID;

-- 2. Staff (101-105) ------------------------------------------------------
INSERT INTO staff (StaffID, UserID, FullName, Role, Email, PhoneNo, Department, StaffStatus, DateJoined) VALUES
(101, 201, 'Namukasa Florence',  'trainer',       'namukasa.florence@gmail.com',  '0700000201', 'Training',       'active',   '2026-07-01'),
(102, 202, 'Byaruhanga Ivan',    'trainer',       'byaruhangaivan45@gmail.com',    '0700000202', 'Training',       'active',   '2026-07-01'),
(103, 203, 'Achieng Patricia',   'trainer',       'apatricia@gmail.com',   '0700000203', 'Quality Assurance', 'active', '2026-07-02'),
(104, 204, 'Mugisha Robert',     'administrator', 'mugishabert@gmail.com',     '0700000204', 'Administration', 'active',   '2026-07-01'),
(105, 205, 'Tumusiime Alex',     'trainer',       'tumusiime.alex@gmail.com',   '0700000205', 'Training',       'inactive', '2026-07-02')
ON DUPLICATE KEY UPDATE StaffID = StaffID;

-- 3. Trainees (101-115) ---------------------------------------------------
INSERT INTO trainee (TraineeID, UserID, FullName, DateOfBirth, Gender, NIN, PhoneNo, Email, Organization, Address, RegistrationDate, TraineeStatus) VALUES
(101, 101, 'Akello Brenda',     '1995-03-14', 'female', 'SAMPLE-NIN-101', '0772458136', 'brendaakello95@gmail.com',   'Kampala Dairy Ltd',        'Kampala',  '2026-07-20', 'active'),
(102, 102, 'Mukasa Daniel',     '1990-11-02', 'male',   'SAMPLE-NIN-102', '0701823946', 'dmukasa110@gmail.com',   'Kampala Dairy Ltd',        'Kampala',  '2026-07-20', 'active'),
(103, 103, 'Namatovu Ruth',     '1993-06-25', 'female', 'SAMPLE-NIN-103', '0783315207', 'ruthnamatovu@gmail.com',   'Pearl Foods Ltd',          'Entebbe',  '2026-07-22', 'active'),
(104, 104, 'Okello Samuel',     '1988-01-30', 'male',   'SAMPLE-NIN-104', '0755096412', 'samuelokello8@gmail.com',   'Pearl Foods Ltd',          'Entebbe',  '2026-08-15', 'active'),
(105, 105, 'Nakato Esther',     '1996-09-09', 'female', 'SAMPLE-NIN-105', '0776204851', 'esthernakato96@gmail.com',   'Ntake bakery',       'Jinja',    '2026-08-15', 'active'),
(106, 106, 'Ssemakula Paul',    '1992-04-18', 'male',   'SAMPLE-NIN-106', '0788741320', 'paulssemakula@gmail.com',  'Nile Fresh Produce',       'Jinja',    '2026-08-18', 'active'),
(107, 107, 'Atim Juliet',       '1994-12-05', 'female', 'SAMPLE-NIN-107', '0759318674', 'julietatim94@gmail.com',     'Yalelo fish farm',          'Gulu',     '2026-09-10', 'active'),
(108, 108, 'Kato Moses',        '1991-07-21', 'male',   'SAMPLE-NIN-108', '0702567390', 'mkato91@gmail.com',      'Lakeside Bakers',          'Gulu',     '2026-09-10', 'active'),
(109, 109, 'Nabirye Joan',      '1997-02-11', 'female', 'SAMPLE-NIN-109', '0794120685', 'joannabirye@gmail.com',    'Savannah Beverages',       'Mbarara',  '2026-09-12', 'inactive'),
(110, 110, 'Opio Henry',        '1989-08-27', 'male',   'SAMPLE-NIN-110', '0777653028', 'henryopio89@gmail.com',      'Entebbe Fish Processors',  'Entebbe',  '2026-10-05', 'active'),
(111, 111, 'Nansubuga Grace',   '1998-05-16', 'female', 'SAMPLE-NIN-111', '0771000111', 'grace.nansubuga@example.com', 'Kampala Fresh Foods', 'Kampala', '2026-10-20', 'active'),
(112, 112, 'Mugabi Joseph',     '1992-09-08', 'male',   'SAMPLE-NIN-112', '0771000112', 'joseph.mugabi@example.com',   'Lakeview Processors', 'Entebbe', '2026-10-20', 'active'),
(113, 113, 'Nakimuli Rita',     '1995-02-22', 'female', 'SAMPLE-NIN-113', '0771000113', 'rita.nakimuli@example.com',   'Green Valley Foods', 'Jinja',   '2026-10-21', 'active'),
(114, 114, 'Okurut Brian',      '1989-12-03', 'male',   'SAMPLE-NIN-114', '0771000114', 'brian.okurut@example.com',    'Northern Harvest',   'Gulu',    '2026-10-21', 'active'),
(115, 115, 'Namanya Susan',     '1997-07-11', 'female', 'SAMPLE-NIN-115', '0771000115', 'susan.namanya@example.com',   'Highland Dairy',     'Mbarara', '2026-10-22', 'active')
ON DUPLICATE KEY UPDATE Email = VALUES(Email), PhoneNo = VALUES(PhoneNo);

-- 4. Courses (101-106) ----------------------------------------------------
INSERT INTO course (CourseID, CourseName, Description, Category, Duration, ModeOfDelivery, CourseFee, CourseStatus, Prerequisites, MaximumCapacity) VALUES
(101, 'Food Labelling and Compliance',   'Labelling rules and regulatory compliance for packaged foods.', 'Quality Assurance', '2 days', 'hybrid',   120000.00, 'active',   NULL,                          25),
(102, 'Internal Auditing for Food Safety','How to plan and carry out internal food safety audits.',         'Quality Assurance', '4 days', 'physical', 250000.00, 'active',   'HACCP Fundamentals',          20),
(103, 'Good Manufacturing Practices',    'Hygiene, facility and process controls in food production.',    'Food Safety',       '3 days', 'physical', 180000.00, 'active',   NULL,                          30),
(104, 'Food Handlers Refresher (Online)','A short online refresher for staff who handle food.',            'Food Safety',       '1 day',  'online',    60000.00, 'active',   'Basic Food Safety',           40),
(105, 'Legacy Cold Chain Handling',      'Older course kept for records. No longer offered.',             'Food Safety',       '2 days', 'physical',  90000.00, 'archived', NULL,                          15),
(106, 'Practical Food Packaging',        'Packaging hygiene, material selection and shelf-life basics.',  'Food Safety',       '2 days', 'hybrid',   150000.00, 'active',   'Basic Food Safety',           24)
ON DUPLICATE KEY UPDATE CourseID = CourseID;

-- 5. Training sessions (101-113) -----------------------------------------
INSERT INTO trainingsession (SessionID, CourseID, TrainerID, SessionDate, StartTime, EndTime, VenuePlatform, SessionStatus) VALUES
(101, 101, 101, '2026-08-10', '09:00:00', '16:00:00', 'NFSI Training Room A',                 'completed'),
(102, 101, 101, '2026-08-11', '09:00:00', '13:00:00', 'Online (Zoom)',                         'completed'),
(103, 102, 102, '2026-09-07', '08:30:00', '16:30:00', 'NFSI Training Room B',                 'completed'),
(104, 102, 102, '2026-09-08', '08:30:00', '16:30:00', 'NFSI Training Room B',                 'completed'),
(105, 102, 102, '2026-09-09', '08:30:00', '16:30:00', 'NFSI Training Room B',                 'completed'),
(106, 102, 102, '2026-09-10', '08:30:00', '12:30:00', 'NFSI Training Room B',                 'completed'),
(107, 103, 103, '2026-10-05', '09:00:00', '16:00:00', 'NFSI Workshop Hall',                   'completed'),
(108, 103, 103, '2026-10-06', '09:00:00', '16:00:00', 'NFSI Workshop Hall',                   'completed'),
(109, 103, 103, '2026-10-07', '09:00:00', '14:00:00', 'NFSI Workshop Hall',                   'completed'),
(110, 104, 103, '2026-11-12', '09:00:00', '15:00:00', 'Online (Microsoft Teams)',             'scheduled'),
(111, 104, 103, '2026-11-19', '09:00:00', '15:00:00', 'Online (Microsoft Teams), second group','postponed'),
(112, 106, 101, '2026-11-25', '09:00:00', '16:00:00', 'NFSI Training Room A',                 'scheduled'),
(113, 106, 101, '2026-11-26', '09:00:00', '13:00:00', 'Online (Microsoft Teams)',             'scheduled')
ON DUPLICATE KEY UPDATE SessionID = SessionID;

-- 6. Enrollments (101-118) ------------------------------------------------
INSERT INTO enrollment (EnrollmentID, TraineeID, CourseID, EnrollmentDate, EnrollmentStatus, PaymentStatus) VALUES
(101, 101, 101, '2026-07-28', 'completed', 'paid'),
(102, 102, 101, '2026-07-30', 'completed', 'paid'),
(103, 103, 101, '2026-08-01', 'completed', 'partially paid'),
(104, 104, 102, '2026-08-25', 'completed', 'paid'),
(105, 105, 102, '2026-08-26', 'completed', 'paid'),
(106, 106, 102, '2026-08-27', 'completed', 'partially paid'),
(107, 107, 103, '2026-09-25', 'completed', 'paid'),
(108, 108, 103, '2026-09-26', 'completed', 'paid'),
(109, 109, 103, '2026-09-28', 'withdrawn', 'partially paid'),
(110, 110, 104, '2026-10-12', 'active',    'pending'),
(111, 101, 104, '2026-10-12', 'active',    'paid'),
(112, 102,   3, '2026-10-14', 'pending',   'partially paid'),
(113, 104,   3, '2026-10-15', 'cancelled', 'pending'),
(114, 111, 106, '2026-10-22', 'active',    'partially paid'),
(115, 112, 106, '2026-10-22', 'active',    'paid'),
(116, 113, 104, '2026-10-23', 'pending',   'pending'),
(117, 114, 102, '2026-10-23', 'active',    'partially paid'),
(118, 115, 106, '2026-10-24', 'active',    'pending')
ON DUPLICATE KEY UPDATE EnrollmentID = EnrollmentID;

-- 7. Payments (101-117). Totals match each course fee or fall short -------
INSERT INTO payment (PaymentID, EnrollmentID, AmountPaid, PaymentDate, PaymentMethod, TransactionReference, PaymentStatus, InvoiceNumber) VALUES
(101, 101, 120000.00, '2026-07-28 10:15:00', 'mobile money',  'SAMPLE-TXN-101', 'confirmed', 'SAMPLE-INV-101'),
(102, 102,  70000.00, '2026-07-30 11:00:00', 'bank transfer', 'SAMPLE-TXN-102', 'confirmed', 'SAMPLE-INV-102'),
(103, 102,  50000.00, '2026-08-05 14:20:00', 'cash',          'SAMPLE-TXN-103', 'confirmed', 'SAMPLE-INV-103'),
(104, 103,  60000.00, '2026-08-01 09:40:00', 'mobile money',  'SAMPLE-TXN-104', 'confirmed', 'SAMPLE-INV-104'),
(105, 104, 150000.00, '2026-08-25 13:10:00', 'bank transfer', 'SAMPLE-TXN-105', 'confirmed', 'SAMPLE-INV-105'),
(106, 104, 100000.00, '2026-09-02 10:05:00', 'bank transfer', 'SAMPLE-TXN-106', 'confirmed', 'SAMPLE-INV-106'),
(107, 105, 250000.00, '2026-08-26 15:30:00', 'card',          'SAMPLE-TXN-107', 'confirmed', 'SAMPLE-INV-107'),
(108, 106, 100000.00, '2026-08-27 09:55:00', 'cash',          'SAMPLE-TXN-108', 'confirmed', 'SAMPLE-INV-108'),
(109, 107, 180000.00, '2026-09-25 12:00:00', 'card',          'SAMPLE-TXN-109', 'confirmed', 'SAMPLE-INV-109'),
(110, 108, 100000.00, '2026-09-26 10:30:00', 'mobile money',  'SAMPLE-TXN-110', 'confirmed', 'SAMPLE-INV-110'),
(111, 108,  80000.00, '2026-10-02 16:45:00', 'mobile money',  'SAMPLE-TXN-111', 'confirmed', 'SAMPLE-INV-111'),
(112, 109,  50000.00, '2026-09-28 11:25:00', 'cash',          'SAMPLE-TXN-112', 'confirmed', 'SAMPLE-INV-112'),
(113, 111,  60000.00, '2026-10-12 17:10:00', 'mobile money',  'SAMPLE-TXN-113', 'confirmed', 'SAMPLE-INV-113'),
(114, 112, 100000.00, '2026-10-14 10:00:00', 'bank transfer', 'SAMPLE-TXN-114', 'confirmed', 'SAMPLE-INV-114'),
(115, 114,  50000.00, '2026-10-22 10:30:00', 'mobile money',  'SAMPLE-TXN-115', 'confirmed', 'SAMPLE-INV-115'),
(116, 115, 150000.00, '2026-10-22 11:10:00', 'bank transfer', 'SAMPLE-TXN-116', 'confirmed', 'SAMPLE-INV-116'),
(117, 117, 100000.00, '2026-10-23 09:45:00', 'cash',          'SAMPLE-TXN-117', 'confirmed', 'SAMPLE-INV-117')
ON DUPLICATE KEY UPDATE PaymentID = PaymentID;

-- 8. Attendance for the completed sessions --------------------------------
-- present = turned up, absent = did not. Trainee 106 (low) and 109 (withdrew)
-- have poor attendance, so the eligibility report shows a mix of results.
INSERT INTO attendance (SessionID, TraineeID, RecordedBy, AttendanceStatus, CheckInTime, RecordedAt) VALUES
(101, 101, 101, 'present', '2026-08-10 08:55:00', '2026-08-10 16:00:00'),
(101, 102, 101, 'present', '2026-08-10 08:58:00', '2026-08-10 16:00:00'),
(101, 103, 101, 'present', '2026-08-10 09:02:00', '2026-08-10 16:00:00'),
(102, 101, 101, 'present', '2026-08-11 08:57:00', '2026-08-11 13:00:00'),
(102, 102, 101, 'present', '2026-08-11 09:01:00', '2026-08-11 13:00:00'),
(102, 103, 101, 'present', '2026-08-11 09:03:00', '2026-08-11 13:00:00'),
(103, 104, 102, 'present', '2026-09-07 08:25:00', '2026-09-07 16:30:00'),
(103, 105, 102, 'present', '2026-09-07 08:28:00', '2026-09-07 16:30:00'),
(103, 106, 102, 'present', '2026-09-07 08:35:00', '2026-09-07 16:30:00'),
(104, 104, 102, 'present', '2026-09-08 08:26:00', '2026-09-08 16:30:00'),
(104, 105, 102, 'present', '2026-09-08 08:29:00', '2026-09-08 16:30:00'),
(104, 106, 102, 'absent',  NULL,                  '2026-09-08 16:30:00'),
(105, 104, 102, 'present', '2026-09-09 08:24:00', '2026-09-09 16:30:00'),
(105, 105, 102, 'present', '2026-09-09 08:27:00', '2026-09-09 16:30:00'),
(105, 106, 102, 'absent',  NULL,                  '2026-09-09 16:30:00'),
(106, 104, 102, 'present', '2026-09-10 08:23:00', '2026-09-10 12:30:00'),
(106, 105, 102, 'present', '2026-09-10 08:30:00', '2026-09-10 12:30:00'),
(106, 106, 102, 'absent',  NULL,                  '2026-09-10 12:30:00'),
(107, 107, 103, 'present', '2026-10-05 08:55:00', '2026-10-05 16:00:00'),
(107, 108, 103, 'present', '2026-10-05 08:58:00', '2026-10-05 16:00:00'),
(107, 109, 103, 'present', '2026-10-05 09:05:00', '2026-10-05 16:00:00'),
(108, 107, 103, 'present', '2026-10-06 08:56:00', '2026-10-06 16:00:00'),
(108, 108, 103, 'present', '2026-10-06 08:59:00', '2026-10-06 16:00:00'),
(108, 109, 103, 'absent',  NULL,                  '2026-10-06 16:00:00'),
(109, 107, 103, 'present', '2026-10-07 08:57:00', '2026-10-07 14:00:00'),
(109, 108, 103, 'present', '2026-10-07 09:00:00', '2026-10-07 14:00:00'),
(109, 109, 103, 'absent',  NULL,                  '2026-10-07 14:00:00')
ON DUPLICATE KEY UPDATE SessionID = SessionID;

-- 9. Certificates: only for trainees who completed, paid in full and attended
-- Enrollment 108 is eligible but not issued yet (shows as "ready to issue").
INSERT INTO certificate (CertificateID, EnrollmentID, IssuedBy, IssueDate, SerialNumber, CertificateStatus) VALUES
(101, 101, 104, '2026-08-14', 'SAMPLE-CERT-101', 'issued'),
(102, 102, 104, '2026-08-14', 'SAMPLE-CERT-102', 'issued'),
(103, 104, 104, '2026-09-14', 'SAMPLE-CERT-103', 'issued'),
(104, 105, 104, '2026-09-14', 'SAMPLE-CERT-104', 'issued'),
(105, 107, 104, '2026-10-12', 'SAMPLE-CERT-105', 'issued')
ON DUPLICATE KEY UPDATE CertificateID = CertificateID;

-- 10. Notifications (101-114) --------------------------------------------
INSERT INTO notification (NotificationID, UserID, NotificationType, MessageContent, DateSent, DeliveryStatus, IsRead) VALUES
(101, 101, 'email',  'Your enrollment in Food Labelling and Compliance is confirmed.',                      '2026-07-28 10:20:00', 'delivered', 1),
(102, 102, 'SMS',    'Payment of UGX 70,000 received. Balance: UGX 50,000.',                               '2026-07-30 11:05:00', 'delivered', 1),
(103, 103, 'SMS',    'Reminder: you have an outstanding balance of UGX 60,000 for your course.',           '2026-08-20 09:00:00', 'delivered', 0),
(104, 104, 'in-app', 'Your certificate is ready for collection.',                                          '2026-09-14 15:00:00', 'delivered', 0),
(105, 106, 'email',  'Please clear your balance of UGX 150,000 to qualify for certification.',             '2026-09-15 08:30:00', 'sent',      0),
(106, 108, 'email',  'Your certificate is being processed.',                                               '2026-10-09 10:00:00', 'sent',      0),
(107, 110, 'SMS',    'Reminder: Food Handlers Refresher (Online) starts on 12 November 2026.',             '2026-10-24 08:00:00', 'pending',   0),
(108, 105, 'SMS',    'Welcome to NFSI. Your account is ready.',                                            '2026-08-15 11:10:00', 'failed',    0),
(109, 203, 'in-app', 'New session assigned: Food Handlers Refresher (Online) on 12 November 2026.',        '2026-10-12 09:00:00', 'delivered', 1),
(110, 111, 'email',  'Your enrollment in Practical Food Packaging is confirmed.',                          '2026-10-22 09:00:00', 'sent',      0),
(111, 112, 'SMS',    'Your Practical Food Packaging course starts on 25 November 2026.',                   '2026-10-22 09:15:00', 'delivered', 1),
(112, 113, 'email',  'Your enrollment is pending confirmation.',                                           '2026-10-23 10:00:00', 'sent',      0),
(113, 114, 'SMS',    'A payment of UGX 100,000 was received. Your balance is UGX 150,000.',               '2026-10-23 10:30:00', 'delivered', 0),
(114, 115, 'in-app', 'Your enrollment is active. Payment is still pending.',                               '2026-10-24 08:30:00', 'sent',      0)
ON DUPLICATE KEY UPDATE NotificationID = NotificationID;

-- Quick check: how many sample rows are there now?
SELECT 'useraccount' AS tbl, COUNT(*) AS rows_total FROM useraccount UNION ALL
SELECT 'staff', COUNT(*) FROM staff UNION ALL
SELECT 'trainee', COUNT(*) FROM trainee UNION ALL
SELECT 'course', COUNT(*) FROM course UNION ALL
SELECT 'trainingsession', COUNT(*) FROM trainingsession UNION ALL
SELECT 'enrollment', COUNT(*) FROM enrollment UNION ALL
SELECT 'payment', COUNT(*) FROM payment UNION ALL
SELECT 'attendance', COUNT(*) FROM attendance UNION ALL
SELECT 'certificate', COUNT(*) FROM certificate UNION ALL
SELECT 'notification', COUNT(*) FROM notification;