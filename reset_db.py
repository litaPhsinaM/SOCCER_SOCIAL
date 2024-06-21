from app import app, db
from app import User, Prediction, ChatMessage  # Import the correct models

def reset_db():
    with app.app_context():
        db.drop_all()  # Drops all tables
        db.create_all()  # Creates all tables

if __name__ == '__main__':
    reset_db()
    print("Database reset completed.")