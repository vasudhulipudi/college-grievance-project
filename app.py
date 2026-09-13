from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_mail import Mail, Message
import os
import re
import uuid
import io
import csv
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher
from dotenv import load_dotenv
from sqlalchemy import func
from moderation_engine import evaluate_content

# Safe imports for Excel & PDF Generation
try:
    import xlsxwriter
    HAS_XLSXWRITER = True
except ImportError:
    HAS_XLSXWRITER = False

try:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

# Load environment variables from .env file
load_dotenv()

# Initialize Flask Application
app = Flask(__name__)

# --- CONFIGURATION ---
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your_super_secret_key_for_production')

# Database Configuration (Supports Cloud DATABASE_URL or local MySQL)
database_url = os.getenv('DATABASE_URL')
if database_url:
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    elif database_url.startswith("mysql://"):
        database_url = database_url.replace("mysql://", "mysql+pymysql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    db_user = os.getenv('DB_USERNAME', 'root')
    db_pass = os.getenv('DB_PASSWORD', 'vasu123')
    db_host = os.getenv('DB_HOST', 'localhost')
    db_name = os.getenv('DB_NAME', 'college_grievance_db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{db_user}:{db_pass}@{db_host}/{db_name}'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 280,
}

# Email (SMTP) Configuration
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'True').lower() in ['true', '1', 'yes']
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME', 'suryakiransrinivasdhulipudi@gmail.com')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD', 'covn scbn zkma vpjm')
app.config['MAIL_DEFAULT_SENDER'] = ('College Grievance System', app.config['MAIL_USERNAME'])

# Initialize Extensions
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
mail = Mail(app)

# --- DATABASE MODELS ---

class CollegeStudent(db.Model):
    __tablename__ = 'college_students'
    roll_number = db.Column(db.String(50), primary_key=True)
    student_name = db.Column(db.String(100), nullable=False)
    is_registered = db.Column(db.Boolean, default=False)

class RegisteredStudent(db.Model, UserMixin):
    __tablename__ = 'registered_students'
    id = db.Column(db.Integer, primary_key=True)
    roll_number = db.Column(db.String(50), db.ForeignKey('college_students.roll_number'), unique=True, nullable=False)
    student_name = db.Column(db.String(100), nullable=False)
    personal_email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    
    def get_id(self):
        return f"student_{self.id}"

class Admin(db.Model, UserMixin):
    __tablename__ = 'admins'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    
    def get_id(self):
        return f"admin_{self.id}"

class Principal(db.Model, UserMixin):
    __tablename__ = 'principals'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    
    def get_id(self):
        return f"principal_{self.id}"

class Complaint(db.Model):
    __tablename__ = 'complaints'
    id = db.Column(db.Integer, primary_key=True)
    complaint_ref_id = db.Column(db.String(50), unique=True, nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('registered_students.id'), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    priority = db.Column(db.String(20), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)
    support_count = db.Column(db.Integer, default=0)
    status = db.Column(db.String(50), default='Submitted')
    is_escalated = db.Column(db.Boolean, default=False)
    escalation_notified = db.Column(db.Boolean, default=False)
    submitted_at = db.Column(db.DateTime, default=datetime.now)
    moderation_status = db.Column(db.String(20), default='Approved') # 'Approved', 'Flagged', 'Quarantined'
    moderation_score = db.Column(db.Integer, default=0) # 0 to 100
    moderation_flags = db.Column(db.String(255), nullable=True)
    replies = db.relationship('ComplaintReply', backref='complaint', lazy=True, order_by='desc(ComplaintReply.replied_at)')

class ModerationLog(db.Model):
    __tablename__ = 'moderation_logs'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('registered_students.id'), nullable=True)
    student_roll = db.Column(db.String(50), nullable=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=True)
    action_taken = db.Column(db.String(50), nullable=False) # 'BLOCKED', 'FLAGGED', 'CLEAN'
    risk_score = db.Column(db.Integer, default=0)
    detected_flags = db.Column(db.String(255), nullable=True)
    reasons = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)

