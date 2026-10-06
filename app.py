import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
from flask import Flask, render_template
from flask_login import current_user
from config import Config
from extensions import csrf, login_manager
from models import User
from routes import auth_bp, faculty_bp, hod_bp, reports_bp, student_bp

def create_app(test_config=None):
    app=Flask(__name__,instance_relative_config=True); app.config.from_object(Config)
    if test_config: app.config.update(test_config)
    Path(app.instance_path).mkdir(parents=True,exist_ok=True)
    login_manager.init_app(app); csrf.init_app(app); login_manager.login_view="auth.login"; login_manager.login_message="Please sign in to continue."; login_manager.login_message_category="info"
    app.register_blueprint(auth_bp); app.register_blueprint(student_bp); app.register_blueprint(faculty_bp); app.register_blueprint(hod_bp); app.register_blueprint(reports_bp)
    @login_manager.user_loader
    def load_user(user_id):
        try:return User.get(int(user_id))
        except (TypeError,ValueError):return None
    @app.context_processor
    def inject_globals(): return {"department_name":app.config.get("DEPARTMENT_NAME","Computer Engineering"),"current_user":current_user}
    @app.errorhandler(403)
    def forbidden(_):return render_template("errors/403.html"),403
    @app.errorhandler(404)
    def not_found(_):return render_template("errors/404.html"),404
    @app.errorhandler(500)
    def internal(_):return render_template("errors/500.html"),500
    @app.cli.command("seed-demo")
    def seed_demo_command():
        from seed import seed_demo_data; seed_demo_data(); print("DeptFeedback demo data is ready.")
    if app.config.get("SEED_DEMO",True):
        from seed import seed_demo_data; seed_demo_data()
    return app
app=create_app()
if __name__=="__main__":app.run(host="0.0.0.0",port=int(os.getenv("PORT","5000")),debug=False)
