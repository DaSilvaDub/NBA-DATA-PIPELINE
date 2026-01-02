import os
import json
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import load_dotenv

def scrape_outlier_insights():
    # Load environment variables
    load_dotenv()

    # 1. Setup Path and Folders
    target_dir = r"C:\Users\dasil\My Drive (dasilvadub@gmail.com)\NBA\MATCHUP\Outlier_insight"
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)

    file_path = os.path.join(target_dir, "nba_insights.json")

    # 2. Configure Selenium
    chrome_options = Options()
    headless = os.getenv('HEADLESS_MODE', 'false').lower() == 'true'
    if headless:
        chrome_options.add_argument("--headless")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    driver.maximize_window()

    try:
        # 3. Login to Outlier.bet
        print("Navigating to Outlier.bet login page...")
        driver.get("https://app.outlier.bet/login")

        # Wait for login page to load
        wait = WebDriverWait(driver, 10)

        # Enter credentials
        email = os.getenv('OUTLIER_EMAIL')
        password = os.getenv('OUTLIER_PASSWORD')

        print(f"Logging in as {email}...")

        # Save initial page for debugging
        with open(os.path.join(target_dir, "login_page_1.html"), 'w', encoding='utf-8') as f:
            f.write(driver.page_source)

        # Find and fill email field
        email_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email'], input[name='email'], input")))
        email_input.clear()
        email_input.send_keys(email)
        time.sleep(1)

        # Try to find the continue button - look for any button on the page
        print("Looking for continue button...")
        try:
            # Try different button selectors
            buttons = driver.find_elements(By.TAG_NAME, "button")
            print(f"Found {len(buttons)} buttons on page")

            continue_button = None
            for btn in buttons:
                btn_text = btn.text.lower()
                print(f"Button text: '{btn_text}'")
                if 'continue' in btn_text or 'email' in btn_text or 'next' in btn_text or btn_text == '':
                    continue_button = btn
                    break

            if continue_button:
                print(f"Clicking button: {continue_button.text}")
                continue_button.click()
                time.sleep(3)
            else:
                # If no continue button, password might already be visible
                print("No continue button found, checking for password field...")
        except Exception as e:
            print(f"Error finding continue button: {e}")

        # Save page after clicking
        with open(os.path.join(target_dir, "login_page_2.html"), 'w', encoding='utf-8') as f:
            f.write(driver.page_source)

        # Look for password field
        print("Looking for password field...")
        try:
            password_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='password']")))
            print("Found password field, entering password...")
            password_input.send_keys(password)
            time.sleep(1)

            # Look for submit button
            print("Looking for submit button...")
            buttons = driver.find_elements(By.TAG_NAME, "button")
            for btn in buttons:
                btn_text = btn.text.lower()
                if 'log' in btn_text or 'sign' in btn_text or 'submit' in btn_text or btn.get_attribute('type') == 'submit':
                    print(f"Clicking submit button: {btn.text}")
                    btn.click()
                    break

            print("Waiting for login to complete...")
            time.sleep(5)

        except Exception as e:
            print(f"Error during password entry: {e}")
            print("Trying alternative: directly navigating to insights page (may already be logged in)...")
            # Save error page
            with open(os.path.join(target_dir, "login_error.html"), 'w', encoding='utf-8') as f:
                f.write(driver.page_source)

        # 4. Navigate to insights page (all teams - no filter)
        print("Navigating to insights page...")
        insights_url = "https://app.outlier.bet/NBA/trending/insights"
        driver.get(insights_url)

        # Wait for page to load
        time.sleep(3)
        print("Page loaded. Starting scroll...")

        # 5. Handle Dynamic Scrolling
        scroll_delay = float(os.getenv('SCROLL_DELAY', '1.5'))
        last_height = driver.execute_script("return document.body.scrollHeight")
        scroll_count = 0
        max_scrolls = 20  # Limit to prevent infinite scrolling

        while scroll_count < max_scrolls:
            # Scroll down to bottom
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(scroll_delay)

            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                print(f"Reached end of page after {scroll_count} scrolls")
                break

            last_height = new_height
            scroll_count += 1

            # Check how many insights we've loaded so far
            insights_count = len(driver.find_elements(By.XPATH, "//div[contains(@class, 'insight') or contains(@class, 'card') or contains(@class, 'item')]"))
            print(f"Scroll {scroll_count}: Found {insights_count} potential insight elements")

        # Wait a bit more to ensure all content is loaded
        time.sleep(2)
        print("Scrolling complete. Parsing insights...")

        # 6. Extract insights data
        insights_data = []

        try:
            # Try to find insight cards - adjust selectors based on actual DOM structure
            # Looking for common patterns in betting insight sites

            # Strategy 1: Look for specific insight containers
            insight_containers = driver.find_elements(By.XPATH,
                "//div[contains(@class, 'insight')] | " +
                "//div[contains(@class, 'card')] | " +
                "//div[contains(@class, 'trend')] | " +
                "//article | " +
                "//li[contains(@class, 'item')]"
            )

            print(f"Found {len(insight_containers)} potential insight containers")

            for container in insight_containers:
                try:
                    text = container.text.strip()

                    # Filter for NBA-related insights with meaningful content
                    if len(text) > 30 and any(keyword in text.lower() for keyword in
                        ['pts', 'points', 'reb', 'rebounds', 'ast', 'assists', 'over', 'under',
                         'exceeded', 'hit', 'line', 'vs', '@', 'game', 'streak', 'last']):

                        # Try to extract link if available
                        url = None
                        try:
                            link_element = container.find_element(By.TAG_NAME, 'a')
                            url = link_element.get_attribute('href')
                        except:
                            pass

                        insight_obj = {
                            "content": text,
                            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                        }

                        if url:
                            insight_obj["url"] = url

                        insights_data.append(insight_obj)

                except Exception as e:
                    continue

            # Remove duplicates based on content
            seen = set()
            unique_insights = []
            for insight in insights_data:
                content_key = insight["content"][:100]  # Use first 100 chars as key
                if content_key not in seen:
                    seen.add(content_key)
                    unique_insights.append(insight)

            insights_data = unique_insights

            print(f"Extracted {len(insights_data)} unique insights")

            # If we still don't have insights, save page source for debugging
            if len(insights_data) == 0:
                print("No insights found. Saving page source for debugging...")
                debug_path = os.path.join(target_dir, "page_source_debug.html")
                with open(debug_path, 'w', encoding='utf-8') as f:
                    f.write(driver.page_source)
                print(f"Page source saved to {debug_path}")
                print("Please check if you need to manually login or if the site structure has changed.")

        except Exception as e:
            print(f"Error during parsing: {str(e)}")
            # Save page source for debugging
            debug_path = os.path.join(target_dir, "page_source_debug.html")
            with open(debug_path, 'w', encoding='utf-8') as f:
                f.write(driver.page_source)
            print(f"Saved page source to {debug_path} for debugging")

        # 7. Save to JSON
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(insights_data, f, indent=4, ensure_ascii=False)

        print(f"Successfully saved {len(insights_data)} insights to {file_path}")

    except Exception as e:
        print(f"Error occurred: {str(e)}")
        # Save screenshot for debugging
        try:
            screenshot_path = os.path.join(target_dir, "error_screenshot.png")
            driver.save_screenshot(screenshot_path)
            print(f"Screenshot saved to {screenshot_path}")
        except:
            pass
        raise

    finally:
        driver.quit()

if __name__ == "__main__":
    scrape_outlier_insights()
