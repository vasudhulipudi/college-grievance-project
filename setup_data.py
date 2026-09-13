from app import app, db, CollegeStudent

with app.app_context():
    added_count = 0
    # Seed roll numbers from 24252-CM-001 to 24252-CM-120
    for i in range(1, 121):
        roll = f"24252-CM-{i:03d}"
        existing = CollegeStudent.query.filter_by(roll_number=roll).first()
        if not existing:
            student = CollegeStudent(
                roll_number=roll,
                student_name=f"Student {i:03d}",
                is_registered=False
            )
            db.session.add(student)
            added_count += 1

    if added_count > 0:
        db.session.commit()
        print(f"Success: Added {added_count} new student roll numbers (24252-CM-001 through 24252-CM-120).")
    else:
        print("All roll numbers (24252-CM-001 through 24252-CM-120) already exist in the database.")

    total = CollegeStudent.query.count()
    print(f"Total verified students in database: {total}")