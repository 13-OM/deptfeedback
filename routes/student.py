import secrets
from datetime import date,datetime,timezone
from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from flask_login import current_user
from decorators import role_required
from models import FeedbackAnswer,FeedbackForm,FeedbackQuestion,FeedbackResponse,Subject,SubmissionTracking,new
from mongo import get_db
from services import is_form_open,student_is_eligible,tracked_submission
bp=Blueprint("student",__name__,url_prefix="/student")
def student_forms(student):
    forms=[]
    for f in FeedbackForm.all({"academic_year":student.academic_year},[("id",1)]):
        s=f.subject
        if s and s.semester==student.semester and s.status=="Active" and s.department.strip().casefold()==student.department.strip().casefold():forms.append(f)
    return sorted(forms,key=lambda f:f.subject.subject_name)
@bp.get("/dashboard")
@role_required("student")
def dashboard():
    student=current_user.student; forms=student_forms(student); items=[]; completed=pending=0
    for form in forms:
        done=tracked_submission(student.id,form.id); open_now=is_form_open(form) and student_is_eligible(student,form)
        if done:state="Completed";completed+=1
        elif open_now:state="Pending";pending+=1
        else:state="Closed" if (form.status in {"Closed","Archived"} or (form.end_date and form.end_date<date.today())) else "Unavailable"
        items.append({"form":form,"subject":form.subject,"done":done,"open":open_now and not done,"state":state})
    total=len(items); return render_template("student/dashboard.html",items=items,student=student,completed=completed,pending=pending,total=total,completion=round(completed/total*100,1) if total else 0)
@bp.get("/subjects")
@role_required("student")
def subjects():return redirect(url_for("student.dashboard"))
@bp.route("/feedback/<int:form_id>",methods=["GET","POST"])
@role_required("student")
def feedback_form(form_id):
    student=current_user.student; form=FeedbackForm.get(form_id)
    if not form:abort(404)
    if not student_is_eligible(student,form):abort(403)
    if tracked_submission(student.id,form.id):flash("You have already submitted feedback for this subject.","info");return redirect(url_for("student.dashboard"))
    if not is_form_open(form):flash("This feedback form is not currently open.","warning");return redirect(url_for("student.dashboard"))
    questions=FeedbackQuestion.all({"status":"Active","is_comment":False},[("question_order",1)]); comment_question=FeedbackQuestion.find_one({"status":"Active","is_comment":True})
    if not questions:flash("This feedback form has no active questions yet. Please contact the department.","error");return redirect(url_for("student.dashboard"))
    if request.method=="POST":
        ratings={};invalid=False
        for q in questions:
            try:r=int(request.form.get(f"rating_{q.id}","")); assert 1<=r<=5; ratings[q.id]=r
            except:invalid=True
        comment=request.form.get("comment","").strip()
        if len(comment)>2000:invalid=True;flash("Comments must be 2,000 characters or fewer.","error")
        if invalid:
            if len(comment)<=2000:flash("Please select a rating from 1 to 5 for every question.","error")
            return render_template("student/feedback_form.html",form=form,questions=questions,comment_question=comment_question,submitted=request.form),400
        now=datetime.now(timezone.utc).replace(tzinfo=None); rounded=now.replace(minute=(now.minute//15)*15,second=0,microsecond=0)
        response=new(FeedbackResponse,feedback_form_id=form.id,anonymous_reference=f"TMP-{secrets.token_hex(10).upper()}",submitted_at=rounded); response.save()
        response.anonymous_reference=f"FB-{form.academic_year.split('-')[0]}-{response.id:05d}"; response.save()
        for q in questions:new(FeedbackAnswer,response_id=response.id,question_id=q.id,rating=ratings[q.id],comment=None).save()
        if comment and comment_question:new(FeedbackAnswer,response_id=response.id,question_id=comment_question.id,rating=None,comment=comment).save()
        try:new(SubmissionTracking,student_id=student.id,feedback_form_id=form.id,submitted_at=now).save()
        except Exception:
            get_db().feedback_responses.delete_one({"id":response.id}); get_db().feedback_answers.delete_many({"response_id":response.id}); flash("You have already submitted feedback for this subject.","info"); return redirect(url_for("student.dashboard"))
        session["feedback_success_reference"]=response.anonymous_reference; return redirect(url_for("student.feedback_success"))
    return render_template("student/feedback_form.html",form=form,questions=questions,comment_question=comment_question,submitted={})
@bp.get("/success")
@role_required("student")
def feedback_success():return render_template("student/success.html",reference=session.pop("feedback_success_reference",None))
