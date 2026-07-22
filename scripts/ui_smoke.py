"""
Headless UI smoke test using Streamlit's AppTest harness.

Runs frontend/app.py in-process for the unauthenticated state and for each role,
asserting the page renders without raising an exception. Does not send chat
messages, so it makes no Gemini calls.

Run: python -m scripts.ui_smoke
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (_ROOT, os.path.join(_ROOT, "frontend")):
    if p not in sys.path:
        sys.path.insert(0, p)

from streamlit.testing.v1 import AppTest
from backend.database.database import SessionLocal
from backend.services.auth_service import AuthService

APP = os.path.join(_ROOT, "frontend", "app.py")


def token_and_user(email, pw):
    db = SessionLocal()
    try:
        u = AuthService.authenticate_user(db, email, pw)
        tok = AuthService.create_access_token(u.id, u.email, u.role.value)
        user = {"id": u.id, "email": u.email, "role": u.role.value,
                "first_name": u.first_name, "last_name": u.last_name,
                "restaurant_id": u.restaurant_id}
        return tok, user
    finally:
        db.close()


def run_case(label, session):
    at = AppTest.from_file(APP, default_timeout=90)
    for k, v in session.items():
        at.session_state[k] = v
    at.run()
    ok = len(at.exception) == 0
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        for ex in at.exception:
            print("        ", str(ex.value)[:400])
    return ok


def main():
    results = []
    results.append(run_case("Unauthenticated (login page)", {}))
    for email, pw, view in [
        ("customer@icsa.com", "Customer123!", "💬 Customer Dashboard"),
        ("manager.pizza@icsa.com", "Manager123!", "📊 Restaurant Dashboard"),
        ("admin@icsa.com", "AdminPass123!", "⚙️ Admin Dashboard"),
    ]:
        tok, user = token_and_user(email, pw)
        results.append(run_case(f"{view} ({email})", {
            "is_authenticated": True, "access_token": tok, "user": user,
            "active_view": view, "selected_restaurant": user.get("restaurant_id"),
        }))
    print(f"\n{sum(results)}/{len(results)} render checks passed.")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
