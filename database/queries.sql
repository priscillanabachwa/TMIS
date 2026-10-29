USE tmis_db;

-- =====================================================================
-- SECTION 1: VIEWS (no input needed, read with a plain SELECT)
-- =====================================================================

CREATE OR REPLACE VIEW v_enrollment_details AS
SELECT e.EnrollmentID, t.TraineeID, t.FullName AS Trainee, c.CourseID,
       c.CourseName, e.EnrollmentDate, e.EnrollmentStatus, e.PaymentStatus
FROM Enrollment e
JOIN Trainee t ON t.TraineeID = e.TraineeID
JOIN Course  c ON c.CourseID  = e.CourseID;

CREATE OR REPLACE VIEW v_enrollment_balance AS
SELECT e.EnrollmentID, e.TraineeID, t.FullName AS Trainee, c.CourseName, c.CourseFee,
       COALESCE(SUM(CASE WHEN p.PaymentStatus = 'confirmed' THEN p.AmountPaid END), 0) AS TotalPaid,
       c.CourseFee - COALESCE(SUM(CASE WHEN p.PaymentStatus = 'confirmed' THEN p.AmountPaid END), 0) AS Balance
FROM Enrollment e
JOIN Trainee t ON t.TraineeID = e.TraineeID
JOIN Course  c ON c.CourseID  = e.CourseID
LEFT JOIN Payment p ON p.EnrollmentID = e.EnrollmentID
GROUP BY e.EnrollmentID, e.TraineeID, t.FullName, c.CourseName, c.CourseFee;

CREATE OR REPLACE VIEW v_course_summary AS
SELECT c.CourseID, c.CourseName, c.CourseStatus, c.MaximumCapacity,
       COUNT(CASE WHEN e.EnrollmentStatus IN ('pending','active','completed') THEN 1 END) AS Enrolled,
       c.MaximumCapacity - COUNT(CASE WHEN e.EnrollmentStatus IN ('pending','active','completed') THEN 1 END) AS SeatsLeft,
       COALESCE(SUM(e.EnrollmentStatus = 'completed'), 0) AS Completed
FROM Course c
LEFT JOIN Enrollment e ON e.CourseID = c.CourseID
GROUP BY c.CourseID, c.CourseName, c.CourseStatus, c.MaximumCapacity;

CREATE OR REPLACE VIEW v_session_schedule AS
SELECT s.SessionID, s.CourseID, c.CourseName, s.TrainerID, st.FullName AS Trainer,
       s.SessionDate, s.StartTime, s.EndTime, s.VenuePlatform, s.SessionStatus
FROM TrainingSession s
JOIN Course c  ON c.CourseID = s.CourseID
JOIN Staff  st ON st.StaffID = s.TrainerID;

CREATE OR REPLACE VIEW v_certificate_register AS
SELECT ct.CertificateID, ct.SerialNumber, t.FullName AS Trainee, c.CourseName,
       ct.IssueDate, ct.CertificateStatus, st.FullName AS IssuedBy
FROM Certificate ct
JOIN Enrollment e ON e.EnrollmentID = ct.EnrollmentID
JOIN Trainee t    ON t.TraineeID = e.TraineeID
JOIN Course c     ON c.CourseID = e.CourseID
JOIN Staff st     ON st.StaffID = ct.IssuedBy;

CREATE OR REPLACE VIEW v_dashboard AS
SELECT
  (SELECT COUNT(*) FROM Trainee WHERE TraineeStatus = 'active')                                        AS ActiveTrainees,
  (SELECT COUNT(*) FROM Course WHERE CourseStatus = 'active')                                          AS ActiveCourses,
  (SELECT COUNT(*) FROM Enrollment WHERE EnrollmentStatus IN ('pending','active'))                     AS OpenEnrollments,
  (SELECT COUNT(*) FROM TrainingSession WHERE SessionStatus = 'scheduled' AND SessionDate >= CURDATE()) AS UpcomingSessions,
  (SELECT COALESCE(SUM(AmountPaid), 0) FROM Payment WHERE PaymentStatus = 'confirmed')                 AS TotalRevenue,
  (SELECT COUNT(*) FROM Certificate WHERE CertificateStatus = 'issued')                                AS CertificatesIssued;

DELIMITER $$

-- =====================================================================
-- SECTION 2: USER ACCOUNTS AND LOGIN
-- =====================================================================

-- Fetch an account by username so the app can verify the password hash
DROP PROCEDURE IF EXISTS sp_login_lookup$$
CREATE PROCEDURE sp_login_lookup(IN p_username VARCHAR(50))
BEGIN
    SELECT u.UserID, u.Username, u.PasswordHash, u.Role, u.AccountStatus,
           COALESCE(t.TraineeID, s.StaffID) AS ProfileID,
           COALESCE(t.FullName, s.FullName) AS FullName
    FROM UserAccount u
    LEFT JOIN Trainee t ON t.UserID = u.UserID
    LEFT JOIN Staff   s ON s.UserID = u.UserID
    WHERE u.Username = p_username;
END$$

-- Stamp the last successful login
DROP PROCEDURE IF EXISTS sp_record_login$$
CREATE PROCEDURE sp_record_login(IN p_user_id INT)
BEGIN
    UPDATE UserAccount SET LastLogin = NOW() WHERE UserID = p_user_id;
END$$

-- Replace a password hash (the app hashes the password before calling)
DROP PROCEDURE IF EXISTS sp_change_password$$
CREATE PROCEDURE sp_change_password(IN p_user_id INT, IN p_password_hash VARCHAR(255))
BEGIN
    UPDATE UserAccount SET PasswordHash = p_password_hash WHERE UserID = p_user_id;
END$$

-- Activate, deactivate or suspend an account
DROP PROCEDURE IF EXISTS sp_set_account_status$$
CREATE PROCEDURE sp_set_account_status(IN p_user_id INT, IN p_status VARCHAR(20))
BEGIN
    UPDATE UserAccount SET AccountStatus = p_status WHERE UserID = p_user_id;
END$$

-- List accounts, every filter optional (pass NULL to ignore it)
DROP PROCEDURE IF EXISTS sp_list_users$$
CREATE PROCEDURE sp_list_users(IN p_role VARCHAR(20), IN p_status VARCHAR(20), IN p_search VARCHAR(100))
BEGIN
    SELECT u.UserID, u.Username, u.Role, u.AccountStatus, u.CreatedAt, u.LastLogin,
           COALESCE(t.FullName, s.FullName) AS FullName
    FROM UserAccount u
    LEFT JOIN Trainee t ON t.UserID = u.UserID
    LEFT JOIN Staff   s ON s.UserID = u.UserID
    WHERE (p_role   IS NULL OR u.Role = p_role)
      AND (p_status IS NULL OR u.AccountStatus = p_status)
      AND (p_search IS NULL OR u.Username LIKE CONCAT('%', p_search, '%')
                            OR COALESCE(t.FullName, s.FullName) LIKE CONCAT('%', p_search, '%'))
    ORDER BY u.UserID;
END$$

-- =====================================================================
-- SECTION 3: TRAINEES
-- =====================================================================

-- Register a trainee: creates the account and the profile together
DROP PROCEDURE IF EXISTS sp_register_trainee$$
CREATE PROCEDURE sp_register_trainee(
    IN p_username VARCHAR(50), IN p_password_hash VARCHAR(255),
    IN p_full_name VARCHAR(150), IN p_date_of_birth DATE, IN p_gender VARCHAR(20),
    IN p_nin VARCHAR(20), IN p_phone VARCHAR(20), IN p_email VARCHAR(150),
    IN p_organization VARCHAR(150), IN p_address VARCHAR(255))
