```python
import random
from datetime import datetime, timedelta

from models import (
    FeedbackAnswer,
    FeedbackForm,
    FeedbackQuestion,
    FeedbackResponse,
    Faculty,
    Student,
    Subject,
    SubmissionTracking,
    User,
    new,
)

from mongo import get_db


DEFAULT_QUESTIONS = [
    ("The faculty explains concepts clearly.", "Teaching"),
    ("The faculty is well prepared for lectures.", "Teaching"),
    ("The faculty encourages student participation.", "Teaching"),
    ("The faculty uses appropriate teaching methods.", "Teaching"),
    ("The faculty provides sufficient examples and explanations.", "Teaching"),
    ("The syllabus is covered properly.", "Subject"),
    ("The subject content is relevant and useful.", "Subject"),
    ("The learning resources are useful.", "Subject"),
    ("The difficulty level is appropriate.", "Subject"),
    ("The subject improves practical and technical knowledge.", "Subject"),
    ("Overall satisfaction with the subject.", "Overall"),
    ("Overall satisfaction with the faculty.", "Overall"),
    ("Additional comments or suggestions (optional).", "Comments"),
]


def user(username, role, password):
    u = User.find_one({
        "username": username,
        "role": role
    })

    if u:
        return u

    u = new(
        User,
        username=username,
        role=role,
        created_at=datetime.utcnow()
    )

    u.set_password(password)
    u.save()

    return u


def seed_demo_data():

    # =========================================================
    # DEMO USERS
    # =========================================================

    hod = user(
        "hod",
        "hod",
        "hod123"
    )

    f1 = user(
        "faculty1",
        "faculty",
        "faculty123"
    )

    f2 = user(
        "faculty2",
        "faculty",
        "faculty123"
    )

    # =========================================================
    # FACULTY
    # =========================================================

    faculty1 = Faculty.find_one({
        "faculty_code": "FAC001"
    })

    if not faculty1:

        faculty1 = new(
            Faculty,
            user_id=f1.id,
            name="Prof. Anjali Patel",
            faculty_code="FAC001",
            email="faculty1@college.edu",
            department="Computer Engineering",
            designation="Assistant Professor",
            status="Active"
        )

        faculty1.save()

    faculty2 = Faculty.find_one({
        "faculty_code": "FAC002"
    })

    if not faculty2:

        faculty2 = new(
            Faculty,
            user_id=f2.id,
            name="Prof. Rahul Shah",
            faculty_code="FAC002",
            email="faculty2@college.edu",
            department="Computer Engineering",
            designation="Assistant Professor",
            status="Active"
        )

        faculty2.save()

    # =========================================================
    # STUDENT
    # =========================================================

    stu_user = user(
        "250183107002",
        "student",
        "student123"
    )

    if not Student.find_one({
        "enrollment_no": "250183107002"
    }):

        student = new(
            Student,
            user_id=stu_user.id,
            enrollment_no="250183107002",
            name="Om A. Bhatt",
            semester=5,
            department="Computer Engineering",
            academic_year="2026-27",
            email="om@college.edu",
            status="Active"
        )

        student.save()

    # =========================================================
    # SUBJECTS
    # =========================================================

    defaults = [

        (
            "Python Programming",
            "BE05000231",
            5,
            faculty1.id
        ),

        (
            "DBMS",
            "BE05000241",
            5,
            faculty1.id
        ),

        (
            "Web Application Development",
            "BE05000281",
            5,
            faculty2.id
        ),

        (
            "System Software",
            "BE05000261",
            5,
            faculty2.id
        ),

        (
            "Computer Networks",
            "BE05000251",
            5,
            faculty2.id
        )
    ]

    for name, code, sem, fid in defaults:

        subject = Subject.find_one({
            "subject_code": code,
            "semester": sem,
            "academic_year": "2026-27"
        })

        if not subject:

            subject = new(
                Subject,
                subject_name=name,
                subject_code=code,
                semester=sem,
                faculty_id=fid,
                academic_year="2026-27",
                department="Computer Engineering",
                subject_type="Theory",
                credits=3,
                status="Active"
            )

            subject.save()

    # =========================================================
    # FEEDBACK QUESTIONS
    # =========================================================

    for i, (text, category) in enumerate(
        DEFAULT_QUESTIONS,
        1
    ):

        question = FeedbackQuestion.find_one({
            "question_text": text
        })

        if not question:

            question = new(
                FeedbackQuestion,
                question_text=text,
                category=category,
                question_order=i,
                status="Active",
                is_comment=(category == "Comments")
            )

            question.save()

    # =========================================================
    # FEEDBACK FORMS
    # =========================================================

    for subject in Subject.all({
        "status": "Active"
    }):

        existing_form = FeedbackForm.find_one({
            "subject_id": subject.id,
            "academic_year": "2026-27"
        })

        if not existing_form:

            form = new(
                FeedbackForm,
                subject_id=subject.id,
                academic_year="2026-27",

                # MongoDB requires datetime objects.
                # Do NOT use datetime.date objects here.
                start_date=datetime(
                    2026,
                    1,
                    1
                ),

                end_date=datetime(
                    2026,
                    12,
                    31
                ),

                status="Active"
            )

            form.save()

    # =========================================================
    # ANONYMOUS DEMO RESPONSES
    # =========================================================

    if FeedbackResponse.count() == 0:

        questions = FeedbackQuestion.all(
            {
                "status": "Active",
                "is_comment": False
            },
            [
                ("question_order", 1)
            ]
        )

        forms = FeedbackForm.all({
            "status": "Active"
        })

        for form in forms[:5]:

            for n in range(5):

                response = new(
                    FeedbackResponse,
                    feedback_form_id=form.id,
                    anonymous_reference=(
                        f"FB-2026-"
                        f"{new_id_preview(form.id, n):05d}"
                    ),
                    submitted_at=datetime(
                        2026,
                        9,
                        15,
                        10,
                        n * 5
                    )
                )

                response.save()

                for question in questions:

                    answer = new(
                        FeedbackAnswer,
                        response_id=response.id,
                        question_id=question.id,
                        rating=random.choice(
                            [3, 4, 4, 5]
                        ),
                        comment=None
                    )

                    answer.save()

                # Add one sample comment
                if n == 0:

                    comment_question = FeedbackQuestion.find_one({
                        "is_comment": True,
                        "status": "Active"
                    })

                    if comment_question:

                        comment_answer = new(
                            FeedbackAnswer,
                            response_id=response.id,
                            question_id=comment_question.id,
                            rating=None,
                            comment=(
                                "More practical examples "
                                "would be helpful."
                            )
                        )

                        comment_answer.save()

    print(
        "MongoDB demo data is ready."
    )


def new_id_preview(form_id, n):
    return (form_id * 100) + n + 1


if __name__ == "__main__":
    seed_demo_data()
```

### Now on GitHub

After replacing the whole `seed.py`:

1. Click **Commit changes**
2. Commit message:

```text
Fix MongoDB seed date handling
```

3. Click **Commit changes**

Then **Render should automatically start a new deployment** because your Render service is connected to the `main` branch.

### One important point

Your previous Render error was specifically:

```text
datetime.date(2026, 1, 1)
```

This code now uses:

```python
datetime(2026, 1, 1)
```

So that particular MongoDB error is fixed.

After you commit, **wait for the new Render deployment and send me the new Render log**. Don't make another change until we see what the new deployment says.
