import sys
import os
import asyncio
import logging
import json
from datetime import datetime
from contextlib import asynccontextmanager
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
        # If the application is run as a bundle (pyinstaller)
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

# ================== تنظیمات Playwright ==================
async def setup_playwright():
    """Setup and verify Playwright installation"""
    print("🔧 تنظیم Playwright...")
    
    # چند مسیر احتمالی برای مرورگرها
    possible_paths = [
        os.path.join(os.environ.get('LOCALAPPDATA', ''), 'ms-playwright'),
        os.path.join(os.path.expanduser('~'), '.cache', 'ms-playwright'),
        os.path.join(EXE_DIR, 'playwright'),
        os.path.join(BASE_DIR, 'playwright'),
    ]
    
    # پیدا کردن مسیر مرورگرها
    browsers_path = None
    for path in possible_paths:
        if os.path.exists(path):
            browsers_path = path
            print(f"✅ مسیر مرورگرها یافت شد: {path}")
            break
    
    # اگر مسیر یافت نشد، مرورگر را نصب کن
    if not browsers_path:
        print("📦 مرورگر Playwright یافت نشد. در حال نصب...")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                capture_output=True,
                text=True,
                cwd=EXE_DIR
            )
            
            if result.returncode == 0:
                print("✅ مرورگر نصب شد")
                # پیدا کردن مسیر نصب شده
                for path in possible_paths:
                    if os.path.exists(path):
                        browsers_path = path
                        break
            else:
                print(f"❌ خطا در نصب: {result.stderr}")
                return None
        except Exception as e:
            print(f"❌ خطا: {str(e)}")
            return None
    
    # تنظیم متغیر محیطی
    if browsers_path:
        os.environ['PLAYWRIGHT_BROWSERS_PATH'] = browsers_path
        print(f"🎯 PLAYWRIGHT_BROWSERS_PATH: {browsers_path}")
        return browsers_path
    
    return None

# ================== تنظیمات لاگینگ ==================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ================== مدل‌های Pydantic ==================
class LoginData(BaseModel):
    phone_number: str

class MessageData(BaseModel):
    message: str
    recipients: List[str]

# ================== متغیرهای Global ==================
browser = None
playwright_instance = None
current_page = None
bot_running = False

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

# تنظیم templates
templates_dir = os.path.join(BASE_DIR, "templates")
static_dir = os.path.join(BASE_DIR, "static")

print(f"📁 مسیر Templates: {templates_dir}")
print(f"📁 مسیر Static: {static_dir}")

# ایجاد پوشه‌ها
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
    
    if browser:
        try:
            await browser.close()
            print("✅ مرورگر بسته شد")
        except:
            pass
    
    if playwright_instance:
        try:
            await playwright_instance.stop()
            print("✅ Playwright متوقف شد")
        except:
            pass

app.router.lifespan_context = lifespan

# ================== Routes ==================
@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/status")
async def get_status():
    return JSONResponse({
        "bot_running": bot_running,
        "browser_open": browser is not None,
        "base_dir": BASE_DIR,
        "exe_dir": EXE_DIR
    })