BEGIN
    DECLARE v_user_id INT;
    DECLARE v_trainee_id INT;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;
    INSERT INTO UserAccount (Username, PasswordHash, Role)
    VALUES (p_username, p_password_hash, 'trainee');
    SET v_user_id = LAST_INSERT_ID();

    INSERT INTO Trainee (UserID, FullName, DateOfBirth, Gender, NIN, PhoneNo, Email,
                         Organization, Address, RegistrationDate)
    VALUES (v_user_id, p_full_name, p_date_of_birth, p_gender, p_nin, p_phone, p_email,
            NULLIF(p_organization, ''), NULLIF(p_address, ''), CURDATE());
    SET v_trainee_id = LAST_INSERT_ID();
    COMMIT;

    SELECT v_user_id AS UserID, v_trainee_id AS TraineeID;
END$$

-- Update a trainee's contact details (NULL or empty keeps the old value)
DROP PROCEDURE IF EXISTS sp_update_trainee$$
CREATE PROCEDURE sp_update_trainee(
    IN p_trainee_id INT, IN p_full_name VARCHAR(150), IN p_phone VARCHAR(20),
    IN p_email VARCHAR(150), IN p_organization VARCHAR(150), IN p_address VARCHAR(255))
BEGIN
    UPDATE Trainee
    SET FullName     = COALESCE(NULLIF(p_full_name, ''), FullName),
        PhoneNo      = COALESCE(NULLIF(p_phone, ''), PhoneNo),
        Email        = COALESCE(NULLIF(p_email, ''), Email),
        Organization = COALESCE(NULLIF(p_organization, ''), Organization),
        Address      = COALESCE(NULLIF(p_address, ''), Address)
    WHERE TraineeID = p_trainee_id;
END$$

-- Activate, deactivate or archive a trainee (records are archived, never deleted)
DROP PROCEDURE IF EXISTS sp_set_trainee_status$$
CREATE PROCEDURE sp_set_trainee_status(IN p_trainee_id INT, IN p_status VARCHAR(20))
BEGIN
    UPDATE Trainee SET TraineeStatus = p_status WHERE TraineeID = p_trainee_id;
END$$

-- Search trainees, every filter optional
DROP PROCEDURE IF EXISTS sp_search_trainees$$
CREATE PROCEDURE sp_search_trainees(
    IN p_search VARCHAR(100), IN p_status VARCHAR(20),
    IN p_organization VARCHAR(150), IN p_gender VARCHAR(20))
BEGIN
    SELECT t.TraineeID, t.FullName, t.Gender, t.DateOfBirth,
           TIMESTAMPDIFF(YEAR, t.DateOfBirth, CURDATE()) AS Age,
           t.NIN, t.PhoneNo, t.Email, t.Organization, t.Address,
           t.RegistrationDate, t.TraineeStatus, t.UserID
    FROM Trainee t
    WHERE (p_search IS NULL OR t.FullName LIKE CONCAT('%', p_search, '%')
                            OR t.NIN = p_search
                            OR t.Email LIKE CONCAT('%', p_search, '%')
                            OR t.PhoneNo LIKE CONCAT('%', p_search, '%'))
      AND (p_status       IS NULL OR t.TraineeStatus = p_status)
      AND (p_organization IS NULL OR t.Organization LIKE CONCAT('%', p_organization, '%'))
      AND (p_gender       IS NULL OR t.Gender = p_gender)
    ORDER BY t.FullName;
END$$

-- Everything one trainee has done: courses, status, payments, certificate
DROP PROCEDURE IF EXISTS sp_trainee_history$$
CREATE PROCEDURE sp_trainee_history(IN p_trainee_id INT)
BEGIN
    SELECT e.EnrollmentID, c.CourseName, e.EnrollmentDate, e.EnrollmentStatus,
           e.PaymentStatus, c.CourseFee,
           COALESCE(SUM(CASE WHEN p.PaymentStatus = 'confirmed' THEN p.AmountPaid END), 0) AS TotalPaid,
           ct.SerialNumber AS CertificateSerial, ct.CertificateStatus
    FROM Enrollment e
    JOIN Course c            ON c.CourseID = e.CourseID
    LEFT JOIN Payment p      ON p.EnrollmentID = e.EnrollmentID
    LEFT JOIN Certificate ct ON ct.EnrollmentID = e.EnrollmentID
    WHERE e.TraineeID = p_trainee_id
    GROUP BY e.EnrollmentID, c.CourseName, e.EnrollmentDate, e.EnrollmentStatus,
             e.PaymentStatus, c.CourseFee, ct.SerialNumber, ct.CertificateStatus
    ORDER BY e.EnrollmentDate DESC;
END$$

-- =====================================================================
-- SECTION 4: STAFF
-- =====================================================================

-- Register a staff member: creates the account and the profile together
DROP PROCEDURE IF EXISTS sp_register_staff$$
CREATE PROCEDURE sp_register_staff(
    IN p_username VARCHAR(50), IN p_password_hash VARCHAR(255),
    IN p_full_name VARCHAR(150), IN p_role VARCHAR(20), IN p_email VARCHAR(150),
    IN p_phone VARCHAR(20), IN p_department VARCHAR(100))
BEGIN
    DECLARE v_user_id INT;
    DECLARE v_staff_id INT;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;
    INSERT INTO UserAccount (Username, PasswordHash, Role)
    VALUES (p_username, p_password_hash, p_role);
    SET v_user_id = LAST_INSERT_ID();

    INSERT INTO Staff (UserID, FullName, Role, Email, PhoneNo, Department)
    VALUES (v_user_id, p_full_name, p_role, p_email, NULLIF(p_phone, ''), p_department);
    SET v_staff_id = LAST_INSERT_ID();
    COMMIT;

    SELECT v_user_id AS UserID, v_staff_id AS StaffID;
END$$

-- Update staff contact details (NULL or empty keeps the old value)
DROP PROCEDURE IF EXISTS sp_update_staff$$
CREATE PROCEDURE sp_update_staff(
    IN p_staff_id INT, IN p_full_name VARCHAR(150), IN p_email VARCHAR(150),
    IN p_phone VARCHAR(20), IN p_department VARCHAR(100))
BEGIN
    UPDATE Staff
    SET FullName   = COALESCE(NULLIF(p_full_name, ''), FullName),
        Email      = COALESCE(NULLIF(p_email, ''), Email),
        PhoneNo    = COALESCE(NULLIF(p_phone, ''), PhoneNo),
        Department = COALESCE(NULLIF(p_department, ''), Department)
    WHERE StaffID = p_staff_id;
END$$

-- Activate, deactivate or archive a staff member
DROP PROCEDURE IF EXISTS sp_set_staff_status$$
CREATE PROCEDURE sp_set_staff_status(IN p_staff_id INT, IN p_status VARCHAR(20))
BEGIN
    UPDATE Staff SET StaffStatus = p_status WHERE StaffID = p_staff_id;
END$$

-- List staff, every filter optional
DROP PROCEDURE IF EXISTS sp_list_staff$$
CREATE PROCEDURE sp_list_staff(IN p_role VARCHAR(20), IN p_department VARCHAR(100),
                               IN p_status VARCHAR(20), IN p_search VARCHAR(100))
BEGIN
    SELECT StaffID, FullName, Role, Email, PhoneNo, Department, StaffStatus, DateJoined, UserID
    FROM Staff
    WHERE (p_role       IS NULL OR Role = p_role)
      AND (p_department IS NULL OR Department = p_department)
      AND (p_status     IS NULL OR StaffStatus = p_status)
      AND (p_search     IS NULL OR FullName LIKE CONCAT('%', p_search, '%')
                                OR Email LIKE CONCAT('%', p_search, '%'))
    ORDER BY FullName;
END$$

-- Sessions per trainer within an optional date range
DROP PROCEDURE IF EXISTS sp_trainer_workload$$
CREATE PROCEDURE sp_trainer_workload(IN p_from DATE, IN p_to DATE)
BEGIN
    SELECT s.StaffID, s.FullName,
           COUNT(ts.SessionID) AS TotalSessions,
           COALESCE(SUM(ts.SessionStatus = 'completed'), 0) AS Completed,
           COALESCE(SUM(ts.SessionStatus = 'scheduled'), 0) AS Upcoming,
           COALESCE(SUM(ts.SessionStatus = 'cancelled'), 0) AS Cancelled
    FROM Staff s
    LEFT JOIN TrainingSession ts
           ON ts.TrainerID = s.StaffID
          AND (p_from IS NULL OR ts.SessionDate >= p_from)
          AND (p_to   IS NULL OR ts.SessionDate <= p_to)
    WHERE s.Role = 'trainer'
    GROUP BY s.StaffID, s.FullName
    ORDER BY TotalSessions DESC;
