#!/usr/bin/env python3
"""
عیب‌یابی عمیق اتصال ParsPack (S3).

برخلاف test_parspack.py که فقط head_bucket می‌زند (و 403 خام می‌دهد)، این اسکریپت:
  - طول کلیدها را چاپ می‌کند (برای کشف فاصله/newline پنهان)
  - list_buckets می‌زند تا اعتبار کلیدها و نام دقیق باکت‌ها را ببیند
  - ترکیب SigV4/SigV2 و path/virtual را امتحان می‌کند
  - از list_objects_v2 (به‌جای head_bucket) استفاده می‌کند چون کد خطای واقعی
    (SignatureDoesNotMatch / InvalidAccessKeyId / NoSuchBucket / AccessDenied)
    را در بدنه‌ی XML برمی‌گرداند

Usage:
    python -m scripts.diagnose_parspack
"""
import sys

from app.config import get_settings

settings = get_settings()


def _make_client(boto3, BotoConfig, sig, style, region):
    cfg = BotoConfig(
        region_name=region,
        signature_version=sig,
        s3={"addressing_style": style},
        retries={"max_attempts": 1},
    )
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        config=cfg,
    )


def _describe_error(e) -> str:
    """استخراج کامل‌ترین اطلاعات ممکن از خطای boto3."""
    resp = getattr(e, "response", {}) or {}
    err = resp.get("Error", {})
    meta = resp.get("ResponseMetadata", {})
    http = meta.get("HTTPStatusCode", "?")
    code = err.get("Code", type(e).__name__)
    msg = err.get("Message", str(e))
    return f"HTTP {http} | Code={code} | {msg}"


def main() -> int:
    print("=== عیب‌یابی اتصال ParsPack ===\n")

    # ---- 0) بررسی مقادیر .env ----
    ak = settings.s3_access_key
    sk = settings.s3_secret_key
    print("[تنظیمات]")
    print(f"  Endpoint : {settings.s3_endpoint_url}")
    print(f"  Bucket   : {settings.s3_bucket_name!r}")
    print(f"  Region   : {settings.s3_region}")
    print(f"  AccessKey: طول={len(ak)}  شروع={ak[:4]!r}  پایان={ak[-2:]!r}")
    print(f"  SecretKey: طول={len(sk)}  شروع={sk[:2]!r}  پایان={sk[-2:]!r}")
    if ak != ak.strip() or sk != sk.strip():
        print("  ⚠ هشدار: کلید فاصله/newline اضافه دارد! در .env اصلاح کنید.")
    print()

    try:
        import boto3
        from botocore.config import Config as BotoConfig
        from botocore.exceptions import ClientError
    except ImportError:
        print("✗ boto3 نصب نیست:  pip install boto3")
        return 1

    bucket = settings.s3_bucket_name

    # ---- 1) list_buckets با SigV4 (بهترین تست اعتبار کلید) ----
    print("[۱] list_buckets با SigV4 (path-style)...")
    client_v4 = _make_client(boto3, BotoConfig, "s3v4", "path", settings.s3_region or "us-east-1")
    creds_ok = False
    try:
        resp = client_v4.list_buckets()
        names = [b["Name"] for b in resp.get("Buckets", [])]
        print(f"      ✓ کلیدها معتبرند! باکت‌های موجود: {names or '(هیچ باکتی نیست)'}")
        creds_ok = True
        if bucket not in names and names:
            print(f"      ⚠ باکت «{bucket}» در لیست نیست — شاید نامش یکی از بالاست؟")
    except ClientError as e:
        print(f"      ✗ {_describe_error(e)}")
    except Exception as e:
        print(f"      ✗ {type(e).__name__}: {e}")
    print()

    # ---- 2) اگر SigV4 نشد، SigV2 را امتحان کن ----
    if not creds_ok:
        print("[۲] list_buckets با SigV2 (بعضی سرورهای قدیمی S3)...")
        client_v2 = _make_client(boto3, BotoConfig, "s3", "path", settings.s3_region or "us-east-1")
        try:
            resp = client_v2.list_buckets()
            names = [b["Name"] for b in resp.get("Buckets", [])]
            print(f"      ✓ با SigV2 کار کرد! باکت‌ها: {names}")
            print("      → راه‌حل: در app/services/storage.py مقدار signature_version را 's3' بگذارید.")
            creds_ok = True
        except ClientError as e:
            print(f"      ✗ {_describe_error(e)}")
        except Exception as e:
            print(f"      ✗ {type(e).__name__}: {e}")
        print()

    # ---- 3) دسترسی مستقیم به باکت با list_objects_v2 (کد خطای شفاف) ----
    print(f"[۳] list_objects_v2 روی باکت «{bucket}» (ترکیب‌های مختلف)...")
    combos = [
        ("s3v4", "path"),
        ("s3v4", "virtual"),
        ("s3", "path"),
    ]
    any_ok = False
    for sig, style in combos:
        client = _make_client(boto3, BotoConfig, sig, style, settings.s3_region or "us-east-1")
        try:
            client.list_objects_v2(Bucket=bucket, MaxKeys=1)
            print(f"      ✓ [{sig} / {style}-style] موفق — همین ترکیب را استفاده کنید")
            any_ok = True
        except ClientError as e:
            print(f"      ✗ [{sig} / {style}-style] {_describe_error(e)}")
        except Exception as e:
            print(f"      ✗ [{sig} / {style}-style] {type(e).__name__}: {e}")
    print()

    # ---- جمع‌بندی ----
    print("=" * 50)
    if any_ok:
        print("✓ حداقل یک ترکیب کار کرد — تنظیمات را مطابق آن ست کنید.")
        return 0
    print("راهنمای تفسیر کد خطا:")
    print("  • SignatureDoesNotMatch → Secret Key اشتباه است یا region/امضا نمی‌خواند")
    print("  • InvalidAccessKeyId    → Access Key اشتباه است")
    print("  • NoSuchBucket          → نام باکت غلط است (به لیست بالا نگاه کنید)")
    print("  • AccessDenied          → کلید معتبر است ولی مجوز این باکت را ندارد")
    return 1


if __name__ == "__main__":
    sys.exit(main())
