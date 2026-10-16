-- =======================================================================
-- TRAINING MANAGEMENT INFORMATION SYSTEM (TMIS)
-- Coursework Module: System Reports & Analytical Views
-- Database: tmis_db
-- =======================================================================

USE tmis_db;

-- -----------------------------------------------------------------------
-- REPORT 1: Course Performance & Revenue Summary (Management Report)
-- Purpose: Evaluates course demand, capacity utilization rate, total revenue
--          collected vs. outstanding payments.
-- Stakeholder: Training Directors / Executive Management
-- -----------------------------------------------------------------------
CREATE OR REPLACE VIEW rpt_course_performance_summary AS
SELECT 
    c.CourseID,
    c.CourseName,
    c.Category,
    c.Duration,
    c.CourseFee,
    c.MaximumCapacity,
    COUNT(DISTINCT e.EnrollmentID) AS TotalEnrolled,
    ROUND((COUNT(DISTINCT e.EnrollmentID) / NULLIF(c.MaximumCapacity, 0)) * 100, 1) AS CapacityUtilizationPercent,
    COALESCE(SUM(p.AmountPaid), 0.00) AS TotalRevenueCollected,
    ((COUNT(DISTINCT e.EnrollmentID) * c.CourseFee) - COALESCE(SUM(p.AmountPaid), 0.00)) AS OutstandingBalance,
    c.CourseStatus
FROM Course c
LEFT JOIN Enrollment e 
    ON c.CourseID = e.CourseID AND e.EnrollmentStatus != 'cancelled'
LEFT JOIN Payment p 
    ON e.EnrollmentID = p.EnrollmentID AND p.PaymentStatus = 'confirmed'
GROUP BY 
    c.CourseID, c.CourseName, c.Category, c.Duration, 
    c.CourseFee, c.MaximumCapacity, c.CourseStatus;


-- -----------------------------------------------------------------------
-- REPORT 2: Trainee Attendance & Certificate Eligibility (Academic/Training Report)
-- Purpose: Assesses trainee attendance compliance (>=75%) and fee clearance
--          to determine qualification for certificate issuance.
-- Stakeholder: Academic Registrar / Lead Trainers
-- -----------------------------------------------------------------------
CREATE OR REPLACE VIEW rpt_trainee_attendance_eligibility AS
SELECT 
    t.TraineeID,
    t.FullName AS TraineeName,
    t.Email,
    c.CourseID,
    c.CourseName,
    e.EnrollmentID,
    e.EnrollmentStatus,
    e.PaymentStatus,
    COUNT(s.SessionID) AS TotalSessionsScheduled,
    SUM(CASE WHEN a.AttendanceStatus = 'present' THEN 1 ELSE 0 END) AS SessionsAttended,
    ROUND(
        (SUM(CASE WHEN a.AttendanceStatus = 'present' THEN 1 ELSE 0 END) / NULLIF(COUNT(s.SessionID), 0)) * 100, 1
    ) AS AttendancePercentage,
    CASE 
        WHEN (SUM(CASE WHEN a.AttendanceStatus = 'present' THEN 1 ELSE 0 END) / NULLIF(COUNT(s.SessionID), 0)) >= 0.75 
             AND e.PaymentStatus = 'paid' 
        THEN 'ELIGIBLE'
        WHEN (SUM(CASE WHEN a.AttendanceStatus = 'present' THEN 1 ELSE 0 END) / NULLIF(COUNT(s.SessionID), 0)) < 0.75 
             AND e.PaymentStatus = 'paid' 
        THEN 'INELIGIBLE (Low Attendance)'
        WHEN (SUM(CASE WHEN a.AttendanceStatus = 'present' THEN 1 ELSE 0 END) / NULLIF(COUNT(s.SessionID), 0)) >= 0.75 
             AND e.PaymentStatus != 'paid' 
        THEN 'INELIGIBLE (Pending Payment)'
        ELSE 'INELIGIBLE (Attendance & Payment Deficit)'
    END AS CertificationEligibility
FROM Enrollment e
JOIN Trainee t ON e.TraineeID = t.TraineeID
JOIN Course c ON e.CourseID = c.CourseID
JOIN TrainingSession s ON s.CourseID = c.CourseID
LEFT JOIN Attendance a ON a.SessionID = s.SessionID AND a.TraineeID = t.TraineeID
GROUP BY 
    t.TraineeID, t.FullName, t.Email, c.CourseID, c.CourseName, 
    e.EnrollmentID, e.EnrollmentStatus, e.PaymentStatus;


-- -----------------------------------------------------------------------
-- REPORT 3: Outstanding Debtor / Payment Default Report (Finance Report)
-- Purpose: Lists trainees with unpaid course fees, their balances, and
--          contact details for accounts receivables follow-up.
-- Stakeholder: Finance & Accounts Department
-- -----------------------------------------------------------------------
CREATE OR REPLACE VIEW rpt_outstanding_debtors AS
SELECT 
    t.TraineeID,
    t.FullName AS TraineeName,
    t.PhoneNo,
    t.Email,
    t.Organization,
    c.CourseName,
    c.CourseFee,
    COALESCE(SUM(p.AmountPaid), 0.00) AS TotalAmountPaid,
    (c.CourseFee - COALESCE(SUM(p.AmountPaid), 0.00)) AS BalanceDue,
    e.EnrollmentDate,
    e.PaymentStatus