END$$

-- =====================================================================
-- SECTION 5: COURSES
-- =====================================================================

-- Create a course
DROP PROCEDURE IF EXISTS sp_add_course$$
CREATE PROCEDURE sp_add_course(
    IN p_name VARCHAR(150), IN p_description TEXT, IN p_category VARCHAR(100),
    IN p_duration VARCHAR(50), IN p_mode VARCHAR(20), IN p_fee DECIMAL(12,2),
    IN p_prerequisites TEXT, IN p_capacity INT)
BEGIN
    INSERT INTO Course (CourseName, Description, Category, Duration, ModeOfDelivery,
                        CourseFee, Prerequisites, MaximumCapacity)
    VALUES (p_name, NULLIF(p_description, ''), p_category, p_duration, p_mode,
            p_fee, NULLIF(p_prerequisites, ''), p_capacity);
    SELECT LAST_INSERT_ID() AS CourseID;
END$$

-- Update a course (NULL or empty keeps the old value)
DROP PROCEDURE IF EXISTS sp_update_course$$
CREATE PROCEDURE sp_update_course(
    IN p_course_id INT, IN p_name VARCHAR(150), IN p_description TEXT,
    IN p_category VARCHAR(100), IN p_duration VARCHAR(50), IN p_mode VARCHAR(20),
    IN p_fee DECIMAL(12,2), IN p_prerequisites TEXT, IN p_capacity INT)
BEGIN
    UPDATE Course
    SET CourseName      = COALESCE(NULLIF(p_name, ''), CourseName),
        Description     = COALESCE(NULLIF(p_description, ''), Description),
        Category        = COALESCE(NULLIF(p_category, ''), Category),
        Duration        = COALESCE(NULLIF(p_duration, ''), Duration),
        ModeOfDelivery  = COALESCE(NULLIF(p_mode, ''), ModeOfDelivery),
        CourseFee       = COALESCE(p_fee, CourseFee),
        Prerequisites   = COALESCE(NULLIF(p_prerequisites, ''), Prerequisites),
        MaximumCapacity = COALESCE(p_capacity, MaximumCapacity)
    WHERE CourseID = p_course_id;
END$$

-- Activate, deactivate or archive a course
DROP PROCEDURE IF EXISTS sp_set_course_status$$
CREATE PROCEDURE sp_set_course_status(IN p_course_id INT, IN p_status VARCHAR(20))
BEGIN
    UPDATE Course SET CourseStatus = p_status WHERE CourseID = p_course_id;
END$$

-- Search courses with seats left, every filter optional
DROP PROCEDURE IF EXISTS sp_search_courses$$
CREATE PROCEDURE sp_search_courses(
    IN p_search VARCHAR(100), IN p_category VARCHAR(100), IN p_mode VARCHAR(20),
    IN p_status VARCHAR(20), IN p_max_fee DECIMAL(12,2), IN p_only_available TINYINT)
BEGIN
    SELECT c.CourseID, c.CourseName, c.Category, c.Duration, c.ModeOfDelivery,
           c.CourseFee, c.CourseStatus, c.Prerequisites, c.MaximumCapacity,
           COUNT(CASE WHEN e.EnrollmentStatus IN ('pending','active','completed') THEN 1 END) AS Enrolled,
           c.MaximumCapacity
             - COUNT(CASE WHEN e.EnrollmentStatus IN ('pending','active','completed') THEN 1 END) AS SeatsLeft
    FROM Course c
    LEFT JOIN Enrollment e ON e.CourseID = c.CourseID
    WHERE (p_search   IS NULL OR c.CourseName LIKE CONCAT('%', p_search, '%')
                              OR c.Description LIKE CONCAT('%', p_search, '%'))
      AND (p_category IS NULL OR c.Category = p_category)
      AND (p_mode     IS NULL OR c.ModeOfDelivery = p_mode)
      AND (p_status   IS NULL OR c.CourseStatus = p_status)
      AND (p_max_fee  IS NULL OR c.CourseFee <= p_max_fee)
    GROUP BY c.CourseID, c.CourseName, c.Category, c.Duration, c.ModeOfDelivery,
             c.CourseFee, c.CourseStatus, c.Prerequisites, c.MaximumCapacity
    HAVING COALESCE(p_only_available, 0) = 0 OR SeatsLeft > 0
    ORDER BY c.Category, c.CourseName;
END$$

-- Class list for a course, optionally filtered by enrollment status
DROP PROCEDURE IF EXISTS sp_class_list$$
CREATE PROCEDURE sp_class_list(IN p_course_id INT, IN p_status VARCHAR(20))
BEGIN
    SELECT t.TraineeID, t.FullName, t.PhoneNo, t.Email, t.Organization,
           e.EnrollmentID, e.EnrollmentStatus, e.PaymentStatus
    FROM Enrollment e
    JOIN Trainee t ON t.TraineeID = e.TraineeID
    WHERE e.CourseID = p_course_id
      AND (p_status IS NULL OR e.EnrollmentStatus = p_status)
    ORDER BY t.FullName;
END$$

-- =====================================================================
-- SECTION 6: ENROLLMENTS
-- =====================================================================

-- Enroll a trainee in a course (course row is locked so capacity cannot be overbooked)
DROP PROCEDURE IF EXISTS sp_enroll_trainee$$
CREATE PROCEDURE sp_enroll_trainee(IN p_trainee_id INT, IN p_course_id INT)
BEGIN
    DECLARE v_course INT DEFAULT NULL;
    DECLARE v_enrollment_id INT;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;
    SELECT CourseID INTO v_course FROM Course WHERE CourseID = p_course_id FOR UPDATE;
    IF v_course IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Course not found';
    END IF;

    INSERT INTO Enrollment (TraineeID, CourseID) VALUES (p_trainee_id, p_course_id);
    SET v_enrollment_id = LAST_INSERT_ID();

    INSERT INTO Notification (UserID, NotificationType, MessageContent)
    SELECT t.UserID, 'in-app',
           CONCAT('Registration confirmed for ', c.CourseName, '.')
    FROM Trainee t, Course c
    WHERE t.TraineeID = p_trainee_id AND c.CourseID = p_course_id;
    COMMIT;

    SELECT v_enrollment_id AS EnrollmentID;
END$$

-- Cancel, withdraw, activate or reset an enrollment (completion has its own procedure)
DROP PROCEDURE IF EXISTS sp_set_enrollment_status$$
CREATE PROCEDURE sp_set_enrollment_status(IN p_enrollment_id INT, IN p_status VARCHAR(20))
BEGIN
    IF p_status = 'completed' THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Use sp_complete_enrollment to mark an enrollment completed';
    END IF;
    UPDATE Enrollment SET EnrollmentStatus = p_status WHERE EnrollmentID = p_enrollment_id;
END$$

