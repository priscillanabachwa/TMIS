import csv
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import connection
from django.http import HttpResponse
from django.shortcuts import render
REPORTS = {
'courses':('Course performance',"""
SELECT c.CourseName AS Course, c.MaximumCapacity AS Capacity,
COALESCE(e.Enrolled,0) AS Enrolled, COALESCE(p.Revenue,0) AS RevenueUGX,
COALESCE(e.Enrolled,0)*c.CourseFee-COALESCE(p.Revenue,0) AS BalanceUGX
FROM Course c
LEFT JOIN (SELECT CourseID,COUNT(*) AS Enrolled FROM Enrollment WHERE EnrollmentStatus IN ('pending','active','completed') GROUP BY CourseID) e ON e.CourseID=c.CourseID
LEFT JOIN (SELECT e.CourseID,SUM(p.AmountPaid) AS Revenue FROM Payment p JOIN Enrollment e ON e.EnrollmentID=p.EnrollmentID WHERE p.PaymentStatus='confirmed' AND e.EnrollmentStatus IN ('pending','active','completed') GROUP BY e.CourseID) p ON p.CourseID=c.CourseID ORDER BY c.CourseName"""),
'debtors':('Outstanding balances',"""
SELECT t.FullName AS Trainee,c.CourseName AS Course,t.PhoneNo AS Phone,
c.CourseFee AS FeeUGX,COALESCE(p.TotalPaid,0) AS PaidUGX,c.CourseFee-COALESCE(p.TotalPaid,0) AS BalanceUGX
FROM Enrollment e JOIN Trainee t ON t.TraineeID=e.TraineeID JOIN Course c ON c.CourseID=e.CourseID
LEFT JOIN (SELECT EnrollmentID,SUM(AmountPaid) AS TotalPaid FROM Payment WHERE PaymentStatus='confirmed' GROUP BY EnrollmentID) p ON p.EnrollmentID=e.EnrollmentID
WHERE e.EnrollmentStatus IN ('pending','active','completed') AND c.CourseFee>COALESCE(p.TotalPaid,0) ORDER BY t.FullName"""),
'attendance':('Attendance and certificate eligibility',"""
SELECT t.FullName AS Trainee,c.CourseName AS Course,e.EnrollmentStatus AS Enrollment,
COALESCE(s.Completed,0) AS CompletedSessions,COALESCE(a.Present,0) AS PresentSessions,
CASE WHEN COALESCE(s.Completed,0)=0 THEN 0 ELSE ROUND(100.0*COALESCE(a.Present,0)/s.Completed,1) END AS AttendancePercent,
CASE WHEN e.EnrollmentStatus='completed' AND COALESCE(s.Completed,0)>0 AND COALESCE(a.Present,0)*4>=s.Completed*3 AND COALESCE(s.Outstanding,0)=0 AND COALESCE(p.Paid,0)>=c.CourseFee THEN 'Eligible' ELSE 'Not eligible' END AS Eligibility
FROM Enrollment e JOIN Trainee t ON t.TraineeID=e.TraineeID JOIN Course c ON c.CourseID=e.CourseID
LEFT JOIN (SELECT CourseID,SUM(CASE WHEN SessionStatus='completed' THEN 1 ELSE 0 END) AS Completed,SUM(CASE WHEN SessionStatus IN ('scheduled','postponed') THEN 1 ELSE 0 END) AS Outstanding FROM TrainingSession GROUP BY CourseID) s ON s.CourseID=e.CourseID
LEFT JOIN (SELECT ts.CourseID,a.TraineeID,COUNT(*) AS Present FROM Attendance a JOIN TrainingSession ts ON ts.SessionID=a.SessionID WHERE ts.SessionStatus='completed' AND a.AttendanceStatus='present' GROUP BY ts.CourseID,a.TraineeID) a ON a.CourseID=e.CourseID AND a.TraineeID=e.TraineeID
LEFT JOIN (SELECT EnrollmentID,SUM(AmountPaid) AS Paid FROM Payment WHERE PaymentStatus='confirmed' GROUP BY EnrollmentID) p ON p.EnrollmentID=e.EnrollmentID
ORDER BY t.FullName,c.CourseName"""),
'workload':('Trainer workload',"""
SELECT st.FullName AS Trainer,COUNT(ts.SessionID) AS Assigned,
SUM(CASE WHEN ts.SessionStatus='completed' THEN 1 ELSE 0 END) AS Completed,
SUM(CASE WHEN ts.SessionStatus='scheduled' THEN 1 ELSE 0 END) AS Scheduled
FROM Staff st LEFT JOIN TrainingSession ts ON ts.TrainerID=st.StaffID
WHERE st.Role='trainer' GROUP BY st.StaffID,st.FullName ORDER BY st.FullName"""),
'register':('Session attendance register',"""
SELECT ts.SessionID AS Session,c.CourseName AS Course,ts.SessionDate AS SessionDate,t.FullName AS Trainee,
COALESCE(a.AttendanceStatus,'not recorded') AS Attendance,a.CheckInTime AS CheckIn
FROM TrainingSession ts JOIN Course c ON c.CourseID=ts.CourseID
JOIN Enrollment e ON e.CourseID=ts.CourseID AND e.EnrollmentStatus IN ('pending','active','completed')
JOIN Trainee t ON t.TraineeID=e.TraineeID
LEFT JOIN Attendance a ON a.SessionID=ts.SessionID AND a.TraineeID=t.TraineeID
WHERE ts.SessionStatus IN ('scheduled','completed') ORDER BY ts.SessionDate DESC,t.FullName"""),
'certificates':('Certificate dispatch',"""
SELECT cert.SerialNumber AS SerialNumber,t.FullName AS Trainee,c.CourseName AS Course,
cert.IssueDate AS IssueDate,st.FullName AS IssuedBy,cert.CertificateStatus AS Status
FROM Certificate cert JOIN Enrollment e ON e.EnrollmentID=cert.EnrollmentID
JOIN Trainee t ON t.TraineeID=e.TraineeID JOIN Course c ON c.CourseID=e.CourseID
JOIN Staff st ON st.StaffID=cert.IssuedBy ORDER BY cert.IssueDate DESC""")}

def csv_cell(value):
    if isinstance(value,str) and value.lstrip().startswith(('=','+','-','@','\t','\r','\n')): return "'"+value
    return value

@login_required
def report(request):
    selected=request.GET.get('report','courses')
    if selected not in REPORTS: selected='courses'
    title,sql=REPORTS[selected]
    with connection.cursor() as cur:
        cur.execute(sql)
        headers=[col[0] for col in cur.description]
        rows=cur.fetchall()
    q=request.GET.get('q','').strip()
    if q: rows=[row for row in rows if q.lower() in ' '.join(str(v or '') for v in row).lower()]
    if request.GET.get('export')=='csv':
        response=HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition']=f'attachment; filename="tmis_{selected}.csv"'
        response.write('\ufeff')
        writer=csv.writer(response)
        writer.writerow(headers)
        writer.writerows([[csv_cell(v) for v in row] for row in rows])
        return response
    printable=request.GET.get('print')=='1'
    page=Paginator(rows,20).get_page(request.GET.get('page'))
    return render(request,'training/reports.html',{'section':'reports','title':title,'reports':[(k,v[0]) for k,v in REPORTS.items()],'selected':selected,'headers':headers,'rows':rows if printable else page,'page':page,'q':q,'total':len(rows),'printable':printable})
