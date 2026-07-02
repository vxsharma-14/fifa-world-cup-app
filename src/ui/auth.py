"""UI authorization workflows controlling context session initialization states."""

import streamlit as st
from streamlit_cookies_controller import CookieController
from src.config import CONFIG
from src.db_service import get_user_data, create_user, hash_password


def _clear_auth_session(controller: CookieController) -> None:
    """Clears the persisted and in-memory auth state."""
    controller.remove("authenticated_user")
    if "authenticated_user" in st.session_state:
        del st.session_state["authenticated_user"]
    if "user_name" in st.session_state:
        del st.session_state["user_name"]


def _is_account_active(user_data: dict | None) -> bool:
    """Returns True when the account is active or legacy records omit the flag."""
    if not user_data:
        return False
    return bool(user_data.get("is_active", True))


def render_auth_panel() -> str:
    """Assembles access cards, login inputs, and sign-out triggers in the left tray."""
    st.sidebar.title("🔐 Access Portal")
    
    # Instantiate controller locally to ensure no stale state
    controller = CookieController()
    
    # Check cookie for persistent session
    user_cookie = controller.get("authenticated_user")
    
    # 1. Handle Logout/Session Mismatch
    if "authenticated_user" in st.session_state and user_cookie != st.session_state["authenticated_user"]:
        # Session state is out of sync with cookie, force logout to be safe
        _clear_auth_session(controller)
        st.rerun()

    # 2. Sync if Cookie exists but Session empty
    if user_cookie and "authenticated_user" not in st.session_state:
        user_data = get_user_data(user_cookie)
        if user_data and _is_account_active(user_data):
            st.session_state["authenticated_user"] = user_cookie
            st.session_state["user_name"] = user_data["name"]
        else:
            # Cookie exists for unknown user, clear it
            _clear_auth_session(controller)
            if user_data and not _is_account_active(user_data):
                st.sidebar.error("This account has been disabled.")
            st.rerun()

    # 3. Render State
    if "authenticated_user" in st.session_state:
        current_user_data = get_user_data(st.session_state["authenticated_user"])
        if not _is_account_active(current_user_data):
            _clear_auth_session(controller)
            st.sidebar.error("This account has been disabled.")
            st.rerun()
        st.sidebar.success(f"Hello, {st.session_state['user_name']}")
        if st.sidebar.button("Log Out", use_container_width=True, key="logout_btn"):
            _clear_auth_session(controller)
            st.rerun()
        return st.session_state["authenticated_user"]

    # 4. Auth Forms
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
                if user_data and _is_account_active(user_data) and user_data["password_hash"] == hash_password(password):
                    # Set persistent cookie
                    controller.set("authenticated_user", email, path="/")
                    
                    st.session_state["authenticated_user"] = email
                    st.session_state["user_name"] = user_data["name"]
                    st.rerun()
                elif user_data and not _is_account_active(user_data):
                    st.sidebar.error("This account has been disabled.")
                else:
                    st.sidebar.error("Invalid credentials.")

    return ""
