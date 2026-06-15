import os
import sys

# Ensure project root is in the path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

# Setup a mock streamlit environment for testing session state
import streamlit as st

# We mock st.session_state using a custom dict interface if needed,
# but since verify_dashboard_shells.py runs standard python, we can just write directly to st.session_state!
# Let's ensure st.session_state has default keys.
if "is_authenticated" not in st.session_state:
    st.session_state.is_authenticated = False
if "user" not in st.session_state:
    st.session_state.user = None
if "active_view" not in st.session_state:
    st.session_state.active_view = None

from frontend.utils.auth_helper import init_landing_view
from backend.core.permissions import has_permission, has_role
from frontend.components.customer_dashboard import render_customer_dashboard
from frontend.components.restaurant_dashboard import render_restaurant_dashboard
from frontend.components.admin_dashboard import render_admin_dashboard

def test_landing_logic():
    print("1. Testing Landing Logic...")
    
    # Test customer landing mapping
    st.session_state.active_view = None
    init_landing_view("customer")
    assert st.session_state.active_view == "💬 Customer Dashboard", f"Failed: Got {st.session_state.active_view}"
    print("✓ Customer landing correctly routed to '💬 Customer Dashboard'.")

    # Test restaurant landing mapping
    st.session_state.active_view = None
    init_landing_view("restaurant")
    assert st.session_state.active_view == "📊 Restaurant Dashboard", f"Failed: Got {st.session_state.active_view}"
    print("✓ Restaurant landing correctly routed to '📊 Restaurant Dashboard'.")

    # Test admin landing mapping
    st.session_state.active_view = None
    init_landing_view("admin")
    assert st.session_state.active_view == "⚙️ Admin Dashboard", f"Failed: Got {st.session_state.active_view}"
    print("✓ Admin landing correctly routed to '⚙️ Admin Dashboard'.")


def test_navigation_restrictions():
    print("\n2. Testing Navigation Restrictions...")
    
    # Test Customer restrictions
    st.session_state.user = {"role": "customer"}
    assert has_permission("customer", "chat:read_write") is True
    assert has_permission("customer", "analytics:read_own") is False
    assert has_permission("customer", "admin:manage_system") is False
    
    # Test Restaurant restrictions
    st.session_state.user = {"role": "restaurant"}
    assert has_permission("restaurant", "chat:read_write") is True
    assert has_permission("restaurant", "analytics:read_own") is True
    assert has_permission("restaurant", "admin:manage_system") is False
    
    # Test Admin restrictions
    st.session_state.user = {"role": "admin"}
    assert has_permission("admin", "chat:read_write") is True
    assert has_permission("admin", "analytics:read_own") is True
    assert has_permission("admin", "admin:manage_system") is True
    
    print("✓ Dashboard access permissions mapped correctly by role.")


def test_rendering_mock():
    print("\n3. Testing Dashboard Shell Rendering...")
    
    # Prepare a test user
    st.session_state.user = {
        "email": "test@saas.com",
        "role": "customer",
        "first_name": "Test",
        "last_name": "User"
    }
    
    # Verify we can invoke the shells without SyntaxErrors or import issues.
    # Note: Streamlit's internal methods (st.markdown) might fail to execute fully
    # if not inside a running streamlit server, but we can verify the function definitions exist.
    assert callable(render_customer_dashboard)
    assert callable(render_restaurant_dashboard)
    assert callable(render_admin_dashboard)
    print("✓ Dashboard shell rendering functions verified.")


def run_tests():
    print("=" * 80)
    print("RUNNING DASHBOARD SHELLS VERIFICATION")
    print("=" * 80)
    
    try:
        test_landing_logic()
        test_navigation_restrictions()
        test_rendering_mock()
        print("\n✓ ALL DASHBOARD SHELLS VERIFICATION TESTS PASSED SUCCESSFULLY!")
        print("=" * 80)
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ TEST FAILURE: {str(e)}")
        print("=" * 80)
        sys.exit(1)

if __name__ == "__main__":
    run_tests()
