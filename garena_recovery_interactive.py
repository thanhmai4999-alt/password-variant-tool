import asyncio
import json
import random
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse
import sys
import platform

import aiofiles
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

try:
    import tkinter as tk
    from tkinter import simpledialog, messagebox, scrolledtext
    HAS_TKINTER = True
except ImportError:
    HAS_TKINTER = False

LOGIN_URL = "https://sso.garena.com/universal/login?app_id=10100&redirect_uri=https%3A%2F%2Faccount.garena.com%2F&locale=vi-VN"
ACCOUNT_URL = "https://account.garena.com/"
NAPTHE_LOGIN_URL = "https://napthe.vn/"
NAPTHE_API_URL = "https://napthe.vn/api/auth/get_user_info/multi"
RECOVERY_URL = "https://account.garena.com/recovery#/submit_phone"

SELECTORS = {
    "username": "input[name='username'], input[type='text']",
    "password": "input[name='password'], input[type='password']",
    "login_button": "button[type='submit'], button:has-text('Đăng nhập'), button:has-text('đăng nhập')",
    "captcha": "iframe[src*='captcha'], text=CAPTCHA, text=captcha, div[class*='captcha']",
    "otp": "text=OTP, text=mã xác minh, text=xác minh, input[placeholder*='OTP']",
    "masked_phone": "input[placeholder*='****']",
    "recovery_phone_input": "input[placeholder*='****'], input[placeholder*='điện thoại']",
    "recovery_submit": "button:has-text('Nhận mã'), button:has-text('tiếp tục'), button[type='submit']",
}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


@dataclass
class Phase1Result:
    login_status: str
    last_4_digits: str = ""
    masked_phone: str = ""
    error: str = ""


@dataclass
class Phase2Result:
    api_status: str
    first_3_digits: str = ""
    full_masked_phone: str = ""
    error: str = ""


@dataclass
class Phase3Result:
    recovery_status: str
    complete_phone: str = ""
    attempts: int = 0
    error: str = ""


@dataclass
class AuditResult:
    username: str
    status: str
    timestamp: str = ""
    proxy_used: str = ""
    user_agent: str = ""
    phase1: Phase1Result = field(default_factory=lambda: Phase1Result("failed"))
    phase2: Phase2Result = field(default_factory=lambda: Phase2Result("failed"))
    phase3: Phase3Result = field(default_factory=lambda: Phase3Result("failed"))


def extract_last_4_digits(masked_phone: str) -> str:
    """Extract last 4 digits from masked phone format."""
    if not masked_phone:
        return ""
    digits = re.findall(r"\d", masked_phone)
    if len(digits) >= 4:
        return "".join(digits[-4:])
    return ""


def extract_first_3_digits(masked_phone_display: str) -> str:
    """Extract first 3 digits from masked phone format."""
    if not masked_phone_display:
        return ""
    phone_clean = masked_phone_display.replace(" ", "").strip()
    if phone_clean.startswith("+84"):
        phone_clean = "0" + phone_clean[3:]
    digits = re.findall(r"\d", phone_clean)
    if len(digits) >= 3:
        return "".join(digits[:3])
    return ""


def is_still_on_login_page(url: str) -> bool:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    path = (parsed.path or "").lower()
    return hostname == "sso.garena.com" and "/login" in path


async def fetch_masked_phone_from_account(page, log_callback=None) -> str:
    """Fetch masked phone từ account.garena.com"""
    try:
        # Method 1: Extract từ text content
        page_text = await page.evaluate("() => document.body.innerText")
        if log_callback:
            log_callback(f"[DEBUG] Page text length: {len(page_text)}")
            log_callback(f"[DEBUG] Page text sample: {page_text[:500]}")
        
        patterns = [
            r'\+84\s+\*{2,}\d{2,4}',
            r'0\s*\*{2,}\d{2,4}',
            r'\+84\*{2,}\d{2,4}',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, page_text)
            if matches:
                result = matches[0].strip()
                if log_callback:
                    log_callback(f"[DEBUG] ✓ Found masked phone from text: {result}")
                return result
        
        # Method 2: Extract từ HTML
        page_html = await page.content()
        if log_callback:
            log_callback(f"[DEBUG] HTML content length: {len(page_html)}")
        
        for pattern in patterns:
            matches = re.findall(pattern, page_html)
            if matches:
                result = matches[0].strip()
                if log_callback:
                    log_callback(f"[DEBUG] ✓ Found masked phone from HTML: {result}")
                return result
        
        if log_callback:
            log_callback(f"[DEBUG] ❌ No masked phone found in text or HTML")
            log_callback(f"[DEBUG] HTML snippet: {page_html[1000:2000]}")
                
    except Exception as e:
        if log_callback:
            log_callback(f"[DEBUG] Error fetching phone: {e}")
    
    return ""