-- Mark an enrollment completed only when attendance meets the minimum percentage
DROP PROCEDURE IF EXISTS sp_complete_enrollment$$
CREATE PROCEDURE sp_complete_enrollment(IN p_enrollment_id INT, IN p_min_attendance_pct DECIMAL(5,2))
BEGIN
    DECLARE v_course INT DEFAULT NULL;
    DECLARE v_trainee INT;
    DECLARE v_status VARCHAR(20);
    DECLARE v_pct DECIMAL(6,2);

    SELECT CourseID, TraineeID, EnrollmentStatus
      INTO v_course, v_trainee, v_status
    FROM Enrollment WHERE EnrollmentID = p_enrollment_id;

    IF v_course IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Enrollment not found';
    END IF;
    IF v_status <> 'active' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Only an active enrollment can be completed';
    END IF;

    SELECT 100 * COUNT(CASE WHEN a.AttendanceStatus IN ('present','late') THEN 1 END)
                / NULLIF(COUNT(s.SessionID), 0)
      INTO v_pct
    FROM TrainingSession s
    LEFT JOIN Attendance a ON a.SessionID = s.SessionID AND a.TraineeID = v_trainee
    WHERE s.CourseID = v_course AND s.SessionStatus = 'completed';

    IF v_pct IS NULL OR v_pct < COALESCE(p_min_attendance_pct, 0) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Attendance requirement not met';
    END IF;

    UPDATE Enrollment SET EnrollmentStatus = 'completed' WHERE EnrollmentID = p_enrollment_id;
    SELECT p_enrollment_id AS EnrollmentID, v_pct AS AttendancePct;
END$$

-- Search enrollments, every filter optional
DROP PROCEDURE IF EXISTS sp_search_enrollments$$
CREATE PROCEDURE sp_search_enrollments(
    IN p_trainee_id INT, IN p_course_id INT, IN p_status VARCHAR(20),
    IN p_payment_status VARCHAR(20), IN p_from DATE, IN p_to DATE, IN p_search VARCHAR(100))
BEGIN
    SELECT e.EnrollmentID, t.TraineeID, t.FullName, t.PhoneNo, c.CourseID, c.CourseName,
           e.EnrollmentDate, e.EnrollmentStatus, e.PaymentStatus
    FROM Enrollment e
    JOIN Trainee t ON t.TraineeID = e.TraineeID
    JOIN Course  c ON c.CourseID  = e.CourseID
    WHERE (p_trainee_id    IS NULL OR e.TraineeID = p_trainee_id)
      AND (p_course_id     IS NULL OR e.CourseID = p_course_id)
      AND (p_status        IS NULL OR e.EnrollmentStatus = p_status)
      AND (p_payment_status IS NULL OR e.PaymentStatus = p_payment_status)
      AND (p_from          IS NULL OR e.EnrollmentDate >= p_from)
      AND (p_to            IS NULL OR e.EnrollmentDate <= p_to)
      AND (p_search        IS NULL OR t.FullName LIKE CONCAT('%', p_search, '%')
                                   OR c.CourseName LIKE CONCAT('%', p_search, '%'))
    ORDER BY e.EnrollmentDate DESC, e.EnrollmentID DESC;
END$$

-- =====================================================================
-- SECTION 7: TRAINING SESSIONS
-- =====================================================================

-- Schedule a session (trainer must be free at that time)
DROP PROCEDURE IF EXISTS sp_schedule_session$$
CREATE PROCEDURE sp_schedule_session(
    IN p_course_id INT, IN p_trainer_id INT, IN p_date DATE,
    IN p_start TIME, IN p_end TIME, IN p_venue VARCHAR(255))
BEGIN
    IF EXISTS (SELECT 1 FROM TrainingSession
               WHERE TrainerID = p_trainer_id AND SessionDate = p_date
                 AND SessionStatus <> 'cancelled'
                 AND StartTime < p_end AND p_start < EndTime) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Trainer already has a session at that time';
    END IF;

    INSERT INTO TrainingSession (CourseID, TrainerID, SessionDate, StartTime, EndTime, VenuePlatform)
    VALUES (p_course_id, p_trainer_id, p_date, p_start, p_end, p_venue);
    SELECT LAST_INSERT_ID() AS SessionID;
END$$

-- Reschedule or reassign a session (NULL keeps the old value)
DROP PROCEDURE IF EXISTS sp_update_session$$
CREATE PROCEDURE sp_update_session(
    IN p_session_id INT, IN p_trainer_id INT, IN p_date DATE,
    IN p_start TIME, IN p_end TIME, IN p_venue VARCHAR(255))
BEGIN
    DECLARE v_trainer INT;
    DECLARE v_date DATE;
    DECLARE v_start TIME;
    DECLARE v_end TIME;
    DECLARE v_found INT DEFAULT NULL;

    SELECT SessionID, COALESCE(p_trainer_id, TrainerID), COALESCE(p_date, SessionDate),
           COALESCE(p_start, StartTime), COALESCE(p_end, EndTime)
      INTO v_found, v_trainer, v_date, v_start, v_end
    FROM TrainingSession WHERE SessionID = p_session_id;

    IF v_found IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Session not found';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM Staff
                   WHERE StaffID = v_trainer AND StaffStatus = 'active' AND Role = 'trainer') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Trainer must be an active staff member with role trainer';
    END IF;
    IF EXISTS (SELECT 1 FROM TrainingSession
               WHERE TrainerID = v_trainer AND SessionDate = v_date
                 AND SessionID <> p_session_id AND SessionStatus <> 'cancelled'
                 AND StartTime < v_end AND v_start < EndTime) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Trainer already has a session at that time';
    END IF;

    UPDATE TrainingSession
    SET TrainerID = v_trainer, SessionDate = v_date, StartTime = v_start, EndTime = v_end,
        VenuePlatform = COALESCE(NULLIF(p_venue, ''), VenuePlatform)
    WHERE SessionID = p_session_id;

    INSERT INTO Notification (UserID, NotificationType, MessageContent)
    SELECT DISTINCT t.UserID, 'in-app',
           CONCAT('Schedule change: ', c.CourseName, ' session is now on ', v_date, ' at ', v_start, '.')
    FROM TrainingSession s
    JOIN Course c     ON c.CourseID = s.CourseID
    JOIN Enrollment e ON e.CourseID = s.CourseID AND e.EnrollmentStatus IN ('pending','active')
    JOIN Trainee t    ON t.TraineeID = e.TraineeID
    WHERE s.SessionID = p_session_id;
END$$

-- Change a session's status; cancellations and postponements notify enrolled trainees
DROP PROCEDURE IF EXISTS sp_set_session_status$$
CREATE PROCEDURE sp_set_session_status(IN p_session_id INT, IN p_status VARCHAR(20))
BEGIN
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;
    UPDATE TrainingSession SET SessionStatus = p_status WHERE SessionID = p_session_id;

    IF p_status IN ('cancelled', 'postponed') THEN
        INSERT INTO Notification (UserID, NotificationType, MessageContent)
        SELECT DISTINCT t.UserID, 'in-app',
               CONCAT(c.CourseName, ' session on ', s.SessionDate, ' has been ', p_status, '.')
        FROM TrainingSession s
        JOIN Course c     ON c.CourseID = s.CourseID
        JOIN Enrollment e ON e.CourseID = s.CourseID AND e.EnrollmentStatus IN ('pending','active')
        JOIN Trainee t    ON t.TraineeID = e.TraineeID
        WHERE s.SessionID = p_session_id;
    END IF;
    COMMIT;
END$$

-- Search sessions, every filter optional
DROP PROCEDURE IF EXISTS sp_search_sessions$$
CREATE PROCEDURE sp_search_sessions(
    IN p_course_id INT, IN p_trainer_id INT, IN p_status VARCHAR(20),
    IN p_from DATE, IN p_to DATE)
BEGIN
    SELECT SessionID, CourseID, CourseName, TrainerID, Trainer, SessionDate,
           StartTime, EndTime, VenuePlatform, SessionStatus
    FROM v_session_schedule
    WHERE (p_course_id  IS NULL OR CourseID = p_course_id)
      AND (p_trainer_id IS NULL OR TrainerID = p_trainer_id)
      AND (p_status     IS NULL OR SessionStatus = p_status)
      AND (p_from       IS NULL OR SessionDate >= p_from)
      AND (p_to         IS NULL OR SessionDate <= p_to)
    ORDER BY SessionDate, StartTime;
END$$

