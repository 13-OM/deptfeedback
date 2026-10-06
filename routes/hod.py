import re
from datetime import datetime

import pandas as pd
from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from decorators import role_required
from models import (
    FeedbackForm,
    FeedbackQuestion,
    Faculty,
    Student,
    Subject,
    User,
    new,
)
from mongo import get_db
from services import (
    active_questions,
    average_rating,
    comments_for_responses,
    completion_for_forms,
    question_averages,
    rating_distribution,
    responses_for_forms,
)
from werkzeug.security import generate_password_hash


bp = Blueprint("hod", __name__, url_prefix="/hod")


def _clean(v):
    return (v or "").strip()
    
def _parse_date(v):
    if not v:
        return None

    try:
        return datetime.strptime(v, "%Y-%m-%d")
    except (TypeError, ValueError):
        return None




def filtered_forms(args):
    forms = []

    faculty = args.get("faculty", "").strip()
    subject = args.get("subject", "").strip()
    sem = args.get("semester", "").strip()
    year = args.get("academic_year", "").strip()
    stype = args.get("subject_type", "").strip()
    code = args.get("subject_code", "").strip()

    for f in FeedbackForm.all({}, [("academic_year", -1)]):
        s = f.subject

        if not s:
            continue

        if faculty.isdigit() and s.faculty_id != int(faculty):
            continue

        if subject.isdigit() and s.id != int(subject):
            continue

        if sem.isdigit() and s.semester != int(sem):
            continue

        if year and f.academic_year != year:
            continue

        if stype and s.subject_type != stype:
            continue

        if code and code.lower() not in s.subject_code.lower():
            continue

        forms.append(f)

    return sorted(
        forms,
        key=lambda f: (
            f.academic_year,
            f.subject.semester,
            f.subject.subject_name,
        ),
        reverse=True,
    )


def _performance_rows(faculty=None):
    out = []

    for s in Subject.all(
        {"status": "Active"},
        [("subject_name", 1)]
    ):
        if faculty and s.faculty_id != faculty.id:
            continue

        rs = responses_for_forms(
            FeedbackForm.all({"subject_id": s.id})
        )

        if rs:
            out.append(
                {
                    "name": s.subject_name,
                    "code": s.subject_code,
                    "faculty": (
                        s.faculty.name
                        if s.faculty
                        else "Unassigned"
                    ),
                    "responses": len(rs),
                    "average": average_rating(rs),
                }
            )

    return out


@bp.get("/dashboard")
@role_required("hod")
def dashboard():
    students = Student.count({"status": "Active"})
    faculty = Faculty.count({"status": "Active"})
    subjects = Subject.count({"status": "Active"})

    forms = FeedbackForm.all()
    responses = responses_for_forms(forms)

    overall = average_rating(responses)
    completion = completion_for_forms(forms)

    faculty_data = []

    for m in Faculty.all(
        {"status": "Active"},
        [("name", 1)]
    ):
        rs = responses_for_forms(
            [
                f
                for f in forms
                if f.subject
                and f.subject.faculty_id == m.id
            ]
        )

        if rs:
            faculty_data.append(
                {
                    "name": m.name,
                    "average": average_rating(rs),
                    "responses": len(rs),
                }
            )

    subject_data = _performance_rows()

    top = sorted(
        subject_data,
        key=lambda x: x["average"],
        reverse=True,
    )[:6]

    return render_template(
        "hod/dashboard.html",
        student_count=students,
        faculty_count=faculty,
        subject_count=subjects,
        response_count=len(responses),
        overall=overall,
        completion=completion,
        faculty_data=faculty_data,
        subject_data=top,
        chart_labels=[
            x["name"] for x in faculty_data
        ],
        chart_values=[
            x["average"] for x in faculty_data
        ],
        subject_labels=[
            x["name"] for x in top
        ],
        subject_values=[
            x["average"] for x in top
        ],
    )


