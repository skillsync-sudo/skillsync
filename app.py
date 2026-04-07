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

# --- 1. SETUP & CONFIGURATION ---
# Database Config (Uses environment variable for Render, falls back to your working string)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'postgresql://postgres.rmknqhaztehgtwigsprs:prabinrokaya123%40%23@aws-1-ap-south-1.pooler.supabase.com:6543/postgres')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'skillsync_2026_super_secret')

# Mail Config
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME', 'your-email@gmail.com')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD', 'your-app-password')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_USERNAME', 'your-email@gmail.com')
mail = Mail(app)

# Cloudinary Config
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

# --- 3. AUTHENTICATION ROUTES ---

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
            new_user = Recruiter(name=full_name, email=email, password=hashed_pw, company_name=company if company else "Independent")

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
            session['user_id'] = admin.admin_id
            session['role'] = 'admin'
            session['name'] = admin.name
            return redirect(url_for('admin_dashboard'))

        student = Student.query.filter_by(email=email).first()
        if student and (check_password_hash(student.password, password) or student.password == password):
            session['user_id'] = student.student_id 
            session['role'] = 'student'
            session['name'] = student.name
            return redirect(url_for('student_feed'))

        recruiter = Recruiter.query.filter_by(email=email).first()
        if recruiter and (check_password_hash(recruiter.password, password) or recruiter.password == password):
            session['user_id'] = recruiter.recruiter_id 
            session['role'] = 'recruiter'
            session['name'] = recruiter.name
            return redirect(url_for('recruiter_dashboard'))

        flash("Invalid Credentials", "danger")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# --- 4. DASHBOARD ROUTES ---

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
    if 'user_id' not in session or session.get('role') != 'admin': return redirect(url_for('login'))
    stats = {'students': Student.query.count(), 'recruiters': Recruiter.query.count(), 'posts': Post.query.count(), 'reports': Report.query.count()}
    reports = Report.query.order_by(Report.date_sent.desc()).all()
    unverified_recruiters = Recruiter.query.filter_by(is_verified=False).all()
    all_posts = Post.query.order_by(Post.date_posted.desc()).limit(20).all()
    
    return render_template('admin.html', stats=stats, reports=reports, unverified_recruiters=unverified_recruiters, recent_posts=all_posts)

@app.route('/admin/change-password', methods=['POST'])
def admin_change_password():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    new_password = request.form.get('new_password')
    admin_user = Admin.query.filter_by(email="admin@skillsync.com").first()
    if admin_user and new_password:
        admin_user.password = generate_password_hash(new_password)
        db.session.commit()
        flash("Admin password updated!", "success")
    return redirect(url_for('admin_dashboard', _anchor='settings'))

@app.route('/admin/verify-recruiter/<int:rec_id>')
def verify_recruiter(rec_id):
    if session.get('role') != 'admin': return redirect(url_for('login'))
    recruiter = Recruiter.query.get_or_404(rec_id)
    recruiter.is_verified = True
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete-post/<int:post_id>')
def admin_delete_post(post_id):
    if session.get('role') != 'admin': return redirect(url_for('login'))
    post = Post.query.get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/dismiss-report/<int:report_id>')
def dismiss_report(report_id):
    if session.get('role') != 'admin': return redirect(url_for('login'))
    report = Report.query.get(report_id)
    if report:
        db.session.delete(report)
        db.session.commit()
    return redirect(url_for('admin_dashboard'))

# --- 5. INTERACTION ROUTES ---

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
    if not post:
        flash("Post not found.", "warning")
        return redirect(request.referrer)
    if post.author_id != session.get('user_id') or post.author_role != session.get('role'):
        flash("You do not have permission to delete this post!", "danger")
        return redirect(request.referrer)
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
            new_like = Like(user_id=u_id, user_role=u_role, post_id=post_id)
            db.session.add(new_like)
            post.likes_count = (post.likes_count or 0) + 1
            
            notif_msg = f"liked your post: {post.content[:20]}..."
            already_notified = Notification.query.filter_by(recipient_id=post.author_id, recipient_role=post.author_role, sender_name=session.get('name'), message=notif_msg).first()
            
            if not already_notified and (post.author_id != u_id or post.author_role != u_role):
                new_notif = Notification(recipient_id=post.author_id, recipient_role=post.author_role, sender_name=session.get('name'), message=notif_msg)
                db.session.add(new_notif)
            db.session.commit()
        else:
            db.session.delete(existing_like)
            post.likes_count = max(0, post.likes_count - 1)
            db.session.commit()
    return redirect(request.referrer or url_for('student_feed'))

