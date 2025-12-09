import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import asyncio
import threading
from datetime import datetime
from utils import convert_phone_number_format
from backend import run_tahvil_bot_async, run_id_sender_bot_async

class ThemeManager:
    THEMES = {
        'dark': {
            'bg': '#2b2b2b', 'fg': '#ffffff', 'entry_bg': '#3c3c3c', 'entry_fg': '#ffffff',
            'button_bg': '#0078D7', 'button_fg': '#ffffff', 'tree_bg': '#2b2b2b', 'tree_fg': '#ffffff',
            'tree_heading_bg': '#3c3c3c', 'tree_heading_fg': '#ffffff', 'label_frame_bg': '#2b2b2b',
            'label_frame_fg': '#ffffff', 'scrollbar_bg': '#3c3c3c', 'scrollbar_trough': '#2b2b2b',
            'text_bg': '#3c3c3c', 'text_fg': '#ffffff', 'text_insert': '#ffffff', 'accent': '#0078D7'
        },
        'light': {
            'bg': '#f5f5f5', 'fg': '#000000', 'entry_bg': '#ffffff', 'entry_fg': '#000000',
            'button_bg': '#0078D7', 'button_fg': '#ffffff', 'tree_bg': '#ffffff', 'tree_fg': '#000000',
            'tree_heading_bg': '#e0e0e0', 'tree_heading_fg': '#000000', 'label_frame_bg': '#f5f5f5',
            'label_frame_fg': '#000000', 'scrollbar_bg': '#d0d0d0', 'scrollbar_trough': '#f0f0f0',
            'text_bg': '#ffffff', 'text_fg': '#000000', 'text_insert': '#000000', 'accent': '#0078D7'
        }
    }

    def __init__(self, root):
        self.root = root
        self.current_theme = 'light'
        self.widgets = []

    def register_widget(self, widget, widget_type):
        self.widgets.append((widget, widget_type))

    def switch_theme(self, theme_name='dark'):
        if theme_name not in self.THEMES:
            theme_name = 'light'
        self.current_theme = theme_name
        theme = self.THEMES[theme_name]
        self.apply_theme(theme)

    def apply_theme(self, theme):
        self.root.configure(bg=theme['bg'])
        for widget, widget_type in self.widgets:
            try:
                if widget_type == 'frame': widget.configure(bg=theme['bg'])
                elif widget_type == 'label': widget.configure(bg=theme['bg'], fg=theme['fg'])
                elif widget_type == 'button':
                    widget.configure(background=theme['button_bg'], foreground=theme['button_fg'],
                                     activebackground=theme['accent'], activeforeground=theme['button_fg'])
                elif widget_type == 'entry':
                    widget.configure(bg=theme['entry_bg'], fg=theme['entry_fg'], insertbackground=theme['text_insert'])
                elif widget_type == 'text':
                    widget.configure(bg=theme['text_bg'], fg=theme['text_fg'], insertbackground=theme['text_insert'])
                elif widget_type == 'treeview':
                    widget.configure(bg=theme['tree_bg'], fg=theme['tree_fg'], fieldbackground=theme['tree_bg'])
                elif widget_type == 'scrollbar':
                    widget.configure(bg=theme['scrollbar_bg'], troughcolor=theme['scrollbar_trough'])
                elif widget_type == 'label_frame':
                    widget.configure(background=theme['label_frame_bg'], foreground=theme['label_frame_fg'])
            except: continue

        style = ttk.Style()
        style.theme_use('clam')
        if self.current_theme == 'dark':
            style.configure("TLabel", background=theme['bg'], foreground=theme['fg'])
            style.configure("TFrame", background=theme['bg'])
            style.configure("TLabelframe", background=theme['bg'], foreground=theme['fg'])
            style.configure("TLabelframe.Label", background=theme['bg'], foreground=theme['fg'])
            style.configure("Treeview", background=theme['tree_bg'], foreground=theme['tree_fg'], fieldbackground=theme['tree_bg'])
            style.configure("Treeview.Heading", background=theme['tree_heading_bg'], foreground=theme['tree_heading_fg'])
            style.map('Treeview', background=[('selected', theme['accent'])])
        else:
            style.configure("TLabel", background=theme['bg'], foreground=theme['fg'])
            style.configure("TFrame", background=theme['bg'])
            style.configure("Treeview", background=theme['tree_bg'], foreground=theme['tree_fg'])

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

