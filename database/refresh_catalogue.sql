-- Run after the existing seed scripts, including seed_sample.sql.
-- Fictional named profiles; these do not represent verified real people.
-- Only known placeholder profiles and explicitly identified sample rows change.
USE tmis_db;
START TRANSACTION;

UPDATE UserAccount SET Username='namusokeagnes' WHERE Username='demo_trainee';
UPDATE UserAccount SET Username='ssekandijames' WHERE Username='demo_trainer';
UPDATE UserAccount SET Username='nalugemasarah' WHERE Username='demo_admin';
UPDATE Trainee SET FullName='Namusoke Agnes', Email='agnes.namusoke@example.test',
    Organization='Central Food Processors' WHERE FullName='Demo Trainee';
UPDATE Staff SET FullName='Ssekandi James', Email='james.ssekandi@example.test'
    WHERE FullName='Demo Trainer';
UPDATE Staff SET FullName='Nalugema Sarah', Email='sarah.nalugemasarah@example.test'
    WHERE FullName='Demo Administrator';

-- Natural keys make catalogue expansion safe to repeat without overwriting courses.
INSERT INTO Course (CourseName, Description, Category, Duration, ModeOfDelivery,
    CourseFee, CourseStatus, Prerequisites, MaximumCapacity)
SELECT n.name, n.description, n.category, n.duration, n.mode, n.fee, n.status, NULL, n.capacity
FROM (
SELECT 'Cold Chain Management' name, 'Temperature monitoring, transport and cold storage controls.' description, 'Food Safety' category, '3 days' duration, 'hybrid' mode, 220000 fee, 'active' status, 25 capacity
UNION ALL SELECT 'Allergen Management', 'Prevent allergen cross-contact and manage declarations.', 'Food Safety', '2 days', 'physical', 160000, 'active', 30
UNION ALL SELECT 'Food Traceability and Recall', 'Build traceability records and practise product recalls.', 'Quality Assurance', '3 days', 'hybrid', 240000, 'active', 24
UNION ALL SELECT 'ISO 22000 Implementation', 'Develop and maintain food safety management systems.', 'Management Systems', '5 days', 'physical', 650000, 'active', 20
UNION ALL SELECT 'Food Microbiology Essentials', 'Understand pathogens, sampling and laboratory results.', 'Laboratory Skills', '4 days', 'physical', 380000, 'active', 18
UNION ALL SELECT 'Water Quality and Sanitation', 'Monitor process water and verify sanitation practices.', 'Food Safety', '2 days', 'hybrid', 175000, 'inactive', 25
) n
WHERE NOT EXISTS (SELECT 1 FROM Course c WHERE c.CourseName=n.name);

-- Fill missing lifecycle examples without changing confirmed payment totals.
UPDATE UserAccount SET AccountStatus='suspended' WHERE UserID=205 AND Username='tumusiimealex';
UPDATE Staff SET StaffStatus='archived' WHERE StaffID=105 AND FullName='Tumusiime Alex';
UPDATE Trainee SET TraineeStatus='archived' WHERE TraineeID=109 AND NIN='SAMPLE-NIN-109';
UPDATE TrainingSession SET SessionStatus='cancelled' WHERE SessionID=113 AND VenuePlatform='Online (Microsoft Teams)';
UPDATE Attendance SET AttendanceStatus='late' WHERE SessionID=101 AND TraineeID=103 AND CheckInTime IS NOT NULL;
UPDATE Attendance SET AttendanceStatus='excused' WHERE SessionID=105 AND TraineeID=106 AND CheckInTime IS NULL;
UPDATE Certificate SET CertificateStatus='revoked' WHERE SerialNumber='SAMPLE-CERT-102';
UPDATE Certificate SET CertificateStatus='replaced' WHERE SerialNumber='SAMPLE-CERT-104';

INSERT INTO Payment (EnrollmentID, AmountPaid, PaymentDate, PaymentMethod,
    TransactionReference, PaymentStatus, InvoiceNumber)
SELECT e.EnrollmentID, 25000, '2026-10-24 10:00:00', 'mobile money',
    CONCAT('SAMPLE-LIFECYCLE-', n.status), n.status, CONCAT('SAMPLE-LIFECYCLE-INV-', n.status)
FROM Enrollment e JOIN Trainee t ON t.TraineeID=e.TraineeID
CROSS JOIN (SELECT 'pending' status UNION ALL SELECT 'failed' UNION ALL SELECT 'reversed') n
WHERE e.EnrollmentID=118 AND t.NIN='SAMPLE-NIN-115'
AND NOT EXISTS (SELECT 1 FROM Payment p WHERE p.TransactionReference=CONCAT('SAMPLE-LIFECYCLE-', n.status));
COMMIT;
