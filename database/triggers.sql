
USE tmis_db;

DELIMITER $$

-- Validate new enrollments
CREATE TRIGGER before_enrollment_insert
BEFORE INSERT ON Enrollment
FOR EACH ROW
BEGIN
    DECLARE trainee_status VARCHAR(20);
    DECLARE course_status VARCHAR(20);
    DECLARE course_capacity INT;
    DECLARE current_enrollments INT;

    SELECT TraineeStatus
    INTO trainee_status
    FROM Trainee
    WHERE TraineeID = NEW.TraineeID;

    SELECT CourseStatus, MaximumCapacity
    INTO course_status, course_capacity
    FROM Course
    WHERE CourseID = NEW.CourseID;

    IF trainee_status <> 'active' THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Only active trainees can enroll.';
    END IF;

    IF course_status <> 'active' THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Only active courses accept enrollments.';
    END IF;

    SELECT COUNT(*)
    INTO current_enrollments
    FROM Enrollment
    WHERE CourseID = NEW.CourseID
      AND EnrollmentStatus IN ('pending', 'active', 'completed');

    IF current_enrollments >= course_capacity THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Course maximum capacity reached.';
    END IF;
END$$


-- Validate attendance before inserting it
CREATE TRIGGER before_attendance_insert
BEFORE INSERT ON Attendance
FOR EACH ROW
BEGIN
    DECLARE session_course INT;
    DECLARE trainee_enrollment_count INT;

    SELECT CourseID
    INTO session_course
    FROM TrainingSession
    WHERE SessionID = NEW.SessionID
      AND SessionStatus <> 'cancelled';

    IF session_course IS NULL THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Attendance requires a valid, non-cancelled session.';
    END IF;

    SELECT COUNT(*)
    INTO trainee_enrollment_count
    FROM Enrollment
    WHERE TraineeID = NEW.TraineeID
      AND CourseID = session_course
      AND EnrollmentStatus IN ('pending', 'active', 'completed');

    IF trainee_enrollment_count = 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Trainee is not enrolled in this session course.';
    END IF;
END$$

DELIMITER ;
