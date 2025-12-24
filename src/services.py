"""
سرویس‌های اصلی اپلیکیشن
"""

import asyncio
import random
import io
import pandas as pd
from random import uniform
from datetime import datetime
import re

from .state_manager import state, add_log
from .browser_ops import ensure_browser, go_to_contacts_page, send_direct_message, add_single_contact, normalize_persian_text, extract_usernames_from_text
from database import db

async def automation_worker(phone, mode, group_name, keyword, msg, min_d, max_d, your_own_username):
    """کارگر اصلی اتوماسیون"""
    state.stop_requested = False
    state.dispatch_report.clear()
    add_log("🧹 گزارش قبلی پاک شد.")
    
    try:
        page = await ensure_browser()
        state.is_running = True
        
        formatted_phone = phone.strip()
        if formatted_phone.startswith("0"):
            formatted_phone = "+98" + formatted_phone[1:]
        elif not formatted_phone.startswith("+"):
            formatted_phone = "+98" + formatted_phone

        add_log(f"شروع با شماره: {formatted_phone}")
        await page.goto("https://web.eitaa.com/", timeout=30000)
        
        try:
            await page.wait_for_selector('#chatlist-container', timeout=15000)
            add_log("حساب متصل است.")
        except:
            add_log("نیاز به ورود...")
            phone_input = page.locator('input[name="phone_number"], .input-field-phone .input-field-input').first
            await phone_input.fill(formatted_phone)
            await page.keyboard.press("Enter")
            
            state.otp_required = True
            state.current_step = "منتظر کد تایید..."
            state.otp_event.clear()
            await state.otp_event.wait()
            
            await page.keyboard.type(state.otp_code)
            state.otp_required = False
            await page.wait_for_selector('#chatlist-container', timeout=60000)
        
        if mode == "tahvil":
            return await handle_tahvil_mode(page, formatted_phone, group_name, keyword, msg, min_d, max_d, your_own_username)
        elif mode == "excel":
            return await handle_excel_mode(page, formatted_phone, msg, min_d, max_d)
        elif mode == "login":
            add_log("ورود انجام شد.")
            return True
            
    except Exception as e:
        add_log(f"❌ خطا در اجرای ربات: {str(e)}")
        return False
    finally:
        state.is_running = False
        state.current_step = "پایان یافت"
        add_log("ربات متوقف شد.")

