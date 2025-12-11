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
#  CLOUDFLARE R2 AYARLARI (Senin Düzelttiğin Hali)
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
def fetch_image(url):
    try:
        r = requests.get(url, verify=False, timeout=10)
        r.raise_for_status()
        return Image.open(BytesIO(r.content)).convert("RGB")