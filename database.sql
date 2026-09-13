-- Create the database and switch to it
CREATE DATABASE IF NOT EXISTS college_grievance_db;
USE college_grievance_db;

-- 1. College Students Table (For Verification)
-- This acts as the college's internal database. A student must exist here to register.
CREATE TABLE college_students (
    roll_number VARCHAR(50) PRIMARY KEY,
    student_name VARCHAR(100) NOT NULL,
    is_registered BOOLEAN DEFAULT FALSE
);

-- 2. Registered Students Table
CREATE TABLE registered_students (
    id INT AUTO_INCREMENT PRIMARY KEY,
    roll_number VARCHAR(50) UNIQUE NOT NULL,
    student_name VARCHAR(100) NOT NULL,
    personal_email VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (roll_number) REFERENCES college_students(roll_number) ON DELETE CASCADE
);

-- 3. Admin Table
CREATE TABLE admins (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Principal (Super Admin) Table
CREATE TABLE principals (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. Complaints Table
CREATE TABLE complaints (
    id INT AUTO_INCREMENT PRIMARY KEY,
    complaint_ref_id VARCHAR(50) UNIQUE NOT NULL, -- e.g., CGMS-2026-0001
    student_id INT NOT NULL, -- Hidden from admin view in backend
    category ENUM('Academic', 'Faculty', 'Library', 'Laboratory', 'Hostel', 'Transport', 'Sports', 'Canteen', 'Infrastructure', 'Other') NOT NULL,
    priority ENUM('Low', 'Medium', 'High') NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    support_count INT DEFAULT 0,
    status ENUM('Submitted', 'Under Review', 'In Progress', 'Resolved', 'Closed') DEFAULT 'Submitted',
    is_escalated BOOLEAN DEFAULT FALSE,
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES registered_students(id) ON DELETE CASCADE
);

-- 6. Complaint Support Table (For the duplicate complaint feature)
-- Tracks which student supported which complaint to prevent multiple votes from one user
CREATE TABLE complaint_support (
    id INT AUTO_INCREMENT PRIMARY KEY,
    complaint_id INT NOT NULL,
    student_id INT NOT NULL,
    supported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (complaint_id) REFERENCES complaints(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES registered_students(id) ON DELETE CASCADE,
    UNIQUE KEY unique_support (complaint_id, student_id) -- Prevents duplicate voting
);

-- 7. Complaint Replies Table
CREATE TABLE complaint_replies (
    id INT AUTO_INCREMENT PRIMARY KEY,
    complaint_id INT NOT NULL,
    reply_text TEXT NOT NULL,
    replied_by_role ENUM('Admin', 'Principal') NOT NULL,
    replied_by_id INT NOT NULL,
    replied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (complaint_id) REFERENCES complaints(id) ON DELETE CASCADE
);

-- 8. Notifications Table
CREATE TABLE notifications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_role ENUM('Student', 'Admin', 'Principal') NOT NULL,
    user_id INT NOT NULL,
    message TEXT NOT NULL,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 9. Announcements Table
CREATE TABLE announcements (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    posted_by_role ENUM('Admin', 'Principal') NOT NULL,
    posted_by_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Add Indexes to speed up filtering and searching on the Admin/Principal Dashboards
CREATE INDEX idx_complaint_status ON complaints(status);
CREATE INDEX idx_complaint_priority ON complaints(priority);
CREATE INDEX idx_complaint_category ON complaints(category);
CREATE INDEX idx_complaint_ref ON complaints(complaint_ref_id);

-- Insert dummy college students for testing the verification system later
INSERT INTO college_students (roll_number, student_name) VALUES 
('24252-CM-010', 'Student One'),
('24252-CM-003', 'Student Two'),
('24252-CM-027', 'Student Three'),
('24252-CM-009', 'Student Four'),
('24252-CM-006', 'Student Five'),
('24252-CM-003', 'Student Six');

-- Insert a default Principal account for initial access
-- The password hash here represents 'admin123' (we will handle proper bcrypt hashing in Flask, but this acts as a placeholder)
INSERT INTO principals (username, email, password_hash) VALUES 
('principal', 'vasudhulipudi0@gmail.com', '$2b$12$eO.h8wPq.x.8nLz/I83jyeD9pP2Y8vVb1Fp3aU8a1D1vXU7Z7Z7Z7');