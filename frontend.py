import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import asyncio
import threading
from datetime import datetime
from utils import convert_phone_number_format
from backend import login_to_eitaa, close_browser, run_tahvil_bot_async, run_id_sender_bot_async

class TextWithRightClickMenu:
    def __init__(self, widget):
        self.widget = widget
        self.menu = tk.Menu(widget, tearoff=0)
        self.menu.add_command(label="برش", command=self.cut)
        self.menu.add_command(label="کپی", command=self.copy)
        self.menu.add_command(label="چسباندن", command=self.paste)
        self.menu.add_separator()
        self.menu.add_command(label="انتخاب همه", command=self.select_all)

        widget.bind("<Button-3>", self.show_menu)
        widget.bind("<Control-a>", self.select_all_event)
        widget.bind("<Control-x>", self.cut_event)
        widget.bind("<Control-c>", self.copy_event)
        widget.bind("<Control-v>", self.paste_event)

    def show_menu(self, event):
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def cut(self):
        self.widget.event_generate("<<Cut>>")
    def copy(self):
        self.widget.event_generate("<<Copy>>")
    def paste(self):
        self.widget.event_generate("<<Paste>>")
    def select_all(self):
        if isinstance(self.widget, tk.Entry):
            self.widget.select_range(0, tk.END)
        elif isinstance(self.widget, tk.Text):
            self.widget.tag_add("sel", "1.0", "end")

    def cut_event(self, event): self.cut()
    def copy_event(self, event): self.copy()
    def paste_event(self, event): self.paste()
    def select_all_event(self, event):
        self.select_all()
        return "break"

class GuiLogger:
    def __init__(self, text_widget, app_root):
        self.text_widget = text_widget
        self.app_root = app_root
        self.text_widget.configure(state='disabled')
        self.text_widget.tag_configure("right", justify="right")

    def log(self, message):
        def _update_text():
            self.text_widget.configure(state='normal')
            self.text_widget.insert(tk.END, str(message) + "\n", "right")
            self.text_widget.see(tk.END)
            self.text_widget.configure(state='disabled')
        self.app_root.after(0, _update_text)

