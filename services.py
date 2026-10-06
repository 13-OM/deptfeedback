from collections import defaultdict
from datetime import date, datetime
import pandas as pd
from mongo import get_db
from models import FeedbackAnswer, FeedbackForm, FeedbackQuestion, FeedbackResponse, Student, SubmissionTracking

def active_questions(): return FeedbackQuestion.all({"status":"Active"}, [("question_order",1)])
def is_form_open(form,today=None):
    today=today or date.today(); return form.status=="Active" and (not form.start_date or form.start_date<=today) and (not form.end_date or form.end_date>=today)
def student_is_eligible(student, form):
    subject = form.subject

    if not student or student.status != "Active":
        return False

    if not subject or subject.status != "Active":
        return False

    # Student must be explicitly assigned this subject
    assigned_ids = set(
        getattr(student, "subject_ids", []) or []
    )

    if subject.id not in assigned_ids:
        return False

    # Semester must match
    if student.semester != subject.semester:
        return False

    # Department must match
    if (
        student.department.strip().casefold()
        != subject.department.strip().casefold()
    ):
        return False

    # Academic year must match
    if student.academic_year != form.academic_year:
        return False

    return True
    

def eligible_student_count(form):
    s=form.subject
    return Student.count({"status":"Active","semester":s.semester,"academic_year":form.academic_year,"department":s.department})
def tracked_submission(student_id,form_id): return get_db().submission_tracking.find_one({"student_id":student_id,"feedback_form_id":form_id}) is not None
def responses_query(): return FeedbackResponse.all({}, [("submitted_at",-1)])
def response_rating_values(responses): return [int(a.rating) for r in responses for a in r.answers if a.rating is not None]
def average_rating(responses):
    vals=response_rating_values(responses); return round(float(pd.Series(vals,dtype="int64").mean()),2) if vals else 0.0
def question_averages(responses,questions=None):
    questions=questions if questions is not None else active_questions(); sums=defaultdict(list)
    for r in responses:
        for a in r.answers:
            if a.rating is not None: sums[a.question_id].append(int(a.rating))
    return [{"question":q.question_text,"category":q.category,"average":round(sum(sums.get(q.id,[]))/len(sums.get(q.id,[])),2) if sums.get(q.id) else None,"count":len(sums.get(q.id,[]))} for q in questions]
def rating_distribution(responses):
    vals=response_rating_values(responses); return {str(i):vals.count(i) for i in range(1,6)}
def comments_for_responses(responses):
    out=[]
    for r in responses:
        sub=r.feedback_form.subject
        for a in r.answers:
            text=(a.comment or "").strip()
            if text: out.append({"comment":text,"submitted_at":r.submitted_at,"subject":sub.subject_name,"subject_code":sub.subject_code,"faculty":sub.faculty.name if sub.faculty else "Unassigned"})
    return sorted(out,key=lambda x:x["submitted_at"],reverse=True)
def response_count_for_form(form): return FeedbackResponse.count({"feedback_form_id":form.id})
def completion_for_forms(forms):
    forms=list(forms); eligible=sum(eligible_student_count(f) for f in forms); submitted=sum(response_count_for_form(f) for f in forms); rate=round(submitted/eligible*100,1) if eligible else 0.0
    return {"eligible":eligible,"submitted":submitted,"rate":min(rate,100.0) if eligible else 0.0}
def responses_for_forms(forms):
    ids=[f.id for f in forms]
    if not ids:return []
    return FeedbackResponse.all({"feedback_form_id":{"$in":ids}},[("submitted_at",-1)])
def academic_year_start(year):
    try:return int(str(year).split("-")[0])
    except:return datetime.now().year