class BaseBotWindow(tk.Toplevel):
    def __init__(self, master, title):
        super().__init__(master)
        self.master_app = master
        self.title(title)
        self.geometry("900x700")

        self.login_event = asyncio.Event()
        self.exit_event = asyncio.Event()
        self.bot_thread = None
        self.bot_loop = None

        self.style = ttk.Style(self)
        self.style.theme_use('clam')

        main_container_frame = ttk.Frame(self, padding="5")
        main_container_frame.pack(fill=tk.BOTH, expand=True)

        settings_frame_container = ttk.Frame(main_container_frame)
        settings_frame_container.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 10), pady=5)

        config_outer_frame = ttk.LabelFrame(settings_frame_container, text="تنظیمات ربات", padding="10")
        config_outer_frame.pack(fill="x", anchor='ne', pady=(0,5))
        self.config_frame = ttk.Frame(config_outer_frame)
        self.config_frame.pack(fill="x")

        display_frame_container = ttk.Frame(main_container_frame)
        display_frame_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=5)

        status_frame = ttk.LabelFrame(display_frame_container, text="وضعیت ارسال پیام‌ها", padding="5")
        status_frame.pack(fill=tk.BOTH, expand=True, pady=(0,5))

        cols = ("نام کاربری", "وضعیت", "جزئیات/زمان")
        self.status_tree = ttk.Treeview(status_frame, columns=cols, show="headings", height=10)

        for col_name in cols:
            self.status_tree.heading(col_name, text=col_name, anchor=tk.E)
            if col_name == "نام کاربری": self.status_tree.column(col_name, anchor=tk.E, width=150, stretch=tk.NO)
            elif col_name == "وضعیت": self.status_tree.column(col_name, anchor=tk.E, width=120, stretch=tk.NO)
            else: self.status_tree.column(col_name, anchor=tk.E, width=250)

        status_scrollbar_y = ttk.Scrollbar(status_frame, orient="vertical", command=self.status_tree.yview)
        status_scrollbar_x = ttk.Scrollbar(status_frame, orient="horizontal", command=self.status_tree.xview)
        self.status_tree.configure(yscrollcommand=status_scrollbar_y.set, xscrollcommand=status_scrollbar_x.set)
        status_scrollbar_y.pack(side=tk.LEFT, fill=tk.Y)
        self.status_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        status_scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X, before=self.status_tree)

        self.status_updater = StatusTableUpdater(self.status_tree, self)

        log_frame = ttk.LabelFrame(display_frame_container, text="لاگ عملیات", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(5,0))
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=8, font=("Tahoma", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.logger = GuiLogger(self.log_text, self)

        control_frame = ttk.Frame(settings_frame_container, padding="5")
        control_frame.pack(fill="x", side=tk.BOTTOM, anchor='se')

        self.start_button = ttk.Button(control_frame, text="شروع ربات", command=self.start_bot_thread_wrapper, style="Accent.TButton")
        self.start_button.pack(side=tk.RIGHT, padx=2, pady=5)

        self.login_continue_button = ttk.Button(control_frame, text="ادامه (پس از ورود)", command=lambda: self.set_async_event(self.login_event))
        self.login_continue_button.pack(side=tk.RIGHT, padx=2, pady=5)
        self.login_continue_button.config(state=tk.DISABLED)

        self.exit_bot_button = ttk.Button(control_frame, text="بستن مرورگر و خروج", command=lambda: self.set_async_event(self.exit_event))
        self.exit_bot_button.pack(side=tk.RIGHT, padx=2, pady=5)
        self.exit_bot_button.config(state=tk.DISABLED)

        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.style.configure("Accent.TButton", font=("Arial", 10, "bold"), foreground="white", background="#0078D7")
        self.style.configure("TLabel", anchor="e", font=("Tahoma", 9))
        self.style.configure("TEntry", font=("Tahoma", 9))
        self.style.configure("TButton", font=("Tahoma", 9))
        self.style.configure("Treeview.Heading", anchor="e", font=("Tahoma", 9, 'bold'))
        self.style.configure("Treeview", font=("Tahoma", 9), rowheight=25)

    def create_entry(self, parent, label_text, var, row, col_label=1, col_entry=0, width=30, is_text_area=False, text_area_height=3):
        lbl = ttk.Label(parent, text=label_text + " :")
        lbl.grid(row=row, column=col_label, padx=(0,5), pady=3, sticky="e")

        if is_text_area:
            widget = tk.Text(parent, height=text_area_height, width=width, wrap=tk.WORD, relief=tk.SOLID, borderwidth=1, font=("Tahoma", 9))
            widget.tag_configure("right", justify="right")
            widget.insert(tk.END, var.get(), "right")
            context_menu = tk.Menu(widget, tearoff=0)
            context_menu.add_command(label="کپی", command=lambda: self.copy_to_clipboard(widget))
            context_menu.add_command(label="برش", command=lambda: self.cut_to_clipboard(widget))
            context_menu.add_command(label="چسباندن", command=lambda: self.paste_from_clipboard(widget))
            context_menu.add_separator()
            context_menu.add_command(label="انتخاب همه", command=lambda: self.select_all_text(widget))
            widget.bind("<Button-3>", lambda e: self.show_context_menu(e, context_menu))
            widget.bind('<Control-c>', lambda e: (self.copy_to_clipboard(widget), "break"))
            widget.bind('<Control-v>', lambda e: (self.paste_from_clipboard(widget), "break"))
            widget.bind('<Control-x>', lambda e: (self.cut_to_clipboard(widget), "break"))
            widget.bind('<Control-a>', lambda e: (self.select_all_text(widget), "break"))
        else:
            widget = ttk.Entry(parent, textvariable=var, width=width, justify=tk.RIGHT, font=("Tahoma", 9))
            context_menu = tk.Menu(widget, tearoff=0)
            context_menu.add_command(label="کپی", command=lambda: widget.event_generate('<<Copy>>'))
            context_menu.add_command(label="برش", command=lambda: widget.event_generate('<<Cut>>'))
            context_menu.add_command(label="چسباندن", command=lambda: widget.event_generate('<<Paste>>'))
            context_menu.add_command(label="انتخاب همه", command=lambda: widget.select_range(0, tk.END))
            widget.bind("<Button-3>", lambda e: context_menu.tk_popup(e.x_root, e.y_root))

        widget.grid(row=row, column=col_entry, padx=(5,0), pady=3, sticky="ew")
        parent.grid_columnconfigure(col_entry, weight=1)
        return widget

    def show_context_menu(self, event, menu):
        try: menu.tk_popup(event.x_root, event.y_root)
        finally: menu.grab_release()

    def copy_to_clipboard(self, text_widget):
        try:
            text = text_widget.selection_get()
            text_widget.clipboard_clear()
            text_widget.clipboard_append(text)
        except tk.TclError: pass

    def cut_to_clipboard(self, text_widget):
        self.copy_to_clipboard(text_widget)
        try: text_widget.delete("sel.first", "sel.last")
        except tk.TclError: pass

    def paste_from_clipboard(self, text_widget):
        try:
            text = text_widget.clipboard_get()
            text_widget.insert(tk.INSERT, text)
        except tk.TclError: pass

    def select_all_text(self, text_widget):
        text_widget.tag_add('sel', '1.0', 'end')

    def set_async_event(self, event_to_set):
        if self.bot_loop and self.bot_loop.is_running() and event_to_set:
            self.bot_loop.call_soon_threadsafe(event_to_set.set)
            if event_to_set == self.login_event: self.login_continue_button.config(state=tk.DISABLED)
        else: self.logger.log("هشدار: حلقه ربات فعال نیست یا رویداد برای تنظیم وجود ندارد.")

    def start_bot_thread_wrapper(self):
        raise NotImplementedError("Subclasses must implement start_bot_thread_wrapper")

    def _start_bot_thread(self, bot_function, config):
        self.start_button.config(state=tk.DISABLED)
        self.login_continue_button.config(state=tk.NORMAL)
        self.exit_bot_button.config(state=tk.NORMAL)
        self.logger.log("در حال آماده سازی ربات...")
        self.status_updater.clear_table()

        self.login_event.clear()
        self.exit_event.clear()

        def bot_target():
            self.bot_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.bot_loop)
            try:
                self.bot_loop.run_until_complete(bot_function(config, self.logger, self.status_updater, self.login_event, self.exit_event))
            except Exception as e: self.logger.log(f"❌ خطای بحرانی در ترد ربات: {e}")
            finally:
                if self.bot_loop.is_running(): self.bot_loop.call_soon_threadsafe(self.bot_loop.stop)
                self.master_app.after(0, self.on_bot_finished)

        self.bot_thread = threading.Thread(target=bot_target, daemon=True)
        self.bot_thread.start()

    def on_bot_finished(self):
        self.start_button.config(state=tk.NORMAL)
        self.login_continue_button.config(state=tk.DISABLED)
        self.exit_bot_button.config(state=tk.DISABLED)
        self.logger.log("عملیات ربات پایان یافته یا متوقف شده است.")
        if self.bot_loop and not self.bot_loop.is_closed():
            if not self.bot_loop.is_running(): self.bot_loop.close()
        self.bot_thread = None

    def on_closing(self):
        if self.bot_thread and self.bot_thread.is_alive():
            if messagebox.askyesno("خروج", "ربات هنوز در حال اجراست. آیا می‌خواهید عملیات را متوقف کرده و خارج شوید?\n(ممکن است مرورگر فوراً بسته نشود.)", parent=self):
                if self.bot_loop and self.bot_loop.is_running():
                    if self.login_event and not self.login_event.is_set(): self.bot_loop.call_soon_threadsafe(self.login_event.set)
                    if self.exit_event and not self.exit_event.is_set(): self.bot_loop.call_soon_threadsafe(self.exit_event.set)
                self.master_app.after(500, self.destroy)
            else: return
        else: self.destroy()

