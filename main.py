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
import requests  # إضافة لـ fallback
from app import server 

# ================= إعداد Logging =================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger(__name__)
import sys
sys.stdout.reconfigure(line_buffering=True)

# ================= Headers مخصصة =================
custom_headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Referer': 'https://wardyati.com/',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
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
                tb = traceback.format_exc()
                log.error(f"[{now}] خطأ ({attempt}/{MAX_RETRIES}): {e}\n{tb}")
                if attempt == MAX_RETRIES:
                    log.error("فشل نهائي في هذه الخطوة، ننتقل...")
                    return None
                log.warning(f"إعادة المحاولة بعد {wait:.1f} ثانية...")
                time.sleep(wait)
        return None
    return wrapper

def get_egypt_time():
    return datetime.now(pytz.timezone('Africa/Cairo'))

@retry
def safe_get(scraper, url, **kwargs):
    log.info(f"GET → {url} | params={kwargs.get('params')}")
    try:
        resp = scraper.get(url, timeout=25, headers=custom_headers, **kwargs)
        log.info(f"← {resp.status_code} من {url} | رد خام: {resp.text[:500]}")  # طباعة جزء من الرد للتشخيص
        resp.raise_for_status()
        return resp
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            log.error(f"403 Forbidden: ربما IP محظورة أو حماية. جرب headers مختلفة.")
            log.error(f"رد الخطأ الكامل: {e.response.text}")
        raise

@retry
def safe_post(scraper, url, **kwargs):
    log.info(f"POST → {url}")
    resp = scraper.post(url, timeout=25, headers=custom_headers, **kwargs)
    if resp.status_code not in (200, 302):
        log.error(f"فشل POST: {resp.status_code} | رد: {resp.text[:500]}")
        raise Exception(f"فشل POST: {resp.status_code}")
    log.info(f"← {resp.status_code} بعد POST")
    return resp

