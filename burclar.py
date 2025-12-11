from fastapi import FastAPI
from fastapi.responses import JSONResponse
from PIL import Image, ImageDraw, ImageFont
import os
import requests
import datetime
from io import BytesIO
import urllib3
import time
import boto3
from botocore.client import Config
from threading import Thread

urllib3.disable_warnings()

app = FastAPI()

# -----------------------------------------------------
#  GENEL AYARLAR
# -----------------------------------------------------
WIDTH = 1080
HEIGHT = 1350
FONT_PATH = "fonts/Arial.ttf"  # Font dosyanın burada olduğundan emin ol

# Yazı boyutlarını biraz küçülttük ki sığsın
FONT_TITLE = 80  
FONT_BODY = 36   

OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_MODEL = "llama-3.3-70b-versatile"

# Görseller (Linkleri aynen koruyoruz)
IMAGE_MAP = {
    1: "https://raw.githubusercontent.com/srknklmz/burc-gorselleri/main/1.jpg",
    2: "https://raw.githubusercontent.com/srknklmz/burc-gorselleri/main/2.jpg",
    3: "https://raw.githubusercontent.com/srknklmz/burc-gorselleri/main/3.jpg",
    4: "https://raw.githubusercontent.com/srknklmz/burc-gorselleri/main/4.jpg",
    5: "https://raw.githubusercontent.com/srknklmz/burc-gorselleri/main/5.jpg",
    6: "https://raw.githubusercontent.com/srknklmz/burc-gorselleri/main/6.jpg",
    7: "https://raw.githubusercontent.com/srknklmz/burc-gorselleri/main/7.jpg",
    8: "https://raw.githubusercontent.com/srknklmz/burc-gorselleri/main/8.jpg",
    9: "https://raw.githubusercontent.com/srknklmz/burc-gorselleri/main/9.jpg",
    10: "https://raw.githubusercontent.com/srknklmz/burc-gorselleri/main/10.jpg",
    11: "https://raw.githubusercontent.com/srknklmz/burc-gorselleri/main/11.jpg",
    12: "https://raw.githubusercontent.com/srknklmz/burc-gorselleri/main/12.jpg",
    13: "https://raw.githubusercontent.com/srknklmz/burc-gorselleri/main/13.jpg",
}

burc_listesi = [
    "Koç", "Boğa", "İkizler", "Yengeç", "Aslan", "Başak",
    "Terazi", "Akrep", "Yay", "Oğlak", "Kova", "Balık"
]

# -----------------------------------------------------
#  CLOUDFLARE R2 AYARLARI
# -----------------------------------------------------
R2_ACCESS_KEY = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
R2_BUCKET = os.getenv("R2_BUCKET_NAME")
R2_ENDPOINT = os.getenv("R2_ENDPOINT_URL")
R2_REGION = os.getenv("R2_REGION", "auto")

# Bağlantı Kurma
try:
    s3 = boto3.client(
        "s3",
        region_name=R2_REGION,
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY,
        aws_secret_access_key=R2_SECRET_KEY,
        config=Config(signature_version="s3v4")
    )
    print("✅ R2 Bağlantısı Hazır.")
except Exception as e:
    print(f"❌ R2 Bağlantı Hatası: {e}")

def upload_to_r2(filename):
    file_path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(file_path):
        return

    try:
        s3.upload_file(
            Filename=file_path,
            Bucket=R2_BUCKET,
            Key=filename,
            ExtraArgs={'ContentType': 'image/png'}
        )
        print(f"🚀 Yüklendi: {filename}")
    except Exception as e:
        print(f"❌ Upload Hatası ({filename}): {e}")

# -----------------------------------------------------
#  YARDIMCI FONKSİYONLAR
# -----------------------------------------------------

# 👇 HATA BURADAYDI, DÜZELTİLDİ 👇
def fetch_image(url):
    try:
        r = requests.get(url, verify=False, timeout=10)
        r.raise_for_status()
        return Image.open(BytesIO(r.content)).convert("RGB")
    except Exception as e:
        print(f"Resim indirilemedi: {e}")
        # Hata durumunda beyaz boş resim dön
        return Image.new("RGB", (WIDTH, HEIGHT), (255, 255, 255))

