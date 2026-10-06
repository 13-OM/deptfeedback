# Department Student Feedback Management System — MongoDB Atlas Edition

This is the same DeptFeedback application converted from SQLite/Flask-SQLAlchemy to **MongoDB Atlas + PyMongo** for cloud deployment. The UI, URLs, role hierarchy, anonymous feedback concept, duplicate-prevention workflow, analytics, and Excel reporting are preserved.

## Local run

1. Install Python 3.10+.
2. Copy `.env.example` to `.env`.
3. Put your MongoDB Atlas connection string in `MONGO_URI`.
4. Create a virtual environment:

```bash
python -m venv venv
venv\\Scripts\\activate
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`.

## Demo accounts

- HOD: `hod` / `hod123`
- Faculty 1: `faculty1` / `faculty123`
- Faculty 2: `faculty2` / `faculty123`
- Student: `250183107002` / `student123`

Change demo credentials before production use.

## Render

Build command:

```text
pip install -r requirements.txt
```

Start command:

```text
gunicorn app:app
```

Required environment variables:

- `SECRET_KEY`
- `MONGO_URI`
- `MONGO_DB_NAME=deptfeedback`
- `DEPARTMENT_NAME=Computer Engineering`
- `SEED_DEMO=true` for the first deployment only, then set it to `false` if you do not want seed checks on startup.
- `SESSION_COOKIE_SECURE=true`

## MongoDB Atlas

Create a cluster, database user, and network access rule. Copy the Python/PyMongo connection string into Render's `MONGO_URI` secret. For a quick Render deployment, Atlas network access can be configured to allow access from `0.0.0.0/0`, with strong database credentials and least-privilege access. Prefer a more restricted network setup when your infrastructure supports it.

## Important privacy design

Student authentication and duplicate tracking are separate from the anonymous feedback response. The feedback response document does not store `student_id` or enrollment number. Excel reports also exclude student identity.
