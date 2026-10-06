from flask import Blueprint, render_template, redirect, url_for, flash, abort, request
from flask_login import current_user

from models.core import (
    Student,
    Subject,
    FeedbackForm,
    FeedbackResponse,
    SubmissionTracking,
)

from auth import role_required
from services import is_form_open


bp = Blueprint("student", __name__, url_prefix="/student")


# ============================================================
# CURRENT STUDENT
# ============================================================

def get_current_student():
    """Return the Student record linked to the logged-in user."""

    student = Student.first({
        "user_id": current_user.id
    })

    if not student:
        abort(404, description="Student profile not found.")

    return student


# ============================================================
# ASSIGNED SUBJECT IDS
# ============================================================

def student_assigned_subject_ids(student):
    """
    Return the subject IDs explicitly assigned to this student.

    Handles both integer and string IDs safely.
    """

    raw_ids = getattr(student, "subject_ids", []) or []

    result = set()

    for value in raw_ids:
        try:
            result.add(int(value))
        except (TypeError, ValueError):
            continue

    return result


# ============================================================
# GET ASSIGNED SUBJECTS
# ============================================================

def get_assigned_subjects(student):
    """
    Return ONLY subjects assigned to this student.

    Assignment is based on student.subject_ids.
    Additional semester, academic year and department
    validation is applied.
    """

    assigned_ids = student_assigned_subject_ids(student)

    if not assigned_ids:
        return []

    subjects = Subject.all({
        "status": "Active"
    })

    result = []

    for subject in subjects:

        try:
            subject_id = int(subject.id)
        except (TypeError, ValueError):
            continue

        # Subject must be explicitly assigned
        if subject_id not in assigned_ids:
            continue

        # ----------------------------------------------------
        # SEMESTER CHECK
        # ----------------------------------------------------

        if student.semester is not None:

            try:
                if int(subject.semester) != int(student.semester):
                    continue
            except (TypeError, ValueError):
                continue

        # ----------------------------------------------------
        # ACADEMIC YEAR CHECK
        # ----------------------------------------------------

        if student.academic_year:

            student_year = str(
                student.academic_year
            ).strip()

            subject_year = str(
                subject.academic_year
            ).strip()

            if student_year != subject_year:
                continue

        # ----------------------------------------------------
        # DEPARTMENT CHECK
        # ----------------------------------------------------

        if student.department:

            student_dept = str(
                student.department
            ).strip().casefold()

            subject_dept = str(
                subject.department
            ).strip().casefold()

            if student_dept != subject_dept:
                continue

        result.append(subject)

    return result


# ============================================================
# GET FEEDBACK FORMS FOR STUDENT
# ============================================================

def get_forms_for_student(student):
    """
    Return active feedback forms belonging ONLY to subjects
    assigned to this student.
    """

    assigned_subjects = get_assigned_subjects(student)

    if not assigned_subjects:
        return []

    assigned_ids = {
        int(subject.id)
        for subject in assigned_subjects
    }

    forms = FeedbackForm.all({
        "status": "Active"
    })

    result = []

    for form in forms:

        subject = form.subject

        if not subject:
            continue

        try:
            subject_id = int(subject.id)
        except (TypeError, ValueError):
            continue

        # Form must belong to assigned subject
        if subject_id not in assigned_ids:
            continue

        # ----------------------------------------------------
        # ACADEMIC YEAR CHECK
        # ----------------------------------------------------

        if form.academic_year:

            form_year = str(
                form.academic_year
            ).strip()

            student_year = str(
                student.academic_year
            ).strip()

            if form_year != student_year:
                continue

        result.append(form)

    return result


# ============================================================
# SUBMISSION CHECK
# ============================================================

def has_submitted(student, form):
    """
    Check whether this student has already submitted
    this feedback form.
    """

    tracking = SubmissionTracking.first({
        "student_id": student.id,
        "feedback_form_id": form.id,
    })

    return tracking is not None


# ============================================================
# STUDENT DASHBOARD
# ============================================================

@bp.get("/dashboard")
@role_required("student")
def dashboard():

    student = get_current_student()

    # --------------------------------------------------------
    # GET ASSIGNED SUBJECTS
    # --------------------------------------------------------

    assigned_subjects = get_assigned_subjects(student)

    # --------------------------------------------------------
    # GET ACTIVE FORMS
    # --------------------------------------------------------

    forms = get_forms_for_student(student)

    # --------------------------------------------------------
    # BUILD ITEMS FOR DASHBOARD
    # --------------------------------------------------------

    items = []

    for form in forms:

        subject = form.subject

        if not subject:
            continue

        submitted = has_submitted(
            student,
            form
        )

        open_status = False

        try:
            open_status = is_form_open(form)
        except Exception:
            open_status = False

        if submitted:
            state = "Completed"

        elif open_status:
            state = "Pending"

        else:
            state = "Not Available"

        items.append({
            "form": form,
            "subject": subject,
            "submitted": submitted,
            "done": submitted,
            "open": open_status,
            "state": state,
        })

    # --------------------------------------------------------
    # IMPORTANT
    #
    # The dashboard template uses "items".
    # Calculate statistics from the SAME items list.
    # --------------------------------------------------------

    total = len(items)

    completed = sum(
        1
        for item in items
        if item["state"] == "Completed"
    )

    pending = sum(
        1
        for item in items
        if item["state"] == "Pending"
    )

    if total > 0:
        completion = round(
            (completed / total) * 100
        )
    else:
        completion = 0

    # --------------------------------------------------------
    # RENDER DASHBOARD
    # --------------------------------------------------------

    return render_template(
        "student/dashboard.html",

        student=student,

        # Assigned subjects
        subjects=assigned_subjects,
        assigned_subjects=assigned_subjects,

        # Dashboard rows
        items=items,

        # Statistics
        total=total,
        completed=completed,
        pending=pending,
        completion=completion,

        # Additional variables
        forms=forms,
        submitted_count=completed,
        pending_count=pending,
        subject_count=len(assigned_subjects),
    )


