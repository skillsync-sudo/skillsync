from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import os
import requests
from collections import Counter
#from flask import current_app
import re
from googleapiclient.discovery import build
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from models import db, Student, Recruiter, Admin, Post, Comment, Internship, Like, Notification,SkillResource,Report
from sklearn.feature_extraction.text import TfidfVectorizer
from flask_mail import Mail, Message

#mail = Mail(app)
# 1. SETUP & CONFIGURATION
basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['SECRET_KEY'] = 'skillsync_2026_super_secret'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
UPLOAD_FOLDER = os.path.join('static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

db.init_app(app)

with app.app_context():
    db.create_all()

# --- 2. CORE PAGE ROUTES ---

@app.route('/')
def home():
    return render_template('index.html')

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

        # 1. ADMIN CHECK
        admin = Admin.query.filter_by(email=email).first()
        if admin:
            # This checks BOTH the hashed password and the plain text 'admin123'
            if check_password_hash(admin.password, password) or admin.password == password:
                session['user_id'] = admin.admin_id
                session['role'] = 'admin'
                session['name'] = admin.name
                return redirect(url_for('admin_dashboard'))

        # 2. STUDENT CHECK
        student = Student.query.filter_by(email=email).first()
        # FIX: Check if student exists before checking password
        if student and (check_password_hash(student.password, password) or student.password == password):
            # FIX: Changed 'students' to 'student' (the variable defined above)
            # FIX: Use 'student_id' as defined in your model
            session['user_id'] = student.student_id 
            session['role'] = 'student'
            session['name'] = student.name
            return redirect(url_for('student_feed'))

        # 3. RECRUITER CHECK
        recruiter = Recruiter.query.filter_by(email=email).first()
        # FIX: Check if recruiter exists before checking password
        if recruiter and (check_password_hash(recruiter.password, password) or recruiter.password == password):
            # FIX: Use 'recruiter_id' (assuming your table uses this naming convention)
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
top_skills_cache = {"data": [], "timestamp": None}
@app.route('/student-feed')
def student_feed():
    if 'user_id' not in session or session.get('role') != 'student':
        return redirect(url_for('login'))
    
    user = db.session.get(Student, session['user_id'])
    posts = Post.query.order_by(Post.date_posted.desc()).all()
    notifications = Notification.query.filter_by(
    recipient_id=session['user_id'], 
    recipient_role='student'  # Filter specifically for students
        ).order_by(Notification.date_created.desc()).limit(10).all()

    unread_count = Notification.query.filter_by(
        recipient_id=session['user_id'], 
        recipient_role='student', 
        is_read=False
    ).count()
    all_internships = Post.query.filter_by(can_apply=True).all()
    market_text = " ".join([p.content for p in all_internships])
    
    skills_found = extract_skills_pro(market_text)
    top_skills = Counter(skills_found).most_common(5)
    return render_template('student.html', 
                           user=user, 
                           user_name=user.name, 
                           user_role='student', 
                           posts=posts, 
                           notifications=notifications, 
                           unread_count=unread_count,
                           Student=Student,    
                           Recruiter=Recruiter 
                          )

@app.route('/recruiter/dashboard')
def recruiter_dashboard():
    if 'user_id' not in session or session.get('role') != 'recruiter':
        return redirect(url_for('login'))
    
    user = db.session.get(Recruiter, session['user_id'])
    
    # This fetches ALL posts from the database, newest first
    posts = Post.query.order_by(Post.date_posted.desc()).all()
    
    notifications = Notification.query.filter_by(
    recipient_id=session['user_id'], 
    recipient_role='recruiter' # Filter specifically for recruiters
    ).order_by(Notification.date_created.desc()).limit(10).all()

    unread_count = Notification.query.filter_by(
    recipient_id=session['user_id'], 
    recipient_role='recruiter', 
    is_read=False
    ).count()
    return render_template('recruiter.html', 
                           user=user,
                           user_name=user.name,
                           user_role='recruiter',
                           posts=posts,
                           notifications=notifications,
                           unread_count=unread_count,
                           Student=Student,    # Required for the post header logic
                           Recruiter=Recruiter # Required for the post header logic
                          )
@app.route('/admin/dashboard')
def admin_dashboard():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    stats = {
        'students': Student.query.count(),
        'recruiters': Recruiter.query.count(),
        'posts': Post.query.count(),
        'reports': Report.query.count()
    }
    
    # Getting data for management tables
    reports = Report.query.order_by(Report.date_sent.desc()).all()
    unverified_recruiters = Recruiter.query.filter_by(is_verified=False).all()
    all_posts = Post.query.order_by(Post.date_posted.desc()).limit(20).all()
    
    return render_template('admin.html', 
                       stats=stats, 
                       reports=reports, 
                       unverified_recruiters=unverified_recruiters, # Match the HTML loop name
                       recent_posts=all_posts) # Match the HTML loop name
@app.route('/admin/change-password', methods=['POST'])
def admin_change_password():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    new_password = request.form.get('new_password')
    admin_user = Admin.query.filter_by(email="admin@skillsync.com").first()
    
    if admin_user and new_password:
        admin_user.password = generate_password_hash(new_password)
        db.session.commit()
        flash("Admin password updated!", "success")
        
    return redirect(url_for('admin_dashboard', _anchor='settings'))

@app.route('/admin/verify-recruiter/<int:rec_id>')
def verify_recruiter(rec_id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    recruiter = Recruiter.query.get_or_404(rec_id)
    recruiter.is_verified = True
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete-post/<int:post_id>')
def admin_delete_post(post_id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
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
    
    new_post = Post(
        content=request.form.get('content'),
        author_name=session['name'],
        author_role=session['role'],
        author_id=session['user_id'],
        can_apply='can_apply' in request.form
    )
    db.session.add(new_post)
    db.session.commit()
    return redirect(request.referrer or url_for('home'))
# ================= DELETE POST =================
@app.route('/delete_post/<int:post_id>')
def delete_post(post_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    
    post = db.session.get(Post, post_id)
    if not post:
        flash("Post not found.", "warning")
        return redirect(request.referrer)
    
    # Check permission (ID + ROLE)
    if post.author_id != session.get('user_id') or post.author_role != session.get('role'):
        flash("You do not have permission to delete this post!", "danger")
        return redirect(request.referrer)
    
    db.session.delete(post)
    db.session.commit() # This also deletes associated Likes and Comments because of cascade
    flash("Post deleted successfully.", "success")
    return redirect(request.referrer)

# ================= LIKE POST (With Multi-User Tracking) =================
@app.route('/like/<int:post_id>')
def like_post(post_id):
    if 'user_id' not in session: return redirect(url_for('login'))

    u_id = session.get('user_id')
    u_role = session.get('role')
    post = db.session.get(Post, post_id)

    if post:
        existing_like = Like.query.filter_by(user_id=u_id, user_role=u_role, post_id=post_id).first()
        
        if not existing_like:
            # 1. Add the like
            new_like = Like(user_id=u_id, user_role=u_role, post_id=post_id)
            db.session.add(new_like)
            post.likes_count = (post.likes_count or 0) + 1
            
            # 2. THE FIX: Define the message and check for duplicates
            notif_msg = f"liked your post: {post.content[:20]}..."
            
            # Check if this specific notification already exists
            already_notified = Notification.query.filter_by(
                recipient_id=post.author_id,
                recipient_role=post.author_role, # Matches the author's role
                sender_name=session.get('name'),
                message=notif_msg
            ).first()

            # 3. Only add if it's not a duplicate and not liking own post
            if not already_notified and (post.author_id != u_id or post.author_role != u_role):
                new_notif = Notification(
                    recipient_id=post.author_id,
                    recipient_role=post.author_role, # This ensures it goes to the right person
                    sender_name=session.get('name'),
                    message=notif_msg
                )
                db.session.add(new_notif)
            
            db.session.commit()
        else:
            # Unlike logic
            db.session.delete(existing_like)
            post.likes_count = max(0, post.likes_count - 1)
            db.session.commit()

    return redirect(request.referrer or url_for('student_feed'))
# ================= ADD COMMENT =================
@app.route('/comment/<int:post_id>', methods=['POST'])
def add_comment(post_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    
    post = db.session.get(Post, post_id)
    text = request.form.get('comment_text')
    
    if text and post:
        # Create the comment
        comment = Comment(
            text=text, 
            author_name=session['name'], 
            author_id=session['user_id'], 
            author_role=session['role'],
            post_id=post_id
        )
        db.session.add(comment)
        
        # Create notification for author
        if post.author_id != session['user_id'] or post.author_role != session['role']:
            new_notif = Notification(
                recipient_id=post.author_id, 
                recipient_role=post.author_role,
                sender_name=session['name'], 
                message=f"commented on your post"
            )
            db.session.add(new_notif)
            
        db.session.commit()
    return redirect(request.referrer)

# --- 6. PROFILE EDITING ---

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
            filename = secure_filename(f"std_{user.student_id}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            user.profile_pic = filename
    db.session.commit()
    session['name'] = user.name
    return redirect(url_for('student_feed'))

@app.route('/edit-recruiter-profile', methods=['POST'])
def edit_recruiter_profile():
    if 'user_id' not in session or session['role'] != 'recruiter': 
        return redirect(url_for('login'))
        
    user = Recruiter.query.get(session['user_id'])
    
    # Update fields from form
    user.name = request.form.get('name')
    user.company_name = request.form.get('company')
    user.phone = request.form.get('phone')
    user.website = request.form.get('website')
    user.facebook = request.form.get('facebook')
    user.twitter = request.form.get('twitter')
    user.position = request.form.get('position')
    # user.bio = request.form.get('bio') # Removed per request
    
    if 'profile_pic' in request.files:
        file = request.files['profile_pic']
        if file and file.filename != '':
            filename = secure_filename(f"rec_{user.recruiter_id}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            user.profile_pic = filename
            
    db.session.commit()
    session['name'] = user.name
    return redirect(url_for('recruiter_dashboard'))

# --- 7. UTILITIES ---
@app.route('/delete-comment/<int:comment_id>')
def delete_comment(comment_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    comment = Comment.query.get_or_404(comment_id)
    # Check if the current user is the author of the comment
    if comment.author_id == session['user_id']:
        db.session.delete(comment)
        db.session.commit()
        flash("Comment deleted.", "success")
    
    return redirect(request.referrer)

@app.route('/clear-notifications')
def clear_notifications():
    if 'user_id' in session:
        # Mark all as read for this specific user and role
        Notification.query.filter_by(
            recipient_id=session['user_id'], 
            recipient_role=session['role'], 
            is_read=False
        ).update({"is_read": True})
        
        db.session.commit()
        return jsonify({"status": "success"})
    return jsonify({"status": "unauthorized"}), 401

@app.route('/submit-report', methods=['POST'])
def submit_report():
    print("--- DEBUG REPORT SUBMISSION ---")
    print(f"User ID in Session: {session.get('user_id')}")
    print(f"Role in Session: {session.get('role')}")  # <--- This MUST say 'student' or 'recruiter'

    if 'user_id' not in session:
        print("ERROR: User ID missing, redirecting to login.")
        return redirect(url_for('login'))

    message_content = request.form.get('message')
    sender_name = session.get('name')
    sender_role = session.get('role', 'student') # Default to student if missing

    if message_content:
        try:
            new_report = Report(
                sender_name=sender_name,
                sender_role=sender_role,
                message=message_content
            )
            db.session.add(new_report)
            db.session.commit()
            print("SUCCESS: Report written to database.")
            
            # Keep session alive
            session.modified = True 
            
        except Exception as e:
            db.session.rollback()
            print(f"DATABASE ERROR: {e}")
    if session.get('role') == 'student':
        return redirect(url_for('student_feed'))
    elif session.get('role') == 'recruiter':
        return redirect(url_for('recruiter_dashboard'))
    else:
        return redirect(url_for('home'))

# --- 8. API ROUTES (For Search & Popups) ---

@app.route('/api/search')
def api_search():
    query = request.args.get('query', '').lower()
    search_type = request.args.get('type', 'all')
    results = {'people': [], 'internships': []}
    
    if not query: return jsonify(results)

    if search_type in ['all', 'people']:
        students = Student.query.filter(Student.name.ilike(f'%{query}%')).limit(5).all()
        recruiters = Recruiter.query.filter(Recruiter.name.ilike(f'%{query}%')).limit(5).all()
        
        for s in students:
            results['people'].append({'id': s.student_id, 'name': s.name, 'role': 'student'})
        for r in recruiters:
            results['people'].append({'id': r.recruiter_id, 'name': r.name, 'role': 'recruiter'})

    if search_type in ['all', 'internships']:
        posts = Post.query.filter(Post.can_apply == True, Post.content.ilike(f'%{query}%')).limit(5).all()
        for p in posts:
            results['internships'].append({'id': p.id, 'title': p.content[:30] + "..."})

    return jsonify(results)

# Add this near your other UTILITIES routes in app.py
@app.route('/api/user-details/<role>/<int:user_id>')
def get_user_details(role, user_id):
    if role == 'student':
        user = Student.query.get(user_id)
        if not user: return jsonify({"error": "Not found"}), 404
        return jsonify({
            "name": user.name,
            "email": user.email,
            "education": user.education or "Not specified",
            "skills": user.skills or "",
            "profile_pic": user.profile_pic,
            "whatsapp": user.whatsapp_link or ""
        })
    else:
        user = Recruiter.query.get(user_id)
        if not user: return jsonify({"error": "Not found"}), 404
        return jsonify({
            "name": user.name,
            "email": user.email,
            "company_name": user.company_name or "Independent",
            "status": "Verified Partner" if getattr(user, 'is_verified', False) else "Standard Recruiter",
            "facebook": user.facebook or "",
            "twitter": user.twitter or "",
            "website": user.website or "",
            "profile_pic": user.profile_pic,
            "position": user.position or ""
        })


# --- NEW MASTER AI CONFIG ---
YOUTUBE_API_KEY = "AIzaSyDeT5dueyBjrcUp1fDdQFmCa5Gnc58rbtQ"
# Get your free key at apilayer.com (Skills API)
SKILLS_API_KEY = "nKpSaFqgGRNiKeVmj2euz0TU9JqOrVrd" 

def extract_skills_pro(text_content):

    url = "https://api.apilayer.com/skills/extract"
    headers = {"apikey": "nKpSaFqgGRNiKeVmj2euz0TU9JqOrVrd"}
    
    try:
        response = requests.post(url, headers=headers, data=text_content.encode("utf-8"))
        if response.status_code == 200:
            return [s['skill'].lower() for s in response.json()]
    except:
        pass 

    # --- 100+ KEYWORD IT DATABASE ---
    it_keywords = [
        # Languages
        "python", "javascript", "typescript", "java", "c++", "c#", "rust", "go", "ruby", "php", "swift", "kotlin", "dart", "scala", "perl", "bash", "powershell", "r language", "solidity", "objective-c",
        # Web Frontend
        "react", "next.js", "angular", "vue", "svelte", "tailwind", "bootstrap", "three.js", "html5", "css3", "sass", "jquery", "webpack", "vite", "redux", "zustand", "webassembly", "responsive design",
        # Backend & Frameworks
        "node", "express", "django", "flask", "fastapi", "spring boot", "laravel", "rails", "asp.net", "nest.js", "graphql", "rest api", "microservices", "socket.io", "grpc",
        # AI & Data Science
        "machine learning", "deep learning", "nlp", "tensorflow", "pytorch", "pandas", "numpy", "scikit-learn", "langchain", "agentic ai", "llm", "vector databases", "tableau", "powerbi", "opencv", "data visualization", "data science", "data structures", "algorithms",
        # Cloud & DevOps
        "aws", "azure", "google cloud", "gcp", "docker", "kubernetes", "terraform", "ansible", "jenkins", "ci/cd", "linux", "nginx", "github actions", "prometheus", "grafana", "cloud computing", "serverless",
        # Databases
        "sql", "postgresql", "mysql", "mongodb", "redis", "firebase", "cassandra", "oracle", "sqlite", "elasticsearch", "dynamodb", "snowflake",
        # Mobile & UI/UX
        "flutter", "react native", "swiftui", "figma", "ui/ux", "adobe xd", "android studio", "ios development", "mobile development",
        # Cybersecurity
        "ethical hacking", "penetration testing", "wireshark", "nmap", "owasp", "cryptography", "network security", "firewall", "siem", "cybersecurity",
        # Industry Tools & Systems
        "git", "github", "bitbucket", "jira", "agile", "scrum", "system design", "unit testing", "playwright", "cypress", "postman", "blockchain", "web3", "iot", "internet of things", "rpa", "edge computing"
    ]

    # --- MATCHING LOGIC ---
    # We use a case-insensitive boundary search to ensure 'Java' doesn't match 'JavaScript'
    text_lower = text_content.lower()
    found = []
    
    # We use a single regex join for speed (highly recommended for 100+ keywords)
    pattern = re.compile(r'\b(' + '|'.join(re.escape(word) for word in it_keywords) + r')\b')
    matches = pattern.findall(text_lower)
    
    # Return unique found skills
    return list(set(matches))
def get_master_ai_recommendations(user_skills):
    
    # 1. ANALYZE MARKET (What recruiters want)
    all_posts = Post.query.filter_by(can_apply=True).all()
    
    market_text = " ".join([p.content for p in all_posts])
    market_skills = Counter(extract_skills_pro(market_text))

    # 2. ANALYZE PEERS (Competitive Benchmarking)
    all_students = Student.query.all()
    peer_skills_text = " ".join([(s.skills or "") for s in all_students])
    peer_skills_list = extract_skills_pro(peer_skills_text)
    peer_popularity = Counter(peer_skills_list)

    # 3. USER GAP ANALYSIS
    user_skills_clean = [s.strip().lower() for s in (user_skills or "").split(',')]
   
    recommendations = []
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

    # Logic: If skill is in demand OR peers have it, and user DOESN'T have it
    all_relevant_skills = set(list(market_skills.keys()) + list(peer_popularity.keys()))
    
    for skill in all_relevant_skills:
        if skill not in user_skills_clean:
            # Determine if this is a "Competitive Gap" (many peers have it)
            peer_count = peer_popularity.get(skill, 0)
            is_competitive = peer_count > (len(all_students) * 0.2) # 20% threshold
            
            reason = "Competitive Threat" if is_competitive else "Market Demand"
            search_q = f"{skill} mastery tutorial 2026 for developers"

            try:
                search_response = youtube.search().list(
                    q=search_q,
                    part='snippet',
                    maxResults=1,
                    type='video'
                ).execute()

                for item in search_response['items']:
                    recommendations.append({
                        "skill": f"{skill.upper()} ({reason})",
                        "title": item['snippet']['title'],
                        "url": f"https://www.youtube.com/watch?v={item['id']['videoId']}",
                        "thumbnail": item['snippet']['thumbnails']['medium']['url']
                    })
            except: continue
            
            if len(recommendations) >= 50: break # Limit to 4 to save API quota

    return recommendations
@app.route('/skill-development')
def skill_development():
    if 'user_id' not in session or session.get('role') != 'student':
        return redirect(url_for('login'))
    
    student_id = session['user_id']
    user = db.session.get(Student, session['user_id'])

    # 1. Check if we already have resources saved
    resources = SkillResource.query.filter_by(student_id=student_id).all()

    # 2. ONLY run AI if there are no resources (first time)
    if not resources:
        ai_results = get_master_ai_recommendations(user.skills or "")
        for rec in ai_results:
            new_res = SkillResource(
                student_id=student_id,
                title=rec['title'],
                link=rec['url'],
                thumbnail=rec['thumbnail'],
                category=rec['skill']
            )
            db.session.add(new_res)
        db.session.commit()
        # Refresh the resources list after adding
        resources = SkillResource.query.filter_by(student_id=student_id).all()

    # 3. Notification Logic (Remains fast)
    notifications = Notification.query.filter_by(
        recipient_id=student_id, 
        recipient_role='student'
    ).order_by(Notification.date_created.desc()).limit(10).all()

    unread_count = Notification.query.filter_by(
        recipient_id=student_id, 
        recipient_role='student', 
        is_read=False
    ).count()

    return render_template('skill_development.html', 
                           user=user, 
                           resources=resources, 
                           notifications=notifications, 
                           unread_count=unread_count)

def get_match_score(student_skills, post_content):
    if not student_skills: return 0
    # Use your AI logic to see what the post needs
    required = extract_skills_pro(post_content)
    if not required: return 0
    
    student_list = [s.strip().lower() for s in student_skills.split(',')]
    matches = [s for s in required if s.lower() in student_list]
    
    # Calculate percentage
    score = (len(matches) / len(required)) * 100
    return round(score)
@app.context_processor
def inject_market_trends():
    """
    Makes 'market_trends' variable available in all templates for the sidebar.
    Processes both 'apply' and 'not apply' posts as requested.
    """
    try:
        # 1. Fetch all posts from recruiters
        all_posts = Post.query.all() 
        
        # 2. Tally every mention of a technical skill
        skill_tally = Counter()
        for post in all_posts:
            # We use your extract_skills_pro function for each post
            found_skills = extract_skills_pro(post.content)
            for skill in found_skills:
                skill_tally[skill] += 1
        
        # 3. Get the top 7 most mentioned skills
        top_trends = skill_tally.most_common(7)
        
        return dict(market_trends=top_trends)
    except:
        # Fallback if DB is empty or error occurs
        return dict(market_trends=[])

@app.route('/refresh-skills')
def refresh_ai():
    if 'user_id' in session and session.get('role') == 'student':
        student_id = session['user_id']
        # Only delete when explicitly asked
        SkillResource.query.filter_by(student_id=student_id).delete()
        db.session.commit()
    return redirect(url_for('skill_development'))
@app.route('/apply/<int:post_id>')
def apply_internship(post_id):
    if 'user_id' not in session or session.get('role') != 'student':
        flash("Please log in as a student to apply.", "warning")
        return redirect(url_for('login'))

    # 1. Fetch data from DB
    post = Post.query.get_or_404(post_id)
    student = Student.query.get(session['user_id'])
    recruiter = Recruiter.query.get(post.author_id)

    # 2. Save the Application record to Database
    new_app = Application(
        post_id=post.id,
        student_id=student.student_id,
        recruiter_id=recruiter.recruiter_id
    )
    db.session.add(new_app)

    # 3. Create Gmail Message
    msg = Message(
        subject=f"SkillSync Application: {student.name}",
        recipients=[recruiter.email],  # Sends to recruiter's Gmail
        body=f"Hello {recruiter.name},\n\n"
             f"{student.name} has applied for your internship post.\n"
             f"Student Email: {student.email}\n"
             f"Skills: {student.skills}\n\n"
             f"Log in to SkillSync to view their full profile."
    )

    # 4. Attempt to send
    try:
        mail.send(msg)
        db.session.commit()
        flash("Success! Application saved and emailed to recruiter.", "success")
    except Exception as e:
        db.session.rollback()
        print(f"Gmail Error: {e}")
        flash("Database saved, but Gmail failed. Check SMTP settings.", "danger")

    return redirect(url_for('student_feed'))

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
    app.run(debug=True, host='0.0.0.0', port=5000)