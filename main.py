import cloudscraper
from bs4 import BeautifulSoup
import json
from urllib.parse import urljoin
from datetime import datetime, timedelta
import pytz
import time
import random
import logging
import traceback
import os

# ================= إعداد الـ Logging =================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger(__name__)

# لضمان ظهور الـ logs فورًا (مهم على Render و Pydroid)
import sys
sys.stdout.reconfigure(line_buffering=True)

# ================= إعدادات الكوكيز والدخول =================
COOKIES_FILE = 'wardyati_cookies.json'

LOGIN_CREDENTIALS = {
    'username': 'mm2872564@gmail.com',
    'password': 'Mm@12345'
}

# ================= إعدادات إعادة المحاولة =================
MAX_RETRIES = 5
BASE_DELAY = 7

def retry(func):
    def wrapper(*args, **kwargs):
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                wait = BASE_DELAY * (2 ** (attempt - 1)) + random.uniform(0, 5)
                now = datetime.now(pytz.timezone('Africa/Cairo')).strftime('%H:%M:%S')
                log.error(f"[{now}] خطأ ({attempt}/{MAX_RETRIES}): {e}")
                if attempt == MAX_RETRIES:
                    log.error("فشل نهائي")
                    return None
                log.warning(f"إعادة المحاولة بعد {wait:.1f} ثانية...")
                time.sleep(wait)
        return None
    return wrapper

def get_egypt_time():
    return datetime.now(pytz.timezone('Africa/Cairo'))

@retry
def safe_get(scraper, url, **kwargs):
    log.info(f"GET → {url}")
    resp = scraper.get(url, timeout=30, **kwargs)
    log.info(f"← {resp.status_code}")
    resp.raise_for_status()
    return resp

@retry
def safe_post(scraper, url, **kwargs):
    log.info(f"POST → {url}")
    resp = scraper.post(url, timeout=30, **kwargs)
    log.info(f"← {resp.status_code}")
    if resp.status_code >= 400:
        raise Exception(f"فشل الطلب: {resp.status_code}")
    return resp

# ================= تحميل الكوكيز =================
def load_cookies(scraper):
    if not os.path.exists(COOKIES_FILE):
        log.info("ملف الكوكيز غير موجود → سيتم تسجيل الدخول")
        return False
    try:
        with open(COOKIES_FILE, 'r', encoding='utf-8') as f:
            cookies = json.load(f)
        # تحميل الكوكيز للدومين الصحيح
        for key, value in cookies.items():
            scraper.cookies.set(key, value, domain='.wardyati.com')
        log.info("تم تحميل الكوكيز من الملف بنجاح")
        return True
    except Exception as e:
        log.warning(f"فشل تحميل الكوكيز: {e}")
        return False

# ================= حفظ الكوكيز =================
def save_cookies(scraper):
    cookies_dict = {}
    for cookie in scraper.cookies:
        if cookie.name in ['csrftoken', 'sessionid']:
            cookies_dict[cookie.name] = cookie.value
    try:
        with open(COOKIES_FILE, 'w', encoding='utf-8') as f:
            json.dump(cookies_dict, f, ensure_ascii=False, indent=4)
        log.info(f"تم حفظ الكوكيز في {COOKIES_FILE}")
        log.info(f"sessionid: {cookies_dict.get('sessionid', 'غير موجود')}")
    except Exception as e:
        log.error(f"خطأ في حفظ الكوكيز: {e}")

# ================= تسجيل الدخول واستخراج الكوكيز =================
def login_and_save_cookies(scraper):
    log.info("بدء تسجيل الدخول لاستخراج كوكيز جديدة...")
    try:
        resp = safe_get(scraper, 'https://wardyati.com/login/')
        soup = BeautifulSoup(resp.text, 'html.parser')
        token = soup.find('input', {'name': 'csrfmiddlewaretoken'})
        if not token:
            log.error("لم يتم العثور على CSRF token")
            return False
        csrf_token = token['value']
        log.info("تم جلب CSRF token")

        data = {
            'username': LOGIN_CREDENTIALS['username'],
            'password': LOGIN_CREDENTIALS['password'],
            'csrfmiddlewaretoken': csrf_token,
        }

        login_resp = safe_post(scraper, 'https://wardyati.com/login/', data=data,
                               headers={'Referer': 'https://wardyati.com/login/'}, allow_redirects=True)

        if login_resp.status_code != 200 or 'تسجيل الدخول' in login_resp.text:
            log.error("فشل تسجيل الدخول - ربما كلمة السر تغيرت أو تم حظر الـ IP")
            return False

        save_cookies(scraper)
        log.info("تم تسجيل الدخول وحفظ الكوكيز بنجاح!")
        return True
    except Exception as e:
        log.error(f"استثناء أثناء تسجيل الدخول: {e}")
        return False

