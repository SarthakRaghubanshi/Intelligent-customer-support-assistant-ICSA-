import os
import shutil
import time
from playwright.sync_api import sync_playwright

def main():
    dest_dir = "/Users/sarthakraghubanshi/.gemini/antigravity-ide/brain/8a1ca73a-0b73-4b34-990a-3c64b3fe7586"
    
    # 1. Copy already captured screenshots to standard names
    src_login = os.path.join(dest_dir, "login_screen_1782324399265.png")
    src_admin = os.path.join(dest_dir, "admin_dashboard_1782324432229.png")
    src_cust = os.path.join(dest_dir, "customer_dashboard_1782324504154.png")
    src_rest = os.path.join(dest_dir, "restaurant_dashboard_1782324584915.png")

    if os.path.exists(src_login):
        shutil.copy(src_login, os.path.join(dest_dir, "login_screen.png"))
        print("Copied login screen screenshot.")
    if os.path.exists(src_admin):
        shutil.copy(src_admin, os.path.join(dest_dir, "admin_dashboard.png"))
        print("Copied admin dashboard screenshot.")
    if os.path.exists(src_cust):
        shutil.copy(src_cust, os.path.join(dest_dir, "customer_dashboard.png"))
        print("Copied customer dashboard screenshot.")
    if os.path.exists(src_rest):
        shutil.copy(src_rest, os.path.join(dest_dir, "restaurant_dashboard.png"))
        print("Copied restaurant dashboard screenshot.")

    # 2. Use Playwright to capture the remaining screens (Registration and Manager Onboarding Controls)
    print("Launching playwright...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            # Go to home
            print("Navigating to http://localhost:8501")
            page.goto("http://localhost:8501")
            # Wait for content to load
            page.wait_for_timeout(3000)
            
            # Click on 'Register' tab. In streamlit, tabs are represented as buttons with role='tab' or text
            register_tab = page.locator("button[role='tab']:has-text('Create Account')")
            if register_tab.count() > 0:
                print("Clicking 'Register' tab...")
                register_tab.click()
                page.wait_for_timeout(2000)
                
                # Take registration_screen.png
                reg_path = os.path.join(dest_dir, "registration_screen.png")
                page.screenshot(path=reg_path)
                print(f"Captured registration screen to {reg_path}")
                
                # Select role "Restaurant Manager"
                role_select = page.locator("div[data-testid='stSelectbox']").first
                if role_select.count() > 0:
                    print("Clicking selectbox for account role...")
                    role_select.click()
                    page.wait_for_timeout(1000)
                    # Dump page content to a file for DOM inspection
                    with open(os.path.join(dest_dir, "dom_dump.html"), "w") as f:
                        f.write(page.content())
                    print("Dumped DOM to dom_dump.html for inspection.")
                    
                    # Click option "Restaurant Manager"
                    option = page.locator("li[role='option']:has-text('Restaurant Manager')").first
                    if option.count() > 0:
                        option.click()
                        print("Selected 'Restaurant Manager' role.")
                        page.wait_for_timeout(2000)
                        
                        # Take manager_onboarding_controls.png
                        ctrl_path = os.path.join(dest_dir, "manager_onboarding_controls.png")
                        page.screenshot(path=ctrl_path)
                        print(f"Captured manager onboarding controls to {ctrl_path}")
                    else:
                        print("Option 'Restaurant Manager' not found.")
                else:
                    print("Selectbox not found.")
            else:
                print("Register tab not found.")
                
            browser.close()
    except Exception as e:
        print(f"Error during playwright execution: {e}")

if __name__ == "__main__":
    main()
