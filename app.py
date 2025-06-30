import streamlit as st
import pandas as pd
import json
import plotly.express as px
import plotly.graph_objects as go
import sqlite3
import random
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from typing import Dict, List, Any, Optional

# =============================================================================
# DATABASE LAYER
# =============================================================================

DATABASE_PATH = "edututor.db"

def get_db_connection():
    """Get database connection with proper configuration"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
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

def get_user_by_email(email):
    """Get user by email"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None

def create_user(name, email, password_hash, user_type):
    """Create new user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO users (name, email, password_hash, user_type)
            VALUES (?, ?, ?, ?)
        ''', (name, email, password_hash, user_type))
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return user_id
    except sqlite3.IntegrityError:
        conn.close()
        return None

def update_user_login(user_id):
    """Update user's last login timestamp"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?",
        (user_id,)
    )
    conn.commit()
    conn.close()

def save_quiz_attempt(user_id, course_name, topic, answers, score, total_questions, feedback=None):
    """Save quiz attempt to database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    percentage = (score / total_questions) * 100
    
    cursor.execute('''
        INSERT INTO quiz_attempts (user_id, course_name, topic, answers, score, total_questions, percentage, feedback)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, course_name, topic, answers, score, total_questions, percentage, feedback))
    
    conn.commit()
    conn.close()

def get_user_quiz_history(user_id):
    """Get user's quiz history"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT course_name, topic, score, total_questions, percentage, attempt_date
        FROM quiz_attempts
        WHERE user_id = ?
        ORDER BY attempt_date DESC
    ''', (user_id,))
    history = cursor.fetchall()
    conn.close()
    return [dict(row) for row in history]

def get_all_students_progress():
    """Get progress data for all students"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT u.id, u.name, u.email, u.student_level,
               COUNT(qa.id) as total_quizzes,
               COALESCE(AVG(qa.percentage), 0) as avg_score,
               MAX(qa.attempt_date) as last_activity
        FROM users u
        LEFT JOIN quiz_attempts qa ON u.id = qa.user_id
        WHERE u.user_type = 'student'
        GROUP BY u.id, u.name, u.email, u.student_level
    ''')
    students = cursor.fetchall()
    conn.close()
    return [dict(row) for row in students]

