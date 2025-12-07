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
from curl_cffi import requests as curl_requests
from fake_useragent import UserAgent
from app import server 
import requests
import os
from collections import defaultdict

# ================= إعداد Logging ليعمل ممتاز على Render =================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger(__name__)

# لضمان ظهور كل شيء في Render Logs حتى لو كان هناك buffering
import sys
sys.stdout.reconfigure(line_buffering=True)

# ================= إعدادات Gist =================
GIST_ID = "cd4bd1519749da63f37eaa594199e1df"
GITHUB_TOKEN_PART1 = "ghp_26iDRXBM6Vh9m"
GITHUB_TOKEN_PART2 = "egs7uCr6eEMi3It0T0UB3xJ"
GITHUB_TOKEN = GITHUB_TOKEN_PART1 + GITHUB_TOKEN_PART2
SHIFTS_GIST_FILENAME = "shifts_data.json"
STATE_GIST_FILENAME = "bot_state.json"
RETRY_LOG_FILENAME = "retry_log.json"

# إعدادات API GitHub
GIST_API_URL = f"https://api.github.com/gists/{GIST_ID}"
HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28"
}

# ================= إعدادات إعادة المحاولة المتقدمة =================
MAX_GLOBAL_RETRIES = 5
MAX_SHIFT_RETRIES = 3  # محاولات لكل شيفت
MAX_MEMBER_RETRIES = 2  # محاولات لكل عضو
BASE_DELAY = 7
SHIFT_RETRY_DELAY = 3  # ثواني بين محاولات الشيفت
MEMBER_RETRY_DELAY = 2  # ثواني بين محاولات العضو

# ================= قائمة User-Agents حقيقية =================
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
]

# ================= إعدادات التعرف على أنواع الشيفتات =================
SHIFT_ALIASES = {
    'Day': ['Day', 'صباحي', 'Day Shift', 'صباح', 'Morning', 'صباحية'],
    'Day Work': ['Day Work', 'عمل يومي', 'دوام يومي', 'نهاري'],
    'Night': ['Night', 'ليلي', 'Night Duty', 'ليل', 'مسائي', 'Night Shift', 'ليلة']
}

def normalize_shift_type(shift_type):
    """توحيد أسماء أنواع الشيفتات"""
    if not shift_type:
        return 'Unknown'
    
    shift_type_lower = shift_type.lower()
    for main_type, aliases in SHIFT_ALIASES.items():
        for alias in aliases:
            if alias.lower() in shift_type_lower:
                return main_type
    return shift_type

def get_browser_headers(referer=None):
    """إنشاء headers مشابهة للمتصفح الحقيقي"""
    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,ar;q=0.8',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
        'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
    }
    if referer:
        headers['Referer'] = referer
    return headers

def create_curl_session():
    """إنشاء جلسة curl_cffi مع محاكاة بصمة المتصفح الحقيقي"""
    
    impersonate_options = [
        "chrome120",
        "chrome119", 
        "chrome116",
        "safari17_0",
        "safari15_3",
        "edge120",
    ]
    
    impersonate = random.choice(impersonate_options)
    log.info(f"استخدام بصمة المتصفح: {impersonate}")
    
    session = curl_requests.Session(impersonate=impersonate)
    
    return session

