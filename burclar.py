from fastapi import FastAPI
from fastapi.responses import JSONResponse
from PIL import Image, ImageDraw, ImageFont
import os
import requests
import datetime
from io import BytesIO
import urllib3
import time
urllib3.disable_warnings()
import boto3
from botocore.client import Config

R2_ACCESS_KEY = "b3be6f386ed30c55f201dd52bed49ce3"
R2_SECRET_KEY = "66b0328150576a04aca10be192bd72b3e0c449895bf657ae94aae80ccaf6233db"
R2_BUCKET = "burclar"
R2_ENDPOINT = "https://c316fd7fb9f1a40d8aa2578d27d579a2.r2.cloudflarestorage.com"

s3 = boto3.client(
    "s3",
    region_name="auto",
    endpoint_url=R2_ENDPOINT,
    aws_access_key_id=R2_ACCESS_KEY,
    aws_secret_access_key=R2_SECRET_KEY,
    config=Config(signature_version="s3v4")  
)


# -----------------------------------------------------
#  Cloudflare R2 Görsel İndirme
# -----------------------------------------------------
def fetch_image(url):
    try:
        r = requests.get(url, verify=False, timeout=10)
        r.raise_for_status()
        return Image.open(BytesIO(r.content)).convert("RGB")
    except Exception as e:
        print("❌ Görsel indirilemedi:", url, e)
        return Image.new("RGB", (WIDTH, HEIGHT), (255, 255, 255))

def upload_to_r2(filename):
    file_path = f"{OUTPUT_DIR}/{filename}"

    s3.upload_file(
        file_path,
        R2_BUCKET,
        filename
    )

    return f"{R2_ENDPOINT}/{R2_BUCKET}/{filename}"

# -----------------------------------------------------
#  GENEL AYARLAR
# -----------------------------------------------------
WIDTH = 1080
HEIGHT = 1350
FONT_PATH = "fonts/Arial.ttf"
FONT_TITLE = 120
FONT_BODY = 44

OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

BOTTOM_SAFE_MARGIN = 230   # Alt emoji alanı

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_MODEL = "llama-3.3-70b-versatile"

IMAGE_MAP = {
    1:"https://raw.githubusercontent.com/srknklmz/burc-gorselleri/main/1.jpg",
    2:"https://raw.githubusercontent.com/srknklmz/burc-gorselleri/main/2.jpg",
    3:"https://raw.githubusercontent.com/srknklmz/burc-gorselleri/main/3.jpg",
    4:"https://raw.githubusercontent.com/srknklmz/burc-gorselleri/main/4.jpg",
    5:"https://raw.githubusercontent.com/srknklmz/burc-gorselleri/main/5.jpg",
    6:"https://raw.githubusercontent.com/srknklmz/burc-gorselleri/main/6.jpg",
    7:"https://raw.githubusercontent.com/srknklmz/burc-gorselleri/main/7.jpg",
    8:"https://raw.githubusercontent.com/srknklmz/burc-gorselleri/main/8.jpg",
    9:"https://raw.githubusercontent.com/srknklmz/burc-gorselleri/main/9.jpg",
    10:"https://raw.githubusercontent.com/srknklmz/burc-gorselleri/main/10.jpg",
    11:"https://raw.githubusercontent.com/srknklmz/burc-gorselleri/main/11.jpg",
    12:"https://raw.githubusercontent.com/srknklmz/burc-gorselleri/main/12.jpg",
    13:"https://raw.githubusercontent.com/srknklmz/burc-gorselleri/main/13.jpg"
}

burc_listesi = [
    "Koç","Boğa","İkizler","Yengeç","Aslan","Başak",
    "Terazi","Akrep","Yay","Oğlak","Kova","Balık"
]


# -----------------------------------------------------
#  METİN PARÇALAMA
# -----------------------------------------------------
def wrap_lines(draw, text, font, max_width):
    lines = []
    for paragraph in text.split("\n"):
        words = paragraph.split()
        if not words:
            lines.append("")
            continue

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
#  BAŞLIK + JUSTIFY METİN
# -----------------------------------------------------
def draw_justified_page(img, burc, text):
    draw = ImageDraw.Draw(img)

    font_title = ImageFont.truetype(FONT_PATH, FONT_TITLE)
    body_size = FONT_BODY

    left_margin = 80
    right_margin = 80
    max_width = WIDTH - left_margin - right_margin

    bottom_limit = HEIGHT - BOTTOM_SAFE_MARGIN
    spacing = 14

    while True:
        font_body = ImageFont.truetype(FONT_PATH, body_size)
        lines = wrap_lines(draw, text, font_body, max_width)

        tbox = draw.textbbox((0, 0), burc, font=font_title)
        title_h = tbox[3] - tbox[1]

        sample = draw.textbbox((0, 0), "Hg", font=font_body)
        line_h = sample[3] - sample[1]

        text_height = len(lines) * (line_h + spacing)
        title_gap = 2 * line_h
        block_height = title_h + title_gap + text_height

        center_y = bottom_limit / 2
        top_y = center_y - block_height / 2

        if top_y < 80:
            top_y = 80
        if top_y + block_height <= bottom_limit or body_size <= 34:
            break

        body_size -= 2

    title_w = draw.textlength(burc, font=font_title)
    tx = (WIDTH - title_w) // 2
    ty = top_y
    draw.text((tx, ty), burc, font=font_title, fill="black")

    y = ty + title_h + title_gap
    for idx, line in enumerate(lines):
        words = line.split()
        is_last = idx == len(lines) - 1
        if len(words) > 1 and not is_last:
            space_w = draw.textlength(" ", font=font_body)
            base = sum(draw.textlength(w, font=font_body) for w in words) + space_w * (len(words)-1)
            extra = max_width - base
            gaps = len(words)-1
            x = left_margin
            add_space = extra / gaps
            for i, w in enumerate(words):
                draw.text((x, y), w, font=font_body, fill="black")
                x += draw.textlength(w, font=font_body) + space_w + add_space
        else:
            draw.text((left_margin, y), line, font=font_body, fill="black")
        y += line_h + spacing


