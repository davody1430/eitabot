// =================================== 1. Tab Management Functions ===================================
/**
 * مدیریت تغییر تب‌ها و فعال/غیرفعال کردن محتوا
 * @param {Event} evt - رویداد کلیک
 * @param {string} tabName - شناسه محتوای تب مورد نظر
 */
function openTab(evt, tabName) {
    let i, tabcontent, tablinks;
    
    // مخفی کردن تمام محتواهای تب
    tabcontent = document.getElementsByClassName("tab-content");
    for (i = 0; i < tabcontent.length; i++) tabcontent[i].classList.remove("active");
    
    // غیرفعال کردن استایل تمام لینک‌های تب
    tablinks = document.getElementsByClassName("nav-link");
    for (i = 0; i < tablinks.length; i++) tablinks[i].classList.remove("active");
    
    // نمایش محتوای تب مورد نظر و فعال کردن لینک آن
    document.getElementById(tabName).classList.add("active");
    evt.currentTarget.classList.add("active");
    
    // عملیات خاص هنگام فعال شدن تب‌ها
    if (tabName === 'ready_messages') {
        loadReadyMessages();
    } else if (tabName === 'dispatch_report') {
        loadDispatchReport(); 
    } else if (tabName === 'database_management') {
        loadDatabaseStats();
    }
}

// =================================== 2. Core Action Functions ===================================
/**
 * شروع عملیات اصلی (ورود، ربات تحویل، ارسال از اکسل)
 * @param {string} mode - نوع عملیات (login, tahvil, excel)
 */
async function startAction(mode) {
    const phone = document.getElementById('phone').value;
    if(!phone) return alert("ابتدا شماره موبایل را وارد کنید");

    // اگر عملیات add_contacts است
    if (mode === 'add_contacts') {
        await startAddContacts();
        return;
    }

    // برای عملیات دیگر
    const formData = new FormData();
    formData.append('phone', phone);
    formData.append('mode', mode);
    
    if (mode === 'tahvil') {
        formData.append('group_name', document.getElementById('group_name').value || '');
        formData.append('keyword', document.getElementById('keyword').value || '');
        formData.append('msg', document.getElementById('tahvil_msg').value || '');
        formData.append('min_d', document.getElementById('min_delay').value || 7);
        formData.append('max_d', document.getElementById('max_delay').value || 12);
        formData.append('your_own_username', document.getElementById('your_own_username').value || '');
    } else if (mode === 'excel') {
        const fileInput = document.getElementById('excel_file');
        if (!fileInput || !fileInput.files[0]) {
            alert("لطفاً ابتدا فایل اکسل را انتخاب کنید");
            return;
        }
        formData.append('msg', document.getElementById('excel_msg').value || '');
        formData.append('min_d', document.getElementById('min_delay').value || 7);
        formData.append('max_d', document.getElementById('max_delay').value || 12);
        
        // آپلود فایل
        const uploadResponse = await fetch('/upload-excel', {
            method: 'POST',
            body: new FormData(fileInput.form)
        });
        const uploadData = await uploadResponse.json();
        if (uploadData.status !== 'success') {
            alert("خطا در آپلود فایل: " + uploadData.message);
            return;
        }
    }

    try {
        const response = await fetch('/start', {
            method: 'POST', 
            body: formData
        });
        
        const data = await response.json();
        
        if (data.status === 'success') {
            alert(data.message);
            document.getElementById('login_status').innerText = "در حال اجرا...";
        } else {
            alert("خطا: " + data.message);
        }
    } catch (error) {
        console.error("Error starting automation:", error);
        alert("خطا در ارتباط با سرور");
    }
}

/**
 * ارسال کد تایید (OTP) پس از دریافت از ایتا
 */
async function sendOTP() {
    const code = document.getElementById('otp_code').value;
    if (!code || code.length !== 5) {
        alert("لطفاً کد ۵ رقمی را وارد کنید");
        return;
    }

    const params = new URLSearchParams();
    params.append('code', code);
    
    try {
        const response = await fetch('/submit-otp', {
            method: 'POST', 
            body: params,
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            }
        });
        
        const data = await response.json();
        
        if (data.status === 'success') {
            // مخفی کردن بخش کد تایید
            document.getElementById('otp_section').style.display = 'none';
            alert("کد تایید ارسال شد");
        } else {
            alert("خطا در ارسال کد: " + data.message);
        }
    } catch (error) {
        console.error("Error sending OTP:", error);
        alert("خطا در ارتباط با سرور");
    }
}

// =================================== 3. Ready Messages Functions ===================================
/**
 * افزودن پیام جدید به لیست پیام‌های پیش‌فرض
 */
async function addReadyMsg() {
    const msg = document.getElementById('new_ready_msg').value.trim();
    if (!msg) return;

    const params = new URLSearchParams();
    params.append('message', msg);
    await fetch('/add-ready-message', {method: 'POST', body: params});
    
    document.getElementById('new_ready_msg').value = '';
    
    // رفرش کردن لیست پس از ذخیره
    await loadReadyMessages();
}

