# College Grievance & Facility Management System - Free Deployment Guide

This guide provides 3 proven ways to deploy this Flask + MySQL system to a **free public domain** accessible worldwide.

---

## Quick Comparison Table

| Method | Setup Time | Cost | Best For | Domain Format |
| :--- | :--- | :--- | :--- | :--- |
| **Method 1: Instant Tunnel (Localtunnel / SSH)** | **30 Seconds** | Free | Live demo, testing from your PC right now | `https://your-name.loca.lt` |
| **Method 2: PythonAnywhere (Recommended)** | **5-10 Mins** | 100% Free | Permanent 24/7 hosting with built-in MySQL | `https://username.pythonanywhere.com` |
| **Method 3: Render.com + TiDB Cloud** | **10-15 Mins** | 100% Free | Modern GitHub CI/CD with Serverless MySQL | `https://appname.onrender.com` |

---

## Method 1: Instant Free Public Domain (30 Seconds from your PC)

Use this method if your Flask app is running on your computer and you want to share a live HTTPS link immediately with anyone (teachers, examiners, friends).

### Step 1: Start your Flask Application
Open a terminal in the project directory:
```powershell
python app.py
```
*(Ensure it is running on `http://127.0.0.1:5000`)*

### Step 2: Run LocalTunnel in a Second Terminal
Open another PowerShell window and run:
```powershell
npx localtunnel --port 5000
```
Or choose a custom subdomain:
```powershell
npx localtunnel --port 5000 --subdomain grievance-portal
```
You will immediately get a live URL:
```text
your url is: https://grievance-portal.loca.lt
```
*Note: The first time a user opens a localtunnel link, it asks for the tunnel host IP. You can find your IP at [localtunnel.me](https://localtunnel.me) or [ipv4.icanhazip.com](https://ipv4.icanhazip.com).*

### Alternative: Instant SSH Tunnel (Zero Installation Needed)
In PowerShell, run:
```powershell
ssh -R 80:localhost:5000 nokey@localhost.run
```
It immediately outputs an encrypted HTTPS domain like `https://xxxxxx.lhr.life`.

---

## Method 2: Permanent 24/7 Hosting on PythonAnywhere (Recommended)

PythonAnywhere is the easiest permanent free host for Python + MySQL because **it includes both the Python web server AND a free MySQL database in one place**, with no credit card required.

### Step 1: Create a Free Account
1. Go to [https://www.pythonanywhere.com](https://www.pythonanywhere.com).
2. Click **Pricing & signup** -> Select the **"Create a Beginner account"** (Free forever).
3. Choose your username (e.g. `suryakiran`). Your live website domain will be:
   `https://suryakiran.pythonanywhere.com`

### Step 2: Set Up MySQL Database
1. In your PythonAnywhere dashboard, click the **Databases** tab.
2. Set a MySQL password and click **Initialize MySQL**.
3. Under **Create a database**, type `college_grievance` and click **Create database**.
4. Note your database details shown on the screen:
   - Host: `<username>.mysql.pythonanywhere-services.com`
   - Database name: `<username>$college_grievance`
   - Username: `<username>`
   - Password: `<the password you set>`

### Step 3: Upload Project Files
1. Click the **Consoles** tab -> Click **Bash** to open a web terminal.
2. Clone your GitHub repository:
   ```bash
   git clone https://github.com/<your-username>/college_grievance_facility_management_system.git
   cd college_grievance_facility_management_system
   ```
   *(Or alternatively, upload files as a ZIP in the **Files** tab and extract it using `unzip`).*

3. Install required libraries:
   ```bash
   pip install -r requirements.txt
   ```

4. Initialize the database (seeds 120 roll numbers, admin, principal):
   In the Bash console, run:
   ```bash
   export DATABASE_URL="mysql+pymysql://<username>:<password>@<username>.mysql.pythonanywhere-services.com/<username>\$college_grievance"
   python init_db.py
   ```

### Step 4: Configure the Web App
1. Click the **Web** tab in PythonAnywhere.
2. Click **Add a new web app**.
3. Select **Manual configuration** -> Select **Python 3.10**.
4. Scroll to the **Code** section:
   - **Source code**: `/home/<username>/college_grievance_facility_management_system`
   - **Working directory**: `/home/<username>/college_grievance_facility_management_system`
5. Click on the **WSGI configuration file** link (e.g. `/var/www/<username>_pythonanywhere_com_wsgi.py`).
6. Replace its contents with:
   ```python
   import sys
   import os

   # Add project path to system path
   project_home = '/home/<username>/college_grievance_facility_management_system'
   if project_home not in sys.path:
       sys.path.insert(0, project_home)

   # Set database environment variable
   os.environ['DATABASE_URL'] = 'mysql+pymysql://<username>:<password>@<username>.mysql.pythonanywhere-services.com/<username>$college_grievance'

   # Import Flask app as application
   from app import app as application
   ```
   *(Make sure to replace `<username>` and `<password>` with your actual credentials).*
7. Save the file.
8. Go back to the **Web** tab and click the green **Reload <username>.pythonanywhere.com** button.
9. Visit your website: `https://<username>.pythonanywhere.com`!

---

## Method 3: Permanent 24/7 Hosting on Render.com + Free TiDB Cloud

Render is a modern cloud platform with automatic Git deployment, paired with TiDB Cloud for free Serverless MySQL (5GB free forever).

### Step 1: Create a Free MySQL Database on TiDB Cloud
1. Go to [https://tidbcloud.com](https://tidbcloud.com) and create a free account (No credit card).
2. Click **Create Cluster** -> Select **Serverless** (Free 5GB).
3. Click **Connect** -> Choose **SQLAlchemy / Python**.
4. Copy the connection string. It looks like:
   `mysql+pymysql://<user>:<password>@gateway01.<region>.prod.aws.tidbcloud.com:4000/<dbname>?ssl_verify_cert=true`

### Step 2: Push Project to GitHub
In your local project folder:
```powershell
git init
git add .
git commit -m "Initial commit for deployment"
git branch -M main
git remote add origin https://github.com/<your-username>/college_grievance.git
git push -u origin main
```

### Step 3: Deploy on Render.com
1. Go to [https://render.com](https://render.com) and sign in with GitHub.
2. Click **New +** -> **Web Service**.
3. Connect your `college_grievance` GitHub repository.
4. Fill in:
   - **Name**: `college-grievance-portal` (your URL will be `https://college-grievance-portal.onrender.com`)
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt && python init_db.py`
   - **Start Command**: `gunicorn app:app`
   - **Plan**: `Free`
5. Under **Environment Variables**, add:
   - `DATABASE_URL` = `<your TiDB connection string>`
   - `SECRET_KEY` = `grievance_prod_secret_key_2026`
   - `MAIL_USERNAME` = `dhulipudisuryakiransrinivas@gmail.com`
   - `MAIL_PASSWORD` = `<your google app password>`
6. Click **Create Web Service**.
7. Render will build and deploy your project automatically. Your app is live!

---

## Pre-Configured Files in This Project

All necessary deployment configurations are already bundled:
- `requirements.txt`: Includes Flask, Flask-SQLAlchemy, PyMySQL, gunicorn, reportlab, xlsxwriter, etc.
- `Procfile`: Ready for production servers (`web: gunicorn app:app`).
- `render.yaml`: 1-click blueprint for Render.
- `init_db.py`: Automatically seeds student roll numbers (`24252-CM-001` to `120`), default Admin, Principal, and governance settings.
- `app.py`: Automatically reads `DATABASE_URL` from the cloud environment or falls back to local MySQL.
