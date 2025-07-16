# MAU_Duyuru.py (İstenen Stabil Sürüm - 12. Adım)

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
    logging.info("Duyuru kontrol scripti başlatıldı (İstenen Stabil Sürüm).")

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

# --- Hata Yönetimi ---
def save_debug_page(content):
    try:
        with open(DEBUG_HTML_FILE, 'w', encoding='utf-8') as f:
            f.write(content)
        logging.info(f"Hata ayıklama için sayfa kaynağı '{DEBUG_HTML_FILE}' olarak kaydedildi.")
    except Exception as e:
        logging.error(f"Debug dosyası kaydedilirken hata oluştu: {e}")

def notify_admin(subject, body):
    # Bu fonksiyon şimdilik sadece loglama yapıyor
    logging.critical(f"YÖNETİCİ BİLDİRİMİ GEREKİYOR: Başlık: {subject}")
    logging.critical(f"Detay: {body}")

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
        return None

# --- Çekirdek Fonksiyon (En Stabil Hali) ---
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
            save_debug_page(page_source)
            notify_admin("Duyuru Script Hatası: Başlık Bulunamadı", "Sayfa yüklendi ancak CSS seçicileri eşleşmedi.")
            return None
        
        best_selector = max(all_results, key=lambda k: len(all_results[k]))
        cleaned_titles = all_results[best_selector]
        
        logging.info(f"En iyi sonuç seçildi. Toplam {len(cleaned_titles)} adet temizlenmiş başlık bulundu.")
        logging.info(f"Kullanılan en verimli seçici: {best_selector}")
        
        return cleaned_titles
        
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

# --- Ana İş Akışı ---
def main():
    setup_logging()
    previous_titles = load_previous_announcements()
    is_first_run = not previous_titles
    current_titles = scrape_announcements()

    if current_titles is None:
        logging.critical("Veri çekilemediği için işlem sonlandırılıyor.")
        sys.exit(1)

    if is_first_run:
        logging.info("İlk çalıştırma. Tüm duyurular listeleniyor:")
        print("\n--- TÜM DUYURULAR (İLK ÇALIŞTIRMA) ---")
        for title in current_titles:
            print(f"- {title}")
        print("----------------------------------------")
    else:
        logging.info("Sonraki çalıştırma. Sadece yeni ve ilgili duyurular listelenecek.")
        
        previous_titles_set = set(previous_titles)
        new_titles = [title for title in current_titles if title not in previous_titles_set]
        
        if not new_titles:
            logging.info("Yeni duyuru bulunamadı.")
        else:
            logging.info(f"{len(new_titles)} adet yeni duyuru tespit edildi.")
            filtered_new_titles = [title for title in new_titles if KEYWORD.lower() in title.lower()]
            
            if filtered_new_titles:
                logging.info(f"'{KEYWORD}' anahtar kelimesini içeren {len(filtered_new_titles)} yeni duyuru bulundu:")
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