/**
 * بارگذاری لیست پیام‌های پیش‌فرض از سرور و نمایش آنها
 */
async function loadReadyMessages() {
    const listElement = document.getElementById('ready_messages_list');
    listElement.innerHTML = `<div class="text-sm text-gray-500 text-center py-2"><i class="fa-solid fa-spinner fa-spin ml-2"></i> در حال بارگذاری...</div>`;

    try {
        const res = await fetch('/get-ready-messages');
        const data = await res.json();
        
        if (data.messages && data.messages.length > 0) {
            listElement.innerHTML = data.messages.map((msg, index) => {
                // Escape کردن کاراکترهای خاص برای انتقال به تابع JS (مانند ' و ")
                const safeMsg = msg.replace(/'/g, "\\'").replace(/"/g, '\\"');
                return `
                    <div class="p-3 bg-white border rounded-lg flex justify-between items-start text-sm shadow-sm">
                        <span class="flex-1 whitespace-pre-wrap">${msg}</span>
                        <div class="flex gap-2 mr-3">
                            <button onclick="editMessage(${index}, '${safeMsg}')" class="text-yellow-600 hover:text-yellow-700" title="ویرایش">
                                <i class="fa-solid fa-edit"></i>
                            </button>
                            <button onclick="copyToClipboard('${safeMsg}')" class="text-indigo-500 hover:text-indigo-700" title="کپی متن">
                                <i class="fa-solid fa-copy"></i>
                            </button>
                        </div>
                    </div>
                `;
            }).join('');
        } else {
            listElement.innerHTML = `<div class="text-sm text-gray-500 text-center py-2">پیام ذخیره‌شده‌ای وجود ندارد.</div>`;
        }
    } catch (error) {
        listElement.innerHTML = `<div class="text-sm text-red-500 text-center py-2">خطا در بارگذاری پیام‌ها.</div>`;
    }
}

/**
 * باز کردن Modal برای ویرایش پیام پیش‌فرض
 * @param {number} index - اندیس پیام در لیست
 * @param {string} currentText - متن فعلی پیام
 */
function editMessage(index, currentText) {
    document.getElementById('edit_index').value = index;
    // Unescape کردن پیام برای نمایش در Textarea
    const unescapedText = currentText.replace(/\\'/g, "'").replace(/\\"/g, '"');
    document.getElementById('edit_textarea').value = unescapedText;
    
    document.getElementById('edit_modal').classList.remove('hidden');
    document.getElementById('edit_modal').classList.add('flex');
}

/**
 * ذخیره پیام ویرایش شده در سرور
 */
async function saveEditedMessage() {
    const index = document.getElementById('edit_index').value;
    const newText = document.getElementById('edit_textarea').value.trim();
    
    if (index === "" || newText === "") {
        alert("خطا: اطلاعات پیام ناقص است.");
        return;
    }

    const params = new URLSearchParams();
    params.append('index', index);
    params.append('new_message', newText);

    try {
        const res = await fetch('/edit-ready-message', {method: 'POST', body: params});
        const data = await res.json();
        
        if (data.status === 'success') {
            // بستن Modal و رفرش لیست
            document.getElementById('edit_modal').classList.add('hidden');
            document.getElementById('edit_modal').classList.remove('flex');
            await loadReadyMessages(); 
        } else {
            alert(`خطا در ویرایش: ${data.message}`);
        }
    } catch (error) {
        alert(`خطا در ارتباط با سرور برای ویرایش پیام.`);
    }
}

/**
 * کپی کردن متن به کلیپ‌بورد کاربر
 * @param {string} text - متن برای کپی شدن (باید Unescape شود)
 */
function copyToClipboard(text) {
    const unescapedText = text.replace(/\\'/g, "'").replace(/\\"/g, '"');
    
    navigator.clipboard.writeText(unescapedText).then(() => {
        alert("متن کپی شد: " + unescapedText.substring(0, 30).replace(/\n/g, ' ') + '...');
    }).catch(err => {
        console.error('Could not copy text: ', err);
        alert('خطا در کپی متن.');
    });
}

// =================================== 4. Ready Message Selection Modal Functions ===================================
/**
 * باز کردن Modal انتخاب پیام‌های پیش‌فرض
 * @param {string} targetId - ID المان Textarea مقصد (مانند 'tahvil_msg')
 */