def wrap_lines(draw, text, font, max_width):
    lines = []
    for paragraph in text.split("\n"):
        words = paragraph.split()
        if not words: continue
        line = words[0]
        for word in words[1:]:
            test = line + " " + word
            if draw.textlength(test, font=font) <= max_width:
                line = test
            else:
                lines.append(line)
                line = word
        lines.append(line)
    return lines

# -----------------------------------------------------
#  TEK BİR BURÇ BLOĞUNU ÇİZEN FONKSİYON (Yarım Sayfa)
# -----------------------------------------------------
def draw_block(draw, burc, text, center_y, max_h_limit):
    """
    draw: ImageDraw objesi
    burc: Burç Adı (Başlık)
    text: Yorum metni
    center_y: Bloğun dikey olarak ortalanacağı nokta (Y ekseni)
    max_h_limit: Metnin sığması gereken maksimum yükseklik
    """
    
    font_title = ImageFont.truetype(FONT_PATH, FONT_TITLE)
    body_size = FONT_BODY
    
    left_margin = 80
    right_margin = 80
    max_width = WIDTH - left_margin - right_margin
    spacing = 10
    
    # Font boyutunu metin sığana kadar küçültme mantığı
    while True:
        font_body = ImageFont.truetype(FONT_PATH, body_size)
        lines = wrap_lines(draw, text, font_body, max_width)
        
        # Başlık Yüksekliği
        tbox = draw.textbbox((0, 0), burc, font=font_title)
        title_h = tbox[3] - tbox[1]
        
        # Satır Yüksekliği
        sample = draw.textbbox((0, 0), "Hg", font=font_body)
        line_h = sample[3] - sample[1]
        
        text_height = len(lines) * (line_h + spacing)
        title_gap = line_h * 0.8
        
        total_block_height = title_h + title_gap + text_height
        
        # Eğer sığıyorsa veya font çok küçüldüyse döngüyü kır
        if total_block_height <= max_h_limit or body_size <= 24:
            break
        
        body_size -= 2 # Sığmazsa fontu küçült ve tekrar dene

    # Çizim Başlangıç Y Koordinatı (Ortalamak için)
    start_y = center_y - (total_block_height / 2)
    
    # 1. Başlığı Çiz
    title_w = draw.textlength(burc, font=font_title)
    tx = (WIDTH - title_w) // 2
    ty = start_y
    draw.text((tx, ty), burc, font=font_title, fill="black")
    
    # 2. Metni Çiz
    current_y = ty + title_h + title_gap
    for line in lines:
        # Ortalayarak yazalım
        w_line = draw.textlength(line, font=font_body)
        lx = (WIDTH - w_line) // 2 
        draw.text((lx, current_y), line, font=font_body, fill="black")
             
        current_y += line_h + spacing

# -----------------------------------------------------
#  GROQ / YORUM ALMA
# -----------------------------------------------------
def groq_chat(prompt, temperature=0.4):
    url = "https://api.groq.com/openai/v1/chat/completions"
    payload = {
        "model": GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
    }
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
    try:
        r = requests.post(url, json=payload, headers=headers)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print("Groq Error:", e)
        return "Yorum alınamadı."

def get_horoscope(burc):
    # Kelime sayısını biraz azalttık ki 2 burç sığsın (80-100 kelime ideal)
    prompt = f"""
    Sen bir astrologsun. Bugün için **{burc} burcu** adına,
    maksimum 70-90 kelimelik, tek paragraf, motive edici 
    ve Türkçe bir günlük yorum yaz.
    """
    return groq_chat(prompt, 0.5).replace('"', '').strip()

