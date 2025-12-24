import sqlite3
import json
from datetime import datetime

class Database:
    def __init__(self, db_name="eitaa_bot.db"):
        self.db_name = db_name
        self.init_database()
    
    def get_connection(self):
        """ایجاد اتصال به دیتابیس"""
        conn = sqlite3.connect(self.db_name, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_database(self):
        """ایجاد جداول مورد نیاز"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # جدول برای ذخیره مخاطبین اضافه شده قبلی
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS added_contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL UNIQUE,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                added_by_phone TEXT
            )
        ''')
        
        # جدول برای ذخیره گزارش‌های ارسال پیام
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dispatch_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                status TEXT NOT NULL,
                error_message TEXT,
                operation_type TEXT,
                message_content TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                phone_number TEXT
            )
        ''')
        
        # ایجاد ایندکس برای جستجوی سریع‌تر
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_contacts_phone ON added_contacts(phone)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_reports_user_id ON dispatch_reports(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_reports_timestamp ON dispatch_reports(timestamp)')
        
        conn.commit()
        conn.close()
    
    def is_contact_exists(self, phone):
        """بررسی وجود مخاطب در دیتابیس"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT id FROM added_contacts WHERE phone = ?', (phone,))
        result = cursor.fetchone()
        
        conn.close()
        return result is not None
    
    def add_contact(self, name, phone, added_by_phone=None):
        """اضافه کردن مخاطب جدید به دیتابیس"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR IGNORE INTO added_contacts (name, phone, added_by_phone)
                VALUES (?, ?, ?)
            ''', (name, phone, added_by_phone))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error adding contact to database: {e}")
            return False
    
    def filter_new_contacts(self, contacts_list, added_by_phone=None):
        """فیلتر کردن مخاطبین جدید (غیرتکراری)"""
        new_contacts = []
        duplicate_count = 0
        
        for contact in contacts_list:
            phone = contact.get('phone', '')
            name = contact.get('name', '')
            
            if phone and not self.is_contact_exists(phone):
                new_contacts.append(contact)
            else:
                duplicate_count += 1
        
        return new_contacts, duplicate_count
    
    def save_dispatch_report(self, user_id, status, error_message, operation_type, message_content, phone_number):
        """ذخیره گزارش ارسال در دیتابیس"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO dispatch_reports (user_id, status, error_message, operation_type, message_content, phone_number)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, status, error_message or "", operation_type or "", message_content or "", phone_number or ""))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error saving dispatch report: {e}")
            return False
    
    def get_dispatch_reports(self, limit=100, offset=0, status_filter=None, date_filter=None):
        """دریافت گزارش‌های ارسال"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        query = 'SELECT * FROM dispatch_reports'
        params = []
        
        conditions = []
        if status_filter:
            conditions.append('status = ?')
            params.append(status_filter)
        if date_filter:
            conditions.append('DATE(timestamp) = ?')
            params.append(date_filter)
        
        if conditions:
            query += ' WHERE ' + ' AND '.join(conditions)
        
        query += ' ORDER BY timestamp DESC LIMIT ? OFFSET ?'
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        reports = [dict(row) for row in cursor.fetchall()]
        
        # تعداد کل رکوردها
        count_query = 'SELECT COUNT(*) as count FROM dispatch_reports'
        if conditions:
            count_query += ' WHERE ' + ' AND '.join(conditions)
            cursor.execute(count_query, params[:-2])
        else:
            cursor.execute(count_query)
        
        total_count = cursor.fetchone()['count']
        
        conn.close()
        return reports, total_count
    
    def get_all_dispatch_reports(self):
        """دریافت تمام گزارش‌های ارسال"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM dispatch_reports ORDER BY timestamp DESC')
        reports = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return reports
    
    def get_contacts_statistics(self):
        """آمار مخاطبین"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) as total FROM added_contacts')
        total = cursor.fetchone()['total']
        
        cursor.execute('SELECT COUNT(DISTINCT phone) as unique_phones FROM added_contacts')
        unique = cursor.fetchone()['unique_phones']
        
        cursor.execute('''
            SELECT strftime('%Y-%m-%d', added_date) as date, COUNT(*) as count 
            FROM added_contacts 
            GROUP BY strftime('%Y-%m-%d', added_date) 
            ORDER BY date DESC 
            LIMIT 7
        ''')
        last_7_days = cursor.fetchall()
        
        conn.close()
        return {
            'total': total,
            'unique': unique,
            'last_7_days': [dict(row) for row in last_7_days]
        }
    
    def clear_database(self, table_name=None):
        """پاک کردن دیتابیس یا جدول خاص"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if table_name == 'contacts':
            cursor.execute('DELETE FROM added_contacts')
        elif table_name == 'reports':
            cursor.execute('DELETE FROM dispatch_reports')
        elif table_name is None:
            cursor.execute('DELETE FROM added_contacts')
            cursor.execute('DELETE FROM dispatch_reports')
        
        conn.commit()
        conn.close()
    
    def export_contacts_to_csv(self):
        """خروجی گرفتن از مخاطبین به فرمت CSV"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT name, phone, added_date, added_by_phone FROM added_contacts ORDER BY added_date DESC')
        contacts = cursor.fetchall()
        
        conn.close()
        return contacts

# ایجاد یک نمونه از دیتابیس
db = Database()