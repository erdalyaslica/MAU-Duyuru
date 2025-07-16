# MAU_Duyuru.py (Plan D: E-posta Bildirimi Aktif)

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
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# --- Sabitler ve Konfigürasyon ---
URL = "https://www.maltepe.edu.tr/tr/duyuru-listesi"
JSON_FILE = "last_announcements.json"
LOG_FILE = "duyuru.log"
DEBUG_HTML_FILE = "debug_page.html"
ENV_FILE = ".env"
KEYWORD = "alınacaktır"

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
    logging.info("Duyuru kontrol scripti başlatıldı (Plan D: E-posta Bildirimi Aktif).")

# --- Dosya İşlemleri ---
def load_previous_announcements():
    if not os.path.exists(JSON_FILE):
        logging.warning(f"'{JSON_FILE}' bulunamadı. İlk çalıştırma olarak kabul ediliyor.")
        return []
    try:
        with open(JSON_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('titles', [])
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logging.error(f"'{JSON_FILE}' okunurken hata oluştu: {e}. Boş dosya veya bozuk format. İlk çalıştırma gibi devam ediliyor.")
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

# --- YENİLENEN E-POSTA FONKSİYONU ---
def notify_admin(subject, body):
    # GitHub Actions'tan gelen ortam değişkenlerini al
    email_enabled = os.getenv("EMAIL_ENABLED", "false").lower() == "true"
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = os.getenv("SMTP_PORT")
    email_user = os.getenv("EMAIL_USER")
    email_password = os.getenv("EMAIL_PASSWORD")
    notification_email = os.getenv("NOTIFICATION_EMAIL")

    # Sadece loglama yap, e-posta gönderme
    logging.critical(f"YÖNETİCİ BİLDİRİMİ: Başlık: {subject}")
    logging.critical(f"Detay: {body}")

    if not email_enabled:
        logging.info("E-posta gönderimi kapalı (EMAIL_ENABLED=false).")
        return

    if not all([smtp_server, smtp_port, email_user, email_password, notification_email]):
        logging.error("E-posta ayarları eksik! Gerekli ortam değişkenleri (secret'lar) tanımlanmamış.")
        return

    try:
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = email_user
        message["To"] = notification_email

        # Hem düz metin hem de HTML formatında e-posta içeriği oluştur
        html_body = f"""
        <html>
        <body>
            <h2>Maltepe Üniversitesi Duyuru Takip Sistemi</h2>
            <p>Merhaba,</p>
            <p>Sisteminizi ilgilendiren yeni bir duyuru tespit edildi:</p>
            <blockquote style="border-left: 4px solid #ccc; padding-left: 10px; margin-left: 5px;">
                {body}
            </blockquote>
            <p>Duyuruları görmek için <a href="{URL}">siteyi ziyaret edebilirsiniz</a>.</p>
            <hr>
            <p><small>Bu e-posta, GitHub Actions üzerinde çalışan otomatik bir betik tarafından gönderilmiştir.</small></p>
        </body>
        </html>
        """
        message.attach(MIMEText(html_body, "html"))

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_server, int(smtp_port), context=context) as server:
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
    
    try:
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        logging.info("WebDriver başarıyla başlatıldı.")
        return driver
    except Exception as e:
        logging.error(f"WebDriver kurulumu başarısız: {e}", exc_info=True)
        # Fallback mekanizmasını da modern hale getirelim
        try:
            logging.info("Fallback: WebDriver'ı options ile başlatma deneniyor...")
            driver = webdriver.Chrome(options=chrome_options)
            return driver
        except Exception as e2:
            logging.critical(f"Fallback WebDriver kurulumu da başarısız: {e2}")
            notify_admin("Kritik Hata: WebDriver Başlatılamadı", f"Script çalışmaya başlayamadı. Hata: {e2}")
            return None


# --- Çekirdek Fonksiyon ---
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
        soup = BeautifulSoup(page_source, 'html.parser')
        
        selectors = [
            "div.pal-list div.item div.has-title",
            "h3"
        ]
        
        all_results = {}
        for selector in selectors:
            try:
                elements = soup.select(selector)
                if elements:
                    potential_titles = [elem.get_text(strip=True) for elem in elements if elem.get_text(strip=True) and len(elem.get_text(strip=True)) > 10]
                    if potential_titles:
                        all_results[selector] = list(set(potential_titles))
                        logging.info(f"'{selector}' seçicisi ile {len(all_results[selector])} adet tekil başlık bulundu.")
            except Exception as e:
                logging.warning(f"Seçici '{selector}' ile hata: {e}")

        if not all_results:
            logging.critical("Hiçbir seçici ile duyuru başlığı bulunamadı!")
            with open(DEBUG_HTML_FILE, 'w', encoding='utf-8') as f:
                f.write(page_source)
            notify_admin("Duyuru Script Hatası: Başlık Bulunamadı", "Sayfa yüklendi ancak CSS seçicileri eşleşmedi. Lütfen debug dosyasını kontrol edin.")
            return None
        
        best_selector = max(all_results, key=lambda k: len(all_results[k]))
        cleaned_titles = all_results[best_selector]
        
        logging.info(f"En iyi sonuç seçildi. Toplam {len(cleaned_titles)} adet başlık bulundu. Kullanılan seçici: {best_selector}")
        return cleaned_titles
        
    except Exception as e:
        logging.error(f"Sayfa çekilirken genel bir hata oluştu: {e}", exc_info=True)
        try:
            with open(DEBUG_HTML_FILE, 'w', encoding='utf-8') as f:
                f.write(driver.page_source)
        except: pass
        notify_admin("Duyuru Script Hatası: Selenium", f"URL: {URL}\nHata: {e}")
        return None
    finally:
        if driver:
            driver.quit()
            logging.info("Tarayıcı kapatıldı.")

# --- ANA İŞ AKIŞI (E-POSTA ÇAĞRISI EKLENDİ) ---
def main():
    setup_logging()
    previous_titles = load_previous_announcements()
    current_titles = scrape_announcements()

    if current_titles is None:
        logging.critical("Veri çekilemediği için işlem sonlandırılıyor.")
        sys.exit(1)

    # Set'e çevirerek daha verimli karşılaştırma yap
    previous_titles_set = set(previous_titles)
    new_titles = [title for title in current_titles if title not in previous_titles_set]
    
    if not new_titles:
        logging.info("Yeni duyuru bulunamadı.")
    else:
        logging.info(f"{len(new_titles)} adet yeni duyuru tespit edildi.")
        
        # Anahtar kelimeyi içeren yeni duyuruları filtrele
        filtered_new_titles = [title for title in new_titles if KEYWORD.lower() in title.lower()]
        
        if filtered_new_titles:
            logging.info(f"'{KEYWORD}' anahtar kelimesini içeren {len(filtered_new_titles)} yeni duyuru bulundu:")
            
            # --- E-POSTA GÖNDERME ADIMI ---
            email_subject = f"Yeni Duyuru Tespit Edildi: '{KEYWORD}'"
            email_body = "<ul>" + "".join(f"<li>{title}</li>" for title in filtered_new_titles) + "</ul>"
            notify_admin(email_subject, email_body)
            # ---
            
            # Konsola da bas
            print(f"\n--- '{KEYWORD}' İÇEREN YENİ DUYURULAR ---")
            for title in filtered_new_titles:
                print(f"- {title}")
            print("-------------------------------------------")
        else:
            logging.info(f"Yeni duyurular arasında '{KEYWORD}' içeren bulunamadı.")
            
    save_announcements(current_titles)
    logging.info("Script başarıyla tamamlandı.")

if __name__ == "__main__":
    main()