# ================= جلب ورديات الغد =================
def fetch_and_print_shifts():
    log.info("=== بدء جلب ورديات الغد ===")
    scraper = cloudscraper.create_scraper()

    # 1. تحميل الكوكيز
    if not load_cookies(scraper):
        if not login_and_save_cookies(scraper):
            log.error("فشل تسجيل الدخول → لا يمكن المتابعة")
            return False
    else:
        # اختبار إذا كانت الكوكيز لا تزال صالحة
        test = safe_get(scraper, 'https://wardyati.com/rooms/')
        if test and ('تسجيل الدخول' in test.text or '/login/' in test.url):
            log.info("الكوكيز منتهية الصلاحية → تسجيل دخول جديد")
            if not login_and_save_cookies(scraper):
                return False

    # البحث عن الغرفة
    home = safe_get(scraper, 'https://wardyati.com/rooms/')
    soup = BeautifulSoup(home.text, 'html.parser')
    target_text = 'شيفتات جراحة غدد شهر 12'
    room_link = None
    for div in soup.find_all('div', class_='overflow-wrap'):
        if target_text in div.get_text(strip=True):
            a = div.find_parent('div', class_='card-body')
            if a:
                link = a.find('a', class_='stretched-link')
                if link:
                    room_link = urljoin('https://wardyati.com/', link['href'])
                    log.info(f"تم العثور على الغرفة: {room_link}")
                    break

    if not room_link:
        log.error("لم يتم العثور على الغرفة! تأكد من النص داخل علامات الاقتباس")
        return False

    # جلب جدول الشهر
    tomorrow = get_egypt_time() + timedelta(days=1)
    arena_url = urljoin(room_link, 'arena/')
    arena = safe_get(scraper, arena_url, params={
        'view': 'monthly',
        'year': tomorrow.year,
        'month': tomorrow.month
    })

    try:
        data = json.loads(arena.text)
    except:
        log.error("فشل تحويل رد arena إلى JSON")
        return False

    target_date = tomorrow.strftime('%Y-%m-%d')
    if target_date not in data.get('shift_instances_by_date', {}):
        log.info(f"لا توجد ورديات غدًا: {tomorrow.strftime('%d/%m %A')}")
        return True

    shifts_by_type = {}
    for shift in data['shift_instances_by_date'][target_date]:
        shift_type = shift.get('shift_type_name', 'غير معروف')
        details_url = urljoin('https://wardyati.com/', shift['get_shift_instance_details_url'])
        details_resp = safe_get(scraper, details_url, headers={'HX-Request': 'true'})
        if not details_resp:
            continue
        try:
            details = json.loads(details_resp.text)
            for h in details.get('holdings', []):
                name = h.get('apparent_name', 'غير معروف')
                phone = ''
                mem_url = h.get('urls', {}).get('get_member_info')
                if mem_url:
                    mem_resp = safe_get(scraper, urljoin('https://wardyati.com/', mem_url), headers={'HX-Request': 'true'})
                    if mem_resp:
                        try:
                            phone = json.loads(mem_resp.text).get('room_member', {}).get('contact_info', '')
                        except:
                            pass
                shifts_by_type.setdefault(shift_type, []).append({'name': name, 'phone': phone})
        except:
            continue

    # طباعة النتيجة النهائية
    log.info(f"\nورديات الغد ({tomorrow.strftime('%A %d/%m')}):")
    log.info("=" * 60)
    order = ['Day', 'Day Work', 'Night']
    printed = set()
    for st in order + list(shifts_by_type.keys()):
        if st in shifts_by_type and st not in printed:
            log.info(f"\n{st}:")
            seen = set()
            for p in shifts_by_type[st]:
                key = (p['name'], p['phone'])
                if key not in seen:
                    seen.add(key)
                    log.info(f"  • {p['name']}")
                    if p['phone']:
                        log.info(f"    {p['phone']}")
            printed.add(st)
    log.info("=" * 60)
    return True

# ================= الحلقة الرئيسية =================
def main():
    log.info("البوت شغال الآن - يستخدم الكوكيز مع fallback لتسجيل الدخول")
    log.info("-" * 70)
    last_printed = None

    while True:
        try:
            now = get_egypt_time()
            today = now.strftime('%Y-%m-%d')
            hour = now.hour

            # يطبع الورديات كل يوم من 2 ظهرًا لـ 2:30 ظهرًا
            if hour == 18 and now.minute < 58 and last_printed != today:
                log.info(f"[{now.strftime('%H:%M')}] جاري جلب ورديات الغد...")
                success = fetch_and_print_shifts()
                if success:
                    last_printed = today
                log.info("-" * 60)

            time.sleep(20)
        except Exception as e:
            log.error("خطأ عام في الحلقة الرئيسية:")
            log.error(traceback.format_exc())
            time.sleep(30)

if __name__ == "__main__":
    # إذا كنت تستخدم Render وفيه ملف app.py
    try:
        from app import server
        server()
    except ImportError:
        pass

    main()
