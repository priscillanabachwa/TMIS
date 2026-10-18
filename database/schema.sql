CREATE DATABASE IF NOT EXISTS tmis_db
    CHARACTER SET utf8mb4;
 
USE tmis_db;

CREATE TABLE UserAccount (
    UserID INT AUTO_INCREMENT PRIMARY KEY,
    Username VARCHAR(50) NOT NULL UNIQUE,
    PasswordHash VARCHAR(255) NOT NULL,
    Role VARCHAR(20) NOT NULL,
    AccountStatus VARCHAR(20) NOT NULL DEFAULT 'active',
    CreatedAt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    LastLogin DATETIME NULL,

    CONSTRAINT chk_user_role
        CHECK (Role IN ('trainee', 'trainer', 'administrator')),

    CONSTRAINT chk_account_status
        CHECK (AccountStatus IN ('active', 'inactive', 'suspended'))
);


-- 2. TRAINEE
CREATE TABLE IF NOT EXISTS Trainee (
    TraineeID INT AUTO_INCREMENT PRIMARY KEY,
    UserID INT NOT NULL UNIQUE,
    FullName VARCHAR(150) NOT NULL,
    DateOfBirth DATE NOT NULL,
    Gender VARCHAR(20) NOT NULL,
    NIN VARCHAR(20) NOT NULL UNIQUE,
    PhoneNo VARCHAR(20) NOT NULL,
    Email VARCHAR(150) NOT NULL UNIQUE,
    Organization VARCHAR(150) NULL,
    Address VARCHAR(255) NULL,
    RegistrationDate DATE NOT NULL,
    TraineeStatus VARCHAR(20) NOT NULL DEFAULT 'active',

    CONSTRAINT fk_trainee_user
        FOREIGN KEY (UserID) REFERENCES UserAccount(UserID),

    CONSTRAINT chk_trainee_status
        CHECK (TraineeStatus IN ('active', 'inactive', 'archived'))
);


-- 3. STAFF
CREATE TABLE IF NOT EXISTS Staff (
    StaffID INT AUTO_INCREMENT PRIMARY KEY,
    UserID INT NOT NULL UNIQUE,
    FullName VARCHAR(150) NOT NULL,
    Role VARCHAR(20) NOT NULL,
    Email VARCHAR(150) NOT NULL UNIQUE,
    PhoneNo VARCHAR(20) NULL,
    Department VARCHAR(100) NOT NULL,
    StaffStatus VARCHAR(20) NOT NULL DEFAULT 'active',
    DateJoined DATE NOT NULL DEFAULT (CURRENT_DATE),

    CONSTRAINT fk_staff_user
        FOREIGN KEY (UserID) REFERENCES UserAccount(UserID),

    CONSTRAINT chk_staff_role
        CHECK (Role IN ('trainer', 'administrator')),

    CONSTRAINT chk_staff_status
        CHECK (StaffStatus IN ('active', 'inactive', 'archived'))
);


-- 4. COURSE
CREATE TABLE IF NOT EXISTS Course (
    CourseID INT AUTO_INCREMENT PRIMARY KEY,
    CourseName VARCHAR(150) NOT NULL,
    Description TEXT NULL,
    Category VARCHAR(100) NOT NULL,
    Duration VARCHAR(50) NOT NULL,
    ModeOfDelivery VARCHAR(20) NOT NULL,
    CourseFee DECIMAL(12, 2) NOT NULL,
    CourseStatus VARCHAR(20) NOT NULL DEFAULT 'active',
    Prerequisites TEXT NULL,
    MaximumCapacity INT NOT NULL,

    CONSTRAINT chk_course_mode
        CHECK (ModeOfDelivery IN ('physical', 'online', 'hybrid')),

    CONSTRAINT chk_course_fee
        CHECK (CourseFee >= 0),

    CONSTRAINT chk_course_capacity
        CHECK (MaximumCapacity > 0),

    CONSTRAINT chk_course_status
        CHECK (CourseStatus IN ('active', 'inactive', 'archived'))
);


-- 5. ENROLLMENT
CREATE TABLE IF NOT EXISTS Enrollment (
    EnrollmentID INT AUTO_INCREMENT PRIMARY KEY,
    TraineeID INT NOT NULL,
    CourseID INT NOT NULL,
    EnrollmentDate DATE NOT NULL DEFAULT (CURRENT_DATE),
    EnrollmentStatus VARCHAR(20) NOT NULL DEFAULT 'pending',
    PaymentStatus VARCHAR(20) NOT NULL DEFAULT 'pending',

    CONSTRAINT fk_enrollment_trainee
        FOREIGN KEY (TraineeID) REFERENCES Trainee(TraineeID),

    CONSTRAINT fk_enrollment_course
        FOREIGN KEY (CourseID) REFERENCES Course(CourseID),

    CONSTRAINT uq_trainee_course
        UNIQUE (TraineeID, CourseID),

    CONSTRAINT chk_enrollment_status
        CHECK (
            EnrollmentStatus IN (
                'pending', 'active', 'completed',
                'cancelled', 'withdrawn'
            )
        ),

    CONSTRAINT chk_enrollment_payment_status
        CHECK (PaymentStatus IN ('pending', 'partially paid', 'paid'))
);


