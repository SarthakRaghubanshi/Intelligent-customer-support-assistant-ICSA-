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
            "last_name": user.last_name,
            "restaurant_id": user.restaurant_id
        }
        
        # Initialize default view based on role
        init_landing_view(user.role.value)
        return True, "Login successful"
    except Exception as e:
        return False, str(e)
    finally:
        db.close()

def init_landing_view(role: str):
    """Initializes the landing view and restaurant context in session state based on user role."""
    role_normalized = str(role).strip().lower()
    if role_normalized == "admin":
        st.session_state.active_view = "⚙️ Admin Dashboard"
        if "selected_restaurant" not in st.session_state or st.session_state.selected_restaurant is None:
            st.session_state.selected_restaurant = "Restaurant_A"
    elif role_normalized == "restaurant":
        st.session_state.active_view = "📊 Restaurant Dashboard"
        user_info = st.session_state.get("user")
        if user_info:
            st.session_state.selected_restaurant = user_info.get("restaurant_id")
    else:
        st.session_state.active_view = "💬 Customer Dashboard"
        if "selected_restaurant" not in st.session_state or st.session_state.selected_restaurant is None:
            st.session_state.selected_restaurant = "Restaurant_A"



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
            
            # Ensure active_view is initialized
            if "active_view" not in st.session_state or st.session_state.active_view is None:
                init_landing_view(st.session_state.user.get("role"))
                
            # Restrict context selector value for restaurant staff/managers
            if st.session_state.user.get("role") == "restaurant":
                st.session_state.selected_restaurant = st.session_state.user.get("restaurant_id")
                
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

def has_permission(permission: str) -> bool:
    """
    Checks if the currently logged-in user has the required permission scope.
    """
    if not st.session_state.get("is_authenticated", False) or not st.session_state.get("user"):
        return False
    user_role = st.session_state.user.get("role")
    from backend.core.permissions import has_permission as backend_has_permission
    return backend_has_permission(user_role, permission)

def has_role(role: str) -> bool:
    """
    Checks if the currently logged-in user matches the required role.
    """
    if not st.session_state.get("is_authenticated", False) or not st.session_state.get("user"):
        return False
    user_role = st.session_state.user.get("role")
    from backend.core.permissions import has_role as backend_has_role
    return backend_has_role(user_role, role)