# -----------------------------------------------------
#  GROQ API
# -----------------------------------------------------
def groq_chat(prompt, temperature=0.4):
    url = "https://api.groq.com/openai/v1/chat/completions"
    payload = {
        "model": GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
    }
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}

    r = requests.post(url, json=payload, headers=headers)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def get_horoscope(burc):
    draft_prompt = f"""
Sen deneyimli bir astrologsun.

Bugün için **{burc} burcu** adına,
110–150 kelime arası, tek paragraf,
profesyonel ve tamamen Türkçe bir günlük burç yorumu yaz.
"""
    draft = groq_chat(draft_prompt, temperature=0.5).strip()

    clean_prompt = f"""
Aşağıdaki metni yalnızca Türkçe imla ve akıcılık açısından düzelt.

METİN:
{draft}
"""
    final_text = groq_chat(clean_prompt, temperature=0.1).strip()
    time.sleep(1)
    return final_text.replace('"""', '').replace("“", "").replace("”", "").strip()


# -----------------------------------------------------
#  TARİH
# -----------------------------------------------------
TURKISH_MONTHS = {
    "January":"Ocak","February":"Şubat","March":"Mart","April":"Nisan",
    "May":"Mayıs","June":"Haziran","July":"Temmuz","August":"Ağustos",
    "September":"Eylül","October":"Ekim","November":"Kasım","December":"Aralık"
}

def get_turkish_today():
    t = datetime.date.today().strftime("%d %B %Y")
    eng = t.split()[1]
    return t.replace(eng, TURKISH_MONTHS[eng])

TODAY_TR = get_turkish_today()


# -----------------------------------------------------
#  KAPAK
# -----------------------------------------------------
def create_cover():
    today = TODAY_TR
    img = fetch_image(IMAGE_MAP[1])
    draw = ImageDraw.Draw(img)

    title = "GÜNLÜK BURÇ YORUMLARI"
    safe_padding = 80
    max_width = WIDTH - safe_padding * 2

    size = 110
    while True:
        font_title = ImageFont.truetype(FONT_PATH, size)
        w_title = draw.textlength(title, font=font_title)
        if w_title <= max_width or size <= 60:
            break
        size -= 2

    y_title = 140
    x_title = (WIDTH - w_title) // 2

    for dx, dy in [(-1,0),(1,0),(0,-1),(0,1),(0,0)]:
        draw.text((x_title + dx, y_title + dy), title, font=font_title, fill="black")

    font_date = ImageFont.truetype(FONT_PATH, FONT_BODY)
    w_date = draw.textlength(today, font=font_date)
    x_date = (WIDTH - w_date) // 2
    y_date = y_title + 100

    draw.text((x_date, y_date), today, font=font_date, fill="black")
    img.save(f"{OUTPUT_DIR}/00_kapak.png")
    upload_to_r2("00_kapak.png")


# -----------------------------------------------------
#  Cloudflare R2 Yükleme Fonksiyonu
# -----------------------------------------------------
def upload_to_r2(filename):
    file_path = os.path.join(OUTPUT_DIR, filename)
    s3.upload_file(file_path, R2_BUCKET, filename)
    print("✓ Upload:", filename)


# -----------------------------------------------------
#  BURÇ SAYFALARI
# -----------------------------------------------------
def create_pages():
    for i, burc in enumerate(burc_listesi, start=1):
        img = fetch_image(IMAGE_MAP[i+1])
        yorum = get_horoscope(burc)

        draw_justified_page(img, burc, yorum)

        draw = ImageDraw.Draw(img)
        font_date = ImageFont.truetype(FONT_PATH, 32)
        margin = 80
        y_date = HEIGHT - margin - 40
        draw.text((margin, y_date), TODAY_TR, font=font_date, fill="black")

        filename = f"{i:02d}_{burc}.png"
        img.save(f"{OUTPUT_DIR}/{filename}")
        upload_to_r2(filename)


# -----------------------------------------------------
#  FASTAPI
# -----------------------------------------------------
app = FastAPI()

@app.get("/generate")
def generate_all():
    create_cover()
    create_pages()

    files = sorted(os.listdir(OUTPUT_DIR))

    return JSONResponse({
        "status": "ok",
        "date": TODAY_TR,
        "files": files
    })