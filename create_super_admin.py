from app import app, db, Principal, bcrypt

with app.app_context():
    # Check if a principal already exists
    p = Principal.query.filter_by(username='principal').first()
    
    if not p:
        # Create the account with a securely hashed password
        hashed_pw = bcrypt.generate_password_hash('admin123').decode('utf-8')
        new_principal = Principal(username='principal', email='vasudhulipudi0@gmail.com', password_hash=hashed_pw)
        db.session.add(new_principal)
        db.session.commit()
        print("Success! Principal account created. Username: 'principal' | Email: 'vasudhulipudi0@gmail.com' | Password: 'admin123'")
    else:
        # If it exists, update email and reset password
        p.email = 'vasudhulipudi0@gmail.com'
        p.password_hash = bcrypt.generate_password_hash('admin123').decode('utf-8')
        db.session.commit()
        print("Success! Principal account updated. Email: 'vasudhulipudi0@gmail.com' | Password: 'admin123'")