async function openMessageSelectModal(targetId) {
    const modal = document.getElementById('select_msg_modal');
    const listElement = document.getElementById('available_ready_messages');
    
    // ۱. ذخیره ID مقصد
    document.getElementById('target_msg_id').value = targetId;

    // ۲. بارگذاری پیام‌ها
    listElement.innerHTML = `<div class="text-sm text-gray-500 text-center py-2"><i class="fa-solid fa-spinner fa-spin ml-2"></i> در حال بارگذاری پیام‌های ذخیره‌شده...</div>`;
    
    try {
        const res = await fetch('/get-ready-messages');
        const data = await res.json();
        const messages = data.messages || [];
        
        if (messages.length > 0) {
            listElement.innerHTML = messages.map(msg => {
                // Escape کردن کاراکترهای خاص برای انتقال به تابع JS
                const safeMsg = msg.replace(/'/g, "\\'").replace(/"/g, '\\"').replace(/\n/g, '\\n');
                return `
                    <div class="p-3 bg-white border rounded-lg flex justify-between items-center text-sm shadow-sm hover:bg-indigo-50 transition cursor-pointer" 
                        onclick="selectReadyMessage('${safeMsg}')">
                        <span class="flex-1 whitespace-pre-wrap">${msg.substring(0, 100)}${msg.length > 100 ? '...' : ''}</span>
                        <span class="text-indigo-600 font-bold mr-3">انتخاب</span>
                    </div>
                `;
            }).join('');
        } else {
            listElement.innerHTML = `<div class="text-sm text-gray-500 text-center py-2">پیام ذخیره‌شده‌ای وجود ندارد. ابتدا در تب پیام‌های پیش‌فرض، پیام ذخیره کنید.</div>`;
        }
    } catch (error) {
        listElement.innerHTML = `<div class="text-sm text-red-500 text-center py-2">خطا در بارگذاری پیام‌ها.</div>`;
    }
    
    // ۳. نمایش Modal
    modal.classList.remove('hidden');
    modal.classList.add('flex');
}

/**
 * تزریق پیام انتخاب شده به Textarea مقصد و بستن Modal
 * @param {string} messageText - متن پیام انتخاب شده (باید Unescape و خطوط جدید جایگذاری شود)
 */
function selectReadyMessage(messageText) {
    const targetId = document.getElementById('target_msg_id').value;
    const targetElement = document.getElementById(targetId);
    
    // Unescape کردن پیام و جایگذاری خطوط جدید
    const finalMessage = messageText.replace(/\\'/g, "'").replace(/\\"/g, '"').replace(/\\n/g, '\n');

    if (targetElement) {
        targetElement.value = finalMessage;
    }
    
    // بستن Modal
    document.getElementById('select_msg_modal').classList.add('hidden');
    document.getElementById('select_msg_modal').classList.remove('flex');
}

// =================================== 5. Dispatch Report Functions ===================================
/**
 * بارگذاری و نمایش گزارش ارسال عملیات
 */
async function loadDispatchReport() {
    const tableBody = document.getElementById('report_table_body');
    const summary = document.getElementById('report_summary');
    
    tableBody.innerHTML = `<tr><td colspan="3" class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-500">در حال بارگذاری گزارش...</td></tr>`;

    try {
        const res = await fetch('/get-dispatch-report');
        const data = await res.json();
        const report = data.report;
        
        if (!report || report.length === 0) {
            tableBody.innerHTML = `<tr><td colspan="3" class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-500">گزارشی وجود ندارد. عملیات را شروع کنید.</td></tr>`;
            summary.innerText = "وضعیت کلی: گزارشی یافت نشد.";
            return;
        }

        let successCount = 0;
        let failedCount = 0;
        let skippedCount = 0;

        const reportHtml = report.map(item => {
            const isSuccess = item.status === 'success';
            const isSkipped = item.status === 'skipped';
            
            if (isSuccess) {
                successCount++;
            } else if (isSkipped) {
                skippedCount++;
            } else {
                failedCount++;
            }

            // آیکون تیک یا ضربدر
            let icon = '';
            let statusText = '';
            let statusColor = '';
            
            if (isSuccess) {
                icon = `<i class="fa-solid fa-check-circle text-green-500 text-lg"></i>`;
                statusText = 'موفق';
                statusColor = 'text-green-700';
            } else if (isSkipped) {
                icon = `<i class="fa-solid fa-minus-circle text-yellow-500 text-lg"></i>`;
                statusText = 'رد شده';
                statusColor = 'text-yellow-700';
            } else {
                icon = `<i class="fa-solid fa-times-circle text-red-500 text-lg"></i>`;
                statusText = 'ناموفق';
                statusColor = 'text-red-700';
            }

            // توضیحات خطا (اختیاری)
            const errorText = item.error ? item.error : (isSuccess ? 'ارسال با موفقیت انجام شد.' : 'خطای نامشخص.');
            
            // نمایش ID به صورت راست به چپ
            const idDisplay = `<span class="dir-ltr text-left inline-block">${item.id}</span>`;

            return `
                <tr>
                    <td class="px-6 py-3 whitespace-nowrap text-sm font-medium text-gray-900 text-right">${idDisplay}</td>
                    <td class="px-6 py-3 whitespace-nowrap text-center">${icon} <span class="${statusColor} font-bold mr-2">${statusText}</span></td>
                    <td class="px-6 py-3 text-sm text-gray-500">${errorText}</td>
                </tr>
            `;
        }).join('');

        tableBody.innerHTML = reportHtml;
        summary.innerHTML = `وضعیت کلی: <span class="text-green-600 font-bold">${successCount} موفق</span> / <span class="text-red-600 font-bold">${failedCount} ناموفق</span> / <span class="text-yellow-600 font-bold">${skippedCount} رد شده</span> (کل: ${report.length}) - <span class="text-blue-600 text-xs">${data.source === 'database' ? 'از دیتابیس' : 'از حافظه موقت'}</span>`;

    } catch (error) {
        console.error("Error loading report:", error);
        tableBody.innerHTML = `<tr><td colspan="3" class="px-6 py-4 whitespace-nowrap text-sm text-center text-red-500">خطا در ارتباط با سرور یا بارگذاری گزارش.</td></tr>`;
        summary.innerText = "وضعیت کلی: خطا در بارگذاری گزارش.";
    }
}

