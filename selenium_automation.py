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
            
            # پیدا کردن مسیر درایور در حالت EXE
            if getattr(sys, 'frozen', False):
                base_path = os.path.dirname(sys.executable)
            else:
                base_path = os.path.dirname(os.path.abspath(__file__))
            
            # اولویت با درایور محلی کنار فایل EXE
            local_driver = os.path.join(base_path, "chromedriver.exe")
            
            if os.path.exists(local_driver):
                service = Service(executable_path=local_driver)
            else:
                # اگر نبود، دانلود خودکار (نیاز به اینترنت)
                driver_path = ChromeDriverManager().install()
                service = Service(driver_path)

            # نمایش پنجره سلنیوم (عدم استفاده از CREATE_NO_WINDOW)
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.set_window_size(1200, 900)
            self.wait = WebDriverWait(self.driver, 30)
            return True
        except Exception as e:
            print(f"WebDriver Error: {e}")
            return False

    def login_to_eitaa(self):
        try:
            self.driver.get("https://web.eitaa.com/")
            time.sleep(5)
            
            # چک کردن لاگین بودن
            try:
                self.driver.find_element(By.CSS_SELECTOR, "input[placeholder='جستجو']")
                return True
            except:
                pass

            # وارد کردن شماره
            phone_input = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='tel']")))
            phone_input.send_keys(self.phone_number)
            self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
            
            # منتظر ماندن برای ورود دستی کد توسط کاربر
            print("Please enter OTP in the browser...")
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder='جستجو']")))
            return True
        except Exception as e:
            print(f"Login Error: {e}")
            return False

    def add_contact(self, name, phone_number):
        try:
            # دکمه منو
            self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[aria-label='منو']"))).click()
            time.sleep(1)
            # دکمه مخاطبین (با استفاده از متن فارسی یا کلاس)
            self.wait.until(EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'مخاطبین')]"))).click()
            time.sleep(1)
            # افزودن مخاطب
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