class ComplaintSupport(db.Model):
    __tablename__ = 'complaint_support'
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey('complaints.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('registered_students.id'), nullable=False)
class SystemSetting(db.Model):
    __tablename__ = 'system_settings'
    id = db.Column(db.Integer, primary_key=True)
    high_escalation_days = db.Column(db.Integer, default=3)
    standard_escalation_days = db.Column(db.Integer, default=7)
    maintenance_mode = db.Column(db.Boolean, default=False)
class ComplaintReply(db.Model):
  __tablename__ = 'complaint_replies'
  id = db.Column(db.Integer, primary_key=True)
  complaint_id = db.Column(db.Integer, db.ForeignKey('complaints.id'), nullable=False)
  reply_text = db.Column(db.Text, nullable=False)
  replied_by_role = db.Column(db.String(50), nullable=False) 
  replied_by_id = db.Column(db.Integer, nullable=False)
  replied_at = db.Column(db.DateTime, default=datetime.now)
class Announcement(db.Model):
    __tablename__ = 'announcements'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    posted_by_role = db.Column(db.String(50), nullable=False) # 'Admin' or 'Principal'
    posted_by_id = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

class RevokedStudent(db.Model):
    __tablename__ = 'revoked_students'
    id = db.Column(db.Integer, primary_key=True)
    roll_number = db.Column(db.String(50), unique=True, nullable=False)
    revoked_at = db.Column(db.DateTime, default=datetime.now)
    reason = db.Column(db.String(255), default='Administrative revocation by Principal')

# --- CORE BUSINESS LOGIC FUNCTIONS ---
@login_manager.user_loader
def load_user(user_id):
    if not user_id:
        return None
    try:
        user_str = str(user_id)
        if '_' in user_str:
            role, uid = user_str.split('_', 1)
            if role == 'student':
                return db.session.get(RegisteredStudent, int(uid))
            elif role == 'admin':
                return db.session.get(Admin, int(uid))
            elif role == 'principal':
                return db.session.get(Principal, int(uid))
        else:
            # Fallback for plain numeric user ID (e.g. legacy session cookies)
            return db.session.get(RegisteredStudent, int(user_str))
    except Exception as e:
        print(f"User loader exception for ID '{user_id}': {e}")
        return None
    return None

def generate_complaint_id():
    """
    Generates a unique sequential complaint tracking reference ID (e.g. CGMS-2026-0019).
    Safely inspects existing IDs to determine the true maximum sequence number, avoiding collisions
    even when earlier records have been deleted or archived.
    """
    current_year = datetime.now().year
    prefix = f"CGMS-{current_year}-"
    
    # Query all complaints for the current year
    records = Complaint.query.filter(Complaint.complaint_ref_id.like(f"{prefix}%")).all()
    
    max_seq = 0
    for record in records:
        ref = record.complaint_ref_id or ''
        parts = ref.split('-')
        if len(parts) == 3 and parts[2].isdigit():
            seq = int(parts[2])
            if seq > max_seq:
                max_seq = seq
                
    next_number = max_seq + 1
    new_ref_id = f"{prefix}{next_number:04d}"
    
    # Absolute collision protection guarantee
    while Complaint.query.filter_by(complaint_ref_id=new_ref_id).first() is not None:
        next_number += 1
        new_ref_id = f"{prefix}{next_number:04d}"
        
    return new_ref_id

def send_admin_notification(complaint):
    """
    Sends email notification to administrators when a new complaint is submitted.
    """
    try:
        # Collect admin emails from database
        admin_records = Admin.query.all()
        recipients = [a.email for a in admin_records if a.email and '@' in a.email]
        primary_admin_email = 'dhulipudisuryakiransrinivas@gmail.com'
        if not recipients:
            recipients = [primary_admin_email]
        elif primary_admin_email not in recipients:
            recipients.append(primary_admin_email)

        msg = Message(
            subject=f"New Grievance Logged: {complaint.complaint_ref_id} - {complaint.priority} Priority",
            recipients=recipients
        )
        msg.body = f"""
A new grievance has been submitted to the College Grievance System.

--- TICKET DETAILS ---
Complaint ID : {complaint.complaint_ref_id}
Category     : {complaint.category}
Priority     : {complaint.priority}
Title        : {complaint.title}
Submitted At : {complaint.submitted_at.strftime('%Y-%m-%d %H:%M:%S') if complaint.submitted_at else 'Just now'}

Action Required: Please log in to the Admin Control Panel to review the full description and update the status of this ticket.
        """
        mail.send(msg)
        print(f"Success: Admin notification email sent for {complaint.complaint_ref_id} to {recipients}")
    except Exception as e:
        print(f"Admin Email Failed to Send: {e}")

def send_principal_escalation_notification(complaint, student=None):
    """
    Sends an urgent email notification to the Super Admin (Principal) when an unresolved complaint breaches SLA thresholds and escalates.
    """
    try:
        principal_records = Principal.query.all()
        recipients = [p.email for p in principal_records if p.email and '@' in p.email]
        primary_principal_email = 'vasudhulipudi0@gmail.com'
        if not recipients:
            recipients = [primary_principal_email]
        elif primary_principal_email not in recipients:
            recipients.append(primary_principal_email)

        student_info = f"{student.student_name} ({student.roll_number}) - {student.personal_email}" if student else "Confidential Enrolled Student"
        
        msg = Message(
            subject=f"[ESCALATION ALERT] Overdue Grievance Escalated to Principal: {complaint.complaint_ref_id}",
            recipients=recipients
        )
        msg.body = f"""
URGENT: GRIEVANCE SLA BREACH ESCALATION

Dear Principal Sir / Madam,

An unresolved student grievance has exceeded the statutory resolution timeframe without remediation and has been automatically escalated to your Executive Desk for immediate intervention.

--- ESCALATED TICKET DETAILS ---
Reference ID    : {complaint.complaint_ref_id}
Category        : {complaint.category}
Priority        : {complaint.priority}
Title           : {complaint.title}
Current Status  : {complaint.status}
Date Submitted  : {complaint.submitted_at.strftime('%Y-%m-%d %H:%M:%S') if complaint.submitted_at else 'N/A'}
Complainant     : {student_info}
Peer Support    : {complaint.support_count} student(s)

--- GRIEVANCE NARRATIVE ---
{complaint.description}

Action Required:
Please log in to the Principal Executive Console to investigate this matter, communicate with the student, or issue direct orders to the department:
http://127.0.0.1:5000/login?role=principal

Sincerely,
Automated SLA Escalation Daemon
College Grievance & Facility Management System
        """
        mail.send(msg)
        print(f"Success: Principal escalation email sent for {complaint.complaint_ref_id} to {recipients}")
    except Exception as e:
        print(f"Principal Escalation Email Failed to Send: {e}")

def send_student_confirmation(complaint, student):
    """
    Sends a confirmation receipt email to the student upon successful grievance submission.
    """
    try:
        if not student or not student.personal_email:
            return
            
        msg = Message(
            subject=f"Grievance Submitted Successfully: {complaint.complaint_ref_id}",
            recipients=[student.personal_email]
        )
        msg.body = f"""
Dear {student.student_name},

Thank you for bringing this matter to our attention. Your grievance has been registered successfully in the College Grievance & Facility Management System.

--- YOUR GRIEVANCE DETAILS ---
Tracking ID : {complaint.complaint_ref_id}
Category    : {complaint.category}
Priority    : {complaint.priority}
Title       : {complaint.title}
Status      : Submitted
Date Logged : {complaint.submitted_at.strftime('%Y-%m-%d %H:%M:%S') if complaint.submitted_at else 'Just now'}

You can log in to your Student Dashboard anytime to track live updates, view administrator responses, and review the grievance resolution timeline.

Sincerely,
Campus Administration & Facility Management
*This is an automated confirmation email. Please do not reply directly to this address.*
        """
        mail.send(msg)
        print(f"Success: Confirmation email sent to student {student.personal_email} for {complaint.complaint_ref_id}")
    except Exception as e:
        print(f"Student Confirmation Email Failed to Send: {e}")

def send_student_notification(complaint, student, new_status):
    """
    Automatically emails the student when an admin changes their ticket status.
    """
    try:
        if not student or not student.personal_email:
            return

        msg = Message(
            subject=f"Update on Your Grievance: {complaint.complaint_ref_id}",
            recipients=[student.personal_email]
        )
        msg.body = f"""
Dear {student.student_name},

The status of your grievance ({complaint.complaint_ref_id}) has been officially updated by the Administration.

New Status: {new_status}
Issue Title: {complaint.title}

Please log in to your Student Dashboard to view the official reply and tracking timeline.

*Note: This is an automated system email. Please do not reply directly to this address.*
        """
        mail.send(msg)
        print(f"Success: Status update email sent to {student.personal_email}")
    except Exception as e:
        print(f"Email Failed to Send: {e}")

# --- SMART DUPLICATE DETECTION LOGIC ---

CATEGORY_ALIASES = {
    'academic': 'Academic',
    'academics': 'Academic',
    'curriculum': 'Academic',
    'syllabus': 'Academic',
    'exam': 'Academic',
    'exams': 'Academic',
    'examination': 'Academic',
    'faculty': 'Faculty',
    'faculties': 'Faculty',
    'teacher': 'Faculty',
    'teachers': 'Faculty',
    'instructor': 'Faculty',
    'library': 'Library',
    'book': 'Library',
    'books': 'Library',
    'lab': 'Laboratory',
    'laboratory': 'Laboratory',
    'equipment': 'Laboratory',
    'hostel': 'Hostel',
    'hostels': 'Hostel',
    'room': 'Hostel',
    'transport': 'Transport',
    'bus': 'Transport',
    'buses': 'Transport',
    'sports': 'Sports',
    'gym': 'Sports',
    'canteen': 'Canteen',
    'food': 'Canteen',
    'mess': 'Canteen',
    'infrastructure': 'Infrastructure',
    'building': 'Infrastructure',
    'maintenance': 'Infrastructure',
    'other': 'Other'
}

CUSTOM_STEMS = {
    'mathematics': 'math',
    'maths': 'math',
    'faculties': 'facult',
    'faculty': 'facult',
    'teachers': 'teacher',
    'teaching': 'teach',
    'classes': 'class',
    'classroom': 'class',
    'classrooms': 'class',
    'exams': 'exam',
    'examination': 'exam',
    'examinations': 'exam',
    'buses': 'bus',
    'hostels': 'hostel',
    'laboratories': 'lab',
    'labs': 'lab',
    'toilets': 'washroom',
    'restrooms': 'washroom',
    'washrooms': 'washroom',
    'internet': 'wifi',
    'network': 'wifi'
}

STOP_WORDS = {
    'a', 'about', 'above', 'after', 'again', 'against', 'all', 'am', 'an', 'and', 'any', 'are', 
    'as', 'at', 'be', 'because', 'been', 'before', 'being', 'below', 'between', 'both', 'but', 'by', 
    'can', 'could', 'did', 'do', 'does', 'doing', 'down', 'during', 'each', 'few', 'for', 'from', 
    'further', 'had', 'has', 'have', 'having', 'he', 'her', 'here', 'hers', 'him', 'his', 'how', 
    'i', 'if', 'in', 'into', 'is', 'it', 'its', 'let', 'me', 'more', 'most', 'my', 'myself', 'no', 
    'nor', 'not', 'of', 'off', 'on', 'once', 'only', 'or', 'other', 'our', 'ours', 'out', 'over', 
    'own', 'same', 'she', 'should', 'so', 'some', 'such', 'than', 'that', 'the', 'their', 'theirs', 
    'them', 'then', 'there', 'these', 'they', 'this', 'those', 'through', 'to', 'too', 'under', 
    'until', 'up', 'very', 'was', 'we', 'were', 'what', 'when', 'where', 'which', 'while', 'who', 
    'whom', 'why', 'with', 'would', 'you', 'your', 'yours', 'please', 'kindly', 'urgent', 'urgently',
    'issue', 'problem', 'complaint', 'regarding', 'want', 'need'
}

def normalize_category(cat):
    if not cat:
        return ''
    clean = cat.strip().lower()
    return CATEGORY_ALIASES.get(clean, clean.rstrip('s').capitalize())

def extract_meaningful_tokens(text):
    if not text:
        return set()
    words = re.findall(r'[a-zA-Z0-9]+', text.lower())
    tokens = set()
    for w in words:
        if len(w) >= 2 and w not in STOP_WORDS:
            w = CUSTOM_STEMS.get(w, w)
            if len(w) > 3 and w.endswith('s') and not w.endswith('ss'):
                w = w.rstrip('s')
            tokens.add(w)
    return tokens

def find_similar_complaint(category, title, description=''):
    """
    Intelligently identifies active complaints with similar subject matter across
    normalized categories using token overlap, fuzzy string matching, and semantic clustering.
    """
    if not title or not title.strip():
        return None
        
    norm_cat = normalize_category(category)
    new_tokens = extract_meaningful_tokens(title)
    new_title_clean = title.strip().lower()
    
    # Query all active grievances
    active_complaints = Complaint.query.filter(
        Complaint.status.in_(['Submitted', 'Under Review', 'In Progress'])
    ).all()
    
    best_match = None
    best_score = 0.0
    
    for comp in active_complaints:
        comp_cat = normalize_category(comp.category)
        cat_match = (not norm_cat) or (not comp_cat) or (norm_cat == comp_cat) or (norm_cat in comp_cat) or (comp_cat in norm_cat)
        
        existing_title_clean = comp.title.strip().lower()
        existing_tokens = extract_meaningful_tokens(comp.title)
        
        # 1. Exact title match
        if new_title_clean == existing_title_clean:
            if cat_match or len(new_title_clean) > 4:
                return comp
                
        # 2. Substring containment
        if len(new_title_clean) >= 5 and (new_title_clean in existing_title_clean or existing_title_clean in new_title_clean):
            if cat_match:
                return comp
                
        # 3. Token overlap score
        common_tokens = new_tokens.intersection(existing_tokens)
        seq_ratio = SequenceMatcher(None, new_title_clean, existing_title_clean).ratio()
        
        token_score = 0.0
        if new_tokens and existing_tokens and common_tokens:
            token_score = len(common_tokens) / min(len(new_tokens), len(existing_tokens))
            
        score = (token_score * 0.65) + (seq_ratio * 0.35)
        
        # Significant keyword matches
        if len(common_tokens) >= 2:
            score = max(score, 0.75)
        elif len(common_tokens) == 1 and min(len(new_tokens), len(existing_tokens)) <= 2:
            score = max(score, 0.60)
            
        # Check description overlap if available
        if description and comp.description:
            d_tok_new = extract_meaningful_tokens(description)
            d_tok_exist = extract_meaningful_tokens(comp.description)
            d_common = d_tok_new.intersection(d_tok_exist)
            if len(d_common) >= 2:
                score += 0.15
                
        if cat_match:
            score += 0.10
        else:
            score -= 0.15
            
        if score > best_score:
            best_score = score
            best_match = comp
            
    # Confidence threshold: 0.45 indicates strong correlation
    if best_score >= 0.45:
        return best_match
        
    return None        

# --- PUBLIC ROUTES ---

@app.route('/')
def index():
    return render_template('splash.html')

@app.route('/home')
@app.route('/home.html')
def home():
    return render_template('home.html')

@app.route('/api/track/<ref_id>')
def api_track_grievance(ref_id):
    """
    Public lookup endpoint to allow students to quickly check the status of a grievance by Ref ID.
    Note: Personal student information is never exposed, preserving 100% anonymity.
    """
    clean_id = ref_id.strip()
    complaint = Complaint.query.filter(Complaint.complaint_ref_id.ilike(clean_id)).first()
    if complaint:
        return jsonify({
            'found': True,
            'ref_id': complaint.complaint_ref_id,
            'title': complaint.title,
            'category': complaint.category,
            'priority': complaint.priority,
            'status': complaint.status,
            'submitted_at': complaint.submitted_at.strftime('%d %b %Y, %I:%M %p') if complaint.submitted_at else 'Recently'
        })
    return jsonify({'found': False})

def normalize_student_roll(roll_str: str) -> str:
    """
    Strictly normalizes roll numbers to the official 24252-CM-XXX format.
    Accepts case-insensitive variations like '24252-cm-001', '24252cm001', '24252 CM 001',
    and standardizes them strictly to '24252-CM-XXX'.
    """
    if not roll_str:
        return ''
    roll = roll_str.strip().upper()
    # Normalize spaces/dots/underscores
    roll = re.sub(r'[\s_.]+', '-', roll)
    # Match 24252CM001 (without hyphens)
    m = re.match(r'^24252CM(\d{3})$', roll)
    if m:
        return f"24252-CM-{m.group(1)}"
    # Match 24252-CM-001 or 24252-CM001 or 24252CM-001
    m2 = re.match(r'^24252-?CM-?(\d{3})$', roll)
    if m2:
        return f"24252-CM-{m2.group(1)}"
    return roll

# --- AUTHENTICATION ROUTES ---

@app.route('/register', methods=['GET', 'POST'])
@app.route('/register.html', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        raw_roll = (request.form.get('roll_number') or '').strip()
        name = (request.form.get('student_name') or '').strip()
        email = (request.form.get('email') or '').strip()
        password = request.form.get('password') or ''
        confirm_password = request.form.get('confirm_password') or ''

        if not raw_roll or not name or not email or not password:
            flash('All fields are required for registration.', 'danger')
            return render_template('register.html')

        clean_roll = normalize_student_roll(raw_roll)

        # 1. STRICT FORMAT ENFORCEMENT: Only 24252-CM-XXX format allowed!
        if not re.match(r'^24252-CM-\d{3}$', clean_roll):
            flash('Invalid Roll Number format. Registration is strictly restricted to roll numbers in the 24252-CM-XXX format (e.g. 24252-CM-001). No other formats are permitted.', 'danger')
            return render_template('register.html', error=True)

        # 2. Check if roll number has been permanently revoked/banned by Principal
        try:
            is_revoked = RevokedStudent.query.filter(
                (func.lower(RevokedStudent.roll_number) == func.lower(clean_roll)) |
                (func.lower(RevokedStudent.roll_number) == func.lower(raw_roll))
            ).first()
            if is_revoked:
                flash('This student roll number has been permanently revoked by administrative action. Registration denied.', 'danger')
                return render_template('register.html', error=True)
        except Exception:
            pass

        # 3. Check if already registered in RegisteredStudent
        existing_user = RegisteredStudent.query.filter(
            (func.lower(RegisteredStudent.roll_number) == func.lower(clean_roll)) |
            (func.lower(RegisteredStudent.roll_number) == func.lower(raw_roll))
        ).first()
        if existing_user:
            flash(f'An account with Roll Number {existing_user.roll_number} already exists. Please login.', 'warning')
            return redirect(url_for('login', role='student'))

        # 4. Check if email is already in use by another student
        existing_email = RegisteredStudent.query.filter(func.lower(RegisteredStudent.personal_email) == func.lower(email)).first()
        if existing_email:
            flash('This email address is already registered to another student account. Please use a different email or login.', 'warning')
            return render_template('register.html')

        # 5. Check password length & match
        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'danger')
            return render_template('register.html')

        if confirm_password and password != confirm_password:
            flash('Passwords do not match. Please re-enter.', 'danger')
            return render_template('register.html')

        # 6. Look up in CollegeStudent master database - strictly enrolled students only
        college_record = CollegeStudent.query.filter(
            (func.lower(CollegeStudent.roll_number) == func.lower(clean_roll)) |
            (func.lower(CollegeStudent.roll_number) == func.lower(raw_roll))
        ).first()

        if not college_record:
            flash(f'You are not a valid college student. Roll Number {clean_roll} is not found in the official college enrollment database.', 'danger')
            return render_template('register.html', error=True)

        # Update placeholder student name if needed
        if not college_record.student_name or college_record.student_name.lower().startswith('student '):
            college_record.student_name = name

        hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
        new_student = RegisteredStudent(
            roll_number=college_record.roll_number,
            student_name=name,
            personal_email=email,
            password_hash=hashed_pw
        )
        
        db.session.add(new_student)
        college_record.is_registered = True

        try:
            db.session.commit()
            flash(f'Registration Successful for {college_record.roll_number}! You can now login.', 'success')
            return redirect(url_for('login', role='student'))
        except Exception as e:
            db.session.rollback()
            print(f"Registration DB error: {e}")
            flash('An unexpected error occurred during registration. Please check your details and try again.', 'danger')
            return render_template('register.html')

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
@app.route('/login.html', methods=['GET', 'POST'])
def login():
    role = request.args.get('role', 'student')
    
    # During lockdown, student and standard admin logins are blocked
    if role != 'principal':
        settings = SystemSetting.query.first()
        if settings and settings.maintenance_mode:
            flash('⚠️ Institutional Maintenance Lockdown is currently active. Student and Administrative logins are suspended.', 'warning')
            return render_template('login.html')
            
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password')

        if role == 'student':
            clean_username = normalize_student_roll(username)
            user = RegisteredStudent.query.filter(
                (func.lower(RegisteredStudent.roll_number) == func.lower(username)) |
                (func.lower(RegisteredStudent.roll_number) == func.lower(clean_username))
            ).first()
        elif role == 'admin':
            user = Admin.query.filter((func.lower(Admin.username) == func.lower(username)) | (func.lower(Admin.email) == func.lower(username))).first()
        elif role == 'principal':
            user = Principal.query.filter((func.lower(Principal.username) == func.lower(username)) | (func.lower(Principal.email) == func.lower(username))).first()
        else:
            user = None

        if user and bcrypt.check_password_hash(user.password_hash, password):
            login_user(user)
            session['role'] = role
            
            if role == 'student':
                return redirect(url_for('student_dashboard'))
            elif role == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif role == 'principal':
                return redirect(url_for('principal_dashboard'))
        else:
            flash('Invalid credentials. Please verify your ID and password.', 'danger')

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    role = session.get('role', 'student')
    logout_user()
    session.clear()
    return redirect(url_for('login', role=role))

# --- STUDENT ROUTES ---



# --- STUDENT ROUTES ---

@app.route('/student/dashboard.html')
@login_required
def student_dashboard():
    if session.get('role') != 'student': 
        return redirect(url_for('login'))
    
    # Fetch all complaints for the logged-in student
    user_complaints = Complaint.query.filter_by(student_id=current_user.id).all()
    
    # Calculate live statistics
    total_count = len(user_complaints)
    # Grouping 'Submitted' and 'Under Review' into the Pending metric
    pending_count = sum(1 for c in user_complaints if c.status in ['Submitted', 'Under Review'])
    progress_count = sum(1 for c in user_complaints if c.status == 'In Progress')
    resolved_count = sum(1 for c in user_complaints if c.status == 'Resolved')
    closed_count = sum(1 for c in user_complaints if c.status == 'Closed')
    
    return render_template('student/dashboard.html', 
                           total=total_count, 
                           pending=pending_count, 
                           progress=progress_count, 
                           resolved=resolved_count, 
                           closed=closed_count)

@app.route('/student/submit_complaint.html', methods=['GET', 'POST'])
@login_required
def submit_complaint():
    if session.get('role') != 'student':
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        category = (request.form.get('category') or '').strip()
        priority = (request.form.get('priority') or 'Medium').strip()
        title = (request.form.get('title') or '').strip()
        description = (request.form.get('description') or '').strip()
        force_submit = request.form.get('force_submit')
        truth_declaration = request.form.get('truth_declaration')
        
        # Enforce statutory truth & disciplinary warning affirmation
        if not truth_declaration and not force_submit:
            flash('⚠️ Warning: You must confirm that your grievance is genuine and true before submitting.', 'danger')
            return render_template('student/submit_complaint.html', 
                                   saved_category=category, 
                                   saved_priority=priority, 
                                   saved_title=title, 
                                   saved_desc=description)
        
        # Canonicalize category
        canonical_category = normalize_category(category) or category
        
        # ==============================================================================
        # AUTOMATED PRE-SUBMISSION MODERATION & ANTI-ABUSE ENGINE
        # ==============================================================================
        moderation_result = evaluate_content(title, description, canonical_category, student_id=current_user.id)
        
        # 1. HARD REJECTION: Intercept, block from complaints table, log for disciplinary oversight
        if moderation_result['action'] == 'REJECT':
            try:
                log_entry = ModerationLog(
                    student_id=current_user.id,
                    student_roll=current_user.roll_number,
                    title=title,
                    description=description,
                    category=canonical_category,
                    action_taken='BLOCKED',
                    risk_score=moderation_result['overall_score'],
                    detected_flags=moderation_result['flags_csv'],
                    reasons="; ".join(moderation_result['all_reasons']),
                    ip_address=request.remote_addr,
                    created_at=datetime.now()
                )
                db.session.add(log_entry)
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                print(f"Error logging moderation block: {e}")
                
            reasons_summary = "; ".join(moderation_result['all_reasons'])
            flash(f"🚫 Submission Blocked by Institutional Anti-Abuse Engine: {reasons_summary}. {moderation_result['suggestions']}", 'danger')
            return render_template('student/submit_complaint.html', 
                                   saved_category=category, 
                                   saved_priority=priority, 
                                   saved_title=title, 
                                   saved_desc=description,
                                   moderation_blocked=True,
                                   moderation_reasons=moderation_result['all_reasons'])
                                   
        # 2. BORDERLINE FLAGGING: Accept into Quarantined status, shielded from Admin dashboard
        is_quarantined = (moderation_result['action'] == 'FLAG')
        
        # Duplicate Complaint Detection (Skips if student explicitly confirmed to lodge separate ticket or quarantined)
        if not force_submit and not is_quarantined:
            similar_complaint = find_similar_complaint(canonical_category, title, description)
            
            if similar_complaint:
                return render_template('student/duplicate_warning.html', 
                                       existing=similar_complaint, 
                                       new_title=title, 
                                       new_desc=description, 
                                       new_priority=priority, 
                                       new_category=canonical_category)
        
        # Save New Grievance Record
        new_ref_id = generate_complaint_id()
        complaint_status = 'Quarantined' if is_quarantined else 'Submitted'
        mod_status = 'Flagged' if is_quarantined else 'Approved'
        
        new_complaint = Complaint(
            complaint_ref_id=new_ref_id,
            student_id=current_user.id,
            category=canonical_category,
            priority=priority,
            title=title,
            description=description,
            status=complaint_status,
            moderation_status=mod_status,
            moderation_score=moderation_result['overall_score'],
            moderation_flags=moderation_result['flags_csv'],
            submitted_at=datetime.now()
        )
        
        try:
            db.session.add(new_complaint)
            
            # If flagged, also record in ModerationLog
            if is_quarantined:
                log_entry = ModerationLog(
                    student_id=current_user.id,
                    student_roll=current_user.roll_number,
                    title=title,
                    description=description,
                    category=canonical_category,
                    action_taken='FLAGGED',
                    risk_score=moderation_result['overall_score'],
                    detected_flags=moderation_result['flags_csv'],
                    reasons="; ".join(moderation_result['all_reasons']),
                    ip_address=request.remote_addr,
                    created_at=datetime.now()
                )
                db.session.add(log_entry)
                
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Error saving complaint to database: {e}")
            flash('⚠️ An unexpected error occurred while saving your grievance. Please try again.', 'danger')
            return render_template('student/submit_complaint.html', 
                                   saved_category=category, 
                                   saved_priority=priority, 
                                   saved_title=title, 
                                   saved_desc=description)
        
        # Trigger Email Notifications (Only for approved/clean tickets)
        if not is_quarantined:
            send_admin_notification(new_complaint)
            send_student_confirmation(new_complaint, current_user)
            flash(f'Grievance Submitted Successfully! Your Official Tracking ID is {new_ref_id}', 'success')
        else:
            flash(f'Grievance Lodged! Ticket {new_ref_id} has been placed under Institutional Quality & Content Review before administrative assignment.', 'info')
            
        return redirect(url_for('student_my_complaints'))
        
    return render_template('student/submit_complaint.html')

@app.route('/api/check_moderation', methods=['POST'])
@login_required
def api_check_moderation():
    """
    Real-time asynchronous content moderation check as student types.
    Analyzes title and description for gibberish, profanity, and spam.
    Returns composite score, action tier, detected reasons, and remedial guidance.
    """
    data = request.get_json() or {}
    title = (data.get('title') or '').strip()
    description = (data.get('description') or '').strip()
    category = (data.get('category') or '').strip()
    
    if not title and not description:
        return jsonify({
            'action': 'APPROVE',
            'overall_score': 0,
            'is_blocked': False,
            'is_flagged': False,
            'is_clean': True,
            'summary_status': 'Clean',
            'primary_reason': 'No content entered yet.',
            'all_reasons': [],
            'suggestions': 'Enter clear, factual grievance details.'
        })
        
    result = evaluate_content(title, description, category, student_id=current_user.id if current_user.is_authenticated else None)
    return jsonify(result)

@app.route('/api/check_duplicate', methods=['POST'])
@login_required
def api_check_duplicate():
    """
    Live asynchronous check for similar complaints as the student fills the submission form.
    Returns matched ticket details and whether the current student has already upvoted it.
    """
    data = request.get_json() or {}
    category = data.get('category', '').strip()
    title = data.get('title', '').strip()
    description = data.get('description', '').strip()
    
    if not title or len(title) < 3:
        return jsonify({'found': False})
        
    canonical_category = normalize_category(category) or category
    similar = find_similar_complaint(canonical_category, title, description)
    
    if similar:
        # Check if the active student has already supported this ticket
        already_supported = False
        if current_user.is_authenticated:
            already_supported = ComplaintSupport.query.filter_by(
                complaint_id=similar.id, 
                student_id=current_user.id
            ).first() is not None
            
        return jsonify({
            'found': True,
            'id': similar.id,
            'ref_id': similar.complaint_ref_id,
            'title': similar.title,
            'description': (similar.description[:160] + '...') if similar.description and len(similar.description) > 160 else (similar.description or ''),
            'category': similar.category,
            'status': similar.status,
            'support_count': similar.support_count or 0,
            'submitted_at': similar.submitted_at.strftime('%d %b %Y') if similar.submitted_at else 'Recent',
            'already_supported': already_supported
        })
    return jsonify({'found': False})

@app.route('/api/category_complaints/<category>')
@login_required
def api_category_complaints(category):
    """
    Returns all active/open complaints in the specified category.
    Allows students to immediately see peer complaints when choosing a category.
    """
    canonical_cat = normalize_category(category) or category
    active_complaints = Complaint.query.filter(
        Complaint.category == canonical_cat,
        Complaint.status.in_(['Submitted', 'Under Review', 'In Progress'])
    ).order_by(Complaint.submitted_at.desc()).all()
    
    results = []
    for c in active_complaints:
        already_supported = False
        if current_user.is_authenticated:
            already_supported = ComplaintSupport.query.filter_by(
                complaint_id=c.id, 
                student_id=current_user.id
            ).first() is not None
            
        results.append({
            'id': c.id,
            'ref_id': c.complaint_ref_id,
            'title': c.title,
            'description': (c.description[:140] + '...') if c.description and len(c.description) > 140 else (c.description or ''),
            'status': c.status,
            'priority': c.priority,
            'support_count': c.support_count or 0,
            'submitted_at': c.submitted_at.strftime('%d %b %Y') if c.submitted_at else 'Recent',
            'already_supported': already_supported
        })
        
    return jsonify({
        'category': canonical_cat,
        'count': len(results),
        'complaints': results
    })

@app.route('/student/support_complaint/<int:complaint_id>', methods=['POST'])
@login_required
def support_complaint(complaint_id):
    if session.get('role') != 'student':
        if request.is_json:
            return jsonify({'success': False, 'message': 'Unauthorized access'}), 403
        return redirect(url_for('login'))
        
    complaint = db.session.get(Complaint, complaint_id)
    if not complaint:
        if request.is_json:
            return jsonify({'success': False, 'message': 'Grievance record not found'}), 404
        flash('Grievance record not found.', 'danger')
        return redirect(url_for('student_my_complaints'))

    existing_support = ComplaintSupport.query.filter_by(complaint_id=complaint_id, student_id=current_user.id).first()
    
    if not existing_support:
        new_support = ComplaintSupport(complaint_id=complaint_id, student_id=current_user.id)
        db.session.add(new_support)
        complaint.support_count = (complaint.support_count or 0) + 1
        db.session.commit()
        
        msg = f'Successfully supported grievance [{complaint.complaint_ref_id}]! Your vote has been pooled into this issue.'
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': True,
                'message': msg,
                'support_count': complaint.support_count,
                'ref_id': complaint.complaint_ref_id,
                'redirect_url': url_for('student_my_complaints')
            })
        flash(msg, 'success')
    else:
        msg = f'You have already supported grievance [{complaint.complaint_ref_id}].'
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': False,
                'already_supported': True,
                'message': msg,
                'support_count': complaint.support_count,
                'ref_id': complaint.complaint_ref_id,
                'redirect_url': url_for('student_my_complaints')
            })
        flash(msg, 'warning')
        
    return redirect(url_for('student_my_complaints'))

