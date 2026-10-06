from datetime import date, datetime
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash
from mongo import get_db, next_id, utcnow

class RelationList(list):
    def count(self, value=None):
        return len(self) if value is None else super().count(value)

class Base:
    collection = None
    def __init__(self, **kw): self.__dict__.update(kw)
    @classmethod
    def get(cls, ident):
        return cls.from_doc(get_db()[cls.collection].find_one({"id": int(ident)})) if ident is not None else None
    @classmethod
    def from_doc(cls, doc):
        if not doc: return None
        return cls(**doc)
    def save(self):
        data = self.__dict__.copy(); get_db()[self.collection].replace_one({"id": self.id}, data, upsert=True); return self
    @classmethod
    def all(cls, query=None, sort=None):
        cur=get_db()[cls.collection].find(query or {})
        if sort: cur=cur.sort(sort)
        return [cls.from_doc(x) for x in cur]
    @classmethod
    def find_one(cls, query): return cls.from_doc(get_db()[cls.collection].find_one(query))
    @classmethod
    def count(cls, query=None): return get_db()[cls.collection].count_documents(query or {})

class User(UserMixin, Base):
    collection="users"
    def get_id(self): return str(self.id)
    @property
    def student(self): return Student.find_one({"user_id": self.id})
    @property
    def faculty(self): return Faculty.find_one({"user_id": self.id})
    @property
    def is_active(self):
        if self.role=="student": return bool(self.student and self.student.status=="Active")
        if self.role=="faculty": return bool(self.faculty and self.faculty.status=="Active")
        return self.role=="hod"
    def set_password(self,p): self.password_hash=generate_password_hash(p)
    def check_password(self,p): return check_password_hash(self.password_hash,p)

class Student(Base):
    collection="students"
    @property
    def user(self): return User.get(self.user_id)
    @property
    def submissions(self): return RelationList(SubmissionTracking.all({"student_id":self.id}))

class Faculty(Base):
    collection="faculty"
    @property
    def user(self): return User.get(self.user_id)
    @property
    def subjects(self): return RelationList(Subject.all({"faculty_id":self.id}))

class Subject(Base):
    collection="subjects"
    @property
    def faculty(self): return Faculty.get(self.faculty_id) if getattr(self,"faculty_id",None) else None
    @property
    def feedback_forms(self): return RelationList(FeedbackForm.all({"subject_id":self.id}, [("academic_year",-1)]))

class FeedbackQuestion(Base): collection="feedback_questions"

class FeedbackForm(Base):
    collection="feedback_forms"
    @property
    def subject(self): return Subject.get(self.subject_id)
    @property
    def responses(self): return RelationList(FeedbackResponse.all({"feedback_form_id":self.id}, [("submitted_at",-1)]))
    @property
    def submissions(self): return RelationList(SubmissionTracking.all({"feedback_form_id":self.id}))

class FeedbackResponse(Base):
    collection="feedback_responses"
    @property
    def feedback_form(self): return FeedbackForm.get(self.feedback_form_id)
    @property
    def answers(self): return RelationList(FeedbackAnswer.all({"response_id":self.id}))

class FeedbackAnswer(Base):
    collection="feedback_answers"
    @property
    def question(self): return FeedbackQuestion.get(self.question_id)
    @property
    def response(self): return FeedbackResponse.get(self.response_id)

class SubmissionTracking(Base):
    collection="submission_tracking"
    @property
    def student(self): return Student.get(self.student_id)
    @property
    def feedback_form(self): return FeedbackForm.get(self.feedback_form_id)


def new(cls, **kw):
    kw.setdefault("id", next_id(cls.collection)); return cls(**kw)
