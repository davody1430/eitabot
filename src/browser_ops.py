"""
عملیات مربوط به مرورگر Playwright
"""

import asyncio
import unicodedata
import re
import random
from playwright.async_api import async_playwright
from .state_manager import state, add_log

async def ensure_browser():
    """اطمینان از وجود مرورگر"""
    if not state.playwright_engine:
        state.playwright_engine = await async_playwright().start()
    if not state.browser:
        add_log("در حال اجرای مرورگر...")
        state.browser = await state.playwright_engine.chromium.launch(headless=False)
        state.context = await state.browser.new_context()
        state.page = await state.context.new_page()
    return state.page

async def go_to_contacts_page(page):
    """هدایت به صفحه مخاطبین"""
    try:
        add_log("تلاش برای بازگشت به صفحه مخاطبین...")
        
        for _ in range(2):
            await page.keyboard.press('Escape')
            await asyncio.sleep(1)
        
        await asyncio.sleep(2)
        
        try:
            add_button = page.locator('button.btn-circle.btn-corner.tgico-add.rp').first
            if await add_button.count() > 0:
                add_log("✓ قبلاً در صفحه مخاطبین هستیم")
                return True
        except:
            pass
        
        try:
            back_button = page.locator('button.btn-icon.tgico-left.sidebar-close-button').first
            if await back_button.count() > 0:
                await back_button.click(timeout=3000)
                await asyncio.sleep(2)
                add_log("✓ دکمه بازگشت کلیک شد")
                
                add_button = page.locator('button.btn-circle.btn-corner.tgico-add.rp').first
                if await add_button.count() > 0:
                    add_log("✓ بعد از بازگشت در صفحه مخاطبین هستیم")
                    return True
        except:
            pass
        
        add_log("از طریق منو به مخاطبین می‌رویم...")
        
        try:
            menu_button = page.locator('div.btn-icon.btn-menu-toggle.rp.sidebar-tools-button.is-visible').first
            if await menu_button.count() > 0:
                await menu_button.click(timeout=5000)
                await asyncio.sleep(2)
        except:
            try:
                await page.click('div.animated-menu-icon')
                await asyncio.sleep(2)
            except:
                add_log("⚠️ نتوانست منو را باز کند")
                return False
        
        try:
            contacts_option = page.locator('div.btn-menu-item.tgico-user.rp').first
            if await contacts_option.count() > 0:
                await contacts_option.click(timeout=5000)
                await asyncio.sleep(3)
                
                try:
                    await page.wait_for_selector('button.btn-circle.btn-corner.tgico-add.rp', timeout=5000)
                    add_log("✓ به صفحه مخاطبین بازگشتیم")
                    return True
                except:
                    await asyncio.sleep(2)
                    add_button = page.locator('button.btn-circle.btn-corner.tgico-add.rp').first
                    if await add_button.count() > 0:
                        add_log("✓ صفحه مخاطبین بارگذاری شد")
                        return True
                    else:
                        add_log("⚠️ صفحه بارگذاری شد اما دکمه افزودن پیدا نشد")
                        return False
        except:
            add_log("⚠️ نتوانست گزینه مخاطبین را پیدا کند")
            return False
        
    except Exception as e:
        add_log(f"⚠️ خطا در بازگشت به صفحه مخاطبین: {e}")
        return False

async def send_direct_message(page, username_with_at, message_to_send, min_d, max_d, operation_type="unknown", phone_number=None):
    """ارسال پیام مستقیم به کاربر"""
    search_input_locator = page.locator('input.input-search-input[placeholder="جستجو"]').first
    
    try:
        clean_user = username_with_at.lstrip('@')
        add_log(f"🗣️ در حال تلاش برای ارسال پیام به {username_with_at}...")

        await search_input_locator.click(timeout=5000)
        await search_input_locator.fill("", timeout=3000)
        await page.wait_for_timeout(500)
        await search_input_locator.fill(username_with_at, timeout=5000)
        await asyncio.sleep(1)

        user_item_selector_dm = f'li.rp.chatlist-chat:has(p.dialog-subtitle > span.user-last-message > i:has-text("{username_with_at}"))'
        user_chat_element_locator_dm = page.locator(user_item_selector_dm).first
        
        await user_chat_element_locator_dm.wait_for(state='attached', timeout=10000)
        await user_chat_element_locator_dm.wait_for(state='visible', timeout=10000)
        await user_chat_element_locator_dm.click(timeout=5000)

        dm_message_input_selector = 'div.input-message-input[contenteditable="true"]:not(.input-field-input-fake)'
        dm_input_area_locator = page.locator(dm_message_input_selector)
        
        await dm_input_area_locator.wait_for(state='visible', timeout=10000)
        await dm_input_area_locator.fill(message_to_send)
        await dm_input_area_locator.press('Enter')
        add_log(f"📨 پیام به {username_with_at} ارسال شد.")
        
        return True, "ارسال با موفقیت انجام شد."
        
    except Exception as e:
        error_msg = str(e)[:100]
        add_log(f"❌ خطا در ارسال به {username_with_at}: {error_msg}")
        return False, f"خطا: {error_msg}"
        
    finally:
        try:
            if await search_input_locator.is_visible(timeout=1000):
                await search_input_locator.click(timeout=3000)
                await search_input_locator.fill("")
                await page.wait_for_timeout(200)
        except:
            pass

async def add_single_contact(page, contact, i, total, phone_number):
    """افزودن یک مخاطب"""
    try:
        name = contact['name']
        phone = contact['phone']
        
        add_log(f"📝 افزودن مخاطب {i+1}/{total}: {name} ({phone})")
        
        add_button = page.locator('button.btn-circle.btn-corner.tgico-add.rp').first
        await add_button.wait_for(state='visible', timeout=3000)
        await add_button.click(timeout=2000)
        add_log("  ✓ دکمه افزودن مخاطب کلیک شد")
        
        name_input = page.locator('div.input-field:has(label:has-text("نام")) div.input-field-input').first
        await name_input.fill(name)
        await asyncio.sleep(0.5)
        
        phone_input = page.locator('div.input-field.input-field-phone div.input-field-input').first
        await phone_input.fill('')
        await phone_input.type(f"+98 {phone[:3]} {phone[3:6]} {phone[6:]}", delay=100)
        await asyncio.sleep(0.5)
        
        submit_button = page.locator('button.btn-primary.btn-color-primary.rp:has-text("افزودن")').first
        await submit_button.click(timeout=2000)
        add_log("  ✓ دکمه افزودن کلیک شد")
        
        await asyncio.sleep(2)
        
        await page.keyboard.press('Escape')
        await asyncio.sleep(1)
        add_log("  ✓ Esc زده شد (فرم بسته شد)")
        
        return True
        
    except Exception as e:
        error_msg = str(e)[:100]
        add_log(f"❌ خطا در افزودن مخاطب {i+1}: {error_msg}")
        
        for _ in range(3):
            await page.keyboard.press('Escape')
            await asyncio.sleep(0.5)
        
        return False

def normalize_persian_text(text):
    """نرمال‌سازی متن فارسی"""
    if not text: return ""
    text = text.replace('\u064A', '\u06CC').replace('\u0649', '\u06CC')
    text = text.replace('\u0643', '\u06A9').replace('\u0629', '\u0647')
    return unicodedata.normalize('NFKC', text)

def extract_usernames_from_text(text):
    """استخراج نام کاربری از متن"""
    return re.findall(r'@[\w\d_]+', text) if text else []