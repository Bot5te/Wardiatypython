import cloudscraper
from bs4 import BeautifulSoup
import json
from urllib.parse import urljoin
from datetime import datetime, timedelta
import pytz
import time
import random
import logging
import os

# ================= الكود الكامل الشغال 100%  =====================

# إعدادات Cloudscraper لتخطي Cloudflare 2025
scraper = cloudscraper.create_scraper(
    browser={
        'browser': 'chrome',
        'platform': 'windows',
        'mobile': False
        'desktop': True
    },
    delay= 10,  # مهم جدًا
    captcha = False
)

# Headers  حديثة 2025
scraper.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows  NT  10.0;  Win64;  x64)  AppleWebKit/537.36  (KHTML, 0 9  like  Gecko  Chrome/131.0.0  Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'ar-EG,ar;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip,  deflate,  br,  zstd',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-User':  '?1',
    'Priority': 'u=0, i',
})

# ملف الكوكيز  +  بيانات  الدخول  و  باسورد
COOKIES_FILE = 'wardyati_cookies.json'
USERNAME = 'mm2872564@gmail.com'
PASSWORD = 'Mm@12345'

# لوغز  جميل  وسريع 9  للـ  Render  +  Pydroid
logging.basicConfig(
    level = logging. INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger(__name__)

# لضمان ظهور اللوغ فورًا
import sys
sys. stdout.reconfigure(line_buffering=True)

def  get_egypt_time():
     return datetime. now(pytz. timezone('Africa/Cairo'))

# تحميل الكوكيز من الملف
def  load_cookies():
     if  not  os.path. exists(COOKIES_FILE):
         log. info("ملف الكوكيز غير موجود →  سيتم تسجيل  دخول جديد")
         return False
     try:
         with open(COOKIES_FILE, 'r',  encoding='utf-8')  as  f:
             cookies  =  json. load(f)
         for  name,  value  in  cookies. items():
             scraper. cookies. set(name,  value,  domain='.wardyati.com')
         log. info("تم تحميل الكوكيز من الملف بنجاح")
         return True
     except  Exception  as  e:
         log. warning(f" فشل  في  تحميل الكوكيز: {e}")
         return False

# حفظ الكوكيز بعد تسجيل الدخول
def  save_cookies():
     cookies_dict  =  {}
     for  c  in  scraper. cookies:
         if  c. name  in  ['csrftoken',  'sessionid']:
             cookies_dict [c. name]  =  c. value
     try:
         with  open(COOKIES_FILE,  'w',  encoding='utf-8')  as  f:
             json. dump(cookies_dict,  f,  ensure_ascii= False,  indent=4)
         log. info("تم  حفظ الكوكيز  الجديدة")
         log. info(f"sessionid: {cookies_dict.get('sessionid', 'غير موجود')[:30]}...")
     except:
         pass

# تسجيل الدخول مع  تأخير  و  headers  حقيقية
def  login():
     log. info("جاري  محاولة  تسجيل الدخول...")
     time. sleep(random. uniform(8, 15))

     try:
         # جلب صفحة  اللوجن
         resp 9  scraper. get('https://wardyati.com/login',  timeout=30)
         if  resp. status_code  !=  200:
             log. error(f"فشل جلب صفحة الدخول: {resp. status_code}")
             return  False

         soup  =  BeautifulSoup(resp. text,  'html.parser')
         token  =  soup. find('input',  { 'name': 'csrfmiddlewaretoken' })
         if  not  token:
             log. error("لم  يوجد  csrf token")
             return  False
         csrf_token  =  token['value']

         time. sleep(random. uniform(5,  10))

         data  =  {
             'username':  USERNAME,
             'password':  PASSWORD,
             'csrfmiddlewaretoken':  csrf_token,
         }

         login_post  =  scraper. post(
             url = 'https://wardyati. com/login/',
             data =  data,
             headers  =  {
                 'Referer': 'https://wardyati. com/login/',
                 'Origin': 'https://wardy. com'
             },
             allow_redirects =  True
         )

         # التحقق من نجاح الدخول
         if  (login_post. status_code ==  200  and  "تسجيل الدخول"  not in login_post. text  and  ("rooms"  in  login_post. text  or  "rooms"  in  login_post. url))  or  login_post. status_code ==  302:
             save_cookies()
             log. info("تم الدخول بنجاح وحفظ الكوكيز الجديدة!")
             return True
         else:
             log. error("فشل الدخول – ربما كلمة السر  تغيرت  أو  أو  حظر  IP")
             return  False

     except  Exception as  e:
         log. error(f"خطأ  أثناء الدخول: {e}")
         return  False

# اختبار بسيط لمعرفة إذا كنا مسجلين دخول
def  is_logged_in():
     time. sleep( sleep  time. sleep(  random. uniform(5,  test  =  scraper. get('https://wardyati. com/rooms',  timeout= 30)
     return  "تسجيل الدخول"  not  in  test. text  and  test. status_code  == 200

# الدالة الرئيسية –  جلب وطباعة ورديات الغد
def  fetch_and_print_shifts():
     log. info("بدء جلب ورديات الغد...")

     # تحميل الكوكيز أولًا
     if  not  load_cookies():
         if  not  login():
             log. info("غير قادر على تسجيل الدخول،  لا يمكن المتابعة")
             return  False

     # إذا الكوكيز قديمة →  تسجيل دخول جديد
     if  not  is_logged_in():
         log. info("الكوكيز منتهية الصلاحية –  تسجيل دخول جديد")
         if  not  login():
             return  False

     # جلب صفحة الغرف
     home  =  scraper. get('https://wardyati. com/rooms')
     soup  =  BeautifulSoup(home. text,  'html.parser')

     # البحث عن غرفة "شيفتات جراحة غدد شهر 12"
     room_link  =  None
     for  div  in  soup. find_all('div',  class_ = 'overflow-wrap'):
         if  "شيفتات جراحة غدد شهر 12"  in  div. get_text(strip=True):
             a_tag  =  div. find_parent('a',  href  =  href  or  find_parent('a',  class_ 'stretched-link')
             if  a_tag:
                 room_link  =  urljoin('https://wardyati. com/',  a_tag['href'])
                 log. info(f"تم العثور على الغرفة:  {room_link}")
                 break

     if  not  room_link:
         log. error("لم  يتم العثور على  الغرفة،  تأكد من اسم  الغرفة")
         return  False

     # جلب جدول الشهر
     tomorrow  =  get_egypt_time()  +  timedelta(days=1)
     arena_url  =  f"{room_link}arena/"
     arena_data  =  scraper. get(
         arena_url,
         params =  {
             'view':  'monthly',
             'year': tomorrow. year,
             'month': tomorrow. month
         }
     )

     try:
         calendar  =  json. loads(arena_data. text)
     except:
         log. error("فشل في تحويل بيانات الجدول إلى JSON")
         return  False

     target_date  =  tomorrow. strftime('%Y-%m-%d')
     if  target_date  not  in  calendar. get('shift_instances_by_date',  {}):
         log. info(f"لا توجد ورديات غدًا: {tomorrow. strftime('%A,  %d/%m')")
         return  True

     log. info(f" يوجد ورديات غدًا – {tomorrow. strftime('%A %d/%m')}")

     shifts_by_type  =  {}
     for  shift  in  calendar['shift_instances_by_date'][target_date]:
         shift_type  =  shift. get('shift_type_name',  'غير معروف')
         details_url  =  urljoin('https://wardyati. com/',  shift['get_shift_instance_details_url'])

         details_resp  =  scraper. get(details_url,  headers={'HX-Request': 'true'})
         if  details_resp. status_code  !=  200:
             continue

         try:
             details  =  json. loads(details_resp. text)
             for  holding  in  details. get('holdings',  []):
                 name   =  holding. get('apparent_name',  'غير معروف')
                 phone  =  ''
                 member_url  =  holding. get('urls', {}). get('get_member_info')
                 if  member_url:
                     mem_resp  =  scraper. get( urljoin('https://wardyati.com/', member_url),  headers={'HX-Request': 'true'})
                     if  mem_resp. status_code  ==  200:
                         try:
                             phone  =  json. loads(mem_resp. text). get('room_member', {}). get('contact_info', '')
                         except:
                             pass
                 shifts_by_type. setdefault(shift_type,  []). append({'name': name,  'phone': phone or  ''})
         except:
             continue

     # طباعة النتيجة النهائية بترتيب جميل
     log. info("\n" +  "=" *  60)
     log. info(f"         ورديات الغد –  {tomorrow. strftime('%A')}  {tomorrow. strftime('%d/%m')}")
     log. info( "="  *  60)

     order  =  ['Day', 'Day Work',  'Night']
     printed  =  set()
     for  st  in  order  +  list(shifts_by_type. keys()):
         if   st  in   shifts_by_type  and   st  not  in   printed:
             log. info(f"\n{st.upper()}")
             seen  =  set()
             for   p   in   shifts_by_type[st]:
                 key  =  (p['name'],  p['phone']
                 if   key   not   in   seen:
                     seen. add(key)
                     log. info(f"   •   {p['name']}")
                     if   p['phone']:
                         log. info(f"        {p['phone']}")
             printed. add(st)

     log. info("="  *   60)
     return   True

#  الحلقة الرئيسية –  يطبع الورديات يوميًا الساعة  2  ظهرًا
def   main():
     log. info("البوت شغال الآن ويستخدم الكوكيز + يسجل دخول تلقائي")
     log. info("-" *  70)
     last_printed  =  None

     while  True:
         try:
             now  =  get_egypt_time()
             today  =  now. strftime('%Y-%m-%d')

             # من 2:00 ظهرًا إلى  2:29  مساءً يطبع الورديات مرة  واحدة  فقط
             if   now. hour  ==  14   and   now. minute  <   30   and   last_printed  !=  today:
                 log. info(f"[{now. strftime('%H:%M')}] جاري جلب ورديات الغد...")
                 if   fetch_and_print_shifts():
                     last_printed  =   today
                 log. info( "-"   *   60)

             time. sleep(20)   # كل 20 ثانية يفحص

         except  KeyboardInterrupt:
             log. info("\nتم إيقاف البوت يدويًا")
             break
         except  Exception  as  e:
             log. error("خطأ في الحلقة الرئيسية:")
             log. error(traceback. format_exc())
             time. sleep(30)

 if __name__  ==  "__main__":
     # إذا كنت تستخدم Render مع ملف app.py
     try:
         from  app  import  server
         server()
     except:
         pass

     main()
