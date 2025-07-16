# MAU_Duyuru.py (Plan C: Selenium ile Geliştirilmiş)

import os
import sys
import json
import logging
import datetime
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService
from bs4 import BeautifulSoup
from dotenv import load_dotenv
# --- E-POSTA İÇİN GEREKLİ KÜTÜPHANELER ---
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
# ---

# --- Sabitler ve Konfigürasyon ---
URL = "https://www.maltepe.edu.tr/tr/duyuru-listesi"
JSON_FILE = "last_announcements.json"
LOG_FILE = "duyuru.log"
DEBUG_HTML_FILE = "debug_page.html"
ENV_FILE = ".env"
KEYWORD = "ALINACAKTIR"

# --- Ortam Değişkenlerini Yükle ---
load_dotenv(dotenv_path=ENV_FILE)

# --- Loglama Kurulumu ---
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] - %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    logging.info("="*50)
    logging.info("Duyuru kontrol scripti başlatıldı (Plan C: Selenium Geliştirilmiş).")

# --- GÜNCELLENMİŞ E-POSTA GÖNDERME FONKSİYONU (STARTTLS UYUMLU) ---
def send_email(subject, html_body):
    email_enabled = os.getenv("EMAIL_ENABLED", "false").lower() == "true"
    if not email_enabled:
        logging.info("E-posta gönderimi kapalı (EMAIL_ENABLED=false).")
        return

    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port_str = os.getenv("SMTP_PORT", "587") # Varsayılan olarak 587 kullan
    email_user = os.getenv("EMAIL_USER")
    email_password = os.getenv("EMAIL_PASSWORD")
    notification_email = os.getenv("NOTIFICATION_EMAIL")

    if not all([smtp_server, smtp_port_str, email_user, email_password, notification_email]):
        logging.error("E-posta ayarları eksik! Lütfen GitHub Secrets'ı kontrol edin.")
        return

    try:
        smtp_port = int(smtp_port_str)
        
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = email_user
        message["To"] = notification_email
        message.attach(MIMEText(html_body, "html"))

        context = ssl.create_default_context()
        logging.info(f"SMTP sunucusuna bağlanılıyor: {smtp_server}:{smtp_port}")

        # --- DEĞİŞEN BÖLÜM ---
        # SMTP_SSL yerine standart SMTP ile bağlanıp STARTTLS'e yükseltiyoruz
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls(context=context) # Güvenli bağlantıya geç
            server.login(email_user, email_password)
            server.sendmail(email_user, notification_email, message.as_string())
        # --- DEĞİŞİKLİK SONU ---
            
        logging.info(f"E-posta başarıyla {notification_email} adresine gönderildi.")

    except Exception as e:
        logging.error(f"E-posta gönderilirken kritik bir hata oluştu: {e}", exc_info=True)
        
