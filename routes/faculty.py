from flask import Blueprint,abort,render_template,url_for
from flask_login import current_user
from decorators import role_required
from models import FeedbackForm,FeedbackQuestion,Subject
from services import average_rating,completion_for_forms,comments_for_responses,question_averages,rating_distribution,responses_for_forms
bp=Blueprint("faculty",__name__,url_prefix="/faculty")
def own_subject_or_403(subject_id):
    s=Subject.get(subject_id)
    if not s:abort(404)
    if not current_user.faculty or s.faculty_id!=current_user.faculty.id:abort(403)
    return s
def forms_for_subject(s):return FeedbackForm.all({"subject_id":s.id},[("academic_year",-1)])
@bp.get("/dashboard")
@role_required("faculty")
def dashboard():
    faculty=current_user.faculty; subjects=Subject.all({"faculty_id":faculty.id,"status":"Active"},[("academic_year",-1),("semester",1),("subject_name",1)]); all_forms=[f for s in subjects for f in forms_for_subject(s)]; responses=responses_for_forms(all_forms); completion=completion_for_forms(all_forms); rows=[]
    for s in subjects:
        forms=forms_for_subject(s); rs=responses_for_forms(forms); rows.append({"subject":s,"forms":forms,"responses":len(rs),"average":average_rating(rs),"url":url_for("faculty.subject_detail",subject_id=s.id)})
    return render_template("faculty/dashboard.html",faculty=faculty,rows=rows,subject_count=len(subjects),response_count=len(responses),average=average_rating(responses),completion=completion)
@bp.get("/subjects")
@role_required("faculty")
def subjects():return dashboard()
@bp.get("/subject/<int:subject_id>")
@role_required("faculty")
def subject_detail(subject_id):
    s=own_subject_or_403(subject_id); forms=forms_for_subject(s); form=forms[0] if forms else None; responses=responses_for_forms([form]) if form else []; completion=completion_for_forms([form]) if form else {"eligible":0,"submitted":0,"rate":0.0}; questions=FeedbackQuestion.all({"status":"Active","is_comment":False},[("question_order",1)]); qdata=question_averages(responses,questions); comments=comments_for_responses(responses); dist=rating_distribution(responses)
    return render_template("faculty/subject_detail.html",subject=s,form=form,responses=responses,response_count=len(responses),average=average_rating(responses),completion=completion,question_data=qdata,comments=comments,distribution=dist,chart_labels=["Very poor","Poor","Average","Good","Excellent"],chart_values=[dist[str(i)] for i in range(1,6)])
@bp.get("/comments")
@role_required("faculty")
def comments():
    faculty=current_user.faculty; subjects=Subject.all({"faculty_id":faculty.id}); forms=[f for s in subjects for f in forms_for_subject(s)]; return render_template("faculty/comments.html",comments=comments_for_responses(responses_for_forms(forms)),subject_count=len(subjects))
