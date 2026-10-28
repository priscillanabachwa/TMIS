USE tmis_db;

SET @trainee_id = (
    SELECT TraineeID FROM Trainee
    WHERE Email = 'agnes.namusoke@example.com'
);

SET @trainer_id = (
    SELECT StaffID FROM Staff
    WHERE Email = 'james.ssekandi@example.com'
);

SET @admin_id = (
    SELECT StaffID FROM Staff
    WHERE Email = 'sarah.nalugemasarah@example.com'
);

SET @user_id = (
    SELECT UserID FROM Trainee
    WHERE TraineeID = @trainee_id
);

SET @enrollment_id = (
    SELECT e.EnrollmentID
    FROM Enrollment e
    JOIN Course c ON c.CourseID = e.CourseID
    WHERE e.TraineeID = @trainee_id
      AND c.CourseName = 'Basic Food Safety'
);

SET @course_id = (
    SELECT CourseID FROM Enrollment
    WHERE EnrollmentID = @enrollment_id
);

START TRANSACTION;

-- Make the demo enrollment earlier than its training sessions.
UPDATE Enrollment
SET EnrollmentDate = CURRENT_DATE - INTERVAL 10 DAY
WHERE EnrollmentID = @enrollment_id;

-- Move the existing session into the past.
UPDATE TrainingSession
SET SessionDate = CURRENT_DATE - INTERVAL 3 DAY,
    SessionStatus = 'completed'
WHERE CourseID = @course_id;

-- Add the other two days of this three-day course.
INSERT INTO TrainingSession (
    CourseID, TrainerID, SessionDate,
    StartTime, EndTime, VenuePlatform, SessionStatus
)
VALUES
(
    @course_id, @trainer_id,
    CURRENT_DATE - INTERVAL 2 DAY,
    '09:00:00', '12:00:00',
    'NFSI Training Room, Ntinda', 'completed'
),
(
    @course_id, @trainer_id,
    CURRENT_DATE - INTERVAL 1 DAY,
    '09:00:00', '12:00:00',
    'NFSI Training Room, Ntinda', 'completed'
);

-- Record attendance for the completed sessions.
INSERT INTO Attendance (
    SessionID, TraineeID, RecordedBy,
    AttendanceStatus, CheckInTime
)
SELECT
    SessionID,
    @trainee_id,
    @trainer_id,
    'present',
    TIMESTAMP(SessionDate, StartTime)
FROM TrainingSession
WHERE CourseID = @course_id
  AND SessionStatus = 'completed';

-- Demo assumption: all completion requirements have been met.
UPDATE Enrollment
SET EnrollmentStatus = 'completed'
WHERE EnrollmentID = @enrollment_id
  AND PaymentStatus = 'paid';

-- Issue only if the enrollment is completed and paid.
INSERT INTO Certificate (
    EnrollmentID, IssuedBy, IssueDate,
    SerialNumber, CertificateStatus
)
SELECT
    EnrollmentID,
    @admin_id,
    CURRENT_DATE,
    'DEMO-CERT-001',
    'issued'
FROM Enrollment
WHERE EnrollmentID = @enrollment_id
  AND EnrollmentStatus = 'completed'
  AND PaymentStatus = 'paid';

-- Notify the trainee only if the certificate exists.
INSERT INTO Notification (
    UserID, NotificationType,
    MessageContent, DeliveryStatus
)
SELECT
    @user_id,
    'in-app',
    'Your Basic Food Safety certificate has been issued.',
    'delivered'
FROM Certificate
WHERE EnrollmentID = @enrollment_id
  AND SerialNumber = 'DEMO-CERT-001';

COMMIT;