-- Sessions that already happened but have no attendance entered
DROP PROCEDURE IF EXISTS sp_sessions_missing_attendance$$
CREATE PROCEDURE sp_sessions_missing_attendance(IN p_course_id INT)
BEGIN
    SELECT s.SessionID, c.CourseName, s.SessionDate, st.FullName AS Trainer
    FROM TrainingSession s
    JOIN Course c  ON c.CourseID = s.CourseID
    JOIN Staff st  ON st.StaffID = s.TrainerID
    LEFT JOIN Attendance a ON a.SessionID = s.SessionID
    WHERE s.SessionDate < CURDATE()
      AND s.SessionStatus IN ('scheduled','completed')
      AND a.SessionID IS NULL
      AND (p_course_id IS NULL OR s.CourseID = p_course_id)
    ORDER BY s.SessionDate;
END$$

-- =====================================================================
-- SECTION 8: ATTENDANCE
-- =====================================================================

-- Record or correct one trainee's attendance for a session
DROP PROCEDURE IF EXISTS sp_record_attendance$$
CREATE PROCEDURE sp_record_attendance(
    IN p_session_id INT, IN p_trainee_id INT, IN p_status VARCHAR(20),
    IN p_check_in DATETIME, IN p_recorded_by INT)
BEGIN
    IF (SELECT SessionStatus FROM TrainingSession WHERE SessionID = p_session_id) = 'cancelled' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Cannot record attendance for a cancelled session';
    END IF;
    IF p_status IN ('present', 'late') AND p_check_in IS NULL THEN
        SET p_check_in = NOW();
    END IF;
    IF p_status IN ('absent', 'excused') THEN
        SET p_check_in = NULL;
    END IF;

    INSERT INTO Attendance (SessionID, TraineeID, RecordedBy, AttendanceStatus, CheckInTime)
    VALUES (p_session_id, p_trainee_id, p_recorded_by, p_status, p_check_in)
    ON DUPLICATE KEY UPDATE
        RecordedBy       = VALUES(RecordedBy),
        AttendanceStatus = VALUES(AttendanceStatus),
        CheckInTime      = VALUES(CheckInTime),
        RecordedAt       = NOW();
END$$

-- Full register for a session: every enrolled trainee with their mark (or none yet)
DROP PROCEDURE IF EXISTS sp_session_register$$
CREATE PROCEDURE sp_session_register(IN p_session_id INT)
BEGIN
    SELECT t.TraineeID, t.FullName, a.AttendanceStatus, a.CheckInTime,
           rb.FullName AS RecordedBy, a.RecordedAt
    FROM TrainingSession s
    JOIN Enrollment e ON e.CourseID = s.CourseID
                     AND e.EnrollmentStatus IN ('pending','active','completed')
    JOIN Trainee t    ON t.TraineeID = e.TraineeID
    LEFT JOIN Attendance a ON a.SessionID = s.SessionID AND a.TraineeID = t.TraineeID
    LEFT JOIN Staff rb     ON rb.StaffID = a.RecordedBy
    WHERE s.SessionID = p_session_id
    ORDER BY t.FullName;
END$$

-- Attendance percentage per enrollment, cancelled sessions excluded
DROP PROCEDURE IF EXISTS sp_attendance_report$$
CREATE PROCEDURE sp_attendance_report(IN p_course_id INT, IN p_trainee_id INT)
BEGIN
    SELECT e.EnrollmentID, t.TraineeID, t.FullName, c.CourseName,
           COUNT(s.SessionID) AS TotalSessions,
           COUNT(CASE WHEN a.AttendanceStatus IN ('present','late') THEN 1 END) AS Attended,
           COUNT(CASE WHEN a.AttendanceStatus = 'absent' THEN 1 END) AS Absent,
           COUNT(CASE WHEN a.AttendanceStatus = 'excused' THEN 1 END) AS Excused,
           ROUND(100 * COUNT(CASE WHEN a.AttendanceStatus IN ('present','late') THEN 1 END)
                     / NULLIF(COUNT(s.SessionID), 0), 1) AS AttendancePct
    FROM Enrollment e
    JOIN Trainee t ON t.TraineeID = e.TraineeID
    JOIN Course  c ON c.CourseID  = e.CourseID
    LEFT JOIN TrainingSession s ON s.CourseID = e.CourseID AND s.SessionStatus <> 'cancelled'
    LEFT JOIN Attendance a ON a.SessionID = s.SessionID AND a.TraineeID = e.TraineeID
    WHERE (p_course_id  IS NULL OR e.CourseID = p_course_id)
      AND (p_trainee_id IS NULL OR e.TraineeID = p_trainee_id)
    GROUP BY e.EnrollmentID, t.TraineeID, t.FullName, c.CourseName
    ORDER BY c.CourseName, t.FullName;
END$$

-- Trainees whose attendance on completed sessions is below a chosen percentage
DROP PROCEDURE IF EXISTS sp_at_risk_trainees$$
CREATE PROCEDURE sp_at_risk_trainees(IN p_course_id INT, IN p_threshold DECIMAL(5,2))
BEGIN
    SELECT e.EnrollmentID, t.FullName, t.PhoneNo, t.Email, c.CourseName,
           COUNT(s.SessionID) AS SessionsHeld,
           ROUND(100 * COUNT(CASE WHEN a.AttendanceStatus IN ('present','late') THEN 1 END)
                     / NULLIF(COUNT(s.SessionID), 0), 1) AS AttendancePct
    FROM Enrollment e
    JOIN Trainee t ON t.TraineeID = e.TraineeID
    JOIN Course  c ON c.CourseID  = e.CourseID
    JOIN TrainingSession s ON s.CourseID = e.CourseID AND s.SessionStatus = 'completed'
    LEFT JOIN Attendance a ON a.SessionID = s.SessionID AND a.TraineeID = e.TraineeID
    WHERE e.EnrollmentStatus IN ('pending','active')
      AND (p_course_id IS NULL OR e.CourseID = p_course_id)
    GROUP BY e.EnrollmentID, t.FullName, t.PhoneNo, t.Email, c.CourseName
    HAVING AttendancePct < COALESCE(p_threshold, 75)
    ORDER BY AttendancePct;
END$$

-- =====================================================================
-- SECTION 9: PAYMENTS
-- =====================================================================

-- Recompute an enrollment's payment status from its confirmed payments
DROP PROCEDURE IF EXISTS sp_refresh_payment_status$$
CREATE PROCEDURE sp_refresh_payment_status(IN p_enrollment_id INT)
BEGIN
    DECLARE v_paid DECIMAL(12,2);
    DECLARE v_fee  DECIMAL(12,2) DEFAULT NULL;

    SELECT COALESCE(SUM(AmountPaid), 0) INTO v_paid
    FROM Payment WHERE EnrollmentID = p_enrollment_id AND PaymentStatus = 'confirmed';

    SELECT c.CourseFee INTO v_fee
    FROM Enrollment e JOIN Course c ON c.CourseID = e.CourseID
    WHERE e.EnrollmentID = p_enrollment_id;

    IF v_fee IS NOT NULL THEN
        UPDATE Enrollment
        SET PaymentStatus = CASE WHEN v_paid >= v_fee THEN 'paid'
                                 WHEN v_paid > 0      THEN 'partially paid'
                                 ELSE 'pending' END
        WHERE EnrollmentID = p_enrollment_id;
    END IF;
END$$

-- Record a payment; reference and invoice are generated when left NULL
DROP PROCEDURE IF EXISTS sp_record_payment$$
CREATE PROCEDURE sp_record_payment(
    IN p_enrollment_id INT, IN p_amount DECIMAL(12,2), IN p_method VARCHAR(20),
    IN p_reference VARCHAR(100), IN p_status VARCHAR(20), IN p_invoice VARCHAR(100))
