# MAU_Duyuru.py (Plan B: cloudscraper ile 403 Hatası Çözümü)

import os
import sys
import json
import logging
import datetime
# import requests # <<< DEĞİŞİKLİK 1: requests'i devre dışı bırakıyoruz
import cloudscraper # <<< DEĞİŞİKLİK 1: cloudscraper'ı içeri aktarıyoruz
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
    logging.info("Duyuru kontrol scripti başlatıldı (Plan B: cloudscraper).")

# --- Dosya İşlemleri (Değişiklik yok) ---
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

# --- Hata Yönetimi (Değişiklik yok) ---
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
    logging.info(f"Duyurular şu adresten çekiliyor: {URL}")

    # <<< DEĞİŞİKLİK 2: cloudscraper nesnesi oluşturuluyor >>>
    # Bu nesne, anti-bot sistemlerini geçmek için gerekli ayarları otomatik yapar.
    scraper = cloudscraper.create_scraper()
    
    # Not: cloudscraper kendi etkili başlıklarını yönettiği için özel header tanımlamaya gerek kalmayabilir,
    # ancak fazladan göndermenin zararı olmaz.
    headers = {
        'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://www.google.com/'
    }
    
    try:
        # <<< DEĞİŞİKLİK 3: requests.get() yerine scraper.get() kullanılıyor >>>
        # cloudscraper, requests ile uyumlu olduğundan hata yakalama (exception) blokları aynı kalabilir.
        response = scraper.get(URL, headers=headers, timeout=30) # Timeout'u biraz artırmak iyi olabilir
        response.raise_for_status()
    except Exception as e: # cloudscraper bazen farklı hatalar fırlatabilir, genel Exception daha güvenli.
        logging.error(f"Sayfa çekilirken hata oluştu: {e}")
        if hasattr(e, 'response') and e.response is not None:
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
        elements = soup.select(selector)
        if elements:
            titles = [elem.get_text(strip=True) for elem in elements]
            logging.info(f"{len(titles)} adet başlık '{selector}' seçicisi ile başarıyla bulundu.")
            break
    
    if not titles:
        logging.critical("Hiçbir seçici ile duyuru başlığı bulunamadı! Sayfa yapısı değişmiş veya koruma aşılamamış olabilir.")
        save_debug_page(page_content)
        notify_admin("Duyuru Script Hatası: Başlık Bulunamadı", f"Sayfa yapısı değişmiş veya koruma aşılamamış olabilir. '{DEBUG_HTML_FILE}' dosyasını kontrol edin.")
        return None
        
    return titles

# --- Ana İş Akışı (Değişiklik Yok) ---
def main():
    setup_logging()
    previous_titles = load_previous_announcements()
    is_first_run = not previous_titles
    current_titles = scrape_announcements()

    if current_titles is None:
        logging.critical("Veri çekilemediği için işlem sonlandırılıyor.")
        sys.exit(1)

    # ... (main fonksiyonunun geri kalanı aynı)
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
