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
    logging.info("Duyuru kontrol scripti başlatıldı (Plan C: Selenium Geliştirilmiş).")

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
        driver = webdriver.Chrome(executable_path=driver_path, options=chrome_options)
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

# --- Çekirdek Fonksiyonlar ---
def scrape_announcements():
    driver = setup_webdriver()
    if not driver:
        return None
    
    try:
        logging.info(f"Sayfa yükleniyor: {URL}")
        driver.get(URL)
        
        # Sayfa yüklenmesini bekle
        wait = WebDriverWait(driver, 20)
        
        # Çoklu bekleme stratejisi
        selectors_to_wait = [
            (By.CSS_SELECTOR, "div.page-announcement-list"),
            (By.CSS_SELECTOR, "div.announcement-list"),
            (By.CSS_SELECTOR, ".announcement-item"),
            (By.CSS_SELECTOR, "h3"),
            (By.TAG_NAME, "body")
        ]
        
        # En az bir selector'ın yüklenmesini bekle
        element_found = False
        for by, selector in selectors_to_wait:
            try:
                wait.until(EC.presence_of_element_located((by, selector)))
                logging.info(f"Sayfa elementi bulundu: {selector}")
                element_found = True
                break
            except TimeoutException:
                continue
        
        if not element_found:
            logging.warning("Hiçbir beklenen element bulunamadı, yine de devam ediliyor...")
        
        # JavaScript'in çalışması için ekstra bekleme
        time.sleep(3)
        
        # Sayfayı scroll et (lazy loading için)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        
        # Sayfa kaynağını al
        page_source = driver.page_source
        logging.info("Sayfa kaynağı alındı, BeautifulSoup ile parse ediliyor...")
        
        soup = BeautifulSoup(page_source, 'html.parser')
        
        # Geliştirilmiş seçici listesi
        selectors = [
            "div.page-announcement-list div.announcement-item h3",
            "div.announcement-list div.announcement-item h3", 
            "div.announcement-item h3",
            ".announcement-item h3",
            "a.announcement-item-link h3",
            ".announcement-item-link h3",
            "div.announcement h3",
            ".announcement h3",
            "div[class*='announcement'] h3",
            "div[class*='duyuru'] h3",
            "h3[class*='title']",
            "h3[class*='baslik']",
            # Fallback seçiciler
            "h3",
            "div.title",
            ".title",
            "a[href*='duyuru']"
        ]
        
        titles = []
        successful_selector = None
        
        for selector in selectors:
            try:
                elements = soup.select(selector)
                if elements:
                    potential_titles = []
                    for elem in elements:
                        text = elem.get_text(strip=True)
                        if text and len(text) > 10:  # Boş veya çok kısa başlıkları filtrele
                            potential_titles.append(text)
                    
                    if potential_titles:
                        titles = potential_titles
                        successful_selector = selector
                        logging.info(f"{len(titles)} adet başlık '{selector}' seçicisi ile başarıyla bulundu.")
                        break
            except Exception as e:
                logging.warning(f"Seçici '{selector}' ile hata: {e}")
                continue
        
        if not titles:
            logging.critical("Hiçbir seçici ile duyuru başlığı bulunamadı!")
            
            # Debug bilgisi ekle
            logging.info("Debug: Sayfa başlığı: " + soup.title.string if soup.title else "Başlık bulunamadı")
            
            # Sayfada bulunan tüm h3'leri logla
            all_h3 = soup.find_all('h3')
            logging.info(f"Debug: Sayfada toplam {len(all_h3)} adet h3 elementi bulundu")
            for i, h3 in enumerate(all_h3[:5]):  # İlk 5 tanesini göster
                logging.info(f"Debug h3[{i}]: {h3.get_text(strip=True)[:100]}")
            
            # Announcement içeren div'leri bul
            announcement_divs = soup.find_all('div', class_=lambda x: x and 'announcement' in x.lower())
            logging.info(f"Debug: 'announcement' içeren {len(announcement_divs)} div bulundu")
            
            save_debug_page(page_source)
            notify_admin("Duyuru Script Hatası: Başlık Bulunamadı", 
                        f"Selenium ile sayfa yüklendi ancak CSS seçicisi eşleşmedi. '{DEBUG_HTML_FILE}' dosyasını kontrol edin.")
            return None
        
        # Başlıkları temizle ve filtrele
        cleaned_titles = []
        for title in titles:
            if title and len(title.strip()) > 5:  # Çok kısa başlıkları filtrele
                cleaned_titles.append(title.strip())
        
        logging.info(f"Toplam {len(cleaned_titles)} adet temizlenmiş başlık bulundu.")
        logging.info(f"Kullanılan seçici: {successful_selector}")
        
        return cleaned_titles
        
    except Exception as e:
        logging.error(f"Sayfa çekilirken hata oluştu: {e}")
        try:
            save_debug_page(driver.page_source)
        except:
            pass
        notify_admin("Duyuru Script Hatası: Selenium", f"URL: {URL}\nHata: {e}")
        return None
    finally:
        try:
            driver.quit()
            logging.info("Tarayıcı kapatıldı.")
        except:
            pass

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
        
        # Güvenli set dönüşümü
        try:
            previous_titles_set = set(str(title) for title in previous_titles if title)
            current_titles_set = set(str(title) for title in current_titles if title)
            
            new_titles = [title for title in current_titles if str(title) not in previous_titles_set]
            
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
                    
        except Exception as e:
            logging.error(f"Duyuru karşılaştırması sırasında hata: {e}")
            logging.info("Güvenli mod: Tüm mevcut duyurular listelenecek.")
            print(f"\n--- MEVCUT DUYURULAR (GÜVENLI MOD) ---")
            for title in current_titles:
                print(f"- {title}")
            print("----------------------------------------")

    save_announcements(current_titles)
    logging.info("Script başarıyla tamamlandı.")

if __name__ == "__main__":
    main()
