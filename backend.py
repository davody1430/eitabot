import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import pandas as pd
from random import uniform
from utils import normalize_persian_text, extract_usernames_from_text, log_failed_dm_to_file_and_gui

async def run_tahvil_bot_async(config, logger, status_updater, login_event, exit_event):
    logger.log("ربات تحویل شروع به کار کرد...")
    status_updater.clear_table()
    browser = None
    page = None

    GROUP_NAME = normalize_persian_text(config["GROUP_NAME"])
    MESSAGE_PREFIX = normalize_persian_text(config["MESSAGE_PREFIX"])
    BASE_DM_MESSAGE = normalize_persian_text(config["BASE_DM_MESSAGE"])
    YOUR_OWN_USERNAME = config["YOUR_OWN_USERNAME"]
    PHONE_NUMBER_TO_ENTER = config["PHONE_NUMBER_TO_ENTER"]
    FAILED_DMS_FILE = config["FAILED_DMS_FILE"]
    MIN_DELAY_S = config["MIN_DELAY_S"]
    MAX_DELAY_S = config["MAX_DELAY_S"]

    async with async_playwright() as p:
        try:
            logger.log("در حال اجرای مرورگر...")
            browser = await p.chromium.launch(headless=False, slow_mo=250)
            context = await browser.new_context()
            page = await context.new_page()
            logger.log("مرورگر با موفقیت اجرا شد و صفحه جدید باز شد.")

            try:
                logger.log("در حال باز کردن صفحه وب ایتا: https://web.eitaa.com/")
                await page.goto("https://web.eitaa.com/", timeout=60000)
                phone_field_selector = 'div.input-field-phone div.input-field-input[contenteditable="true"]'
                phone_input_locator = page.locator(phone_field_selector)
                await phone_input_locator.wait_for(state='visible', timeout=30000)
                await phone_input_locator.fill(PHONE_NUMBER_TO_ENTER)
                await phone_input_locator.press('Enter')
                logger.log(f"شماره تلفن '{PHONE_NUMBER_TO_ENTER}' به صورت خودکار وارد شد.")
                logger.log("🔑 لطفاً کد تایید ارسال شده را در پنجره مرورگر وارد کنید.")
                logger.log("✅ پس از اینکه ایتا به صورت خودکار وارد شد و صفحه اصلی چت‌ها بارگذاری شد،")
                logger.log("⌨️ دکمه 'ادامه (پس از ورود دستی)' را در این برنامه فشار دهید.")
                await login_event.wait()
                login_event.clear()
                chat_list_container_selector = '#chatlist-container'
                await page.wait_for_selector(chat_list_container_selector, state='visible', timeout=60000)
                logger.log("✅ ورود با موفقیت تأیید شد. ادامه عملیات...")
            except Exception as e_login:
                logger.log(f"❌ خطا در مرحله ورود: {e_login}")
                if page: await page.screenshot(path='tahvil_error_login_stage.png')
                return

            try:
                main_search_input_selector = 'input.input-search-input[placeholder="جستجو"]'
                search_input_locator = page.locator(main_search_input_selector)
                await search_input_locator.wait_for(state='visible', timeout=20000)
                await search_input_locator.click(timeout=10000)
                await search_input_locator.fill(GROUP_NAME, timeout=10000)
                group_item_selector_main_search = f'li.rp.chatlist-chat:has(span.peer-title > i:text-is("{GROUP_NAME}"))'
                group_element_locator = page.locator(group_item_selector_main_search).first
                await group_element_locator.wait_for(state='attached', timeout=15000)
                try: await group_element_locator.scroll_into_view_if_needed(timeout=5000)
                except: pass
                await group_element_locator.wait_for(state='visible', timeout=20000)
                await group_element_locator.click(timeout=10000)
                target_group_page_content_selector = ".bubble-content"
                await page.wait_for_selector(target_group_page_content_selector, state='visible', timeout=15000)
                logger.log(f"✅ با موفقیت وارد گروه '{GROUP_NAME}' شدید.")
            except Exception as e_search_group:
                logger.log(f"❌ خطا در مرحله جستجو و ورود به گروه: {e_search_group}")
                if page: await page.screenshot(path='tahvil_error_search_group.png')
                return

            target_message_text = None
            logger.log("\n--- شروع مرحله ۳: پیدا کردن پیام هدف در گروه ---")
            try:
                message_bubble_selector = "div.bubble"
                message_text_in_bubble_selector = "div.message"
                chat_scrollable_area_locator = page.locator('//div[contains(@class, "bubbles")]/div[contains(@class, "scrollable-y")]').first
                if await chat_scrollable_area_locator.count() > 0 :
                    for _ in range(2):
                        await chat_scrollable_area_locator.evaluate("el => el.scrollTop = 0")
                        await page.wait_for_timeout(2000)
                all_message_bubbles = page.locator(message_bubble_selector)
                count = await all_message_bubbles.count()
                logger.log(f"تعداد {count} حباب پیام در گروه یافت شد. در حال بررسی از آخر...")
                for i in range(count - 1, -1, -1):
                    single_bubble_locator = all_message_bubbles.nth(i)
                    message_text_locator = single_bubble_locator.locator(message_text_in_bubble_selector)
                    if await message_text_locator.count() > 0:
                        try:
                            text_content = await message_text_locator.inner_text(timeout=3000)
                            text_to_check = normalize_persian_text(text_content.strip() if text_content else "")
                            if text_to_check and MESSAGE_PREFIX and text_to_check.startswith(MESSAGE_PREFIX):
                                target_message_text = text_content.strip()
                                logger.log(f"🎯 پیام هدف پیدا شد: '{target_message_text[:50]}...'")
                                break
                        except: pass
                if not target_message_text: logger.log(f"⚠️ پیام با پیشوند '{MESSAGE_PREFIX}' در گروه '{GROUP_NAME}' پیدا نشد.")
            except Exception as e_find_msg:
                logger.log(f"❌ خطایی در هنگام جستجوی پیام هدف در گروه '{GROUP_NAME}' رخ داد: {e_find_msg}")

            logger.log("\n--- شروع مرحله ۴: استخراج و ارسال پیام خصوصی ---")
            if target_message_text:
                usernames_to_message = extract_usernames_from_text(target_message_text)
                if not usernames_to_message:
                    logger.log("⚠️ هیچ نام کاربری (@username) در پیام پیدا نشد.")
                else:
                    for uname in usernames_to_message:
                        status_updater.update_status(uname, "در صف")

                    hashtagged_prefix = f"#{MESSAGE_PREFIX}"
                    final_message_to_send = f"{BASE_DM_MESSAGE}\n{hashtagged_prefix}"
                    logger.log(f"📨 آماده‌سازی برای ارسال پیام به {len(usernames_to_message)} کاربر.")

                    for username_with_at in usernames_to_message:
                        clean_username = username_with_at.lstrip('@')
                        if clean_username.lower() == YOUR_OWN_USERNAME.lower():
                            logger.log(f"ℹ️ از ارسال پیام به '{username_with_at}' (خودتان) صرف نظر شد.")
                            status_updater.update_status(username_with_at, "صرف‌نظر شد (خودتان)")
                            continue

                        status_updater.update_status(username_with_at, "در حال ارسال...")
                        logger.log(f"🗣️ در حال تلاش برای ارسال پیام به {username_with_at}...")
                        try:
                            await search_input_locator.click(timeout=10000)
                            await search_input_locator.fill("")
                            await page.wait_for_timeout(500)
                            await search_input_locator.fill(username_with_at)

                            user_item_selector_dm = f'li.rp.chatlist-chat:has(p.dialog-subtitle > span.user-last-message > i:has-text("{username_with_at}"))'
                            user_chat_element_locator_dm = page.locator(user_item_selector_dm).first
                            await user_chat_element_locator_dm.wait_for(state='attached', timeout=15000)
                            try: await user_chat_element_locator_dm.scroll_into_view_if_needed(timeout=5000)
                            except: pass
                            await user_chat_element_locator_dm.wait_for(state='visible', timeout=20000)
                            await user_chat_element_locator_dm.click(timeout=10000)

                            dm_message_input_selector = 'div.input-message-input[contenteditable="true"]:not(.input-field-input-fake)'
                            dm_input_area_locator = page.locator(dm_message_input_selector)
                            await dm_input_area_locator.wait_for(state='visible', timeout=15000)
                            await dm_input_area_locator.fill(final_message_to_send)
                            await dm_input_area_locator.press('Enter')
                            logger.log(f"📨 پیام به {username_with_at} ارسال شد.")
                            status_updater.update_status(username_with_at, "ارسال موفق")

                            delay_seconds = uniform(MIN_DELAY_S, MAX_DELAY_S)
                            logger.log(f"   تاخیر {delay_seconds:.2f} ثانیه‌ای...")
                            await page.wait_for_timeout(int(delay_seconds * 1000))

                        except Exception as e_dm_user:
                            error_msg_dm = f"خطا در پردازش کاربر '{username_with_at}': {e_dm_user}"
                            logger.log(f"❌ {error_msg_dm}")
                            status_updater.update_status(username_with_at, "خطا در ارسال", str(e_dm_user)[:50])
                            log_failed_dm_to_file_and_gui(username_with_at, FAILED_DMS_FILE, logger, str(e_dm_user))
                            if page: await page.screenshot(path=f'tahvil_error_dm_{clean_username}.png')
                        finally:
                            try:
                                if await search_input_locator.is_visible(timeout=1000):
                                    await search_input_locator.click(timeout=3000)
                                    await search_input_locator.fill("")
                                    await page.wait_for_timeout(200)
                            except: pass
                    logger.log("🎉 عملیات ارسال پیام‌ها به پایان رسید.")
            else:
                if not target_message_text:
                    logger.log("ℹ️ پیام هدف یافت نشد، پیامی ارسال نمی‌شود.")

            logger.log("\n********************************************************************")
            logger.log("⏹️ تمام عملیات برنامه‌ریزی شده به پایان رسید.")
            logger.log("   برای بستن مرورگر، دکمه 'بستن مرورگر و خروج از ربات' را در این برنامه فشار دهید.")
            await exit_event.wait()
            exit_event.clear()

        except PlaywrightTimeoutError as pte:
            logger.log(f"❌ خطای تایم‌اوت Playwright رخ داد: {pte}")
            if page: await page.screenshot(path='tahvil_error_playwright_timeout.png')
        except Exception as e:
            logger.log(f"❌ یک خطای غیرمنتظره کلی در ربات تحویل رخ داد: {e}")
            if page: await page.screenshot(path='tahvil_error_unknown_general.png')
        finally:
            if browser and browser.is_connected():
                await browser.close()
                logger.log("مرورگر بسته شد.")
            else: logger.log("مرورگر قبلاً بسته شده یا متصل نبوده است.")
            logger.log("ربات تحویل خاتمه یافت.")

