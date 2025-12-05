# ================ الكود الكامل الجديد الشغال 100% ديسمبر 2025 ================

import json
import logging
import traceback
import time
import random
from datetime import datetime, timedelta
from urllib.parse import urljoin

import pytz
from bs4 import BeautifulSoup
from curl_cffi import requests  # <-- هذه هي المكتبة السحرية الجديدة

# ================= إعداد Logging ممتاز لـ Render =================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger(__name__)
import sys
sys.stdout.reconfigure(line_buffering=True)

# ================= إعدادات إعادة المحاولة =================
MAX_RETRIES = 6
BASE_DELAY = 8

def retry(func):
    def wrapper(*args, **kwargs):
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                wait = BASE_DELAY * (2 ** (attempt - 1)) + random.uniform(0, 7)
                now = datetime.now(pytz.timezone('Africa/Cairo')).strftime('%H:%M:%S')
                log.error(f"[{now}] خطأ ({attempt}/{MAX_RETRIES}): {e}")
                log.error(traceback.format_exc())
                if attempt == MAX_RETRIES:
                    log.error("فشل نهائي، ننتقل...")
                    return None
                log.warning(f"إعادة المحاولة بعد {wait:.1f} ثانية...")
                time.sleep(wait)
        return None
    return wrapper

def get_egypt_time():
    return datetime.now(pytz.timezone('Africa/Cairo'))

# ================= الدوال الأساسية باستخدام curl-cffi =================
@retry
def safe_get(session, url, **kwargs):
    log.info(f"GET → {url}")
    if kwargs.get('params'):
        log.info(f"    params → {kwargs['params']}")
    if kwargs.get('headers'):
        log.info(f"    headers → {kwargs['headers']}")

    resp = session.get(url, timeout=30, **kwargs)

    log.info(f"← {resp.status_code} | {len(resp.text)} حرف | {resp.url}")
    if resp.status_code == 403:
        log.error("تحذير: 403 Forbidden! الرد محفوظ في 403_debug.html")
        with open("403_debug.html", "w", encoding="utf-8") as f:
            f.write(resp.text)
        resp.raise_for_status()  # عشان يدخل الـ retry

    preview = resp.text.replace('\n', ' ').replace').replace('\r', '')[0:1200]
    log.info(f"    معاينة الرد: {preview}...")
    resp.raise_for_status()
    return resp

@retry
def safe_post(session, url, **kwargs):
    log.info(f"POST → {url}")
    if kwargs.get('data'):
        log.info(f"    البيانات → {kwargs['data']}")
    resp = session.post(url, timeout=30, **kwargs)
    log.info(f"← {resp.status_code} بعد POST | {resp.url}")
    preview = resp.text.replace('\n', ' ')[0:1000]
    log.info(f"    معاينة الرد: {preview}...")
    return resp

