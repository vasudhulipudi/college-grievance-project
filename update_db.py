from app import app, db

with app.app_context():
    # This command scans your app.py for any new models we added
    # and safely creates the missing tables in MySQL without deleting your old data!
    db.create_all()
    print("Success: All missing tables (complaint_replies, system_settings) have been generated!")