/**
 * پاک کردن گزارش ارسال
 */
async function clearReport() {
    if (!confirm("آیا مطمئنید که می‌خواهید گزارش فعلی را پاک کنید؟")) {
        return;
    }
    
    try {
        const res = await fetch('/clear-report', {method: 'POST'});
        const data = await res.json();
        
        if (data.status === 'cleared') {
            alert("گزارش با موفقیت پاک شد.");
            loadDispatchReport(); // رفرش گزارش
        }
    } catch (error) {
        alert("خطا در پاک کردن گزارش.");
    }
}

// =================================== 6. Export Functions ===================================
/**
 * دانلود گزارش کامل به صورت فایل اکسل
 */
async function exportAllReport() {
    try {
        // نمایش پیام در حال بارگذاری
        const summary = document.getElementById('report_summary');
        const originalText = summary.innerHTML;
        summary.innerHTML = `<i class="fa-solid fa-spinner fa-spin ml-2"></i> در حال ایجاد فایل اکسل گزارش کامل...`;
        
        // درخواست به سرور
        const response = await fetch('/export-report-excel');
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.message || 'خطا در ایجاد فایل');
        }
        
        // دریافت فایل
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        
        // ایجاد لینک دانلود
        const a = document.createElement('a');
        a.href = url;
        
        // استخراج نام فایل از headers
        const contentDisposition = response.headers.get('Content-Disposition');
        let filename = `گزارش_ارسال_ایتا_${new Date().toLocaleDateString('fa-IR').replace(/\//g, '-')}.xlsx`;
        
        if (contentDisposition) {
            const filenameMatch = contentDisposition.match(/filename="(.+)"/);
            if (filenameMatch && filenameMatch[1]) {
                filename = filenameMatch[1];
            }
        }
        
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        
        // آزاد کردن منابع
        window.URL.revokeObjectURL(url);
        
        // بازگرداندن متن اصلی
        summary.innerHTML = originalText;
        
        // نمایش پیام موفقیت
        showNotification('success', 'فایل اکسل با موفقیت دانلود شد');
        
    } catch (error) {
        console.error('Error exporting report:', error);
        document.getElementById('report_summary').innerHTML = `خطا در دانلود گزارش: ${error.message}`;
        showNotification('error', `خطا در دانلود گزارش: ${error.message}`);
    }
}

/**
 * دانلود فقط لیست آی‌دی‌ها در ستون A
 */
async function exportIdsOnly() {
    try {
        // نمایش پیام در حال بارگذاری
        const summary = document.getElementById('report_summary');
        const originalText = summary.innerHTML;
        summary.innerHTML = `<i class="fa-solid fa-spinner fa-spin ml-2"></i> در حال ایجاد فایل لیست آی‌دی‌ها...`;
        
        // درخواست به سرور
        const response = await fetch('/export-ids-excel');
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.message || 'خطا در ایجاد فایل');
        }
        
        // دریافت فایل
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        
        // ایجاد لینک دانلود
        const a = document.createElement('a');
        a.href = url;
        
        // استخراج نام فایل از headers
        const contentDisposition = response.headers.get('Content-Disposition');
        let filename = `لیست_آی‌دی‌های_ایتا_${new Date().toLocaleDateString('fa-IR').replace(/\//g, '-')}.xlsx`;
        
        if (contentDisposition) {
            const filenameMatch = contentDisposition.match(/filename="(.+)"/);
            if (filenameMatch && filenameMatch[1]) {
                filename = filenameMatch[1];
            }
        }
        
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        
        // آزاد کردن منابع
        window.URL.revokeObjectURL(url);
        
        // بازگرداندن متن اصلی
        summary.innerHTML = originalText;
        
        // نمایش پیام موفقیت
        showNotification('success', 'فایل لیست آی‌دی‌ها با موفقیت دانلود شد');
        
    } catch (error) {
        console.error('Error exporting IDs:', error);
        document.getElementById('report_summary').innerHTML = `خطا در دانلود لیست آی‌دی‌ها: ${error.message}`;
        showNotification('error', `خطا در دانلود لیست آی‌دی‌ها: ${error.message}`);
    }
}

