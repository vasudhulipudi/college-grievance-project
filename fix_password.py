from app import app, db, Principal, bcrypt

with app.app_context():
    # Find the principal account
    p = Principal.query.filter_by(username='principal').first()
    if p:
        # Generate a real, secure hash for 'admin123'
        p.password_hash = bcrypt.generate_password_hash('admin123').decode('utf-8')
        db.session.commit()
        print("Principal password securely updated to 'admin123'!")