@app.post("/login")
async def post_login(data: LoginData):
    global browser, current_page, bot_running, playwright_instance
    
    print(f"📱 درخواست ورود با شماره: {data.phone_number}")
    await save_log("INFO", f"درخواست ورود با شماره: {data.phone_number}")
    
    if bot_running:
        return JSONResponse({"status": "error", "message": "ربات در حال اجرا است"})
    
    try:
        # 1. تنظیم Playwright
        print("🔧 در حال تنظیم Playwright...")
        browsers_path = await setup_playwright()
        
        if not browsers_path:
            return JSONResponse({
                "status": "error", 
                "message": "Playwright تنظیم نشد"
            })
        
        # 2. Import Playwright - مهم: باید اینجا import شود
        print("🎬 Import کردن Playwright...")
        from playwright.async_api import async_playwright
        
        # 3. شروع Playwright
        print("🚀 شروع Playwright...")
        playwright_instance = await async_playwright().start()
        
        # 4. یافتن مسیر اجرایی chromium
        import glob
        chromium_paths = glob.glob(
            os.path.join(browsers_path, '**', 'chrome.exe'), 
            recursive=True
        )
        
        executable_path = None
        if chromium_paths:
            executable_path = chromium_paths[0]
            print(f"✅ مسیر chromium: {executable_path}")
        else:
            print("⚠️ مسیر chromium یافت نشد، استفاده از مرورگر سیستم")
        
        # 5. اجرای مرورگر
        print("🌐 باز کردن مرورگر...")
        launch_options = {
            "headless": False,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
                "--disable-dev-shm-usage",
                "--no-sandbox"
            ],
            "slow_mo": 50  # کاهش سرعت برای مشاهده
        }
        
        if executable_path:
            launch_options["executable_path"] = executable_path
        
        browser = await playwright_instance.chromium.launch(**launch_options)
        
        # 6. ایجاد صفحه
        print("📄 ایجاد صفحه جدید...")
        current_page = await browser.new_page()
        await current_page.set_viewport_size({"width": 1366, "height": 768})
        
        # 7. رفتن به واتساپ
        print("📱 رفتن به واتساپ وب...")
        await current_page.goto("https://web.whatsapp.com")
        
        # 8. منتظر QR code
        print("🔍 منتظر QR code...")
        try:
            # صبر کن تا صفحه لود شود
            await current_page.wait_for_load_state("networkidle", timeout=30000)
            
            # بررسی وجود QR code
            qr_selector = "canvas[aria-label='Scan me!']"
            await current_page.wait_for_selector(qr_selector, timeout=30000)
            
            print("✅ QR code نمایش داده شد")
            await save_log("SUCCESS", "QR code نمایش داده شد")
            
            bot_running = True
            
            return JSONResponse({
                "status": "success",
                "message": "مرورگر باز شد. لطفاً QR code را اسکن کنید.",
                "qr_required": True
            })
            
        except Exception as e:
            print(f"⚠️ QR code: {e}")
            
            # شاید قبلاً وارد شده‌اید
            try:
                await current_page.wait_for_selector("div[data-testid='chat-list']", timeout=5000)
                print("✅ قبلاً وارد شده‌اید")
                
                bot_running = True
                await save_log("SUCCESS", "کاربر قبلاً وارد شده")
                
                return JSONResponse({
                    "status": "success",
                    "message": "با موفقیت وارد شدید",
                    "qr_required": False
                })
            except:
                # گرفتن اسکرین‌شات برای دیباگ
                screenshot_path = os.path.join(EXE_DIR, "debug_screenshot.png")
                await current_page.screenshot(path=screenshot_path)
                print(f"📸 اسکرین‌شات ذخیره شد: {screenshot_path}")
                
                return JSONResponse({
                    "status": "error",
                    "message": f"QR code نمایش داده نشد. خطا: {str(e)}"
                })
        
    except Exception as e:
        error_msg = f"خطا: {str(e)}"
        print(f"❌ {error_msg}")
        import traceback
        traceback.print_exc()
        
        await save_log("ERROR", error_msg)
        
        # تمیزکاری
        if browser:
            try:
                await browser.close()
            except:
                pass
        
        if playwright_instance:
            try:
                await playwright_instance.stop()
            except:
                pass
        
        browser = None
        playwright_instance = None
        current_page = None
        bot_running = False
        
        return JSONResponse({
            "status": "error",
            "message": error_msg
        })

@app.post("/send_message")
async def post_send_message(data: MessageData):
    if not current_page or not browser:
        return JSONResponse({
            "status": "error", 
            "message": "ابتدا وارد شوید"
        })
    
    try:
        print(f"📨 ارسال پیام به {len(data.recipients)} گیرنده")
        await save_log("INFO", f"ارسال پیام: {data.message}")
        
        # این یک نمونه ساده است
        # در واقعیت باید با عناصر واتساپ کار کنید
        for recipient in data.recipients:
            print(f"  ↪️ به: {recipient}")
            await save_log("INFO", f"ارسال به {recipient}")
        
        return JSONResponse({
            "status": "success",
            "message": f"پیام به {len(data.recipients)} نفر ارسال شد"
        })
        
    except Exception as e:
        error_msg = f"خطا در ارسال: {str(e)}"
        print(f"❌ {error_msg}")
        await save_log("ERROR", error_msg)
        
        return JSONResponse({
            "status": "error",
            "message": error_msg
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
    """تابع اجرای سرور"""
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
        print("4. روی 'ورود به واتساپ' کلیک کنید")
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