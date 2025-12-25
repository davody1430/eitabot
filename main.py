import sys
import os
import asyncio
import logging
import json
from datetime import datetime
from contextlib import asynccontextmanager
import threading
from selenium_automation import EitaaAutomation
import subprocess
import shutil

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import aiofiles

# ================== تنظیمات مسیر برای PyInstaller ==================
def get_base_path():
    """Get the base path for the application (for PyInstaller)"""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    else:
        return os.path.dirname(os.path.abspath(__file__))

def get_exe_path():
    """Get the executable path"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_base_path()
EXE_DIR = get_exe_path()

print("=" * 60)
print(f"📂 حالت: {'EXE' if getattr(sys, 'frozen', False) else 'توسعه'}")
print(f"📁 مسیر پایه: {BASE_DIR}")
print(f"📁 مسیر اجرا: {EXE_DIR}")
print("=" * 60)

# ================== تنظیمات لاگینگ ==================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ================== مدل‌های Pydantic ==================
class MessageData(BaseModel):
    message: str
    recipients: List[str]

# ================== متغیرهای Global ==================
automation_instance = None
bot_running = False
otp_needed = False

# ================== توابع کمکی ==================
def get_log_file_path():
    return os.path.join(EXE_DIR, "bot_logs.json")

async def save_log(level: str, message: str):
    log_file = get_log_file_path()
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "level": level,
        "message": message
    }

    try:
        logs = []
        if os.path.exists(log_file):
            async with aiofiles.open(log_file, 'r', encoding='utf-8') as f:
                content = await f.read()
                if content:
                    logs = json.loads(content)

        logs.append(log_entry)

        async with aiofiles.open(log_file, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(logs, ensure_ascii=False, indent=2))

    except Exception as e:
        print(f"❌ خطا در ذخیره لاگ: {e}")

# ================== تنظیمات FastAPI ==================
app = FastAPI(title="فرستیار")

templates_dir = os.path.join(BASE_DIR, "templates")
static_dir = os.path.join(BASE_DIR, "static")

print(f"📁 مسیر Templates: {templates_dir}")
print(f"📁 مسیر Static: {static_dir}")

os.makedirs(templates_dir, exist_ok=True)
os.makedirs(static_dir, exist_ok=True)

templates = Jinja2Templates(directory=templates_dir)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# ================== Lifespan Events ==================
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 راه‌اندازی فرستیار...")
    await save_log("INFO", "برنامه راه‌اندازی شد")
    yield
    print("🛑 خاموش کردن...")
    await save_log("INFO", "برنامه خاموش می‌شود")
    if automation_instance:
        automation_instance.close()

app.router.lifespan_context = lifespan

# ================== Routes ==================
@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/get-status")
async def get_status():
    global otp_needed
    return JSONResponse({
        "bot_running": bot_running,
        "otp_required": otp_needed,
        "current_step": "در انتظار کد تایید..." if otp_needed else ("در حال اجرا..." if bot_running else "آماده"),
        "logs": []
    })

def run_eitaa_automation(phone_number):
    global automation_instance, bot_running, otp_needed
    bot_running = True
    otp_needed = False
    try:
        automation_instance = EitaaAutomation(phone_number)
        if automation_instance.setup_driver():
            result = automation_instance.login_to_eitaa()
            if result.get("status") == "otp_required":
                otp_needed = True
    except Exception as e:
        logger.error(f"Error in Eitaa automation thread: {e}", exc_info=True)
    finally:
        # If OTP is needed, the bot is still in a "running" state
        if not otp_needed:
            bot_running = False

@app.post("/login")
async def post_login(phone_number: str = Form(...)):
    global bot_running
    if bot_running:
        return JSONResponse({"status": "error", "message": "ربات در حال اجرا است"})

    thread = threading.Thread(target=run_eitaa_automation, args=(phone_number,))
    thread.start()

    return JSONResponse({"status": "success", "message": "فرآیند اتصال به ایتا آغاز شد."})

@app.post("/submit-otp")
async def submit_otp(code: str = Form(...)):
    global automation_instance
    if not automation_instance or not automation_instance.driver:
        return JSONResponse({"status": "error", "message": "ربات آماده نیست. لطفاً ابتدا شماره تلفن را وارد کنید."})

    result = automation_instance.submit_otp(code)
    return JSONResponse(result)

@app.post("/send_message")
async def post_send_message(data: MessageData):
    # This endpoint is not fully implemented for Eitaa yet
    # but we keep it to avoid breaking the frontend if it's called.
    return JSONResponse({
        "status": "error",
        "message": "ارسال پیام هنوز برای ایتا پیاده‌سازی نشده است"
    })

@app.get("/logs")
async def get_logs():
    try:
        log_file = get_log_file_path()
        if os.path.exists(log_file):
            async with aiofiles.open(log_file, 'r', encoding='utf-8') as f:
                logs = json.loads(await f.read())
                return JSONResponse({"logs": logs})
        return JSONResponse({"logs": []})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# ================== اجرای سرور ==================
def run_server():
    try:
        import uvicorn

        print("=" * 60)
        print("🚀 فرستیار آماده اجرا")
        print(f"🌐 آدرس: http://127.0.0.1:8000")
        print(f"📁 مسیر: {EXE_DIR}")
        print("=" * 60)
        print("📋 دستورالعمل:")
        print("1. مرورگر را باز کنید")
        print("2. به آدرس بالا بروید")
        print("3. شماره تلفن را وارد کنید")
        print("4. روی 'اتصال به ایتا' کلیک کنید")
        print("=" * 60)

        uvicorn.run(
            app,
            host="127.0.0.1",
            port=8000,
            log_level="info",
            access_log=True
        )

    except Exception as e:
        print(f"❌ خطا: {e}")
        import traceback
        traceback.print_exc()
        input("\n⏸️ برای خروج Enter را بزنید...")

if __name__ == "__main__":
    run_server()