async def handle_tahvil_mode(page, phone, group_name, keyword, msg, min_d, max_d, your_own_username):
    """مدیریت حالت ربات تحویل"""
    add_log(f"در حال جستجوی گروه: {group_name}")
    
    try:
        main_search_input_selector = 'input.input-search-input[placeholder="جستجو"]'
        search_input_locator = page.locator(main_search_input_selector)
        await search_input_locator.wait_for(state='visible', timeout=20000)
        await search_input_locator.click(timeout=10000)
        await search_input_locator.fill("")
        await page.wait_for_timeout(500)
        await search_input_locator.fill(group_name, timeout=10000)
        
        group_item_selector_main_search = f'li.rp.chatlist-chat:has(span.peer-title > i:text-is("{group_name}"))'
        group_element_locator = page.locator(group_item_selector_main_search).first
        
        await group_element_locator.wait_for(state='attached', timeout=15000)
        
        try:
            await group_element_locator.scroll_into_view_if_needed(timeout=5000)
        except:
            pass
        
        await group_element_locator.wait_for(state='visible', timeout=20000)
        await group_element_locator.click(timeout=10000)
        
        target_group_page_content_selector = ".bubble-content"
        await page.wait_for_selector(target_group_page_content_selector, state='visible', timeout=15000)
        add_log(f"✅ با موفقیت وارد گروه '{group_name}' شدید.")
        
    except Exception as e_search_group:
        add_log(f"❌ خطا در مرحله جستجو و ورود به گروه: {e_search_group}")
        return False

    add_log(f"\n--- در حال جستجوی پیام‌های دارای پیشوند: '{keyword}' ---")
    target_message_text = None
    
    try:
        message_bubble_selector = "div.bubble"
        message_text_in_bubble_selector = "div.message"
        
        chat_scrollable_area_locator = page.locator('//div[contains(@class, "bubbles")]/div[contains(@class, "scrollable-y")]').first
        if await chat_scrollable_area_locator.count() > 0:
            for _ in range(2):
                await chat_scrollable_area_locator.evaluate("el => el.scrollTop = 0")
                await asyncio.sleep(2)

        all_message_bubbles = page.locator(message_bubble_selector)
        count = await all_message_bubbles.count()
        add_log(f"تعداد {count} حباب پیام در گروه یافت شد. در حال بررسی از آخر...")
        
        for i in range(count - 1, -1, -1):
            single_bubble_locator = all_message_bubbles.nth(i)
            message_text_locator = single_bubble_locator.locator(message_text_in_bubble_selector)
            
            if await message_text_locator.count() > 0:
                try:
                    text_content = await message_text_locator.inner_text(timeout=3000)
                    text_to_check = normalize_persian_text(text_content.strip() if text_content else "")
                    
                    if text_to_check and keyword and text_to_check.startswith(keyword):
                        target_message_text = text_content.strip()
                        add_log(f"🎯 پیام هدف پیدا شد: '{target_message_text[:50]}...'")
                        break
                except:
                    continue
        
        if not target_message_text: 
            add_log(f"⚠️ پیام با پیشوند '{keyword}' در گروه '{group_name}' پیدا نشد.")
            return False
            
    except Exception as e_find_msg:
        add_log(f"❌ خطایی در هنگام جستجوی پیام هدف در گروه '{group_name}' رخ داد: {e_find_msg}")
        return False

    found_users = extract_usernames_from_text(target_message_text)
    found_users = list(dict.fromkeys(found_users))
    
    if not found_users:
        add_log("⚠️ هیچ نام کاربری (@username) در پیام پیدا نشد.")
        return False

    hashtagged_prefix = f"#{keyword}"
    final_message_to_send = f"{msg}\n{hashtagged_prefix}"
    
    add_log(f"🎯 {len(found_users)} کاربر برای ارسال پیام پیدا شد.")
    
    for user_with_at in found_users:
        if state.stop_requested:
            add_log("توقف درخواست شده.")
            break
            
        clean_username = user_with_at.lstrip('@')
        
        if your_own_username and clean_username.lower() == your_own_username.lower():
            add_log(f"ℹ️ از ارسال پیام به '{user_with_at}' (خودتان) صرف نظر شد.")
            
            state.dispatch_report.append({
                "id": user_with_at,
                "status": "skipped",
                "error": "نام کاربری خودتان - صرف نظر شد",
                "timestamp": datetime.now().strftime("%H:%M:%S")
            })
            
            db.save_dispatch_report(
                user_id=user_with_at,
                status="skipped",
                error_message="نام کاربری خودتان - صرف نظر شد",
                operation_type="tahvil",
                message_content=final_message_to_send[:500],
                phone_number=phone
            )
            continue
        
        success, message = await send_direct_message(page, user_with_at, final_message_to_send, min_d, max_d, "tahvil", phone)
        
        if success:
            status = "success"
            error_msg = "ارسال با موفقیت انجام شد."
        else:
            status = "failed"
            error_msg = message
        
        state.dispatch_report.append({
            "id": user_with_at,
            "status": status,
            "error": error_msg,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        })
        
        db.save_dispatch_report(
            user_id=user_with_at,
            status=status,
            error_message=error_msg,
            operation_type="tahvil",
            message_content=final_message_to_send[:500],
            phone_number=phone
        )
        
        delay_seconds = uniform(float(min_d), float(max_d))
        add_log(f"   تاخیر {delay_seconds:.2f} ثانیه‌ای...")
        await page.wait_for_timeout(int(delay_seconds * 1000))
    
    add_log("🎉 عملیات ارسال پیام‌ها به پایان رسید.")
    return True

async def handle_excel_mode(page, phone, msg, min_d, max_d):
    """مدیریت حالت ارسال از اکسل"""
    add_log(f"شروع ارسال به {len(state.target_list)} کاربر از اکسل")
    
    if not state.target_list:
        add_log("⚠️ لیست کاربران از اکسل خالی است.")
        return False
    
    for user in state.target_list:
        if state.stop_requested:
            break
            
        if not user.startswith('@'):
            user = '@' + user
            
        success, message = await send_direct_message(page, user, msg, min_d, max_d, "excel", phone)
        
        if success:
            status = "success"
            error_msg = "ارسال با موفقیت انجام شد."
        else:
            status = "failed"
            error_msg = message
        
        state.dispatch_report.append({
            "id": user,
            "status": status,
            "error": error_msg,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        })
        
        db.save_dispatch_report(
            user_id=user,
            status=status,
            error_message=error_msg,
            operation_type="excel",
            message_content=msg[:500],
            phone_number=phone
        )
        
        delay_seconds = uniform(float(min_d), float(max_d))
        add_log(f"   تاخیر {delay_seconds:.2f} ثانیه‌ای...")
        await page.wait_for_timeout(int(delay_seconds * 1000))
    
    return True