class StatusTableUpdater:
    def __init__(self, treeview_widget, app_root):
        self.tree = treeview_widget
        self.app_root = app_root
        self.item_ids = {}

    def _update_treeview_thread_safe(self, action, username, status, details=""):
        now_time = datetime.now().strftime('%H:%M:%S')
        display_details = f"{details} ({now_time})"
        if action == "add_or_update":
            if username in self.item_ids:
                self.tree.item(self.item_ids[username], values=(username, status, display_details))
            else:
                item_id = self.tree.insert("", 0, values=(username, status, display_details))
                self.item_ids[username] = item_id
        elif action == "clear":
            for i in self.tree.get_children(): self.tree.delete(i)
            self.item_ids.clear()
        if self.tree.get_children(): self.tree.see(self.tree.get_children()[0])

    def update_status(self, username, status, details=""):
        self.app_root.after(0, self._update_treeview_thread_safe, "add_or_update", username, status, details)

    def clear_table(self):
        self.app_root.after(0, self._update_treeview_thread_safe, "clear", "", "")

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Eitaa Bot Manager")
        self.geometry("950x750")

        self.style = ttk.Style(self)
        self.style.theme_use('clam')
        self.configure_styles()

        self.browser = None
        self.page = None
        self.bot_thread = None
        self.bot_loop = None

        self.main_container = ttk.Frame(self)
        self.main_container.pack(fill=tk.BOTH, expand=True)

        self._create_login_view()
        self._create_main_view()

        self.show_login_view()

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def configure_styles(self):
        self.style.configure("TLabel", anchor="e", font=("Tahoma", 9))
        self.style.configure("TEntry", font=("Tahoma", 9))
        self.style.configure("TButton", font=("Tahoma", 9))
        self.style.configure("Accent.TButton", font=("Arial", 10, "bold"), foreground="white", background="#0078D7")
        self.style.configure("Treeview.Heading", anchor="e", font=("Tahoma", 9, 'bold'))
        self.style.configure("Treeview", font=("Tahoma", 9), rowheight=25)

    def _create_login_view(self):
        self.login_frame = ttk.Frame(self.main_container, padding="40")

        ttk.Label(self.login_frame, text="ورود به ایتا", font=("Tahoma", 16, "bold")).pack(pady=20)

        phone_frame = ttk.Frame(self.login_frame)
        phone_frame.pack(pady=10)

        self.phone_number_var = tk.StringVar(value="09012195787")
        ttk.Label(phone_frame, text=": شماره تلفن").pack(side=tk.RIGHT, padx=5)
        phone_entry = ttk.Entry(phone_frame, textvariable=self.phone_number_var, width=30, justify=tk.RIGHT)
        phone_entry.pack(side=tk.LEFT, expand=True, fill=tk.X)
        TextWithRightClickMenu(phone_entry)

        self.login_button = ttk.Button(self.login_frame, text="ورود", command=self.start_login_thread, style="Accent.TButton")
        self.login_button.pack(pady=20)

    def _create_main_view(self):
        self.main_app_frame = ttk.Frame(self.main_container, padding="5")

        top_bar = ttk.Frame(self.main_app_frame)
        top_bar.pack(fill=tk.X, padx=10, pady=5)

        self.connection_status_label = ttk.Label(top_bar, text="وضعیت: وارد نشده", foreground="red", font=("Tahoma", 10, "bold"))
        self.connection_status_label.pack(side=tk.RIGHT)

        self.logout_button = ttk.Button(top_bar, text="خروج از حساب", command=self.start_logout_thread, state=tk.DISABLED)
        self.logout_button.pack(side=tk.LEFT)

        self.notebook = ttk.Notebook(self.main_app_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.log_text_widget = scrolledtext.ScrolledText(self, wrap=tk.WORD, height=8, font=("Tahoma", 9))
        self.logger = GuiLogger(self.log_text_widget, self)
        TextWithRightClickMenu(self.log_text_widget)

        self.create_tahvil_tab()
        self.create_id_sender_tab()

        bottom_frame = ttk.Frame(self.main_app_frame)
        bottom_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        log_frame = ttk.LabelFrame(bottom_frame, text="لاگ عملیات", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True, side=tk.LEFT, padx=(0, 5))
        self.log_text_widget.pack(fill=tk.BOTH, expand=True)

        status_frame = ttk.LabelFrame(bottom_frame, text="وضعیت ارسال پیام‌ها", padding="5")
        status_frame.pack(fill=tk.BOTH, expand=True, side=tk.RIGHT)

        cols = ("نام کاربری", "وضعیت", "جزئیات/زمان")
        self.status_tree = ttk.Treeview(status_frame, columns=cols, show="headings", height=10)
        for col in cols:
            self.status_tree.heading(col, text=col, anchor=tk.E)
            self.status_tree.column(col, anchor=tk.E, width=150 if col=="نام کاربری" else 120 if col=="وضعیت" else 250, stretch=tk.NO if col!="جزئیات/زمان" else tk.YES)

        status_scrollbar = ttk.Scrollbar(status_frame, orient="vertical", command=self.status_tree.yview)
        self.status_tree.configure(yscrollcommand=status_scrollbar.set)
        status_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.status_tree.pack(fill=tk.BOTH, expand=True)

        self.status_updater = StatusTableUpdater(self.status_tree, self)

    def create_tahvil_tab(self):
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text="ارسال پیام از گروه")

        group_name_var = tk.StringVar(value="دوپلاس")
        message_prefix_var = tk.StringVar(value="ماژیک_ساعت")
        base_dm_var = tk.StringVar(value="سلام\nخرید شما رسیده، لطفا طبق ساعتهای اعلامی در گروه، برای تحویلشون اقدام کنید. 🌺")
        own_username_var = tk.StringVar(value="adminbahar")
        min_delay_var = tk.IntVar(value=3)
        max_delay_var = tk.IntVar(value=10)

        config_frame = ttk.LabelFrame(tab, text="تنظیمات ربات تحویل", padding=10)
        config_frame.pack(fill=tk.X, padx=5, pady=5)

        create_entry(config_frame, "نام گروه", group_name_var, 0)
        create_entry(config_frame, "پیشوند پیام", message_prefix_var, 1)
        dm_editor = create_entry(config_frame, "پیام خصوصی", base_dm_var, 2, is_text_area=True, height=4)
        create_entry(config_frame, "نام کاربری شما", own_username_var, 3)
        create_entry(config_frame, "حداقل تاخیر (ثانیه)", min_delay_var, 4)
        create_entry(config_frame, "حداکثر تاخیر (ثانیه)", max_delay_var, 5)

        start_button = ttk.Button(tab, text="شروع ربات تحویل", style="Accent.TButton", state=tk.DISABLED,
                                  command=lambda: self.start_bot_thread(
                                      run_tahvil_bot_async, {
                                          "GROUP_NAME": group_name_var.get(),
                                          "MESSAGE_PREFIX": message_prefix_var.get(),
                                          "BASE_DM_MESSAGE": dm_editor.get("1.0", tk.END).strip(),
                                          "YOUR_OWN_USERNAME": own_username_var.get(),
                                          "FAILED_DMS_FILE": "tahvil_failed_dms.txt",
                                          "MIN_DELAY_S": min_delay_var.get(),
                                          "MAX_DELAY_S": max_delay_var.get()
                                      }, start_button
                                  ))
        start_button.pack(pady=10)
        self.tahvil_start_button = start_button

    def create_id_sender_tab(self):
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text="ارسال پیام از اکسل")

        own_username_var = tk.StringVar(value="davody")
        direct_message_var = tk.StringVar(value="سلام\nممنون که توی گروه ما عضو شدین.\nخبرای خوبی تو راهه. 🌺.")
        excel_path_var = tk.StringVar()
        min_delay_var = tk.IntVar(value=5)
        max_delay_var = tk.IntVar(value=15)

        config_frame = ttk.LabelFrame(tab, text="تنظیمات ربات ارسال مستقیم", padding=10)
        config_frame.pack(fill=tk.X, padx=5, pady=5)

        create_entry(config_frame, "نام کاربری شما", own_username_var, 0)
        dm_editor = create_entry(config_frame, "پیام ارسالی", direct_message_var, 1, is_text_area=True, height=4)

        excel_frame = ttk.Frame(config_frame)
        excel_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=5)
        ttk.Label(excel_frame, text=": مسیر فایل اکسل").pack(side=tk.RIGHT)
        ttk.Button(excel_frame, text="انتخاب فایل...", command=lambda: self.browse_excel(excel_path_var)).pack(side=tk.LEFT)
        entry_excel = ttk.Entry(excel_frame, textvariable=excel_path_var, justify=tk.RIGHT)
        entry_excel.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        TextWithRightClickMenu(entry_excel)

        create_entry(config_frame, "حداقل تاخیر (ثانیه)", min_delay_var, 3)
        create_entry(config_frame, "حداکثر تاخیر (ثانیه)", max_delay_var, 4)

        start_button = ttk.Button(tab, text="شروع ربات ارسال مستقیم", style="Accent.TButton", state=tk.DISABLED,
                                  command=lambda: self.start_bot_thread(
                                      run_id_sender_bot_async, {
                                          "YOUR_OWN_USERNAME": own_username_var.get(),
                                          "DIRECT_MESSAGE_TO_SEND": dm_editor.get("1.0", tk.END).strip(),
                                          "EXCEL_FILE_PATH": excel_path_var.get(),
                                          "FAILED_DMS_FILE": "id_failed_dms.txt",
                                          "MIN_DELAY_S": min_delay_var.get(),
                                          "MAX_DELAY_S": max_delay_var.get()
                                      }, start_button
                                  ))
        start_button.pack(pady=10)
        self.id_sender_start_button = start_button

    def browse_excel(self, var):
        filepath = filedialog.askopenfilename(title="فایل اکسل را انتخاب کنید", filetypes=(("Excel files", "*.xlsx *.xls"), ("All files", "*.*")))
        if filepath: var.set(filepath)

    def show_login_view(self):
        self.main_app_frame.pack_forget()
        self.login_frame.pack(fill=tk.BOTH, expand=True)

    def show_main_view(self):
        self.login_frame.pack_forget()
        self.main_app_frame.pack(fill=tk.BOTH, expand=True)
        self.connection_status_label.config(text="وضعیت: متصل", foreground="green")
        self.logout_button.config(state=tk.NORMAL)
        self.tahvil_start_button.config(state=tk.NORMAL)
        self.id_sender_start_button.config(state=tk.NORMAL)

    def start_login_thread(self):
        phone_number = self.phone_number_var.get()
        converted_phone = convert_phone_number_format(phone_number)
        if not (converted_phone and converted_phone.startswith('989') and len(converted_phone) == 13):
            messagebox.showerror("خطا", "فرمت شماره تلفن صحیح نیست. مثال: 09123456789")
            return

        self.login_button.config(state=tk.DISABLED, text="در حال ورود...")
        self.logger.log(f"تلاش برای ورود با شماره: {converted_phone}")

        threading.Thread(target=self.run_login, args=(converted_phone,), daemon=True).start()

    def run_login(self, phone_number):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        browser, page = loop.run_until_complete(login_to_eitaa(self.logger, phone_number))
        loop.close()

        self.after(0, self.on_login_complete, browser, page)

    def on_login_complete(self, browser, page):
        self.login_button.config(state=tk.NORMAL, text="ورود")
        if browser and page:
            self.browser = browser
            self.page = page
            self.show_main_view()
        else:
            self.logger.log("❌ ورود ناموفق بود. لطفاً دوباره تلاش کنید.")

    def start_logout_thread(self):
        self.logout_button.config(state=tk.DISABLED)
        self.logger.log("در حال خروج از حساب...")
        threading.Thread(target=self.run_logout, daemon=True).start()

    def run_logout(self):
        if self.browser:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(close_browser(self.browser, self.logger))
            loop.close()
        self.after(0, self.on_logout_complete)

    def on_logout_complete(self):
        self.browser = None
        self.page = None
        self.show_login_view()
        self.connection_status_label.config(text="وضعیت: وارد نشده", foreground="red")
        self.tahvil_start_button.config(state=tk.DISABLED)
        self.id_sender_start_button.config(state=tk.DISABLED)
        self.logger.log("✅ با موفقیت از حساب خارج شدید.")

    def start_bot_thread(self, bot_function, config, button):
        if not self.page or not self.browser.is_connected():
            messagebox.showerror("خطا", "اتصال با مرورگر برقرار نیست. لطفاً ابتدا وارد شوید.")
            return

        button.config(state=tk.DISABLED)
        self.logout_button.config(state=tk.DISABLED)
        self.logger.log(f"شروع عملیات ربات: {bot_function.__name__}")

        self.bot_thread = threading.Thread(target=self.run_bot, args=(bot_function, config, button), daemon=True)
        self.bot_thread.start()

    def run_bot(self, bot_function, config, button):
        self.bot_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.bot_loop)
        try:
            self.bot_loop.run_until_complete(bot_function(self.page, config, self.logger, self.status_updater))
        except Exception as e:
            self.logger.log(f"❌ خطای بحرانی در ترد ربات: {e}")
        finally:
            self.bot_loop.close()
            self.after(0, self.on_bot_finished, button)

    def on_bot_finished(self, button):
        button.config(state=tk.NORMAL)
        self.logout_button.config(state=tk.NORMAL)
        self.logger.log("عملیات ربات پایان یافت.")
        self.bot_thread = None

    def on_closing(self):
        if self.browser:
            if messagebox.askyesno("خروج", "آیا می‌خواهید از حساب خود خارج شده و برنامه را ببندید؟"):
                self.start_logout_thread()
                self.after(1000, self.destroy)
        else:
            self.destroy()

def create_entry(parent, label, var, row, is_text_area=False, height=3):
    ttk.Label(parent, text=f": {label}").grid(row=row, column=1, padx=5, pady=5, sticky="w")
    if is_text_area:
        widget = tk.Text(parent, height=height, wrap=tk.WORD, font=("Tahoma", 9))
        widget.insert("1.0", var.get())
        TextWithRightClickMenu(widget)
        widget.grid(row=row, column=0, padx=5, pady=5, sticky="ew")
    else:
        widget = ttk.Entry(parent, textvariable=var, justify=tk.RIGHT)
        TextWithRightClickMenu(widget)
        widget.grid(row=row, column=0, padx=5, pady=5, sticky="ew")

    parent.grid_columnconfigure(0, weight=1)
    return widget

if __name__ == '__main__':
    app = App()
    app.mainloop()