USE tmis_db;

-- Find the demo trainee's enrollments.
SET @safety_enrollment = (
    SELECT e.EnrollmentID
    FROM Enrollment e
    JOIN Trainee t ON t.TraineeID = e.TraineeID
    JOIN Course c ON c.CourseID = e.CourseID
    WHERE t.Email = 'agnes.namusoke@example.test'
      AND c.CourseName = 'Basic Food Safety'
);

SET @hygiene_enrollment = (
    SELECT e.EnrollmentID
    FROM Enrollment e
    JOIN Trainee t ON t.TraineeID = e.TraineeID
    JOIN Course c ON c.CourseID = e.CourseID
    WHERE t.Email = 'agnes.namusoke@example.test'
      AND c.CourseName = 'Food Hygiene'
);

SET @trainee_user = (
    SELECT UserID
    FROM Trainee
    WHERE Email = 'agnes.namusoke@example.test'
);

START TRANSACTION;

-- Food Safety: fully paid through two installments.
-- Food Hygiene: partially paid.
INSERT INTO Payment (
    EnrollmentID, AmountPaid, PaymentMethod,
    TransactionReference, PaymentStatus, InvoiceNumber
)
VALUES
(
    @safety_enrollment, 100000.00, 'mobile money',
    'DEMO-TXN-001', 'confirmed', 'DEMO-INV-001'
),
(
    @safety_enrollment, 50000.00, 'cash',
    'DEMO-TXN-002', 'confirmed', 'DEMO-INV-002'
),
(
    @hygiene_enrollment, 40000.00, 'bank transfer',
    'DEMO-TXN-003', 'confirmed', 'DEMO-INV-003'
);

-- Calculate payment status from confirmed payments.
UPDATE Enrollment e
JOIN Course c ON c.CourseID = e.CourseID
LEFT JOIN (
    SELECT EnrollmentID, SUM(AmountPaid) AS TotalPaid
    FROM Payment
    WHERE PaymentStatus = 'confirmed'
    GROUP BY EnrollmentID
) p ON p.EnrollmentID = e.EnrollmentID
SET e.PaymentStatus = CASE
    WHEN COALESCE(p.TotalPaid, 0) >= c.CourseFee THEN 'paid'
    WHEN COALESCE(p.TotalPaid, 0) > 0 THEN 'partially paid'
    ELSE 'pending'
END
WHERE e.EnrollmentID IN (@safety_enrollment, @hygiene_enrollment);

INSERT INTO Notification (
    UserID, NotificationType, MessageContent,
    DeliveryStatus, IsRead
)
VALUES
(
    @trainee_user, 'in-app',
    'Your Basic Food Safety enrollment is confirmed.',
    'delivered', FALSE
),
(
    @trainee_user, 'in-app',
    'Your Food Hygiene enrollment is confirmed.',
    'delivered', FALSE
),
(
    @trainee_user, 'in-app',
    'Payment of UGX 100,000 received for Basic Food Safety.',
    'delivered', FALSE
),
(
    @trainee_user, 'in-app',
    'Payment of UGX 50,000 received. Basic Food Safety is fully paid.',
    'delivered', FALSE
),
(
    @trainee_user, 'in-app',
    'Payment of UGX 40,000 received for Food Hygiene.',
    'delivered', FALSE
),
(
    @trainee_user, 'in-app',
    'Your Food Hygiene balance is UGX 60,000.',
    'delivered', FALSE
);

COMMIT;