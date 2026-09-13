"""
Master Database Initialization & Seed Script
Run this once after deploying to a new cloud database to set up all tables and default accounts.
"""
from app import app, db, CollegeStudent, Admin, Principal, SystemSetting, bcrypt

def init_database():
    with app.app_context():
        print("1. Creating database tables...")
        db.create_all()
        print("   -> Tables verified.")

        print("2. Initializing System Governance Settings...")
        settings = SystemSetting.query.first()
        if not settings:
            settings = SystemSetting(high_escalation_days=3, standard_escalation_days=7, maintenance_mode=False)
            db.session.add(settings)
            db.session.commit()
            print("   -> Default governance settings created.")
        else:
            print("   -> Governance settings already exist.")

        print("3. Seeding verified student roll numbers (24252-CM-001 to 24252-CM-120)...")
        added_students = 0
        for i in range(1, 121):
            roll = f"24252-CM-{i:03d}"
            existing = CollegeStudent.query.filter_by(roll_number=roll).first()
            if not existing:
                student = CollegeStudent(roll_number=roll, student_name=f"Student {i:03d}", is_registered=False)
                db.session.add(student)
                added_students += 1
        if added_students > 0:
            db.session.commit()
            print(f"   -> Added {added_students} student roll numbers.")
        else:
            print("   -> All roll numbers already present.")

        print("4. Ensuring default Admin account...")
        admin = Admin.query.filter_by(username='admin').first()
        admin_email = 'dhulipudisuryakiransrinivas@gmail.com'
        if not admin:
            hashed_pw = bcrypt.generate_password_hash('admin123').decode('utf-8')
            new_admin = Admin(username='admin', email=admin_email, password_hash=hashed_pw)
            db.session.add(new_admin)
            db.session.commit()
            print(f"   -> Admin created. Login: 'admin' | Email: '{admin_email}' | Password: 'admin123'")
        else:
            print(f"   -> Admin exists with email '{admin.email}'.")

        print("5. Ensuring default Principal (Super Admin) account...")
        principal = Principal.query.filter_by(username='principal').first()
        principal_email = 'vasudhulipudi0@gmail.com'
        if not principal:
            hashed_pw = bcrypt.generate_password_hash('admin123').decode('utf-8')
            new_principal = Principal(username='principal', email=principal_email, password_hash=hashed_pw)
            db.session.add(new_principal)
            db.session.commit()
            print(f"   -> Principal created. Login: 'principal' | Email: '{principal_email}' | Password: 'admin123'")
        else:
            print(f"   -> Principal exists with email '{principal.email}'.")

        print("\n=======================================================")
        print("DATABASE INITIALIZATION & SEED COMPLETED SUCCESSFULLY!")
        print("=======================================================")

if __name__ == '__main__':
    init_database()
