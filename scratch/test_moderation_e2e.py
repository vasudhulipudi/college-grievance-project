import sys
import os

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db, Complaint, ModerationLog, RegisteredStudent, Admin
from moderation_engine import evaluate_content, analyze_gibberish, analyze_profanity, analyze_spam

def run_tests():
    print("=" * 70)
    print("RUNNING AUTOMATED MODERATION & ANTI-ABUSE ENGINE VERIFICATION SUITE")
    print("=" * 70)

    # ---------------------------------------------------------
    # TEST 1: Unit Tests on Moderation Engine
    # ---------------------------------------------------------
    print("\n--- TEST 1: Moderation Engine Unit Tests ---")
    
    # 1a. Whitelist and legitimate grievance
    res_clean = evaluate_content(
        title="Air conditioner in Lab 301 is not functioning",
        description="The AC unit in Computer Lab 301 Block C has been leaking water and not cooling since yesterday morning during practical classes.",
        category="Laboratory"
    )
    print(f"Clean Grievance: Action={res_clean['action']}, Score={res_clean['overall_score']}")
    assert res_clean['action'] == 'APPROVE', f"Expected APPROVE, got {res_clean['action']}"
    assert res_clean['overall_score'] < 35, f"Expected clean score < 35, got {res_clean['overall_score']}"

    # 1b. Whitelist words that contain substrings (Scunthorpe test)
    res_whitelist = evaluate_content(
        title="Classroom assessment feedback and faculty assistant inquiry",
        description="We need documentation regarding our continuous internal assessment and assignment guidelines from the faculty assistant.",
        category="Academic"
    )
    print(f"Scunthorpe Whitelist Test: Action={res_whitelist['action']}, Score={res_whitelist['overall_score']}")
    assert res_whitelist['action'] == 'APPROVE', f"Expected APPROVE for whitelist terms, got {res_whitelist['action']}"

    # 1c. Keyboard smash gibberish
    res_gibberish = evaluate_content(
        title="asdfghjkl qwertyuiop zxcvbnm",
        description="sdfghjkljhgfdsasdfghjk qwertyuiopasdfghjkl",
        category="Other"
    )
    print(f"Gibberish Test: Action={res_gibberish['action']}, Score={res_gibberish['overall_score']}, Reasons={res_gibberish['all_reasons']}")
    assert res_gibberish['action'] == 'REJECT', f"Expected REJECT for keyboard smash, got {res_gibberish['action']}"
    assert res_gibberish['is_blocked'] is True

    # 1d. Obscene profanity / abuse
    res_profanity = evaluate_content(
        title="This faculty member is a fucking bitch",
        description="I hate everyone fuck you all piece of shit assholes",
        category="Faculty"
    )
    print(f"Profanity Test: Action={res_profanity['action']}, Score={res_profanity['overall_score']}, Reasons={res_profanity['all_reasons']}")
    assert res_profanity['action'] == 'REJECT', f"Expected REJECT for profanity, got {res_profanity['action']}"
    assert res_profanity['is_blocked'] is True

    # 1e. Spam URL
    res_spam = evaluate_content(
        title="Earn free money and crypto prizes online",
        description="Visit http://free-crypto-giveaway.xyz/claim now to get 500 dollars instantly!",
        category="Other"
    )
    print(f"Spam Test: Action={res_spam['action']}, Score={res_spam['overall_score']}, Reasons={res_spam['all_reasons']}")
    assert res_spam['action'] == 'REJECT', f"Expected REJECT for spam link, got {res_spam['action']}"

    print(">>> All Engine Unit Tests PASSED!")

    # ---------------------------------------------------------
    # TEST 2: Integration Tests via Flask Test Client
    # ---------------------------------------------------------
    print("\n--- TEST 2: Flask App Integration Tests ---")
    with app.test_client() as client:
        with app.app_context():
            # Find or ensure a test student
            student = RegisteredStudent.query.first()
            if not student:
                print("No registered student in DB to test with. Creating dummy student...")
                from app import CollegeStudent, bcrypt
                cs = CollegeStudent(roll_number='MOD-TEST-001', student_name='Moderation Tester', is_registered=True)
                db.session.add(cs)
                db.session.commit()
                student = RegisteredStudent(
                    roll_number='MOD-TEST-001',
                    student_name='Moderation Tester',
                    personal_email='modtester@example.com',
                    password_hash=bcrypt.generate_password_hash('testpass123').decode('utf-8')
                )
                db.session.add(student)
                db.session.commit()

            admin = Admin.query.first()
            student_id = student.id
            student_roll = student.roll_number

        # 2a. API /api/check_moderation with student session
        with client.session_transaction() as sess:
            sess['_user_id'] = f"student_{student_id}"
            sess['role'] = 'student'

        # Test API clean
        resp = client.post('/api/check_moderation', json={
            'title': 'Library air conditioner water leakage',
            'description': 'The AC unit on the 2nd floor silent study section is leaking water onto study desks.',
            'category': 'Library'
        })
        assert resp.status_code == 200
        data = resp.get_json()
        print(f"API Clean check: Action={data['action']}, is_clean={data['is_clean']}")
        assert data['action'] == 'APPROVE'

        # Test API blocked gibberish
        resp_gib = client.post('/api/check_moderation', json={
            'title': 'asdfghjkl zxcvbnm',
            'description': 'qwertyuiopasdfghjklzxcvbnm',
            'category': 'Other'
        })
        assert resp_gib.status_code == 200
        data_gib = resp_gib.get_json()
        print(f"API Gibberish check: Action={data_gib['action']}, is_blocked={data_gib['is_blocked']}")
        assert data_gib['action'] == 'REJECT'
        assert data_gib['is_blocked'] is True

        # 2b. Form Submission Pre-Submission Hard Rejection
        with app.app_context():
            initial_complaint_count = Complaint.query.count()
            initial_log_count = ModerationLog.query.filter_by(action_taken='BLOCKED').count()

        resp_submit_block = client.post('/student/submit_complaint.html', data={
            'category': 'Infrastructure',
            'priority': 'High',
            'title': 'qwertyuiop asdfghjkl',
            'description': 'zxcvbnmasdfghjklqwertyuiop',
            'truth_declaration': 'on'
        }, follow_redirects=True)

        assert resp_submit_block.status_code == 200
        with app.app_context():
            after_complaint_count = Complaint.query.count()
            after_log_count = ModerationLog.query.filter_by(action_taken='BLOCKED').count()
            print(f"Complaints count before: {initial_complaint_count}, after: {after_complaint_count}")
            print(f"Blocked logs before: {initial_log_count}, after: {after_log_count}")
            assert after_complaint_count == initial_complaint_count, "Abusive complaint was erroneously saved to complaints table!"
            assert after_log_count == initial_log_count + 1, "Blocked submission was not logged to ModerationLog!"

            # Verify audit log details
            latest_log = ModerationLog.query.order_by(ModerationLog.id.desc()).first()
            assert latest_log.student_roll == student_roll
            assert latest_log.action_taken == 'BLOCKED'
            print(f"Verified Audit Vault record ID={latest_log.id}, Student={latest_log.student_roll}, Reasons={latest_log.reasons}")

        # 2c. Form Submission Clean Grievance
        resp_submit_clean = client.post('/student/submit_complaint.html', data={
            'category': 'Laboratory',
            'priority': 'Medium',
            'title': 'Chemical hood exhaust fan malfunction in Lab 204',
            'description': 'The chemical fume extraction hood in organic chemistry lab 204 is making an abnormal buzzing sound and not drawing air.',
            'truth_declaration': 'on'
        }, follow_redirects=True)

        assert resp_submit_clean.status_code == 200
        with app.app_context():
            clean_ticket = Complaint.query.filter_by(title='Chemical hood exhaust fan malfunction in Lab 204').first()
            assert clean_ticket is not None, "Clean grievance was not saved to complaints table!"
            assert clean_ticket.status == 'Submitted'
            assert clean_ticket.moderation_status == 'Approved'
            print(f"Clean Ticket Created: Ref ID={clean_ticket.complaint_ref_id}, Status={clean_ticket.status}, ModStatus={clean_ticket.moderation_status}")

        # 2d. Quarantined ticket moderation action by Admin
        # Create a flagged/quarantined ticket for testing admin release
        with app.app_context():
            flagged_comp = Complaint(
                complaint_ref_id='CGMS-2026-TESTQ',
                student_id=student_id,
                category='Infrastructure',
                priority='Low',
                title='Water cooler temperature warm in hallway',
                description='The drinking water cooler is not cold enough in block B first floor hallway.',
                status='Quarantined',
                moderation_status='Flagged',
                moderation_score=45,
                moderation_flags='MILD_SUSPICION'
            )
            db.session.add(flagged_comp)
            db.session.commit()
            flagged_id = flagged_comp.id

        # Switch to Admin session
        with client.session_transaction() as sess:
            sess['_user_id'] = f"admin_{admin.id if admin else 1}"
            sess['role'] = 'admin'

        # Verify Admin dashboard pending count excludes the flagged ticket
        resp_admin_dash = client.get('/admin/dashboard.html')
        assert resp_admin_dash.status_code == 200
        assert b'CGMS-2026-TESTQ' not in resp_admin_dash.data, "Quarantined ticket leaked into admin pending table!"
        assert b'Quarantined Grievances' in resp_admin_dash.data

        # Verify Quarantined queue in manage_complaints
        resp_admin_quarantine = client.get('/admin/manage_complaints.html?filter=quarantined')
        assert resp_admin_quarantine.status_code == 200
        assert b'CGMS-2026-TESTQ' in resp_admin_quarantine.data, "Quarantined ticket not visible in quarantined queue!"

        # Admin releases the quarantined ticket
        resp_release = client.post(f'/admin/complaint/{flagged_id}/moderation_action', data={'action': 'release'}, follow_redirects=True)
        assert resp_release.status_code == 200

        with app.app_context():
            released_comp = db.session.get(Complaint, flagged_id)
            assert released_comp.moderation_status == 'Approved'
            assert released_comp.status == 'Submitted'
            print(f"Verified Admin Release: Ticket {released_comp.complaint_ref_id} status={released_comp.status}, moderation_status={released_comp.moderation_status}")

            # Clean up test tickets
            db.session.delete(released_comp)
            if clean_ticket:
                db.session.delete(clean_ticket)
            db.session.commit()

    print("\n" + "=" * 70)
    print("ALL MODERATION & ANTI-ABUSE VERIFICATIONS PASSED SUCCESSFULLY (100%)")
    print("=" * 70)

if __name__ == '__main__':
    run_tests()