@app.route('/student/my_complaints.html')
@login_required
def student_my_complaints():
    if session.get('role') != 'student':
        return redirect(url_for('login'))
        
    my_complaints = Complaint.query.filter_by(student_id=current_user.id).order_by(Complaint.submitted_at.desc()).all()
    return render_template('student/my_complaints.html', complaints=my_complaints)

@app.route('/student/timeline.html')
@login_required
def student_timeline():
    if session.get('role') != 'student':
        return redirect(url_for('login'))
    
    # Get the ID from the URL (e.g., ?id=CGMS-2026-0001)
    ref_id = request.args.get('id')
    complaint = None
    replies = []
    
    if ref_id:
        # Fetch the specific complaint from the database securely
        complaint = Complaint.query.filter_by(complaint_ref_id=ref_id, student_id=current_user.id).first()
        if complaint:
            replies = ComplaintReply.query.filter_by(complaint_id=complaint.id).order_by(ComplaintReply.replied_at.desc()).all()
        
    return render_template('student/timeline.html', complaint=complaint, replies=replies)

@app.route('/student/profile.html')
@login_required
def student_profile():
    if session.get('role') != 'student':
        return redirect(url_for('login'))
    return render_template('student/profile.html')

@app.route('/student/profile/update_email', methods=['POST'])
@login_required
def student_update_email():
    """
    Allows logged-in students to update their personal notifications email.
    Requires current password verification for security.
    """
    if session.get('role') != 'student':
        return redirect(url_for('login'))
        
    new_email = (request.form.get('new_email') or '').strip().lower()
    current_password = request.form.get('current_password') or ''
    
    if not new_email or '@' not in new_email or '.' not in new_email:
        flash('Please provide a valid email address.', 'danger')
        return redirect(url_for('student_profile'))
        
    if not bcrypt.check_password_hash(current_user.password_hash, current_password):
        flash('Verification failed: Incorrect current password. Email was not changed.', 'danger')
        return redirect(url_for('student_profile'))
        
    if new_email == (current_user.personal_email or '').lower():
        flash('The entered email address is identical to your current email.', 'info')
        return redirect(url_for('student_profile'))
        
    # Check uniqueness across registered students
    existing = RegisteredStudent.query.filter(
        func.lower(RegisteredStudent.personal_email) == new_email,
        RegisteredStudent.id != current_user.id
    ).first()
    if existing:
        flash('This email address is already registered to another student account.', 'danger')
        return redirect(url_for('student_profile'))
        
    current_user.personal_email = new_email
    try:
        db.session.commit()
        flash(f'Your notification email has been successfully updated to {new_email}!', 'success')
    except Exception as e:
        db.session.rollback()
        print(f"Error updating student email: {e}")
        flash('An error occurred while updating your email. Please try again.', 'danger')
        
    return redirect(url_for('student_profile'))