def create_enhanced_scraper():
    """إنشاء cloudscraper كبديل"""
    
    ua = random.choice(USER_AGENTS)
    
    browser_configs = [
        {'browser': 'chrome', 'platform': 'windows', 'desktop': True},
        {'browser': 'chrome', 'platform': 'darwin', 'desktop': True},
        {'browser': 'firefox', 'platform': 'windows', 'desktop': True},
    ]
    
    browser_config = random.choice(browser_configs)
    
    scraper = cloudscraper.create_scraper(
        browser=browser_config,
        delay=random.uniform(5, 10),
        interpreter='native',
        allow_brotli=False,
        debug=False,
    )
    
    scraper.headers.update({
        'User-Agent': ua,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'ar,en-US;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    })
    
    return scraper

def random_delay(min_sec=1.0, max_sec=4.0):
    """تأخير عشوائي للمحاكاة البشرية"""
    delay = random.uniform(min_sec, max_sec)
    time.sleep(delay)

def retry_with_backoff(max_retries=3, base_delay=2, max_delay=10):
    """ديكوراتور لإعادة المحاولة مع backoff"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries:
                        log.warning(f"فشل {func.__name__} بعد {max_retries} محاولات: {e}")
                        raise
                    
                    wait = min(base_delay * (2 ** (attempt - 1)), max_delay)
                    wait += random.uniform(0, 2)
                    
                    log.warning(f"إعادة محاولة {attempt}/{max_retries} لـ {func.__name__} بعد {wait:.1f} ثانية: {e}")
                    time.sleep(wait)
            return None
        return wrapper
    return decorator

def get_egypt_time():
    return datetime.now(pytz.timezone('Africa/Cairo'))

@retry_with_backoff(max_retries=3, base_delay=3)
def safe_get_with_retry(scraper, url, **kwargs):
    """GET مع إعادة محاولة"""
    log.info(f"GET → {url}")
    random_delay(0.5, 2)
    
    default_headers = get_browser_headers(kwargs.pop('referer', None))
    if 'headers' in kwargs:
        default_headers.update(kwargs['headers'])
    kwargs['headers'] = default_headers
    
    resp = scraper.get(url, timeout=30, **kwargs)
    log.info(f"← {resp.status_code} من {url}")
    resp.raise_for_status()
    return resp

@retry_with_backoff(max_retries=3, base_delay=3)
def safe_post_with_retry(scraper, url, **kwargs):
    """POST مع إعادة محاولة"""
    log.info(f"POST → {url}")
    random_delay(1, 3)
    
    default_headers = get_browser_headers(kwargs.get('headers', {}).get('Referer'))
    default_headers['Content-Type'] = 'application/x-www-form-urlencoded'
    if 'headers' in kwargs:
        default_headers.update(kwargs['headers'])
    kwargs['headers'] = default_headers
    
    resp = scraper.post(url, timeout=30, **kwargs)
    if resp.status_code not in (200, 302):
        raise Exception(f"فشل POST: {resp.status_code}")
    log.info(f"← {resp.status_code} بعد POST")
    return resp

# ================= دوال Gist =================

def save_shifts_to_gist(shifts_data, date, retry_stats=None):
    """حفظ بيانات الورديات في Gist"""
    try:
        # قراءة Gist الحالي
        response = requests.get(GIST_API_URL, headers=HEADERS)
        if response.status_code != 200:
            log.error(f"فشل قراءة Gist: {response.status_code}")
            return False
        
        gist_data = response.json()
        files = gist_data.get('files', {})
        
        # إضافة بيانات الورديات الجديدة
        if SHIFTS_GIST_FILENAME not in files:
            all_shifts = {}
        else:
            try:
                existing_content = files[SHIFTS_GIST_FILENAME]['content']
                all_shifts = json.loads(existing_content)
            except:
                all_shifts = {}
        
        # إضافة إحصائيات إعادة المحاولة
        shift_entry = {
            "timestamp": datetime.now().isoformat(),
            "shifts": shifts_data
        }
        
        if retry_stats:
            shift_entry["retry_stats"] = retry_stats
        
        # تحديث بيانات اليوم
        all_shifts[date] = shift_entry
        
        # حفظ فقط آخر 30 يوماً
        if len(all_shifts) > 30:
            sorted_dates = sorted(all_shifts.keys())
            dates_to_remove = sorted_dates[:-30]
            for date_to_remove in dates_to_remove:
                del all_shifts[date_to_remove]
        
        # تحديث Gist
        update_data = {
            "files": {
                SHIFTS_GIST_FILENAME: {
                    "content": json.dumps(all_shifts, ensure_ascii=False, indent=2)
                }
            }
        }
        
        update_response = requests.patch(GIST_API_URL, headers=HEADERS, json=update_data)
        
        if update_response.status_code == 200:
            log.info(f"تم حفظ الورديات ليوم {date} في Gist بنجاح")
            return True
        else:
            log.error(f"فشل حفظ الورديات في Gist: {update_response.status_code}")
            return False
            
    except Exception as e:
        log.error(f"خطأ في حفظ الورديات إلى Gist: {e}")
        return False

def save_retry_log_to_gist(retry_log):
    """حفظ سجل إعادة المحاولات في Gist"""
    try:
        response = requests.get(GIST_API_URL, headers=HEADERS)
        if response.status_code != 200:
            return False
        
        gist_data = response.json()
        files = gist_data.get('files', {})
        
        update_data = {
            "files": {
                RETRY_LOG_FILENAME: {
                    "content": json.dumps(retry_log, ensure_ascii=False, indent=2)
                }
            }
        }
        
        update_response = requests.patch(GIST_API_URL, headers=HEADERS, json=update_data)
        
        return update_response.status_code == 200
            
    except Exception as e:
        log.error(f"خطأ في حفظ سجل المحاولات: {e}")
        return False

def save_state_to_gist(last_execution_date, last_success_date, next_execution_time, retry_count=0):
    """حفظ حالة البوت في Gist"""
    try:
        response = requests.get(GIST_API_URL, headers=HEADERS)
        if response.status_code != 200:
            return False
        
        gist_data = response.json()
        files = gist_data.get('files', {})
        
        state_data = {
            "last_execution_date": last_execution_date,
            "last_success_date": last_success_date,
            "next_execution_time": next_execution_time,
            "last_update": datetime.now().isoformat(),
            "bot_status": "running",
            "retry_count": retry_count,
            "total_retries_today": retry_count
        }
        
        update_data = {
            "files": {
                STATE_GIST_FILENAME: {
                    "content": json.dumps(state_data, ensure_ascii=False, indent=2)
                }
            }
        }
        
        update_response = requests.patch(GIST_API_URL, headers=HEADERS, json=update_data)
        
        if update_response.status_code == 200:
            log.info("تم حفظ حالة البوت في Gist بنجاح")
            return True
        else:
            return False
            
    except Exception as e:
        log.error(f"خطأ في حفظ الحالة إلى Gist: {e}")
        return False

def load_state_from_gist():
    """قراءة حالة البوت من Gist"""
    try:
        response = requests.get(GIST_API_URL, headers=HEADERS)
        if response.status_code != 200:
            return None, None, 0
        
        gist_data = response.json()
        files = gist_data.get('files', {})
        
        if STATE_GIST_FILENAME not in files:
            return None, None, 0
        
        state_content = files[STATE_GIST_FILENAME]['content']
        state_data = json.loads(state_content)
        
        last_execution_date = state_data.get("last_execution_date")
        last_success_date = state_data.get("last_success_date")
        retry_count = state_data.get("retry_count", 0)
        
        log.info(f"تم تحميل الحالة: آخر تنفيذ={last_execution_date}, آخر نجاح={last_success_date}, محاولات={retry_count}")
        return last_execution_date, last_success_date, retry_count
        
    except Exception as e:
        log.error(f"خطأ في قراءة الحالة: {e}")
        return None, None, 0

def check_if_already_processed(date):
    """التحقق مما إذا تمت معالجة هذا اليوم مسبقاً"""
    try:
        response = requests.get(GIST_API_URL, headers=HEADERS)
        if response.status_code != 200:
            return False
        
        gist_data = response.json()
        files = gist_data.get('files', {})
        
        if SHIFTS_GIST_FILENAME not in files:
            return False
        
        content = files[SHIFTS_GIST_FILENAME]['content']
        all_shifts = json.loads(content)
        
        return date in all_shifts
        
    except Exception as e:
        log.error(f"خطأ في التحقق من المعالجة السابقة: {e}")
        return False

# ================= دوال الجلب مع إعادة المحاولة =================

@retry_with_backoff(max_retries=MAX_SHIFT_RETRIES, base_delay=SHIFT_RETRY_DELAY)
def get_shift_details_with_retry(scraper, details_url, shift_info):
    """جلب تفاصيل الشيفت مع إعادة المحاولة"""
    log.info(f"جلب تفاصيل الشيفت: {shift_info}")
    
    details_resp = safe_get_with_retry(
        scraper, 
        details_url, 
        headers={'HX-Request': 'true'}
    )
    
    if details_resp.status_code != 200:
        raise Exception(f"فشل جلب الشيفت: {details_resp.status_code}")
    
    return json.loads(details_resp.text)

@retry_with_backoff(max_retries=MAX_MEMBER_RETRIES, base_delay=MEMBER_RETRY_DELAY)
def get_member_info_with_retry(scraper, member_url, member_name):
    """جلب معلومات العضو مع إعادة المحاولة"""
    log.info(f"جلب معلومات العضو: {member_name}")
    
    mem_resp = safe_get_with_retry(
        scraper,
        member_url,
        headers={'HX-Request': 'true'}
    )
    
    if mem_resp.status_code != 200:
        raise Exception(f"فشل جلب معلومات العضو: {mem_resp.status_code}")
    
    return json.loads(mem_resp.text)

def process_shift_with_retry(scraper, shift, retry_stats):
    """معالجة شيفت مع إعادة محاولة شاملة"""
    shift_type = shift.get('shift_type_name', 'Unknown')
    normalized_type = normalize_shift_type(shift_type)
    details_url = urljoin('https://wardyati.com/', shift['get_shift_instance_details_url'])
    
    shift_key = f"{normalized_type}_{shift.get('id', 'unknown')}"
    
    for attempt in range(1, MAX_SHIFT_RETRIES + 1):
        try:
            details = get_shift_details_with_retry(scraper, details_url, f"{normalized_type} (محاولة {attempt})")
            retry_stats['successful_shifts'].add(shift_key)
            
            members_data = []
            failed_members = []
            
            # معالجة كل عضو مع إعادة محاولة
            for h in details.get('holdings', []):
                name = h.get('apparent_name', 'غير معروف')
                if not name or name == 'غير معروف':
                    members_data.append({'name': 'غير معروف', 'phone': ''})
                    continue
                
                phone = ''
                member_url = h.get('urls', {}).get('get_member_info')
                
                if member_url:
                    for member_attempt in range(1, MAX_MEMBER_RETRIES + 1):
                        try:
                            mdata = get_member_info_with_retry(
                                scraper, 
                                urljoin('https://wardyati.com/', member_url),
                                f"{name} (محاولة {member_attempt})"
                            )
                            phone = mdata.get('room_member', {}).get('contact_info', '')
                            retry_stats['successful_members'].add(name)
                            break
                        except Exception as e:
                            log.warning(f"فشل محاولة {member_attempt} للعضو {name}: {e}")
                            if member_attempt == MAX_MEMBER_RETRIES:
                                failed_members.append(name)
                                retry_stats['failed_members'].add(name)
                else:
                    retry_stats['members_without_url'].add(name)
                
                members_data.append({'name': name, 'phone': phone})
            
            # تسجيل الإحصائيات
            if failed_members:
                retry_stats['shifts_with_failed_members'].add(shift_key)
                log.warning(f"شيفت {normalized_type}: فشل {len(failed_members)} عضو: {', '.join(failed_members)}")
            
            return normalized_type, members_data
            
        except Exception as e:
            log.error(f"فشل محاولة {attempt} للشيفت {normalized_type}: {e}")
            if attempt == MAX_SHIFT_RETRIES:
                retry_stats['failed_shifts'].add(shift_key)
                log.error(f"فشل نهائي في جلب شيفت {normalized_type}")
                return None, None
    
    return None, None

def fetch_with_curl_cffi():
    """محاولة الجلب باستخدام curl_cffi"""
    log.info("=== محاولة باستخدام curl_cffi ===")
    
    session = create_curl_session()
    random_delay(3, 6)
    
    log.info("GET → https://wardyati.com/login/")
    resp = session.get('https://wardyati.com/login/', timeout=30)
    log.info(f"← {resp.status_code} من https://wardyati.com/login/")
    
    if resp.status_code != 200:
        log.error(f"فشل الطلب: {resp.status_code}")
        return None
    
    return session, resp

def process_with_curl_session(session, login_page_resp, retry_stats):
    """معالجة تسجيل الدخول وجلب البيانات باستخدام curl_cffi"""
    try:
        soup = BeautifulSoup(login_page_resp.text, 'html.parser')
        
        # البحث عن CSRF token
        csrf = soup.find('input', {'name': 'csrfmiddlewaretoken'})
        csrf_token = csrf['value'] if csrf and csrf.get('value') else ''
        
        if not csrf_token:
            cookies = session.cookies.get_dict() if hasattr(session.cookies, 'get_dict') else dict(session.cookies)
            if 'csrftoken' in cookies:
                csrf_token = cookies['csrftoken']
                log.info(f"تم العثور على csrf token من الـ cookies")
        
        if not csrf_token:
            log.error("فشل إيجاد CSRF token")
            return False, None, retry_stats
        
        log.info(f"CSRF Token: {csrf_token[:20]}...")
        
        # تسجيل الدخول
        random_delay(2, 4)
        
        login_data = {
            'username': 'mm2872564@gmail.com',
            'password': 'Mm@12345',
            'csrfmiddlewaretoken': csrf_token,
        }
        
        log.info("POST → https://wardyati.com/login/")
        login_resp = session.post(
            'https://wardyati.com/login/',
            data=login_data,
            headers={'Referer': 'https://wardyati.com/login/'},
            allow_redirects=True,
            timeout=30
        )
        log.info(f"← {login_resp.status_code} بعد POST")
        
        if login_resp.status_code not in (200, 302) or 'ممنوع' in login_resp.text or '403' in login_resp.text:
            log.error("فشل تسجيل الدخول")
            return False, None, retry_stats
        
        log.info("تم تسجيل الدخول بنجاح")
        
        # جلب صفحة الغرف
        random_delay(1, 3)
        log.info("GET → https://wardyati.com/rooms/")
        home = session.get('https://wardyati.com/rooms/', timeout=30)
        log.info(f"← {home.status_code} من https://wardyati.com/rooms/")
        
        if home.status_code != 200:
            return False, None, retry_stats
        
        soup = BeautifulSoup(home.text, 'html.parser')
        target_text = 'COLORECTAL DEC'
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
            log.error("لم يتم العثور على الغرفة")
            return False, None, retry_stats
        
        tomorrow = get_egypt_time() + timedelta(days=1)
        target_date = tomorrow.strftime('%Y-%m-%d')
        target_year = tomorrow.year
        target_month = tomorrow.month
        
        arena_url = urljoin(room_link, 'arena/')
        random_delay(1, 2)
        log.info(f"GET → {arena_url}")
        arena_resp = session.get(arena_url, params={
            'view': 'monthly',
            'year': target_year,
            'month': target_month
        }, timeout=30)
        log.info(f"← {arena_resp.status_code} من {arena_url}")
        
        if arena_resp.status_code != 200:
            return False, None, retry_stats
        
        try:
            data = json.loads(arena_resp.text)
            log.info(f"تم جلب بيانات الشهر - عدد الأيام: {len(data.get('shift_instances_by_date', {}))}")
        except Exception as e:
            log.error(f"فشل تحليل JSON: {e}")
            return False, None, retry_stats
        
        if target_date not in data.get('shift_instances_by_date', {}):
            day_name = tomorrow.strftime('%A')
            formatted = tomorrow.strftime('%d/%m')
            log.info(f"لا توجد ورديات يوم الغد: {day_name} {formatted}")
            return True, {"date": target_date, "shifts": {}}, retry_stats
        
        shifts_by_type = defaultdict(list)
        total_shifts = len(data['shift_instances_by_date'][target_date])
        log.info(f"عدد الشيفتات المطلوبة: {total_shifts}")
        
        # معالجة كل شيفت مع إعادة المحاولة
        for idx, shift in enumerate(data['shift_instances_by_date'][target_date], 1):
            log.info(f"معالجة الشيفت {idx}/{total_shifts}")
            
            shift_type, members_data = process_shift_with_retry(session, shift, retry_stats)
            
            if shift_type and members_data:
                for member_data in members_data:
                    shifts_by_type[shift_type].append(member_data)
        
        # طباعة النتيجة
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
        
        log.info("=" * 50)
        
        # طباعة إحصائيات إعادة المحاولة
        log.info("\n" + "="*50)
        log.info("إحصائيات إعادة المحاولة:")
        log.info(f"الشيفتات الناجحة: {len(retry_stats['successful_shifts'])}/{total_shifts}")
        log.info(f"الشيفتات الفاشلة: {len(retry_stats['failed_shifts'])}")
        log.info(f"الأعضاء الناجحين: {len(retry_stats['successful_members'])}")
        log.info(f"الأعضاء الفاشلين: {len(retry_stats['failed_members'])}")
        log.info(f"الشيفتات بأعضاء فاشلين: {len(retry_stats['shifts_with_failed_members'])}")
        log.info(f"الأعضاء بدون رابط معلومات: {len(retry_stats['members_without_url'])}")
        log.info("="*50)
        
        return True, {"date": target_date, "shifts": dict(shifts_by_type)}, retry_stats
        
    except Exception as e:
        log.error(f"خطأ في process_with_curl_session: {e}")
        log.error(traceback.format_exc())
        return False, None, retry_stats

def fetch_and_print_shifts_with_retry():
    """الجلب الرئيسي مع نظام إعادة المحاولة المتكامل"""
    log.info("=== بدء جلب ورديات الغد مع إعادة المحاولة ===")
    
    # إحصائيات إعادة المحاولة
    retry_stats = {
        'successful_shifts': set(),
        'failed_shifts': set(),
        'successful_members': set(),
        'failed_members': set(),
        'shifts_with_failed_members': set(),
        'members_without_url': set(),
        'start_time': datetime.now().isoformat()
    }
    
    # محاولة curl_cffi أولاً
    result = None
    try:
        result = fetch_with_curl_cffi()
    except Exception as e:
        log.warning(f"فشل curl_cffi: {e}")
    
    if result:
        scraper, login_page_resp = result
        log.info("نجح curl_cffi!")
        
        # متابعة باستخدام curl_cffi
        return process_with_curl_session(scraper, login_page_resp, retry_stats)
    
    # محاولة cloudscraper كبديل
    log.info("=== محاولة باستخدام cloudscraper كبديل ===")
    try:
        scraper = create_enhanced_scraper()
        log.info(f"تم إنشاء scraper جديد مع User-Agent محسّن")

        random_delay(2, 5)

        login_page = safe_get_with_retry(scraper, 'https://wardyati.com/login/', referer='https://wardyati.com/')
        if not login_page:
            return False, None, retry_stats

        soup = BeautifulSoup(login_page.text, 'html.parser')
        
        csrf = soup.find('input', {'name': 'csrfmiddlewaretoken'})
        if not csrf:
            csrf = soup.find('input', {'type': 'hidden'})
        
        csrf_token = csrf['value'] if csrf and csrf.get('value') else ''
        
        if not csrf_token:
            cookies = scraper.cookies.get_dict()
            if 'csrftoken' in cookies:
                csrf_token = cookies['csrftoken']
                log.info(f"تم العثور على csrf token من الـ cookies")
        
        if not csrf_token:
            log.error("فشل إيجاد CSRF token نهائياً")
            return False, None, retry_stats

        login_data = {
            'username': 'mm2872564@gmail.com',
            'password': 'Mm@12345',
            'csrfmiddlewaretoken': csrf_token,
        }

        login_resp = safe_post_with_retry(scraper, 'https://wardyati.com/login/', 
                                          data=login_data,
                                          headers={'Referer': 'https://wardyati.com/login/'}, 
                                          allow_redirects=True)
        if not login_resp or 'ممنوع' in login_resp.text or '403' in login_resp.text:
            log.error("فشل تسجيل الدخول")
            return False, None, retry_stats

        log.info("تم تسجيل الدخول بنجاح")

        home = safe_get_with_retry(scraper, 'https://wardyati.com/rooms/')
        if not home:
            return False, None, retry_stats

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
            log.error("لم يتم العثور على الغرفة")
            return False, None, retry_stats

        tomorrow = get_egypt_time() + timedelta(days=1)
        target_date = tomorrow.strftime('%Y-%m-%d')
        target_year = tomorrow.year
        target_month = tomorrow.month

        arena_url = urljoin(room_link, 'arena/')
        arena_resp = safe_get_with_retry(scraper, arena_url, params={
            'view': 'monthly',
            'year': target_year,
            'month': target_month
        })
        if not arena_resp:
            return False, None, retry_stats

        try:
            data = json.loads(arena_resp.text)
            log.info(f"تم جلب بيانات الشهر بنجاح - عدد الأيام: {len(data.get('shift_instances_by_date', {}))}")
        except Exception as e:
            log.error(f"فشل تحليل JSON من arena: {e}")
            return False, None, retry_stats

        if target_date not in data.get('shift_instances_by_date', {}):
            day_name = tomorrow.strftime('%A')
            formatted = tomorrow.strftime('%d/%m')
            log.info(f"لا توجد ورديات يوم الغد: {day_name} {formatted}")
            return True, {"date": target_date, "shifts": {}}, retry_stats

        shifts_by_type = defaultdict(list)
        total_shifts = len(data['shift_instances_by_date'][target_date])
        log.info(f"عدد الشيفتات المطلوبة: {total_shifts}")
        
        # معالجة كل شيفت مع إعادة المحاولة
        for idx, shift in enumerate(data['shift_instances_by_date'][target_date], 1):
            log.info(f"معالجة الشيفت {idx}/{total_shifts}")
            
            shift_type, members_data = process_shift_with_retry(scraper, shift, retry_stats)
            
            if shift_type and members_data:
                for member_data in members_data:
                    shifts_by_type[shift_type].append(member_data)

        # طباعة النتيجة النهائية
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

        log.info("=" * 50)
        
        # طباعة إحصائيات إعادة المحاولة
        log.info("\n" + "="*50)
        log.info("إحصائيات إعادة المحاولة:")
        log.info(f"الشيفتات الناجحة: {len(retry_stats['successful_shifts'])}/{total_shifts}")
        log.info(f"الشيفتات الفاشلة: {len(retry_stats['failed_shifts'])}")
        log.info(f"الأعضاء الناجحين: {len(retry_stats['successful_members'])}")
        log.info(f"الأعضاء الفاشلين: {len(retry_stats['failed_members'])}")
        log.info(f"الشيفتات بأعضاء فاشلين: {len(retry_stats['shifts_with_failed_members'])}")
        log.info(f"الأعضاء بدون رابط معلومات: {len(retry_stats['members_without_url'])}")
        log.info("="*50)
        
        return True, {"date": target_date, "shifts": dict(shifts_by_type)}, retry_stats

    except Exception as e:
        log.error("خطأ غير متوقع في fetch_and_print_shifts:")
        log.error(traceback.format_exc())
        return False, None, retry_stats

# ================= الحلقة الرئيسية مع إعادة المحاولة =================
def main():
    log.info("البوت شغال الآن مع نظام إعادة المحاولة المتقدم")
    log.info("-" * 70)

    # تحميل الحالة السابقة من Gist
    last_execution_date, last_success_date, total_retries = load_state_from_gist()
    
    if last_execution_date:
        log.info(f"آخر تنفيذ: {last_execution_date}")
        log.info(f"آخر نجاح: {last_success_date}")
        log.info(f"إجمالي محاولات إعادة: {total_retries}")

    while True:
        try:
            now = get_egypt_time()
            current_date = now.strftime('%Y-%m-%d')
            current_hour = now.hour
            current_minute = now.minute
            
            # تاريخ الغد
            tomorrow_date = (now + timedelta(days=1)).strftime('%Y-%m-%d')

            # التحقق مما إذا تمت معالجة اليوم بالفعل
            if check_if_already_processed(tomorrow_date):
                log.info(f"[{now.strftime('%H:%M:%S')}] ورديات يوم {tomorrow_date} تمت معالجتها مسبقاً - تخطي")
                time.sleep(90)
                continue

            if current_hour == 22 and current_minute < 60 and last_execution_date != current_date:
                log.info(f"[{now.strftime('%H:%M:%S')}] جاري جلب ورديات الغد ({tomorrow_date})...")
                
                success, shifts_data, retry_stats = fetch_and_print_shifts_with_retry()
                
                if success:
                    # تحويل sets إلى lists للتخزين في JSON
                    retry_stats_serializable = {
                        'successful_shifts': list(retry_stats.get('successful_shifts', [])),
                        'failed_shifts': list(retry_stats.get('failed_shifts', [])),
                        'successful_members': list(retry_stats.get('successful_members', [])),
                        'failed_members': list(retry_stats.get('failed_members', [])),
                        'shifts_with_failed_members': list(retry_stats.get('shifts_with_failed_members', [])),
                        'members_without_url': list(retry_stats.get('members_without_url', [])),
                        'start_time': retry_stats.get('start_time'),
                        'end_time': datetime.now().isoformat(),
                        'total_retries': total_retries + 1
                    }
                    
                    # حفظ بيانات الورديات في Gist مع إحصائيات المحاولات
                    if shifts_data:
                        save_shifts_to_gist(shifts_data['shifts'], tomorrow_date, retry_stats_serializable)
                    
                    # حفظ سجل المحاولات
                    save_retry_log_to_gist(retry_stats_serializable)
                    
                    # تحديث حالة البوت في Gist
                    next_execution_time = (now + timedelta(days=1)).replace(hour=20, minute=0, second=0).isoformat()
                    save_state_to_gist(current_date, current_date, next_execution_time, total_retries + 1)
                    
                    last_execution_date = current_date
                    last_success_date = current_date
                    total_retries += 1
                    
                    log.info("✅ تم إكمال العملية بنجاح مع إعادة المحاولات")
                else:
                    log.error(f"❌ فشل جلب ورديات يوم {tomorrow_date}")
                    
                    # حفظ حالة الفشل في Gist مع زيادة عداد المحاولات
                    next_execution_time = (now + timedelta(minutes=5)).isoformat()
                    save_state_to_gist(current_date, last_success_date, next_execution_time, total_retries + 1)
                    
                    total_retries += 1
                
                log.info("-" * 60)

            time.sleep(400)

        except Exception as e:
            log.error("خطأ في الحلقة الرئيسية:")
            log.error(traceback.format_exc())
            time.sleep(10)

if __name__ == "__main__":
    server()  # لو عندك web server شغال
    
    while True:
        try:
            main()
        except Exception as e:
            log.error(f"خطأ غير متوقع – البوت وقع: {e}")
            log.error(traceback.format_exc())
            log.info("إعادة تشغيل تلقائي بعد 15 ثانية...")
            time.sleep(15)
        
