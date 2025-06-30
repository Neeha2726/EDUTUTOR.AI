import streamlit as st
import pandas as pd
import json
import plotly.express as px
import plotly.graph_objects as go
from werkzeug.security import generate_password_hash, check_password_hash
from models import (
    init_db, get_user_by_email, create_user, update_user_login,
    save_quiz_attempt, get_user_quiz_history, get_all_students_progress,
    get_course_analytics, update_user_diagnostic
)
from ai_quiz import AIQuizGenerator
from utils.auth import initialize_session_state
from utils.data_manager import initialize_data

# Page configuration
st.set_page_config(
    page_title="EduTutor AI Platform",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize database and session state
init_db()
initialize_session_state()
initialize_data()

def main():
    st.title("🎓 EduTutor AI Platform")
    st.markdown("---")
    
    # Check if user is logged in
    if not st.session_state.get('logged_in', False):
        show_login_page()
    else:
        show_main_interface()

def show_login_page():
    st.markdown("### Welcome to EduTutor AI")
    st.markdown("An AI-powered personalized education platform")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        # Login/Register tabs
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
        
        # Demo credentials
        st.markdown("---")
        st.markdown("**Demo Login:**")
        st.markdown("Email: demo@student.edu | Password: demo123")
        st.markdown("Email: prof@university.edu | Password: prof123")

def show_main_interface():
    # Sidebar navigation
    with st.sidebar:
        st.markdown(f"### Welcome, {st.session_state.username}")
        st.markdown(f"**Role:** {st.session_state.user_type.title()}")
        
        if st.button("Logout"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    
    # Main content based on user type
    if st.session_state.user_type == "student":
        show_student_interface()
    else:
        show_educator_interface()

# [Continue with all the remaining functions from the app.py file...]

if __name__ == "__main__":
    main()