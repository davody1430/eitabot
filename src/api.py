"""
تعریف APIهای FastAPI
"""

import asyncio
import io
import tempfile
import os
import uvicorn
import pandas as pd
from datetime import datetime
from fastapi import FastAPI, Request, Form, BackgroundTasks, UploadFile, File
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from .state_manager import state, add_log
from .services import automation_worker, add_contacts_worker, process_contacts_excel
from database import db

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# --- API Routes ---
@app.get("/", response_class=HTMLResponse)
@app.get("/index.html", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/help.html", response_class=HTMLResponse)
async def help_page(request: Request):
    return templates.TemplateResponse("help.html", {"request": request})

@app.get("/get-status")
async def get_status():
    return {
        "current_step": state.current_step,
        "logs": state.logs,
        "otp_required": state.otp_required,
        "is_running": state.is_running
    }

@app.post("/start")
async def start_process(
    background_tasks: BackgroundTasks,
    phone: str = Form(...),
    mode: str = Form(...),
    group_name: str = Form(None),
    keyword: str = Form(None),
    msg: str = Form(None),
    min_d: str = Form(7),
    max_d: str = Form(16),
    your_own_username: str = Form(None)
):
    if state.is_running:
        return {"status": "already_running"}
    
    background_tasks.add_task(
        automation_worker, 
        phone, mode, group_name, keyword, msg, min_d, max_d, your_own_username
    )
    return {"status": "started"}

@app.post("/submit-otp")
async def submit_otp(code: str = Form(...)):
    state.otp_code = code
    state.otp_event.set()
    add_log("کد OTP دریافت شد.")
    return {"status": "ok"}

@app.post("/upload-excel")
async def upload_excel(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))
        
        usernames = []
        for u in df.iloc[:, 0].dropna().astype(str):
            username = u.strip()
            if username and not username.startswith('@'):
                username = '@' + username
            usernames.append(username)
        
        state.target_list = usernames
        state.dispatch_report.clear()
        
        add_log(f"فایل اکسل بارگذاری شد: {len(usernames)} کاربر")
        return {"count": len(usernames), "status": "success"}
    except Exception as e:
        add_log(f"خطا در بارگذاری اکسل: {str(e)}")
        return {"count": 0, "status": "error", "message": str(e)}

@app.post("/stop")
async def stop_bot():
    state.stop_requested = True
    add_log("درخواست توقف دریافت شد.")
    return {"status": "stopping"}

@app.get("/get-ready-messages")
async def get_ready_messages():
    return {"messages": state.ready_messages}

@app.post("/add-ready-message")
async def add_ready_message(message: str = Form(...)):
    state.ready_messages.append(message.strip()[:500])
    add_log(f"پیام جدید اضافه شد: {message.strip()[:30]}...")
    return {"status": "added", "message": message.strip()}

