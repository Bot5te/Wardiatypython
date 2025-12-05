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
from app import server 
import os

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

def create_scraper():
    """إنشاء scraper مع إعدادات مختلفة للبيئات المختلفة"""
    try:
        # تحقق إذا كنا على Render
        is_render = os.environ.get('RENDER', False) or 'render.com' in os.environ.get('RENDER_EXTERNAL_HOSTNAME', '')
        
        if is_render:
            log.info("تشغيل على Render - استخدام إعدادات خاصة")
            
            # إعدادات cloudscraper مختلفة لـ Render
            scraper = cloudscraper.create_scraper(
                browser={
                    'browser': 'chrome',
                    'platform': 'windows',
                    'desktop': True,
                },
                delay=10,
                interpreter='js2py',  # استخدم js2py بدلاً من nodejs على Render
                debug=False
            )
            
            # تحديث headers للمظهر أكثر واقعية
            scraper.headers.update({
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'ar,en-US;q=0.7,en;q=0.3',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'same-origin',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0',
            })
            
            # تعيين User-Agent عشوائي
            user_agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            ]
            scraper.headers['User-Agent'] = random.choice(user_agents)
            
        else:
            # إعدادات للتشغيل المحلي
            log.info("التشغيل محلياً")
            scraper = cloudscraper.create_scraper()
        
        return scraper
        
    except Exception as e:
        log.error(f"خطأ في إنشاء الـ scraper: {e}")
        # استخدام الـ scraper الأساسي كحل احتياطي
        return cloudscraper.create_scraper()

@retry
def safe_get(scraper, url, **kwargs):
    log.info(f"GET → {url} | params={kwargs.get('params')}")
    
    # إضافة headers إضافية إذا لزم الأمر
    headers = kwargs.pop('headers', {})
    if 'HX-Request' not in headers:
        headers.update({
            'Referer': 'https://wardyati.com/',
            'Origin': 'https://wardyati.com'
        })
    
    resp = scraper.get(url, timeout=30, headers=headers, **kwargs)
    log.info(f"← {resp.status_code} من {url}")
    
    if resp.status_code == 403:
        log.warning("حصلنا على 403 - قد نحتاج لتغيير استراتيجية")
        # إعادة تعيين الـ scraper
        global current_scraper
        current_scraper = create_scraper()
        raise Exception(f"تم حظر الطلب (403). سيتم إعادة المحاولة بمعرّف جديد.")
    
    resp.raise_for_status()
    return resp

@retry
def safe_post(scraper, url, **kwargs):
    log.info(f"POST → {url}")
    
    headers = kwargs.pop('headers', {})
    headers.update({
        'Content-Type': 'application/x-www-form-urlencoded',
        'Referer': url,
        'Origin': 'https://wardyati.com'
    })
    
    resp = scraper.post(url, timeout=30, headers=headers, **kwargs)
    
    if resp.status_code in (403, 429):
        log.error(f"تم حظر الطلب: {resp.status_code}")
        # إعادة تعيين الـ scraper
        global current_scraper
        current_scraper = create_scraper()
        raise Exception(f"تم حظر الطلب ({resp.status_code}). سيتم إعادة المحاولة.")
    
    if resp.status_code not in (200, 302):
        raise Exception(f"فشل POST: {resp.status_code} | {resp.text[:500]}")
    
    log.info(f"← {resp.status_code} بعد POST")
    return resp