@app.route('/comment/<int:post_id>', methods=['POST'])
def add_comment(post_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    post = db.session.get(Post, post_id)
    text = request.form.get('comment_text')
    
    if text and post:
        comment = Comment(text=text, author_name=session['name'], author_id=session['user_id'], author_role=session['role'], post_id=post_id)
        db.session.add(comment)
        if post.author_id != session['user_id'] or post.author_role != session['role']:
            new_notif = Notification(recipient_id=post.author_id, recipient_role=post.author_role, sender_name=session['name'], message=f"commented on your post")
            db.session.add(new_notif)
        db.session.commit()
    return redirect(request.referrer)

# --- 6. PROFILE EDITING (WITH CLOUDINARY) ---

@app.route('/edit-profile', methods=['POST'])
def edit_profile():
    if 'user_id' not in session or session['role'] != 'student': return redirect(url_for('login'))
    user = db.session.get(Student, session['user_id'])
    user.name = request.form.get('name')
    user.bio = request.form.get('bio')
    user.education = request.form.get('education')
    user.skills = request.form.get('skills')
    user.whatsapp_link = request.form.get('whatsapp_link')
    
    if 'profile_pic' in request.files:
        file = request.files['profile_pic']
        if file and file.filename != '':
            upload_result = cloudinary.uploader.upload(file, folder="skillsync/students/")
            user.profile_pic = upload_result['secure_url']
            
    db.session.commit()
    session['name'] = user.name
    return redirect(url_for('student_feed'))

@app.route('/edit-recruiter-profile', methods=['POST'])
def edit_recruiter_profile():
    if 'user_id' not in session or session['role'] != 'recruiter': return redirect(url_for('login'))
    user = Recruiter.query.get(session['user_id'])
    user.name = request.form.get('name')
    user.company_name = request.form.get('company')
    user.phone = request.form.get('phone')
    user.website = request.form.get('website')
    user.facebook = request.form.get('facebook')
    user.twitter = request.form.get('twitter')
    user.position = request.form.get('position')
    
    if 'profile_pic' in request.files:
        file = request.files['profile_pic']
        if file and file.filename != '':
            upload_result = cloudinary.uploader.upload(file, folder="skillsync/recruiters/")
            user.profile_pic = upload_result['secure_url']
            
    db.session.commit()
    session['name'] = user.name
    return redirect(url_for('recruiter_dashboard'))

# --- 7. UTILITIES ---

@app.route('/delete-comment/<int:comment_id>')
def delete_comment(comment_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    comment = Comment.query.get_or_404(comment_id)
    if comment.author_id == session['user_id']:
        db.session.delete(comment)
        db.session.commit()
        flash("Comment deleted.", "success")
    return redirect(request.referrer)

@app.route('/clear-notifications')
def clear_notifications():
    if 'user_id' in session:
        Notification.query.filter_by(recipient_id=session['user_id'], recipient_role=session['role'], is_read=False).update({"is_read": True})
        db.session.commit()
        return jsonify({"status": "success"})
    return jsonify({"status": "unauthorized"}), 401

@app.route('/submit-report', methods=['POST'])
def submit_report():
    if 'user_id' not in session: return redirect(url_for('login'))
    message_content = request.form.get('message')
    if message_content:
        try:
            new_report = Report(sender_name=session.get('name'), sender_role=session.get('role', 'student'), message=message_content)
            db.session.add(new_report)
            db.session.commit()
            session.modified = True 
        except Exception as e:
            db.session.rollback()
            print(f"DATABASE ERROR: {e}")
            
    if session.get('role') == 'student': return redirect(url_for('student_feed'))
    elif session.get('role') == 'recruiter': return redirect(url_for('recruiter_dashboard'))
    return redirect(url_for('home'))

# --- 8. API ROUTES ---

@app.route('/api/search')
def api_search():
    query = request.args.get('query', '').lower()
    search_type = request.args.get('type', 'all')
    results = {'people': [], 'internships': []}
    
    if not query: return jsonify(results)

    if search_type in ['all', 'people']:
        for s in Student.query.filter(Student.name.ilike(f'%{query}%')).limit(5).all():
            results['people'].append({'id': s.student_id, 'name': s.name, 'role': 'student'})
        for r in Recruiter.query.filter(Recruiter.name.ilike(f'%{query}%')).limit(5).all():
            results['people'].append({'id': r.recruiter_id, 'name': r.name, 'role': 'recruiter'})

    if search_type in ['all', 'internships']:
        for p in Post.query.filter(Post.can_apply == True, Post.content.ilike(f'%{query}%')).limit(5).all():
            results['internships'].append({'id': p.id, 'title': p.content[:30] + "..."})

    return jsonify(results)

@app.route('/api/user-details/<role>/<int:user_id>')
def get_user_details(role, user_id):
    if role == 'student':
        user = Student.query.get(user_id)
        if not user: return jsonify({"error": "Not found"}), 404
        return jsonify({"name": user.name, "email": user.email, "education": user.education or "Not specified", "skills": user.skills or "", "profile_pic": user.profile_pic, "whatsapp": user.whatsapp_link or ""})
    else:
        user = Recruiter.query.get(user_id)
        if not user: return jsonify({"error": "Not found"}), 404
        return jsonify({"name": user.name, "email": user.email, "company_name": user.company_name or "Independent", "status": "Verified Partner" if getattr(user, 'is_verified', False) else "Standard Recruiter", "facebook": user.facebook or "", "twitter": user.twitter or "", "website": user.website or "", "profile_pic": user.profile_pic, "position": user.position or ""})

# --- 9. MASTER AI CONFIG & SKILLS ---

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "AIzaSyDeT5dueyBjrcUp1fDdQFmCa5Gnc58rbtQ")

def extract_skills_pro(text_content):
    url = "https://api.apilayer.com/skills/extract"
    headers = {"apikey": os.getenv("SKILLS_API_KEY", "nKpSaFqgGRNiKeVmj2euz0TU9JqOrVrd")}
    try:
        response = requests.post(url, headers=headers, data=text_content.encode("utf-8"))
        if response.status_code == 200:
            return [s['skill'].lower() for s in response.json()]
    except: pass 

    it_keywords = ["python", "javascript", "typescript", "java", "c++", "c#", "rust", "go", "ruby", "php", "swift", "kotlin", "react", "next.js", "angular", "vue", "tailwind", "bootstrap", "html5", "css3", "node", "express", "django", "flask", "fastapi", "spring boot", "machine learning", "deep learning", "nlp", "tensorflow", "pytorch", "pandas", "aws", "azure", "google cloud", "docker", "kubernetes", "sql", "postgresql", "mysql", "mongodb", "redis", "firebase"]
    
    text_lower = text_content.lower()
    pattern = re.compile(r'\b(' + '|'.join(re.escape(word) for word in it_keywords) + r')\b')
    return list(set(pattern.findall(text_lower)))

def get_master_ai_recommendations(user_skills):
    all_posts = Post.query.filter_by(can_apply=True).all()
    market_skills = Counter(extract_skills_pro(" ".join([p.content for p in all_posts])))
    all_students = Student.query.all()
    peer_popularity = Counter(extract_skills_pro(" ".join([(s.skills or "") for s in all_students])))
    user_skills_clean = [s.strip().lower() for s in (user_skills or "").split(',')]
   
    recommendations = []
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    all_relevant_skills = set(list(market_skills.keys()) + list(peer_popularity.keys()))
    
    for skill in all_relevant_skills:
        if skill not in user_skills_clean:
            is_competitive = peer_popularity.get(skill, 0) > (len(all_students) * 0.2) 
            reason = "Competitive Threat" if is_competitive else "Market Demand"
            search_q = f"{skill} mastery tutorial 2026 for developers"

            try:
                search_response = youtube.search().list(q=search_q, part='snippet', maxResults=1, type='video').execute()
                for item in search_response['items']:
                    recommendations.append({"skill": f"{skill.upper()} ({reason})", "title": item['snippet']['title'], "url": f"https://www.youtube.com/watch?v={item['id']['videoId']}", "thumbnail": item['snippet']['thumbnails']['medium']['url']})
            except: continue
            if len(recommendations) >= 5: break 
    return recommendations

@app.route('/skill-development')
def skill_development():
    if 'user_id' not in session or session.get('role') != 'student': return redirect(url_for('login'))
    student_id = session['user_id']
    user = db.session.get(Student, student_id)

    resources = SkillResource.query.filter_by(student_id=student_id).all()
    if not resources:
        ai_results = get_master_ai_recommendations(user.skills or "")
        for rec in ai_results:
            db.session.add(SkillResource(student_id=student_id, title=rec['title'], link=rec['url'], thumbnail=rec['thumbnail'], category=rec['skill']))
        db.session.commit()
        resources = SkillResource.query.filter_by(student_id=student_id).all()

    notifications = Notification.query.filter_by(recipient_id=student_id, recipient_role='student').order_by(Notification.date_created.desc()).limit(10).all()
    unread_count = Notification.query.filter_by(recipient_id=student_id, recipient_role='student', is_read=False).count()

    return render_template('skill_development.html', user=user, resources=resources, notifications=notifications, unread_count=unread_count)

def get_match_score(student_skills, post_content):
    if not student_skills: return 0
    required = extract_skills_pro(post_content)
    if not required: return 0
    student_list = [s.strip().lower() for s in student_skills.split(',')]
    matches = [s for s in required if s.lower() in student_list]
    return round((len(matches) / len(required)) * 100)

@app.context_processor
def inject_sidebar_data():
    try:
        skill_tally = Counter()
        for post in Post.query.all():
            found_skills = extract_skills_pro(post.content)
            if found_skills:
                for skill in found_skills: skill_tally[skill] += 1
        
        student_scores = []
        for s in Student.query.all():
            skill_list = [sk.strip() for sk in (s.skills or "").split(',') if sk.strip()]
            student_scores.append({'name': s.name, 'skill_count': len(skill_list), 'profile_pic': s.profile_pic, 'id': s.student_id, 'top_skills': skill_list[:2]})
        
        return dict(market_trends=skill_tally.most_common(7), top_students=sorted(student_scores, key=lambda x: x['skill_count'], reverse=True)[:5])
    except Exception as e:
        print(f"CRITICAL SIDEBAR ERROR: {e}")
        return dict(market_trends=[], top_students=[])

@app.route('/refresh-skills')
def refresh_ai():
    if 'user_id' in session and session.get('role') == 'student':
        SkillResource.query.filter_by(student_id=session['user_id']).delete()
        db.session.commit()
    return redirect(url_for('skill_development'))

@app.route('/apply/<int:post_id>')
def apply_internship(post_id):
    if 'user_id' not in session or session.get('role') != 'student':
        flash("Please log in as a student to apply.", "warning")
        return redirect(url_for('login'))

    post = Post.query.get_or_404(post_id)
    student = Student.query.get(session['user_id'])
    recruiter = Recruiter.query.get(post.author_id)

    if Application.query.filter_by(post_id=post.id, student_id=student.student_id).first():
        flash("You have already applied for this internship.", "info")
        return redirect(url_for('student_feed'))

    db.session.add(Application(post_id=post.id, student_id=student.student_id, recruiter_id=recruiter.recruiter_id if recruiter else None))

    try:
        if recruiter:
            db.session.add(Notification(recipient_id=recruiter.recruiter_id, recipient_role='recruiter', sender_name=student.name, message=f"applied for your internship: {post.content[:30]}...", is_read=False))
        db.session.commit() 
        
        if recruiter and recruiter.email:
            msg = Message(subject=f"SkillSync Application: {student.name}", sender=app.config.get('MAIL_USERNAME'), recipients=[recruiter.email], body=f"Hello {recruiter.name},\n\n{student.name} has applied for your internship.")
            mail.send(msg)
            flash("Success! Application sent and recruiter notified.", "success")
        else:
            flash("Applied successfully!", "success")
    except Exception as e:
        db.session.rollback()
        print(f"Error: {e}")
        flash("An error occurred. Please try again.", "danger")

    return redirect(url_for('student_feed'))

@app.route('/recruiter/applications')
def view_applications():
    if 'user_id' not in session or session.get('role') != 'recruiter':
        flash("Please log in as a recruiter.", "warning")
        return redirect(url_for('login'))
    
    recruiter_id = session['user_id']
    user = db.session.get(Recruiter, recruiter_id)
    
    notifications = Notification.query.filter_by(recipient_id=recruiter_id, recipient_role='recruiter').order_by(Notification.date_created.desc()).limit(10).all()
    unread_count = Notification.query.filter_by(recipient_id=recruiter_id, recipient_role='recruiter', is_read=False).count()

    applied_students = []
    for app_entry in Application.query.filter_by(recruiter_id=recruiter_id).all():
        student = Student.query.get(app_entry.student_id)
        post = Post.query.get(app_entry.post_id)
        if student and post:
            try: score = get_match_score(student.skills or "", post.content or "")
            except: score = 0 
            applied_students.append({'student': student, 'post_content': post.content, 'score': score, 'date': app_entry.date_applied})

    return render_template('application.html', user=user, user_name=user.name, user_role='recruiter', notifications=notifications, unread_count=unread_count, applications=sorted(applied_students, key=lambda x: x['score'], reverse=True))

'''@app.route('/setup-admin')

def setup_admin():
    # Only create if no admin exists
    if Admin.query.count() == 0:
        admin = Admin(
            name="Super Admin",
            email="admin@skillsync.com",
            password="admin123" # Change this to a secure password
        )
        db.session.add(admin)
        db.session.commit()
        return "Admin account created! You can now log in at /login."
    return "Admin already exists."'''
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
