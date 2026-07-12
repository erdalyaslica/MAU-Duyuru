# MAU Duyuru Takip

Maltepe Üniversitesi duyuru sayfasını düzenli kontrol eder. Yeni duyuruları `data/duyurular.csv` dosyasındaki kayıtlarla karşılaştırır; CSV'de olmayan kayıtları yeni kabul edip e-posta ve Telegram bildirimi göndermeyi dener.

## Klasör yapısı

- `src/mau_duyuru.py`: Ana takip scripti
- `data/duyurular.csv`: Takip edilen duyuru listesi
- `.github/workflows/duyuru-kontrol.yml`: Tek GitHub Actions workflow'u
- `requirements.txt`: Python bağımlılıkları

## GitHub Secrets

- `SCRAPEDO_TOKEN`
- `EMAIL_ENABLED`
- `SMTP_SERVER`
- `SMTP_PORT`
- `EMAIL_USER`
- `EMAIL_PASSWORD`
- `NOTIFICATION_EMAIL`
- `TELEGRAM_TOKEN`
- `TELEGRAM_CHAT_ID`

## Test

Actions sekmesinden `Maltepe Duyuru Kontrol` workflow'u `master` branch üzerinde manuel çalıştırılabilir. CSV'den bir duyuru satırı silinip workflow tekrar çalıştırıldığında, o kayıt yeni duyuru gibi algılanır ve bildirim testi yapılabilir.
