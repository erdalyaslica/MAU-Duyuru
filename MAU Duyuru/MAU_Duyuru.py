# MAU_Duyuru.py (403 Forbidden Hatası Çözümü)

import os
import sys
import json
import logging
import datetime
import requests
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
    """Detaylı loglama ayarlarını yapılandırır."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] - %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    logging.info("="*50)
    logging.info("Duyuru kontrol scripti başlatıldı.")

# --- Dosya İşlemleri ---
def load_previous_announcements():
    if not os.path.exists(JSON_FILE):
        logging.warning(f"'{JSON_FILE}' bulunamadı. İlk çalıştırma olarak kabul ediliyor.")
        return []
    try:
        with open(JSON_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('titles', []) if isinstance(data, dict) else data
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

# --- Hata Yönetimi ve Bildirim ---
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

# --- Çekirdek Fonksiyonlar ---
def scrape_announcements():
    """Maltepe Üniversitesi duyuru sayfasından başlıkları çeker."""
    logging.info(f"Duyurular şu adresten çekiliyor: {URL}")
    
    # <<< GÜNCELLEME BURADA: 403 Hatasını aşmak için tarayıcı başlıkları taklit ediliyor >>>
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'DNT': '1', # Do Not Track
        'Referer': 'https://www.google.com/' # Nereden geldiğimizi belirtmek
    }
    
    try:
        response = requests.get(URL, headers=headers, timeout=20)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logging.error(f"Sayfa çekilirken ağ hatası oluştu: {e}")
        # Hata durumunda sayfa içeriğini (genellikle bir hata mesajı içerir) kaydetmeyi dene
        if e.response is not None:
            save_debug_page(e.response.text)
        notify_admin("Duyuru Script Hatası: Sayfa Erişimi", f"URL: {URL}\nHata: {e}")
        return None

    page_content = response.text
    soup = BeautifulSoup(page_content, 'html.parser')

    selectors = [
        "div.page-announcement-list div.announcement-item h3",
        "div.announcement-list div.announcement-item h3",
        "a.announcement-item-link h3"
    ]
    
    titles = []
    for selector in selectors:
        logging.info(f"Seçici deneniyor: '{selector}'")
        elements = soup.select(selector)
        if elements:
            titles = [elem.get_text(strip=True) for elem in elements]
            logging.info(f"{len(titles)} adet başlık '{selector}' seçicisi ile başarıyla bulundu.")
            break
    
    if not titles:
        logging.critical("Hiçbir seçici ile duyuru başlığı bulunamadı! Sayfa yapısı değişmiş olabilir.")
        save_debug_page(page_content)
        notify_admin("Duyuru Script Hatası: Başlık Bulunamadı", "Sayfa yapısı değişmiş olabilir. 'debug_page.html' dosyasını kontrol edin.")
        return None
        
    return titles

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
            filtered_new_titles = [title for title in new_titles if KEYWORD in title.lower()]
            
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