def get_course_analytics():
    """Get course-wide analytics"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT course_name, topic,
               COUNT(*) as attempts,
               AVG(percentage) as avg_score,
               MIN(percentage) as min_score,
               MAX(percentage) as max_score
        FROM quiz_attempts
        GROUP BY course_name, topic
        ORDER BY course_name, avg_score DESC
    ''')
    analytics = cursor.fetchall()
    conn.close()
    return [dict(row) for row in analytics]

def update_user_diagnostic(user_id, difficulty_level, student_level):
    """Update user's diagnostic results"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE users 
        SET diagnostic_completed = TRUE, difficulty_level = ?, student_level = ?
        WHERE id = ?
    ''', (difficulty_level, student_level, user_id))
    conn.commit()
    conn.close()

# =============================================================================
# AI QUIZ GENERATOR
# =============================================================================

class AIQuizGenerator:
    """Enhanced AI Quiz Generator with comprehensive question banks"""
    
    def __init__(self):
        self.question_banks = {
            "mathematics": {
                "easy": [
                    {
                        "question": "What is 15% of 200?",
                        "options": ["20", "25", "30", "35"],
                        "correct": 2,
                        "explanation": "15% of 200 = 0.15 × 200 = 30",
                        "topic": "Percentages"
                    },
                    {
                        "question": "What is the area of a rectangle with length 8 and width 5?",
                        "options": ["40", "13", "26", "35"],
                        "correct": 0,
                        "explanation": "Area = length × width = 8 × 5 = 40",
                        "topic": "Basic Geometry"
                    },
                    {
                        "question": "Solve: 3x + 7 = 16",
                        "options": ["x = 2", "x = 3", "x = 4", "x = 5"],
                        "correct": 1,
                        "explanation": "3x = 16 - 7 = 9, so x = 3",
                        "topic": "Basic Algebra"
                    }
                ],
                "medium": [
                    {
                        "question": "What is the derivative of x² + 3x?",
                        "options": ["2x + 3", "x² + 3", "2x", "3x"],
                        "correct": 0,
                        "explanation": "Using power rule: d/dx(x²) = 2x and d/dx(3x) = 3",
                        "topic": "Calculus"
                    },
                    {
                        "question": "Find the limit of (x² - 4)/(x - 2) as x approaches 2",
                        "options": ["2", "4", "0", "Undefined"],
                        "correct": 1,
                        "explanation": "Factor: (x+2)(x-2)/(x-2) = x+2, limit = 4",
                        "topic": "Limits"
                    }
                ],
                "hard": [
                    {
                        "question": "Solve the differential equation dy/dx = 2y",
                        "options": ["y = Ce^(2x)", "y = C + 2x", "y = 2Ce^x", "y = Ce^x"],
                        "correct": 0,
                        "explanation": "Separable equation: dy/y = 2dx, ln|y| = 2x + C",
                        "topic": "Differential Equations"
                    }
                ]
            },
            "computer_science": {
                "easy": [
                    {
                        "question": "What does CPU stand for?",
                        "options": ["Central Processing Unit", "Computer Processing Unit", "Central Program Unit", "Computer Program Unit"],
                        "correct": 0,
                        "explanation": "CPU stands for Central Processing Unit",
                        "topic": "Computer Basics"
                    },
                    {
                        "question": "Which of these is a programming language?",
                        "options": ["HTML", "Python", "CSS", "HTTP"],
                        "correct": 1,
                        "explanation": "Python is a general-purpose programming language",
                        "topic": "Programming Languages"
                    }
                ],
                "medium": [
                    {
                        "question": "What is the time complexity of binary search?",
                        "options": ["O(n)", "O(log n)", "O(n²)", "O(1)"],
                        "correct": 1,
                        "explanation": "Binary search halves the search space each iteration",
                        "topic": "Algorithms"
                    },
                    {
                        "question": "Which data structure uses LIFO principle?",
                        "options": ["Queue", "Stack", "Array", "Linked List"],
                        "correct": 1,
                        "explanation": "Stack follows Last In, First Out (LIFO) principle",
                        "topic": "Data Structures"
                    }
                ],
                "hard": [
                    {
                        "question": "What is the worst-case time complexity of QuickSort?",
                        "options": ["O(n log n)", "O(n²)", "O(n)", "O(log n)"],
                        "correct": 1,
                        "explanation": "QuickSort worst case is O(n²) when pivot is always smallest/largest",
                        "topic": "Advanced Algorithms"
                    }
                ]
            },
            "physics": {
                "easy": [
                    {
                        "question": "What is the unit of force in SI system?",
                        "options": ["Joule", "Watt", "Newton", "Pascal"],
                        "correct": 2,
                        "explanation": "The SI unit of force is Newton (N)",
                        "topic": "Units and Measurements"
                    }
                ],
                "medium": [
                    {
                        "question": "What is the acceleration due to gravity on Earth?",
                        "options": ["9.8 m/s²", "10 m/s²", "9.81 m/s²", "9.0 m/s²"],
                        "correct": 2,
                        "explanation": "Standard acceleration due to gravity is 9.81 m/s²",
                        "topic": "Mechanics"
                    }
                ],
                "hard": [
                    {
                        "question": "What is Schrödinger's equation used for?",
                        "options": ["Classical mechanics", "Quantum mechanics", "Thermodynamics", "Electromagnetism"],
                        "correct": 1,
                        "explanation": "Schrödinger's equation describes quantum mechanical systems",
                        "topic": "Quantum Physics"
                    }
                ]
            },
            "literature": {
                "easy": [
                    {
                        "question": "Who wrote 'Romeo and Juliet'?",
                        "options": ["Charles Dickens", "William Shakespeare", "Jane Austen", "Mark Twain"],
                        "correct": 1,
                        "explanation": "Romeo and Juliet was written by William Shakespeare",
                        "topic": "Classic Literature"
                    }
                ],
                "medium": [
                    {
                        "question": "What literary device is 'The wind whispered through the trees'?",
                        "options": ["Metaphor", "Simile", "Personification", "Alliteration"],
                        "correct": 2,
                        "explanation": "Personification gives human characteristics to non-human things",
                        "topic": "Literary Devices"
                    }
                ],
                "hard": [
                    {
                        "question": "In which novel does the character Jay Gatsby appear?",
                        "options": ["To Kill a Mockingbird", "The Great Gatsby", "1984", "Pride and Prejudice"],
                        "correct": 1,
                        "explanation": "Jay Gatsby is the protagonist of F. Scott Fitzgerald's 'The Great Gatsby'",
                        "topic": "American Literature"
                    }
                ]
            }
        }

    def generate_diagnostic_quiz(self, num_questions: int = 10) -> List[Dict[str, Any]]:
        """Generate a diagnostic quiz to assess student level"""
        diagnostic_questions = []
        subjects = list(self.question_banks.keys())
        difficulties = ["easy", "medium", "hard"]
        
        questions_per_difficulty = num_questions // 3
        remaining_questions = num_questions % 3
        
        for i, difficulty in enumerate(difficulties):
            count = questions_per_difficulty + (1 if i < remaining_questions else 0)
            
            for _ in range(count):
                subject = random.choice(subjects)
                if difficulty in self.question_banks[subject]:
                    questions = self.question_banks[subject][difficulty]
                    if questions:
                        question = random.choice(questions).copy()
                        question['difficulty'] = difficulty
                        question['subject'] = subject
                        diagnostic_questions.append(question)
        
        random.shuffle(diagnostic_questions)
        return diagnostic_questions

    def generate_quiz(self, topic: str, difficulty_level: int = 2, subject: str = "general", num_questions: int = 5) -> List[Dict[str, Any]]:
        """Generate a quiz based on topic and difficulty"""
        difficulty_map = {1: "easy", 2: "medium", 3: "hard"}
        difficulty = difficulty_map.get(difficulty_level, "medium")
        
        if subject == "general":
            subject = self._determine_subject_from_topic(topic)
        
        subject_key = subject.lower().replace(" ", "_")
        
        if subject_key in self.question_banks and difficulty in self.question_banks[subject_key]:
            available_questions = self.question_banks[subject_key][difficulty].copy()
        else:
            available_questions = self.question_banks["mathematics"][difficulty].copy()
        
        if len(available_questions) < num_questions:
            for other_diff in ["easy", "medium", "hard"]:
                if other_diff != difficulty and subject_key in self.question_banks:
                    if other_diff in self.question_banks[subject_key]:
                        available_questions.extend(self.question_banks[subject_key][other_diff])
        
        selected_questions = random.sample(
            available_questions, 
            min(num_questions, len(available_questions))
        )
        
        for question in selected_questions:
            question['generated_topic'] = topic
            question['difficulty'] = difficulty
            question['subject'] = subject
        
        return selected_questions

    def _determine_subject_from_topic(self, topic: str) -> str:
        """Determine subject based on topic keywords"""
        topic_lower = topic.lower()
        
        math_keywords = ["math", "algebra", "calculus", "geometry", "statistics", "equation", "derivative", "integral"]
        cs_keywords = ["programming", "algorithm", "data structure", "computer", "coding", "software", "python", "java"]
        physics_keywords = ["physics", "force", "energy", "momentum", "gravity", "quantum", "mechanics"]
        literature_keywords = ["literature", "novel", "poem", "shakespeare", "author", "writing", "story"]
        
        if any(keyword in topic_lower for keyword in math_keywords):
            return "mathematics"
        elif any(keyword in topic_lower for keyword in cs_keywords):
            return "computer_science"
        elif any(keyword in topic_lower for keyword in physics_keywords):
            return "physics"
        elif any(keyword in topic_lower for keyword in literature_keywords):
            return "literature"
        else:
            return "mathematics"

    def evaluate_answers(self, questions: List[Dict], answers: List[int]) -> Dict[str, Any]:
        """Evaluate quiz answers and provide detailed feedback"""
        if not questions or not answers:
            return {
                "score": 0,
                "percentage": 0,
                "total_questions": len(questions),
                "correct_answers": 0,
                "performance_level": "Incomplete",
                "feedback": []
            }
        
        correct_count = 0
        feedback = []
        
        for i, (question, answer) in enumerate(zip(questions, answers)):
            is_correct = answer == question['correct']
            if is_correct:
                correct_count += 1
            
            feedback.append({
                "question_id": i,
                "question": question['question'],
                "your_answer": question['options'][answer] if 0 <= answer < len(question['options']) else "No answer",
                "correct_answer": question['options'][question['correct']],
                "is_correct": is_correct,
                "explanation": question.get('explanation', 'No explanation available'),
                "topic": question.get('topic', 'General')
            })
        
        percentage = (correct_count / len(questions)) * 100
        
        if percentage >= 90:
            performance_level = "Excellent"
        elif percentage >= 80:
            performance_level = "Very Good"
        elif percentage >= 70:
            performance_level = "Good"
        elif percentage >= 60:
            performance_level = "Fair"
        else:
            performance_level = "Needs Improvement"
        
        recommendations = self._generate_recommendations(percentage, feedback)
        
        return {
            "score": percentage,
            "percentage": percentage,
            "total_questions": len(questions),
            "correct_answers": correct_count,
            "performance_level": performance_level,
            "feedback": feedback,
            "recommendations": recommendations
        }

    def _generate_recommendations(self, percentage: float, feedback: List[Dict]) -> List[str]:
        """Generate personalized recommendations based on performance"""
        recommendations = []
        
        if percentage >= 90:
            recommendations.append("Excellent work! Consider advancing to more challenging topics.")
            recommendations.append("You might be ready for advanced level courses.")
        elif percentage >= 70:
            recommendations.append("Good performance! Review the questions you missed.")
            recommendations.append("Focus on strengthening weak areas for even better results.")
        else:
            recommendations.append("Consider reviewing fundamental concepts.")
            recommendations.append("Practice more problems in areas where you struggled.")
            recommendations.append("Don't hesitate to seek additional help or resources.")
        
        weak_topics = {}
        for item in feedback:
            if not item['is_correct']:
                topic = item['topic']
                weak_topics[topic] = weak_topics.get(topic, 0) + 1
        
        if weak_topics:
            most_challenging_topic = ""
            max_errors = 0
            for topic, error_count in weak_topics.items():
                if error_count > max_errors:
                    max_errors = error_count
                    most_challenging_topic = topic
            if most_challenging_topic:
                recommendations.append(f"Pay special attention to {most_challenging_topic} - this seems to be a challenging area.")
        
        return recommendations

    def generate_adaptive_quiz(self, user_history: List[Dict], subject: str, num_questions: int = 8) -> List[Dict[str, Any]]:
        """Generate adaptive quiz based on user's performance history"""
        if not user_history:
            return self.generate_quiz("General Assessment", 2, subject, num_questions)
        
        recent_scores = [attempt['percentage'] for attempt in user_history[-5:]]
        avg_recent_score = sum(recent_scores) / len(recent_scores)
        
        if avg_recent_score >= 85:
            difficulty_level = 3
        elif avg_recent_score >= 65:
            difficulty_level = 2
        else:
            difficulty_level = 1
        
        quiz = self.generate_quiz(f"Adaptive {subject} Quiz", difficulty_level, subject, num_questions)
        
        for question in quiz:
            question['adaptive'] = True
            question['based_on_performance'] = avg_recent_score
        
        return quiz

# =============================================================================
# STREAMLIT APPLICATION
# =============================================================================

# Page configuration
st.set_page_config(
    page_title="EduTutor AI Platform",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

def initialize_session_state():
    """Initialize session state variables"""
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'username' not in st.session_state:
        st.session_state.username = None
    if 'user_type' not in st.session_state:
        st.session_state.user_type = None
    if 'user_id' not in st.session_state:
        st.session_state.user_id = None
    if 'student_level' not in st.session_state:
        st.session_state.student_level = 'Beginner'

# Initialize database and session state
init_db()
initialize_session_state()

def main():
    st.title("🎓 EduTutor AI Platform")
    st.markdown("---")
    
    if not st.session_state.get('logged_in', False):
        show_login_page()
    else:
        show_main_interface()

def show_login_page():
    st.markdown("### Welcome to EduTutor AI")
    st.markdown("An AI-powered personalized education platform")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        tab1, tab2 = st.tabs(["Login", "Register"])
        
        with tab1:
            st.markdown("#### Login")
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")
            
            if st.button("Login", use_container_width=True, key="login_btn"):
                if email and password:
                    user = get_user_by_email(email)
                    if user and check_password_hash(user['password_hash'], password):
                        st.session_state.logged_in = True
                        st.session_state.user_id = user['id']
                        st.session_state.username = user['name']
                        st.session_state.user_type = user['user_type']
                        st.session_state.email = user['email']
                        st.session_state.student_level = user.get('student_level', 'Beginner')
                        
                        update_user_login(user['id'])
                        st.success("Logged in successfully!")
                        st.rerun()
                    else:
                        st.error("Invalid email or password")
                else:
                    st.error("Please enter email and password")
        
        with tab2:
            st.markdown("#### Register")
            name = st.text_input("Full Name", key="register_name")
            email = st.text_input("Email", key="register_email")
            password = st.text_input("Password", type="password", key="register_password")
            user_type = st.selectbox("User Type", ["student", "educator"], key="register_type")
            
            if st.button("Register", use_container_width=True, key="register_btn"):
                if name and email and password:
                    password_hash = generate_password_hash(password)
                    user_id = create_user(name, email, password_hash, user_type)
                    
                    if user_id:
                        st.session_state.logged_in = True
                        st.session_state.user_id = user_id
                        st.session_state.username = name
                        st.session_state.user_type = user_type
                        st.session_state.email = email
                        st.session_state.student_level = 'Beginner'
                        
                        st.success("Registration successful!")
                        st.rerun()
                    else:
                        st.error("Email already exists")
                else:
                    st.error("Please fill all fields")
        
        st.markdown("---")
        st.markdown("**Demo Login:**")
        st.markdown("Email: demo@student.edu | Password: demo123")
        st.markdown("Email: prof@university.edu | Password: prof123")

def show_main_interface():
    with st.sidebar:
        st.markdown(f"### Welcome, {st.session_state.username}")
        st.markdown(f"**Role:** {st.session_state.user_type.title()}")
        
        if st.button("Logout"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    
    if st.session_state.user_type == "student":
        show_student_interface()
    else:
        show_educator_interface()

def show_student_interface():
    st.markdown("### Student Dashboard")
    
    tab1, tab2, tab3, tab4 = st.tabs(["📚 Courses", "📝 Take Quiz", "📊 Progress", "🏆 Achievements"])
    
    with tab1:
        show_courses()
    
    with tab2:
        show_quiz_interface()
    
    with tab3:
        show_student_progress()
    
    with tab4:
        show_achievements()

def show_educator_interface():
    st.markdown("### Educator Dashboard")
    
    tab1, tab2, tab3, tab4 = st.tabs(["👥 Students", "📈 Analytics", "📝 Quiz Management", "📚 Courses"])
    
    with tab1:
        show_student_list()
    
    with tab2:
        show_analytics()
    
    with tab3:
        show_quiz_management()
    
    with tab4:
        show_course_management()

def show_courses():
    st.markdown("#### My Courses")
    
    courses = st.session_state.get('courses', [])
    
    if not courses:
        st.info("No courses found. Sync with Google Classroom to load your courses.")
        if st.button("🔄 Sync with Google Classroom"):
            mock_courses = [
                {"name": "Advanced Mathematics", "code": "MATH301", "instructor": "Dr. Smith", "students": 25},
                {"name": "Computer Science Fundamentals", "code": "CS101", "instructor": "Prof. Johnson", "students": 30},
                {"name": "Physics Laboratory", "code": "PHYS201", "instructor": "Dr. Wilson", "students": 20},
                {"name": "English Literature", "code": "ENG102", "instructor": "Ms. Davis", "students": 28}
            ]
            st.session_state.courses = mock_courses
            st.success("Courses synced successfully!")
            st.rerun()
    else:
        for course in courses:
            with st.expander(f"📚 {course['name']} ({course['code']})"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Instructor:** {course['instructor']}")
                    st.write(f"**Students:** {course['students']}")
                with col2:
                    if st.button(f"Take Quiz", key=f"quiz_{course['code']}"):
                        st.session_state.selected_course = course
                        st.session_state.show_quiz = True
                        st.rerun()

def show_quiz_interface():
    st.markdown("#### Take Quiz")
    
    col1, col2 = st.columns(2)
    with col1:
        topic = st.text_input("Enter quiz topic", placeholder="e.g., Algebra, Programming, Physics")
    with col2:
        subject_type = st.selectbox("Subject", ["mathematics", "computer_science", "physics", "literature"])
    
    if topic and st.button("Generate New Quiz"):
        quiz_generator = AIQuizGenerator()
        user_history = get_user_quiz_history(st.session_state.user_id)
        
        with st.spinner("Generating AI-powered quiz..."):
            if len(user_history) > 3:
                quiz_questions = quiz_generator.generate_adaptive_quiz(user_history, subject_type)
            else:
                difficulty_level = 1 if st.session_state.student_level == 'Beginner' else 2 if st.session_state.student_level == 'Intermediate' else 3
                quiz_questions = quiz_generator.generate_quiz(topic, difficulty_level, subject_type)
        
        st.session_state.current_quiz = quiz_questions
        st.session_state.quiz_topic = topic
        st.session_state.quiz_subject = subject_type
        st.session_state.quiz_answers = {}
    
    if 'current_quiz' in st.session_state and st.session_state.current_quiz:
        st.markdown("---")
        st.markdown(f"### Quiz: {st.session_state.get('quiz_topic', 'General Assessment')}")
        
        quiz_questions = st.session_state.current_quiz
        
        for i, question in enumerate(quiz_questions):
            st.markdown(f"**Question {i+1}:** {question['question']}")
            
            answer_index = st.radio(
                "Select your answer:",
                range(len(question['options'])),
                format_func=lambda x: question['options'][x],
                key=f"quiz_q_{i}",
                index=None
            )
            
            if answer_index is not None:
                st.session_state.quiz_answers[i] = answer_index
        
        if len(st.session_state.quiz_answers) == len(quiz_questions):
            if st.button("Submit Quiz", type="primary"):
                quiz_generator = AIQuizGenerator()
                evaluation = quiz_generator.evaluate_answers(quiz_questions, list(st.session_state.quiz_answers.values()))
                
                save_quiz_attempt(
                    user_id=st.session_state.user_id,
                    course_name=st.session_state.get('quiz_subject', 'General'),
                    topic=st.session_state.get('quiz_topic', 'General Quiz'),
                    answers=json.dumps(list(st.session_state.quiz_answers.values())),
                    score=evaluation['correct_answers'],
                    total_questions=evaluation['total_questions'],
                    feedback=json.dumps(evaluation['feedback'])
                )
                
                st.success(f"Quiz completed! Score: {evaluation['correct_answers']}/{evaluation['total_questions']} ({evaluation['percentage']:.1f}%)")
                st.markdown(f"**Performance Level:** {evaluation['performance_level']}")
                
                with st.expander("View Detailed Feedback"):
                    for item in evaluation['feedback']:
                        if item['is_correct']:
                            st.success(f"Q{item['question_id']+1}: ✓ Correct!")
                        else:
                            st.error(f"Q{item['question_id']+1}: ✗ Incorrect")
                            st.write(f"Your answer: {item['your_answer']}")
                            st.write(f"Correct answer: {item['correct_answer']}")
                            st.write(f"Explanation: {item['explanation']}")
                
                if evaluation['recommendations']:
                    st.markdown("### Recommendations")
                    for rec in evaluation['recommendations']:
                        st.write(f"• {rec}")
                
                for key in ['current_quiz', 'quiz_answers', 'quiz_topic', 'quiz_subject']:
                    if key in st.session_state:
                        del st.session_state[key]
                
                st.rerun()
    
    st.markdown("---")
    if st.button("Take Diagnostic Test"):
        st.session_state.show_diagnostic = True
        st.rerun()
    
    if st.session_state.get('show_diagnostic', False):
        st.markdown("### Diagnostic Test")
        st.info("This test will assess your current knowledge level and help personalize your learning experience.")
        
        if 'diagnostic_quiz' not in st.session_state:
            quiz_generator = AIQuizGenerator()
            st.session_state.diagnostic_quiz = quiz_generator.generate_diagnostic_quiz()
            st.session_state.diagnostic_answers = {}
        
        diagnostic_questions = st.session_state.diagnostic_quiz
        
        for i, question in enumerate(diagnostic_questions):
            st.markdown(f"**Question {i+1}:** {question['question']}")
            
            answer_index = st.radio(
                "Select your answer:",
                range(len(question['options'])),
                format_func=lambda x: question['options'][x],
                key=f"diag_q_{i}",
                index=None
            )
            
            if answer_index is not None:
                st.session_state.diagnostic_answers[i] = answer_index
        
        if len(st.session_state.diagnostic_answers) == len(diagnostic_questions):
            if st.button("Complete Diagnostic Test", type="primary"):
                quiz_generator = AIQuizGenerator()
                evaluation = quiz_generator.evaluate_answers(diagnostic_questions, list(st.session_state.diagnostic_answers.values()))
                
                percentage = evaluation['percentage']
                if percentage >= 80:
                    student_level = "Advanced"
                    difficulty_level = 3
                elif percentage >= 60:
                    student_level = "Intermediate"
                    difficulty_level = 2
                else:
                    student_level = "Beginner"
                    difficulty_level = 1
                
                update_user_diagnostic(st.session_state.user_id, difficulty_level, student_level)
                st.session_state.student_level = student_level
                
                st.success(f"Diagnostic test completed! Your level: **{student_level}**")
                st.markdown(f"**Score:** {evaluation['correct_answers']}/{evaluation['total_questions']} ({percentage:.1f}%)")
                
                for key in ['diagnostic_quiz', 'diagnostic_answers', 'show_diagnostic']:
                    if key in st.session_state:
                        del st.session_state[key]
                
                st.rerun()

def show_student_progress():
    st.markdown("#### Your Progress")
    
    quiz_history = get_user_quiz_history(st.session_state.user_id)
    
    if not quiz_history:
        st.info("No quiz history available. Take some quizzes to see your progress!")
        return
    
    df = pd.DataFrame(quiz_history)
    
    st.markdown("##### Score Trend")
    df['attempt_date'] = pd.to_datetime(df['attempt_date'])
    df_sorted = df.sort_values('attempt_date')
    
    fig = px.line(df_sorted, x='attempt_date', y='percentage', title='Quiz Performance Over Time')
    fig.update_layout(yaxis_title="Score (%)", xaxis_title="Date")
    st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("##### Performance by Course")
    course_avg = df.groupby('course_name')['percentage'].mean().reset_index()
    
    fig2 = px.bar(course_avg, x='course_name', y='percentage', title='Average Score by Course')
    fig2.update_layout(yaxis_title="Average Score (%)", xaxis_title="Course")
    st.plotly_chart(fig2, use_container_width=True)
    
    st.markdown("##### Recent Quiz Results")
    recent_df = df_sorted.tail(10)[['course_name', 'topic', 'score', 'total_questions', 'percentage']].copy()
    recent_df = recent_df.iloc[::-1]
    st.dataframe(recent_df, use_container_width=True)

def show_achievements():
    st.markdown("#### Achievements")
    
    quiz_history = get_user_quiz_history(st.session_state.user_id)
    
    if not quiz_history:
        st.info("Complete quizzes to unlock achievements!")
        return
    
    df = pd.DataFrame(quiz_history)
    total_quizzes = len(quiz_history)
    avg_score = df['percentage'].mean()
    perfect_scores = len(df[df['percentage'] == 100])
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Quizzes", total_quizzes)
        if total_quizzes >= 10:
            st.success("🏆 Quiz Master - 10+ quizzes completed!")
    
    with col2:
        st.metric("Average Score", f"{avg_score:.1f}%")
        if avg_score >= 80:
            st.success("⭐ High Achiever - 80%+ average!")
    
    with col3:
        st.metric("Perfect Scores", perfect_scores)
        if perfect_scores >= 3:
            st.success("💯 Perfectionist - 3+ perfect scores!")

def show_student_list():
    st.markdown("#### Student Performance Overview")
    
    students_data = get_all_students_progress()
    
    if not students_data:
        st.info("No student data available yet. Students need to take quizzes to appear here.")
        return
    
    df = pd.DataFrame(students_data)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Students", len(df))
    with col2:
        avg_quizzes = df['total_quizzes'].mean() if len(df) > 0 else 0
        st.metric("Avg Quiz Count", f"{avg_quizzes:.1f}")
    with col3:
        class_avg = df['avg_score'].mean() if len(df) > 0 else 0
        st.metric("Class Average", f"{class_avg:.1f}%")
    with col4:
        today = pd.Timestamp.now().strftime('%Y-%m-%d')
        active_today = len(df[df['last_activity'].fillna('').str.contains(today, na=False)])
        st.metric("Active Today", active_today)
    
    display_cols = ['name', 'student_level', 'total_quizzes', 'avg_score', 'last_activity']
    display_df = df[display_cols].copy()
    display_df.columns = ['Name', 'Level', 'Total Quizzes', 'Avg Score (%)', 'Last Activity']
    st.dataframe(display_df, use_container_width=True)

def show_analytics():
    st.markdown("#### Class Analytics")
    
    analytics_data = get_course_analytics()
    
    if not analytics_data:
        st.info("No quiz data available yet. Analytics will appear once students start taking quizzes.")
        return
    
    st.markdown("##### Score Distribution")
    scores = [item['avg_score'] for item in analytics_data if item['avg_score']]
    
    if scores:
        fig = px.histogram(x=scores, nbins=10, title="Average Score Distribution by Topic")
        fig.update_layout(xaxis_title="Score (%)", yaxis_title="Number of Topics")
        st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("##### Topic Performance Analysis")
    if analytics_data:
        df_analytics = pd.DataFrame(analytics_data)
        
        fig2 = px.scatter(df_analytics, x='attempts', y='avg_score', 
                         size='attempts', hover_name='topic',
                         color='course_name',
                         title='Topic Performance vs Attempts')
        fig2.update_layout(xaxis_title="Number of Attempts", yaxis_title="Average Score (%)")
        st.plotly_chart(fig2, use_container_width=True)
        
        st.markdown("##### Detailed Analytics")
        display_df = df_analytics[['course_name', 'topic', 'attempts', 'avg_score', 'min_score', 'max_score']].copy()
        display_df.columns = ['Course', 'Topic', 'Attempts', 'Avg Score', 'Min Score', 'Max Score']
        display_df = display_df.round(1)
        st.dataframe(display_df, use_container_width=True)

def show_quiz_management():
    st.markdown("#### Quiz Management")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("##### Create New Quiz")
        course = st.selectbox("Select Course", ["mathematics", "computer_science", "physics", "literature"])
        topic = st.text_input("Quiz Topic")
        difficulty = st.selectbox("Difficulty Level", ["Easy", "Medium", "Hard"])
        num_questions = st.slider("Number of Questions", 5, 20, 10)
        
        if st.button("Generate Quiz"):
            if topic:
                quiz_generator = AIQuizGenerator()
                difficulty_level = {"Easy": 1, "Medium": 2, "Hard": 3}[difficulty]
                
                with st.spinner("Generating quiz with AI..."):
                    questions = quiz_generator.generate_quiz(topic, difficulty_level, course, num_questions)
                
                st.success(f"Quiz on '{topic}' created successfully with {len(questions)} questions!")
                
                with st.expander("Preview Generated Questions"):
                    for i, q in enumerate(questions[:3]):
                        st.write(f"**Q{i+1}:** {q['question']}")
                        for j, option in enumerate(q['options']):
                            st.write(f"  {chr(65+j)}. {option}")
                        st.write(f"**Correct:** {q['options'][q['correct']]}")
                        st.write("---")
            else:
                st.error("Please enter a quiz topic")
    
    with col2:
        st.markdown("##### Quiz Analytics")
        analytics = get_course_analytics()
        
        if analytics:
            st.write("**Recent Quiz Performance:**")
            for item in analytics[:5]:
                st.write(f"• {item['topic']}: {item['avg_score']:.1f}% avg ({item['attempts']} attempts)")
        else:
            st.info("No quiz data available yet")

def show_course_management():
    st.markdown("#### Course Management")
    
    courses = st.session_state.get('courses', [])
    
    if courses:
        for course in courses:
            with st.expander(f"📚 {course['name']}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Code:** {course['code']}")
                    st.write(f"**Students:** {course['students']}")
                with col2:
                    if st.button(f"View Analytics", key=f"analytics_{course['code']}"):
                        st.info(f"Analytics for {course['name']} would be displayed here.")
    else:
        st.info("No courses available. Sync with Google Classroom to load courses.")
        if st.button("🔄 Sync Courses"):
            mock_courses = [
                {"name": "Advanced Mathematics", "code": "MATH301", "instructor": "Dr. Smith", "students": 25},
                {"name": "Computer Science Fundamentals", "code": "CS101", "instructor": "Prof. Johnson", "students": 30},
                {"name": "Physics Laboratory", "code": "PHYS201", "instructor": "Dr. Wilson", "students": 20},
                {"name": "English Literature", "code": "ENG102", "instructor": "Ms. Davis", "students": 28}
            ]
            st.session_state.courses = mock_courses
            st.success("Courses synced successfully!")
            st.rerun()

if __name__ == "__main__":
    main()