@app.post("/edit-ready-message")
async def edit_ready_message(index: int = Form(...), new_message: str = Form(...)):
    try:
        if 0 <= index < len(state.ready_messages):
            state.ready_messages[index] = new_message.strip()[:500]
            add_log(f"پیام ذخیره شده با اندیس {index} ویرایش شد.")
            return {"status": "success", "message": f"پیام با موفقیت ویرایش شد: {new_message.strip()[:30]}..."}
        else:
            return {"status": "error", "message": "اندیس پیام نامعتبر است."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/get-dispatch-report")
async def get_dispatch_report():
    db_reports = db.get_all_dispatch_reports()
    
    if db_reports:
        formatted_reports = []
        for report in db_reports:
            formatted_reports.append({
                "id": report.get("user_id", ""),
                "status": report.get("status", ""),
                "error": report.get("error_message", ""),
                "timestamp": report.get("timestamp", "")
            })
        return {"report": formatted_reports, "source": "database"}
    else:
        return {"report": state.dispatch_report, "source": "memory"}

@app.post("/clear-report")
async def clear_report():
    state.dispatch_report.clear()
    add_log("گزارش ارسال پاک شد.")
    return {"status": "cleared"}

@app.get("/export-report-excel")
async def export_report_excel():
    try:
        reports = db.get_all_dispatch_reports()
        
        if not reports and state.dispatch_report:
            temp_reports = []
            for report in state.dispatch_report:
                temp_reports.append({
                    "user_id": report.get("id", ""),
                    "status": report.get("status", ""),
                    "error_message": report.get("error", ""),
                    "timestamp": report.get("timestamp", ""),
                    "operation_type": "",
                    "message_content": "",
                    "phone_number": ""
                })
            reports = temp_reports
        
        df_data = []
        for report in reports:
            try:
                status_text = report.get("status", "unknown")
                
                status_fa = ""
                if status_text == "success":
                    status_fa = "موفق"
                elif status_text == "failed":
                    status_fa = "ناموفق"
                elif status_text == "skipped":
                    status_fa = "رد شده"
                else:
                    status_fa = "ناشناخته"
                
                df_data.append({
                    "آی‌دی کاربر": str(report.get("user_id", "")),
                    "وضعیت": status_fa,
                    "توضیحات": str(report.get("error_message", "")),
                    "نوع عملیات": str(report.get("operation_type", "")),
                    "زمان": str(report.get("timestamp", "")),
                    "شماره تلفن": str(report.get("phone_number", ""))
                })
            except Exception as e:
                add_log(f"⚠️ خطا در پردازش رکورد گزارش: {e}")
                continue
        
        if not df_data:
            df_data = [{
                "آی‌دی کاربر": "بدون داده",
                "وضعیت": "Info", 
                "توضیحات": "هنوز گزارشی در دیتابیس ثبت نشده است",
                "نوع عملیات": "",
                "زمان": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "شماره تلفن": ""
            }]
        
        df = pd.DataFrame(df_data)
        
        from io import BytesIO
        output = BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Report', index=False)
            worksheet = writer.sheets['Report']
            column_widths = {'A': 30, 'B': 15, 'C': 40, 'D': 15, 'E': 20, 'F': 20}
            for col, width in column_widths.items():
                worksheet.column_dimensions[col].width = width
        
        output.seek(0)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"eitaa_report_{timestamp}.xlsx"
        
        return StreamingResponse(
            output,
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={'Content-Disposition': f'attachment; filename="{filename}"'}
        )
        
    except Exception as e:
        add_log(f"❌ خطا در ایجاد فایل اکسل: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"خطا در ایجاد فایل: {str(e)}"}
        )

@app.get("/export-ids-excel")
async def export_ids_excel():
    try:
        reports = db.get_all_dispatch_reports()
        
        if not reports:
            return {"status": "error", "message": "گزارشی برای دانلود وجود ندارد"}
        
        ids_set = set()
        for report in reports:
            user_id = report.get("user_id", "").strip()
            if user_id:
                ids_set.add(user_id)
        
        ids = list(ids_set)
        
        if not ids:
            return {"status": "error", "message": "آی‌دی‌ای برای دانلود وجود ندارد"}
        
        df = pd.DataFrame({"آی‌دی کاربر": ids})
        
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
        file_path = temp_file.name
        temp_file.close()
        
        try:
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='لیست آی‌دی‌ها', index=False)
                worksheet = writer.sheets['لیست آی‌دی‌ها']
                worksheet.column_dimensions['A'].width = 30
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"eitaa_ids_{timestamp}.xlsx"
            
            return FileResponse(
                path=file_path,
                filename=filename,
                media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                headers={
                    'Content-Disposition': f'attachment; filename="{filename}"'
                }
            )
            
        except Exception as e:
            add_log(f"❌ خطا در ذخیره فایل اکسل: {str(e)}")
            csv_path = file_path.replace('.xlsx', '.csv')
            df.to_csv(csv_path, index=False, encoding='utf-8-sig')
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"eitaa_ids_{timestamp}.csv"
            return FileResponse(
                path=csv_path,
                filename=filename,
                media_type='text/csv',
                headers={
                    'Content-Disposition': f'attachment; filename="{filename}"'
                }
            )
        
    except Exception as e:
        add_log(f"❌ خطا در ایجاد فایل لیست آی‌دی‌ها: {str(e)}")
        return {"status": "error", "message": f"خطا در ایجاد فایل: {str(e)}"}
    
    finally:
        try:
            if 'file_path' in locals() and os.path.exists(file_path):
                os.unlink(file_path)
        except:
            pass
            