/**
 * نمایش نوتیفیکیشن
 */
function showNotification(type, message) {
    // حذف نوتیفیکیشن قبلی اگر وجود دارد
    const existingNotification = document.getElementById('custom-notification');
    if (existingNotification) {
        existingNotification.remove();
    }
    
    // رنگ‌های مختلف برای انواع نوتیفیکیشن
    const colors = {
        success: { bg: 'bg-green-100', border: 'border-green-400', text: 'text-green-800', icon: 'fa-check-circle' },
        error: { bg: 'bg-red-100', border: 'border-red-400', text: 'text-red-800', icon: 'fa-times-circle' },
        warning: { bg: 'bg-yellow-100', border: 'border-yellow-400', text: 'text-yellow-800', icon: 'fa-exclamation-triangle' },
        info: { bg: 'bg-blue-100', border: 'border-blue-400', text: 'text-blue-800', icon: 'fa-info-circle' }
    };
    
    const color = colors[type] || colors.info;
    
    // ایجاد عنصر نوتیفیکیشن
    const notification = document.createElement('div');
    notification.id = 'custom-notification';
    notification.className = `fixed top-4 right-4 ${color.bg} ${color.border} border-l-4 ${color.text} p-4 rounded-r-lg shadow-lg z-[1000] max-w-md animate-fade-in`;
    notification.innerHTML = `
        <div class="flex items-center">
            <i class="fas ${color.icon} ml-2 text-lg"></i>
            <span class="font-medium">${message}</span>
            <button onclick="this.parentElement.parentElement.remove()" class="mr-auto text-gray-500 hover:text-gray-700">
                <i class="fas fa-times"></i>
            </button>
        </div>
    `;
    
    document.body.appendChild(notification);
    
    // حذف خودکار پس از 5 ثانیه
    setTimeout(() => {
        if (notification.parentElement) {
            notification.remove();
        }
    }, 5000);
}

// =================================== 7. Status Polling ===================================
/**
 * نظرسنجی دوره‌ای برای دریافت وضعیت فعلی ربات (لاگ‌ها و مرحله فعلی)
 */
setInterval(async () => {
    try {
        const res = await fetch('/get-status');
        const data = await res.json();
        
        // نمایش/مخفی سازی بخش کد تایید
        const otpBox = document.getElementById('otp_section');
        if(data.otp_required) {
            otpBox.style.display = 'block';
        } else {
            otpBox.style.display = 'none';
        }
        
        // به‌روزرسانی وضعیت ورود و لاگ‌ها
        document.getElementById('login_status').innerText = "وضعیت: " + data.current_step;
        
        // به‌روزرسانی لاگ‌ها (حداکثر 50 خط)
        const logsElement = document.getElementById('logs');
        if (data.logs && Array.isArray(data.logs)) {
            const lastLogs = data.logs.slice(-50); // آخرین 50 خط
            logsElement.innerHTML = lastLogs.map(l => `<div>> ${l}</div>`).join('');
            // اسکرول به پایین
            logsElement.scrollTop = logsElement.scrollHeight;
        }
    } catch (error) {
        console.error("Error polling status:", error);
    }
}, 2000); // هر ۲ ثانیه

// =================================== 8. Contacts Management Functions ===================================

/**
 * بارگذاری فایل اکسل مخاطبین
 */
