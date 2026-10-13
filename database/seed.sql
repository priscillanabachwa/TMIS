USE tmis_db;

-- Sample accounts.
-- These password values are placeholders, not usable login hashes.
INSERT INTO UserAccount
    (Username, PasswordHash, Role, AccountStatus)
VALUES
    ('demo_trainee', 'DEMO_HASH_NOT_FOR_LOGIN', 'trainee', 'active'),
    ('demo_trainer', 'DEMO_HASH_NOT_FOR_LOGIN', 'trainer', 'active'),
    ('demo_admin', 'DEMO_HASH_NOT_FOR_LOGIN', 'administrator', 'active');


-- Trainee profile linked to the trainee account.
INSERT INTO Trainee (
    UserID, FullName, DateOfBirth, Gender, NIN,
    PhoneNo, Email, Organization, Address,
    RegistrationDate, TraineeStatus
)
VALUES (
    (SELECT UserID FROM UserAccount WHERE Username = 'demo_trainee'),
    'Demo Trainee',
    '2002-05-14',
    'female',
    'DEMO-NIN-001',
    '0700000001',
    'trainee@example.com',
    'Demo Food Company',
    'Kampala',
    CURRENT_DATE,
    'active'
);


-- Staff profiles linked to their accounts.
INSERT INTO Staff (
    UserID, FullName, Role, Email,
    PhoneNo, Department, StaffStatus, DateJoined
)
VALUES
(
    (SELECT UserID FROM UserAccount WHERE Username = 'demo_trainer'),
    'Demo Trainer',
    'trainer',
    'trainer@example.com',
    '0700000002',
    'Training',
    'active',
    CURRENT_DATE
),
(
    (SELECT UserID FROM UserAccount WHERE Username = 'demo_admin'),
    'Demo Administrator',
    'administrator',
    'admin@example.com',
    '0700000003',
    'Administration',
    'active',
    CURRENT_DATE
);