@app.get("/export-ids-simple")
async def export_ids_simple():
    try:
        reports = db.get_all_dispatch_reports()
        
        if not reports:
            return {"status": "error", "message": "گزارشی برای دانلود وجود ندارد"}
        
        ids_set = set()
        for report in reports:
            user_id = report.get("user_id", "").strip()
            if user_id:
                ids_set.add(user_id)
        
        ids = list(ids_set)
        
        if not ids:
            return {"status": "error", "message": "آی‌دی‌ای برای دانلود وجود ندارد"}
        
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode='w', encoding='utf-8')
        file_path = temp_file.name
        
        for user_id in ids:
            temp_file.write(user_id + '\n')
        
        temp_file.close()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"لیست_آی‌دی‌های_ایتا_{timestamp}.txt"
        
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type='text/plain',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"'
            }
        )
        
    except Exception as e:
        add_log(f"❌ خطا در ایجاد فایل متنی: {str(e)}")
        return {"status": "error", "message": f"خطا در ایجاد فایل: {str(e)}"}
    
    finally:
        try:
            if 'file_path' in locals() and os.path.exists(file_path):
                os.unlink(file_path)
        except:
            pass

@app.post("/upload-contacts-excel")
async def upload_contacts_excel(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        result = process_contacts_excel(contents)
        return result
        
    except Exception as e:
        add_log(f"خطا در بارگذاری اکسل مخاطبین: {str(e)}")
        return {"status": "error", "message": f"خطا در پردازش فایل: {str(e)}"}

@app.post("/start-add-contacts")
async def start_add_contacts(
    background_tasks: BackgroundTasks,
    phone: str = Form(...)
):
    if state.contacts_is_running:
        return {"status": "already_running", "message": "عملیات افزودن مخاطبین در حال اجراست"}
    
    if not state.filtered_contacts_list:
        return {"status": "error", "message": "لیست مخاطبین جدید خالی است. ممکن است همه مخاطبین قبلاً اضافه شده باشند یا فایل اکسل بارگذاری نشده باشد"}
    
    background_tasks.add_task(add_contacts_worker, phone)
    return {"status": "started", "message": "عملیات افزودن مخاطبین شروع شد"}

@app.get("/get-contacts-status")
async def get_contacts_status():
    return {
        "is_running": state.contacts_is_running,
        "progress": state.contacts_progress,
        "total": state.contacts_total,
        "status": state.contacts_status,
        "completed": state.contacts_completed,
        "success_count": state.contacts_success_count,
        "failed_count": state.contacts_failed_count,
        "error": state.contacts_error,
        "duplicate_count": state.duplicate_contacts_count,
        "filtered_count": len(state.filtered_contacts_list)
    }

@app.post("/clear-contacts-list")
async def clear_contacts_list():
    state.contacts_list = []
    state.filtered_contacts_list = []
    state.contacts_progress = 0
    state.contacts_total = 0
    state.contacts_completed = False
    state.contacts_error = None
    state.duplicate_contacts_count = 0
    add_log("لیست مخاطبین پاک شد.")
    return {"status": "cleared"}

@app.get("/get-database-stats")
async def get_database_stats():
    try:
        contacts_stats = db.get_contacts_statistics()
        reports, total_reports = db.get_dispatch_reports(limit=1)
        
        return {
            "status": "success",
            "contacts": contacts_stats,
            "reports_count": total_reports,
            "database_file": "eitaa_bot.db"
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/clear-database")
async def clear_database(table: str = Form(None)):
    try:
        db.clear_database(table)
        add_log(f"دیتابیس پاک شد: {table if table else 'تمام جداول'}")
        return {"status": "success", "message": f"دیتابیس با موفقیت پاک شد: {table if table else 'تمام جداول'}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/export-contacts-csv")
async def export_contacts_csv():
    try:
        contacts = db.export_contacts_to_csv()
        
        if not contacts:
            return {"status": "error", "message": "هیچ مخاطبی در دیتابیس وجود ندارد"}
        
        import csv
        from io import StringIO
        
        output = StringIO()
        writer = csv.writer(output)
        
        writer.writerow(['نام', 'شماره تلفن', 'تاریخ اضافه شدن', 'اضافه شده توسط'])
        
        for contact in contacts:
            writer.writerow(contact)
        
        output.seek(0)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"eitaa_contacts_{timestamp}.csv"
        
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type='text/csv',
            headers={'Content-Disposition': f'attachment; filename="{filename}"'}
        )
        
    except Exception as e:
        add_log(f"❌ خطا در ایجاد فایل CSV: {str(e)}")
        return {"status": "error", "message": f"خطا در ایجاد فایل: {str(e)}"}