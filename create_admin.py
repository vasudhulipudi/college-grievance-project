from app import app, db, Admin, bcrypt

with app.app_context():
    # Check if a default admin already exists
    a = Admin.query.filter_by(username='admin').first()
    
    if not a:
        # Create the admin account with a securely hashed password
        hashed_pw = bcrypt.generate_password_hash('admin123').decode('utf-8')
        new_admin = Admin(username='admin', email='dhulipudisuryakiransrinivas@gmail.com', password_hash=hashed_pw)
        db.session.add(new_admin)
        db.session.commit()
        print("Success! Admin account created. Username: 'admin' | Email: 'dhulipudisuryakiransrinivas@gmail.com' | Password: 'admin123'")
    else:
        # If it exists, update email and reset password
        a.email = 'dhulipudisuryakiransrinivas@gmail.com'
        a.password_hash = bcrypt.generate_password_hash('admin123').decode('utf-8')
        db.session.commit()
        print("Success! Admin account updated. Email: 'dhulipudisuryakiransrinivas@gmail.com' | Password: 'admin123'")