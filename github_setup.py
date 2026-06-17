"""
GitHub Auto Setup
- ตรวจสอบ/ติดตั้ง GitHub CLI (gh)
- Login GitHub
- สร้าง private repository
- Push โค้ดทั้งหมด
- ตั้ง Secrets จาก .env อัตโนมัติ
รัน: python github_setup.py
"""
import os
import sys
import io
import subprocess
import shutil
import webbrowser
import time
from pathlib import Path
from dotenv import load_dotenv

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

load_dotenv()

G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"
B = "\033[94m"; C = "\033[96m"; W = "\033[97m"
BOLD = "\033[1m"; DIM = "\033[2m"; X = "\033[0m"

REPO_NAME = "auto-social-poster"
PROJECT_DIR = Path(__file__).parent


def run(cmd: list, check=True, capture=False) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, check=check,
        capture_output=capture, text=True,
        cwd=PROJECT_DIR,
    )


def run_out(cmd: list) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_DIR)
    return r.stdout.strip()


def ok(m): print(f"  {G}✓ {m}{X}")
def err(m): print(f"  {R}✗ {m}{X}")
def info(m): print(f"  {C}→ {m}{X}")
def warn(m): print(f"  {Y}! {m}{X}")
def step(n, t): print(f"\n{B}{BOLD}[{n}] {t}{X}\n  {'─'*44}")


def check_gh_installed() -> bool:
    return shutil.which("gh") is not None


def install_gh_windows():
    info("กำลังติดตั้ง GitHub CLI ผ่าน winget...")
    try:
        run(["winget", "install", "--id", "GitHub.cli", "-e", "--silent"])
        ok("GitHub CLI ติดตั้งแล้ว")
        warn("กรุณา restart PowerShell/Terminal แล้วรัน script นี้ใหม่")
        sys.exit(0)
    except Exception:
        warn("winget ไม่ได้ติดตั้ง กำลังเปิดหน้าดาวน์โหลด...")
        webbrowser.open("https://github.com/cli/cli/releases/latest")
        print(f"""
  {W}ดาวน์โหลด:{X} gh_*_windows_amd64.msi
  ติดตั้งแล้วรัน script นี้ใหม่
""")
        sys.exit(1)


def gh_login():
    status = run_out(["gh", "auth", "status"])
    if "Logged in" in status or "logged in" in status:
        username = run_out(["gh", "api", "user", "--jq", ".login"])
        ok(f"Login แล้วในฐานะ: {username}")
        return username

    info("เปิดเบราว์เซอร์เพื่อ login GitHub...")
    time.sleep(1)
    run(["gh", "auth", "login", "--web", "--git-protocol", "https"])
    username = run_out(["gh", "api", "user", "--jq", ".login"])
    ok(f"Login สำเร็จ: {username}")
    return username


def repo_exists() -> bool:
    r = subprocess.run(
        ["gh", "repo", "view", REPO_NAME],
        capture_output=True, text=True, cwd=PROJECT_DIR
    )
    return r.returncode == 0


def create_repo():
    if repo_exists():
        warn(f"Repository '{REPO_NAME}' มีอยู่แล้ว")
        return
    info(f"สร้าง private repository: {REPO_NAME}")
    run([
        "gh", "repo", "create", REPO_NAME,
        "--private",
        "--description", "Auto Social Media Poster — AI content generator",
    ])
    ok(f"Repository สร้างแล้ว: github.com/[you]/{REPO_NAME}")


def init_git():
    git_dir = PROJECT_DIR / ".git"
    if not git_dir.exists():
        run(["git", "init"])
        run(["git", "branch", "-M", "main"])
        ok("Git initialized")

    gitignore = PROJECT_DIR / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(
            ".env\n__pycache__/\n*.pyc\npost_logs/\nauto_poster.log\n*.log\n",
            encoding="utf-8"
        )
        ok(".gitignore สร้างแล้ว (ซ่อน .env)")

    run(["git", "add", "-A"])
    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=PROJECT_DIR
    )
    if result.returncode != 0:
        run(["git", "commit", "-m", "Initial: Auto Social Media Poster setup"])
        ok("Git commit สร้างแล้ว")
    else:
        info("ไม่มีการเปลี่ยนแปลงใหม่ในโค้ด")