# --- Dosya İşlemleri ---
def load_previous_announcements():
    if not os.path.exists(JSON_FILE):
        logging.warning(f"'{JSON_FILE}' bulunamadı. İlk çalıştırma olarak kabul ediliyor.")
        return []
    try:
        with open(JSON_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
            # Veri formatını kontrol et ve normalize et
            if isinstance(data, dict):
                titles = data.get('titles', [])
            elif isinstance(data, list):
                titles = data
            else:
                logging.warning(f"Beklenmeyen veri formatı: {type(data)}. Boş liste döndürülüyor.")
                return []
            
            # Tüm öğelerin string olduğundan emin ol
            clean_titles = []
            for title in titles:
                if isinstance(title, str):
                    clean_titles.append(title)
                elif isinstance(title, dict):
                    # Eğer dict ise, 'title' veya 'text' anahtarını ara
                    if 'title' in title:
                        clean_titles.append(str(title['title']))
                    elif 'text' in title:
                        clean_titles.append(str(title['text']))
                    else:
                        logging.warning(f"Dict formatında başlık işlenemedi: {title}")
                else:
                    clean_titles.append(str(title))
            
            logging.info(f"Önceki duyuru dosyasından {len(clean_titles)} adet başlık yüklendi.")
            return clean_titles
            
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logging.error(f"'{JSON_FILE}' okunurken hata oluştu: {e}. İlk çalıştırma olarak devam ediliyor.")
        return []

def save_announcements(titles):
    try:
        with open(JSON_FILE, 'w', encoding='utf-8') as f:
            payload = {
                'last_update': datetime.datetime.now().isoformat(),
                'count': len(titles),
                'titles': titles
            }
            json.dump(payload, f, ensure_ascii=False, indent=4)
        logging.info(f"{len(titles)} adet güncel duyuru '{JSON_FILE}' dosyasına başarıyla kaydedildi.")
    except Exception as e:
        logging.error(f"Duyurular '{JSON_FILE}' dosyasına kaydedilirken hata: {e}")
        notify_admin(f"Kritik Hata: Duyurular JSON dosyasına yazılamadı!", f"Detaylar: {e}")

# --- Hata Yönetimi ---
def save_debug_page(content):
    try:
        with open(DEBUG_HTML_FILE, 'w', encoding='utf-8') as f:
            f.write(content)
        logging.info(f"Hata ayıklama için sayfa kaynağı '{DEBUG_HTML_FILE}' olarak kaydedildi.")
    except Exception as e:
        logging.error(f"Debug dosyası kaydedilirken hata oluştu: {e}")

def notify_admin(subject, body):
    logging.critical(f"YÖNETİCİ BİLDİRİMİ GEREKİYOR: Başlık: {subject}")
    logging.critical(f"Detay: {body}")


# --- YENİ EKLENEN FONKSİYON ---
def send_email(subject, html_body):
    email_enabled = os.getenv("EMAIL_ENABLED", "false").lower() == "true"
    if not email_enabled:
        logging.info("E-posta gönderimi kapalı (EMAIL_ENABLED=false).")
        return

    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port_str = os.getenv("SMTP_PORT", "587")
    email_user = os.getenv("EMAIL_USER")
    email_password = os.getenv("EMAIL_PASSWORD")
    notification_email = os.getenv("NOTIFICATION_EMAIL")

    if not all([smtp_server, smtp_port_str, email_user, email_password, notification_email]):
        logging.error("E-posta ayarları eksik! Lütfen GitHub Secrets'ı kontrol edin.")
        return

    try:
        smtp_port = int(smtp_port_str)
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = email_user
        message["To"] = notification_email
        message.attach(MIMEText(html_body, "html"))

        context = ssl.create_default_context()
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls(context=context)
            server.login(email_user, email_password)
            server.sendmail(email_user, notification_email, message.as_string())
        logging.info(f"E-posta başarıyla {notification_email} adresine gönderildi.")
    except Exception as e:
        logging.error(f"E-posta gönderilirken kritik bir hata oluştu: {e}", exc_info=True)


# --- Selenium WebDriver Kurulumu ---
def setup_webdriver():
    logging.info("Selenium ile tarayıcı başlatılıyor...")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    try:
        # ChromeDriver yolunu al
        driver_path = ChromeDriverManager().install()
        logging.info(f"ChromeDriver yolu: {driver_path}")
        
        # WebDriver'ı başlat
       
        service = ChromeService(executable_path=driver_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)

        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        logging.info("WebDriver başarıyla başlatıldı.")
        return driver
    except Exception as e:
        logging.error(f"WebDriver kurulumu başarısız: {e}")
        
        # Fallback: executable_path olmadan dene
        try:
            logging.info("Fallback: executable_path olmadan deneniyor...")
            driver = webdriver.Chrome(options=chrome_options)
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            logging.info("Fallback WebDriver başarıyla başlatıldı.")
            return driver
        except Exception as e2:
            logging.error(f"Fallback WebDriver kurulumu da başarısız: {e2}")
            notify_admin("Selenium Kurulum Hatası", f"WebDriver başlatılamadı: {e}\nFallback hatası: {e2}")
            return None

# --- Çekirdek Fonksiyonlar (Link Alacak Şekilde Güncellendi) ---
def scrape_announcements():
    driver = setup_webdriver()
    if not driver:
        return None
    
    try:
        logging.info(f"Sayfa yükleniyor: {URL}")
        driver.get(URL)
        
        wait = WebDriverWait(driver, 20)
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.pal-list")))
            logging.info("Ana duyuru listesi (div.pal-list) bulundu.")
        except TimeoutException:
            logging.warning("Ana duyuru listesi bulunamadı, yine de devam ediliyor...")
        
        time.sleep(3)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        
        page_source = driver.page_source
        logging.info("Sayfa kaynağı alındı, BeautifulSoup ile parse ediliyor...")
        soup = BeautifulSoup(page_source, 'html.parser')
        
        announcements = []
        # Her bir duyuru 'item'ını ayrı ayrı işleyeceğiz
        items = soup.select("div.pal-list div.item")

        if not items:
            logging.critical("Hiçbir duyuru 'item'ı bulunamadı!")
            save_debug_page(page_source)
            return None

        for item in items:
            title_element = item.select_one("div.has-title")
            link_element = item.select_one("a") # Her item'ın içindeki linki bul
            
            if title_element and link_element and link_element.has_attr('href'):
                title = title_element.get_text(strip=True)
                relative_link = link_element['href']
                
                # Linkin tam URL olduğundan emin ol
                if relative_link.startswith('/'):
                    full_link = f"https://www.maltepe.edu.tr{relative_link}"
                else:
                    full_link = relative_link
                    
                if title and len(title) > 10:
                    announcements.append({'title': title, 'link': full_link})

        logging.info(f"Toplam {len(announcements)} adet duyuru başlığı ve linki bulundu.")
        return announcements
        
    except Exception as e:
        logging.error(f"Sayfa çekilirken genel bir hata oluştu: {e}", exc_info=True)
        try:
            save_debug_page(driver.page_source)
        except: pass
        notify_admin("Duyuru Script Hatası: Selenium", f"URL: {URL}\nHata: {e}")
        return None
    finally:
        if driver:
            driver.quit()
            logging.info("Tarayıcı kapatıldı.")

# --- Ana İş Akışı (Linkli ve Filtreli E-posta Gönderimi) ---
def main():
    setup_logging()
    previous_titles = load_previous_announcements()
    current_announcements = scrape_announcements()

    if not current_announcements:
        logging.warning("Güncel duyuru bulunamadı veya siteye erişilemedi. İşlem sonlandırılıyor.")
        sys.exit(0)

    # Karşılaştırma için sadece güncel başlıkları içeren bir set oluştur
    current_titles_set = {ann['title'] for ann in current_announcements}
    
    # Yeni duyuruları (hem başlık hem link içeren dict'ler olarak) bul
    new_announcements = [ann for ann in current_announcements if ann['title'] not in previous_titles]
    
    if not new_announcements:
        logging.info("Yeni duyuru bulunamadı.")
    else:
        logging.info(f"--- {len(new_announcements)} ADET YENİ DUYURU TESPİT EDİLDİ ---")
        
        # Sadece anahtar kelimeyi içeren yeni duyuruları filtrele
        filtered_announcements = [ann for ann in new_announcements if KEYWORD.lower() in ann['title'].lower()]
        
        if filtered_announcements:
            logging.warning(f"--- ÖNEMLİ: '{KEYWORD}' İÇEREN YENİ DUYURULAR ---")
            
            # --- E-POSTA GÖNDERME ADIMI ---
            email_subject = f"Yeni '{KEYWORD}' Duyurusu Tespit Edildi!"
            
            html_body = f"<h3>Merhaba,</h3><p>Maltepe Üniversitesi'nde '{KEYWORD}' kelimesini içeren yeni duyurular bulundu:</p><ul>"
            for ann in filtered_announcements:
                logging.warning(f"BULUNDU: {ann['title']}")
                # E-posta içeriğine tıklanabilir link olarak ekle
                html_body += f"<li><a href='{ann['link']}' target='_blank'>{ann['title']}</a></li>"
            html_body += '</ul><hr><p><small>Bu e-posta, MAU-Duyuru betiği tarafından otomatik olarak gönderilmiştir.</small></p>'
            
            send_email(email_subject, html_body)
            # --- E-POSTA GÖNDERME SONU ---
            
        else:
            logging.info(f"Yeni duyurular arasında '{KEYWORD}' içeren bulunamadı.")

    # JSON dosyasına kaydetmek için sadece başlıkları kullan
    save_announcements(list(current_titles_set))
    logging.info("Script başarıyla tamamlandı.")
if __name__ == "__main__":
    main()
