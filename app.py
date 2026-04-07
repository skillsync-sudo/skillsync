from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import os
import requests
from collections import Counter
import re
from googleapiclient.discovery import build
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from models import db, Student, Recruiter, Admin, Post, Comment, Internship, Like, Notification, SkillResource, Report, Application
from flask_mail import Mail, Message
import cloudinary
import cloudinary.uploader

app = Flask(__name__)

# --- 1. CONFIGURATION & SECRETS ---
# Using environment variables for security. Local defaults are provided as fallbacks.
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'postgresql://postgres.rmknqhaztehgtwigsprs:prabinrokaya123%40%23@aws-1-ap-south-1.pooler.supabase.com:6543/postgres')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'skillsync_2026_super_secret')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Mail Settings (Gmail App Password required)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME', 'your-email@gmail.com')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD', 'your-app-password')
app.config['MAIL_DEFAULT_SENDER'] = app.config['MAIL_USERNAME']
mail = Mail(app)

# Cloudinary Setup for persistent image hosting on Render
cloudinary.config(
    cloud_name = os.getenv('CLOUDINARY_NAME'),
    api_key = os.getenv('CLOUDINARY_KEY'),
    api_secret = os.getenv('CLOUDINARY_SECRET'),
    secure = True
)

db.init_app(app)

# --- 2. CORE PAGE ROUTES ---

@app.route('/')
def home(): return render_template('index.html')

@app.route('/about-us')
def about_us(): return render_template('about_us.html')

@app.route('/feedback')
def feedback(): return render_template('feedback.html')

@app.route('/privacy-policy')
def privacy_policy(): return render_template('privacy_policy.html')

@app.route('/user-agreement')
def user_agreement(): return render_template('user_agreement.html')

@app.route('/copyright')
def copyright(): return render_template('copyright.html')

@app.route('/cookie-policy')
def cookie_policy(): return render_template('cookie_policy.html')

@app.route('/forgot-password')
def forget(): return render_template('forget.html')

@app.route('/community')
def community(): return render_template('community.html')

# --- 3. AUTHENTICATION ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        first_name = request.form.get('firstName')
        last_name = request.form.get('lastName')
        full_name = f"{first_name} {last_name}"
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role') 
        company = request.form.get('companyName')

        if Student.query.filter_by(email=email).first() or Recruiter.query.filter_by(email=email).first():
            flash('Email already registered!', 'danger')
            return redirect(url_for('register'))

        hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')

        if role == 'student':
            new_user = Student(name=full_name, email=email, password=hashed_pw)
        else:
            new_user = Recruiter(name=full_name, email=email, password=hashed_pw, 
                                company_name=company if company else "Independent")

        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        admin = Admin.query.filter_by(email=email).first()
        if admin and (check_password_hash(admin.password, password) or admin.password == password):
            session.update({'user_id': admin.admin_id, 'role': 'admin', 'name': admin.name})
            return redirect(url_for('admin_dashboard'))

        student = Student.query.filter_by(email=email).first()
        if student and (check_password_hash(student.password, password) or student.password == password):
            session.update({'user_id': student.student_id, 'role': 'student', 'name': student.name})
            return redirect(url_for('student_feed'))

        recruiter = Recruiter.query.filter_by(email=email).first()
        if recruiter and (check_password_hash(recruiter.password, password) or recruiter.password == password):
            session.update({'user_id': recruiter.recruiter_id, 'role': 'recruiter', 'name': recruiter.name})
            return redirect(url_for('recruiter_dashboard'))

        flash("Invalid Credentials", "danger")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# --- 4. DASHBOARDS ---

@app.route('/student-feed')
def student_feed():
    if 'user_id' not in session or session.get('role') != 'student':
        return redirect(url_for('login'))
    
    user = db.session.get(Student, session['user_id'])
    posts = Post.query.order_by(Post.date_posted.desc()).all()
    user_applications = Application.query.filter_by(student_id=user.student_id).all()
    applied_post_ids = [app.post_id for app in user_applications]
    
    notifications = Notification.query.filter_by(recipient_id=session['user_id'], recipient_role='student').order_by(Notification.date_created.desc()).limit(10).all()
    unread_count = Notification.query.filter_by(recipient_id=session['user_id'], recipient_role='student', is_read=False).count()
    
    return render_template('student.html', user=user, user_name=user.name, user_role='student', posts=posts, notifications=notifications, unread_count=unread_count, Student=Student, Recruiter=Recruiter, applied_post_ids=applied_post_ids)

@app.route('/recruiter/dashboard')
def recruiter_dashboard():
    if 'user_id' not in session or session.get('role') != 'recruiter':
        return redirect(url_for('login'))
    
    user = db.session.get(Recruiter, session['user_id'])
    posts = Post.query.order_by(Post.date_posted.desc()).all()
    notifications = Notification.query.filter_by(recipient_id=session['user_id'], recipient_role='recruiter').order_by(Notification.date_created.desc()).limit(10).all()
    unread_count = Notification.query.filter_by(recipient_id=session['user_id'], recipient_role='recruiter', is_read=False).count()
    
    return render_template('recruiter.html', user=user, user_name=user.name, user_role='recruiter', posts=posts, notifications=notifications, unread_count=unread_count, Student=Student, Recruiter=Recruiter)

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    stats = {'students': Student.query.count(), 'recruiters': Recruiter.query.count(), 'posts': Post.query.count(), 'reports': Report.query.count()}
    reports = Report.query.order_by(Report.date_sent.desc()).all()
    unverified_recruiters = Recruiter.query.filter_by(is_verified=False).all()
    all_posts = Post.query.order_by(Post.date_posted.desc()).limit(20).all()
    
    return render_template('admin.html', stats=stats, reports=reports, unverified_recruiters=unverified_recruiters, recent_posts=all_posts)