@bp.get("/students")
@role_required("hod")
def students():
    search = _clean(
        request.args.get("q")
    ).lower()

    sem = _clean(
        request.args.get("semester")
    )

    year = _clean(
        request.args.get("academic_year")
    )

    rows = []

    for s in Student.all(
        {},
        [("semester", 1), ("name", 1)]
    ):
        if search and not any(
            search in str(
                getattr(s, k, "")
            ).lower()
            for k in (
                "name",
                "enrollment_no",
                "email",
            )
        ):
            continue

        if sem.isdigit() and s.semester != int(sem):
            continue

        if year and s.academic_year != year:
            continue

        rows.append(s)

    return render_template(
        "hod/students.html",
        students=rows,
        semesters=sorted(
            {
                s.semester
                for s in Student.all()
            }
        ),
        years=sorted(
            {
                s.academic_year
                for s in Student.all()
            },
            reverse=True,
        ),
        import_result=session.pop(
            "import_result",
            None,
        ),
    )


@bp.post("/students")
@role_required("hod")
def add_student():
    enrollment = _clean(
        request.form.get("enrollment_no")
    )

    name = _clean(
        request.form.get("name")
    )

    password = (
        request.form.get("password")
        or "student123"
    )

    email = (
        _clean(request.form.get("email"))
        or None
    )

    dept = (
        _clean(
            request.form.get("department")
        )
        or current_app.config[
            "DEPARTMENT_NAME"
        ]
    )

    year = _clean(
        request.form.get("academic_year")
    )

    sem = _clean(
        request.form.get("semester")
    )

    if (
        not enrollment
        or not name
        or not year
        or not sem.isdigit()
        or not 1 <= int(sem) <= 12
        or len(password) < 6
    ):
        flash(
            "Enter a valid enrollment number, "
            "name, semester, academic year and "
            "password (6+ characters).",
            "error",
        )

        return redirect(
            url_for("hod.students")
        )

    if (
        User.find_one(
            {"username": enrollment}
        )
        or Student.find_one(
            {"enrollment_no": enrollment}
        )
    ):
        flash(
            "That enrollment number is already registered.",
            "error",
        )

        return redirect(
            url_for("hod.students")
        )

    u = new(
        User,
        username=enrollment,
        role="student",
        created_at=__import__(
            "datetime"
        ).datetime.utcnow(),
    )

    u.set_password(password)
    u.save()

    student = new(
        Student,
        user_id=u.id,
        enrollment_no=enrollment,
        name=name,
        semester=int(sem),
        department=dept,
        academic_year=year,
        email=email,
        status="Active",
        subject_ids=[],
    )

    student.save()

    flash(
        f"Student {name} added successfully. "
        "Now assign subjects to the student.",
        "success",
    )

    return redirect(
        url_for(
            "hod.assign_student_subjects",
            student_id=student.id,
        )
    )


@bp.route(
    "/students/<int:student_id>/assign-subjects",
    methods=["GET", "POST"],
)
@role_required("hod")
def assign_student_subjects(student_id):
    student = Student.get(student_id)

    if not student:
        abort(404)

    subjects = [
        s
        for s in Subject.all(
            {"status": "Active"},
            [("subject_name", 1)],
        )
        if (
            s.semester == student.semester
            and s.academic_year
            == student.academic_year
            and s.department.strip().casefold()
            == student.department.strip().casefold()
        )
    ]

    assigned_ids = set(
        getattr(
            student,
            "subject_ids",
            [],
        )
        or []
    )

    if request.method == "POST":
        selected = request.form.getlist(
            "subject_ids"
        )

        try:
            selected_ids = [
                int(x)
                for x in selected
            ]
        except ValueError:
            selected_ids = []

        valid_ids = {
            s.id
            for s in subjects
        }

        selected_ids = [
            subject_id
            for subject_id in selected_ids
            if subject_id in valid_ids
        ]

        student.subject_ids = selected_ids
        student.save()

        flash(
            f"Subjects assigned successfully to "
            f"{student.name}.",
            "success",
        )

        return redirect(
            url_for("hod.students")
        )

    return render_template(
        "hod/assign_subjects.html",
        student=student,
        subjects=subjects,
        assigned_ids=assigned_ids,
    )


