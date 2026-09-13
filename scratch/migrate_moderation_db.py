from app import app, db, Complaint
from sqlalchemy import inspect, text

def run_migration():
    with app.app_context():
        inspector = inspect(db.engine)
        existing_cols = [c['name'] for c in inspector.get_columns('complaints')]
        print(f"Existing columns in complaints: {existing_cols}")

        with db.engine.connect() as conn:
            if 'moderation_status' not in existing_cols:
                conn.execute(text("ALTER TABLE complaints ADD COLUMN moderation_status VARCHAR(20) DEFAULT 'Approved'"))
                print("Added column 'moderation_status' to complaints.")
            if 'moderation_score' not in existing_cols:
                conn.execute(text("ALTER TABLE complaints ADD COLUMN moderation_score INT DEFAULT 0"))
                print("Added column 'moderation_score' to complaints.")
            if 'moderation_flags' not in existing_cols:
                conn.execute(text("ALTER TABLE complaints ADD COLUMN moderation_flags VARCHAR(255) NULL"))
                print("Added column 'moderation_flags' to complaints.")
            conn.commit()

        # Create any new tables (like moderation_logs)
        db.create_all()
        print("db.create_all() executed.")

        # Verify updated columns
        inspector = inspect(db.engine)
        updated_cols = [c['name'] for c in inspector.get_columns('complaints')]
        print(f"Updated columns in complaints: {updated_cols}")
        print("Tables in database:", inspector.get_table_names())

if __name__ == '__main__':
    run_migration()