async def add_contacts_worker(phone):
    """کارگر افزودن مخاطبین"""
    state.contacts_is_running = True
    state.contacts_completed = False
    state.contacts_success_count = 0
    state.contacts_failed_count = 0
    state.contacts_progress = 0
    state.contacts_total = len(state.filtered_contacts_list)
    state.contacts_status = "در حال شروع..."
    state.contacts_error = None
    
    try:
        page = await ensure_browser()
        
        formatted_phone = phone.strip()
        if formatted_phone.startswith("0"):
            formatted_phone = "+98" + formatted_phone[1:]
        elif not formatted_phone.startswith("+"):
            formatted_phone = "+98" + formatted_phone

        add_log(f"شروع افزودن مخاطبین با شماره: {formatted_phone}")
        add_log(f"📊 {len(state.filtered_contacts_list)} مخاطب جدید، {state.duplicate_contacts_count} مخاطب تکراری")
        state.contacts_status = "در حال ورود به ایتا..."
        
        await page.goto("https://web.eitaa.com/", timeout=30000)
        
        try:
            await page.wait_for_selector('#chatlist-container', timeout=10000)
            add_log("حساب متصل است.")
        except:
            add_log("نیاز به ورود...")
            phone_input = page.locator('input[name="phone_number"], .input-field-phone .input-field-input').first
            await phone_input.fill(formatted_phone)
            await page.keyboard.press("Enter")
            
            state.otp_required = True
            state.current_step = "منتظر کد تایید..."
            state.otp_event.clear()
            await state.otp_event.wait()
            
            await page.keyboard.type(state.otp_code)
            state.otp_required = False
            await page.wait_for_selector('#chatlist-container', timeout=60000)
        
        state.contacts_status = "در حال باز کردن منو..."
        add_log("باز کردن منوی همبرگر...")
        
        try:
            menu_button = page.locator('div.btn-icon.btn-menu-toggle.rp.sidebar-tools-button.is-visible').first
            await menu_button.wait_for(state='visible', timeout=4000)
            await menu_button.click(timeout=3000)
            add_log("منوی همبرگر باز شد.")
            await asyncio.sleep(3)
            
        except Exception as e:
            error_msg = f"خطا در باز کردن منو: {str(e)}"
            add_log(f"❌ {error_msg}")
            state.contacts_error = error_msg
            state.contacts_is_running = False
            return
        
        state.contacts_status = "در حال انتخاب مخاطبین..."
        add_log("کلیک روی گزینه مخاطبین...")
        
        try:
            contacts_option = page.locator('div.btn-menu-item.tgico-user.rp').first
            await contacts_option.wait_for(state='visible', timeout=3000)
            await contacts_option.click(timeout=2000)
            add_log("گزینه مخاطبین انتخاب شد.")
            await asyncio.sleep(3)
            
            add_contact_btn = page.locator('button.btn-circle.btn-corner.tgico-add.rp').first
            if await add_contact_btn.count() > 0:
                add_log("✓ صفحه مخاطبین بارگذاری شد")
            else:
                add_log("⚠️ صفحه مخاطبین ممکن است کامل بارگذاری نشده باشد")
            
        except Exception as e:
            error_msg = f"خطا در انتخاب گزینه مخاطبین: {str(e)}"
            add_log(f"❌ {error_msg}")
            state.contacts_error = error_msg
            state.contacts_is_running = False
            return
        
        state.contacts_status = "در حال افزودن مخاطبین..."
        
        for i, contact in enumerate(state.filtered_contacts_list):
            success = await add_single_contact(page, contact, i, state.contacts_total, phone)
            
            if success:
                state.contacts_success_count += 1
            else:
                state.contacts_failed_count += 1
            
            state.contacts_progress = i + 1
            
            if i < state.contacts_total - 1:
                delay = random.uniform(2, 4)
                add_log(f"⏳ تاخیر {delay:.1f} ثانیه تا مخاطب بعدی...")
                await asyncio.sleep(delay)
        
        state.contacts_status = "عملیات تکمیل شد"
        state.contacts_completed = True
        add_log(f"🎉 عملیات افزودن مخاطبین تکمیل شد. موفق: {state.contacts_success_count}, ناموفق: {state.contacts_failed_count}, تکراری: {state.duplicate_contacts_count}")
        
        stats = db.get_contacts_statistics()
        add_log(f"📈 آمار کلی مخاطبین: {stats['total']} مخاطب در دیتابیس")
        
    except Exception as e:
        error_msg = f"خطای کلی در عملیات افزودن مخاطبین: {str(e)}"
        add_log(f"❌ {error_msg}")
        state.contacts_error = error_msg
    finally:
        state.contacts_is_running = False
        state.contacts_status = "پایان یافت"

