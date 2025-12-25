import time
import os
import sys
import logging
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

logger = logging.getLogger(__name__)

class EitaaAutomation:
    def __init__(self, phone_number, delay=7, headless=False):
        self.phone_number = phone_number
        self.delay = delay
        self.headless = headless
        self.driver = None
        self.wait = None

    def setup_driver(self):
        try:
            chrome_options = Options()
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])

            if self.headless:
                chrome_options.add_argument("--headless=new")

            if getattr(sys, 'frozen', False):
                base_path = os.path.dirname(sys.executable)
            else:
                base_path = os.path.dirname(os.path.abspath(__file__))

            local_driver = os.path.join(base_path, "chromedriver.exe")

            if os.path.exists(local_driver):
                service = Service(executable_path=local_driver)
            else:
                driver_path = ChromeDriverManager().install()
                service = Service(driver_path)

            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.set_window_size(1200, 900)
            self.wait = WebDriverWait(self.driver, 30)
            return True
        except Exception as e:
            logger.error(f"WebDriver Error: {e}", exc_info=True)
            return False

    def login_to_eitaa(self):
        try:
            logger.info("Navigating to Eitaa Web...")
            self.driver.get("https://web.eitaa.com/")

            try:
                logger.info("Checking if already logged in...")
                WebDriverWait(self.driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder='جستجو']")))
                logger.info("Already logged in.")
                return {"status": "already_logged_in"}
            except:
                logger.info("Not logged in. Proceeding with login flow.")

            logger.info("Looking for phone number input field...")
            phone_input = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='tel']")))
            logger.info("Phone number input found. Sending keys...")
            phone_input.send_keys(self.phone_number)

            logger.info("Looking for submit button...")
            submit_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            logger.info("Submit button found. Clicking...")
            submit_button.click()

            logger.info("Waiting for OTP screen...")
            self.wait.until(EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'کد تایید را وارد کنید')]")))
            logger.info("OTP screen is visible.")
            return {"status": "otp_required"}

        except Exception as e:
            logger.error(f"An error occurred during login: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

    def submit_otp(self, code):
        try:
            logger.info(f"Submitting OTP code: {code}")
            # Assuming the OTP input is a single field that takes the whole code
            otp_input = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='text']"))) # Adjust selector if needed
            otp_input.send_keys(code)

            # Usually there is no submit button for OTP, but if there is, click it.
            # For now, we assume entering the code is enough.

            logger.info("Waiting for successful login after OTP submission...")
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder='جستجو']")))
            logger.info("Login successful after OTP.")
            return {"status": "success"}
        except Exception as e:
            logger.error(f"An error occurred during OTP submission: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

    def add_contact(self, name, phone_number):
        try:
            self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[aria-label='منو']"))).click()
            time.sleep(1)
            self.wait.until(EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'مخاطبین')]"))).click()
            time.sleep(1)
            self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[aria-label='افزودن مخاطب']"))).click()

            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder='نام']"))).send_keys(name)
            self.driver.find_element(By.CSS_SELECTOR, "input[placeholder='شماره تلفن']").send_keys(phone_number)
            self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()

            time.sleep(self.delay)
            return True
        except:
            return False

    def process_excel_file(self, excel_path, operation_type):
        df = pd.read_excel(excel_path)
        results = []
        for _, row in df.iterrows():
            name = str(row['name'])
            phone = str(row['phone'])
            success = self.add_contact(name, phone) if operation_type == "add_contact" else False
            results.append({'name': name, 'phone': phone, 'success': success})
        return results

    def close(self):
        if self.driver:
            self.driver.quit()