# --- 5. INTERACTIONS & UTILITIES ---

@app.route('/create-post', methods=['POST'])
def create_post():
    if 'user_id' not in session: return redirect(url_for('login'))
    new_post = Post(content=request.form.get('content'), author_name=session['name'], author_role=session['role'], author_id=session['user_id'], can_apply='can_apply' in request.form)
    db.session.add(new_post)
    db.session.commit()
    return redirect(request.referrer or url_for('home'))

@app.route('/delete_post/<int:post_id>')
def delete_post(post_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    post = db.session.get(Post, post_id)
    if post and (post.author_id == session.get('user_id') and post.author_role == session.get('role')):
        db.session.delete(post)
        db.session.commit()
        flash("Post deleted successfully.", "success")
    return redirect(request.referrer)

@app.route('/like/<int:post_id>')
def like_post(post_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    u_id, u_role = session.get('user_id'), session.get('role')
    post = db.session.get(Post, post_id)
    if post:
        existing_like = Like.query.filter_by(user_id=u_id, user_role=u_role, post_id=post_id).first()
        if not existing_like:
            db.session.add(Like(user_id=u_id, user_role=u_role, post_id=post_id))
            post.likes_count = (post.likes_count or 0) + 1
            if post.author_id != u_id or post.author_role != u_role:
                db.session.add(Notification(recipient_id=post.author_id, recipient_role=post.author_role, sender_name=session.get('name'), message=f"liked your post: {post.content[:20]}..."))
        else:
            db.session.delete(existing_like)
            post.likes_count = max(0, post.likes_count - 1)
        db.session.commit()
    return redirect(request.referrer or url_for('student_feed'))

@app.route('/edit-profile', methods=['POST'])
def edit_profile():
    if 'user_id' not in session or session['role'] != 'student': return redirect(url_for('login'))
    user = db.session.get(Student, session['user_id'])
    user.name, user.bio, user.education, user.skills, user.whatsapp_link = request.form.get('name'), request.form.get('bio'), request.form.get('education'), request.form.get('skills'), request.form.get('whatsapp_link')
    if 'profile_pic' in request.files:
        file = request.files['profile_pic']
        if file and file.filename != '':
            upload_result = cloudinary.uploader.upload(file, folder="skillsync/students/")
            user.profile_pic = upload_result['secure_url']
    db.session.commit()
    session['name'] = user.name
    return redirect(url_for('student_feed'))

# --- 6. AI & MASTER LOGIC ---

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "AIzaSyDeT5dueyBjrcUp1fDdQFmCa5Gnc58rbtQ")

def extract_skills_pro(text_content):
    url = "https://api.apilayer.com/skills/extract"
    headers = {"apikey": os.getenv("SKILLS_API_KEY", "nKpSaFqgGRNiKeVmj2euz0TU9JqOrVrd")}
    try:
        response = requests.post(url, headers=headers, data=text_content.encode("utf-8"))
        if response.status_code == 200: return [s['skill'].lower() for s in response.json()]
    except: pass
    it_keywords = ["python", "javascript", "react", "flask", "django", "sql", "aws", "docker", "machine learning"]
    return list(set(re.findall(r'\b(' + '|'.join(it_keywords) + r')\b', text_content.lower())))

@app.route('/apply/<int:post_id>')
def apply_internship(post_id):
    if 'user_id' not in session or session.get('role') != 'student': return redirect(url_for('login'))
    post = Post.query.get_or_404(post_id)
    student = Student.query.get(session['user_id'])
    recruiter = Recruiter.query.get(post.author_id)
    
    if not Application.query.filter_by(post_id=post.id, student_id=student.student_id).first():
        db.session.add(Application(post_id=post.id, student_id=student.student_id, recruiter_id=recruiter.recruiter_id if recruiter else None))
        if recruiter:
            db.session.add(Notification(recipient_id=recruiter.recruiter_id, recipient_role='recruiter', sender_name=student.name, message=f"applied for: {post.content[:30]}..."))
            if recruiter.email:
                mail.send(Message(subject=f"SkillSync Application: {student.name}", recipients=[recruiter.email], body=f"{student.name} applied for your internship."))
        db.session.commit()
        flash("Application sent!", "success")
    return redirect(url_for('student_feed'))

@app.context_processor
def inject_sidebar_data():
    try:
        all_posts = Post.query.all()
        skill_tally = Counter()
        for p in all_posts:
            for s in extract_skills_pro(p.content): skill_tally[s] += 1
        top_students = sorted([{'name': s.name, 'skill_count': len((s.skills or "").split(',')), 'profile_pic': s.profile_pic, 'id': s.student_id} for s in Student.query.all()], key=lambda x: x['skill_count'], reverse=True)[:5]
        return dict(market_trends=skill_tally.most_common(7), top_students=top_students)
    except: return dict(market_trends=[], top_students=[])

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