-- 6. TRAINING SESSION
CREATE TABLE IF NOT EXISTS TrainingSession (
    SessionID INT AUTO_INCREMENT PRIMARY KEY,
    CourseID INT NOT NULL,
    TrainerID INT NOT NULL,
    SessionDate DATE NOT NULL,
    StartTime TIME NOT NULL,
    EndTime TIME NOT NULL,
    VenuePlatform VARCHAR(255) NOT NULL,
    SessionStatus VARCHAR(20) NOT NULL DEFAULT 'scheduled',

    CONSTRAINT fk_session_course
        FOREIGN KEY (CourseID) REFERENCES Course(CourseID),

    CONSTRAINT fk_session_trainer
        FOREIGN KEY (TrainerID) REFERENCES Staff(StaffID),

    CONSTRAINT chk_session_times
        CHECK (EndTime > StartTime),

    CONSTRAINT chk_session_status
        CHECK (
            SessionStatus IN (
                'scheduled', 'completed', 'postponed', 'cancelled'
            )
        )
);


-- 7. ATTENDANCE
CREATE TABLE IF NOT EXISTS Attendance (
    SessionID INT NOT NULL,
    TraineeID INT NOT NULL,
    RecordedBy INT NULL,
    AttendanceStatus VARCHAR(20) NOT NULL,
    CheckInTime DATETIME NULL,
    RecordedAt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (SessionID, TraineeID),

    CONSTRAINT fk_attendance_session
        FOREIGN KEY (SessionID) REFERENCES TrainingSession(SessionID),

    CONSTRAINT fk_attendance_trainee
        FOREIGN KEY (TraineeID) REFERENCES Trainee(TraineeID),

    CONSTRAINT fk_attendance_staff
        FOREIGN KEY (RecordedBy) REFERENCES Staff(StaffID),

    CONSTRAINT chk_attendance_status
        CHECK (AttendanceStatus IN ('present', 'absent', 'late', 'excused'))
);


-- 8. PAYMENT
CREATE TABLE IF NOT EXISTS Payment (
    PaymentID INT AUTO_INCREMENT PRIMARY KEY,
    EnrollmentID INT NOT NULL,
    AmountPaid DECIMAL(12, 2) NOT NULL,
    PaymentDate DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PaymentMethod VARCHAR(20) NOT NULL,
    TransactionReference VARCHAR(100) NOT NULL UNIQUE,
    PaymentStatus VARCHAR(20) NOT NULL DEFAULT 'pending',
    InvoiceNumber VARCHAR(100) NOT NULL UNIQUE,

    CONSTRAINT fk_payment_enrollment
        FOREIGN KEY (EnrollmentID) REFERENCES Enrollment(EnrollmentID),

    CONSTRAINT chk_payment_amount
        CHECK (AmountPaid > 0),

    CONSTRAINT chk_payment_method
        CHECK (
            PaymentMethod IN (
                'cash', 'bank transfer', 'card', 'mobile money'
            )
        ),

    CONSTRAINT chk_payment_status
        CHECK (PaymentStatus IN ('pending', 'confirmed', 'failed', 'reversed'))
);


-- 9. CERTIFICATE
CREATE TABLE IF NOT EXISTS Certificate (
    CertificateID INT AUTO_INCREMENT PRIMARY KEY,
    EnrollmentID INT NOT NULL UNIQUE,
    IssuedBy INT NOT NULL,
    IssueDate DATE NOT NULL,
    SerialNumber VARCHAR(100) NOT NULL UNIQUE,
    CertificateStatus VARCHAR(20) NOT NULL DEFAULT 'issued',

    CONSTRAINT fk_certificate_enrollment
        FOREIGN KEY (EnrollmentID) REFERENCES Enrollment(EnrollmentID),

    CONSTRAINT fk_certificate_staff
        FOREIGN KEY (IssuedBy) REFERENCES Staff(StaffID),

    CONSTRAINT chk_certificate_status
        CHECK (CertificateStatus IN ('issued', 'revoked', 'replaced'))
);


-- 10. NOTIFICATION
CREATE TABLE IF NOT EXISTS Notification (
    NotificationID INT AUTO_INCREMENT PRIMARY KEY,
    UserID INT NOT NULL,
    NotificationType VARCHAR(20) NOT NULL,
    MessageContent TEXT NOT NULL,
    DateSent DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    DeliveryStatus VARCHAR(20) NOT NULL DEFAULT 'pending',
    IsRead BOOLEAN NOT NULL DEFAULT FALSE,

    CONSTRAINT fk_notification_user
        FOREIGN KEY (UserID) REFERENCES UserAccount(UserID),

    CONSTRAINT chk_notification_type
        CHECK (NotificationType IN ('SMS', 'email', 'in-app')),

    CONSTRAINT chk_notification_delivery
        CHECK (DeliveryStatus IN ('pending', 'sent', 'delivered', 'failed')),

    CONSTRAINT chk_notification_read
        CHECK (IsRead IN (0, 1))
);