@app.route('/student/profile/change_password', methods=['POST'])
@login_required
def student_change_password():
    """
    Allows logged-in students to change their account password.
    Requires current password verification and confirmation match.
    """
    if session.get('role') != 'student':
        return redirect(url_for('login'))
        
    current_password = request.form.get('current_password') or ''
    new_password = request.form.get('new_password') or ''
    confirm_password = request.form.get('confirm_password') or ''
    
    if not bcrypt.check_password_hash(current_user.password_hash, current_password):
        flash('Verification failed: Incorrect current password. Password was not changed.', 'danger')
        return redirect(url_for('student_profile'))
        
    if len(new_password) < 6:
        flash('New password must be at least 6 characters long.', 'danger')
        return redirect(url_for('student_profile'))
        
    if new_password != confirm_password:
        flash('New password and confirmation password do not match.', 'danger')
        return redirect(url_for('student_profile'))
        
    if bcrypt.check_password_hash(current_user.password_hash, new_password):
        flash('New password cannot be the same as your current password.', 'warning')
        return redirect(url_for('student_profile'))
        
    new_hash = bcrypt.generate_password_hash(new_password).decode('utf-8')
    current_user.password_hash = new_hash
    try:
        db.session.commit()
        flash('Your password has been changed successfully! Please use your new password for future logins.', 'success')
    except Exception as e:
        db.session.rollback()
        print(f"Error updating student password: {e}")
        flash('An error occurred while updating your password. Please try again.', 'danger')
        
    return redirect(url_for('student_profile'))