async function uploadContactsFile() {
    const file = document.getElementById('contacts_excel_file').files[0];
    const fileInfoElement = document.getElementById('contacts_file_info');
    const previewElement = document.getElementById('contacts_preview');
    const countElement = document.getElementById('contacts_count');
    const duplicateBadge = document.getElementById('duplicate_badge');
    const duplicateCountElement = document.getElementById('duplicate_count');
    
    if (!file) {
        fileInfoElement.innerText = `لطفاً یک فایل انتخاب کنید.`;
        return;
    }
    
    const formData = new FormData();
    formData.append('file', file);
    fileInfoElement.innerText = `در حال بارگذاری فایل ${file.name}...`;
    previewElement.innerHTML = `<div class="text-sm text-gray-500 text-center py-2"><i class="fa-solid fa-spinner fa-spin ml-2"></i> در حال پردازش فایل و بررسی تکراری‌ها...</div>`;
    
    try {
        const res = await fetch('/upload-contacts-excel', {method: 'POST', body: formData});
        const data = await res.json();
        
        if(data.status === 'success') {
            fileInfoElement.innerText = `فایل ${file.name} با موفقیت بارگذاری شد.`;
            
            // نمایش آمار تکراری‌ها
            if (data.duplicate_count > 0) {
                duplicateBadge.classList.remove('hidden');
                duplicateCountElement.innerText = data.duplicate_count;
            } else {
                duplicateBadge.classList.add('hidden');
            }
            
            countElement.innerText = data.new_count;
            
            // نمایش پیش‌نمایش مخاطبین
            if (data.contacts && data.contacts.length > 0) {
                let previewHtml = '<div class="space-y-2">';
                data.contacts.slice(0, 5).forEach(contact => {
                    previewHtml += `
                        <div class="flex items-center justify-between p-2 bg-white border rounded">
                            <div class="flex-1">
                                <span class="font-medium text-gray-800">${contact.name}</span>
                                <span class="text-gray-500 text-sm mr-3">(${contact.phone})</span>
                            </div>
                            <span class="text-green-500 text-xs font-bold">✓ جدید</span>
                        </div>
                    `;
                });
                
                if (data.new_count > 5) {
                    previewHtml += `<div class="text-center text-sm text-gray-500 py-1">و ${data.new_count - 5} مخاطب جدید دیگر...</div>`;
                }
                
                if (data.duplicate_count > 0) {
                    previewHtml += `<div class="text-center text-sm text-yellow-600 py-1 font-medium"><i class="fa-solid fa-clone ml-1"></i> ${data.duplicate_count} مخاطب تکراری شناسایی و حذف شد</div>`;
                }
                
                previewHtml += '</div>';
                previewElement.innerHTML = previewHtml;
            } else {
                if (data.duplicate_count > 0) {
                    previewElement.innerHTML = `<div class="text-center py-4">
                        <i class="fa-solid fa-clone text-3xl text-yellow-500 mb-2"></i>
                        <p class="text-sm text-gray-700">همه ${data.duplicate_count} مخاطب قبلاً در دیتابیس وجود دارند!</p>
                        <p class="text-xs text-gray-500 mt-1">نیازی به افزودن مجدد نیست.</p>
                    </div>`;
                } else {
                    previewElement.innerHTML = `<div class="text-sm text-gray-500 text-center py-2">مخاطب جدیدی برای افزودن وجود ندارد.</div>`;
                }
            }
        } else {
            fileInfoElement.innerText = `خطا در بارگذاری: ${data.message || 'خطای نامشخص'}`;
            previewElement.innerHTML = `<div class="text-sm text-red-500 text-center py-2">خطا در پردازش فایل</div>`;
            countElement.innerText = '0';
            duplicateBadge.classList.add('hidden');
        }
    } catch (error) {
        fileInfoElement.innerText = `خطا در ارتباط با سرور: ${error.message}`;
        previewElement.innerHTML = `<div class="text-sm text-red-500 text-center py-2">خطا در ارتباط با سرور</div>`;
        countElement.innerText = '0';
        duplicateBadge.classList.add('hidden');
    }
}

/**
 * شروع عملیات افزودن مخاطبین
 */
async function startAddContacts() {
    const phone = document.getElementById('phone').value;
    if(!phone) return alert("ابتدا شماره موبایل را وارد کنید");
    
    // نمایش پیشرفت
    document.getElementById('contacts_progress_container').classList.remove('hidden');
    document.getElementById('contacts_progress_bar').style.width = '0%';
    document.getElementById('contacts_progress_text').innerText = '0/0';
    document.getElementById('contacts_status').innerText = 'در حال شروع عملیات...';
    
    // ارسال درخواست به سرور
    const params = new URLSearchParams();
    params.append('phone', phone);
    
    try {
        const res = await fetch('/start-add-contacts', {method: 'POST', body: params});
        const data = await res.json();
        
        if (data.status === 'started') {
            // شروع نظرسنجی برای وضعیت
            startContactsStatusPolling();
        } else {
            alert("خطا در شروع عملیات: " + (data.message || 'خطای ناشناخته'));
            document.getElementById('contacts_progress_container').classList.add('hidden');
        }
    } catch (error) {
        alert("خطا در ارتباط با سرور: " + error.message);
        document.getElementById('contacts_progress_container').classList.add('hidden');
    }
}

/**
 * نظرسنجی وضعیت افزودن مخاطبین
 */
let contactsStatusInterval = null;

