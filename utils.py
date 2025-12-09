import re
from datetime import datetime
import unicodedata

def normalize_persian_text(text):
    if text is None:
        return None
    text = text.replace('\u064A', '\u06CC').replace('\u0649', '\u06CC')
    text = text.replace('\u0643', '\u06A9')
    text = text.replace('\u0629', '\u0647')
    return unicodedata.normalize('NFKC', text)

def extract_usernames_from_text(text):
    if not text: return []
    return re.findall(r'@[\w\d_]+', text)

def log_failed_dm_to_file_and_gui(username, failed_dms_filepath, gui_logger, reason="Unknown"):
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(failed_dms_filepath, "a", encoding="utf-8") as f:
            f.write(f"{timestamp} - {username} - Reason: {reason}\n")
        gui_logger.log(f"ℹ️ نام کاربری '{username}' به لیست ارسال‌های ناموفق در '{failed_dms_filepath}' اضافه شد. دلیل: {reason}")
    except Exception as e:
        gui_logger.log(f"‼️ خطا در نوشتن لاگ برای کاربر ناموفق {username} در فایل {failed_dms_filepath}: {e}")

def convert_phone_number_format(phone_number_str):
    if phone_number_str and phone_number_str.startswith('09') and len(phone_number_str) == 11 and phone_number_str.isdigit():
        return '98' + phone_number_str[1:]
    return phone_number_str