@bp.post("/students/<int:student_id>/edit")
@role_required("hod")
def edit_student(student_id):
    s = Student.get(student_id)

    if not s:
        abort(404)

    enrollment = _clean(
        request.form.get("enrollment_no")
    )

    name = _clean(
        request.form.get("name")
    )

    sem = _clean(
        request.form.get("semester")
    )

    year = _clean(
        request.form.get("academic_year")
    )

    if (
        not enrollment
        or not name
        or not sem.isdigit()
        or not year
    ):
        flash(
            "Please provide valid student details.",
            "error",
        )

        return redirect(
            url_for("hod.students")
        )

    existing = Student.find_one(
        {"enrollment_no": enrollment}
    )

    if existing and existing.id != s.id:
        flash(
            "That enrollment number is already assigned "
            "to another student.",
            "error",
        )

        return redirect(
            url_for("hod.students")
        )

    s.enrollment_no = enrollment
    s.name = name
    s.semester = int(sem)

    s.department = (
        _clean(
            request.form.get("department")
        )
        or current_app.config[
            "DEPARTMENT_NAME"
        ]
    )

    s.academic_year = year

    s.email = (
        _clean(
            request.form.get("email")
        )
        or None
    )

    s.status = (
        "Active"
        if request.form.get("status")
        == "Active"
        else "Inactive"
    )

    s.save()

    u = s.user

    if u:
        u.username = enrollment
        u.save()

    flash(
        "Student record updated.",
        "success",
    )

    return redirect(
        url_for("hod.students")
    )


@bp.post("/students/import")
@role_required("hod")
def import_students():
    upload = request.files.get("file")

    if not upload or not upload.filename:
        flash(
            "Choose a CSV or Excel file to import.",
            "error",
        )

        return redirect(
            url_for("hod.students")
        )

    ext = (
        upload.filename.rsplit(
            ".",
            1,
        )[-1].lower()
        if "." in upload.filename
        else ""
    )

    if ext not in {"csv", "xlsx"}:
        flash(
            "Only .csv and .xlsx student lists are supported.",
            "error",
        )

        return redirect(
            url_for("hod.students")
        )

    try:
        frame = (
            pd.read_csv(upload)
            if ext == "csv"
            else pd.read_excel(upload)
        )
    except Exception:
        flash(
            "The uploaded file could not be read. "
            "Check that it is a valid CSV or .xlsx file.",
            "error",
        )

        return redirect(
            url_for("hod.students")
        )

    norm = {
        re.sub(
            r"[^a-z0-9]",
            "",
            str(c).lower(),
        ): c
        for c in frame.columns
    }

    def source(*keys):
        return next(
            (
                norm[k]
                for k in keys
                if k in norm
            ),
            None,
        )

    ec = source(
        "enrollmentno",
        "enrollmentnumber",
        "enrollment",
        "enrollmentid",
        "enrollmentnum",
    )

    nc = source(
        "studentname",
        "name",
        "fullname",
    )

    sc = source(
        "semester",
        "sem",
    )

    dc = source(
        "department",
        "dept",
    )

    yc = source(
        "academicyear",
        "year",
    )

    emc = source(
        "email",
        "emailaddress",
    )

    pc = source(
        "password",
        "pin",
    )

    if not ec or not nc or not sc:
        flash(
            "The file needs columns for Enrollment No, "
            "Student Name and Semester.",
            "error",
        )

        return redirect(
            url_for("hod.students")
        )

    imported = 0
    duplicates = 0
    invalid = 0

    for _, row in frame.iterrows():

        def cell(c, d=""):
            if not c:
                return d

            v = row.get(c, d)

            if pd.isna(v):
                return d

            if (
                isinstance(v, float)
                and v.is_integer()
            ):
                v = int(v)

            return str(v).strip()

        enrollment = re.sub(
            r"\.0$",
            "",
            cell(ec),
        )

        name = cell(nc)
        st = cell(sc)

        dept = cell(
            dc,
            current_app.config[
                "DEPARTMENT_NAME"
            ],
        )

        year = cell(
            yc,
            "2026-27",
        )

        email = (
            cell(emc)
            or None
        )

        password = (
            cell(
                pc,
                "student123",
            )
            or "student123"
        )

        try:
            semester = int(
                float(st)
            )
        except:
            invalid += 1
            continue

        if (
            not enrollment
            or not name
            or not year
            or not 1 <= semester <= 12
            or len(password) < 6
        ):
            invalid += 1
            continue

        if (
            Student.find_one(
                {"enrollment_no": enrollment}
            )
            or User.find_one(
                {"username": enrollment}
            )
        ):
            duplicates += 1
            continue

        u = new(
            User,
            username=enrollment,
            role="student",
            created_at=__import__(
                "datetime"
            ).datetime.utcnow(),
        )

        u.set_password(password)
        u.save()

        new(
            Student,
            user_id=u.id,
            enrollment_no=enrollment,
            name=name,
            semester=semester,
            department=(
                dept
                or current_app.config[
                    "DEPARTMENT_NAME"
                ]
            ),
            academic_year=year,
            email=email,
            status="Active",
            subject_ids=[],
        ).save()

        imported += 1

    session["import_result"] = {
        "total": len(frame),
        "imported": imported,
        "duplicates": duplicates,
        "invalid": invalid,
    }

    flash(
        f"Import finished: {imported} imported, "
        f"{duplicates} duplicates, "
        f"{invalid} invalid.",
        "success"
        if imported
        else "warning",
    )

    return redirect(
        url_for("hod.students")
    )


