import streamlit as st
from typing import Tuple, Dict, Any
from backend.database.database import get_db
from backend.services.auth_service import AuthService
from backend.models.user import UserRole

def init_auth_session_state():
    """
    Initializes authentication variables in Streamlit session state.
    """
    if "is_authenticated" not in st.session_state:
        st.session_state.is_authenticated = False
    if "access_token" not in st.session_state:
        st.session_state.access_token = None
    if "user" not in st.session_state:
        st.session_state.user = None

def login_user(email: str, password_raw: str) -> Tuple[bool, str]:
    """
    Authenticates user and saves JWT token + user details in session state.
    Returns (Success, Error Message).
    """
    db_gen = get_db()
    db = next(db_gen)
    try:
        user = AuthService.authenticate_user(db, email, password_raw)
        token = AuthService.create_access_token(
            user_id=user.id,
            email=user.email,
            role=user.role.value
        )
        
        # Save to session state
        st.session_state.is_authenticated = True
        st.session_state.access_token = token
        st.session_state.user = {
            "id": user.id,
            "email": user.email,
            "role": user.role.value,
            "first_name": user.first_name,
            "last_name": user.last_name
        }
        return True, "Login successful"
    except Exception as e:
        return False, str(e)
    finally:
        db.close()

def register_user(
    email: str, 
    password_raw: str, 
    role: UserRole = UserRole.CUSTOMER,
    first_name: str = "",
    last_name: str = ""
) -> Tuple[bool, str]:
    """
    Registers a new user in the database.
    Returns (Success, Info/Error Message).
    """
    db_gen = get_db()
    db = next(db_gen)
    try:
        # Pass empty strings as None
        f_name = first_name.strip() or None
        l_name = last_name.strip() or None
        
        AuthService.register_user(
            db=db,
            email=email,
            password_raw=password_raw,
            role=role,
            first_name=f_name,
            last_name=l_name
        )
        return True, "Registration successful! You can now log in."
    except Exception as e:
        return False, str(e)
    finally:
        db.close()

def logout_user():
    """
    Logs out the user by clearing authentication session state and rerunning.
    """
    st.session_state.is_authenticated = False
    st.session_state.access_token = None
    st.session_state.user = None
    st.rerun()

def check_auth() -> bool:
    """
    Validates token if logged in. Automatically logs out user if token is expired or invalid.
    Returns True if user is authenticated and token is valid, False otherwise.
    """
    init_auth_session_state()
    if st.session_state.is_authenticated:
        try:
            # Cryptographically check if token signature is still valid
            AuthService.validate_access_token(st.session_state.access_token)
            return True
        except Exception:
            # Token signature has expired or was tampered with
            st.session_state.is_authenticated = False
            st.session_state.access_token = None
            st.session_state.user = None
            st.warning("Your session has expired. Please log in again.")
            st.rerun()
            return False
    return False