# -----------------------------------------------------
#  SAYFA OLUŞTURUCULAR
# -----------------------------------------------------
TURKISH_MONTHS = {
    "January": "Ocak", "February": "Şubat", "March": "Mart", "April": "Nisan",
    "May": "Mayıs", "June": "Haziran", "July": "Temmuz", "August": "Ağustos",
    "September": "Eylül", "October": "Ekim", "November": "Kasım", "December": "Aralık"
}

def get_turkish_today():
    t = datetime.date.today().strftime("%d %B %Y")
    eng = t.split()[1]
    return t.replace(eng, TURKISH_MONTHS[eng])

TODAY_TR = get_turkish_today()

def create_cover():
    today = TODAY_TR
    img = fetch_image(IMAGE_MAP[1])
    draw = ImageDraw.Draw(img)
    
    # Biraz karartma efekti (yazı okunsun diye)
    overlay = Image.new('RGBA', img.size, (255, 255, 255, 180))
    img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')
    draw = ImageDraw.Draw(img)

    title = "GÜNLÜK\nBURÇ YORUMLARI"
    font_title = ImageFont.truetype(FONT_PATH, 100)
    
    # Çoklu satır ortalama
    w = draw.multiline_textbbox((0,0), title, font=font_title)[2]
    h = draw.multiline_textbbox((0,0), title, font=font_title)[3]
    
    x = (WIDTH - w) // 2
    y = (HEIGHT - h) // 2 - 50
    
    draw.multiline_text((x, y), title, font=font_title, fill="black", align="center")

    font_date = ImageFont.truetype(FONT_PATH, 40)
    w_date = draw.textlength(today, font=font_date)
    draw.text(((WIDTH - w_date) // 2, y + h + 40), today, font=font_date, fill="black")
    
    img.save(f"{OUTPUT_DIR}/00_kapak.png")
    upload_to_r2("00_kapak.png")

def create_split_pages():
    # Burçları 2'şerli gruplar halinde geziyoruz (0-1, 2-3, ...)
    for i in range(0, len(burc_listesi), 2):
        burc1 = burc_listesi[i]
        burc2 = burc_listesi[i+1]
        
        # Arka plan olarak ilk burcun görselini kullan (Örn: Koç görseli)
        img = fetch_image(IMAGE_MAP[i + 2]) 
        
        # Resmi biraz beyazlat ki yazılar okunsun
        overlay = Image.new('RGBA', img.size, (255, 255, 255, 200))
        img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')
        draw = ImageDraw.Draw(img)
        
        # Yorumları Al
        yorum1 = get_horoscope(burc1)
        yorum2 = get_horoscope(burc2)
        
        # --- ÜST BLOK (Burç 1) ---
        draw_block(draw, burc1, yorum1, center_y=350, max_h_limit=550)
        
        # --- AYIRICI ÇİZGİ ---
        draw.line([(100, HEIGHT/2), (WIDTH-100, HEIGHT/2)], fill="black", width=3)
        
        # --- ALT BLOK (Burç 2) ---
        draw_block(draw, burc2, yorum2, center_y=1000, max_h_limit=550)
        
        # Tarih (En alta ufakça)
        font_date = ImageFont.truetype(FONT_PATH, 24)
        draw.text((40, HEIGHT - 40), TODAY_TR, font=font_date, fill="gray")
        
        # Kaydet
        safe_burc1 = burc1.replace("ç","c").replace("ğ","g").replace("ş","s").replace("ı","i").replace("ö","o").replace("ü","u")
        safe_burc2 = burc2.replace("ç","c").replace("ğ","g").replace("ş","s").replace("ı","i").replace("ö","o").replace("ü","u")
        
        filename = f"{ (i//2) + 1:02d}_{safe_burc1}_{safe_burc2}.png"
        img.save(f"{OUTPUT_DIR}/{filename}")
        upload_to_r2(filename)

# -----------------------------------------------------
#  ENDPOINTLER
# -----------------------------------------------------
@app.get("/generate-fast")
def generate_fast():
    def background_job():
        create_cover()
        create_split_pages() 
        
    Thread(target=background_job).start()
    return {"status": "started", "mode": "split_view"}

@app.get("/")
def home():
    return {"status": "active"}