@bp.get("/faculty")
@role_required("hod")
def faculty_list():
    q = _clean(
        request.args.get("q")
    ).lower()

    members = [
        f
        for f in Faculty.all(
            {},
            [("name", 1)],
        )
        if (
            not q
            or any(
                q
                in str(
                    getattr(f, k, "")
                ).lower()
                for k in (
                    "name",
                    "faculty_code",
                    "email",
                )
            )
        )
    ]

    return render_template(
        "hod/faculty.html",
        faculty=members,
    )


@bp.post("/faculty")
@role_required("hod")
def add_faculty():
    name = _clean(
        request.form.get("name")
    )

    code = _clean(
        request.form.get("faculty_code")
    )

    email = _clean(
        request.form.get("email")
    )

    username = (
        _clean(
            request.form.get("username")
        )
        or code.lower()
    )

    password = (
        request.form.get("password")
        or "faculty123"
    )

    dept = (
        _clean(
            request.form.get("department")
        )
        or current_app.config[
            "DEPARTMENT_NAME"
        ]
    )

    designation = (
        _clean(
            request.form.get("designation")
        )
        or "Assistant Professor"
    )

    if (
        not name
        or not code
        or not email
        or not username
        or len(password) < 6
    ):
        flash(
            "Name, faculty ID, email, login username "
            "and a 6+ character password are required.",
            "error",
        )

        return redirect(
            url_for("hod.faculty_list")
        )

    if (
        User.find_one(
            {"username": username}
        )
        or Faculty.find_one(
            {"faculty_code": code}
        )
    ):
        flash(
            "That faculty login or faculty ID already exists.",
            "error",
        )

        return redirect(
            url_for("hod.faculty_list")
        )

    u = new(
        User,
        username=username,
        role="faculty",
        created_at=__import__(
            "datetime"
        ).datetime.utcnow(),
    )

    u.set_password(password)
    u.save()

    new(
        Faculty,
        user_id=u.id,
        name=name,
        faculty_code=code,
        email=email,
        department=dept,
        designation=designation,
        status="Active",
    ).save()

    flash(
        f"Faculty member {name} added successfully.",
        "success",
    )

    return redirect(
        url_for("hod.faculty_list")
    )