class TahvilBotWindow(BaseBotWindow):
    def __init__(self, master):
        super().__init__(master, "ربات پیام گروه (تحویل)")

        self.group_name_var = tk.StringVar(value="دوپلاس")
        self.message_prefix_var = tk.StringVar(value="ماژیک_ساعت")
        self.base_dm_var = tk.StringVar(value="سلام\nخرید شما رسیده، لطفا طبق ساعتهای اعلامی در گروه، برای تحویلشون اقدام کنید. 🌺")
        self.own_username_var = tk.StringVar(value="adminbahar")
        self.phone_number_var = tk.StringVar(value="09012195787")
        self.min_delay_var = tk.IntVar(value=3)
        self.max_delay_var = tk.IntVar(value=10)

        self.create_entry(self.config_frame, "نام گروه", self.group_name_var, 0)
        self.create_entry(self.config_frame, "پیشوند پیام در گروه", self.message_prefix_var, 1)
        self.dm_message_editor_tahvil = self.create_entry(self.config_frame, "پیام پایه برای ارسال خصوصی", self.base_dm_var, 2, is_text_area=True, text_area_height=4)
        self.create_entry(self.config_frame, "نام کاربری شما (عدم ارسال به خود)", self.own_username_var, 3)
        self.create_entry(self.config_frame, "شماره تلفن (مثال: 09123456789)", self.phone_number_var, 4)
        self.create_entry(self.config_frame, "حداقل تاخیر ارسال (ثانیه)", self.min_delay_var, 5)
        self.create_entry(self.config_frame, "حداکثر تاخیر ارسال (ثانیه)", self.max_delay_var, 6)

    def start_bot_thread_wrapper(self):
        min_delay, max_delay = self.min_delay_var.get(), self.max_delay_var.get()
        if not (isinstance(min_delay, int) and isinstance(max_delay, int) and 0 < min_delay <= max_delay):
            messagebox.showerror("خطا در تاخیر", "مقادیر حداقل و حداکثر تاخیر باید اعداد صحیح مثبت باشند و حداقل نباید از حداکثر بیشتر باشد.", parent=self)
            return

        original_phone_number = self.phone_number_var.get()
        converted_phone_number = convert_phone_number_format(original_phone_number)
        if not (converted_phone_number.startswith('989') and len(converted_phone_number) == 13 and converted_phone_number[2:].isdigit()):
             if not (original_phone_number.startswith('09') and len(original_phone_number) == 11 and original_phone_number.isdigit()):
                messagebox.showerror("خطا در شماره تلفن", "فرمت شماره تلفن صحیح نیست. مثال: 09123456789", parent=self)
                return

        config = {
            "GROUP_NAME": self.group_name_var.get(),
            "MESSAGE_PREFIX": self.message_prefix_var.get(),
            "BASE_DM_MESSAGE": self.dm_message_editor_tahvil.get("1.0", tk.END).strip(),
            "YOUR_OWN_USERNAME": self.own_username_var.get(),
            "PHONE_NUMBER_TO_ENTER": converted_phone_number,
            "FAILED_DMS_FILE": "tahvil_failed_dms.txt",
            "MIN_DELAY_S": min_delay, "MAX_DELAY_S": max_delay
        }
        if not all(config.values()):
            messagebox.showerror("خطا", "لطفاً تمام فیلدهای تنظیمات را پر کنید.", parent=self)
            return

        self.logger.log(f"شماره تلفن وارد شده: {original_phone_number}, تبدیل شده برای سیستم: {converted_phone_number}")
        super()._start_bot_thread(run_tahvil_bot_async, config)

