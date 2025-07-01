#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Maltepe Üniversitesi Duyuru Takip Scripti (Geliştirilmiş Versiyon)
Bu script düzenli olarak MAÜ duyuru sayfasını kontrol eder,
yeni duyuruları (belirli anahtar kelimeler içeren) tespit eder
ve tıklanabilir linklerle e-posta gönderir.
"""

import requests
import json
import logging
import os
import time
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import sys
import traceback

class MAUDuyuruTakipci:
    def __init__(self):
        """Sınıf başlatıcı - gerekli ayarları yapar"""
        load_dotenv()
        
        self.base_url = "https://www.maltepe.edu.tr"
        self.duyuru_url = "https://www.maltepe.edu.tr/tr/duyuru-listesi"
        self.json_file = "last_announcements.json"
        self.log_file = "duyuru.log"
        self.debug_file = "debug_page.html"
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'tr-TR,tr;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
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
        """Loglama sistemini kurar"""
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
        """Debug için sayfa içeriğini kaydeder"""
        try:
            with open(self.debug_file, 'w', encoding='utf-8') as f:
                f.write(content)
            self.logger.info(f"Debug sayfası kaydedildi: {self.debug_file} (Sebep: {reason})")
        except Exception as e:
            self.logger.error(f"Debug sayfası kaydedilemedi: {e}")

    def fetch_page(self, url, max_retries=3):
        """Sayfayı indirir ve içeriğini döndürür"""
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
        """HTML içeriğinden duyuruları parse eder"""
        self.logger.info("Duyurular parse ediliyor...")
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        selectors = [
            '.page-announcement-list .announcement-item', '.page-announcement-list li',
            '.page-announcement-list a', '.page-announcement-list div',
            'div.page-announcement-list', '.page-announcement-list', '.announcement-list',
            '.duyuru-listesi', 'div.announcement-item', 'div.duyuru-item', 'div.news-item',
            '.announcement', '.duyuru', 'li.announcement', 'li.duyuru', 'article',
            'a[href*="duyuru"]', 'a[href*="announcement"]', 'tr td a', 'table tr',
            'div h3 a', 'div h4 a', 'div h2 a',
        ]
        for selector in selectors:
            try:
                elements = soup.select(selector)
                if not elements: continue
                parsed_announcements = self.parse_with_selector(elements, selector, soup)
                if parsed_announcements:
                    announcements.extend(parsed_announcements)
                    if selector.startswith('.page-announcement-list'):
                         break
            except Exception as e:
                self.logger.debug(f"Selektör '{selector}' ile parse hatası: {e}")
        
        if not announcements:
            self.logger.warning("Hiçbir ana selektör çalışmadı, fallback denenecek...")
            announcements = self.fallback_parse(soup)

        unique_announcements = []
        seen_titles = set()
        for ann in announcements:
            if ann.get('title') and ann['title'] not in seen_titles:
                unique_announcements.append(ann)
                seen_titles.add(ann['title'])
        self.logger.info(f"Toplam {len(unique_announcements)} benzersiz duyuru bulundu")
        return unique_announcements

    def parse_with_selector(self, elements, selector, soup):
        """Belirli bir selektör ile elementleri parse eder"""
        announcements = []
        for element in elements:
            try:
                title, link, date = "", "", ""
                link_element = element if element.name == 'a' else element.find('a')
                if link_element:
                    title = link_element.get_text(strip=True)
                    link = link_element.get('href', '')
                else:
                    title = element.get_text(strip=True)

                if link and not link.startswith('http'):
                    link = urljoin(self.base_url, link)

                if title and len(title) > 5:
                    announcements.append({'title': title, 'link': link, 'date': date})
            except Exception as e:
                self.logger.debug(f"Element parse hatası: {e}")
        return announcements
        
    def fallback_parse(self, soup):
        """Yedek parse stratejisi - tüm linkleri kontrol eder"""
        announcements = []
        for link_tag in soup.find_all('a', href=True):
            href = link_tag.get('href', '')
            title = link_tag.get_text(strip=True)
            if title and len(title) > 15 and ('duyuru' in href.lower() or 'ilan' in title.lower()):
                if not href.startswith('http'):
                    href = urljoin(self.base_url, href)
                announcements.append({'title': title, 'link': href, 'date': ''})
        return announcements

    def load_previous_announcements(self):
        """Önceki duyuruları JSON dosyasından yükler"""
        try:
            if os.path.exists(self.json_file):
                with open(self.json_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except Exception as e:
            self.logger.error(f"Önceki duyurular yüklenemedi: {e}")
            return []

    def save_announcements(self, announcements):
        """Duyuruları JSON dosyasına kaydeder"""
        try:
            data_to_save = [{'title': ann['title'], 'link': ann['link']} for ann in announcements]
            with open(self.json_file, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, ensure_ascii=False, indent=2)
            self.logger.info(f"{len(data_to_save)} duyuru JSON dosyasına kaydedildi")
        except Exception as e:
            self.logger.error(f"Duyurular kaydedilemedi: {e}")

    def find_new_announcements(self, current_announcements, previous_announcements):
        """Yeni duyuruları bulur"""
        previous_titles = {ann['title'] for ann in previous_announcements}
        return [ann for ann in current_announcements if ann['title'] not in previous_titles]

    def filter_important_announcements(self, announcements):
        """İstenen anahtar kelimeleri içeren önemli duyuruları filtreler"""
        keywords = ["ALINACAKTIR", "ÖN DEĞERLENDİRME SONUÇLARI"]
        filtered = []
        self.logger.info(f"Duyurular şu kelimelere göre filtreleniyor: {', '.join(keywords)}")
        for ann in announcements:
            title_upper = ann.get('title', '').upper()
            if any(keyword in title_upper for keyword in keywords):
                filtered.append(ann)
        self.logger.info(f"{len(filtered)} duyuru filtre ile eşleşti")
        return filtered

    def format_announcement_list_html(self, announcements):
        """Duyuru listesini HTML olarak formatlar"""
        if not announcements: return "<p>Yeni duyuru bulunamadı.</p>"
        html = """
        <html><head><style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; line-height: 1.6; }
        ul { list-style-type: none; padding: 0; }
        li { margin-bottom: 15px; padding: 12px; border: 1px solid #e1e1e1; border-radius: 8px; background-color: #f9f9f9; }
        a { text-decoration: none; color: #0056b3; font-weight: bold; font-size: 1.1em; }
        a:hover { text-decoration: underline; }
        .date { font-size: 0.9em; color: #555; display: block; margin-top: 8px; }
        </style></head><body><ul>
        """
        for ann in announcements:
            html += f'<li><a href="{ann.get("link", "#")}">{ann.get("title", "Başlık Yok")}</a></li>'
        html += "</ul></body></html>"
        return html

    def format_announcement_list(self, announcements):
        """Duyuru listesini düz metin olarak formatlar"""
        if not announcements: return "Duyuru bulunamadı."
        formatted = []
        for i, ann in enumerate(announcements, 1):
            formatted.append(f"{i}. {ann['title']}")
            if ann.get('link'): formatted.append(f"   Link: {ann['link']}")
            formatted.append("")
        return "\n".join(formatted)

    def send_email_notification(self, subject, body, is_html=False):
        """E-posta bildirimi gönderir."""
        if not self.email_enabled or not self.notification_email:
            self.logger.info("E-posta bildirimi devre dışı veya gerekli ayarlar eksik")
            return False
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_user
            msg['To'] = self.notification_email
            msg['Subject'] = subject
            content_type = 'html' if is_html else 'plain'
            msg.attach(MIMEText(body, content_type, 'utf-8'))
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.email_user, self.email_password)
            server.sendmail(self.email_user, self.notification_email, msg.as_string())
            server.quit()
            self.logger.info(f"E-posta bildirimi ({content_type}) gönderildi: {self.notification_email}")
            return True
        except Exception as e:
            self.logger.error(f"E-posta gönderme hatası: {e}")
            return False

    def run(self):
        """Ana çalıştırma fonksiyonu"""
        try:
            self.logger.info("Duyuru kontrolü başlatılıyor...")
            html_content = self.fetch_page(self.duyuru_url)
            current_announcements = self.parse_announcements(html_content)
            if not current_announcements:
                self.logger.warning("Hiçbir duyuru bulunamadı!")
                self.save_debug_page(html_content, "Duyuru bulunamadı")
                return
            previous_announcements = self.load_previous_announcements()
            if not previous_announcements:
                self.logger.info("İlk çalıştırma. Mevcut duyurular kaydediliyor.")
            else:
                new_announcements = self.find_new_announcements(current_announcements, previous_announcements)
                if new_announcements:
                    self.logger.info(f"{len(new_announcements)} yeni duyuru tespit edildi.")
                    filtered_announcements = self.filter_important_announcements(new_announcements)
                    if filtered_announcements:
                        print("\n" + "="*60)
                        print("YENİ ÖNEMLİ DUYURULAR")
                        print("="*60)
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
            self.logger.error(error_msg)
            self.logger.error(traceback.format_exc())
            if self.email_enabled:
                self.send_email_notification("MAÜ Duyuru Takip - HATA", f"Sistemde hata oluştu:\n\n{error_msg}")
            sys.exit(1)

def main():
    """Ana fonksiyon"""
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
