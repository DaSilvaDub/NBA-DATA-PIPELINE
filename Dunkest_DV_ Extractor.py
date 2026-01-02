import os
import json
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

# === CONFIG ===
SAVE_PATH = r"C:\Users\dasil\My Drive (dasilvadub@gmail.com)\NBA\MATCHUP\DVP DUNKEST"
URL = "https://www.dunkest.com/en/nba/stats/teams/defense-vs-position/regular-season/2025-2026"
POSITIONS = {
    "Guard": "1",
    "Forward": "2",
    "Center": "3"
}
STATS = {
    "Points": "4",
    "Rebounds": "5",
    "Assists": "6",
    "3PT Made": "7"
}

# === SETUP SELENIUM ===
options = Options()
options.add_argument("--headless")
options.add_argument("--disable-blink-features=AutomationControlled")
driver = webdriver.Chrome(options=options)
driver.get(URL)

# Wait for the page to fully load
wait = WebDriverWait(driver, 15)
print("Waiting for page to load...")

try:
    # Wait for stats dropdown to be present
    stats_dropdown = wait.until(EC.presence_of_element_located((By.ID, "statsSelect")))
    print("Stats dropdown found!")
except Exception as e:
    print(f"Error: Could not find stats dropdown. Page may have changed.")
    print(f"Trying to find all select elements on the page...")

    selects = driver.find_elements(By.TAG_NAME, "select")
    print(f"Found {len(selects)} select elements:")
    for i, select in enumerate(selects):
        select_id = select.get_attribute("id")
        select_name = select.get_attribute("name")
        select_class = select.get_attribute("class")
        print(f"  {i+1}. ID: {select_id}, Name: {select_name}, Class: {select_class}")

    driver.quit()
    exit(1)

# === SCRAPE LOOP ===
all_data = {}

for pos_name, pos_id in POSITIONS.items():
    all_data[pos_name] = {}
    for stat_name, stat_id in STATS.items():
        print(f"\nScraping {pos_name} - {stat_name}...")

        try:
            # Select stat using JavaScript and trigger change event
            driver.execute_script(f"""
                var statsSelect = document.getElementById('statsSelect');
                statsSelect.value = '{stat_id}';
                $('#statsSelect').selectpicker('refresh');
                $('#statsSelect').trigger('change');
            """)
            time.sleep(2)

            # Select position using JavaScript and trigger change event
            driver.execute_script(f"""
                var positionSelect = document.getElementById('positionSelect');
                positionSelect.value = '{pos_id}';
                $('#positionSelect').selectpicker('refresh');
                $('#positionSelect').trigger('change');
            """)
            time.sleep(3)

            # Wait for table to update
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr")))

            # Extract table
            rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
            data = []
            for row in rows:
                cols = row.find_elements(By.TAG_NAME, "td")
                if cols and len(cols) >= 5:
                    data.append({
                        "team": cols[0].text.strip(),
                        "last_3": cols[1].text.strip(),
                        "last_5": cols[2].text.strip(),
                        "last_10": cols[3].text.strip(),
                        "season_avg": cols[4].text.strip()
                    })

            all_data[pos_name][stat_name] = data
            print(f"[OK] Scraped {len(data)} rows")

        except Exception as e:
            print(f"[ERROR] Scraping {pos_name} - {stat_name}: {str(e)}")
            all_data[pos_name][stat_name] = []

# Save all data to a single JSON file
output_file = os.path.join(SAVE_PATH, "Dunkest_DVP_All_Stats.json")
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(all_data, f, indent=2)

print(f"\n=== Scraping Complete ===")
print(f"[OK] All data saved to: {output_file}")
driver.quit()
