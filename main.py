import cloudscraper
from bs4 import BeautifulSoup
import json
from urllib.parse import urljoin
from datetime import datetime, timedelta
import pytz
import time
import random
from app import server 

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
                print(f"[{now}] خطأ ({attempt}/{MAX_RETRIES}): {e}")
                if attempt == MAX_RETRIES:
                    print("فشل نهائي في هذه الخطوة، ننتقل...")
                    return None
                print(f"إعادة المحاولة بعد {wait:.1f} ثانية...")
                time.sleep(wait)
        return None
    return wrapper

def get_egypt_time():
    return datetime.now(pytz.timezone('Africa/Cairo'))

@retry
def safe_get(scraper, url, **kwargs):
    resp = scraper.get(url, timeout=25, **kwargs)
    resp.raise_for_status()
    return resp

@retry
def safe_post(scraper, url, **kwargs):
    resp = scraper.post(url, timeout=25, **kwargs)
    if resp.status_code not in (200, 302):
        raise Exception(f"فشل POST: {resp.status_code}")
    return resp

def fetch_and_print_shifts():
    scraper = cloudscraper.create_scraper()

    # 1. تسجيل الدخول
    login_page = safe_get(scraper, 'https://wardyati.com/login/')
    if not login_page:
        return False

    soup = BeautifulSoup(login_page.text, 'html.parser')
    csrf = soup.find('input', {'name': 'csrfmiddlewaretoken'})
    csrf_token = csrf['value'] if csrf else ''

    login_data = {
        'username': 'mm2872564@gmail.com',
        'password': 'Mm@12345',
        'csrfmiddlewaretoken': csrf_token,
    }

    login_resp = safe_post(scraper, 'https://wardyati.com/login/', data=login_data,
                           headers={'Referer': 'https://wardyati.com/login/'}, allow_redirects=True)
    if not login_resp or 'ممنوع' in login_resp.text or '403' in login_resp.text:
        print("فشل تسجيل الدخول حتى بعد كل المحاولات")
        return False

    # 2. البحث عن الغرفة
    home = safe_get(scraper, 'https://wardyati.com/rooms/')
    if not home:
        return False

    soup = BeautifulSoup(home.text, 'html.parser')
    target_text = 'شيفتات جراحة غدد شهر 12'  # غيّر الرقم حسب الشهر الحالي لو احتجت
    room_link = None
    for div in soup.find_all('div', class_='overflow-wrap'):
        if target_text in div.text.strip():
            card = div.find_parent('div', class_='card-body')
            if card:
                a = card.find('a', class_='stretched-link')
                if a:
                    room_link = urljoin('https://wardyati.com/', a.get('href'))
                    break

    if not room_link:
        print("لم يتم العثور على الغرفة - تأكد من اسم الشهر (شهر 12؟)")
        return False

    # 3. تحديد تاريخ الغد (التعديل الأساسي)
    egypt_now = get_egypt_time()
    tomorrow = egypt_now + timedelta(days=1)
    target_date = tomorrow.strftime('%Y-%m-%d')
    target_year = tomorrow.year
    target_month = tomorrow.month

    # 4. جلب بيانات الشهر
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
    except:
        print("فشل تحليل JSON من arena")
        return False

    if target_date not in data.get('shift_instances_by_date', {}):
        day_name = tomorrow.strftime('%A')
        formatted = tomorrow.strftime('%d/%m')
        print(f"\nلا توجد ورديات يوم الغد: {day_name} {formatted}")
        print("(ربما إجازة أو لم تُحدد بعد)")
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
        except:
            continue

    # 5. طباعة ورديات الغد
    if shifts_by_type:
        day_name = tomorrow.strftime('%A')
        formatted = tomorrow.strftime('%d/%m')
        print(f"\nورديات الغد: {day_name} {formatted}")
        print("=" * 50)

        order = ['Day', 'Day Work', 'Night']
        printed = set()

        for st in order:
            if st in shifts_by_type:
                print(f"\n{st}")
                seen = set()
                for p in shifts_by_type[st]:
                    key = (p['name'], p['phone'])
                    if key not in seen:
                        seen.add(key)
                        print(f'"{p["name"]}')
                        if p['phone']:
                            print(f'({p["phone"]})')
                printed.add(st)

        for st in shifts_by_type:
            if st not in printed:
                print(f"\n{st}")
                seen = set()
                for p in shifts_by_type[st]:
                    key = (p['name'], p['phone'])
                    if key not in seen:
                        seen.add(key)
                        print(f'"{p["name"]}')
                        if p['phone']:
                            print(f'({p["phone"]})')

        print("=" * 50)
    else:
        print("لا توجد بيانات ورديات الغد رغم المحاولات")

    return True

# ================= الحلقة الرئيسية (نفس أسلوبك الأصلي 100%) =================
def main():
    print("البوت شغال الآن - يطبع ورديات الغد يوميًا من 8:00 إلى 8:44 صباحًا")
    print("بإذن الله لن يسقط أبدًا مهما حصل")
    print("-" * 70)

    last_printed_date = None

    while True:
        now = get_egypt_time()
        current_date = now.strftime('%Y-%m-%d')
        current_hour = now.hour
        current_minute = now.minute

        # نفس الشرط الأصلي بالضبط
        if current_hour == 8 and current_minute < 45 and last_printed_date != current_date:
            print(f"\n[{now.strftime('%H:%M:%S')}] جاري جلب ورديات الغد...")
            print("-" * 60)
            success = fetch_and_print_shifts()
            print("-" * 60)
            if success:
                last_printed_date = current_date

        time.sleep(9)

if __name__ == "__main__":
    server()
    try:
        main()
    except KeyboardInterrupt:
        print("\nتم إيقاف البوت يدويًا")
    except Exception as e:
        print(f"خطأ عام: {e}")
        time.sleep(10)
        main()  # يعيد تشغيل البوت حتى لو الكود كله سقط