def set_remote(username: str):
    remotes = run_out(["git", "remote"])
    remote_url = f"https://github.com/{username}/{REPO_NAME}.git"

    if "origin" in remotes:
        run(["git", "remote", "set-url", "origin", remote_url])
    else:
        run(["git", "remote", "add", "origin", remote_url])
    ok(f"Remote: {remote_url}")


def push_code():
    info("Push โค้ดไปยัง GitHub...")
    run(["git", "push", "-u", "origin", "main"])
    ok("Push สำเร็จ!")


def set_secrets():
    info("ตั้งค่า GitHub Secrets จาก .env...")

    secrets = {
        "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY", ""),
        "FACEBOOK_PAGE_ID": os.getenv("FACEBOOK_PAGE_ID", ""),
        "FACEBOOK_ACCESS_TOKEN": os.getenv("FACEBOOK_ACCESS_TOKEN", ""),
        "LINE_CHANNEL_ACCESS_TOKEN": os.getenv("LINE_CHANNEL_ACCESS_TOKEN", ""),
        "CONTENT_NICHE": os.getenv("CONTENT_NICHE", "ความรู้การเงินและการลงทุน"),
    }

    set_count = 0
    for name, value in secrets.items():
        if value:
            subprocess.run(
                ["gh", "secret", "set", name, "--body", value, "--repo", REPO_NAME],
                capture_output=True, cwd=PROJECT_DIR
            )
            ok(f"Secret ตั้งค่าแล้ว: {name}")
            set_count += 1
        else:
            warn(f"ข้าม (ว่าง): {name}")

    ok(f"ตั้ง {set_count} secrets สำเร็จ")


def enable_actions(username: str):
    actions_url = f"https://github.com/{username}/{REPO_NAME}/actions"
    info(f"เปิดใช้งาน GitHub Actions: {actions_url}")
    time.sleep(1)
    webbrowser.open(actions_url)
    print(f"""
  {W}ใน GitHub:{X}
  1. คลิก {Y}"I understand my workflows, go ahead and enable them"{X}
  2. เสร็จ! ระบบจะโพสต์อัตโนมัติตามเวลาใน workflow
""")


def main():
    os.chdir(PROJECT_DIR)
    print(f"\n{B}{BOLD}╔══════════════════════════════════════════╗")
    print(f"║      GitHub Auto Setup — Auto Poster   ║")
    print(f"╚══════════════════════════════════════════╝{X}\n")

    # Step 1: GitHub CLI
    step(1, "ตรวจสอบ GitHub CLI")
    if not check_gh_installed():
        warn("ไม่พบ GitHub CLI (gh) กำลังติดตั้ง...")
        install_gh_windows()
    else:
        ok("GitHub CLI พร้อมแล้ว")

    # Step 2: Login
    step(2, "Login GitHub")
    username = gh_login()

    # Step 3: สร้าง repo
    step(3, f"สร้าง Repository: {REPO_NAME}")
    create_repo()

    # Step 4: Git init + commit
    step(4, "เตรียมโค้ด")
    init_git()

    # Step 5: Push
    step(5, "Push โค้ด")
    set_remote(username)
    push_code()

    # Step 6: Secrets
    step(6, "ตั้ง GitHub Secrets (API Keys)")
    set_secrets()

    # Step 7: เปิด Actions
    step(7, "เปิดใช้งาน GitHub Actions")
    enable_actions(username)

    repo_url = f"https://github.com/{username}/{REPO_NAME}"
    print(f"""{G}{BOLD}
  ══════════════════════════════════════════
  Setup GitHub เสร็จสมบูรณ์!
  ══════════════════════════════════════════{X}

  {W}Repository:{X} {C}{repo_url}{X}
  {W}Actions:{X}   {C}{repo_url}/actions{X}

  {Y}ตารางโพสต์อัตโนมัติ:{X}
    08:00 น.  •  12:00 น.  •  18:00 น.

  {Y}โพสต์ทันทีโดยไม่ต้องรอเวลา:{X}
    ไปที่ Actions → Auto Social Media Poster
    → คลิก "Run workflow" → Run workflow
""")


if __name__ == "__main__":
    main()
