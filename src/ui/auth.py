"""UI authorization workflows controlling context session initialization states."""

import streamlit as st
from streamlit_cookies_controller import CookieController
from src.config import CONFIG
from src.db_service import get_user_data, create_user, hash_password

# Initialize the cookie controller once
controller = CookieController()

def render_auth_panel() -> str:
    """Assembles access cards, login inputs, and sign-out triggers in the left tray."""
    st.sidebar.title("🔐 Access Portal")

    # Check cookie for persistent session
    user_cookie = controller.get("authenticated_user")
    
    if user_cookie and "authenticated_user" not in st.session_state:
        # If cookie exists but session is empty, re-sync session
        user_data = get_user_data(user_cookie)
        if user_data:
            st.session_state["authenticated_user"] = user_cookie
            st.session_state["user_name"] = user_data["name"]

    if "authenticated_user" in st.session_state:
        st.sidebar.success(f"Hello, {st.session_state['user_name']}")
        if st.sidebar.button("Log Out", use_container_width=True, key="logout_btn"):
            controller.remove("authenticated_user")
            del st.session_state["authenticated_user"]
            del st.session_state["user_name"]
            st.rerun()
        return st.session_state["authenticated_user"]

    auth_mode = st.sidebar.radio("Choose Action:", ["Login", "Sign Up"])

    if auth_mode == "Sign Up":
        with st.sidebar.form("signup_form"):
            st.subheader("Create Account")
            new_name = st.text_input("Full Name").strip()
            new_email = st.text_input("Email Address").strip().lower()
            new_pass = st.text_input("Password", type="password")

            if st.form_submit_button("Register"):
                if not new_name or not new_email or not new_pass:
                    st.sidebar.error("All fields are required.")
                    return ""
                if get_user_data(new_email) is not None:
                    st.sidebar.error("Email already registered.")
                    return ""

                create_user(new_email, new_name, new_pass)
                st.sidebar.success("Registration successful! Switch to Login.")

    elif auth_mode == "Login":
        with st.sidebar.form("login_form"):
            st.subheader("Sign In")
            email = st.text_input("Email Address").strip().lower()
            password = st.text_input("Password", type="password")

            if st.form_submit_button("Login"):
                user_data = get_user_data(email)
                if user_data and user_data["password_hash"] == hash_password(password):
                    # Set persistent cookie
                    controller.set("authenticated_user", email, path="/")
                    
                    st.session_state["authenticated_user"] = email
                    st.session_state["user_name"] = user_data["name"]
                    st.rerun()
                else:
                    st.sidebar.error("Invalid credentials.")

    return ""
