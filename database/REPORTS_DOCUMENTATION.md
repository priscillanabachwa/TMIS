# Chapter: System Reports and Analytical Views
**Project**: Training Management Information System (TMIS)  
**Database**: `tmis_db`  
**Module**: Business Intelligence, Operational & Strategic Reporting  

---

## 1. Introduction to TMIS Reporting Subsystem

In a computerized Training Management Information System (TMIS), raw transactional data entered through forms (trainee registrations, attendance marks, course creation, fee payments) only provides real value when synthesized into actionable business reports.

The reporting subsystem of TMIS is designed to satisfy three operational tiers:
1. **Strategic / Executive Level**: High-level financial and operational summaries for management decision-making.
2. **Operational / Administrative Level**: Day-to-day coordination documents for trainers and administrators (e.g., class rosters, debt collection).
3. **Formal Verification Level**: Official external documents certifying trainee accomplishments and compliance.

---

## 2. Summary Matrix of TMIS Reports

| No. | Report Title | Report Classification | Primary Stakeholder | Key Tables Involved | Core Metrics / Outputs |
|:---:|:---|:---|:---|:---|:---|
| **1** | **Course Performance & Revenue Summary** | Strategic / Financial | Executive Directors, Training Managers | `Course`, `Enrollment`, `Payment` | Total Enrolled, Capacity Utilization %, Total Revenue, Outstanding Balance |
| **2** | **Trainee Attendance & Certificate Eligibility** | Operational / Academic | Academic Registrar, Lead Trainers | `Trainee`, `Course`, `Enrollment`, `TrainingSession`, `Attendance` | Attended Sessions, Attendance %, Certification Eligibility Status |
| **3** | **Outstanding Debtors & Defaulters Report** | Financial / Accounts | Accounts & Finance Department | `Trainee`, `Course`, `Enrollment`, `Payment` | Course Fee, Amount Paid, Balance Due, Contact Phone & NIN |
| **4** | **Trainer Workload & Allocation Analysis** | HR / Operations | Training Coordinator, HR Manager | `Staff`, `TrainingSession`, `Course` | Total Sessions, Completed vs. Upcoming Sessions, Unique Courses |
| **5** | **Session Attendance Register (Roster)** | Daily Operational | Class Trainers, Supervisors | `TrainingSession`, `Course`, `Enrollment`, `Trainee`, `Attendance` | Trainee Name, Phone, Attendance Status, Check-in Timestamp |
| **6** | **Verified Certificate Dispatch Document** | Credentialing / Legal | Trainees, Auditing Bodies, Employers | `Certificate`, `Enrollment`, `Trainee`, `Course`, `Staff` | Serial Number, Issue Date, Trainee NIN, Issuing Officer |

---

## 3. Detailed Report Specifications

### Report 1: Course Performance & Revenue Summary
* **Business Objective**: Enables management to assess which training courses generate the highest revenue, identify under-subscribed courses, and track payment collection efficiency.
* **SQL View**: `rpt_course_performance_summary`
* **Underlying SQL Logic**:
```sql
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
```

#### Sample Expected Output:
| CourseID | CourseName | Category | Fee (UGX) | Capacity | Enrolled | Utilization % | Revenue Collected | Outstanding | Status |
|:---:|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 | Basic Food Safety | Food Safety | 150,000.00 | 30 | 1 | 3.3% | 150,000.00 | 0.00 | active |
| 2 | Food Hygiene | Food Safety | 100,000.00 | 25 | 1 | 4.0% | 40,000.00 | 60,000.00 | active |
| 3 | HACCP Fundamentals | Quality Assurance | 300,000.00 | 20 | 0 | 0.0% | 0.00 | 0.00 | active |

---

### Report 2: Trainee Attendance & Certificate Eligibility
* **Business Objective**: Automates the academic policy rule: A trainee is only eligible for a certificate if their attendance is at or above 75% **and** their tuition fees are completely paid.
* **SQL View**: `rpt_trainee_attendance_eligibility`
* **Underlying SQL Logic**:
```sql
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
```

#### Sample Expected Output:
| TraineeName | CourseName | Payment Status | Scheduled Sessions | Attended | Attendance % | Eligibility |
|:---|:---|:---:|:---:|:---:|:---:|:---|
| Demo Trainee | Basic Food Safety | paid | 3 | 3 | 100.0% | **ELIGIBLE** |
| Demo Trainee | Food Hygiene | partially paid | 2 | 1 | 50.0% | **INELIGIBLE (Attendance & Payment Deficit)** |

---

### Report 3: Outstanding Debtors & Defaulters Report
* **Business Objective**: Provides the accounts department with actionable intelligence on trainees with overdue balances, displaying exact amounts owed and primary phone contacts.
* **SQL View**: `rpt_outstanding_debtors`
* **Underlying SQL Logic**:
```sql
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
```

#### Sample Expected Output:
| TraineeName | PhoneNo | Organization | CourseName | Fee (UGX) | Paid (UGX) | Balance Due (UGX) | Status |
|:---|:---:|:---|:---|:---:|:---:|:---:|:---:|
| Demo Trainee | 0700000001 | Demo Food Company | Food Hygiene | 100,000.00 | 40,000.00 | **60,000.00** | partially paid |

---

### Report 4: Trainer Workload & Activity Analysis
* **Business Objective**: Helps management maintain balanced trainer schedules, prevent burnout, and confirm fulfillment of contractual teaching obligations.
* **SQL View**: `rpt_trainer_workload`
* **Underlying SQL Logic**:
```sql
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
```

#### Sample Expected Output:
| StaffID | TrainerName | Department | Assigned Sessions | Completed | Upcoming | Distinct Courses |
|:---:|:---|:---|:---:|:---:|:---:|:---:|
| 1 | Demo Trainer | Training | 3 | 3 | 0 | 1 |

---

### Report 5: Session Attendance Register (Daily Roll Call)
* **Business Objective**: Serves as the real-time class roster for instructors at the beginning of each session.
* **SQL View**: `rpt_session_attendance_register`
* **Underlying SQL Logic**:
```sql
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
```

---

### Report 6: Verified Certificate Dispatch Document
* **Business Objective**: Generates verified data records for the physical printing of official training certificates with unique serial numbers and authorized signatures.
* **SQL View**: `rpt_certificate_dispatch`
* **Underlying SQL Logic**:
```sql
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
```

#### Sample Expected Output:
| SerialNumber | TraineeName | NIN | CourseName | Duration | IssueDate | IssuedBy | Status |
|:---:|:---|:---:|:---|:---:|:---:|:---|:---:|
| DEMO-CERT-001 | Demo Trainee | DEMO-NIN-001 | Basic Food Safety | 3 days | 2026-10-15 | Demo Administrator | issued |

---

## 4. Technical Conclusion

By implementing these reports as database views (`CREATE OR REPLACE VIEW ...`), the TMIS architecture provides:
1. **Separation of Concerns**: Complex join, aggregation, and business calculation logic resides securely in the database layer rather than cluttering frontend application code.
2. **Reusability**: Any user interface (web dashboard, PDF generator, or desktop database tool) can fetch updated report data via a simple `SELECT * FROM view_name;`.
3. **Data Integrity & Security**: User privileges can be granted selectively to view objects without exposing raw underlying transactional tables.