async def phase1_garena_login(
    username: str,
    password: str,
    timeout: int,
    proxy: Optional[str],
    log_callback=None,
) -> Phase1Result:
    result = Phase1Result(login_status="failed")
    
    args = []
    if platform.system() != "Windows":
        args = ["--no-sandbox"]
    
    launch_kwargs = {"headless": False, "args": args}  # headless=False để thấy browser
    if proxy:
        launch_kwargs["proxy"] = {"server": proxy}
    
    browser = None
    context = None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(**launch_kwargs)
            context = await browser.new_context(
                locale="vi-VN",
                viewport={"width": 1280, "height": 800},
                user_agent=random.choice(USER_AGENTS),
            )
            page = await context.new_page()
            
            if log_callback:
                log_callback("[Phase 1] 🔐 Đăng nhập Garena...")
            
            await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=timeout)
            await asyncio.sleep(2)
            
            if log_callback:
                log_callback(f"[Phase 1] Current URL: {page.url}")
            
            # Fill credentials
            try:
                await page.fill(SELECTORS["username"], username)
                if log_callback:
                    log_callback(f"[Phase 1] ✓ Filled username")
            except Exception as e:
                if log_callback:
                    log_callback(f"[Phase 1] ❌ Error filling username: {e}")
            
            try:
                await page.fill(SELECTORS["password"], password)
                if log_callback:
                    log_callback(f"[Phase 1] ✓ Filled password")
            except Exception as e:
                if log_callback:
                    log_callback(f"[Phase 1] ❌ Error filling password: {e}")
            
            if log_callback:
                log_callback("[Phase 1] Clicking login button...")
            
            await page.click(SELECTORS["login_button"])
            await asyncio.sleep(3)
            
            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
            except:
                pass
            
            if log_callback:
                log_callback(f"[Phase 1] URL after login: {page.url}")
            
            # Check if still on login page
            if is_still_on_login_page(page.url):
                result.login_status = "failed"
                result.error = "Still on login page - credentials may be invalid"
                if log_callback:
                    log_callback(f"[Phase 1] ❌ Still on login page")
                return result
            
            # Navigate to account page
            if log_callback:
                log_callback("[Phase 1] Going to account page...")
            
            await page.goto(ACCOUNT_URL, wait_until="domcontentloaded", timeout=timeout)
            await asyncio.sleep(3)
            
            if log_callback:
                log_callback(f"[Phase 1] Current URL: {page.url}")
            
            # Fetch masked phone
            if log_callback:
                log_callback("[Phase 1] 🔍 Searching for masked phone...")
            
            masked_phone = await fetch_masked_phone_from_account(page, log_callback)
            result.masked_phone = masked_phone
            result.last_4_digits = extract_last_4_digits(masked_phone)
            
            if result.last_4_digits:
                result.login_status = "success"
                if log_callback:
                    log_callback(f"✅ Found masked phone: {masked_phone}")
                    log_callback(f"✅ Last 4 digits: {result.last_4_digits}")
            else:
                result.login_status = "failed"
                result.error = f"Could not extract 4 digits from: {masked_phone}"
                if log_callback:
                    log_callback(f"❌ {result.error}")
            
            return result
    
    except Exception as e:
        result.error = f"{type(e).__name__}: {str(e)}"
        if log_callback:
            log_callback(f"❌ Phase 1 Exception: {result.error}")
        return result
    finally:
        if browser:
            try:
                await browser.close()
            except:
                pass