BEGIN
    DECLARE v_fee DECIMAL(12,2) DEFAULT NULL;
    DECLARE v_paid DECIMAL(12,2);
    DECLARE v_payment_id INT;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;
    SELECT c.CourseFee INTO v_fee
    FROM Enrollment e JOIN Course c ON c.CourseID = e.CourseID
    WHERE e.EnrollmentID = p_enrollment_id FOR UPDATE;

    IF v_fee IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Enrollment not found';
    END IF;

    SELECT COALESCE(SUM(AmountPaid), 0) INTO v_paid
    FROM Payment WHERE EnrollmentID = p_enrollment_id AND PaymentStatus = 'confirmed';

    IF COALESCE(p_status, 'confirmed') = 'confirmed' AND v_paid + p_amount > v_fee THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Payment exceeds the outstanding balance';
    END IF;

    INSERT INTO Payment (EnrollmentID, AmountPaid, PaymentMethod, TransactionReference,
                         PaymentStatus, InvoiceNumber)
    VALUES (p_enrollment_id, p_amount, p_method,
            COALESCE(NULLIF(p_reference, ''), CONCAT('TXN-', UUID_SHORT())),
            COALESCE(p_status, 'confirmed'),
            COALESCE(NULLIF(p_invoice, ''), CONCAT('INV-', UUID_SHORT())));
    SET v_payment_id = LAST_INSERT_ID();

    IF COALESCE(p_status, 'confirmed') = 'confirmed' THEN
        INSERT INTO Notification (UserID, NotificationType, MessageContent)
        SELECT t.UserID, 'in-app',
               CONCAT('Payment of ', p_amount, ' received for ', c.CourseName, '.')
        FROM Enrollment e
        JOIN Trainee t ON t.TraineeID = e.TraineeID
        JOIN Course c  ON c.CourseID = e.CourseID
        WHERE e.EnrollmentID = p_enrollment_id;
    END IF;
    COMMIT;

    SELECT p.PaymentID, p.InvoiceNumber, p.TransactionReference, e.PaymentStatus AS EnrollmentPaymentStatus
    FROM Payment p JOIN Enrollment e ON e.EnrollmentID = p.EnrollmentID
    WHERE p.PaymentID = v_payment_id;
END$$

-- Confirm, fail or reverse an existing payment
DROP PROCEDURE IF EXISTS sp_set_payment_status$$
CREATE PROCEDURE sp_set_payment_status(IN p_payment_id INT, IN p_status VARCHAR(20))
BEGIN
    DECLARE v_enrollment INT DEFAULT NULL;
    DECLARE v_amount DECIMAL(12,2);
    DECLARE v_fee DECIMAL(12,2);
    DECLARE v_paid DECIMAL(12,2);
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;
    SELECT EnrollmentID, AmountPaid INTO v_enrollment, v_amount
    FROM Payment WHERE PaymentID = p_payment_id FOR UPDATE;

    IF v_enrollment IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Payment not found';
    END IF;

    IF p_status = 'confirmed' THEN
        SELECT c.CourseFee INTO v_fee
        FROM Enrollment e JOIN Course c ON c.CourseID = e.CourseID
        WHERE e.EnrollmentID = v_enrollment;
        SELECT COALESCE(SUM(AmountPaid), 0) INTO v_paid
        FROM Payment
        WHERE EnrollmentID = v_enrollment AND PaymentStatus = 'confirmed' AND PaymentID <> p_payment_id;
        IF v_paid + v_amount > v_fee THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Payment exceeds the outstanding balance';
        END IF;
    END IF;

    UPDATE Payment SET PaymentStatus = p_status WHERE PaymentID = p_payment_id;

    IF p_status = 'confirmed' THEN
        INSERT INTO Notification (UserID, NotificationType, MessageContent)
        SELECT t.UserID, 'in-app',
               CONCAT('Payment of ', v_amount, ' confirmed for ', c.CourseName, '.')
        FROM Enrollment e
        JOIN Trainee t ON t.TraineeID = e.TraineeID
        JOIN Course c  ON c.CourseID = e.CourseID
        WHERE e.EnrollmentID = v_enrollment;
    END IF;
    COMMIT;
END$$

-- Balances per enrollment, optionally only those still owing
DROP PROCEDURE IF EXISTS sp_enrollment_balance$$
CREATE PROCEDURE sp_enrollment_balance(
    IN p_enrollment_id INT, IN p_trainee_id INT, IN p_only_outstanding TINYINT)
BEGIN
    SELECT v.EnrollmentID, v.Trainee, v.CourseName, v.CourseFee, v.TotalPaid, v.Balance
    FROM v_enrollment_balance v
    JOIN Enrollment e ON e.EnrollmentID = v.EnrollmentID
    WHERE (p_enrollment_id IS NULL OR v.EnrollmentID = p_enrollment_id)
      AND (p_trainee_id    IS NULL OR v.TraineeID = p_trainee_id)
      AND e.EnrollmentStatus NOT IN ('cancelled','withdrawn')
      AND (COALESCE(p_only_outstanding, 0) = 0 OR v.Balance > 0)
    ORDER BY v.Balance DESC;
END$$

-- Search payments, every filter optional (invoice and reference match exactly)
DROP PROCEDURE IF EXISTS sp_search_payments$$
CREATE PROCEDURE sp_search_payments(
    IN p_enrollment_id INT, IN p_method VARCHAR(20), IN p_status VARCHAR(20),
    IN p_from DATE, IN p_to DATE, IN p_invoice_or_reference VARCHAR(100))
BEGIN
    SELECT p.PaymentID, p.EnrollmentID, t.FullName, c.CourseName, p.AmountPaid,
           p.PaymentDate, p.PaymentMethod, p.PaymentStatus,
           p.TransactionReference, p.InvoiceNumber
    FROM Payment p
    JOIN Enrollment e ON e.EnrollmentID = p.EnrollmentID
    JOIN Trainee t    ON t.TraineeID = e.TraineeID
    JOIN Course c     ON c.CourseID = e.CourseID
    WHERE (p_enrollment_id IS NULL OR p.EnrollmentID = p_enrollment_id)
      AND (p_method  IS NULL OR p.PaymentMethod = p_method)
      AND (p_status  IS NULL OR p.PaymentStatus = p_status)
      AND (p_from    IS NULL OR p.PaymentDate >= p_from)
      AND (p_to      IS NULL OR p.PaymentDate < p_to + INTERVAL 1 DAY)
      AND (p_invoice_or_reference IS NULL
           OR p.InvoiceNumber = p_invoice_or_reference
           OR p.TransactionReference = p_invoice_or_reference)
    ORDER BY p.PaymentDate DESC;
END$$

-- Revenue grouped by month, method or course within an optional date range
DROP PROCEDURE IF EXISTS sp_revenue_report$$
CREATE PROCEDURE sp_revenue_report(IN p_group_by VARCHAR(10), IN p_from DATE, IN p_to DATE)
BEGIN
    IF p_group_by NOT IN ('month', 'method', 'course') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Group by must be month, method or course';
    END IF;

    SELECT CASE p_group_by
               WHEN 'month'  THEN DATE_FORMAT(p.PaymentDate, '%Y-%m')
               WHEN 'method' THEN p.PaymentMethod
               ELSE c.CourseName END AS GroupName,
           COUNT(*) AS Transactions,
           SUM(p.AmountPaid) AS Revenue
    FROM Payment p
    JOIN Enrollment e ON e.EnrollmentID = p.EnrollmentID
    JOIN Course c     ON c.CourseID = e.CourseID
    WHERE p.PaymentStatus = 'confirmed'
      AND (p_from IS NULL OR p.PaymentDate >= p_from)
      AND (p_to   IS NULL OR p.PaymentDate < p_to + INTERVAL 1 DAY)
    GROUP BY GroupName
    ORDER BY GroupName;
END$$

-- =====================================================================
-- SECTION 10: CERTIFICATES
-- =====================================================================

-- Enrollments that are completed and paid but have no certificate yet
DROP PROCEDURE IF EXISTS sp_certificate_candidates$$
CREATE PROCEDURE sp_certificate_candidates(IN p_course_id INT)
BEGIN
    SELECT e.EnrollmentID, t.FullName, c.CourseName, e.EnrollmentDate
    FROM Enrollment e
    JOIN Trainee t ON t.TraineeID = e.TraineeID
    JOIN Course  c ON c.CourseID  = e.CourseID
    LEFT JOIN Certificate ct ON ct.EnrollmentID = e.EnrollmentID
    WHERE e.EnrollmentStatus = 'completed'
      AND e.PaymentStatus = 'paid'
      AND ct.CertificateID IS NULL
      AND (p_course_id IS NULL OR e.CourseID = p_course_id)
    ORDER BY c.CourseName, t.FullName;
