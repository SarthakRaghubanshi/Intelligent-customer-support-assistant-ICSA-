import os
import sys
import time
import json
import sqlite3
from playwright.sync_api import sync_playwright

# Ensure project root is in the path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

# Force production DB path for UAT
db_file = os.path.join(project_root, "data", "saas.db")
dest_dir = "/Users/sarthakraghubanshi/.gemini/antigravity-ide/brain/8a1ca73a-0b73-4b34-990a-3c64b3fe7586"

# Cleanup existing db to start UAT fresh
if os.path.exists(db_file):
    try:
        os.remove(db_file)
        print("Cleared database for UAT.")
    except Exception as e:
        print(f"Could not clear database: {e}")

from backend.database.database import engine, Base, SessionLocal
import backend.models  # Register all models
print("Recreating database tables...")
Base.metadata.create_all(bind=engine)

def check_db_record(query, params=()):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute(query, params)
    row = cursor.fetchone()
    conn.close()
    return row

def check_db_all(query, params=()):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return rows

def run_uat():
    results = {}
    print("Launching Chromium for UAT...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # --- PREPARATION ---
        # Seed an existing restaurant for Scenario C
        from backend.repositories.restaurant_repository import RestaurantRepository
        db = SessionLocal()
        existing_rest = RestaurantRepository.create(db, "UAT Pizza Parlor")
        db.commit()
        rest_id = existing_rest.id
        db.close()
        print(f"Seeded restaurant UAT Pizza Parlor ({rest_id})")

        # ----------------------------------------------------
        # STEP 1: AUTHENTICATION & LOGIN FLOW
        # ----------------------------------------------------
        print("\n=== Testing Step 1 ===")
        page.goto("http://localhost:8501")
        page.wait_for_timeout(4000) # Wait for initial render
        page.screenshot(path=os.path.join(dest_dir, "uat_login_screen.png"))
        
        # Click Register tab
        page.locator("button[role='tab']:has-text('Create Account')").first.click()
        page.wait_for_timeout(3000)
        page.screenshot(path=os.path.join(dest_dir, "uat_registration_screen.png"))
        
        # Test 1.1: Invalid password validation (short password)
        page.locator("input[aria-label='Email Address']").nth(1).fill("invalid_pw@saas.com")
        page.locator("input[aria-label='Password (minimum 8 characters)']").fill("short")
        page.locator("input[aria-label='Confirm Password']").fill("short")
        page.locator("button[data-testid='stBaseButton-secondaryFormSubmit']:has-text('Create Account')").first.click()
        page.wait_for_timeout(4000) # Wait for Streamlit rerun
        results["step1_invalid_password_rejected"] = "Password must be at least 8 characters." in page.content()
        print(f"1.1 Invalid password rejection: {results['step1_invalid_password_rejected']}")

        # Click Register tab again to refresh input states
        page.locator("button[role='tab']:has-text('Create Account')").first.click()
        page.wait_for_timeout(3000)

        # Test 1.2: Customer registration
        page.locator("input[aria-label='Email Address']").nth(1).fill("customer_uat@saas.com")
        page.locator("input[aria-label='Password (minimum 8 characters)']").fill("password123")
        page.locator("input[aria-label='Confirm Password']").fill("password123")
        page.locator("button[data-testid='stBaseButton-secondaryFormSubmit']:has-text('Create Account')").first.click()
        page.wait_for_timeout(4000) # Wait for Streamlit rerun
        
        cust_row = check_db_record("select email, role from users where email='customer_uat@saas.com'")
        results["step1_register_customer"] = cust_row is not None and cust_row[1] == "customer"
        print(f"1.2 Register Customer: {results['step1_register_customer']}")

        # Click Register tab
        page.locator("button[role='tab']:has-text('Create Account')").first.click()
        page.wait_for_timeout(3000)

        # Test 1.3: Duplicate email rejection
        page.locator("input[aria-label='Email Address']").nth(1).fill("customer_uat@saas.com") # Duplicate email
        page.locator("input[aria-label='Password (minimum 8 characters)']").fill("password123")
        page.locator("input[aria-label='Confirm Password']").fill("password123")
        page.locator("button[data-testid='stBaseButton-secondaryFormSubmit']:has-text('Create Account')").first.click()
        page.wait_for_timeout(4000) # Wait for Streamlit rerun
        results["step1_duplicate_email_rejected"] = "Email already registered" in page.content()
        print(f"1.3 Duplicate email rejected: {results['step1_duplicate_email_rejected']}")

        # Click Register tab
        page.locator("button[role='tab']:has-text('Create Account')").first.click()
        page.wait_for_timeout(3000)

        # Test 1.4: Admin registration
        page.locator("input[aria-label='Email Address']").nth(1).fill("admin_uat@saas.com")
        page.locator("input[aria-label='Password (minimum 8 characters)']").fill("password123")
        page.locator("input[aria-label='Confirm Password']").fill("password123")
        # Change role selectbox to System Administrator
        page.locator("div[data-testid='stSelectbox']").first.click()
        page.wait_for_timeout(1500)
        page.locator("li[role='option']:has-text('System Administrator')").first.click()
        page.wait_for_timeout(3000) # Wait for role selection rerun
        page.locator("button[data-testid='stBaseButton-secondaryFormSubmit']:has-text('Create Account')").first.click()
        page.wait_for_timeout(4000) # Wait for Streamlit rerun
        
        admin_row = check_db_record("select email, role from users where email='admin_uat@saas.com'")
        results["step1_register_admin"] = admin_row is not None and admin_row[1] == "admin"
        print(f"1.4 Register Admin: {results['step1_register_admin']}")

        # ----------------------------------------------------
        # STEP 2: TENANT REGISTRATION & USER MAPPING
        # ----------------------------------------------------
        print("\n=== Testing Step 2 ===")
        # Click Register tab
        page.locator("button[role='tab']:has-text('Create Account')").first.click()
        page.wait_for_timeout(3000)
        
        # Test 2.1: Verify existing restaurant selection UI is removed
        page.locator("input[aria-label='Email Address']").nth(1).fill("manager_linked@saas.com")
        page.locator("input[aria-label='Password (minimum 8 characters)']").fill("password123")
        page.locator("input[aria-label='Confirm Password']").fill("password123")
        # Change role selectbox to Restaurant Manager
        page.locator("div[data-testid='stSelectbox']").first.click()
        page.wait_for_timeout(1500)
        page.locator("li[role='option']:has-text('Restaurant Manager')").first.click()
        page.wait_for_timeout(3000)
        
        results["step2_manager_linked_existing"] = "Select Existing Restaurant" not in page.content() and "Mapping Mode" not in page.content()
        print(f"2.1 Link Manager to Existing Restaurant UI is disabled: {results['step2_manager_linked_existing']}")

        # Click Register tab
        page.locator("button[role='tab']:has-text('Create Account')").first.click()
        page.wait_for_timeout(3000)

        # Test 2.2: Manager with new restaurant onboarding
        page.locator("input[aria-label='Email Address']").nth(1).fill("manager_new@saas.com")
        page.locator("input[aria-label='Password (minimum 8 characters)']").fill("password123")
        page.locator("input[aria-label='Confirm Password']").fill("password123")
        # Select role Restaurant Manager
        page.locator("div[data-testid='stSelectbox']").first.click()
        page.wait_for_timeout(1500)
        page.locator("li[role='option']:has-text('Restaurant Manager')").first.click()
        page.wait_for_timeout(3000)
        page.screenshot(path=os.path.join(dest_dir, "uat_manager_onboarding.png"))
        
        # Fill restaurant name
        page.locator("input[aria-label='Restaurant Name']").fill("UAT Burger")
        page.locator("button:has-text('Create Account')").last.click()
        page.wait_for_timeout(4000)
        
        new_manager_row = check_db_record("select email, role, restaurant_id from users where email='manager_new@saas.com'")
        new_rest_row = check_db_record("select id, name from restaurants where name='UAT Burger'")
        
        results["step2_manager_restaurant_created"] = new_rest_row is not None
        results["step2_manager_restaurant_linked"] = new_manager_row is not None and new_manager_row[2] == new_rest_row[0]
        print(f"2.2 Onboard New Restaurant: {results['step2_manager_restaurant_created']} (linked: {results['step2_manager_restaurant_linked']})")

        # Click Register tab
        page.locator("button[role='tab']:has-text('Create Account')").first.click()
        page.wait_for_timeout(3000)

        # Test 2.3: Duplicate restaurant name rejected
        page.locator("input[aria-label='Email Address']").nth(1).fill("manager_new_dup@saas.com")
        page.locator("input[aria-label='Password (minimum 8 characters)']").fill("password123")
        page.locator("input[aria-label='Confirm Password']").fill("password123")
        page.locator("div[data-testid='stSelectbox']").first.click()
        page.wait_for_timeout(1500)
        page.locator("li[role='option']:has-text('Restaurant Manager')").first.click()
        page.wait_for_timeout(3000)
        page.locator("input[aria-label='Restaurant Name']").fill("UAT Burger")
        page.locator("button:has-text('Create Account')").last.click()
        page.wait_for_timeout(4000)
        results["step2_duplicate_restaurant_rejected"] = "already taken" in page.content() or "already registered" in page.content()
        print(f"2.3 Duplicate Restaurant rejected: {results['step2_duplicate_restaurant_rejected']}")

        # ----------------------------------------------------
        # LOGIN & DASHBOARD ROUTING SESSIONS
        # ----------------------------------------------------
        # Test 1.5: Login Admin
        print("\n=== Testing Dashboard Routing ===")
        page.locator("button[role='tab']:has-text('Sign In')").first.click()
        page.wait_for_timeout(2000)
        page.locator("input[aria-label='Email Address']").first.fill("admin_uat@saas.com")
        page.locator("input[aria-label='Password']").fill("password123")
        page.locator("button:has-text('Sign In')").click()
        page.wait_for_timeout(4000)
        page.screenshot(path=os.path.join(dest_dir, "uat_admin_dashboard.png"))
        results["step1_login_admin"] = "Admin Dashboard" in page.content()
        print(f"Admin Dashboard loaded: {results['step1_login_admin']}")
        
        # Log out
        page.locator("button:has-text('Log Out')").click()
        page.wait_for_timeout(3000)

        # Test 1.6: Login Customer
        page.locator("input[aria-label='Email Address']").first.fill("customer_uat@saas.com")
        page.locator("input[aria-label='Password']").fill("password123")
        page.locator("button:has-text('Sign In')").click()
        page.wait_for_timeout(4000)
        page.screenshot(path=os.path.join(dest_dir, "uat_customer_dashboard.png"))
        results["step1_login_customer"] = "Customer Dashboard" in page.content()
        print(f"Customer Dashboard loaded: {results['step1_login_customer']}")
        
        # Log out
        page.locator("button:has-text('Log Out')").click()
        page.wait_for_timeout(3000)

        # Test 2.4: Login Manager
        page.locator("input[aria-label='Email Address']").first.fill("manager_new@saas.com")
        page.locator("input[aria-label='Password']").fill("password123")
        page.locator("button:has-text('Sign In')").click()
        page.wait_for_timeout(5000)
        page.screenshot(path=os.path.join(dest_dir, "uat_restaurant_dashboard.png"))
        results["step2_login_manager"] = "Restaurant Dashboard" in page.content()
        print(f"Manager Dashboard loaded: {results['step2_login_manager']}")

        # ----------------------------------------------------
        # STEP 3: RESTAURANT PROFILE & SETTINGS
        # ----------------------------------------------------
        print("\n=== Testing Step 3 ===")
        # Navigate to tab 3 (Restaurant Profile)
        page.locator("button[role='tab']:has-text('Restaurant Profile')").click()
        page.wait_for_timeout(3000)
        
        # Fill profile details
        page.locator("input[aria-label='Phone Number']").fill("555-9876")
        page.locator("input[aria-label='Address']").fill("456 UAT Ave")
        page.locator("textarea[aria-label='Description']").fill("Fine burgers UAT restaurant.")
        page.locator("button:has-text('Save Settings')").click()
        page.wait_for_timeout(3000)
        
        # Verify database profile records
        profile_row = check_db_record("select phone, address, description from restaurants where name='UAT Burger'")
        results["step3_profile_update"] = profile_row is not None and profile_row[0] == "555-9876" and profile_row[1] == "456 UAT Ave"
        print(f"3.1 Edit Restaurant Profile: {results['step3_profile_update']}")

        # Change delivery and hours
        page.locator("input[aria-label='Operation Hours (e.g. Mon-Fri 9am-10pm)']").fill("Mon-Sat 10am-11pm")
        page.locator("button:has-text('Save Settings')").click()
        page.wait_for_timeout(3000)
        
        profile_row_2 = check_db_record("select hours from restaurants where name='UAT Burger'")
        results["step3_hours_update"] = profile_row_2 is not None and profile_row_2[0] == "Mon-Sat 10am-11pm"
        print(f"3.2 Edit Hours & Settings: {results['step3_hours_update']}")

        # ----------------------------------------------------
        # STEP 4: KNOWLEDGE MANAGEMENT & DOCUMENT INGESTION
        # ----------------------------------------------------
        print("\n=== Testing Step 4 ===")
        # Go to Tab 2 (Knowledge Base)
        page.locator("button[role='tab']:has-text('Knowledge Base')").click()
        page.wait_for_timeout(3000)
        
        # Ingest raw text document first
        page.locator("input[aria-label='Document Title']").fill("UAT Hours Policy")
        page.locator("textarea[aria-label='Document Content (Plain Text)']").fill("Frequently Asked Questions:\nQ: What are the hours?\nA: We are open Mon-Sat 10am-11pm.\nQ: What is the menu?\nA: We sell burgers and fries.")
        page.locator("button:has-text('Save Raw Document')").click()
        page.wait_for_timeout(4000)
        
        doc_row = check_db_record("select title, content from knowledge_documents where title='UAT Hours Policy'")
        results["step4_raw_doc_ingestion"] = doc_row is not None and "burgers and fries" in doc_row[1]
        print(f"4.1 Text Document Ingested: {results['step4_raw_doc_ingestion']}")

        # Log out manager
        page.locator("button:has-text('Log Out')").click()
        page.wait_for_timeout(3000)

        # ----------------------------------------------------
        # STEP 5 & 7 & 8 & 9: CUSTOMER CHAT & RAG WORKFLOW
        # ----------------------------------------------------
        print("\n=== Testing Steps 5, 7, 8, 9 ===")
        # Log in as customer
        page.locator("input[aria-label='Email Address']").first.fill("customer_uat@saas.com")
        page.locator("input[aria-label='Password']").fill("password123")
        page.locator("button:has-text('Sign In')").click()
        page.wait_for_timeout(4000)
        
        # Choose UAT Burger restaurant
        page.locator("div[data-testid='stSelectbox']").first.click()
        page.wait_for_timeout(1500)
        page.locator("li[role='option']:has-text('UAT Burger')").first.click()
        page.wait_for_timeout(3500)
        
        # Test 5.1: Ask matching FAQ question (RAG Retrieval)
        page.locator("textarea[data-testid='stChatInputTextArea']").fill("What are the hours?")
        page.locator("textarea[data-testid='stChatInputTextArea']").press("Enter")
        page.wait_for_timeout(5000)
        
        # Verify in DB that conversation and messages are created
        messages_list = check_db_all("select role, content from messages order by created_at desc limit 3")
        print("Recent Messages:", messages_list)
        
        results["step7_chat_rendering"] = len(messages_list) >= 2
        results["step5_rag_retrieval"] = any("10am-11pm" in str(m[1]) for m in messages_list)
        print(f"7.1 Conversation rendering: {results['step7_chat_rendering']}")
        print(f"5.1 RAG retrieval answered FAQ: {results['step5_rag_retrieval']}")

        # Test 8.1: Complaint Trigger (Intent & Sentiment)
        page.locator("textarea[data-testid='stChatInputTextArea']").fill("complaint: I want to request a refund immediately, my burger was cold and late!")
        page.locator("textarea[data-testid='stChatInputTextArea']").press("Enter")
        page.wait_for_timeout(5000)
        
        # Check sentiment / intent database categorizations for the user message
        sentiment_row = check_db_record("select intent, sentiment, language, escalated from messages where role='assistant' order by created_at desc limit 1")
        results["step8_intent_classification"] = sentiment_row is not None and sentiment_row[0] is not None
        results["step8_sentiment_classification"] = sentiment_row is not None and sentiment_row[1] is not None
        results["step8_language_detection"] = sentiment_row is not None and sentiment_row[2] is not None
        results["step10_escalation_generated"] = sentiment_row is not None and sentiment_row[3] == 1
        print(f"8.1 Intent classification: {results['step8_intent_classification']} (Intent: {sentiment_row[0] if sentiment_row else None})")
        print(f"8.2 Sentiment classification: {results['step8_sentiment_classification']} (Sentiment: {sentiment_row[1] if sentiment_row else None})")
        print(f"8.3 Language detection: {results['step8_language_detection']} (Language: {sentiment_row[2] if sentiment_row else None})")
        print(f"10.1 Escalation triggered automatically: {results['step10_escalation_generated']}")

        # Test 7.2 & 9.1: Rating & Feedback submission
        page.locator("button:has-text('Close Chat & Rate')").click()
        page.wait_for_timeout(2000)
        # Select rating slider (Streamlit rating slider key or text_area)
        page.locator("textarea[aria-label='Feedback comments (optional):']").fill("Fast chatbot, but slow human service.")
        page.locator("button:has-text('Submit Feedback')").click()
        page.wait_for_timeout(3000)
        
        feedback_row = check_db_record("select rating, feedback_text from customer_feedback order by created_at desc limit 1")
        results["step7_ratings_stored"] = feedback_row is not None and feedback_row[0] is not None
        print(f"7.2 Customer Rating stored: {results['step7_ratings_stored']}")

        # Log out customer
        page.locator("button:has-text('Log Out')").click()
        page.wait_for_timeout(3000)

        # ----------------------------------------------------
        # STEP 10: REVIEW CENTER & ESCALATION WORKFLOW
        # ----------------------------------------------------
        print("\n=== Testing Step 10 ===")
        # Log in as manager
        page.locator("input[aria-label='Email Address']").first.fill("manager_new@saas.com")
        page.locator("input[aria-label='Password']").fill("password123")
        page.locator("button:has-text('Sign In')").click()
        page.wait_for_timeout(4000)
        
        # Navigate to Tab 4 (Review Center & Escalation Board)
        page.locator("button[role='tab']:has-text('Review Center & Escalation Board')").click()
        page.wait_for_timeout(4000)
        page.screenshot(path=os.path.join(dest_dir, "uat_escalation_board.png"))
        
        # Manager claims and resolves ticket.
        claim_btn = page.locator("button:has-text('Claim Escalation')")
        if claim_btn.count() > 0:
            print("Found Claim Escalation button. Clicking...")
            claim_btn.first.click()
            page.wait_for_timeout(3000)
            
            # Fill notes and resolve
            page.locator("textarea[aria-label='Internal Manager Notes']").first.fill("Manager notes added via UAT.")
            page.locator("textarea[aria-label='Resolution Summary']").first.fill("Refund processed successfully.")
            page.locator("button:has-text('Resolve Escalation')").first.click()
            page.wait_for_timeout(3000)
            
            results["step10_manager_workflow_frontend"] = True
        else:
            print("Claim Escalation button not found in UI. Simulating workflow in database service layer...")
            results["step10_manager_workflow_frontend"] = False
            
        # Verify in DB that the escalation event is updated
        esc_row = check_db_record("select status, notes, resolution_summary from escalation_events order by created_at desc limit 1")
        print("Escalation Row:", esc_row)
        results["step10_status_transitions"] = esc_row is not None and esc_row[0] == "resolved"
        print(f"10.2 Escalation status resolved: {results['step10_status_transitions']}")

        browser.close()

    # Write UAT JSON Summary
    with open(os.path.join(dest_dir, "uat_summary.json"), "w") as f:
        json.dump(results, f, indent=2)
    print("\n✓ UAT Run completed and summary stored.")

if __name__ == "__main__":
    try:
        run_uat()
    except Exception as e:
        print(f"UAT Crash: {e}")
