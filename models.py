import sqlite3
import os
from datetime import datetime

DATABASE_PATH = "edututor.db"

def get_db_connection():
    """Get database connection with proper configuration"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # Enable dict-like access to rows
    return conn

def init_db():
    """Initialize database with all required tables"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            user_type TEXT NOT NULL CHECK (user_type IN ('student', 'educator')),
            diagnostic_completed BOOLEAN DEFAULT FALSE,
            difficulty_level INTEGER DEFAULT 1,
            student_level TEXT DEFAULT 'Beginner',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    ''')
    
    # Quiz attempts table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS quiz_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            quiz_id INTEGER,
            course_name TEXT NOT NULL,
            topic TEXT NOT NULL,
            answers TEXT NOT NULL,
            score INTEGER NOT NULL,
            total_questions INTEGER NOT NULL,
            percentage REAL NOT NULL,
            feedback TEXT,
            attempt_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Insert demo users if they don't exist
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        from werkzeug.security import generate_password_hash
        
        demo_users = [
            ('Demo Student', 'demo@student.edu', generate_password_hash('demo123'), 'student', 'Intermediate'),
            ('Prof Demo', 'prof@university.edu', generate_password_hash('prof123'), 'educator', 'Advanced'),
            ('Alice Smith', 'alice@student.edu', generate_password_hash('alice123'), 'student', 'Advanced'),
            ('John Doe', 'john@student.edu', generate_password_hash('john123'), 'student', 'Beginner')
        ]
        
        cursor.executemany('''
            INSERT INTO users (name, email, password_hash, user_type, student_level)
            VALUES (?, ?, ?, ?, ?)
        ''', demo_users)
    
    conn.commit()
    conn.close()

# [Include all other database functions from models.py...]