function startContactsStatusPolling() {
    if (contactsStatusInterval) {
        clearInterval(contactsStatusInterval);
    }
    
    contactsStatusInterval = setInterval(async () => {
        try {
            const res = await fetch('/get-contacts-status');
            const data = await res.json();
            
            // به‌روزرسانی پیشرفت
            if (data.progress) {
                const progress = data.progress;
                const total = data.total || 1;
                const percentage = Math.round((progress / total) * 100);
                
                document.getElementById('contacts_progress_bar').style.width = `${percentage}%`;
                document.getElementById('contacts_progress_text').innerText = `${progress}/${total}`;
                document.getElementById('contacts_status').innerText = data.status || 'در حال پردازش...';
                
                // اگر عملیات تمام شد
                if (data.completed) {
                    clearInterval(contactsStatusInterval);
                    
                    // نمایش نتیجه نهایی
                    setTimeout(() => {
                        document.getElementById('contacts_status').innerHTML = 
                            `عملیات تکمیل شد: <span class="text-green-600 font-bold">${data.success_count || 0} موفق</span>، <span class="text-red-600 font-bold">${data.failed_count || 0} ناموفق</span>، <span class="text-yellow-600 font-bold">${data.duplicate_count || 0} تکراری</span>`;
                        
                        // پنهان کردن پیشرفت بعد از 5 ثانیه
                        setTimeout(() => {
                            document.getElementById('contacts_progress_container').classList.add('hidden');
                        }, 5000);
                    }, 1000);
                    
                    showNotification('success', `عملیات افزودن مخاطبین تکمیل شد. موفق: ${data.success_count || 0}، ناموفق: ${data.failed_count || 0}، تکراری: ${data.duplicate_count || 0}`);
                    
                    // به‌روزرسانی آمار دیتابیس
                    loadDatabaseStats();
                }
            }
            
            // در صورت خطا
            if (data.error) {
                clearInterval(contactsStatusInterval);
                document.getElementById('contacts_status').innerText = `خطا: ${data.error}`;
                document.getElementById('contacts_status').classList.add('text-red-500');
                showNotification('error', `خطا در افزودن مخاطبین: ${data.error}`);
            }
            
        } catch (error) {
            console.error("Error polling contacts status:", error);
        }
    }, 2000); // هر 2 ثانیه
}

/**
 * پاک کردن لیست مخاطبین
 */
function clearContactsList() {
    if (confirm("آیا مطمئنید که می‌خواهید لیست مخاطبین را پاک کنید؟")) {
        fetch('/clear-contacts-list', {method: 'POST'})
            .then(() => {
                document.getElementById('contacts_file_info').innerText = 'فایلی بارگذاری نشده است.';
                document.getElementById('contacts_preview').innerHTML = 
                    '<div class="text-sm text-gray-500 text-center py-2">هنوز فایلی بارگذاری نشده است.</div>';
                document.getElementById('contacts_count').innerText = '0';
                document.getElementById('duplicate_badge').classList.add('hidden');
                document.getElementById('contacts_excel_file').value = '';
                showNotification('success', 'لیست مخاطبین پاک شد.');
            });
    }
}

// =================================== 9. Database Management Functions ===================================

/**
 * بارگذاری آمار دیتابیس
 */
async function loadDatabaseStats() {
    const statsElement = document.getElementById('database_stats');
    statsElement.innerHTML = `
        <div class="text-center py-4">
            <i class="fa-solid fa-spinner fa-spin text-2xl text-gray-400"></i>
            <p class="text-sm text-gray-500 mt-2">در حال بارگذاری آمار دیتابیس...</p>
        </div>
    `;
    
    try {
        const res = await fetch('/get-database-stats');
        const data = await res.json();
        
        if (data.status === 'success') {
            const contacts = data.contacts;
            const reportsCount = data.reports_count;
            
            statsElement.innerHTML = `
                <div class="grid grid-cols-2 gap-4">
                    <div class="stats-card bg-green-50 p-4 rounded-xl border border-green-200 text-center">
                        <div class="text-green-600 text-3xl font-bold">${contacts.total}</div>
                        <div class="text-sm text-green-800 font-medium mt-1">مخاطب ذخیره شده</div>
                        <div class="text-xs text-green-600 mt-1">${contacts.unique} شماره منحصر به فرد</div>
                    </div>
                    
                    <div class="stats-card bg-blue-50 p-4 rounded-xl border border-blue-200 text-center">
                        <div class="text-blue-600 text-3xl font-bold">${reportsCount}</div>
                        <div class="text-sm text-blue-800 font-medium mt-1">گزارش ارسال</div>
                        <div class="text-xs text-blue-600 mt-1">در دیتابیس ذخیره شده</div>
                    </div>
                </div>
                
                <div class="mt-4 pt-4 border-t border-gray-200">
                    <h4 class="font-medium text-gray-700 mb-2">آخرین مخاطبین اضافه شده (7 روز گذشته):</h4>
                    <div class="space-y-2">
                        ${contacts.last_7_days && contacts.last_7_days.length > 0 ? 
                            contacts.last_7_days.map(day => `
                                <div class="flex justify-between items-center text-sm">
                                    <span class="text-gray-600">${day.date}</span>
                                    <span class="bg-purple-100 text-purple-800 text-xs font-bold px-2 py-1 rounded">${day.count} مخاطب</span>
                                </div>
                            `).join('') : 
                            '<div class="text-center text-sm text-gray-500 py-2">هنوز مخاطبی اضافه نشده است</div>'
                        }
                    </div>
                </div>
                
                <div class="mt-3 text-xs text-gray-500 text-center">
                    <i class="fa-solid fa-database ml-1"></i> فایل دیتابیس: ${data.database_file}
                </div>
            `;
        } else {
            statsElement.innerHTML = `
                <div class="text-center py-4">
                    <i class="fa-solid fa-exclamation-triangle text-2xl text-yellow-500"></i>
                    <p class="text-sm text-gray-700 mt-2">خطا در بارگذاری آمار</p>
                    <p class="text-xs text-gray-500 mt-1">${data.message || 'خطای ناشناخته'}</p>
                </div>
            `;
        }
    } catch (error) {
        statsElement.innerHTML = `
            <div class="text-center py-4">
                <i class="fa-solid fa-exclamation-triangle text-2xl text-red-500"></i>
                <p class="text-sm text-gray-700 mt-2">خطا در ارتباط با سرور</p>
                <p class="text-xs text-gray-500 mt-1">${error.message}</p>
            </div>
        `;
    }
}

