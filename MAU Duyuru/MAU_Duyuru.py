# MAU_Duyuru.py (Plan C: Selenium ile Nihai Çözüm)

import os
import sys
import json
import logging
import datetime
import time
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Selenium kütüphaneleri
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# --- Sabitler ve Konfigürasyon ---
URL = "https://www.maltepe.edu.tr/tr/duyuru-listesi"
JSON_FILE = "last_announcements.json"
LOG_FILE = "duyuru.log"
DEBUG_HTML_FILE = "debug_page.html"
ENV_FILE = ".env"
KEYWORD = "alınacaktır"

load_dotenv(dotenv_path=ENV_FILE)

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
    logging.info("Duyuru kontrol scripti başlatıldı (Plan C: Selenium).")

# --- Dosya ve Hata Yönetimi Fonksiyonları (Değişiklik Yok) ---
def load_previous_announcements():
    if not os.path.exists(JSON_FILE):
        logging.warning(f"'{JSON_FILE}' bulunamadı. İlk çalıştırma olarak kabul ediliyor.")
        return []
    try:
        with open(JSON_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('titles', []) if isinstance(data, dict) else data
    except (json.JSONDecodeError, FileNotFoundError):
        logging.error(f"'{JSON_FILE}' okunurken hata oluştu.")
        return []

def save_announcements(titles):
    try:
        with open(JSON_FILE, 'w', encoding='utf-8') as f:
            payload = {'last_update': datetime.datetime.now().isoformat(), 'count': len(titles), 'titles': titles}
            json.dump(payload, f, ensure_ascii=False, indent=4)
        logging.info(f"{len(titles)} adet güncel duyuru '{JSON_FILE}' dosyasına kaydedildi.")
    except Exception as e:
        logging.error(f"Duyurular '{JSON_FILE}' dosyasına kaydedilirken hata: {e}")

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

# --- Çekirdek Fonksiyon (SELENIUM İLE GÜNCELLENDİ) ---
def scrape_announcements():
    logging.info(f"Selenium ile tarayıcı başlatılıyor...")
    
    # Tarayıcı ayarları (görünmez modda çalıştırma)
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

    driver = None
    try:
        # Chrome sürücüsünü otomatik olarak kur ve başlat
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        logging.info(f"Sayfa yükleniyor: {URL}")
        driver.get(URL)

        # Duyuruların bulunduğu ana kapsayıcının yüklenmesini bekle (En önemli kısım)
        # JavaScript'in içeriği getirmesi için 15 saniyeye kadar bekleyecek.
        wait = WebDriverWait(driver, 15)
        
        # Sayfayı inceleyerek en dıştaki duyuru listesi konteynerini buldum: "page-announcement-list"
        container_selector = "div.page-announcement-list"
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, container_selector)))
        
        logging.info("Duyuru listesi başarıyla yüklendi. Sayfa kaynağı alınıyor.")
        time.sleep(2) # Tüm elemanların tam oturması için kısa bir ek bekleme süresi
        
        page_content = driver.page_source
        soup = BeautifulSoup(page_content, 'html.parser')

        # Artık sayfa tam yüklendiği için seçicilerimiz çalışacaktır.
        selector = "div.page-announcement-list div.announcement-item h3"
        elements = soup.select(selector)
        
        if not elements:
            logging.critical("Sayfa yüklendi ancak duyuru başlıkları seçici ile bulunamadı!")
            save_debug_page(page_content)
            notify_admin("Duyuru Script Hatası: Başlık Bulunamadı", "Selenium ile sayfa yüklendi ancak CSS seçicisi eşleşmedi. 'debug_page.html' dosyasını kontrol edin.")
            return None

        titles = [elem.get_text(strip=True) for elem in elements]
        logging.info(f"{len(titles)} adet başlık başarıyla bulundu.")
        return titles

    except Exception as e:
        logging.error(f"Selenium çalışırken bir hata oluştu: {e}")
        notify_admin("Kritik Selenium Hatası", str(e))
        if driver and driver.page_source:
             save_debug_page(driver.page_source)
        return None
    finally:
        if driver:
            driver.quit()
            logging.info("Tarayıcı kapatıldı.")

# --- Ana İş Akışı (Değişiklik Yok) ---
def main():
    setup_logging()
    previous_titles = load_previous_announcements()
    current_titles = scrape_announcements()

    if current_titles is None:
        logging.critical("Veri çekilemediği için işlem sonlandırılıyor.")
        sys.exit(1)

    is_first_run = not previous_titles
    if is_first_run:
        logging.info("İlk çalıştırma. Tüm duyurular listeleniyor:")
        print("\n--- TÜM DUYURULAR (İLK ÇALIŞTIRMA) ---")
        for title in current_titles:
            print(f"- {title}")
        print("----------------------------------------")
    else:
        # ... (main fonksiyonunun geri kalanı aynı)
        previous_titles_set = set(previous_titles)
        new_titles = [title for title in current_titles if title not in previous_titles_set]
        if not new_titles:
            logging.info("Yeni duyuru bulunamadı.")
        else:
            logging.info(f"{len(new_titles)} adet yeni duyuru tespit edildi.")
            filtered_new_titles = [title for title in new_titles if KEYWORD in title.lower()]
            if filtered_new_titles:
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