@app.route('/student/announcements.html')
@login_required
def student_announcements():
    if session.get('role') != 'student':
        return redirect(url_for('login'))
        
    # Fetch all announcements from the database, newest first
    live_announcements = Announcement.query.order_by(Announcement.created_at.desc()).all()
    count = len(live_announcements)
    
    return render_template('student/announcements.html', announcements=live_announcements, count=count)
# --- ADMIN & PRINCIPAL ROUTES ---

# --- ADMIN ROUTES ---

@app.route('/admin/dashboard.html')
@login_required
def admin_dashboard():
    if session.get('role') != 'admin': 
        return redirect(url_for('login'))
        
    # Calculate live system-wide statistics (excluding quarantined / flagged abuse)
    total_complaints = Complaint.query.filter(Complaint.moderation_status != 'Flagged').count()
    high_priority = Complaint.query.filter(Complaint.priority == 'High', Complaint.moderation_status != 'Flagged').count()
    pending_complaints = Complaint.query.filter(
        Complaint.status.in_(['Submitted', 'Under Review']),
        Complaint.moderation_status != 'Flagged'
    ).count()
    quarantined_count = Complaint.query.filter(Complaint.moderation_status == 'Flagged').count()
    blocked_count = ModerationLog.query.filter_by(action_taken='BLOCKED').count()
    
    # Count complaints submitted exactly today (clean)
    today = datetime.now().date()
    today_complaints = Complaint.query.filter(
        func.date(Complaint.submitted_at) == today,
        Complaint.moderation_status != 'Flagged'
    ).count()
    
    # Fetch the 5 most recent unresolved complaints for the preview table (clean)
    recent_complaints = Complaint.query.filter(
        Complaint.status.in_(['Submitted', 'Under Review', 'In Progress']),
        Complaint.moderation_status != 'Flagged'
    ).order_by(Complaint.submitted_at.desc()).limit(5).all()
    
    return render_template('admin/dashboard.html', 
                           total=total_complaints,
                           high=high_priority,
                           pending=pending_complaints,
                           today_count=today_complaints,
                           recent_complaints=recent_complaints,
                           quarantined_count=quarantined_count,
                           blocked_count=blocked_count)

@app.route('/admin/manage_complaints.html')
@login_required
def admin_manage_complaints():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    # Filter parameter: 'active' (default), 'quarantined', or 'all'
    view_filter = request.args.get('filter', 'active')
    if view_filter == 'quarantined':
        all_complaints = Complaint.query.filter(Complaint.moderation_status == 'Flagged').order_by(Complaint.submitted_at.desc()).all()
    elif view_filter == 'all':
        all_complaints = Complaint.query.order_by(Complaint.submitted_at.desc()).all()
    else:
        # Default: only verified active complaints (quarantined kept off standard dashboard)
        all_complaints = Complaint.query.filter(Complaint.moderation_status != 'Flagged').order_by(Complaint.submitted_at.desc()).all()
        
    quarantined_count = Complaint.query.filter(Complaint.moderation_status == 'Flagged').count()
    return render_template('admin/manage_complaints.html', 
                           complaints=all_complaints, 
                           active_filter=view_filter, 
                           quarantined_count=quarantined_count)

@app.route('/admin/complaint/<int:id>/moderation_action', methods=['POST'])
@login_required
def admin_moderation_action(id):
    """
    Allows authorized administrators to release a quarantined complaint to active
    status or dismiss it as abusive/invalid.
    """
    if session.get('role') not in ['admin', 'principal']:
        return redirect(url_for('login'))
        
    action = request.form.get('action') # 'release' or 'dismiss'
    complaint = db.session.get(Complaint, id)
    if not complaint:
        flash('Complaint not found.', 'danger')
        return redirect(url_for('admin_manage_complaints'))
        
    if action == 'release':
        complaint.moderation_status = 'Approved'
        complaint.status = 'Submitted'
        db.session.commit()
        flash(f'Ticket {complaint.complaint_ref_id} has been verified and released to active remediation queue.', 'success')
    elif action == 'dismiss':
        complaint.moderation_status = 'Rejected'
        complaint.status = 'Closed'
        db.session.commit()
        flash(f'Ticket {complaint.complaint_ref_id} has been dismissed and closed.', 'warning')
        
    return redirect(url_for('admin_manage_complaints', filter='quarantined'))

@app.route('/admin/view_complaint.html', methods=['GET', 'POST'])
@login_required
def admin_view_complaint():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
        
    # Fetch the specific ticket based on the URL ID securely
    ref_id = request.args.get('id')
    complaint = Complaint.query.filter_by(complaint_ref_id=ref_id).first()
    
    if not complaint:
        flash('Complaint not found.', 'danger')
        return redirect(url_for('admin_manage_complaints'))
        
    # Handle the Admin submitting a status update and reply
    if request.method == 'POST':
        new_status = request.form.get('status')
        reply_text = request.form.get('reply_text')
        
        # 1. Update the master status
        complaint.status = new_status
        
        # 2. Record the Admin's reply in the database
        new_reply = ComplaintReply(
            complaint_id=complaint.id,
            reply_text=reply_text,
            replied_by_role='Admin',
            replied_by_id=current_user.id,
            replied_at=datetime.now()
        )
        db.session.add(new_reply)
        db.session.commit()
        
        # 3. Fetch the student's details and trigger the automated email
        student = db.session.get(RegisteredStudent, complaint.student_id)
        if student:
            send_student_notification(complaint, student, new_status)
        
        flash('Ticket updated and email notification sent to student successfully.', 'success')
        return redirect(url_for('admin_view_complaint', id=ref_id))
        
    # --- THESE ARE THE LINES THAT WERE LIKELY MISSING ---
    # Fetch the live interaction history for this specific ticket
    replies = ComplaintReply.query.filter_by(complaint_id=complaint.id).order_by(ComplaintReply.replied_at.asc()).all()
    return render_template('admin/view_complaint.html', complaint=complaint, replies=replies)
