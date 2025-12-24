"""
مدیریت وضعیت اپلیکیشن - جدا از منطق عملیات
"""

import asyncio
from datetime import datetime

class BotState:
    def __init__(self):
        self.is_running = False
        self.logs = []
        self.current_step = "آماده"
        self.otp_required = False
        self.otp_event = asyncio.Event()
        self.otp_code = None
        self.target_list = []
        self.playwright_engine = None
        self.browser = None
        self.context = None
        self.page = None
        self.stop_requested = False
        self.ready_messages = []
        self.dispatch_report = []
        
        # مدیریت مخاطبین
        self.contacts_list = []
        self.filtered_contacts_list = []
        self.duplicate_contacts_count = 0
        self.contacts_progress = 0
        self.contacts_total = 0
        self.contacts_status = "آماده"
        self.contacts_completed = False
        self.contacts_success_count = 0
        self.contacts_failed_count = 0
        self.contacts_error = None
        self.contacts_is_running = False

# ایجاد نمونه global از state
state = BotState()

def add_log(msg):
    """افزودن لاگ به سیستم"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    state.logs.insert(0, f"[{timestamp}] {msg}")
    print(f"LOG: [{timestamp}] {msg}")