# ============================================================
# SUBJECTS
# ============================================================

@bp.get("/subjects")
@role_required("student")
def subjects():

    return redirect(
        url_for("student.dashboard")
    )


# ============================================================
# FEEDBACK FORM
# ============================================================

@bp.route(
    "/feedback/<int:form_id>",
    methods=["GET", "POST"]
)
@role_required("student")
def feedback(form_id):

    student = get_current_student()

    form = FeedbackForm.get(form_id)

    if not form:
        abort(404)

    subject = form.subject

    if not subject:
        abort(404)

    # --------------------------------------------------------
    # ASSIGNMENT CHECK
    # --------------------------------------------------------

    assigned_ids = student_assigned_subject_ids(
        student
    )

    try:
        subject_id = int(subject.id)
    except (TypeError, ValueError):
        abort(404)

    if subject_id not in assigned_ids:

        flash(
            "You are not assigned to this subject.",
            "error"
        )

        return redirect(
            url_for("student.dashboard")
        )

    # --------------------------------------------------------
    # SEMESTER CHECK
    # --------------------------------------------------------

    if student.semester is not None:

        try:

            if int(subject.semester) != int(
                student.semester
            ):

                flash(
                    "This subject is not assigned to your semester.",
                    "error"
                )

                return redirect(
                    url_for("student.dashboard")
                )

        except (TypeError, ValueError):

            flash(
                "Invalid semester information.",
                "error"
            )

            return redirect(
                url_for("student.dashboard")
            )

    # --------------------------------------------------------
    # DEPARTMENT CHECK
    # --------------------------------------------------------

    if student.department:

        student_dept = str(
            student.department
        ).strip().casefold()

        subject_dept = str(
            subject.department
        ).strip().casefold()

        if student_dept != subject_dept:

            flash(
                "This subject is not assigned to your department.",
                "error"
            )

            return redirect(
                url_for("student.dashboard")
            )

    # --------------------------------------------------------
    # DUPLICATE SUBMISSION CHECK
    # --------------------------------------------------------

    if has_submitted(student, form):

        flash(
            "You have already submitted feedback for this subject.",
            "info"
        )

        return redirect(
            url_for("student.dashboard")
        )

    # --------------------------------------------------------
    # FORM OPEN CHECK
    # --------------------------------------------------------

    if not is_form_open(form):

        flash(
            "This feedback form is currently closed.",
            "error"
        )

        return redirect(
            url_for("student.dashboard")
        )

    # --------------------------------------------------------
    # QUESTIONS
    # --------------------------------------------------------

    questions = form.questions

    # ========================================================
    # POST
    # ========================================================

    if request.method == "POST":

        ratings = {}

        # ----------------------------------------------------
        # VALIDATE RATINGS
        # ----------------------------------------------------

        for question in questions:

            value = request.form.get(
                f"question_{question.id}"
            )

            if not value:

                flash(
                    "Please answer all required questions.",
                    "error"
                )

                return render_template(
                    "student/feedback.html",
                    student=student,
                    form=form,
                    subject=subject,
                    questions=questions,
                )

            try:

                rating = int(value)

            except (TypeError, ValueError):

                flash(
                    "Invalid rating.",
                    "error"
                )

                return render_template(
                    "student/feedback.html",
                    student=student,
                    form=form,
                    subject=subject,
                    questions=questions,
                )

            if rating < 1 or rating > 5:

                flash(
                    "Rating must be between 1 and 5.",
                    "error"
                )

                return render_template(
                    "student/feedback.html",
                    student=student,
                    form=form,
                    subject=subject,
                    questions=questions,
                )

            ratings[question.id] = rating

        # ----------------------------------------------------
        # COMMENT
        # ----------------------------------------------------

        comment = request.form.get(
            "comment",
            ""
        ).strip()

        # ====================================================
        # CREATE ANONYMOUS RESPONSE
        # ====================================================

        response = FeedbackResponse(
            feedback_form_id=form.id,
            anonymous_reference=(
                FeedbackResponse.generate_anonymous_reference()
            ),
        )

        response.save()

        # ----------------------------------------------------
        # SAVE ANSWERS
        # ----------------------------------------------------

        for question in questions:

            response.add_answer(
                question_id=question.id,
                rating=ratings[question.id],
                comment=(
                    comment
                    if questions
                    and question.id == questions[-1].id
                    else ""
                ),
            )

        # ====================================================
        # SAVE SUBMISSION TRACKING
        # ====================================================

        tracking = SubmissionTracking(
            student_id=student.id,
            feedback_form_id=form.id,
        )

        tracking.save()

        # ----------------------------------------------------
        # SUCCESS
        # ----------------------------------------------------

        flash(
            "Feedback submitted successfully and anonymously.",
            "success"
        )

        return redirect(
            url_for(
                "student.success",
                form_id=form.id
            )
        )

    # ========================================================
    # GET
    # ========================================================

    return render_template(
        "student/feedback.html",
        student=student,
        form=form,
        subject=subject,
        questions=questions,
    )


# ============================================================
# SUCCESS PAGE
# ============================================================

@bp.get("/success/<int:form_id>")
@role_required("student")
def success(form_id):

    student = get_current_student()

    form = FeedbackForm.get(form_id)

    if not form:
        abort(404)

    return render_template(
        "student/success.html",
        student=student,
        form=form,
        subject=form.subject,
    )