async def phase2_napthe_api(
    username: str,
    password: str,
    garena_username: str,
    timeout: int,
    proxy: Optional[str],
    log_callback=None,
) -> Phase2Result:
    result = Phase2Result(api_status="failed")
    
    args = []
    if platform.system() != "Windows":
        args = ["--no-sandbox"]
    
    launch_kwargs = {"headless": False, "args": args}
    if proxy:
        launch_kwargs["proxy"] = {"server": proxy}
    
    browser = None
    context = None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(**launch_kwargs)
            context = await browser.new_context(
                locale="vi-VN",
                viewport={"width": 1280, "height": 800},
                user_agent=random.choice(USER_AGENTS),
            )
            page = await context.new_page()
            
            if log_callback:
                log_callback("\n[Phase 2] 🌐 Đăng nhập napthe.vn...")
            
            await page.goto(NAPTHE_LOGIN_URL, wait_until="domcontentloaded", timeout=timeout)
            await asyncio.sleep(2)
            
            try:
                await page.fill("input[name='username'], input[type='email']", username)
                await page.fill("input[name='password'], input[type='password']", password)
                if log_callback:
                    log_callback(f"[Phase 2] ✓ Filled credentials")
                
                await page.click("button[type='submit'], button:has-text('Đăng nhập')")
                await asyncio.sleep(3)
                
                try:
                    await page.wait_for_load_state("networkidle", timeout=5000)
                except:
                    pass
                
                if log_callback:
                    log_callback(f"[Phase 2] Current URL: {page.url}")
            except Exception as e:
                result.error = f"napthe login failed: {str(e)}"
                if log_callback:
                    log_callback(f"❌ {result.error}")
                return result
            
            if log_callback:
                log_callback(f"[Phase 2] 📞 Calling API for: {garena_username}")
            
            try:
                api_response = await page.evaluate(f"""
                    (async () => {{
                        try {{
                            const response = await fetch('{NAPTHE_API_URL}', {{
                                method: 'POST',
                                headers: {{'Content-Type': 'application/json'}},
                                body: JSON.stringify({{username: '{garena_username}'}})
                            }});
                            const data = await response.json();
                            console.log('API Response:', JSON.stringify(data));
                            return data;
                        }} catch (e) {{
                            return {{'error': e.message}};
                        }}
                    }})()
                """)
                
                if log_callback:
                    log_callback(f"[Phase 2] 📦 API Response: {json.dumps(api_response, ensure_ascii=False)}")
                
                if api_response and isinstance(api_response, dict):
                    phone = None
                    
                    if "display_mobile_no" in api_response:
                        phone = api_response.get("display_mobile_no")
                    elif "data" in api_response and isinstance(api_response.get("data"), dict):
                        phone = api_response["data"].get("display_mobile_no")
                    
                    if phone:
                        result.full_masked_phone = str(phone)
                        result.first_3_digits = extract_first_3_digits(str(phone))
                        
                        if result.first_3_digits:
                            result.api_status = "success"
                            if log_callback:
                                log_callback(f"✅ Phone from API: {result.full_masked_phone}")
                                log_callback(f"✅ First 3 digits: {result.first_3_digits}")
                            return result
                    
                    if log_callback:
                        log_callback(f"❌ No phone found in response")
                
                return result
            
            except Exception as e:
                result.error = f"API call error: {str(e)}"
                if log_callback:
                    log_callback(f"❌ {result.error}")
                return result
    
    except Exception as e:
        result.error = f"{type(e).__name__}: {str(e)}"
        if log_callback:
            log_callback(f"❌ Phase 2 Exception: {result.error}")
        return result
    finally:
        if browser:
            try:
                await browser.close()
            except:
                pass


async def process_account(
    username: str,
    password: str,
    proxy: Optional[str],
    log_callback=None,
) -> AuditResult:
    result = AuditResult(
        username=username,
        status="failed",
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )
    
    result.proxy_used = proxy or "none"
    
    if log_callback:
        log_callback(f"\n{'='*60}")
        log_callback(f"🔐 Processing Account: {username}")
        log_callback(f"{'='*60}")
    
    # Phase 1
    result.phase1 = await phase1_garena_login(username, password, 45000, proxy, log_callback)
    
    if result.phase1.login_status != "success":
        result.status = result.phase1.login_status
        if log_callback:
            log_callback(f"\n❌ Phase 1 Failed: {result.phase1.error}")
        return result
    
    await asyncio.sleep(2)
    
    # Phase 2
    result.phase2 = await phase2_napthe_api(
        username, password, username, 45000, proxy, log_callback
    )
    
    if result.phase2.api_status != "success":
        result.status = "failed"
        if log_callback:
            log_callback(f"\n❌ Phase 2 Failed: {result.phase2.error}")
        return result
    
    return result


class GarenaRecoveryGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Garena Phone Recovery - DEBUG MODE")
        self.root.geometry("1000x750")
        
        self.is_running = False
        
        main_frame = tk.Frame(root, padx=20, pady=20, bg="#f0f0f0")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        title_label = tk.Label(
            main_frame,
            text="🔐 Garena Phone Recovery - DEBUG",
            font=("Arial", 16, "bold"),
            fg="#d4af37",
            bg="#f0f0f0"
        )
        title_label.pack(pady=10)
        
        account_frame = tk.LabelFrame(main_frame, text="Account", padx=10, pady=10, font=("Arial", 10, "bold"), bg="#f0f0f0")
        account_frame.pack(fill=tk.X, pady=10)
        
        tk.Label(account_frame, text="Username:", font=("Arial", 10), bg="#f0f0f0").pack(anchor=tk.W)
        self.username = tk.Entry(account_frame, width=50, font=("Arial", 10))
        self.username.pack(fill=tk.X, pady=5)
        
        tk.Label(account_frame, text="Password:", font=("Arial", 10), bg="#f0f0f0").pack(anchor=tk.W)
        self.password = tk.Entry(account_frame, width=50, font=("Arial", 10), show="*")
        self.password.pack(fill=tk.X, pady=5)
        
        button_frame = tk.Frame(main_frame, bg="#f0f0f0")
        button_frame.pack(fill=tk.X, pady=15)
        
        self.start_btn = tk.Button(
            button_frame,
            text="▶ Start",
            font=("Arial", 12, "bold"),
            bg="#4CAF50",
            fg="white",
            padx=20,
            pady=10,
            command=self.start_recovery
        )
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        log_frame = tk.LabelFrame(main_frame, text="Debug Log", padx=10, pady=10, font=("Arial", 10, "bold"), bg="#f0f0f0")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=14, width=100, font=("Courier", 9), bg="#1e1e1e", fg="#00ff00")
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        self.status_label = tk.Label(main_frame, text="Ready", font=("Arial", 10), fg="#4CAF50", bg="#f0f0f0")
        self.status_label.pack(pady=5)
    
    def log(self, message):
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.root.update()
    
    def start_recovery(self):
        username = self.username.get().strip()
        password = self.password.get().strip()
        
        if not username or not password:
            messagebox.showerror("Error", "Please enter credentials")
            return
        
        if self.is_running:
            messagebox.showwarning("Warning", "Already running!")
            return
        
        self.start_btn.config(state=tk.DISABLED)
        self.log_text.delete(1.0, tk.END)
        
        self.is_running = True
        asyncio.create_task(self.run_recovery(username, password))
    
    async def run_recovery(self, username, password):
        try:
            self.status_label.config(text="Running...", fg="#FF9800")
            
            result = await process_account(username, password, None, self.log)
            
            self.log("\n" + "="*60)
            self.log(f"RESULT: {result.status}")
            self.log("="*60)
            self.log(f"Phase 1: {result.phase1.login_status} - {result.phase1.last_4_digits}")
            self.log(f"Phase 2: {result.phase2.api_status} - {result.phase2.first_3_digits}")
            
            if result.status == "success":
                self.status_label.config(text="✓ Success!", fg="#4CAF50")
            else:
                self.status_label.config(text="✗ Failed", fg="#f44336")
        
        except Exception as e:
            self.log(f"\n[ERROR] {str(e)}")
            self.status_label.config(text="✗ Error", fg="#f44336")
        
        finally:
            self.start_btn.config(state=tk.NORMAL)
            self.is_running = False


async def main_gui():
    if not HAS_TKINTER:
        print("ERROR: tkinter not found")
        return
    
    root = tk.Tk()
    app = GarenaRecoveryGUI(root)
    
    async def update_gui():
        try:
            while True:
                root.update()
                await asyncio.sleep(0.01)
        except tk.TclError:
            pass
    
    await update_gui()


if __name__ == "__main__":
    try:
        asyncio.run(main_gui())
    except KeyboardInterrupt:
        print("\nExiting...")
