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


def get_current_student():
    """Return the Student record linked to the logged-in user."""
    student = Student.first({"user_id": current_user.id})

    if not student:
        abort(404, description="Student profile not found.")

    return student


def student_assigned_subject_ids(student):
    """Return assigned subject IDs as integers."""
    raw_ids = getattr(student, "subject_ids", []) or []

    result = set()

    for value in raw_ids:
        try:
            result.add(int(value))
        except (TypeError, ValueError):
            continue

    return result


def get_assigned_subjects(student):
    """
    Get ONLY the subjects explicitly assigned to this student.
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

        if subject_id not in assigned_ids:
            continue

        # Extra academic validation
        if student.semester is not None:
            if int(subject.semester) != int(student.semester):
                continue

        if student.academic_year:
            if str(subject.academic_year).strip() != str(student.academic_year).strip():
                continue

        if student.department:
            student_dept = str(student.department).strip().casefold()
            subject_dept = str(subject.department).strip().casefold()

            if student_dept != subject_dept:
                continue

        result.append(subject)

    return result


def get_forms_for_student(student):
    """
    Return active feedback forms belonging ONLY to subjects
    assigned to this student.
    """
    assigned_subjects = get_assigned_subjects(student)

    if not assigned_subjects:
        return []

    assigned_ids = {int(subject.id) for subject in assigned_subjects}

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

        if subject_id not in assigned_ids:
            continue

        # Academic year check
        if form.academic_year:
            if str(form.academic_year).strip() != str(student.academic_year).strip():
                continue

        result.append(form)

    return result


def has_submitted(student, form):
    """Check whether this student already submitted this feedback form."""
    tracking = SubmissionTracking.first({
        "student_id": student.id,
        "feedback_form_id": form.id,
    })

    return tracking is not None


@bp.get("/dashboard")
@role_required("student")
def dashboard():
    student = get_current_student()

    assigned_subjects = get_assigned_subjects(student)
    forms = get_forms_for_student(student)

    form_data = []

    for form in forms:
        form_data.append({
            "form": form,
            "subject": form.subject,
            "submitted": has_submitted(student, form),
            "open": is_form_open(form),
        })

    submitted_count = sum(
        1 for item in form_data
        if item["submitted"]
    )

    pending_count = sum(
        1 for item in form_data
        if not item["submitted"]
    )

    return render_template(
        "student/dashboard.html",
        student=student,
        subjects=assigned_subjects,
        forms=form_data,
        assigned_subjects=assigned_subjects,
        submitted_count=submitted_count,
        pending_count=pending_count,
        subject_count=len(assigned_subjects),
    )


@bp.get("/subjects")
@role_required("student")
def subjects():
    return redirect(url_for("student.dashboard"))


@bp.route("/feedback/<int:form_id>", methods=["GET", "POST"])
@role_required("student")
def feedback(form_id):
    student = get_current_student()

    form = FeedbackForm.get(form_id)

    if not form:
        abort(404)

    subject = form.subject

    if not subject:
        abort(404)

    # IMPORTANT:
    # Student can submit feedback ONLY for an assigned subject.
    assigned_ids = student_assigned_subject_ids(student)

    if int(subject.id) not in assigned_ids:
        flash(
            "You are not assigned to this subject.",
            "error"
        )
        return redirect(url_for("student.dashboard"))

    # Academic validation
    if student.semester is not None:
        if int(subject.semester) != int(student.semester):
            flash("This subject is not assigned to your semester.", "error")
            return redirect(url_for("student.dashboard"))

    if student.department:
        student_dept = str(student.department).strip().casefold()
        subject_dept = str(subject.department).strip().casefold()

        if student_dept != subject_dept:
            flash("This subject is not assigned to your department.", "error")
            return redirect(url_for("student.dashboard"))

    if has_submitted(student, form):
        flash(
            "You have already submitted feedback for this subject.",
            "info"
        )
        return redirect(url_for("student.dashboard"))

    if not is_form_open(form):
        flash(
            "This feedback form is currently closed.",
            "error"
        )
        return redirect(url_for("student.dashboard"))

    questions = form.questions

    if request.method == "POST":

        ratings = {}

        for question in questions:
            value = request.form.get(f"question_{question.id}")

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
            except ValueError:
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

        comment = request.form.get("comment", "").strip()

        # ---------------------------------------------------------
        # ANONYMOUS RESPONSE
        # ---------------------------------------------------------
        response = FeedbackResponse(
            feedback_form_id=form.id,
            anonymous_reference=FeedbackResponse.generate_anonymous_reference(),
        )
        response.save()

        for question in questions:
            answer = response.add_answer(
                question_id=question.id,
                rating=ratings[question.id],
                comment=comment if question.id == questions[-1].id else "",
            )

        # ---------------------------------------------------------
        # STUDENT TRACKING
        # ---------------------------------------------------------
        tracking = SubmissionTracking(
            student_id=student.id,
            feedback_form_id=form.id,
        )
        tracking.save()

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

    return render_template(
        "student/feedback.html",
        student=student,
        form=form,
        subject=subject,
        questions=questions,
    )


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
