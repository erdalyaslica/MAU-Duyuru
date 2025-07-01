# MAU_Duyuru.py (Düzeltilmiş ve Temizleme Eklenmiş Hali)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests, json, logging, os, time, sys, traceback, smtplib
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

class MAUDuyuruTakipci:
    def __init__(self):
        load_dotenv()
        self.base_url = "https://www.maltepe.edu.tr"
        self.duyuru_url = "https://www.maltepe.edu.tr/tr/duyuru-listesi"
        self.json_file = "last_announcements.json"
        self.log_file = "duyuru.log"
        self.debug_file = "debug_page.html"
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.email_enabled = os.getenv('EMAIL_ENABLED', 'false').lower() == 'true'
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.email_user = os.getenv('EMAIL_USER', '')
        self.email_password = os.getenv('EMAIL_PASSWORD', '')
        self.notification_email = os.getenv('NOTIFICATION_EMAIL', '')
        self.setup_logging()
        self.logger.info("="*60)
        self.logger.info("MAÜ Duyuru Takipci başlatıldı")
        self.logger.info(f"Tarih: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info("="*60)

    def setup_logging(self):
        log_format = '%(asctime)s - %(levelname)s - %(message)s'
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(log_format))
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter(log_format))
        self.logger = logging.getLogger('MAUDuyuru')
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def save_debug_page(self, content, reason="Hata"):
        try:
            with open(self.debug_file, 'w', encoding='utf-8') as f:
                f.write(content)
            self.logger.info(f"Debug sayfası kaydedildi: {self.debug_file} (Sebep: {reason})")
        except Exception as e:
            self.logger.error(f"Debug sayfası kaydedilemedi: {e}")

    def fetch_page(self, url, max_retries=3):
        for attempt in range(max_retries):
            try:
                self.logger.info(f"Sayfa indiriliyor (Deneme {attempt + 1}/{max_retries}): {url}")
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                response.encoding = 'utf-8'
                self.logger.info(f"Sayfa başarıyla indirildi. Boyut: {len(response.text)} karakter")
                return response.text
            except requests.exceptions.RequestException as e:
                self.logger.warning(f"Sayfa indirme hatası (Deneme {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep((attempt + 1) * 5)
                else:
                    self.logger.error(f"Sayfa {max_retries} denemede indirilemedi")
                    raise

    def parse_announcements(self, html_content):
        self.logger.info("Ham duyurular (temizlenmemiş) parse ediliyor...")
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        elements = soup.select('.page-announcement-list li a, a[href*="duyuru"]')
        
        for element in elements:
            title = element.get_text(strip=True)
            link = element.get('href', '')
            if title and link:
                full_link = urljoin(self.base_url, link)
                announcements.append({'title': title, 'link': full_link})
        
        unique_announcements = {ann['link']: ann for ann in announcements}.values()
        self.logger.info(f"Toplam {len(unique_announcements)} ham duyuru bulundu.")
        return list(unique_announcements)
    
    def clean_titles_post_parsing(self, announcements):
        self.logger.info("Duyuru başlıkları temizleniyor...")
        cleaned_list = []
        for ann in announcements:
            clean_title = ann['title'].replace("Detayı görüntüle", "").strip()
            if clean_title:
                ann['title'] = clean_title
                cleaned_list.append(ann)
        self.logger.info(f"{len(cleaned_list)} temizlenmiş duyuru işlenmeye hazır.")
        return cleaned_list

    def load_previous_announcements(self):
        try:
            if os.path.exists(self.json_file):
                with open(self.json_file, 'r', encoding='utf-8') as f: return json.load(f)
            return []
        except Exception: return []

    def save_announcements(self, announcements):
        try:
            data_to_save = [{'title': ann['title'], 'link': ann['link']} for ann in announcements]
            with open(self.json_file, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, ensure_ascii=False, indent=2)
            self.logger.info(f"{len(data_to_save)} duyuru JSON dosyasına kaydedildi")
        except Exception as e: self.logger.error(f"Duyurular kaydedilemedi: {e}")

    def find_new_announcements(self, current_announcements, previous_announcements):
        previous_titles = {ann['title'] for ann in previous_announcements}
        return [ann for ann in current_announcements if ann['title'] not in previous_titles]

    def filter_important_announcements(self, announcements):
        keywords = ["ALINACAKTIR", "DEĞERLENDİRME"]
        filtered = [ann for ann in announcements if any(keyword in ann.get('title', '').upper() for keyword in keywords)]
        self.logger.info(f"{len(filtered)} duyuru filtre ile eşleşti")
        return filtered

    def format_announcement_list_html(self, announcements):
        if not announcements: return "<p>Yeni duyuru bulunamadı.</p>"
        html = '<html><head><style>body{font-family:sans-serif;line-height:1.6}ul{list-style-type:none;padding:0}li{margin-bottom:15px;padding:12px;border:1px solid #e1e1e1;border-radius:8px;background-color:#f9f9f9}a{text-decoration:none;color:#0056b3;font-weight:bold}a:hover{text-decoration:underline}</style></head><body><ul>'
        for ann in announcements: html += f'<li><a href="{ann.get("link", "#")}">{ann.get("title", "Başlık Yok")}</a></li>'
        html += "</ul></body></html>"
        return html

    def format_announcement_list(self, announcements):
        if not announcements: return "Duyuru bulunamadı."
        formatted = [f"{i}. {ann['title']}\n   Link: {ann.get('link', '')}\n" for i, ann in enumerate(announcements, 1)]
        return "\n".join(formatted)

    def send_email_notification(self, subject, body, is_html=False):
        if not self.email_enabled: return False
        try:
            msg = MIMEMultipart()
            msg['From'], msg['To'], msg['Subject'] = self.email_user, self.notification_email, subject
            msg.attach(MIMEText(body, 'html' if is_html else 'plain', 'utf-8'))
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.email_user, self.email_password)
            server.sendmail(self.email_user, self.notification_email, msg.as_string())
            server.quit()
            self.logger.info("E-posta bildirimi gönderildi.")
            return True
        except Exception as e:
            self.logger.error(f"E-posta gönderme hatası: {e}")
            return False

    def run(self):
        try:
            self.logger.info("Duyuru kontrolü başlatılıyor...")
            html_content = self.fetch_page(self.duyuru_url)
            raw_announcements = self.parse_announcements(html_content)
            current_announcements = self.clean_titles_post_parsing(raw_announcements)
            if not current_announcements:
                self.logger.warning("İşlenecek temiz duyuru bulunamadı!")
                self.save_debug_page(html_content, "Temiz duyuru bulunamadı")
                return
            previous_announcements = self.load_previous_announcements()
            if not previous_announcements:
                self.logger.info("İlk çalıştırma. Mevcut duyurular kaydediliyor.")
                print(self.format_announcement_list(current_announcements))
            else:
                new_announcements = self.find_new_announcements(current_announcements, previous_announcements)
                if new_announcements:
                    self.logger.info(f"{len(new_announcements)} yeni duyuru tespit edildi.")
                    filtered_announcements = self.filter_important_announcements(new_announcements)
                    if filtered_announcements:
                        print("\n" + "="*60 + "\nYENİ ÖNEMLİ DUYURULAR\n" + "="*60)
                        print(self.format_announcement_list(filtered_announcements))
                        if self.email_enabled:
                            subject = "MAÜ Duyuru Takip - Önemli Duyuru Bulundu!"
                            email_intro = f"Filtrenizle eşleşen {len(filtered_announcements)} yeni duyuru bulundu:<br><br>"
                            html_list = self.format_announcement_list_html(filtered_announcements)
                            self.send_email_notification(subject, email_intro + html_list, is_html=True)
                else:
                    self.logger.info("Yeni duyuru bulunamadı.")
                    print("Yeni duyuru bulunamadı.")
            self.save_announcements(current_announcements)
            self.logger.info("Duyuru kontrolü başarıyla tamamlandı.")
        except Exception as e:
            error_msg = f"Kritik hata: {e}"
            self.logger.error(f"{error_msg}\n{traceback.format_exc()}")
            if self.email_enabled:
                self.send_email_notification("MAÜ Duyuru Takip - HATA", f"Sistemde hata oluştu:\n\n{error_msg}")
            sys.exit(1)

def main():
    try:
        tracker = MAUDuyuruTakipci()
        tracker.run()
    except KeyboardInterrupt:
        print("\nProgram kullanıcı tarafından durduruldu.")
        sys.exit(0)
    except Exception as e:
        print(f"Program başlatılamadı: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