# ================= الدالة الرئيسية لجلب ورديات الغد =================
def fetch_and_print_shifts():
    log.info("=== بدء جلب ورديات الغد ===")

    # أقوى إصدار حاليًا ضد Cloudflare (ديسمبر 2025)
    session = requests.Session(impersonate="chrome124", timeout=30)

    # نضيف headers مصرية عشان يبدو طبيعي أكتر
    session.headers.update({
        'Accept-Language': 'ar-EG,ar;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
    })

    try:
        # 1. تسجيل الدخول
        login_page = safe_get(session, 'https://wardyati.com/login/')
        soup = BeautifulSoup(login_page.text, 'html.parser')
        csrf_token = soup.find('input', {'name': 'csrfmiddlewaretoken'})['value']

        login_data = {
            'username': 'mm2872564@gmail.com',
            'password': 'Mm@12345',
            'csrfmiddlewaretoken': csrf_token,
        }

        login_resp = safe_post(session, 'https://wardyati.com/login/', data=login_data,
                               headers={'Referer': 'https://wardyati.com/login/'})

        if 'تسجيل الدخول' in login_resp.text or 'اسم المستخدم أو كلمة المرور' in login_resp.text:
            log.error("فشل تسجيل الدخول – تأكد من البيانات أو تم تغيير كلمة السر")
            return False

        log.info("تم تسجيل الدخول بنجاح")

        # 2. الذهاب لصفحة الغرف
        rooms_page = safe_get(session, 'https://wardyati.com/rooms/')
        soup = BeautifulSoup(rooms_page.text, 'html.parser')

        target_text = 'شيفتات جراحة غدد شهر 12'
        room_link = None
        for a in soup.find_all('a', class_='stretched-link'):
            if target_text in a.get_text(strip=True):
                room_link = urljoin('https://wardyati.com', a['href'])
                log.info(f"تم العثور على الغرفة: {room_link}")
                break

        if not room_link:
            log.error("لم يتم العثور على الغرفة – ربما تغير اسمها")
            return False

        # 3. جلب تقويم الشهر القادم
        tomorrow = get_egypt_time() + timedelta(days=1)
        arena_url = urljoin(room_link, 'arena/')
        arena_resp = safe_get(session, arena_url, params={
            'view': 'monthly',
            'year': tomorrow.year,
            'month': tomorrow.month
        })

        data = arena_resp.json()
        target_date = tomorrow.strftime('%Y-%m-%d')

        if target_date not in data.get('shift_instances_by_date', {}):
            day_name = tomorrow.strftime('%A')
            formatted = tomorrow.strftime('%d/%m')
            log.info(f"لا توجد ورديات يوم الغد: {day_name} {formatted}")
            return True

        # 4. استخراج التفاصيل
        shifts_by_type = {}
        for shift in data['shift_instances_by_date'][target_date]:
            shift_type = shift.get('shift_type_name', 'غير معروف')
            details_url = urljoin('https://wardyati.com/', shift['get_shift_instance_details_url'])

            details_resp = safe_get(session, details_url, headers={'HX-Request': 'true'})
            if not details_resp:
                continue

            details = details_resp.json()
            for h in details.get('holdings', []):
                name = h.get('apparent_name', 'غير معروف')
                phone = ''
                member_url = h.get('urls', {}).get('get_member_info')
                if member_url:
                    mem_resp = safe_get(session, urljoin('https://wardyati.com/', member_url),
                                        headers={'HX-Request': 'true'})
                    if mem_resp:
                        try:
                            mdata = mem_resp.json()
                            phone = mdata.get('room_member', {}).get('contact_info', '')
                        except:
                            pass
                shifts_by_type.setdefault(shift_type, []).append({'name': name, 'phone': phone})

        # 5. طباعة النتيجة النهائية بترتيب جميل
        day_name = tomorrow.strftime('%A')
        formatted_date = tomorrow.strftime('%d/%m')
        log.info(f"\nورديات الغد: {day_name} {formatted_date}")
        log.info("=" * 60)

        order = ['Day', 'Day Work', 'Night']
        printed = set()

        for shift_type in order + list(shifts_by_type.keys()):
            if shift_type in shifts_by_type and shift_type not in printed:
                log.info(f"\n{shift_type.upper()}")
                seen = set()
                for person in shifts_by_type[shift_type]:
                    key = (person['name'], person['phone'])
                    if key not in seen:
                        seen.add(key)
                        log.info(f"  • {person['name']}")
                        if person['phone']:
                            log.info(f"    📞 {person['phone']}")
                printed.add(shift_type)

        log.info("=" * 60)
        log.info("تم بنجاح!")
        return True

    except Exception as e:
        log.error("خطأ غير متوقع:")
        log.error(traceback.format_exc())
        return False

# ================= الحلقة الرئيسية (تشتغل كل يوم الساعة 2 ظهرًا) =================
def main():
    log.info("البوت شغال الآن – يجيب ورديات الغد كل يوم الساعة 2 ظهرًا")
    log.info("-" * 80)
    last_printed_date = None

    while True:
        try:
            now = get_egypt_time()
            current_date = now.strftime('%Y-%m-%d')

            # نشغل كل يوم الساعة 14:00 إلى 14:29
            if now.hour == 16 and now.minute < 59 and last_printed_date != current_date:
                log.info(f"[{now.strftime('%H:%M:%S')}] جاري جلب ورديات الغد...")
                success = fetch_and_print_shifts()
                if success:
                    last_printed_date = current_date
                log.info("-" * 70)

            time.sleep(25)

        except Exception as e:
            log.error("خطأ في الحلقة الرئيسية:")
            log.error(traceback.format_exc())
            time.sleep(30)

# ================= تشغيل السيرفر إذا كان موجود + البوت
if __name__ == "__main__":
    try:
        from app import server
        server()
    except ImportError:
        pass

    try:
        main()
    except KeyboardInterrupt:
        log.info("تم إيقاف البوت يدويًا")
