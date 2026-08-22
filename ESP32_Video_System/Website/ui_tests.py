from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time
import os

print("Starting comprehensive browser automation...")

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service)

try:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    login_url = f"file:///{current_dir}/login.html"

    # 1. TEST LOGIN
    driver.get(login_url)
    print("1. Opened Login Page...")
    driver.find_element(By.ID, "username").send_keys("general")
    driver.find_element(By.ID, "password").send_keys("1234")
    driver.find_element(By.TAG_NAME, "button").click()
    WebDriverWait(driver, 5).until(EC.url_contains("index.html"))
    print("✅ Logged in successfully!")

    # Wait 2 seconds for the Django API to fetch and render the videos
    time.sleep(2) 

    # 2. TEST CLIPBOARD BUTTON
    driver.find_element(By.XPATH, "//button[contains(text(), 'Copy to Clipboard')]").click()
    WebDriverWait(driver, 5).until(EC.alert_is_present())
    driver.switch_to.alert.accept()
    print("✅ Device ID copy alert handled!")
    time.sleep(1)

    # 3. TEST VIDEO BUTTONS (Download & Vault)
    video_cards = driver.find_elements(By.CLASS_NAME, "video-card")
    if video_cards:
        print(f"Found {len(video_cards)} videos! Testing buttons on the first one...")
        
        # Test Download
        video_cards[0].find_element(By.XPATH, ".//button[contains(text(), 'Download')]").click()
        print("✅ Download triggered!")
        time.sleep(1.5) # Give the browser a second to start the download

        # Test Save to Vault
        vault_btn = video_cards[0].find_element(By.XPATH, ".//button[contains(text(), 'Vault')]")
        if "disabled" not in vault_btn.get_attribute("outerHTML"):
            vault_btn.click()
            WebDriverWait(driver, 5).until(EC.alert_is_present())
            alert = driver.switch_to.alert
            print(f"✅ Vault API responded with: {alert.text}")
            alert.accept()
        else:
            print("✅ Video already in the vault, skipping save test.")
    else:
        print("⚠️ No videos found to test buttons! Make sure the server has data.")

    # 4. TEST NAVIGATION (Vault -> Dashboard -> Logout)
    driver.find_element(By.LINK_TEXT, "View Cloud Vault →").click()
    WebDriverWait(driver, 5).until(EC.url_contains("vault.html"))
    print("✅ Successfully navigated to Cloud Vault page!")
    time.sleep(1)

    driver.find_element(By.LINK_TEXT, "← Back to Dashboard").click()
    WebDriverWait(driver, 5).until(EC.url_contains("index.html"))
    print("✅ Successfully returned to Dashboard!")
    time.sleep(1)

    driver.find_element(By.XPATH, "//button[contains(text(), 'Logout')]").click()
    WebDriverWait(driver, 5).until(EC.url_contains("login.html"))
    print("✅ Successfully logged out!")

    print("\n🎉 ALL END-TO-END UI TESTS PASSED! YOU ARE BULLETPROOF.")
    time.sleep(2)

finally:
    driver.quit()