def process_contacts_excel(contents):
    """پردازش فایل اکسل مخاطبین"""
    try:
        import openpyxl
        from io import BytesIO
        
        wb = openpyxl.load_workbook(BytesIO(contents))
        ws = wb.active
        
        contacts = []
        valid_count = 0
        invalid_count = 0
        
        for idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            if not any(row):
                continue
                
            try:
                name = str(row[0]).strip() if row[0] is not None else ""
                
                phone_raw = ""
                if row[1] is not None:
                    if isinstance(row[1], (int, float)):
                        phone_int = int(row[1])
                        phone_raw = str(phone_int)
                        
                        if len(phone_raw) < 10:
                            phone_raw = phone_raw.zfill(10)
                        elif len(phone_raw) > 10:
                            phone_raw = phone_raw[-10:]
                    else:
                        phone_raw = str(row[1]).strip()
                
                phone = re.sub(r'\D', '', phone_raw)
                
                if not phone:
                    invalid_count += 1
                    add_log(f"⚠️ سطر {idx}: شماره تلفن خالی - صرف نظر شد")
                    continue
                
                original_phone = phone
                
                if phone.startswith('0'):
                    phone = phone[1:]
                if phone.startswith('98'):
                    phone = phone[2:]
                if phone.startswith('989'):
                    phone = phone[3:]
                
                if len(phone) > 10:
                    phone = phone[:10]
                    add_log(f"  ⚠️ شماره کوتاه شد: {original_phone} -> {phone}")
                elif len(phone) < 10:
                    phone = phone.zfill(10)
                    add_log(f"  ⚠️ صفرهای ابتدایی اضافه شد: {original_phone} -> {phone}")
                
                if not phone.startswith('9'):
                    phone = '9' + phone[1:] if len(phone) > 1 else '9' + phone
                    add_log(f"  ⚠️ به 9 شروع شد: {original_phone} -> {phone}")
                
                if (name and 
                    phone.isdigit() and 
                    len(phone) == 10 and 
                    phone.startswith('9')):
                    
                    contacts.append({
                        "name": name[:50],
                        "phone": phone
                    })
                    valid_count += 1
                    add_log(f"✓ سطر {idx}: '{name[:20]}...' - '{phone}' پذیرفته شد")
                    
                else:
                    invalid_count += 1
                    add_log(f"⚠️ سطر {idx}: اطلاعات نامعتبر - نام: '{name[:20]}...'، تلفن: '{phone}'")
                    
            except Exception as e:
                invalid_count += 1
                add_log(f"⚠️ خطا در پردازش سطر {idx}: {str(e)}")
                continue
        
        state.contacts_list = contacts
        state.filtered_contacts_list, state.duplicate_contacts_count = db.filter_new_contacts(contacts)
        
        state.contacts_progress = 0
        state.contacts_total = len(state.filtered_contacts_list)
        state.contacts_completed = False
        state.contacts_error = None
        
        add_log(f"📊 نتیجه بارگذاری: {valid_count} مخاطب معتبر، {invalid_count} مخاطب نامعتبر")
        add_log(f"📊 بعد از فیلتر تکراری‌ها: {len(state.filtered_contacts_list)} مخاطب جدید، {state.duplicate_contacts_count} مخاطب تکراری")
        
        return {
            "status": "success",
            "count": len(contacts),
            "new_count": len(state.filtered_contacts_list),
            "duplicate_count": state.duplicate_contacts_count,
            "contacts": state.filtered_contacts_list[:10],
            "message": f"{len(contacts)} مخاطب معتبر شناسایی شد ({invalid_count} نامعتبر). {len(state.filtered_contacts_list)} مخاطب جدید، {state.duplicate_contacts_count} تکراری"
        }
        
    except Exception as e:
        add_log(f"خطا در پردازش اکسل مخاطبین: {str(e)}")
        return {"status": "error", "message": f"خطا در پردازش فایل: {str(e)}"}