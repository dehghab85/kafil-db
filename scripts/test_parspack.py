#!/usr/bin/env python3
"""
تست اتصال به فضای ابری ParsPack (S3-compatible).

این اسکریپت به‌صورت end-to-end بررسی می‌کند:
  1) اتصال و احراز هویت با endpoint پارس‌پک
  2) وجود باکت (bucket) و دسترسی به آن
  3) آپلود یک فایل تست کوچک
  4) دانلود همان فایل و مقایسه‌ی محتوا
  5) ساخت URL عمومی
  6) حذف فایل تست

Usage:
    python scripts/test_parspack.py
"""
import sys
import time

from app.config import get_settings

settings = get_settings()


def main() -> int:
    print("=== تست اتصال ParsPack (S3) ===\n")

    if not settings.s3_enabled:
        print("✗ S3 غیرفعال است. در .env مقدار S3_ENABLED=true بگذارید.")
        return 1

    print(f"Endpoint : {settings.s3_endpoint_url}")
    print(f"Bucket   : {settings.s3_bucket_name}")
    print(f"Region   : {settings.s3_region}")
    print(f"PathStyle: {settings.s3_path_style}")
    print(f"AccessKey: {settings.s3_access_key[:4]}***\n")

    try:
        import boto3
        from botocore.config import Config as BotoConfig
        from botocore.exceptions import ClientError
    except ImportError:
        print("✗ boto3 نصب نیست. اجرا کنید:  pip install boto3")
        return 1

    boto_config = BotoConfig(
        region_name=settings.s3_region or "us-east-1",
        signature_version="s3v4",
        s3={"addressing_style": "path" if settings.s3_path_style else "virtual"},
    )
    client = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        config=boto_config,
    )

    # ---- 1) بررسی دسترسی به باکت ----
    print("[1/5] بررسی وجود باکت...")
    try:
        client.head_bucket(Bucket=settings.s3_bucket_name)
        print("      ✓ باکت در دسترس است\n")
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "?")
        if code in ("404", "NoSuchBucket"):
            print(f"      ✗ باکت «{settings.s3_bucket_name}» وجود ندارد.")
            print("        از پنل پارس‌پک یک باکت با همین نام بسازید،")
            print("        یا S3_BUCKET_NAME را به نام باکت موجود تغییر دهید.\n")
        elif code in ("403", "AccessDenied", "SignatureDoesNotMatch", "InvalidAccessKeyId"):
            print(f"      ✗ خطای احراز هویت ({code}).")
            print("        Access Key / Secret Key را در .env بررسی کنید.\n")
        else:
            print(f"      ✗ خطا: {code} — {e}\n")
        return 1

    # ---- 2) آپلود فایل تست ----
    test_key = f"_healthcheck/test_{int(time.time())}.txt"
    test_body = b"Kafil Music ParsPack connectivity test - OK"
    print(f"[2/5] آپلود فایل تست: {test_key} ...")
    try:
        client.put_object(
            Bucket=settings.s3_bucket_name,
            Key=test_key,
            Body=test_body,
            ContentType="text/plain",
            ACL="public-read",
        )
        print("      ✓ آپلود موفق\n")
    except ClientError as e:
        print(f"      ✗ آپلود ناموفق: {e}\n")
        return 1

    # ---- 3) دانلود و مقایسه ----
    print("[3/5] دانلود و بررسی محتوا...")
    try:
        obj = client.get_object(Bucket=settings.s3_bucket_name, Key=test_key)
        downloaded = obj["Body"].read()
        if downloaded == test_body:
            print("      ✓ محتوای دانلودشده مطابق است\n")
        else:
            print("      ✗ محتوا مطابقت ندارد!\n")
            return 1
    except ClientError as e:
        print(f"      ✗ دانلود ناموفق: {e}\n")
        return 1

    # ---- 4) URL عمومی ----
    public_url = f"{settings.s3_endpoint_url.rstrip('/')}/{settings.s3_bucket_name}/{test_key}"
    print("[4/5] URL عمومی فایل:")
    print(f"      {public_url}\n")

    # ---- 5) حذف فایل تست ----
    print("[5/5] حذف فایل تست...")
    try:
        client.delete_object(Bucket=settings.s3_bucket_name, Key=test_key)
        print("      ✓ حذف شد\n")
    except ClientError as e:
        print(f"      ⚠ حذف ناموفق (مهم نیست): {e}\n")

    print("=" * 40)
    print("✓ همه‌چیز درست کار می‌کند! اتصال ParsPack سالم است.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