def get_filtered_complaints():
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    category = request.args.get('category', 'All')
    priority = request.args.get('priority', 'All')
    status = request.args.get('status', 'All')

    query = db.session.query(Complaint, RegisteredStudent)\
        .outerjoin(RegisteredStudent, Complaint.student_id == RegisteredStudent.id)

    if start_date_str:
        try:
            s_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            query = query.filter(Complaint.submitted_at >= s_date)
        except ValueError:
            pass

    if end_date_str:
        try:
            e_date = datetime.strptime(end_date_str, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(Complaint.submitted_at < e_date)
        except ValueError:
            pass

    if category and category != 'All':
        query = query.filter(Complaint.category == category)
    if priority and priority != 'All':
        query = query.filter(Complaint.priority == priority)
    if status and status != 'All':
        query = query.filter(Complaint.status == status)

    records = query.order_by(Complaint.submitted_at.desc()).all()
    return records, {
        'start_date': start_date_str or 'Earliest Logged',
        'end_date': end_date_str or datetime.now().strftime('%Y-%m-%d'),
        'category': category,
        'priority': priority,
        'status': status
    }

@app.route('/admin/reports.html')
@login_required
def admin_reports():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
        
    current_date = datetime.now()
    total_records = Complaint.query.count()
    start_date = current_date - timedelta(days=180)
    
    return render_template('admin/reports.html', current_date=current_date, start_date=start_date, total_records=total_records)

@app.route('/admin/export/pdf')
@login_required
def admin_export_pdf():
    if session.get('role') not in ['admin', 'principal']:
        return redirect(url_for('login'))

    records, filters = get_filtered_complaints()

    if not HAS_REPORTLAB:
        flash('PDF generation module is initializing. You may export as Structured CSV/Excel in the meantime.', 'warning')
        return redirect(url_for('admin_reports'))

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=28,
        rightMargin=28,
        topMargin=26,
        bottomMargin=26
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=18,
        textColor=colors.HexColor('#0f2b48')
    )
    sub_style = ParagraphStyle(
        'DocSub',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#475569')
    )
    cell_style = ParagraphStyle(
        'CellText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor('#1e293b')
    )
    header_cell_style = ParagraphStyle(
        'HeaderCell',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.white
    )
    summary_style = ParagraphStyle(
        'SummaryCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        textColor=colors.white
    )

    elements = []

    # Title & Subtitle
    elements.append(Paragraph("COLLEGE GRIEVANCE REDRESSAL & FACILITY MANAGEMENT SYSTEM", title_style))
    elements.append(Paragraph("Autonomous Academic Quality Assurance Cell (IQAC) - Official Grievance Audit & Compliance Dossier", sub_style))
    elements.append(Spacer(1, 8))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#c59b27'), spaceAfter=8))

    # Metadata Table
    gen_time = datetime.now().strftime('%d %b %Y, %I:%M %p')
    meta_data = [
        [
            Paragraph(f"<b>Reporting Window:</b> {filters['start_date']} to {filters['end_date']}", cell_style),
            Paragraph(f"<b>Category:</b> {filters['category']}", cell_style),
            Paragraph(f"<b>Priority:</b> {filters['priority']}", cell_style),
            Paragraph(f"<b>Status:</b> {filters['status']}", cell_style),
            Paragraph(f"<b>Generated:</b> {gen_time}", cell_style)
        ]
    ]
    meta_table = Table(meta_data, colWidths=[185, 150, 130, 130, 190])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 10))

    # Metrics Summary
    total_count = len(records)
    resolved_count = sum(1 for c, _ in records if c.status in ['Resolved', 'Closed'])
    in_progress_count = sum(1 for c, _ in records if c.status in ['In Progress', 'Under Review'])
    submitted_count = sum(1 for c, _ in records if c.status == 'Submitted')
    escalated_count = sum(1 for c, _ in records if c.is_escalated)
    res_rate = int((resolved_count / total_count * 100)) if total_count > 0 else 0

    summary_data = [
        [
            Paragraph(f"<b>TOTAL LOGGED:</b> {total_count}", summary_style),
            Paragraph(f"<b>RESOLVED / CLOSED:</b> {resolved_count} ({res_rate}%)", summary_style),
            Paragraph(f"<b>IN PROGRESS / REVIEW:</b> {in_progress_count}", summary_style),
            Paragraph(f"<b>NEW / SUBMITTED:</b> {submitted_count}", summary_style),
            Paragraph(f"<b>ESCALATED BREACHES:</b> {escalated_count}", summary_style)
        ]
    ]
    summary_table = Table(summary_data, colWidths=[150, 175, 175, 150, 135])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#0f2b48')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#0f2b48')),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 10))

    # Records Table
    records_data = [
        [
            Paragraph("Ref ID", header_cell_style),
            Paragraph("Lodged Date", header_cell_style),
            Paragraph("Complainant Roll / Dept", header_cell_style),
            Paragraph("Category", header_cell_style),
            Paragraph("Priority", header_cell_style),
            Paragraph("Status", header_cell_style),
            Paragraph("Subject & Incident Details", header_cell_style),
        ]
    ]

    for c, s in records:
        roll = s.roll_number if s else 'N/A'
        dept = 'CSE' if ('-CM-' in roll or '-CS-' in roll) else ('ECE' if '-EC-' in roll else 'General')
        date_str = c.submitted_at.strftime('%d %b %Y') if c.submitted_at else 'N/A'
        
        p_color = '#dc2626' if c.priority == 'High' else ('#d97706' if c.priority == 'Medium' else '#16a34a')
        p_html = f"<font color='{p_color}'><b>{c.priority}</b></font>"
        
        s_color = '#16a34a' if c.status in ['Resolved', 'Closed'] else ('#2563eb' if c.status == 'In Progress' else '#475569')
        s_html = f"<font color='{s_color}'><b>{c.status}</b></font>"
        if c.is_escalated:
            s_html += "<br/><font color='#dc2626' size='6'>[ESCALATED]</font>"
            
        desc_snippet = (c.description[:180] + '...') if (c.description and len(c.description) > 180) else (c.description or '')
        title_esc = (c.title or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        desc_esc = (desc_snippet or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        subject_content = f"<b>{title_esc}</b><br/><font color='#64748b'>{desc_esc}</font>"

        records_data.append([
            Paragraph(c.complaint_ref_id, cell_style),
            Paragraph(date_str, cell_style),
            Paragraph(f"<b>{roll}</b><br/><font color='#64748b'>{dept}</font>", cell_style),
            Paragraph(c.category or '', cell_style),
            Paragraph(p_html, cell_style),
            Paragraph(s_html, cell_style),
            Paragraph(subject_content, cell_style),
        ])

    if len(records) == 0:
        records_data.append([
            Paragraph("No grievance records matched the specified reporting criteria.", cell_style),
            Paragraph("", cell_style),
            Paragraph("", cell_style),
            Paragraph("", cell_style),
            Paragraph("", cell_style),
            Paragraph("", cell_style),
            Paragraph("", cell_style),
        ])

    records_table = Table(records_data, colWidths=[90, 70, 110, 85, 60, 80, 290])
    records_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0f2b48')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f8fafc')]),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    elements.append(records_table)
    elements.append(Spacer(1, 15))

    # Attestation Signatures
    sig_data = [
        [
            Paragraph("<b>Compiled & Verified By:</b><br/><br/><br/>____________________________________<br/><b>Administrative Officer</b><br/>Grievance Redressal Cell", cell_style),
            Paragraph("<b>Attested & Certified By:</b><br/><br/><br/>____________________________________<br/><b>Principal & Head of Institution</b><br/>Supreme Executive Authority", cell_style)
        ]
    ]
    sig_table = Table(sig_data, colWidths=[392, 393])
    sig_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 8),
    ]))
    elements.append(KeepTogether([sig_table]))

    doc.build(elements)
    buffer.seek(0)
    filename = f"Grievance_Quality_Dossier_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    return send_file(buffer, mimetype='application/pdf', as_attachment=True, download_name=filename)

@app.route('/admin/export/excel')
@login_required
def admin_export_excel():
    if session.get('role') not in ['admin', 'principal']:
        return redirect(url_for('login'))

    records, filters = get_filtered_complaints()

    if not HAS_XLSXWRITER:
        csv_buf = io.StringIO()
        writer = csv.writer(csv_buf)
        writer.writerow([
            'Complaint Ref ID', 'Lodged Date', 'Roll Number', 'Complainant Name',
            'Department', 'Category', 'Subject / Title', 'Detailed Incident Description',
            'Priority Severity', 'Workflow Status', 'SLA Escalation Flag'
        ])
        for c, s in records:
            roll = s.roll_number if s else 'N/A'
            name = s.student_name if s else 'N/A'
            dept = 'CSE' if ('-CM-' in roll or '-CS-' in roll) else ('ECE' if '-EC-' in roll else 'General')
            date_str = c.submitted_at.strftime('%Y-%m-%d %H:%M') if c.submitted_at else 'N/A'
            esc_str = 'YES - ESCALATED' if c.is_escalated else 'No'
            writer.writerow([
                c.complaint_ref_id, date_str, roll, name, dept,
                c.category or '', c.title or '', c.description or '',
                c.priority, c.status, esc_str
            ])
        mem = io.BytesIO()
        mem.write(csv_buf.getvalue().encode('utf-8-sig'))
        mem.seek(0)
        filename = f"Grievance_Register_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        return send_file(mem, mimetype='text/csv', as_attachment=True, download_name=filename)

    buffer = io.BytesIO()
    workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
    worksheet = workbook.add_worksheet('Grievance Register')

    title_fmt = workbook.add_format({'bold': True, 'font_size': 14, 'font_color': '#0f2b48', 'valign': 'vcenter'})
    sub_fmt = workbook.add_format({'font_size': 9, 'font_color': '#64748b', 'valign': 'vcenter'})
    hdr_fmt = workbook.add_format({
        'bold': True, 'font_size': 10, 'font_color': '#ffffff', 'bg_color': '#0f2b48',
        'border': 1, 'border_color': '#cbd5e1', 'align': 'center', 'valign': 'vcenter'
    })
    cell_fmt = workbook.add_format({'font_size': 9, 'border': 1, 'border_color': '#e2e8f0', 'valign': 'top'})
    cell_alt_fmt = workbook.add_format({'font_size': 9, 'border': 1, 'border_color': '#e2e8f0', 'bg_color': '#f8fafc', 'valign': 'top'})
    badge_high = workbook.add_format({'font_size': 9, 'bold': True, 'font_color': '#b91c1c', 'bg_color': '#fee2e2', 'border': 1, 'border_color': '#fca5a5', 'align': 'center'})
    badge_med = workbook.add_format({'font_size': 9, 'bold': True, 'font_color': '#b45309', 'bg_color': '#fef3c7', 'border': 1, 'border_color': '#fde68a', 'align': 'center'})
    badge_low = workbook.add_format({'font_size': 9, 'bold': True, 'font_color': '#15803d', 'bg_color': '#dcfce7', 'border': 1, 'border_color': '#86efac', 'align': 'center'})
    badge_resolved = workbook.add_format({'font_size': 9, 'bold': True, 'font_color': '#15803d', 'bg_color': '#dcfce7', 'border': 1, 'border_color': '#86efac', 'align': 'center'})
    badge_escalated = workbook.add_format({'font_size': 9, 'bold': True, 'font_color': '#991b1b', 'bg_color': '#fecaca', 'border': 1, 'border_color': '#f87171', 'align': 'center'})

    worksheet.write('A1', 'COLLEGE GRIEVANCE REDRESSAL & FACILITY MANAGEMENT SYSTEM', title_fmt)
    worksheet.write('A2', f'Institutional Compliance Register | Window: {filters["start_date"]} to {filters["end_date"]} | Exported: {datetime.now().strftime("%d %b %Y, %I:%M %p")}', sub_fmt)

    headers = [
        'Complaint Ref ID', 'Lodged Date', 'Roll Number', 'Complainant Name',
        'Department', 'Category', 'Subject / Title', 'Detailed Incident Description',
        'Priority Severity', 'Workflow Status', 'SLA Escalation Flag'
    ]

    worksheet.set_row(3, 26)
    for col_idx, h in enumerate(headers):
        worksheet.write(3, col_idx, h, hdr_fmt)

    for row_idx, (c, s) in enumerate(records, start=4):
        fmt = cell_fmt if row_idx % 2 == 0 else cell_alt_fmt
        roll = s.roll_number if s else 'N/A'
        name = s.student_name if s else 'N/A'
        dept = 'CSE' if ('-CM-' in roll or '-CS-' in roll) else ('ECE' if '-EC-' in roll else 'General')
        date_str = c.submitted_at.strftime('%Y-%m-%d %H:%M') if c.submitted_at else 'N/A'
        esc_str = 'YES - ESCALATED' if c.is_escalated else 'No'

        worksheet.write(row_idx, 0, c.complaint_ref_id, fmt)
        worksheet.write(row_idx, 1, date_str, fmt)
        worksheet.write(row_idx, 2, roll, fmt)
        worksheet.write(row_idx, 3, name, fmt)
        worksheet.write(row_idx, 4, dept, fmt)
        worksheet.write(row_idx, 5, c.category or '', fmt)
        worksheet.write(row_idx, 6, c.title or '', fmt)
        worksheet.write(row_idx, 7, c.description or '', fmt)
        
        if c.priority == 'High':
            worksheet.write(row_idx, 8, c.priority, badge_high)
        elif c.priority == 'Medium':
            worksheet.write(row_idx, 8, c.priority, badge_med)
        else:
            worksheet.write(row_idx, 8, c.priority, badge_low)

        if c.status in ['Resolved', 'Closed']:
            worksheet.write(row_idx, 9, c.status, badge_resolved)
        else:
            worksheet.write(row_idx, 9, c.status, fmt)

        if c.is_escalated:
            worksheet.write(row_idx, 10, esc_str, badge_escalated)
        else:
            worksheet.write(row_idx, 10, esc_str, fmt)

    col_widths = [18, 16, 16, 22, 14, 16, 28, 45, 14, 16, 18]
    for idx, width in enumerate(col_widths):
        worksheet.set_column(idx, idx, width)

    workbook.close()
    buffer.seek(0)
    filename = f"Grievance_Register_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return send_file(buffer, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name=filename)