@bp.post("/faculty/<int:faculty_id>/edit")
@role_required("hod")
def edit_faculty(faculty_id):
    m = Faculty.get(faculty_id)

    if not m:
        abort(404)

    name = _clean(
        request.form.get("name")
    )

    code = _clean(
        request.form.get("faculty_code")
    )

    username = _clean(
        request.form.get("username")
    )

    email = _clean(
        request.form.get("email")
    )

    if (
        not name
        or not code
        or not username
        or not email
    ):
        flash(
            "Please complete the required faculty details.",
            "error",
        )

        return redirect(
            url_for("hod.faculty_list")
        )

    m.name = name
    m.faculty_code = code
    m.email = email

    m.department = (
        _clean(
            request.form.get("department")
        )
        or current_app.config[
            "DEPARTMENT_NAME"
        ]
    )

    m.designation = (
        _clean(
            request.form.get("designation")
        )
        or "Assistant Professor"
    )

    m.status = (
        "Active"
        if request.form.get("status")
        == "Active"
        else "Inactive"
    )

    m.save()

    u = m.user

    if u:
        u.username = username
        u.save()

    flash(
        "Faculty record updated.",
        "success",
    )

    return redirect(
        url_for("hod.faculty_list")
    )


@bp.get("/subjects")
@role_required("hod")
def subject_list():
    q = _clean(
        request.args.get("q")
    ).lower()

    rows = [
        s
        for s in Subject.all(
            {},
            [
                ("academic_year", -1),
                ("semester", 1),
                ("subject_name", 1),
            ],
        )
        if (
            not q
            or q in s.subject_name.lower()
            or q in s.subject_code.lower()
        )
    ]

    return render_template(
        "hod/subjects.html",
        subjects=rows,
        faculty=Faculty.all(
            {"status": "Active"},
            [("name", 1)],
        ),
    )


@bp.post("/subjects")
@role_required("hod")
def add_subject():
    name = _clean(
        request.form.get("subject_name")
    )

    code = _clean(
        request.form.get("subject_code")
    )

    sem = _clean(
        request.form.get("semester")
    )

    year = _clean(
        request.form.get("academic_year")
    )

    fid = _clean(
        request.form.get("faculty_id")
    )

    dept = (
        _clean(
            request.form.get("department")
        )
        or current_app.config[
            "DEPARTMENT_NAME"
        ]
    )

    kind = (
        _clean(
            request.form.get("subject_type")
        )
        or "Theory"
    )

    credits = (
        _clean(
            request.form.get("credits")
        )
        or "3"
    )

    if (
        not name
        or not code
        or not sem.isdigit()
        or not year
        or not credits.isdigit()
        or not 1 <= int(sem) <= 12
        or int(credits) < 1
    ):
        flash(
            "Enter valid subject details.",
            "error",
        )

        return redirect(
            url_for("hod.subject_list")
        )

    member = (
        Faculty.get(int(fid))
        if fid.isdigit()
        else None
    )

    if fid and not member:
        flash(
            "Select a valid faculty member.",
            "error",
        )

        return redirect(
            url_for("hod.subject_list")
        )

    if Subject.find_one(
        {
            "subject_code": code,
            "semester": int(sem),
            "academic_year": year,
        }
    ):
        flash(
            "That subject code/year/semester already exists.",
            "error",
        )

        return redirect(
            url_for("hod.subject_list")
        )

    new(
        Subject,
        subject_name=name,
        subject_code=code,
        semester=int(sem),
        faculty_id=(
            member.id
            if member
            else None
        ),
        academic_year=year,
        department=dept,
        subject_type=(
            kind
            if kind
            in {
                "Theory",
                "Practical",
                "Laboratory",
                "Elective",
            }
            else "Theory"
        ),
        credits=int(credits),
        status="Active",
    ).save()

    flash(
        "Subject added successfully.",
        "success",
    )

    return redirect(
        url_for("hod.subject_list")
    )


