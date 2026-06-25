import os
import sys
import time
from playwright.sync_api import sync_playwright

dest_dir = "/Users/sarthakraghubanshi/.gemini/antigravity-ide/brain/8a1ca73a-0b73-4b34-990a-3c64b3fe7586"

def run_debug():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("http://localhost:8501")
        page.wait_for_timeout(3000)
        
        # Click Register tab
        page.locator("button[role='tab']:has-text('Create Account')").first.click()
        page.wait_for_timeout(2000)
        
        # Fill fields
        page.locator("input[aria-label='Email Address']").nth(1).fill("customer_uat@saas.com")
        page.locator("input[aria-label='Password (minimum 8 characters)']").fill("password123")
        page.locator("input[aria-label='Confirm Password']").fill("password123")
        
        # Save screenshot before submit
        page.screenshot(path=os.path.join(dest_dir, "debug_before_submit.png"))
        
        # Click Submit
        page.locator("button[data-testid='stBaseButton-secondaryFormSubmit']:has-text('Create Account')").first.click()
        page.wait_for_timeout(4000)
        
        # Save screenshot after submit
        page.screenshot(path=os.path.join(dest_dir, "debug_after_submit.png"))
        browser.close()

if __name__ == "__main__":
    run_debug()