def fetch_and_print_shifts():
    log.info("=== بدء جلب ورديات الغد ===")
    
    # إعادة إنشاء الـ scraper لكل عملية
    scraper = create_scraper()
    
    try:
        # 1. زيارة الصفحة الرئيسية أولاً للحصول على الكوكيز
        log.info("زيارة الصفحة الرئيسية أولاً...")
        home_page = safe_get(scraper, 'https://wardyati.com/')
        if not home_page:
            log.error("فشل في زيارة الصفحة الرئيسية")
            return False
        
        # 2. الانتظار قليلاً قبل تسجيل الدخول
        time.sleep(random.uniform(2, 5))
        
        # 3. تسجيل الدخول
        login_page = safe_get(scraper, 'https://wardyati.com/login/')
        if not login_page:
            return False

        soup = BeautifulSoup(login_page.text, 'html.parser')
        csrf = soup.find('input', {'name': 'csrfmiddlewaretoken'})
        csrf_token = csrf['value'] if csrf else ''
        
        if not csrf_token:
            # محاولة البحث عن التوكن بطريقة أخرى
            for script in soup.find_all('script'):
                if 'csrf' in script.text:
                    import re
                    matches = re.search(r'csrf_token["\']?\s*:\s*["\']([^"\']+)["\']', script.text)
                    if matches:
                        csrf_token = matches.group(1)
                        break
            
            if not csrf_token:
                log.error("لم يتم العثور على csrf token")
                log.error(f"محتوى الصفحة: {login_page.text[:2000]}")
                return False

        login_data = {
            'username': 'mm2872564@gmail.com',
            'password': 'Mm@12345',
            'csrfmiddlewaretoken': csrf_token,
        }

        # إضافة تأخير عشوائي قبل تسجيل الدخول
        time.sleep(random.uniform(1, 3))
        
        login_resp = safe_post(scraper, 'https://wardyati.com/login/', data=login_data, allow_redirects=True)
        
        if not login_resp:
            log.error("فشل تسجيل الدخول - لا يوجد رد")
            return False
        
        # التحقق من نجاح تسجيل الدخول
        if 'logout' in login_resp.text.lower() or 'profile' in login_resp.text.lower():
            log.info("تم تسجيل الدخول بنجاح ✓")
        else:
            log.warning("قد يكون هناك مشكلة في تسجيل الدخول")
            log.debug(f"جزء من الرد: {login_resp.text[:1000]}")
        
        # الانتظار قبل الانتقال للصفحة التالية
        time.sleep(random.uniform(2, 4))

        # 4. البحث عن الغرفة
        home = safe_get(scraper, 'https://wardyati.com/rooms/')
        if not home:
            return False

        soup = BeautifulSoup(home.text, 'html.parser')
        target_text = 'شيفتات جراحة غدد شهر 12'
        room_link = None
        
        # البحث بطرق مختلفة
        for div in soup.find_all('div', class_='overflow-wrap'):
            if target_text in div.text.strip():
                card = div.find_parent('div', class_='card-body')
                if card:
                    a = card.find('a', class_='stretched-link')
                    if a:
                        room_link = urljoin('https://wardyati.com/', a.get('href'))
                        log.info(f"تم العثور على الغرفة: {room_link}")
                        break
        
        # محاولة بديلة إذا لم يتم العثور
        if not room_link:
            log.warning("محاولة البحث عن طريق الروابط مباشرة...")
            for a in soup.find_all('a', href=True):
                if 'rooms' in a['href'] and target_text in a.text:
                    room_link = urljoin('https://wardyati.com/', a['href'])
                    log.info(f"تم العثور على الغرفة (الطريقة البديلة): {room_link}")
                    break

        if not room_link:
            log.error(f"لم يتم العثور على الغرفة - تأكد من النص '{target_text}'")
            log.error(f"الأقسام الموجودة: {[div.text[:50] for div in soup.find_all('div', class_='overflow-wrap')[:3]]}")
            return False

        # 5. جلب بيانات الورديات
        tomorrow = get_egypt_time() + timedelta(days=1)
        target_date = tomorrow.strftime('%Y-%m-%d')
        target_year = tomorrow.year
        target_month = tomorrow.month

        arena_url = urljoin(room_link, 'arena/')
        
        # إضافة headers خاصة لطلبات AJAX
        headers = {
            'HX-Request': 'true',
            'HX-Current-URL': room_link,
            'X-Requested-With': 'XMLHttpRequest'
        }
        
        arena_resp = safe_get(scraper, arena_url, params={
            'view': 'monthly',
            'year': target_year,
            'month': target_month
        }, headers=headers)
        
        if not arena_resp:
            return False

        try:
            data = json.loads(arena_resp.text)
            log.info(f"تم جلب بيانات الشهر بنجاح - عدد الأيام: {len(data.get('shift_instances_by_date', {}))}")
        except Exception as e:
            log.error(f"فشل تحليل JSON من arena: {e}")
            log.error(f"الرد الخام: {arena_resp.text[:1000]}")
            return False

        if target_date not in data.get('shift_instances_by_date', {}):
            day_name = tomorrow.strftime('%A')
            formatted = tomorrow.strftime('%d/%m')
            log.info(f"لا توجد ورديات يوم الغد: {day_name} {formatted}")
            return True

        # 6. جلب تفاصيل كل وردية
        shifts_by_type = {}
        shifts_count = len(data['shift_instances_by_date'][target_date])
        log.info(f"جاري جلب تفاصيل {shifts_count} وردية...")
        
        for i, shift in enumerate(data['shift_instances_by_date'][target_date], 1):
            shift_type = shift.get('shift_type_name', 'Unknown')
            details_url = urljoin('https://wardyati.com/', shift['get_shift_instance_details_url'])
            
            log.info(f"جلب وردية {i}/{shifts_count}: {shift_type}")
            
            # تأخير عشوائي بين الطلبات
            if i < shifts_count:
                time.sleep(random.uniform(1, 2))
            
            details_resp = safe_get(scraper, details_url, headers={
                'HX-Request': 'true',
                'HX-Current-URL': arena_url,
                'X-Requested-With': 'XMLHttpRequest'
            })
            
            if not details_resp:
                continue

            try:
                details = json.loads(details_resp.text)
                for h in details.get('holdings', []):
                    name = h.get('apparent_name', 'غير معروف')
                    phone = ''
                    
                    # جلب معلومات العضو إذا كان هناك رابط
                    member_url = h.get('urls', {}).get('get_member_info')
                    if member_url:
                        # تأخير صغير قبل طلب معلومات العضو
                        time.sleep(random.uniform(0.5, 1))
                        
                        mem_resp = safe_get(scraper, urljoin('https://wardyati.com/', member_url),
                                          headers={
                                              'HX-Request': 'true',
                                              'X-Requested-With': 'XMLHttpRequest'
                                          })
                        if mem_resp:
                            try:
                                mdata = json.loads(mem_resp.text)
                                phone = mdata.get('room_member', {}).get('contact_info', '')
                            except:
                                log.warning(f"فشل تحويل JSON لمعلومات العضو: {name}")
                    
                    shifts_by_type.setdefault(shift_type, []).append({'name': name, 'phone': phone})
                    
            except Exception as e:
                log.error(f"خطأ أثناء معالجة تفاصيل الشيفت {i}: {e}")
                continue

        # 7. طباعة النتيجة النهائية
        day_name = tomorrow.strftime('%A')
        formatted = tomorrow.strftime('%d/%m')
        log.info(f"\n" + "="*60)
        log.info(f"ورديات الغد: {day_name} {formatted}")
        log.info("="*60)

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
                        if p['phone']:
                            log.info(f'  • {p["name"]} ({p["phone"]})')
                        else:
                            log.info(f'  • {p["name"]}')
                printed.add(st)

        log.info("="*60)
        log.info(f"تم جلب {sum(len(v) for v in shifts_by_type.values())} اسم بنجاح ✓")
        
        return True

    except Exception as e:
        log.error("خطأ غير متوقع في fetch_and_print_shifts:")
        log.error(traceback.format_exc())
        return False