@bp.post("/subjects/<int:subject_id>/edit")
@role_required("hod")
def edit_subject(subject_id):
    s = Subject.get(subject_id)

    if not s:
        abort(404)

    name = _clean(
        request.form.get("subject_name")
    )

    code = _clean(
        request.form.get("subject_code")
    )

    sem = _clean(
        request.form.get("semester")
    )

    year = _clean(
        request.form.get("academic_year")
    )

    credits = (
        _clean(
            request.form.get("credits")
        )
        or "3"
    )

    fid = _clean(
        request.form.get("faculty_id")
    )

    member = (
        Faculty.get(int(fid))
        if fid.isdigit()
        else None
    )

    if (
        not name
        or not code
        or not sem.isdigit()
        or not year
        or not credits.isdigit()
    ):
        flash(
            "Please provide valid subject details.",
            "error",
        )

        return redirect(
            url_for("hod.subject_list")
        )

    s.subject_name = name
    s.subject_code = code
    s.semester = int(sem)
    s.academic_year = year
    s.faculty_id = (
        member.id
        if member
        else None
    )

    s.department = (
        _clean(
            request.form.get("department")
        )
        or current_app.config[
            "DEPARTMENT_NAME"
        ]
    )

    s.subject_type = request.form.get(
        "subject_type",
        "Theory",
    )

    s.credits = int(credits)

    s.status = (
        "Active"
        if request.form.get("status")
        == "Active"
        else "Inactive"
    )

    s.save()

    flash(
        "Subject updated successfully.",
        "success",
    )

    return redirect(
        url_for("hod.subject_list")
    )


@bp.get("/forms")
@role_required("hod")
def forms():
    return render_template(
        "hod/forms.html",
        forms=FeedbackForm.all(
            {},
            [("academic_year", -1)],
        ),
        subjects=Subject.all(
            {"status": "Active"},
            [("subject_name", 1)],
        ),
    )

@bp.post("/forms/create")
@role_required("hod")
def create_form():

    sid = _clean(request.form.get("subject_id"))

    s = Subject.get(int(sid)) if sid.isdigit() else None

    if not s:
        flash(
            "Select a subject to create a feedback form.",
            "error"
        )
        return redirect(url_for("hod.forms"))

    year = (
        _clean(request.form.get("academic_year"))
        or s.academic_year
    )

    # Prevent duplicate feedback forms
    if FeedbackForm.find_one({
        "subject_id": s.id,
        "academic_year": year
    }):
        flash(
            "A feedback form already exists for that subject and academic year.",
            "warning"
        )
        return redirect(url_for("hod.forms"))

    # Convert HTML date values into MongoDB-compatible datetime
    start = _parse_date(
        request.form.get("start_date")
    )

    end = _parse_date(
        request.form.get("end_date")
    )

    status = request.form.get(
        "status",
        "Draft"
    )

    if status not in {
        "Draft",
        "Active",
        "Closed",
        "Archived"
    }:
        status = "Draft"

    form = new(
        FeedbackForm,
        subject_id=s.id,
        academic_year=year,
        start_date=start,
        end_date=end,
        status=status
    )

    form.save()

    flash(
        "Feedback form created successfully.",
        "success"
    )

    return redirect(
        url_for("hod.forms")
    )



@bp.post("/forms/<int:form_id>/update")
@role_required("hod")
def update_form(form_id):

    f = FeedbackForm.get(form_id)

    if not f:
        abort(404)

    status = request.form.get(
        "status",
        "Draft"
    )

    if status not in {
        "Draft",
        "Active",
        "Closed",
        "Archived"
    }:
        status = "Draft"

    f.status = status

    # Convert HTML date values to datetime
    f.start_date = _parse_date(
        request.form.get("start_date")
    )

    f.end_date = _parse_date(
        request.form.get("end_date")
    )

    f.save()

    flash(
        "Feedback form settings saved.",
        "success"
    )

    return redirect(
        url_for("hod.forms")
    )

