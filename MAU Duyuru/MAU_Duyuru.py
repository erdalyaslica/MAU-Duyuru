import csv
import html
import logging
import os
import smtplib
import sys
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

URL = os.getenv("ANNOUNCEMENTS_URL", "https://www.maltepe.edu.tr/tr/duyuru-listesi")
STATE_FILE = Path(os.getenv("STATE_FILE", "duyurular.csv"))
IMPORTANT_WORDS = ("alınacaktır", "değerlendirme")
MIN_ANNOUNCEMENTS = int(os.getenv("MIN_ANNOUNCEMENTS", "20"))


def setup_logging():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def normalize_url(url):
    parts = urlsplit(urljoin(URL, (url or "").strip()))
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/") or "/", "", ""))


def fetch_html():
    headers = {"User-Agent": "Mozilla/5.0 Chrome/142 Safari/537.36", "Accept-Language": "tr-TR,tr;q=0.9"}
    response = None
    try:
        response = requests.get(URL, headers=headers, timeout=60)
        response.raise_for_status()
        logging.info("Duyuru sayfası doğrudan bağlantıyla alındı")
    except requests.RequestException as direct_error:
        logging.warning("Doğrudan bağlantı başarısız (%s); Scrape.do deneniyor", direct_error)
        token = os.getenv("SCRAPEDO_TOKEN", "").strip()
        if not token:
            raise RuntimeError(
                "Maltepe sitesi doğrudan erişimi engelledi ve SCRAPEDO_TOKEN tanımlı değil"
            ) from direct_error
        response = requests.get(
            "https://api.scrape.do/",
            params={"token": token, "url": URL, "super": "true", "geoCode": "tr"},
            headers=headers,
            timeout=120,
        )
        response.raise_for_status()
        logging.info("Duyuru sayfası Scrape.do üzerinden alındı")
    if len(response.text) < 5000:
        raise RuntimeError(f"Duyuru sayfası beklenenden kısa geldi ({len(response.text)} karakter)")
    return response.text


def parse_announcements(source):
    soup = BeautifulSoup(source, "html.parser")
    announcements, seen = [], set()
    for item in soup.select("div.pal-list div.item"):
        anchor, title_node = item.select_one("a[href]"), item.select_one("div.has-title")
        if not anchor or not title_node:
            continue
        title = " ".join(title_node.get_text(" ", strip=True).split())
        link = normalize_url(anchor.get("href", ""))
        if len(title) < 4 or "/tr/" not in link or link in seen:
            continue
        seen.add(link)
        announcements.append({"Başlık": title, "Link": link})
    if len(announcements) < MIN_ANNOUNCEMENTS:
        raise RuntimeError(f"Yalnızca {len(announcements)} duyuru bulundu; sayfa yapısı değişmiş olabilir. Liste korunuyor.")
    return announcements


def load_state():
    if not STATE_FILE.exists():
        return []
    with STATE_FILE.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def save_state(current, previous):
    previous_by_link = {normalize_url(row.get("Link", "")): row for row in previous}
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    rows = []
    for item in current:
        old = previous_by_link.get(normalize_url(item["Link"]), {})
        rows.append({"Duyuru Başlığı": item["Başlık"], "Link": item["Link"], "Eklenme Tarihi": old.get("Eklenme Tarihi") or now, "Mail Durumu": old.get("Mail Durumu") or "ℹ️ Listeye Eklendi"})
    temp = STATE_FILE.with_suffix(".tmp")
    with temp.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("Duyuru Başlığı", "Link", "Eklenme Tarihi", "Mail Durumu"))
        writer.writeheader()
        writer.writerows(rows)
    temp.replace(STATE_FILE)


def email_shell(eyebrow, title, subtitle, content, accent="#0071e3"):
    return f"""<!doctype html><html><body style="margin:0;background:#f5f5f7;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;color:#1d1d1f">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0"><tr><td align="center" style="padding:40px 16px">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:720px;background:#fff;border-radius:24px;overflow:hidden;box-shadow:0 8px 32px rgba(0,0,0,.08)">
    <tr><td style="height:6px;background:{accent}">&nbsp;</td></tr><tr><td style="padding:44px 44px 24px">
    <div style="font-size:12px;font-weight:700;letter-spacing:1.4px;text-transform:uppercase;color:{accent}">{eyebrow}</div>
    <h1 style="margin:10px 0 12px;font-size:34px;line-height:40px">{title}</h1>
    <p style="margin:0;font-size:17px;line-height:26px;color:#6e6e73">{subtitle}</p></td></tr>
    <tr><td style="padding:0 44px 44px">{content}</td></tr></table>
    <p style="font-size:12px;color:#86868b">MAU Duyuru · GitHub Actions</p>
    </td></tr></table></body></html>"""


def announcement_cards(items):
    return "".join(
        f"""<div style="margin-top:14px;padding:20px;border:1px solid #e8e8ed;border-radius:16px">
        <div style="font-size:16px;line-height:23px;font-weight:650">{html.escape(item['Başlık'])}</div>
        <a href="{html.escape(item['Link'], quote=True)}" style="display:inline-block;margin-top:12px;color:#0071e3;text-decoration:none;font-size:14px;font-weight:600">Duyuruyu görüntüle →</a></div>"""
        for item in items
    )


