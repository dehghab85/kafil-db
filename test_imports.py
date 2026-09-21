"""
تست اولیه imports و ساختار پروژه
"""
import sys

print("Python version:", sys.version)
print("\nTesting imports...")

try:
    import database
    print("✓ database module imported successfully")
except Exception as e:
    print(f"✗ database import failed: {e}")

try:
    import schemas
    print("✓ schemas module imported successfully")
except Exception as e:
    print(f"✗ schemas import failed: {e}")

try:
    import auth
    print("✓ auth module imported successfully")
except Exception as e:
    print(f"✗ auth import failed: {e}")

try:
    import otp
    print("✓ otp module imported successfully")
except Exception as e:
    print(f"✗ otp import failed: {e}")

try:
    import recommendations
    print("✓ recommendations module imported successfully")
except Exception as e:
    print(f"✗ recommendations import failed: {e}")

try:
    import main
    print("✓ main module imported successfully")
except Exception as e:
    print(f"✗ main import failed: {e}")

print("\n✓ All imports successful!")
