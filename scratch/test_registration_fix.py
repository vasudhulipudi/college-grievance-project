import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db, CollegeStudent, RegisteredStudent, RevokedStudent, normalize_student_roll

def test_registration():
    print("=" * 70)
    print("RUNNING STUDENT REGISTRATION VERIFICATION SUITE")
    print("=" * 70)

    # 1. Test Roll Normalization
    assert normalize_student_roll('24252cm001') == '24252-CM-001'
    assert normalize_student_roll('24252 cm 001') == '24252-CM-001'
    assert normalize_student_roll('24252_cm_001') == '24252-CM-001'
    assert normalize_student_roll('24252.cm.001') == '24252-CM-001'
    assert normalize_student_roll('22a91a0501') == '22A91A0501'
    print("PASS: normalize_student_roll unit test!")

    with app.test_client() as client:
        # 2. Test Registering with 24252-CM-001 (previously missing)
        with app.app_context():
            # Clean up if already registered from earlier test
            existing_001 = RegisteredStudent.query.filter_by(roll_number='24252-CM-001').first()
            if existing_001:
                db.session.delete(existing_001)
                db.session.commit()

        res1 = client.post('/register', data={
            'roll_number': '24252-CM-001',
            'student_name': 'First Student',
            'email': 'student001@example.com',
            'password': 'password123',
            'confirm_password': 'password123'
        }, follow_redirects=True)

        assert res1.status_code == 200
        assert b'Registration Successful' in res1.data, "Registration for 24252-CM-001 failed!"
        print("PASS: Registered with 24252-CM-001 successfully!")

        # 3. Test Registering with un-hyphenated 24252cm002
        with app.app_context():
            existing_002 = RegisteredStudent.query.filter_by(roll_number='24252-CM-002').first()
            if existing_002:
                db.session.delete(existing_002)
                db.session.commit()

        res2 = client.post('/register', data={
            'roll_number': '24252cm002',
            'student_name': 'Second Student',
            'email': 'student002@example.com',
            'password': 'password123',
            'confirm_password': 'password123'
        }, follow_redirects=True)

        assert res2.status_code == 200
        assert b'Registration Successful' in res2.data, "Registration for 24252cm002 failed!"
        print("PASS: Registered with un-hyphenated 24252cm002 successfully!")

        # 4. Test Registering with dynamic/new roll number (e.g. 24252-CS-099)
        with app.app_context():
            existing_cs = RegisteredStudent.query.filter_by(roll_number='24252-CS-099').first()
            if existing_cs:
                db.session.delete(existing_cs)
            cs_col = CollegeStudent.query.filter_by(roll_number='24252-CS-099').first()
            if cs_col:
                db.session.delete(cs_col)
            db.session.commit()

        res3 = client.post('/register', data={
            'roll_number': '24252-CS-099',
            'student_name': 'Computer Science Student',
            'email': 'cs099@example.com',
            'password': 'password123',
            'confirm_password': 'password123'
        }, follow_redirects=True)

        assert res3.status_code == 200
        assert b'Registration Successful' in res3.data, "Dynamic registration failed!"
        with app.app_context():
            cs_student = RegisteredStudent.query.filter_by(roll_number='24252-CS-099').first()
            assert cs_student is not None
            cs_college = CollegeStudent.query.filter_by(roll_number='24252-CS-099').first()
            assert cs_college is not None
            print(f"PASS: Dynamic student auto-enrolled and registered: {cs_student.roll_number}, {cs_student.student_name}")

        # 5. Test Duplicate Roll Number handling
        res_dup = client.post('/register', data={
            'roll_number': '24252-CM-001',
            'student_name': 'Another Person',
            'email': 'different_email@example.com',
            'password': 'password123',
            'confirm_password': 'password123'
        }, follow_redirects=True)
        assert b'already exists' in res_dup.data
        print("PASS: Duplicate roll number properly detected and guided to login!")

        # 6. Test Duplicate Email handling
        res_email_dup = client.post('/register', data={
            'roll_number': '24252-CM-088',
            'student_name': 'Different Roll',
            'email': 'student001@example.com',
            'password': 'password123',
            'confirm_password': 'password123'
        }, follow_redirects=True)
        assert b'already registered to another student' in res_email_dup.data
        print("PASS: Duplicate email properly rejected with clear warning!")

        # 7. Test Student Login with newly registered credentials
        res_login1 = client.post('/login?role=student', data={
            'username': '24252-CM-001',
            'password': 'password123'
        }, follow_redirects=False)
        assert res_login1.status_code == 302
        assert '/student/dashboard.html' in res_login1.headers.get('Location', '')
        print("PASS: Student login with exact roll number 24252-CM-001 succeeded!")

        # 8. Test Student Login with case/hyphen insensitive username
        res_login2 = client.post('/login?role=student', data={
            'username': '24252cm001',
            'password': 'password123'
        }, follow_redirects=False)
        assert res_login2.status_code == 302
        assert '/student/dashboard.html' in res_login2.headers.get('Location', '')
        print("PASS: Student login with un-hyphenated 24252cm001 succeeded!")

        # 9. Test Revoked Student Re-Registration Block
        with app.app_context():
            rev = RevokedStudent.query.filter_by(roll_number='24252-BANNED-01').first()
            if not rev:
                db.session.add(RevokedStudent(roll_number='24252-BANNED-01', reason='Test ban'))
                db.session.commit()

        res_banned = client.post('/register', data={
            'roll_number': '24252-BANNED-01',
            'student_name': 'Banned User',
            'email': 'banned@example.com',
            'password': 'password123',
            'confirm_password': 'password123'
        }, follow_redirects=True)
        assert b'permanently revoked' in res_banned.data
        print("PASS: Revoked student re-registration properly blocked!")

        # Clean up test accounts
        with app.app_context():
            for r in ['24252-CM-001', '24252-CM-002', '24252-CS-099']:
                reg = RegisteredStudent.query.filter_by(roll_number=r).first()
                if reg:
                    db.session.delete(reg)
            db.session.query(RevokedStudent).filter_by(roll_number='24252-BANNED-01').delete()
            # Reset is_registered on 001 and 002
            s1 = CollegeStudent.query.filter_by(roll_number='24252-CM-001').first()
            if s1: s1.is_registered = False
            s2 = CollegeStudent.query.filter_by(roll_number='24252-CM-002').first()
            if s2: s2.is_registered = False
            # Remove dummy 24252-CS-099 from college_students
            db.session.query(CollegeStudent).filter_by(roll_number='24252-CS-099').delete()
            db.session.commit()

    print("\n" + "=" * 70)
    print("ALL REGISTRATION & LOGIN CHECKS PASSED (100% VERIFIED)")
    print("=" * 70)

if __name__ == '__main__':
    test_registration()
