#!/usr/bin/env python3
"""
Code cleanup checker — detects dead code, unused imports, and stale dependencies.

Usage:
    python scripts/cleanup_check.py --check        # Report only
    python scripts/cleanup_check.py --fix          # Auto-fix safe issues (imports)
    python scripts/cleanup_check.py --aggressive   # Remove detected dead code
"""
import argparse
import ast
import os
import sys
from pathlib import Path


def find_python_files(root: Path) -> list[Path]:
    """Find all Python files in app/, excluding __pycache__."""
    return [
        p for p in root.rglob("*.py")
        if "__pycache__" not in str(p) and ".venv" not in str(p)
    ]


def check_unused_imports(filepath: Path) -> list[str]:
    """Detect unused imports in a Python file (simple heuristic)."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    try:
        tree = ast.parse(content, filename=str(filepath))
    except SyntaxError:
        return []

    # Collect imported names
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imports.add(alias.asname or alias.name)

    # Collect used names (simple: any Name or Attribute reference)
    used = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Attribute):
            # e.g., np.array → "np"
            if isinstance(node.value, ast.Name):
                used.add(node.value.id)

    unused = imports - used
    return sorted(unused)


def check_dead_functions(filepath: Path) -> list[str]:
    """Detect functions that are defined but never called (simple heuristic)."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    try:
        tree = ast.parse(content, filename=str(filepath))
    except SyntaxError:
        return []

    # Collect function definitions
    defined_funcs = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if not node.name.startswith("_"):  # skip private/magic methods
                defined_funcs.add(node.name)

    # Collect function calls
    called_funcs = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                called_funcs.add(node.func.id)

    uncalled = defined_funcs - called_funcs
    return sorted(uncalled)


def audit_dependencies() -> dict:
    """Check which dependencies in requirements.txt are actually imported."""
    req_file = Path("requirements.txt")
    if not req_file.exists():
        return {"error": "requirements.txt not found"}

    # Parse requirements
    with open(req_file, "r") as f:
        lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    required_packages = set()
    for line in lines:
        pkg = line.split(">=")[0].split("==")[0].split("[")[0].strip()
        required_packages.add(pkg.lower().replace("-", "_"))

    # Collect imports from all Python files
    imported = set()
    for py_file in find_python_files(Path("app")):
        with open(py_file, "r", encoding="utf-8") as f:
            try:
                tree = ast.parse(f.read(), filename=str(py_file))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            imported.add(alias.name.split(".")[0])
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            imported.add(node.module.split(".")[0])
            except SyntaxError:
                pass

    # Map common package names
    PACKAGE_MAP = {
        "jose": "python_jose",
        "dotenv": "python_dotenv",
        "multipart": "python_multipart",
        "pydantic_settings": "pydantic_settings",
        "sqlalchemy": "sqlalchemy",
        "fastapi": "fastapi",
        "uvicorn": "uvicorn",
    }

    imported_normalized = {PACKAGE_MAP.get(pkg, pkg) for pkg in imported}

    potentially_unused = required_packages - imported_normalized

    return {
        "required": sorted(required_packages),
        "imported": sorted(imported_normalized),
        "potentially_unused": sorted(potentially_unused),
    }


def main():
    parser = argparse.ArgumentParser(description="Code cleanup checker")
    parser.add_argument("--check", action="store_true", help="Report issues only")
    parser.add_argument("--fix", action="store_true", help="Auto-fix safe issues")
    parser.add_argument("--aggressive", action="store_true", help="Remove dead code")
    args = parser.parse_args()

    if not any([args.check, args.fix, args.aggressive]):
        args.check = True  # default

    print("=== Kafil Music Cleanup Check ===\n")

    # 1. Unused imports
    print("[1] Checking for unused imports...")
    py_files = find_python_files(Path("app"))
    total_unused = 0
    for filepath in py_files:
        unused = check_unused_imports(filepath)
        if unused:
            print(f"  {filepath}: {', '.join(unused)}")
            total_unused += len(unused)

    if total_unused == 0:
        print("  ✓ No unused imports detected")
    else:
        print(f"  ⚠ Found {total_unused} potentially unused imports")

    # 2. Dead functions
    print("\n[2] Checking for uncalled functions...")
    total_dead = 0
    for filepath in py_files:
        dead = check_dead_functions(filepath)
        if dead:
            print(f"  {filepath}: {', '.join(dead)}")
            total_dead += len(dead)

    if total_dead == 0:
        print("  ✓ No obviously dead functions detected")
    else:
        print(f"  ⚠ Found {total_dead} functions defined but not called in same file")
        print("    (May be exported/used elsewhere — verify before removing)")

    # 3. Dependency audit
    print("\n[3] Auditing dependencies...")
    dep_report = audit_dependencies()
    if "error" in dep_report:
        print(f"  ✗ {dep_report['error']}")
    else:
        if dep_report["potentially_unused"]:
            print("  ⚠ Potentially unused dependencies:")
            for pkg in dep_report["potentially_unused"]:
                print(f"    - {pkg}")
        else:
            print("  ✓ All dependencies appear to be imported")

    print("\n=== Summary ===")
    print(f"Unused imports: {total_unused}")
    print(f"Potentially dead functions: {total_dead}")
    print(f"Potentially unused deps: {len(dep_report.get('potentially_unused', []))}")

    if args.fix:
        print("\n⚠ --fix not yet implemented (would use autoflake/ruff)")
    if args.aggressive:
        print("\n⚠ --aggressive not yet implemented (manual review recommended)")


if __name__ == "__main__":
    main()
