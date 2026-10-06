from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from models import Faculty, User
from mongo import get_db
bp=Blueprint("auth",__name__)
def dashboard_for_role(role):return {"student":"student.dashboard","faculty":"faculty.dashboard","hod":"hod.dashboard"}.get(role,"auth.login")
@bp.route("/")
def home():return redirect(url_for(dashboard_for_role(current_user.role))) if current_user.is_authenticated else redirect(url_for("auth.login"))
@bp.route("/login",methods=["GET","POST"])
def login():
    if current_user.is_authenticated:return redirect(url_for(dashboard_for_role(current_user.role)))
    if request.method=="POST":
        role=request.form.get("role","").strip().lower(); username=request.form.get("username","").strip(); password=request.form.get("password","")
        if role not in {"student","faculty","hod"}:flash("Choose a valid account type to continue.","error")
        elif not username or not password:flash("Enter your login ID and password.","error")
        else:
            user=User.find_one({"username":username,"role":role})
            if user is None and role=="faculty":
                fac=Faculty.find_one({"email":{"$regex":f"^{username}$","$options":"i"}}); user=User.get(fac.user_id) if fac else None
            if user and user.check_password(password) and user.is_active: login_user(user,remember=False,fresh=True); return redirect(request.args.get("next")) if request.args.get("next","").startswith("/") and not request.args.get("next","").startswith("//") else redirect(url_for(dashboard_for_role(role)))
            flash("Those credentials did not match an active account.","error")
    return render_template("login.html",page_title="Sign in",selected_role=request.form.get("role","student"))
@bp.get("/profile")
@login_required
def profile():
    profile=current_user.student if current_user.role=="student" else current_user.faculty if current_user.role=="faculty" else None
    return render_template("profile.html",profile=profile)
@bp.post("/logout")
def logout():logout_user(); flash("You have been securely signed out.","success"); return redirect(url_for("auth.login"))