def fetch_and_print_shifts():
    log.info("=== بدء جلب ورديات الغد ===")
    try:
        # تحسين cloudscraper مع خيارات لتجاوز
        scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False},  # محاكاة متصفح حقيقي
            delay=10,  # delay لتجنب rate limiting
            captcha={'provider': 'return_response'}  # إذا كان captcha، لكن نادراً
        )

        # 1. تسجيل الدخول (مع fallback إذا فشل cloudscraper)
        try:
            login_page = safe_get(scraper, 'https://wardyati.com/login/')
        except:
            log.warning("فشل cloudscraper، جرب fallback مع requests عادي...")
            session = requests.Session()
            session.headers.update(custom_headers)
            login_page = session.get('https://wardyati.com/login/', timeout=25)
            login_page.raise_for_status()

        if not login_page:
            return False

        soup = BeautifulSoup(login_page.text, 'html.parser')
        csrf = soup.find('input', {'name': 'csrfmiddlewaretoken'})
        csrf_token = csrf['value'] if csrf else ''
        if not csrf_token:
            log.error("لم يتم العثور على csrf token")
            return False

        login_data = {
            'username': 'mm2872564@gmail.com',
            'password': 'Mm@12345',
            'csrfmiddlewaretoken': csrf_token,
        }

        login_resp = safe_post(scraper, 'https://wardyati.com/login/', data=login_data,
                               headers={'Referer': 'https://wardyati.com/login/'}, allow_redirects=True)
        if not login_resp or 'ممنوع' in login_resp.text or '403' in login_resp.text:
            log.error("فشل تسجيل الدخول - ربما تم حظر الـ IP أو تغيّر الكود")
            log.error(f"جزء من الرد: {login_resp.text[:1000]}")
            return False

        log.info("تم تسجيل الدخول بنجاح")

        # باقي الكود كما هو الأصلي، مع إضافة headers في كل safe_get/safe_post

        home = safe_get(scraper, 'https://wardyati.com/rooms/')
        if not home:
            return False

        soup = BeautifulSoup(home.text, 'html.parser')
        target_text = 'شيفتات جراحة غدد شهر 12'  
        room_link = None
        for div in soup.find_all('div', class_='overflow-wrap'):
            if target_text in div.text.strip():
                card = div.find_parent('div', class_='card-body')
                if card:
                    a = card.find('a', class_='stretched-link')
                    if a:
                        room_link = urljoin('https://wardyati.com/', a.get('href'))
                        log.info(f"تم العثور على الغرفة: {room_link}")
                        break

        if not room_link:
            log.error("لم يتم العثور على الغرفة - تأكد من النص")
            return False

        tomorrow = get_egypt_time() + timedelta(days=1)
        target_date = tomorrow.strftime('%Y-%m-%d')
        target_year = tomorrow.year
        target_month = tomorrow.month

        arena_url = urljoin(room_link, 'arena/')
        arena_resp = safe_get(scraper, arena_url, params={
            'view': 'monthly',
            'year': target_year,
            'month': target_month
        })
        if not arena_resp:
            return False

        try:
            data = json.loads(arena_resp.text)
            log.info(f"تم جلب بيانات الشهر بنجاح")
        except Exception as e:
            log.error(f"فشل تحليل JSON: {e}")
            return False

        if target_date not in data.get('shift_instances_by_date', {}):
            day_name = tomorrow.strftime('%A')
            formatted = tomorrow.strftime('%d/%m')
            log.info(f"لا توجد ورديات يوم الغد: {day_name} {formatted}")
            return True

        shifts_by_type = {}
        for shift in data['shift_instances_by_date'][target_date]:
            shift_type = shift.get('shift_type_name', 'Unknown')
            details_url = urljoin('https://wardyati.com/', shift['get_shift_instance_details_url'])

            details_resp = safe_get(scraper, details_url, headers={'HX-Request': 'true'})
            if not details_resp:
                continue

            try:
                details = json.loads(details_resp.text)
                for h in details.get('holdings', []):
                    name = h.get('apparent_name', 'غير معروف')
                    phone = ''
                    member_url = h.get('urls', {}).get('get_member_info')
                    if member_url:
                        mem_resp = safe_get(scraper, urljoin('https://wardyati.com/', member_url),
                                            headers={'HX-Request': 'true'})
                        if mem_resp:
                            try:
                                mdata = json.loads(mem_resp.text)
                                phone = mdata.get('room_member', {}).get('contact_info', '')
                            except:
                                pass
                    shifts_by_type.setdefault(shift_type, []).append({'name': name, 'phone': phone})
            except Exception as e:
                log.error(f"خطأ في تفاصيل الشيفت: {e}")

        # طباعة النتيجة
        if shifts_by_type:
            day_name = tomorrow.strftime('%A')
            formatted = tomorrow.strftime('%d/%m')
            log.info(f"\nورديات الغد: {day_name} {formatted}")
            log.info("=" * 50)

            order = ['Day', 'Day Work', 'Night']
            printed = set()

            for st in order:
                if st in shifts_by_type:
                    log.info(f"\n{st}")
                    seen = set()
                    for p in shifts_by_type[st]:
                        key = (p['name'], p['phone'])
                        if key not in seen:
                            seen.add(key)
                            log.info(f'"{p["name"]}')
                            if p['phone']:
                                log.info(f'({p["phone"]})')
                    printed.add(st)

            for st in shifts_by_type:
                if st not in printed:
                    log.info(f"\n{st}")
                    seen = set()
                    for p in shifts_by_type[st]:
                        key = (p['name'], p['phone'])
                        if key not in seen:
                            seen.add(key)
                            log.info(f'"{p["name"]}')
                            if p['phone']:
                                log.info(f'({p["phone"]})')

            log.info("=" * 50)
        else:
            log.info("لا توجد بيانات ورديات الغد")

        return True

    except Exception as e:
        log.error("خطأ غير متوقع:")
        log.error(traceback.format_exc())
        return False

# ================= الحلقة الرئيسية =================
def main():
    log.info("البوت شغال الآن")
    log.info("-" * 70)

    last_printed_date = None

    while True:
        try:
            now = get_egypt_time()
            current_date = now.strftime('%Y-%m-%d')
            current_hour = now.hour
            current_minute = now.minute

            if current_hour == 14 and current_minute < 58 and last_printed_date != current_date:
                log.info(f"[{now.strftime('%H:%M:%S')}] جاري جلب...")
                success = fetch_and_print_shifts()
                if success:
                    last_printed_date = current_date
                log.info("-" * 60)

            time.sleep(20)

        except Exception as e:
            log.error("خطأ في الحلقة:")
            log.error(traceback.format_exc())
            time.sleep(10)

if __name__ == "__main__":
    server()
    try:
        main()
    except KeyboardInterrupt:
        log.info("إيقاف يدوي")
    except Exception as e:
        log.error(f"خطأ فادح: {e}")
        main()  # إعادة تشغيل