END$$

-- Issue a certificate with a generated serial number and notify the trainee
DROP PROCEDURE IF EXISTS sp_issue_certificate$$
CREATE PROCEDURE sp_issue_certificate(IN p_enrollment_id INT, IN p_issued_by INT)
BEGIN
    DECLARE v_serial VARCHAR(100);
    DECLARE v_certificate_id INT;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    SET v_serial = CONCAT('NFSI-', YEAR(CURDATE()), '-', LPAD(p_enrollment_id, 5, '0'),
                          '-', LPAD(FLOOR(RAND() * 10000), 4, '0'));

    START TRANSACTION;
    INSERT INTO Certificate (EnrollmentID, IssuedBy, IssueDate, SerialNumber)
    VALUES (p_enrollment_id, p_issued_by, CURDATE(), v_serial);
    SET v_certificate_id = LAST_INSERT_ID();

    INSERT INTO Notification (UserID, NotificationType, MessageContent)
    SELECT t.UserID, 'in-app',
           CONCAT('Your certificate for ', c.CourseName, ' has been issued. Serial: ', v_serial)
    FROM Enrollment e
    JOIN Trainee t ON t.TraineeID = e.TraineeID
    JOIN Course c  ON c.CourseID = e.CourseID
    WHERE e.EnrollmentID = p_enrollment_id;
    COMMIT;

    SELECT v_certificate_id AS CertificateID, v_serial AS SerialNumber;
END$$

-- Revoke or mark a certificate as replaced
DROP PROCEDURE IF EXISTS sp_set_certificate_status$$
CREATE PROCEDURE sp_set_certificate_status(IN p_certificate_id INT, IN p_status VARCHAR(20))
BEGIN
    UPDATE Certificate SET CertificateStatus = p_status WHERE CertificateID = p_certificate_id;
END$$

-- Verify a certificate by its serial number
DROP PROCEDURE IF EXISTS sp_verify_certificate$$
CREATE PROCEDURE sp_verify_certificate(IN p_serial VARCHAR(100))
BEGIN
    SELECT SerialNumber, Trainee, CourseName, IssueDate, CertificateStatus, IssuedBy
    FROM v_certificate_register
    WHERE SerialNumber = p_serial;
END$$

-- Search issued certificates, every filter optional
DROP PROCEDURE IF EXISTS sp_search_certificates$$
CREATE PROCEDURE sp_search_certificates(
    IN p_search VARCHAR(100), IN p_status VARCHAR(20), IN p_from DATE, IN p_to DATE)
BEGIN
    SELECT CertificateID, SerialNumber, Trainee, CourseName, IssueDate, CertificateStatus, IssuedBy
    FROM v_certificate_register
    WHERE (p_search IS NULL OR Trainee LIKE CONCAT('%', p_search, '%')
                            OR CourseName LIKE CONCAT('%', p_search, '%')
                            OR SerialNumber = p_search)
      AND (p_status IS NULL OR CertificateStatus = p_status)
      AND (p_from   IS NULL OR IssueDate >= p_from)
      AND (p_to     IS NULL OR IssueDate <= p_to)
    ORDER BY IssueDate DESC;
END$$

-- =====================================================================
-- SECTION 11: NOTIFICATIONS
-- =====================================================================

-- Queue a notification for one user
DROP PROCEDURE IF EXISTS sp_send_notification$$
CREATE PROCEDURE sp_send_notification(
    IN p_user_id INT, IN p_type VARCHAR(20), IN p_message TEXT)
BEGIN
    INSERT INTO Notification (UserID, NotificationType, MessageContent)
    VALUES (p_user_id, p_type, p_message);
    SELECT LAST_INSERT_ID() AS NotificationID;
END$$

-- Queue a notification for every trainee enrolled in a course
DROP PROCEDURE IF EXISTS sp_notify_course$$
CREATE PROCEDURE sp_notify_course(
    IN p_course_id INT, IN p_type VARCHAR(20), IN p_message TEXT)
BEGIN
    INSERT INTO Notification (UserID, NotificationType, MessageContent)
    SELECT DISTINCT t.UserID, p_type, p_message
    FROM Enrollment e
    JOIN Trainee t ON t.TraineeID = e.TraineeID
    WHERE e.CourseID = p_course_id AND e.EnrollmentStatus IN ('pending','active');
    SELECT ROW_COUNT() AS NotificationsQueued;
END$$

-- A user's inbox, optionally only unread, newest first
DROP PROCEDURE IF EXISTS sp_user_inbox$$
CREATE PROCEDURE sp_user_inbox(IN p_user_id INT, IN p_unread_only TINYINT)
BEGIN
    SELECT NotificationID, NotificationType, MessageContent, DateSent, DeliveryStatus, IsRead
    FROM Notification
    WHERE UserID = p_user_id
      AND (COALESCE(p_unread_only, 0) = 0 OR IsRead = FALSE)
    ORDER BY DateSent DESC, NotificationID DESC;
END$$

-- Count of unread notifications for the badge
DROP PROCEDURE IF EXISTS sp_unread_count$$
CREATE PROCEDURE sp_unread_count(IN p_user_id INT)
BEGIN
    SELECT COUNT(*) AS Unread FROM Notification WHERE UserID = p_user_id AND IsRead = FALSE;
END$$

-- Mark one notification as read (only the owner can)
DROP PROCEDURE IF EXISTS sp_mark_read$$
CREATE PROCEDURE sp_mark_read(IN p_notification_id INT, IN p_user_id INT)
BEGIN
    UPDATE Notification SET IsRead = TRUE
    WHERE NotificationID = p_notification_id AND UserID = p_user_id;
END$$

-- Mark all of a user's notifications as read
DROP PROCEDURE IF EXISTS sp_mark_all_read$$
CREATE PROCEDURE sp_mark_all_read(IN p_user_id INT)
BEGIN
    UPDATE Notification SET IsRead = TRUE WHERE UserID = p_user_id AND IsRead = FALSE;
END$$

-- Notifications waiting to be sent, with the contact details a dispatcher needs
DROP PROCEDURE IF EXISTS sp_notification_queue$$
CREATE PROCEDURE sp_notification_queue(IN p_type VARCHAR(20))
BEGIN
    SELECT n.NotificationID, n.UserID, n.NotificationType, n.MessageContent, n.DateSent,
           COALESCE(t.PhoneNo, s.PhoneNo) AS PhoneNo,
           COALESCE(t.Email, s.Email) AS Email
    FROM Notification n
    LEFT JOIN Trainee t ON t.UserID = n.UserID
    LEFT JOIN Staff   s ON s.UserID = n.UserID
    WHERE n.DeliveryStatus = 'pending'
      AND (p_type IS NULL OR n.NotificationType = p_type)
    ORDER BY n.DateSent;
END$$

-- Record the delivery result reported by the SMS or email gateway
DROP PROCEDURE IF EXISTS sp_set_delivery_status$$
CREATE PROCEDURE sp_set_delivery_status(IN p_notification_id INT, IN p_status VARCHAR(20))
BEGIN
    UPDATE Notification SET DeliveryStatus = p_status WHERE NotificationID = p_notification_id;
END$$

-- Delivery success rate per channel
DROP PROCEDURE IF EXISTS sp_delivery_report$$
CREATE PROCEDURE sp_delivery_report(IN p_from DATE, IN p_to DATE)
BEGIN
    SELECT NotificationType, COUNT(*) AS Total,
           SUM(DeliveryStatus IN ('sent','delivered')) AS Successful,
           SUM(DeliveryStatus = 'failed') AS Failed,
           SUM(DeliveryStatus = 'pending') AS Pending,
           ROUND(100 * SUM(DeliveryStatus IN ('sent','delivered')) / COUNT(*), 1) AS SuccessPct
    FROM Notification
    WHERE (p_from IS NULL OR DateSent >= p_from)
      AND (p_to   IS NULL OR DateSent < p_to + INTERVAL 1 DAY)
    GROUP BY NotificationType;