# ================= الحلقة الرئيسية =================
def main():
    log.info("="*70)
    log.info("بوت ورديات الغد شغال الآن - يطبع ورديات الغد يوميًا الساعة 2:30 مساءً")
    log.info("="*70)

    last_printed_date = None

    while True:
        try:
            now = get_egypt_time()
            current_date = now.strftime('%Y-%m-%d')
            current_hour = now.hour
            current_minute = now.minute
            
            # تسجيل الوقت الحالي
            if now.minute % 30 == 0:  # كل 30 دقيقة
                log.info(f"[{now.strftime('%H:%M:%S')}] البوت شغال...")

            # تشغيل الساعة 2:30 مساءً
            if (current_hour == 14 and current_minute >= 30) or \
               (current_hour == 15 and current_minute < 5):
                if last_printed_date != current_date:
                    log.info(f"[{now.strftime('%H:%M:%S')}] ⏰ وقت جلب ورديات الغد...")
                    success = fetch_and_print_shifts()
                    if success:
                        last_printed_date = current_date
                        log.info("تمت العملية بنجاح ✓")
                    else:
                        log.error("فشلت العملية، سيتم إعادة المحاولة غداً ✗")
                    
                    log.info("-" * 60)
                    
                    # الانتظار حتى تمر الساعة 3:05 قبل التحقق مجدداً
                    time.sleep(60 * 35)
            
            # فحص كل دقيقة
            time.sleep(60)

        except KeyboardInterrupt:
            log.info("\nتم إيقاف البوت يدويًا")
            break
        except Exception as e:
            log.error("خطأ في الحلقة الرئيسية:")
            log.error(traceback.format_exc())
            time.sleep(60)  # انتظار دقيقة قبل إعادة المحاولة

if __name__ == "__main__":
    # تشغيل خادم ويب إذا كان موجوداً
    try:
        server()
    except:
        log.info("لا يوجد خادم ويب، التشغيل في وضع CLI فقط")
    
    try:
        main()
    except Exception as e:
        log.error(f"خطأ فادح: {e}")
        log.error(traceback.format_exc())
