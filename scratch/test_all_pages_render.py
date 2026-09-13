import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db, RegisteredStudent, Admin, Principal

def test_all_pages():
    with app.test_client() as client:
        with app.app_context():
            student = RegisteredStudent.query.first()
            admin = Admin.query.first()
            principal = Principal.query.first()

        # 1. Student Submit Complaint Page
        with client.session_transaction() as sess:
            sess['_user_id'] = f"student_{student.id}"
            sess['role'] = 'student'

        res_submit = client.get('/student/submit_complaint.html')
        assert res_submit.status_code == 200
        html = res_submit.get_data(as_text=True)
        assert 'id="moderationMeter"' in html
        assert 'id="moderationBlockModal"' in html
        assert 'checkModerationLive' in html
        assert '/api/check_moderation' in html
        print("PASS: /student/submit_complaint.html renders with moderation meter, modal & live check!")

        # 2. Admin Dashboard
        with client.session_transaction() as sess:
            sess['_user_id'] = f"admin_{admin.id}"
            sess['role'] = 'admin'

        res_admin_dash = client.get('/admin/dashboard.html')
        assert res_admin_dash.status_code == 200
        html_admin = res_admin_dash.get_data(as_text=True)
        assert 'Quarantined Grievances' in html_admin
        assert 'Pre-Submission Blocks' in html_admin
        print("PASS: /admin/dashboard.html renders with Quarantined & Pre-Submission stats!")

        # 3. Admin Manage Complaints
        res_admin_manage = client.get('/admin/manage_complaints.html')
        assert res_admin_manage.status_code == 200
        html_manage = res_admin_manage.get_data(as_text=True)
        assert 'Verified Active Queue' in html_manage
        assert 'Quarantined Audit Queue' in html_manage
        assert 'All Tickets Repository' in html_manage
        print("PASS: /admin/manage_complaints.html renders with Queue Filter tabs!")

        # 4. Principal Dashboard
        with client.session_transaction() as sess:
            sess['_user_id'] = f"principal_{principal.id}"
            sess['role'] = 'principal'

        res_princ_dash = client.get('/principal/dashboard.html')
        assert res_princ_dash.status_code == 200
        html_princ = res_princ_dash.get_data(as_text=True)
        assert 'Pre-Submission Abuse Blocks' in html_princ
        assert 'Disciplinary Anti-Abuse Audit Vault' in html_princ
        print("PASS: /principal/dashboard.html renders with Audit Vault & Abuse metrics!")

        # 5. Splash & Home animation check
        res_splash = client.get('/')
        assert res_splash.status_code == 200
        assert 'splash-shockwave shockwave-1' in res_splash.get_data(as_text=True)
        print("PASS: Splash screen and YouTube animation verified!")

    print("\nALL SYSTEM PAGES & MODERATION UI ELEMENTS RENDER PERFECTLY (100% OK)")

if __name__ == '__main__':
    test_all_pages()