@bp.get("/analytics")
@role_required("hod")
def analytics():
    return redirect(url_for("hod.dashboard"))


@bp.get("/faculty-performance")
@role_required("hod")
def faculty_performance():
    rows = []

    for m in Faculty.all(
        {},
        [("name", 1)],
    ):
        forms_m = [
            f
            for f in FeedbackForm.all()
            if f.subject
            and f.subject.faculty_id == m.id
        ]

        rs = responses_for_forms(
            forms_m
        )

        rows.append(
            {
                "faculty": m,
                "subjects": len(
                    Subject.all(
                        {"faculty_id": m.id}
                    )
                ),
                "responses": len(rs),
                "average": average_rating(rs),
            }
        )

    return render_template(
        "hod/performance.html",
        title="Faculty performance",
        subtitle=(
            "Compare anonymous response averages "
            "across the department."
        ),
        rows=rows,
        kind="faculty",
        chart_labels=[
            r["faculty"].name
            for r in rows
            if r["responses"]
        ],
        chart_values=[
            r["average"]
            for r in rows
            if r["responses"]
        ],
    )


@bp.get("/subject-performance")
@role_required("hod")
def subject_performance():
    rows = []

    for s in Subject.all(
        {},
        [("subject_name", 1)],
    ):
        rs = responses_for_forms(
            FeedbackForm.all(
                {"subject_id": s.id}
            )
        )

        rows.append(
            {
                "subject": s,
                "responses": len(rs),
                "average": average_rating(rs),
            }
        )

    return render_template(
        "hod/performance.html",
        title="Subject performance",
        subtitle=(
            "See how each subject is rated "
            "across its feedback forms."
        ),
        rows=rows,
        kind="subject",
        chart_labels=[
            r["subject"].subject_name
            for r in rows
            if r["responses"]
        ],
        chart_values=[
            r["average"]
            for r in rows
            if r["responses"]
        ],
    )


@bp.get("/questions")
@role_required("hod")
def questions():
    return render_template(
        "hod/questions.html",
        questions=FeedbackQuestion.all(
            {},
            [("question_order", 1)],
        ),
    )


@bp.post("/questions")
@role_required("hod")
def save_question():
    qid = _clean(
        request.form.get("question_id")
    )

    text = _clean(
        request.form.get("question_text")
    )

    category = (
        _clean(
            request.form.get("category")
        )
        or "Subject"
    )

    order = (
        _clean(
            request.form.get("question_order")
        )
        or "99"
    )

    try:
        order = int(order)
    except:
        order = 99

    if qid.isdigit():
        q = FeedbackQuestion.get(
            int(qid)
        )

        if not q:
            abort(404)

        if not text:
            q.status = "Inactive"

            flash(
                "Question deactivated.",
                "success",
            )

        else:
            q.question_text = text
            q.category = category
            q.question_order = order

            q.status = (
                "Active"
                if request.form.get("status")
                == "Active"
                else "Inactive"
            )

            q.is_comment = (
                request.form.get("is_comment")
                == "yes"
            )

            flash(
                "Question settings saved.",
                "success",
            )

        q.save()

    else:
        if not text:
            flash(
                "Enter a question before saving.",
                "error",
            )

            return redirect(
                url_for("hod.questions")
            )

        new(
            FeedbackQuestion,
            question_text=text,
            category=category,
            question_order=order,
            status="Active",
            is_comment=(
                request.form.get(
                    "is_comment"
                )
                == "yes"
            ),
        ).save()

        flash(
            "Feedback question added.",
            "success",
        )

    return redirect(
        url_for("hod.questions")
    )


@bp.get("/reports")
@role_required("hod")
def reports():
    return render_template(
        "hod/reports.html"
    )
