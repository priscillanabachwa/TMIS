USE tmis_db;

-- 1. SAMPLE COURSES
INSERT INTO Course (
    CourseName, Description, Category, Duration,
    ModeOfDelivery, CourseFee, CourseStatus,
    Prerequisites, MaximumCapacity
)
VALUES
(
    'Basic Food Safety',
    'Introduction to safe food handling and storage.',
    'Food Safety',
    '3 days',
    'physical',
    150000.00,
    'active',
    NULL,
    30
),
(
    'Food Hygiene',
    'Personal hygiene, cleaning and contamination prevention.',
    'Food Safety',
    '2 days',
    'online',
    100000.00,
    'active',
    NULL,
    25
),
(
    'HACCP Fundamentals',
    'Introduction to hazard analysis and critical control points.',
    'Quality Assurance',
    '5 days',
    'hybrid',
    300000.00,
    'active',
    'Basic knowledge of food safety',
    20
);


-- 2. FIND THE EXISTING TRAINEE AND TRAINER
SET @trainee_id = (
    SELECT TraineeID
    FROM Trainee
    WHERE Email = 'agnes.namusoke@example.test'
);

SET @trainer_id = (
    SELECT StaffID
    FROM Staff
    WHERE Email = 'james.ssekandi@example.test'
);

-- Capture the IDs of the three courses just inserted.
SET @first_course_id = LAST_INSERT_ID();
SET @food_safety_id = @first_course_id;
SET @food_hygiene_id = @first_course_id + @@auto_increment_increment;
SET @haccp_id = @first_course_id + (2 * @@auto_increment_increment);


-- 3. ENROLL THE TRAINEE IN TWO COURSES
INSERT INTO Enrollment (
    TraineeID, CourseID, EnrollmentDate,
    EnrollmentStatus, PaymentStatus
)
VALUES
(
    @trainee_id,
    @food_safety_id,
    CURRENT_DATE,
    'active',
    'pending'
),
(
    @trainee_id,
    @food_hygiene_id,
    CURRENT_DATE,
    'active',
    'pending'
);


-- 4. CREATE TRAINING SESSIONS
INSERT INTO TrainingSession (
    CourseID, TrainerID, SessionDate,
    StartTime, EndTime, VenuePlatform, SessionStatus
)
VALUES
(
    @food_safety_id,
    @trainer_id,
    CURRENT_DATE + INTERVAL 7 DAY,
    '09:00:00',
    '12:00:00',
    'NFSI Training Room, Ntinda',
    'scheduled'
),
(
    @food_hygiene_id,
    @trainer_id,
    CURRENT_DATE + INTERVAL 8 DAY,
    '10:00:00',
    '12:00:00',
    'Online training platform',
    'scheduled'
),
(
    @haccp_id,
    @trainer_id,
    CURRENT_DATE + INTERVAL 9 DAY,
    '09:00:00',
    '13:00:00',
    'NFSI Training Room and online platform',
    'scheduled'
);