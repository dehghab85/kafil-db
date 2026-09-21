import os
from pathlib import Path
import boto3
from botocore.client import Config
from dotenv import load_dotenv

ENV_FILE = Path(__file__).with_name(".env")
load_dotenv(ENV_FILE, override=True)

endpoint = os.getenv("S3_ENDPOINT_URL")
access_key = os.getenv("S3_ACCESS_KEY")
secret_val = os.getenv("S3_SECRET_KEY")
bucket = os.getenv("S3_BUCKET_NAME")

print(f"Testing endpoint: {endpoint} | Bucket: {bucket}\n")

# حالت ۱: نسخه امضای ۲ (s3)
try:
    print("1. تست با signature_version='s3':")
    s3_v2 = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_val,
        config=Config(signature_version="s3", s3={"addressing_style": "path"}),
    )
    res = s3_v2.list_objects_v2(Bucket=bucket)
    print("✓ موفق بود! تعداد فایل‌ها:", res.get("KeyCount", 0))
except Exception as e:
    print("✗ خطا:", e)

# حالت ۲: نسخه امضای ۴ با ریجن us-east-1
try:
    print("\n2. تست با signature_version='s3v4' و region_name='us-east-1':")
    s3_v4 = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_val,
        region_name="us-east-1",
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )
    res = s3_v4.list_objects_v2(Bucket=bucket)
    print("✓ موفق بود! تعداد فایل‌ها:", res.get("KeyCount", 0))
except Exception as e:
    print("✗ خطا:", e)

# حالت ۳: تست دریافت لیست باکت‌ها
try:
    print("\n3. تست list_buckets با امضای s3:")
    s3_lb = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_val,
        config=Config(signature_version="s3", s3={"addressing_style": "path"}),
    )
    buckets = s3_lb.list_buckets()
    print("✓ باکت‌های شما:")
    for b in buckets.get("Buckets", []):
        print(f" - {b['Name']}")
except Exception as e:
    print("✗ خطا:", e)


import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"), override=True)

ak = os.getenv("S3_ACCESS_KEY", "")
sk = os.getenv("S3_SECRET_KEY", "")

print(f"Access Key: طول={len(ak)} | شروع={ak[:3]}... | پایان=...{ak[-3:]}")
print(f"Secret Key: طول={len(sk)} | شروع={sk[:3]}... | پایان=...{sk[-3:]}")
print(f"فاصله مخفی دارد؟ Access: {' ' in ak} | Secret: {' ' in sk}")