/**
 * خروجی گرفتن از مخاطبین به صورت CSV
 */
async function exportContactsCSV() {
    try {
        showNotification('info', 'در حال ایجاد فایل خروجی مخاطبین...');
        
        const response = await fetch('/export-contacts-csv');
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.message || 'خطا در ایجاد فایل');
        }
        
        // دریافت فایل
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        
        // ایجاد لینک دانلود
        const a = document.createElement('a');
        a.href = url;
        
        // استخراج نام فایل از headers
        const contentDisposition = response.headers.get('Content-Disposition');
        let filename = `مخاطبین_ایتا_${new Date().toLocaleDateString('fa-IR').replace(/\//g, '-')}.csv`;
        
        if (contentDisposition) {
            const filenameMatch = contentDisposition.match(/filename="(.+)"/);
            if (filenameMatch && filenameMatch[1]) {
                filename = filenameMatch[1];
            }
        }
        
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        
        // آزاد کردن منابع
        window.URL.revokeObjectURL(url);
        
        showNotification('success', 'فایل مخاطبین با موفقیت دانلود شد');
        
    } catch (error) {
        console.error('Error exporting contacts:', error);
        showNotification('error', `خطا در دانلود مخاطبین: ${error.message}`);
    }
}

/**
 * پاک کردن جدول خاص از دیتابیس
 */
async function clearDatabaseTable(tableName) {
    const tableNameText = tableName === 'contacts' ? 'مخاطبین' : 'گزارش‌ها';
    
    if (!confirm(`آیا مطمئنید که می‌خواهید جدول ${tableNameText} را پاک کنید؟\nاین عمل غیرقابل بازگشت است!`)) {
        return;
    }
    
    try {
        const params = new URLSearchParams();
        params.append('table', tableName);
        
        const res = await fetch('/clear-database', {method: 'POST', body: params});
        const data = await res.json();
        
        if (data.status === 'success') {
            showNotification('success', `جدول ${tableNameText} با موفقیت پاک شد`);
            loadDatabaseStats();
            
            // اگر گزارش‌ها پاک شدند، گزارش نمایش را هم رفرش کن
            if (tableName === 'reports') {
                loadDispatchReport();
            }
        } else {
            showNotification('error', `خطا در پاک کردن جدول: ${data.message}`);
        }
    } catch (error) {
        showNotification('error', `خطا در ارتباط با سرور: ${error.message}`);
    }
}

/**
 * پاک کردن کامل دیتابیس
 */
async function clearEntireDatabase() {
    if (!confirm(`⚠️  هشدار جدی!\n\nآیا مطمئنید که می‌خواهید تمام دیتابیس را پاک کنید؟\nاین عمل تمام مخاطبین و گزارش‌های ذخیره شده را حذف می‌کند و غیرقابل بازگشت است!\n\nقبل از ادامه، مطمئن شوید که از داده‌های مهم خروجی گرفته‌اید.`)) {
        return;
    }
    
    try {
        const res = await fetch('/clear-database', {method: 'POST'});
        const data = await res.json();
        
        if (data.status === 'success') {
            showNotification('success', 'دیتابیس با موفقیت پاک شد');
            loadDatabaseStats();
            loadDispatchReport();
        } else {
            showNotification('error', `خطا در پاک کردن دیتابیس: ${data.message}`);
        }
    } catch (error) {
        showNotification('error', `خطا در ارتباط با سرور: ${error.message}`);
    }
}

// =================================== 10. Initialization ===================================

/**
 * فعال‌سازی تب اول به صورت پیش‌فرض هنگام بارگذاری صفحه
 */
document.addEventListener('DOMContentLoaded', () => {
    const defaultTab = document.querySelector('.nav-link');
    if (defaultTab) {
        defaultTab.click();
    }
    
    // بارگذاری آمار دیتابیس
    loadDatabaseStats();
});