FROM Enrollment e
JOIN Trainee t ON e.TraineeID = t.TraineeID
JOIN Course c ON e.CourseID = c.CourseID
LEFT JOIN Payment p ON e.EnrollmentID = p.EnrollmentID AND p.PaymentStatus = 'confirmed'
WHERE e.PaymentStatus IN ('pending', 'partially paid')
GROUP BY 
    e.EnrollmentID, t.TraineeID, t.FullName, t.PhoneNo, t.Email, 
    t.Organization, c.CourseName, c.CourseFee, e.EnrollmentDate, e.PaymentStatus
HAVING BalanceDue > 0;


-- -----------------------------------------------------------------------
-- REPORT 4: Trainer Workload & Activity Analysis (HR / Operations Report)
-- Purpose: Analyzes trainer allocation across courses, sessions conducted,
--          and upcoming training commitments.
-- Stakeholder: Human Resources / Training Operations Coordinator
-- -----------------------------------------------------------------------
CREATE OR REPLACE VIEW rpt_trainer_workload AS
SELECT 
    st.StaffID,
    st.FullName AS TrainerName,
    st.Department,
    st.Email,
    COUNT(ts.SessionID) AS TotalSessionsAssigned,
    SUM(CASE WHEN ts.SessionStatus = 'completed' THEN 1 ELSE 0 END) AS CompletedSessions,
    SUM(CASE WHEN ts.SessionStatus = 'scheduled' THEN 1 ELSE 0 END) AS UpcomingSessions,
    COUNT(DISTINCT ts.CourseID) AS DistinctCoursesTaught
FROM Staff st
LEFT JOIN TrainingSession ts ON st.StaffID = ts.TrainerID
WHERE st.Role = 'trainer'
GROUP BY st.StaffID, st.FullName, st.Department, st.Email;


-- -----------------------------------------------------------------------
-- REPORT 5: Session Attendance Register (Daily Operational Sheet)
-- Purpose: Provides a roll call roster for a specific scheduled training session,
--          including contact details and real-time check-in logs.
-- Stakeholder: Assigned Trainer / Classroom Supervisor
-- -----------------------------------------------------------------------
CREATE OR REPLACE VIEW rpt_session_attendance_register AS
SELECT 
    s.SessionID,
    c.CourseName,
    s.SessionDate,
    s.StartTime,
    s.EndTime,
    s.VenuePlatform,
    t.TraineeID,
    t.FullName AS TraineeName,
    t.NIN,
    t.PhoneNo,
    COALESCE(a.AttendanceStatus, 'not recorded') AS AttendanceStatus,
    a.CheckInTime
FROM TrainingSession s
JOIN Course c ON s.CourseID = c.CourseID
JOIN Enrollment e ON e.CourseID = c.CourseID AND e.EnrollmentStatus IN ('active', 'completed')
JOIN Trainee t ON t.TraineeID = e.TraineeID
LEFT JOIN Attendance a ON a.SessionID = s.SessionID AND a.TraineeID = t.TraineeID;


-- -----------------------------------------------------------------------
-- REPORT 6: Verified Certificate Dispatch (Official Records Document)
-- Purpose: Renders verified credential details for printing certificates
--          with trace serial numbers and issuing officer signatures.
-- Stakeholder: Trainees, Verification Bodies, Quality Assurance
-- -----------------------------------------------------------------------
CREATE OR REPLACE VIEW rpt_certificate_dispatch AS
SELECT 
    cert.CertificateID,
    cert.SerialNumber,
    cert.IssueDate,
    cert.CertificateStatus,
    t.FullName AS TraineeName,
    t.NIN,
    t.Organization,
    c.CourseName,
    c.Duration,
    c.Category,
    st.FullName AS IssuedByOfficer,
    st.Role AS OfficerRole
FROM Certificate cert
JOIN Enrollment e ON cert.EnrollmentID = e.EnrollmentID
JOIN Trainee t ON e.TraineeID = t.TraineeID
JOIN Course c ON e.CourseID = c.CourseID
JOIN Staff st ON cert.IssuedBy = st.StaffID;


-- =======================================================================
-- VERIFICATION QUERIES
-- Run these statements to preview each report's dataset
-- =======================================================================
SELECT * FROM rpt_course_performance_summary;
SELECT * FROM rpt_trainee_attendance_eligibility;
SELECT * FROM rpt_outstanding_debtors;
SELECT * FROM rpt_trainer_workload;
SELECT * FROM rpt_session_attendance_register WHERE SessionDate = CURRENT_DATE - INTERVAL 3 DAY;
SELECT * FROM rpt_certificate_dispatch;

