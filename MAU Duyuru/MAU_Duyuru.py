# MAU_Duyuru.py (Tüm Duyuruları E-posta Gönderme Sürümü)

import os
import sys
import json
import logging
import datetime
import time
# --- E-POSTA İÇİN GEREKLİ KÜTÜPHANELER ---
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
# ---
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from dotenv import load_dotenv

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
    logging.info("Duyuru kontrol scripti başlatıldı (Tüm Duyuruları E-posta Gönderme Sürümü).")

# --- E-POSTA GÖNDERME FONKSİYONU ---
def send_email(subject, html_body):
    email_enabled = os.getenv("EMAIL_ENABLED", "false").lower() == "true"
    if not email_enabled:
        logging.info("E-posta gönderimi kapalı (EMAIL_ENABLED=false).")
        return

    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port_str = os.getenv("SMTP_PORT")
    email_user = os.getenv("EMAIL_USER")
    email_password = os.getenv("EMAIL_PASSWORD")
    notification_email = os.getenv("NOTIFICATION_EMAIL")

    if not all([smtp_server, smtp_port_str, email_user, email_password, notification_email]):
        logging.error("E-posta ayarları eksik! Gerekli GitHub secret'ları tanımlanmamış.")
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
        with smtplib.SMTP_SSL(smtp_server, smtp_port, context=context) as server:
            server.login(email_user, email_password)
            server.sendmail(email_user, notification_email, message.as_string())
        logging.info(f"E-posta başarıyla {notification_email} adresine gönderildi.")

    except Exception as e:
        logging.error(f"E-posta gönderilirken kritik bir hata oluştu: {e}", exc_info=True)

# --- Dosya İşlemleri ---
def load_previous_announcements():
    if not os.path.exists(JSON_FILE):
        return []
    try:
        with open(JSON_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('titles', [])
    except (json.JSONDecodeError, FileNotFoundError):
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
        logging.info(f"Güncel {len(titles)} duyuru '{JSON_FILE}' dosyasına kaydedildi.")
    except Exception as e:
        logging.error(f"Duyurular '{JSON_FILE}' dosyasına kaydedilirken hata: {e}")

# --- Selenium ve Scraping Fonksiyonları (Değişiklik yok) ---
def setup_webdriver():
    logging.info("Selenium ile tarayıcı başlatılıyor...")
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    try:
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        logging.info("WebDriver başarıyla başlatıldı.")
        return driver
    except Exception as e:
        logging.error(f"WebDriver kurulumu başarısız: {e}", exc_info=True)
        return None

def scrape_announcements():
    driver = setup_webdriver()
    if not driver:
        return None
    try:
        logging.info(f"Sayfa yükleniyor: {URL}")
        driver.get(URL)
        page_source = driver.page_source
        if "MsgSystemErrorTitle" in page_source:
            logging.error("Site bir sunucu hatası döndürdü. İşlem durduruluyor.")
            return None
        wait = WebDriverWait(driver, 20)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.pal-list")))
        time.sleep(3)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')
        elements = soup.select("div.pal-list div.item div.has-title")
        titles = [elem.get_text(strip=True) for elem in elements if elem.get_text(strip=True) and len(elem.get_text(strip=True)) > 10]
        logging.info(f"Toplam {len(titles)} adet başlık siteden başarıyla çekildi.")
        return titles
    except Exception as e:
        logging.error(f"Sayfa çekilirken bir hata oluştu: {e}", exc_info=True)
        return None
    finally:
        if driver:
            driver.quit()
            logging.info("Tarayıcı kapatıldı.")

# --- ANA İŞ AKIŞI (YENİ E-POSTA MANTIĞIYLA) ---
def main():
    setup_logging()
    
    current_titles = scrape_announcements()

    if current_titles is None or not current_titles:
        logging.warning("Güncel duyuru bulunamadı veya siteye erişilemedi. İşlem sonlandırılıyor.")
        sys.exit(0) # Hata değil, normal bir bitiş olarak çık

    # --- İsteğiniz Üzerine: Tüm Duyuruları E-posta Gönderme ---
    today_str = datetime.date.today().strftime('%d-%m-%Y')
    email_subject = f"Maltepe Üniversitesi Güncel Duyurular - {today_str}"
    
    html_body = f"<h3>Merhaba,</h3><p>Maltepe Üniversitesi web sitesindeki güncel duyurular ({len(current_titles)} adet):</p><ul>"
    for title in current_titles:
        html_body += f"<li>{title}</li>"
    html_body += f'</ul><hr><p><small>Bu e-posta, MAU-Duyuru betiği tarafından otomatik olarak gönderilmiştir.</small></p>'
    
    send_email(email_subject, html_body)
    # --- E-posta Gönderme Bitişi ---

    # JSON dosyasını her zaman en güncel haliyle kaydet
    save_announcements(current_titles)
    
    logging.info("Script başarıyla tamamlandı.")

if __name__ == "__main__":
    main()