END$$

-- =====================================================================
-- SECTION 12: DATA INTEGRITY AUDIT
-- =====================================================================

-- One row per check with the number of violations (all should be 0)
DROP PROCEDURE IF EXISTS sp_integrity_audit$$
CREATE PROCEDURE sp_integrity_audit()
BEGIN
    SELECT 'Attendance for a trainee not enrolled in the course' AS CheckName, COUNT(*) AS Violations
    FROM Attendance a
    JOIN TrainingSession s ON s.SessionID = a.SessionID
    LEFT JOIN Enrollment e ON e.TraineeID = a.TraineeID AND e.CourseID = s.CourseID
    WHERE e.EnrollmentID IS NULL
    UNION ALL
    SELECT 'Courses over capacity', COUNT(*) FROM (
        SELECT c.CourseID
        FROM Enrollment e JOIN Course c ON c.CourseID = e.CourseID
        WHERE e.EnrollmentStatus IN ('pending','active','completed')
        GROUP BY c.CourseID, c.MaximumCapacity
        HAVING COUNT(*) > c.MaximumCapacity) x
    UNION ALL
    SELECT 'Certificates without a completed and paid enrollment', COUNT(*)
    FROM Certificate ct JOIN Enrollment e ON e.EnrollmentID = ct.EnrollmentID
    WHERE ct.IssueDate < e.EnrollmentDate
       OR e.EnrollmentStatus <> 'completed' OR e.PaymentStatus <> 'paid'
    UNION ALL
    SELECT 'Open enrollments for inactive trainees or courses', COUNT(*)
    FROM Enrollment e
    JOIN Trainee t ON t.TraineeID = e.TraineeID
    JOIN Course c  ON c.CourseID = e.CourseID
    WHERE e.EnrollmentStatus IN ('pending','active')
      AND (t.TraineeStatus <> 'active' OR c.CourseStatus <> 'active')
    UNION ALL
    SELECT 'Scheduled sessions with an inactive or non-trainer staff member', COUNT(*)
    FROM TrainingSession s JOIN Staff st ON st.StaffID = s.TrainerID
    WHERE s.SessionStatus = 'scheduled' AND (st.StaffStatus <> 'active' OR st.Role <> 'trainer')
    UNION ALL
    SELECT 'Accounts with no trainee or staff profile', COUNT(*)
    FROM UserAccount u
    LEFT JOIN Trainee t ON t.UserID = u.UserID
    LEFT JOIN Staff   s ON s.UserID = u.UserID
    WHERE t.TraineeID IS NULL AND s.StaffID IS NULL
    UNION ALL
    SELECT 'Account role differs from profile role', COUNT(*)
    FROM UserAccount u
    LEFT JOIN Trainee t ON t.UserID = u.UserID
    LEFT JOIN Staff   s ON s.UserID = u.UserID
    WHERE (t.TraineeID IS NOT NULL AND u.Role <> 'trainee')
       OR (s.StaffID  IS NOT NULL AND u.Role <> s.Role)
    UNION ALL
    SELECT 'Present or late records with no check-in time', COUNT(*)
    FROM Attendance WHERE AttendanceStatus IN ('present','late') AND CheckInTime IS NULL
    UNION ALL
    SELECT 'Enrollments whose payment status disagrees with payments', COUNT(*) FROM (
        SELECT e.EnrollmentID
        FROM Enrollment e
        JOIN Course c ON c.CourseID = e.CourseID
        LEFT JOIN Payment p ON p.EnrollmentID = e.EnrollmentID
        GROUP BY e.EnrollmentID, e.PaymentStatus, c.CourseFee
        HAVING e.PaymentStatus <> CASE
            WHEN COALESCE(SUM(CASE WHEN p.PaymentStatus = 'confirmed' THEN p.AmountPaid END), 0) >= c.CourseFee THEN 'paid'
            WHEN COALESCE(SUM(CASE WHEN p.PaymentStatus = 'confirmed' THEN p.AmountPaid END), 0) > 0 THEN 'partially paid'
            ELSE 'pending' END) y;
END$$

-- =====================================================================
-- SECTION 13: TRIGGERS (the database enforces these even if the app forgets)
-- =====================================================================

-- Enrollment needs an active trainee, an active course and a free seat
DROP TRIGGER IF EXISTS trg_enrollment_bi$$
CREATE TRIGGER trg_enrollment_bi BEFORE INSERT ON Enrollment
FOR EACH ROW
BEGIN
    IF (SELECT TraineeStatus FROM Trainee WHERE TraineeID = NEW.TraineeID) <> 'active' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Trainee is not active';
    END IF;
    IF (SELECT CourseStatus FROM Course WHERE CourseID = NEW.CourseID) <> 'active' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Course is not active';
    END IF;
    IF (SELECT COUNT(*) FROM Enrollment
        WHERE CourseID = NEW.CourseID
          AND EnrollmentStatus IN ('pending','active','completed'))
       >= (SELECT MaximumCapacity FROM Course WHERE CourseID = NEW.CourseID) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Course has reached maximum capacity';
    END IF;
END$$

-- A session must be run by an active trainer
DROP TRIGGER IF EXISTS trg_session_bi$$
CREATE TRIGGER trg_session_bi BEFORE INSERT ON TrainingSession
FOR EACH ROW
BEGIN
    IF NOT EXISTS (SELECT 1 FROM Staff
                   WHERE StaffID = NEW.TrainerID AND StaffStatus = 'active' AND Role = 'trainer') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Trainer must be an active staff member with role trainer';
    END IF;
END$$

-- Attendance is only allowed for trainees enrolled in the session's course
DROP TRIGGER IF EXISTS trg_attendance_bi$$
CREATE TRIGGER trg_attendance_bi BEFORE INSERT ON Attendance
FOR EACH ROW
BEGIN
    IF NOT EXISTS (SELECT 1 FROM TrainingSession s
                   JOIN Enrollment e ON e.CourseID = s.CourseID
                   WHERE s.SessionID = NEW.SessionID AND e.TraineeID = NEW.TraineeID
                     AND e.EnrollmentStatus IN ('pending','active','completed')) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Trainee is not enrolled in this session course';
    END IF;
END$$

-- A certificate needs a completed, fully paid enrollment and a valid issue date
DROP TRIGGER IF EXISTS trg_certificate_bi$$
CREATE TRIGGER trg_certificate_bi BEFORE INSERT ON Certificate
FOR EACH ROW
BEGIN
    DECLARE v_status VARCHAR(20);
    DECLARE v_pay VARCHAR(20);
    DECLARE v_date DATE;

    SELECT EnrollmentStatus, PaymentStatus, EnrollmentDate
      INTO v_status, v_pay, v_date
    FROM Enrollment WHERE EnrollmentID = NEW.EnrollmentID;

    IF v_status <> 'completed' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Enrollment is not completed';
    END IF;
    IF v_pay <> 'paid' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Enrollment is not fully paid';
    END IF;
    IF NEW.IssueDate < v_date THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Issue date is before the enrollment date';
    END IF;
END$$

-- Keep Enrollment.PaymentStatus in step with payments automatically
DROP TRIGGER IF EXISTS trg_payment_ai$$
CREATE TRIGGER trg_payment_ai AFTER INSERT ON Payment
FOR EACH ROW
BEGIN
    CALL sp_refresh_payment_status(NEW.EnrollmentID);
END$$

DROP TRIGGER IF EXISTS trg_payment_au$$
CREATE TRIGGER trg_payment_au AFTER UPDATE ON Payment
FOR EACH ROW
BEGIN
    CALL sp_refresh_payment_status(NEW.EnrollmentID);
END$$

DELIMITER ;