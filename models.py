from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

# ================= USERS =================
class Student(db.Model):
    __tablename__ = 'students'
    student_id = db.Column(db.Integer, primary_key=True) # Matches your app.py
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(20))
    bio = db.Column(db.Text)
    resume_link = db.Column(db.String(200))
    education = db.Column(db.String(100))
    skills = db.Column(db.Text)
    whatsapp_link = db.Column(db.String(200))
    joined_date = db.Column(db.String(50), default=lambda: datetime.utcnow().strftime('%Y-%m-%d'))
    profile_pic = db.Column(db.String(200), default='default.png')

class Recruiter(db.Model):
    __tablename__ = 'recruiters'
    recruiter_id = db.Column(db.Integer, primary_key=True) # Matches your app.py
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    company_name = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    website = db.Column(db.String(200))
    facebook = db.Column(db.String(200))
    twitter = db.Column(db.String(200))
    position = db.Column(db.String(200))
    is_verified = db.Column(db.Boolean, default=False)
    profile_pic = db.Column(db.String(200), default='default.png')

class Admin(db.Model):
    __tablename__ = 'admins'
    admin_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(200))

# ================= SOCIAL =================
class Post(db.Model):
    __tablename__ = 'posts'
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    image_file = db.Column(db.String(255), nullable=True)
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)
    likes_count = db.Column(db.Integer, default=0)
    author_id = db.Column(db.Integer, nullable=False)
    author_name = db.Column(db.String(100), nullable=False)
    author_role = db.Column(db.String(20), nullable=False)
    can_apply = db.Column(db.Boolean, default=False)

    comments = db.relationship('Comment', backref='parent_post', lazy=True, cascade="all, delete-orphan")
    likes_rel = db.relationship('Like', backref='target_post', lazy=True, cascade="all, delete-orphan")

class Like(db.Model):
    __tablename__ = 'likes'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    user_role = db.Column(db.String(20), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)

class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(500), nullable=False)
    author_name = db.Column(db.String(100), nullable=False)
    author_id = db.Column(db.Integer, nullable=False)
    author_role = db.Column(db.String(20), nullable=False)
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)

# ================= INTERNSHIPS & SKILLS =================
class Internship(db.Model):
    __tablename__ = 'internships'
    internship_id = db.Column(db.Integer, primary_key=True)
    recruiter_id = db.Column(db.Integer, db.ForeignKey('recruiters.recruiter_id'))
    title = db.Column(db.String(200))
    description = db.Column(db.Text)
    posted_date = db.Column(db.String(50), default=lambda: datetime.utcnow().strftime('%Y-%m-%d'))

'''class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    #Ensure these match the __tablename__ in your Student/Recruiter classes
    student_id = db.Column(db.Integer, db.ForeignKey('student.student_id'), nullable=False)
    recruiter_id = db.Column(db.Integer, db.ForeignKey('recruiter.recruiter_id'), nullable=False)
    
    date_applied = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='Pending') # Pending, Accepted, Rejected'''
class SkillResource(db.Model):
    __tablename__ = 'skill_resources'
    resource_id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.student_id'), nullable=False)
    title = db.Column(db.String(200))
    link = db.Column(db.String(200))
    thumbnail = db.Column(db.String(200))
    category = db.Column(db.String(50))
    date_added = db.Column(db.DateTime, default=datetime.utcnow)

# ================= UTILITIES =================
class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    recipient_id = db.Column(db.Integer, nullable=False)
    recipient_role = db.Column(db.String(20), nullable=False)
    sender_name = db.Column(db.String(100))
    message = db.Column(db.String(255))
    is_read = db.Column(db.Boolean, default=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)

class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_name = db.Column(db.String(100), nullable=False)
    sender_role = db.Column(db.String(50), nullable=False)
    message = db.Column(db.Text, nullable=False)
    date_sent = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Report from {self.sender_name}>'