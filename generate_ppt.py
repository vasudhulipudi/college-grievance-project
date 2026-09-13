from pptx import Presentation
from pptx.util import Pt

# Initialize presentation
prs = Presentation()

def add_slide(title_text, bullet_points):
    """Helper function to create a slide with a title and bullet points."""
    slide_layout = prs.slide_layouts[1] # Title and Content layout
    slide = prs.slides.add_slide(slide_layout)
    title = slide.shapes.title
    title.text = title_text
    
    body_shape = slide.placeholders[1]
    tf = body_shape.text_frame
    
    for i, point in enumerate(bullet_points):
        if i == 0:
            tf.text = point
        else:
            p = tf.add_paragraph()
            p.text = point

# --- Slide 1: Title Slide ---
title_slide_layout = prs.slide_layouts[0]
slide = prs.slides.add_slide(title_slide_layout)
title = slide.shapes.title
subtitle = slide.placeholders[1]
title.text = "College Grievance & Facility Management System"
subtitle.text = "Final Year Diploma Project Presentation\nAcademic Year: 2026-2027"

# --- Slide 2: Team Members ---
add_slide("Team Members & Project Guide", [
    "Project Guide: [Insert Name], [Designation]",
    "1. Dhulipudi Surya Kiran Srinivas (Roll No: [Insert])",
    "2. [Team Member 2 Name] (Roll No: [Insert])",
    "3. [Team Member 3 Name] (Roll No: [Insert])",
    "4. [Team Member 4 Name] (Roll No: [Insert])",
    "5. [Team Member 5 Name] (Roll No: [Insert])",
    "6. [Team Member 6 Name] (Roll No: [Insert])"
])

# --- Slide 3: Abstract ---
add_slide("Project Abstract", [
    "A secure, web-based platform designed to bridge the communication gap between students and administration.",
    "Provides a centralized portal to report infrastructure and academic issues with strict identity protection.",
    "Automates ticket tracking from 'Submitted' to 'Closed'.",
    "Detects duplicate complaints to prevent database spam.",
    "Features an automated escalation matrix to hold staff accountable."
])

# --- Slide 4: Existing System & Disadvantages ---
add_slide("Existing System & Disadvantages", [
    "Currently relies on manual paper-based forms or basic emails.",
    "DISADVANTAGE: No Transparency - Students cannot track complaint status.",
    "DISADVANTAGE: Fear of Retaliation - Lack of anonymity prevents reporting.",
    "DISADVANTAGE: Data Redundancy - Multiple students report the exact same issue.",
    "DISADVANTAGE: No Accountability - Issues can be ignored for weeks."
])

# --- Slide 5: Proposed System & Advantages ---
add_slide("Proposed System & Advantages", [
    "A fully digitized, three-tier web application with role-based access.",
    "ADVANTAGE: 100% Anonymity - Admin staff cannot see student identities.",
    "ADVANTAGE: Live Tracking - Unique IDs (e.g., CGMS-2026-001) for real-time tracking.",
    "ADVANTAGE: Smart Detection - Groups similar complaints via a 'Support' system.",
    "ADVANTAGE: Automated Escalation - Unresolved tickets automatically go to the Principal."
])

# --- Slide 6: Software Requirements ---
add_slide("Software Requirements", [
    "Frontend Technologies: HTML5, CSS3, JavaScript",
    "Frontend Framework: Bootstrap 5 (Mobile Responsive)",
    "Backend Language: Python 3.10+",
    "Backend Framework: Flask & SQLAlchemy (ORM)",
    "Database Management: MySQL Community Server 8.0",
    "Development Tools: Visual Studio Code, Git/GitHub"
])

# --- Slide 7: Hardware Requirements ---
add_slide("Hardware Requirements", [
    "Processor: Intel Core i3 / AMD Ryzen 3 or higher",
    "RAM: Minimum 4 GB (8 GB Recommended)",
    "Storage: 256 GB HDD/SSD",
    "Network: Active Internet Connection (Required for SMTP Emails)",
    "Architecture: 64-bit operating system (Windows / Linux / macOS)"
])

# --- Slide 8: System Architecture ---
add_slide("System Architecture", [
    "Follows a secure Client-Server Architecture.",
    "Presentation Layer (Client): UI built with HTML/Bootstrap where users submit data.",
    "Logic Layer (Server): Python Flask application handles authentication and logic.",
    "Data Layer (Database): MySQL server securely stores records and interaction histories."
])

# --- Slide 9: Core User Modules ---
add_slide("Core User Modules", [
    "Student Module: Secure registration, dashboard stats, submission form, and timeline.",
    "Admin Module: Master grievance list, status updating, and anonymous interaction.",
    "Principal (Super Admin) Module: Global database view, user management, and privacy override."
])

# --- Slide 10: Security Features ---
add_slide("System Security Implementation", [
    "Password Encryption: Cryptographically hashed using Flask-Bcrypt.",
    "SQL Injection Prevention: SQLAlchemy ORM sanitizes all user inputs.",
    "Session Management: Cryptographically signed cookies prevent session hijacking.",
    "Strict Verification: Registration locked to a pre-approved college database."
])

# --- Slide 11: Conclusion & Future Scope ---
add_slide("Conclusion & Future Scope", [
    "CONCLUSION: The system successfully eliminates traditional flaws by enforcing accountability and automating workflow.",
    "FUTURE SCOPE: Dedicated cross-platform Mobile Application (Android/iOS).",
    "FUTURE SCOPE: AI Chatbot integration for instant FAQ resolution.",
    "FUTURE SCOPE: SMS alerts alongside existing email notifications."
])

# --- Slide 12: Q&A ---
title_slide_layout = prs.slide_layouts[0]
slide = prs.slides.add_slide(title_slide_layout)
title = slide.shapes.title
subtitle = slide.placeholders[1]
title.text = "Thank You!"
subtitle.text = "Any Questions?"

# Save the presentation
prs.save('College_Grievance_Presentation.pptx')
print("Success! 'College_Grievance_Presentation.pptx' has been generated in your folder.")