def has_important_word(item):
    return any(word in item["Başlık"].casefold() for word in IMPORTANT_WORDS)


def required(name):
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Eksik ortam değişkeni: {name}")
    return value


def send_email(subject, body):
    if os.getenv("EMAIL_ENABLED", "true").lower() != "true":
        logging.info("E-posta gönderimi kapalı")
        return
    sender = required("EMAIL_USER")
    recipients = [x.strip() for x in required("NOTIFICATION_EMAIL").split(",") if x.strip()]
    msg = MIMEText(body, "html", "utf-8")
    msg["Subject"], msg["From"], msg["To"] = subject, sender, ", ".join(recipients)
    with smtplib.SMTP(os.getenv("SMTP_SERVER", "smtp.gmail.com"), int(os.getenv("SMTP_PORT", "587"))) as server:
        server.starttls()
        server.login(sender, required("EMAIL_PASSWORD"))
        server.sendmail(sender, recipients, msg.as_string())


def telegram_text(items):
    lines = ["📣 Maltepe Üniversitesi Yeni Duyurular", datetime.now().strftime("🕒 %d.%m.%Y %H:%M"), "", f"Toplam {len(items)} yeni duyuru:"]
    for index, item in enumerate(items, 1):
        lines.extend(["", f"{index}. {item['Başlık']}", f"🔗 {item['Link']}"])
    return "\n".join(lines)


def send_telegram(text):
    token, chat_id = os.getenv("TELEGRAM_TOKEN", "").strip(), os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        logging.info("Telegram ayarları yok; bildirim atlandı")
        return
    chunks, current = [], ""
    for line in text.splitlines(keepends=True):
        if len(current) + len(line) > 3800 and current:
            chunks.append(current.rstrip())
            current = ""
        current += line
    if current:
        chunks.append(current.rstrip())
    for chunk in chunks:
        response = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": chunk, "disable_web_page_preview": True}, timeout=30)
        if not response.ok:
            try:
                detail = response.json().get("description") or response.text
            except ValueError:
                detail = response.text
            raise RuntimeError(f"Telegram API {response.status_code}: {detail[:500]}")


def test_email():
    body = email_shell("Sistem Kontrolü", "Duyuru sistemi hazır.", "GitHub Actions ve e-posta bağlantınız sorunsuz çalışıyor.", f"""<div style="margin-top:28px;padding:22px;border-radius:18px;background:#f5f5f7"><b>Test başarıyla tamamlandı</b><div style="margin-top:7px;font-size:13px;color:#6e6e73">{datetime.now().strftime('%d.%m.%Y %H:%M')} · Duyuru listesi değiştirilmedi</div></div>""", "#30a14e")
    send_email("MAU Duyuru Sistemi Testi Başarılı", body)


def main():
    setup_logging()
    try:
        if os.getenv("SEND_TEST_EMAIL", "").lower() == "true":
            test_email()
            return 0
        previous = load_state()
        current = parse_announcements(fetch_html())
        previous_links = {normalize_url(row.get("Link", "")) for row in previous}
        new_items = [item for item in current if normalize_url(item["Link"]) not in previous_links]
        if not previous:
            save_state(current, [])
            logging.info("İlk çalışma: %d duyuru başlangıç listesi olarak kaydedildi", len(current))
            return 0
        if new_items:
            logging.info("%d yeni duyuru bulundu", len(new_items))
            for item in new_items:
                logging.info("Yeni duyuru: %s", item["Başlık"])
            try:
                send_telegram(telegram_text(new_items))
            except Exception as telegram_error:
                logging.error("Telegram bildirimi gönderilemedi: %s", telegram_error)
            important = [item for item in new_items if has_important_word(item)]
            accent = "#ff3b30" if important else "#0071e3"
            eyebrow = "Önemli Duyuru" if important else "Yeni Duyuru"
            title = f"{len(new_items)} yeni duyuru bulundu."
            subtitle = datetime.now().strftime("%d.%m.%Y %H:%M itibarıyla CSV listesinde olmayan yeni kayıtlar.")
            body = email_shell(eyebrow, title, subtitle, announcement_cards(new_items), accent)
            try:
                send_email("Maltepe Üniversitesi Yeni Duyuru", body)
            except Exception as email_error:
                logging.error("E-posta bildirimi gönderilemedi: %s", email_error)
        else:
            logging.info("Yeni duyuru yok")
        save_state(current, previous)
        logging.info("%d güncel, %d yeni duyuru işlendi", len(current), len(new_items))
        return 0
    except Exception as exc:
        logging.exception("Duyuru kontrolü başarısız: %s", exc)
        try:
            send_telegram("⚠️ MAU Duyuru sistemi hata verdi:\n" + str(exc))
        except Exception:
            logging.exception("Telegram hata bildirimi gönderilemedi")
        return 1


if __name__ == "__main__":
    sys.exit(main())
