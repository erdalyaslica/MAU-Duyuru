# MAU_Duyuru.py (Stabil Sürüm - Duyuruları Loglama Odaklı)

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
    logging.info("Duyuru kontrol scripti başlatıldı (Stabil Sürüm - Loglama Odaklı).")

# --- Dosya İşlemleri ---
def load_previous_announcements():
    if not os.path.exists(JSON_FILE):
        logging.warning(f"'{JSON_FILE}' bulunamadı. İlk çalıştırma olarak kabul ediliyor.")
        return []
    try:
        with open(JSON_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data.get('titles', [])
            return [] # Eğer format bozuksa boş liste döndür
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

# --- Çekirdek Fonksiyonlar ---
def scrape_announcements():
    driver = setup_webdriver()
    if not driver:
        return None
    
    try:
        logging.info(f"Sayfa yükleniyor: {URL}")
        driver.get(URL)
        
        # Olası sunucu hatası için basit kontrol
        if "500" in driver.title or "Error" in driver.title:
             logging.error("Site bir sunucu hatası döndürdü. İşlem durduruluyor.")
             save_debug_page(driver.page_source)
             return None
             
        wait = WebDriverWait(driver, 20)
        
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.pal-list")))
            logging.info("Ana duyuru listesi (div.pal-list) bulundu.")
        except TimeoutException:
            logging.warning("Ana duyuru listesi zamanında bulunamadı. Sayfa içeriği yine de kontrol edilecek.")
        
        time.sleep(3)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        
        page_source = driver.page_source
        logging.info("Sayfa kaynağı alındı, BeautifulSoup ile parse ediliyor...")
        soup = BeautifulSoup(page_source, 'html.parser')
        
        elements = soup.select("div.pal-list div.item div.has-title")
        if not elements: # Eğer ana seçici çalışmazsa yedek seçiciyi dene
            logging.warning("'div.has-title' ile sonuç bulunamadı. Yedek seçici (h3) deneniyor.")
            elements = soup.select("h3")

        if not elements:
            logging.critical("Hiçbir seçici ile duyuru başlığı bulunamadı!")
            save_debug_page(page_source)
            return None

        cleaned_titles = list(set([elem.get_text(strip=True) for elem in elements if len(elem.get_text(strip=True)) > 10]))
        
        logging.info(f"Toplam {len(cleaned_titles)} adet tekil başlık bulundu.")
        return cleaned_titles
        
    except Exception as e:
        logging.error(f"Sayfa çekilirken genel bir hata oluştu: {e}", exc_info=True)
        try:
            save_debug_page(driver.page_source)
        except: pass
        return None
    finally:
        if driver:
            driver.quit()
            logging.info("Tarayıcı kapatıldı.")

# --- Ana İş Akışı ---
def main():
    setup_logging()
    previous_titles = load_previous_announcements()
    current_titles = scrape_announcements()

    if not current_titles:
        logging.warning("Güncel duyuru bulunamadı veya siteye erişilemedi. İşlem sonlandırılıyor.")
        # JSON dosyasını boş kaydetmemek için burada çıkış yapıyoruz.
        # Böylece bir sonraki çalıştırmada eski liste kaybolmaz.
        sys.exit(0) 

    # --- İSTEK: Bulunan tüm duyuruları logla ---
    logging.info("--- SİTEDEKİ GÜNCEL DUYURULAR ---")
    for title in sorted(current_titles): # Alfabetik sıralı loglayalım
        logging.info(f"- {title}")
    logging.info("--- GÜNCEL DUYURU LİSTESİ SONU ---")
    
    # --- Yeni duyuruları bulma ve karşılaştırma ---
    previous_titles_set = set(previous_titles)
    new_titles = [title for title in current_titles if title not in previous_titles_set]
    
    if not new_titles:
        logging.info("Yeni duyuru bulunamadı.")
    else:
        logging.info("--- YENİ DUYURULAR TESPİT EDİLDİ ---")
        for title in sorted(new_titles):
            logging.info(f"YENİ: {title}")
        logging.info("--- YENİ DUYURU LİSTESİ SONU ---")

        # Keyword içeren yeni duyuruları ayrıca belirt
        filtered_new_titles = [title for title in new_titles if KEYWORD.lower() in title.lower()]
        if filtered_new_titles:
            logging.warning(f"--- ÖNEMLİ: '{KEYWORD}' İÇEREN YENİ DUYURULAR ---")
            for title in sorted(filtered_new_titles):
                logging.warning(f"BULUNDU: {title}")
            logging.warning("--- ÖNEMLİ DUYURULAR LİSTE SONU ---")

    save_announcements(current_titles)
    logging.info("Script başarıyla tamamlandı.")

if __name__ == "__main__":
    main()
