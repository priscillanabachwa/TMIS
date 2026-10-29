USE tmis_db;

-- Sample accounts.
-- These password values are placeholders, not usable login hashes.
INSERT INTO UserAccount
    (Username, PasswordHash, Role, AccountStatus)
VALUES
    ('namusokeagnes', 'DEMO_HASH_NOT_FOR_LOGIN', 'trainee', 'active'),
    ('ssekandijames', 'DEMO_HASH_NOT_FOR_LOGIN', 'trainer', 'active'),
    ('nalugemasarah', 'DEMO_HASH_NOT_FOR_LOGIN', 'administrator', 'active');


-- Trainee profile linked to the trainee account.
INSERT INTO Trainee (
    UserID, FullName, DateOfBirth, Gender, NIN,
    PhoneNo, Email, Organization, Address,
    RegistrationDate, TraineeStatus
)
VALUES (
    (SELECT UserID FROM UserAccount WHERE Username = 'namusokeagnes'),
    'Namusoke Agnes',
    '2002-05-14',
    'female',
    'DEMO-NIN-001',
    '0700000001',
    'agnes.namusoke@example.com',
    'Central Food Processors',
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
    (SELECT UserID FROM UserAccount WHERE Username = 'ssekandijames'),
    'Ssekandi James',
    'trainer',
    'james.ssekandi@example.com',
    '0700000002',
    'Training',
    'active',
    CURRENT_DATE
),
(
    (SELECT UserID FROM UserAccount WHERE Username = 'nalugemasarah'),
    'Nalugema Sarah',
    'administrator',
    'sarah.nalugemasarah@example.com',
    '0700000003',
    'Administration',
    'active',
    CURRENT_DATE
);