class IdSenderBotWindow(BaseBotWindow):
    def __init__(self, master):
        super().__init__(master, "ربات پیام مستقیم (از اکسل)")

        self.own_username_var = tk.StringVar(value="davody")
        self.direct_message_var = tk.StringVar(value="سلام\nممنون که توی گروه ما عضو شدین.\nخبرای خوبی تو راهه. 🌺.")
        self.excel_path_var = tk.StringVar()
        self.phone_number_var = tk.StringVar(value="")
        self.min_delay_var = tk.IntVar(value=5)
        self.max_delay_var = tk.IntVar(value=15)

        self.create_entry(self.config_frame, "نام کاربری شما (عدم ارسال به خود)", self.own_username_var, 0)
        self.direct_message_editor_id = self.create_entry(self.config_frame, "پیام برای ارسال مستقیم", self.direct_message_var, 1, is_text_area=True, text_area_height=4)

        lbl_excel = ttk.Label(self.config_frame, text="مسیر فایل اکسل آی‌دی‌ها :")
        lbl_excel.grid(row=2, column=1, padx=(0,5), pady=3, sticky="e")

        excel_frame = ttk.Frame(self.config_frame)
        excel_frame.grid(row=2, column=0, padx=(5,0), pady=3, sticky="ew")
        self.config_frame.grid_columnconfigure(0, weight=1)

        btn_browse = ttk.Button(excel_frame, text="...انتخاب فایل", command=self.browse_excel)
        btn_browse.pack(side=tk.LEFT, padx=(0,2))

        entry_excel = ttk.Entry(excel_frame, textvariable=self.excel_path_var, justify=tk.RIGHT, font=("Tahoma", 9))
        entry_excel.pack(side=tk.RIGHT, expand=True, fill="x")

        self.create_entry(self.config_frame, "شماره تلفن (اختیاری، مثال: 09123456789)", self.phone_number_var, 3)
        self.create_entry(self.config_frame, "حداقل تاخیر ارسال (ثانیه)", self.min_delay_var, 4)
        self.create_entry(self.config_frame, "حداکثر تاخیر ارسال (ثانیه)", self.max_delay_var, 5)

    def browse_excel(self):
        filepath = filedialog.askopenfilename(title="فایل اکسل آی‌دی‌ها را انتخاب کنید",
                                            filetypes=(("Excel files", "*.xlsx *.xls"), ("All files", "*.*")), parent=self)
        if filepath: self.excel_path_var.set(filepath)

    def start_bot_thread_wrapper(self):
        min_delay, max_delay = self.min_delay_var.get(), self.max_delay_var.get()
        if not (isinstance(min_delay, int) and isinstance(max_delay, int) and 0 < min_delay <= max_delay):
            messagebox.showerror("خطا در تاخیر", "مقادیر حداقل و حداکثر تاخیر باید اعداد صحیح مثبت باشند و حداقل نباید از حداکثر بیشتر باشد.", parent=self)
            return

        original_phone_number = self.phone_number_var.get()
        converted_phone_number = original_phone_number
        if original_phone_number:
            converted_phone_number = convert_phone_number_format(original_phone_number)
            if not (converted_phone_number.startswith('989') and len(converted_phone_number) == 13 and converted_phone_number[2:].isdigit()):
                if not (original_phone_number.startswith('09') and len(original_phone_number) == 11 and original_phone_number.isdigit()):
                    messagebox.showerror("خطا در شماره تلفن", "فرمت شماره تلفن (در صورت ورود) صحیح نیست. مثال: 09123456789", parent=self)
                    return
            self.logger.log(f"شماره تلفن وارد شده: {original_phone_number}, تبدیل شده برای سیستم: {converted_phone_number}")

        config = {
            "YOUR_OWN_USERNAME": self.own_username_var.get(),
            "DIRECT_MESSAGE_TO_SEND": self.direct_message_editor_id.get("1.0", tk.END).strip(),
            "EXCEL_FILE_PATH": self.excel_path_var.get(),
            "PHONE_NUMBER_TO_ENTER": converted_phone_number,
            "FAILED_DMS_FILE": "id_failed_direct_dms.txt",
            "MIN_DELAY_S": min_delay, "MAX_DELAY_S": max_delay
        }
        if not all([config["YOUR_OWN_USERNAME"], config["DIRECT_MESSAGE_TO_SEND"], config["EXCEL_FILE_PATH"]]):
            messagebox.showerror("خطا", "لطفاً نام کاربری خود، پیام ارسالی و مسیر فایل اکسل را مشخص کنید.", parent=self)
            return

        super()._start_bot_thread(run_id_sender_bot_async, config)

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Eitaa Bot Launcher")
        self.geometry("400x200")
        self.resizable(False, False)

        self.style = ttk.Style(self)
        self.style.theme_use('clam')

        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(expand=True, fill=tk.BOTH)
        main_frame.columnconfigure(0, weight=1)

        ttk.Label(main_frame, text="کدام ربات را می‌خواهید اجرا کنید؟", font=("Tahoma", 14, "bold"), anchor=tk.CENTER).pack(pady=(0,20), fill=tk.X)

        tahvil_button = ttk.Button(main_frame, text="ربات پیام گروه (تحویل)", command=self.open_tahvil_bot, style="Large.TButton", padding=10)
        tahvil_button.pack(pady=7, fill="x", padx=20)

        id_button = ttk.Button(main_frame, text="ربات پیام مستقیم (از اکسل)", command=self.open_id_bot, style="Large.TButton", padding=10)
        id_button.pack(pady=7, fill="x", padx=20)

        self.style.configure("Large.TButton", font=("Tahoma", 11, "bold"))
        self.style.configure("TLabel", font=("Tahoma", 10), anchor="e")
        self.style.configure("TEntry", font=("Tahoma", 10))
        self.style.configure("TButton", font=("Tahoma", 10))
        self.style.configure("Treeview.Heading", font=("Tahoma", 9, 'bold'), anchor="e")
        self.style.configure("Treeview", font=("Tahoma", 9), rowheight=25)

    def open_tahvil_bot(self): TahvilBotWindow(self)
    def open_id_bot(self): IdSenderBotWindow(self)

if __name__ == '__main__':
    app = App()
    app.mainloop()