@app.route('/admin/notices.html', methods=['GET', 'POST'])
@login_required
def admin_notices():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        
        if not title or not content:
            flash('Please enter both an official title and bulletin message.', 'danger')
        else:
            new_notice = Announcement(
                title=title,
                content=content,
                posted_by_role='Admin',
                posted_by_id=current_user.id,
                created_at=datetime.now()
            )
            db.session.add(new_notice)
            db.session.commit()
            flash('Official Campus Notice published to student bulletin board successfully.', 'success')
        return redirect(url_for('admin_notices'))
        
    announcements = Announcement.query.order_by(Announcement.created_at.desc()).all()
    return render_template('admin/notices.html', announcements=announcements)

@app.route('/admin/notices/delete/<int:id>', methods=['POST'])
@login_required
def admin_delete_notice(id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
        
    notice = db.session.get(Announcement, id)
    if notice:
        db.session.delete(notice)
        db.session.commit()
        flash('Campus Notice has been retracted and removed from the student bulletin board.', 'warning')
    else:
        flash('Notice not found.', 'danger')
    return redirect(url_for('admin_notices'))
# --- PRINCIPAL ROUTES ---

from datetime import timedelta

def update_escalations():
    """
    Scans the database and flags tickets as escalated if they breach the time limit.
    Sends notification email to Super Admin (Principal) when a ticket escalates.
    """
    settings = SystemSetting.query.first()
    if not settings:
        settings = SystemSetting()
        db.session.add(settings)
        db.session.commit()
        
    unresolved = Complaint.query.filter(Complaint.status.in_(['Submitted', 'Under Review', 'In Progress'])).all()
    for c in unresolved:
        days_passed = (datetime.now() - c.submitted_at).days
        limit = settings.high_escalation_days if c.priority == 'High' else settings.standard_escalation_days
        
        if days_passed >= limit:
            c.is_escalated = True
            if not getattr(c, 'escalation_notified', False):
                student = db.session.get(RegisteredStudent, c.student_id)
                send_principal_escalation_notification(c, student)
                c.escalation_notified = True
    db.session.commit()

@app.before_request
def check_maintenance_lockdown():
    """
    Enforces the Institutional Maintenance Lockdown Flag.
    When enabled by the Principal, all public and student routes are intercepted with an
    official 503 Maintenance screen. The Principal retains full administrative console access.
    """
    if request.path.startswith('/static'):
        return None

    try:
        settings = SystemSetting.query.first()
        if settings and settings.maintenance_mode:
            # Principal users have supreme administrative clearance to access all endpoints
            if session.get('role') == 'principal':
                return None

            # Allow login & logout endpoints so the Principal can sign in to deactivate lockdown
            allowed_endpoints = ['login', 'logout']
            if request.endpoint in allowed_endpoints:
                return None

            # Intercept all student, admin, and public portal requests
            return render_template('maintenance.html', settings=settings), 503
    except Exception as e:
        print(f"Maintenance check error: {e}")

@app.before_request
def check_sla_escalations():
    """
    Automatically checks for SLA breaches and escalations on web navigation.
    """
    if request.method == 'GET' and not request.path.startswith('/static'):
        try:
            update_escalations()
        except Exception as e:
            print(f"Escalation check notice: {e}")

@app.route('/principal/dashboard.html')
@login_required
def principal_dashboard():
    if session.get('role') != 'principal': 
        return redirect(url_for('login'))
        
    update_escalations()
    
    # Calculate Live Analytics
    escalated_count = Complaint.query.filter(Complaint.is_escalated == True, Complaint.status.in_(['Submitted', 'Under Review', 'In Progress'])).count()
    student_count = RegisteredStudent.query.count()
    admin_count = Admin.query.count()
    
    total_complaints = Complaint.query.count()
    resolved_complaints = Complaint.query.filter(Complaint.status.in_(['Resolved', 'Closed'])).count()
    resolution_rate = int((resolved_complaints / total_complaints * 100)) if total_complaints > 0 else 0

    # Anti-Abuse & Moderation Metrics
    blocked_abuse_count = ModerationLog.query.filter_by(action_taken='BLOCKED').count()
    quarantined_count = Complaint.query.filter(Complaint.moderation_status == 'Flagged').count()
    recent_moderation_logs = ModerationLog.query.order_by(ModerationLog.created_at.desc()).limit(6).all()
    
    escalated_tickets = db.session.query(Complaint, RegisteredStudent)\
        .join(RegisteredStudent, Complaint.student_id == RegisteredStudent.id)\
        .filter(Complaint.is_escalated == True, Complaint.status.in_(['Submitted', 'Under Review', 'In Progress']))\
        .order_by(Complaint.submitted_at.asc()).limit(5).all()
    
    return render_template('principal/dashboard.html', 
                           escalated_count=escalated_count,
                           student_count=student_count,
                           admin_count=admin_count,
                           resolution_rate=resolution_rate,
                           escalated_tickets=escalated_tickets,
                           blocked_abuse_count=blocked_abuse_count,
                           quarantined_count=quarantined_count,
                           recent_moderation_logs=recent_moderation_logs)

@app.route('/principal/escalations.html')
@login_required
def principal_escalations():
    if session.get('role') != 'principal': 
        return redirect(url_for('login'))
        
    update_escalations()
    
    escalated_tickets = db.session.query(Complaint, RegisteredStudent)\
        .join(RegisteredStudent, Complaint.student_id == RegisteredStudent.id)\
        .filter(Complaint.is_escalated == True, Complaint.status.in_(['Submitted', 'Under Review', 'In Progress']))\
        .order_by(Complaint.submitted_at.asc()).all()
        
    return render_template('principal/escalations.html', tickets=escalated_tickets)

@app.route('/principal/view_escalation.html', methods=['GET', 'POST'])
@login_required
def principal_view_escalation():
    if session.get('role') != 'principal': 
        return redirect(url_for('login'))
        
    ref_id = request.args.get('id')
    
    data = db.session.query(Complaint, RegisteredStudent)\
        .join(RegisteredStudent, Complaint.student_id == RegisteredStudent.id)\
        .filter(Complaint.complaint_ref_id == ref_id).first()
        
    if not data:
        flash('Ticket not found.', 'danger')
        return redirect(url_for('principal_escalations'))
        
    complaint, student = data
    
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'force_close':
            complaint.status = 'Closed'
            complaint.is_escalated = False
            db.session.commit()
            flash(f'Ticket {ref_id} has been forcefully closed by Executive Action.', 'warning')
        return redirect(url_for('principal_view_escalation', id=ref_id))
        
    replies = ComplaintReply.query.filter_by(complaint_id=complaint.id).order_by(ComplaintReply.replied_at.asc()).all()
    
    return render_template('principal/view_escalation.html', complaint=complaint, student=student, replies=replies)

@app.route('/principal/dispatch_email/<ref_id>', methods=['POST'])
@login_required
def principal_dispatch_email(ref_id):
    if session.get('role') != 'principal': 
        return redirect(url_for('login'))
        
    data = db.session.query(Complaint, RegisteredStudent)\
        .join(RegisteredStudent, Complaint.student_id == RegisteredStudent.id)\
        .filter(Complaint.complaint_ref_id == ref_id).first()
        
    if not data:
        flash('Ticket or student record not found.', 'danger')
        return redirect(url_for('principal_escalations'))
        
    complaint, student = data
    
    subject = request.form.get('subject', '').strip() or f"Official Communication regarding Grievance {complaint.complaint_ref_id}"
    body = request.form.get('body', '').strip()
    record_in_history = request.form.get('record_in_history') == 'true'
    
    if not body:
        flash('Email body cannot be empty.', 'warning')
        return redirect(url_for('principal_view_escalation', id=ref_id))
        
    try:
        msg = Message(
            subject=f"[{complaint.complaint_ref_id}] {subject}",
            recipients=[student.personal_email]
        )
        msg.body = f"""OFFICE OF THE PRINCIPAL & HEAD OF INSTITUTION
EXECUTIVE GRIEVANCE DIRECTIVE
----------------------------------------------------------------------
Grievance Docket ID : {complaint.complaint_ref_id}
Complainant Roll No : {student.roll_number}
Complainant Name    : {student.student_name}
Category            : {complaint.category}
Docket Title        : {complaint.title}
----------------------------------------------------------------------

Dear {student.student_name},

{body}

----------------------------------------------------------------------
This is an official communication dispatched under executive seal by the 
Office of the Principal, Autonomous Academic Quality Assurance Cell (IQAC).
For assistance, log in to your Student Portal: {request.url_root.rstrip('/')}/login
"""
        mail.send(msg)
        
        if record_in_history:
            new_reply = ComplaintReply(
                complaint_id=complaint.id,
                reply_text=f"[Official Principal Email Dispatched to {student.personal_email}]\nSubject: {subject}\n\n{body}",
                replied_by_role='Principal',
                replied_by_id=current_user.id,
                replied_at=datetime.now()
            )
            db.session.add(new_reply)
            db.session.commit()
            
        flash(f'Official executive directive dispatched successfully to {student.student_name} ({student.personal_email}).', 'success')
    except Exception as e:
        print(f"Error dispatching email: {e}")
        if record_in_history:
            new_reply = ComplaintReply(
                complaint_id=complaint.id,
                reply_text=f"[Official Principal Directive Recorded]\nSubject: {subject}\n\n{body}",
                replied_by_role='Principal',
                replied_by_id=current_user.id,
                replied_at=datetime.now()
            )
            db.session.add(new_reply)
            db.session.commit()
        flash(f'Directive recorded in ticket history. (Email delivery notice: {e})', 'info')
        
    return redirect(url_for('principal_view_escalation', id=ref_id))

@app.route('/principal/master_records.html')
@login_required
def principal_master_records():
    if session.get('role') != 'principal': 
        return redirect(url_for('login'))
        
    records = db.session.query(Complaint, RegisteredStudent)\
        .join(RegisteredStudent, Complaint.student_id == RegisteredStudent.id)\
        .order_by(Complaint.submitted_at.desc()).all()
        
    return render_template('principal/master_records.html', records=records)

@app.route('/principal/manage_users.html', methods=['GET', 'POST'])
@app.route('/principal/users.html', methods=['GET', 'POST'])
@login_required
def principal_manage_users():
    if session.get('role') != 'principal': 
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if username and email and password:
            hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
            new_admin = Admin(username=username, email=email, password_hash=hashed_pw)
            db.session.add(new_admin)
            db.session.commit()
            flash('New Administrative account created successfully.', 'success')
            
        return redirect(url_for('principal_manage_users'))
        
    admins = Admin.query.all()
    students = RegisteredStudent.query.all()
    revoked_students = RevokedStudent.query.order_by(RevokedStudent.revoked_at.desc()).all()
    
    return render_template('principal/manage_users.html', admins=admins, students=students, revoked_students=revoked_students)

@app.route('/principal/users/revoke_student/<int:id>', methods=['POST'])
@login_required
def principal_revoke_student(id):
    if session.get('role') != 'principal': 
        return redirect(url_for('login'))
        
    student = db.session.get(RegisteredStudent, id)
    if not student:
        flash('Student account not found.', 'danger')
        return redirect(url_for('principal_manage_users'))
        
    roll_number = student.roll_number
    student_name = student.student_name

    try:
        # 1. Decrement support count on other complaints and delete supports cast by this student
        supports_cast = ComplaintSupport.query.filter_by(student_id=student.id).all()
        for s in supports_cast:
            comp = db.session.get(Complaint, s.complaint_id)
            if comp and comp.support_count and comp.support_count > 0:
                comp.support_count -= 1
            db.session.delete(s)

        # 2. Find and delete all complaints lodged by this student along with replies and supports
        student_complaints = Complaint.query.filter_by(student_id=student.id).all()
        for comp in student_complaints:
            ComplaintReply.query.filter_by(complaint_id=comp.id).delete(synchronize_session=False)
            ComplaintSupport.query.filter_by(complaint_id=comp.id).delete(synchronize_session=False)
            db.session.delete(comp)

        # 3. Delete any replies posted by this student
        ComplaintReply.query.filter_by(replied_by_role='Student', replied_by_id=student.id).delete(synchronize_session=False)

        # 4. Clean up moderation logs associated with this student (prevents foreign key integrity constraint failure)
        ModerationLog.query.filter_by(student_id=student.id).delete(synchronize_session=False)
        ModerationLog.query.filter(func.lower(ModerationLog.student_roll) == func.lower(roll_number)).delete(synchronize_session=False)

        # 5. Record in RevokedStudent so re-registration is permanently blocked
        existing_rev = RevokedStudent.query.filter(func.lower(RevokedStudent.roll_number) == func.lower(roll_number)).first()
        if not existing_rev:
            db.session.add(RevokedStudent(
                roll_number=roll_number,
                reason=f'Access permanently revoked by Principal on {datetime.now().strftime("%d %b %Y, %I:%M %p")}'
            ))

        # 6. Reset the CollegeStudent is_registered flag while preserving the official 120-student college roster
        college_record = CollegeStudent.query.filter(func.lower(CollegeStudent.roll_number) == func.lower(roll_number)).first()
        if college_record:
            college_record.is_registered = False

        # 7. Delete the RegisteredStudent account
        db.session.delete(student)

        db.session.commit()
        flash(f'Student {student_name} ({roll_number}) access permanently revoked and record deleted. Login permissions blocked.', 'warning')
    except Exception as e:
        db.session.rollback()
        print(f"Error revoking student access: {e}")
        flash(f'Error revoking student access: {e}', 'danger')

    return redirect(url_for('principal_manage_users'))

@app.route('/principal/users/unrevoke_student/<int:id>', methods=['POST'])
@login_required
def principal_unrevoke_student(id):
    if session.get('role') != 'principal': 
        return redirect(url_for('login'))
        
    rev_record = db.session.get(RevokedStudent, id)
    if not rev_record:
        flash('Revocation record not found.', 'danger')
        return redirect(url_for('principal_manage_users'))
        
    roll_number = rev_record.roll_number
    try:
        db.session.delete(rev_record)
        db.session.commit()
        flash(f'Sanction lifted: Roll Number {roll_number} is no longer restricted. Student is now eligible to register.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error restoring student: {e}', 'danger')

    return redirect(url_for('principal_manage_users'))

@app.route('/principal/users/revoke_admin/<int:id>', methods=['POST'])
@login_required
def principal_revoke_admin(id):
    if session.get('role') != 'principal': 
        return redirect(url_for('login'))
        
    admin = db.session.get(Admin, id)
    if not admin:
        flash('Administrative account not found.', 'danger')
        return redirect(url_for('principal_manage_users'))

    if admin.username == 'admin':
        flash('The primary system administrator account cannot be revoked.', 'danger')
        return redirect(url_for('principal_manage_users'))

    username = admin.username
    try:
        db.session.delete(admin)
        db.session.commit()
        flash(f'Administrative account for {username} has been permanently revoked and deleted.', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'Error revoking administrative account: {e}', 'danger')

    return redirect(url_for('principal_manage_users'))

@app.route('/principal/settings.html', methods=['GET', 'POST'])
@login_required
def principal_settings():
    if session.get('role') != 'principal': 
        return redirect(url_for('login'))
        
    settings = SystemSetting.query.first()
    if not settings:
        settings = SystemSetting()
        db.session.add(settings)
        db.session.commit()
        
    if request.method == 'POST':
        settings.high_escalation_days = int(request.form.get('high_escalation', 3))
        settings.standard_escalation_days = int(request.form.get('standard_escalation', 7))
        was_maintenance = bool(settings.maintenance_mode)
        now_maintenance = True if request.form.get('maintenance_mode') else False
        settings.maintenance_mode = now_maintenance
        db.session.commit()
        
        if now_maintenance and not was_maintenance:
            flash('⚠️ Institutional Maintenance Lockdown has been ACTIVATED. Student and public access is now suspended.', 'warning')
        elif not now_maintenance and was_maintenance:
            flash('✅ Institutional Maintenance Lockdown has been DEACTIVATED. Full campus portal operations restored.', 'success')
        else:
            flash('System governance configurations updated successfully.', 'success')
            
        return redirect(url_for('principal_settings'))
        
    return render_template('principal/settings.html', settings=settings)

@app.route('/principal/notices.html', methods=['GET', 'POST'])
@login_required
def principal_notices():
    if session.get('role') != 'principal': 
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        
        if not title or not content:
            flash('Please provide both an executive title and directive message.', 'danger')
        else:
            new_notice = Announcement(
                title=title,
                content=content,
                posted_by_role='Principal',
                posted_by_id=current_user.id,
                created_at=datetime.now()
            )
            db.session.add(new_notice)
            db.session.commit()
            flash('Official Executive Directive broadcasted to campus bulletin board successfully.', 'success')
        return redirect(url_for('principal_notices'))
        
    announcements = Announcement.query.order_by(Announcement.created_at.desc()).all()
    return render_template('principal/notices.html', announcements=announcements)

@app.route('/principal/notices/delete/<int:id>', methods=['POST'])
@login_required
def principal_delete_notice(id):
    if session.get('role') != 'principal': 
        return redirect(url_for('login'))
        
    notice = db.session.get(Announcement, id)
    if notice:
        db.session.delete(notice)
        db.session.commit()
        flash('Executive directive retracted and removed from the student bulletin board.', 'warning')
    else:
        flash('Notice not found.', 'danger')
    return redirect(url_for('principal_notices'))
if __name__ == '__main__':
    # Creates tables if they don't exist yet before starting the server
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)