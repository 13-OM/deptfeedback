from functools import wraps

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from flask_login import (
    current_user,
    login_required,
    login_user,
    logout_user,
)

from models import Faculty, User


bp = Blueprint("auth", __name__)


# ============================================================
# ROLE REQUIRED DECORATOR
# ============================================================

def role_required(required_role):
    """
    Allow access only to an authenticated user
    having the required role.
    """

    def decorator(view_function):

        @wraps(view_function)
        def wrapped_view(*args, **kwargs):

            # User must be logged in
            if not current_user.is_authenticated:

                return redirect(
                    url_for(
                        "auth.login",
                        next=request.path
                    )
                )

            # User must have the required role
            if current_user.role != required_role:

                flash(
                    "You are not authorized to access this page.",
                    "error"
                )

                return redirect(
                    url_for("auth.home")
                )

            return view_function(*args, **kwargs)

        return wrapped_view

    return decorator


# ============================================================
# DASHBOARD ROUTING
# ============================================================

def dashboard_for_role(role):

    return {
        "student": "student.dashboard",
        "faculty": "faculty.dashboard",
        "hod": "hod.dashboard",
    }.get(
        role,
        "auth.login"
    )


# ============================================================
# HOME
# ============================================================

@bp.route("/")
def home():

    if current_user.is_authenticated:

        return redirect(
            url_for(
                dashboard_for_role(
                    current_user.role
                )
            )
        )

    return redirect(
        url_for("auth.login")
    )


# ============================================================
# LOGIN
# ============================================================

@bp.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    # Already logged in
    if current_user.is_authenticated:

        return redirect(
            url_for(
                dashboard_for_role(
                    current_user.role
                )
            )
        )

    # --------------------------------------------------------
    # POST LOGIN
    # --------------------------------------------------------

    if request.method == "POST":

        role = request.form.get(
            "role",
            ""
        ).strip().lower()

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        # ----------------------------------------------------
        # VALIDATE ROLE
        # ----------------------------------------------------

        if role not in {
            "student",
            "faculty",
            "hod"
        }:

            flash(
                "Choose a valid account type to continue.",
                "error"
            )

        # ----------------------------------------------------
        # VALIDATE CREDENTIALS
        # ----------------------------------------------------

        elif not username or not password:

            flash(
                "Enter your login ID and password.",
                "error"
            )

        else:

            # ------------------------------------------------
            # FIND USER
            # ------------------------------------------------

            user = User.find_one({
                "username": username,
                "role": role
            })

            # ------------------------------------------------
            # FACULTY LOGIN USING EMAIL
            # ------------------------------------------------

            if user is None and role == "faculty":

                fac = Faculty.find_one({
                    "email": {
                        "$regex": f"^{username}$",
                        "$options": "i"
                    }
                })

                user = (
                    User.get(fac.user_id)
                    if fac
                    else None
                )

            # ------------------------------------------------
            # CHECK PASSWORD
            # ------------------------------------------------

            if (
                user
                and user.check_password(password)
                and user.is_active
            ):

                login_user(
                    user,
                    remember=False,
                    fresh=True
                )

                # --------------------------------------------
                # SAFE NEXT URL
                # --------------------------------------------

                next_url = request.args.get(
                    "next",
                    ""
                )

                if (
                    next_url.startswith("/")
                    and not next_url.startswith("//")
                ):

                    return redirect(next_url)

                return redirect(
                    url_for(
                        dashboard_for_role(role)
                    )
                )

            # ------------------------------------------------
            # INVALID LOGIN
            # ------------------------------------------------

            flash(
                "Those credentials did not match an active account.",
                "error"
            )

    # --------------------------------------------------------
    # LOGIN PAGE
    # --------------------------------------------------------

    return render_template(
        "login.html",
        page_title="Sign in",
        selected_role=request.form.get(
            "role",
            "student"
        )
    )


# ============================================================
# PROFILE
# ============================================================

@bp.get("/profile")
@login_required
def profile():

    if current_user.role == "student":

        profile = current_user.student

    elif current_user.role == "faculty":

        profile = current_user.faculty

    else:

        profile = None

    return render_template(
        "profile.html",
        profile=profile
    )


# ============================================================
# LOGOUT
# ============================================================

@bp.post("/logout")
def logout():

    logout_user()

    flash(
        "You have been securely signed out.",
        "success"
    )

    return redirect(
        url_for("auth.login")
    )