async def run_id_sender_bot_async(config, logger, status_updater, login_event, exit_event):
    logger.log("ربات ارسال پیام مستقیم شروع به کار کرد...")
    status_updater.clear_table()
    browser = None
    page = None

    YOUR_OWN_USERNAME = config["YOUR_OWN_USERNAME"]
    DIRECT_MESSAGE_TO_SEND = normalize_persian_text(config["DIRECT_MESSAGE_TO_SEND"])
    EXCEL_FILE_PATH = config["EXCEL_FILE_PATH"]
    FAILED_DMS_FILE = config["FAILED_DMS_FILE"]
    PHONE_NUMBER_TO_ENTER = config["PHONE_NUMBER_TO_ENTER"]
    MIN_DELAY_S = config["MIN_DELAY_S"]
    MAX_DELAY_S = config["MAX_DELAY_S"]

    async with async_playwright() as p:
        try:
            logger.log("در حال اجرای مرورگر...")
            browser = await p.chromium.launch(headless=False, slow_mo=250)
            context = await browser.new_context()
            page = await context.new_page()
            logger.log("مرورگر با موفقیت اجرا شد.")

            try:
                logger.log("در حال باز کردن صفحه وب ایتا...")
                await page.goto("https://web.eitaa.com/", timeout=60000)
                if PHONE_NUMBER_TO_ENTER:
                    phone_field_selector = 'div.input-field-phone div.input-field-input[contenteditable="true"]'
                    try:
                        phone_input_locator = page.locator(phone_field_selector)
                        await phone_input_locator.wait_for(state='visible', timeout=10000)
                        await phone_input_locator.fill(PHONE_NUMBER_TO_ENTER)
                        await phone_input_locator.press('Enter')
                        logger.log(f"شماره تلفن '{PHONE_NUMBER_TO_ENTER}' وارد شد (اگر فیلد پیدا شده باشد).")
                    except: pass
                logger.log("🔑 لطفاً مراحل ورود را در مرورگر تکمیل و سپس دکمه 'ادامه' را در برنامه بزنید.")
                await login_event.wait()
                login_event.clear()
                chat_list_container_selector = '#chatlist-container'
                await page.wait_for_selector(chat_list_container_selector, state='visible', timeout=60000)
                logger.log("✅ ورود با موفقیت تأیید شد.")
            except Exception as e_login:
                logger.log(f"❌ خطا در مرحله ورود: {e_login}")
                if page: await page.screenshot(path='id_error_login_stage.png')
                return

            usernames_to_message = []
            try:
                logger.log(f" خواندن آی‌دی‌ها از '{EXCEL_FILE_PATH}'...")
                df = pd.read_excel(EXCEL_FILE_PATH, header=None, names=['username_col'])
                usernames_to_message = [str(uname).strip() for uname in df['username_col']
                                        if pd.notna(uname) and isinstance(uname, str) and str(uname).strip().startswith('@')]
                if not usernames_to_message:
                    logger.log(f"⚠️ هیچ نام کاربری معتبری در '{EXCEL_FILE_PATH}' یافت نشد.")
                    return
                logger.log(f"✅ {len(usernames_to_message)} نام کاربری از اکسل خوانده شد.")
                for uname in usernames_to_message:
                    status_updater.update_status(uname, "در صف")
            except FileNotFoundError:
                logger.log(f"❌ فایل اکسل '{EXCEL_FILE_PATH}' پیدا نشد.")
                return
            except Exception as e_excel:
                logger.log(f"❌ خطا در خواندن فایل اکسل: {e_excel}")
                if page: await page.screenshot(path='id_error_excel_reading.png')
                return

            if usernames_to_message:
                logger.log(f"📨 آماده‌سازی برای ارسال پیام به {len(usernames_to_message)} کاربر.")
                main_search_input_selector = 'input.input-search-input[placeholder="جستجو"]'
                search_input_locator = page.locator(main_search_input_selector)
                dm_message_input_selector = 'div.input-message-input[contenteditable="true"]:not(.input-field-input-fake)'

                for username_with_at in usernames_to_message:
                    clean_username = username_with_at.lstrip('@')
                    if clean_username.lower() == YOUR_OWN_USERNAME.lower():
                        logger.log(f"ℹ️ صرف نظر از ارسال به '{username_with_at}' (خودتان).")
                        status_updater.update_status(username_with_at, "صرف‌نظر شد (خودتان)")
                        continue

                    status_updater.update_status(username_with_at, "در حال ارسال...")
                    logger.log(f"🗣️ تلاش برای ارسال پیام به {username_with_at}...")
                    try:
                        await search_input_locator.wait_for(state='visible', timeout=10000)
                        await search_input_locator.click(timeout=10000)
                        await search_input_locator.fill("")
                        await page.wait_for_timeout(500)
                        await search_input_locator.fill(username_with_at)
                        await page.wait_for_timeout(4000)

                        user_item_selector_dm = f'li.rp.chatlist-chat:has(p.dialog-subtitle > span.user-last-message > i:has-text("{username_with_at}"))'
                        user_chat_element_locator_dm = page.locator(user_item_selector_dm).first
                        await user_chat_element_locator_dm.wait_for(state='attached', timeout=15000)
                        try: await user_chat_element_locator_dm.scroll_into_view_if_needed(timeout=5000)
                        except: pass
                        await user_chat_element_locator_dm.wait_for(state='visible', timeout=20000)
                        await user_chat_element_locator_dm.click(timeout=10000)

                        dm_input_area_locator = page.locator(dm_message_input_selector)
                        await dm_input_area_locator.wait_for(state='visible', timeout=15000)
                        await dm_input_area_locator.fill(DIRECT_MESSAGE_TO_SEND)
                        await dm_input_area_locator.press('Enter')
                        logger.log(f"📨 پیام به {username_with_at} ارسال شد.")
                        status_updater.update_status(username_with_at, "ارسال موفق")

                        delay_seconds = uniform(MIN_DELAY_S, MAX_DELAY_S)
                        logger.log(f"   تاخیر {delay_seconds:.2f} ثانیه‌ای...")
                        await page.wait_for_timeout(int(delay_seconds * 1000))
                    except Exception as e_dm_user:
                        error_msg_dm = f"خطا در پردازش '{username_with_at}': {e_dm_user}"
                        logger.log(f"❌ {error_msg_dm}")
                        status_updater.update_status(username_with_at, "خطا در ارسال", str(e_dm_user)[:50])
                        log_failed_dm_to_file_and_gui(username_with_at, FAILED_DMS_FILE, logger, str(e_dm_user))
                        if page: await page.screenshot(path=f'id_error_dm_direct_{clean_username}.png')
                    finally:
                        try:
                            if await search_input_locator.is_visible(timeout=1000):
                                await search_input_locator.click(timeout=3000)
                                await search_input_locator.fill("")
                                await page.wait_for_timeout(500)
                        except: pass
                logger.log("🎉 عملیات ارسال پیام‌ها پایان یافت.")

            logger.log("⏹️ عملیات ربات ارسال پیام مستقیم پایان یافت. برای بستن مرورگر، دکمه مربوطه را فشار دهید.")
            await exit_event.wait()
            exit_event.clear()

        except PlaywrightTimeoutError as pte:
            logger.log(f"❌ خطای تایم‌اوت Playwright: {pte}")
            if page: await page.screenshot(path='id_error_playwright_timeout.png')
        except Exception as e:
            logger.log(f"❌ خطای کلی در ربات ارسال پیام مستقیم: {e}")
            if page: await page.screenshot(path='id_error_unknown_general.png')
        finally:
            if browser and browser.is_connected():
                await browser.close()
                logger.log("مرورگر بسته شد.")
            else: logger.log("مرورگر قبلاً بسته شده یا متصل نبوده است.")
            logger.log("ربات ارسال پیام مستقیم خاتمه یافت.")