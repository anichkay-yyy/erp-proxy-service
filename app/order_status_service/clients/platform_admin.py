import os
import re
import time
from http.cookiejar import MozillaCookieJar

import requests

from order_status_service.datatables import datatables_order_params


class PlatformAdminClient:
    def __init__(self, base_url: str, cookie_jar_path: str):
        self.base_url = base_url.rstrip("/")
        self.cookie_jar_path = cookie_jar_path
        self.cookies = MozillaCookieJar(cookie_jar_path)
        self.session = requests.Session()
        self.session.cookies = self.cookies
        self.csrf_token = None
        self.csrf_update_url = None
        self.csrf_update_timeout_minutes = None
        self.csrf_timestamp = None

        if os.path.exists(cookie_jar_path):
            self.cookies.load(ignore_discard=True, ignore_expires=True)

    def save_cookies(self) -> None:
        self.cookies.save(ignore_discard=True, ignore_expires=True)

    def _headers(self, ajax: bool = False) -> dict:
        headers = {
            "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0 Safari/537.36"
            ),
        }
        if ajax:
            headers.update(
                {
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "X-Requested-With": "XMLHttpRequest",
                }
            )
        if self.csrf_token:
            headers["X-CSRF-TOKEN"] = self.csrf_token
        return headers

    def _extract_csrf(self, html: str) -> str:
        for pattern in (
            r'<meta\s+name="csrf-token"([^>]*)>',
            r'name="_token"\s+value="([^"]+)"',
        ):
            match = re.search(pattern, html)
            if match:
                if pattern.startswith("<meta"):
                    attrs = match.group(1)
                    token = self._extract_attr(attrs, "content")
                    self.csrf_update_url = self._extract_attr(attrs, "data-update-url")
                    timeout = self._extract_attr(attrs, "data-update-timeout")
                    timestamp = self._extract_attr(attrs, "data-timestamp")
                    self.csrf_update_timeout_minutes = int(timeout) if timeout else None
                    self.csrf_timestamp = int(timestamp) if timestamp else None
                    if token:
                        return token
                else:
                    return match.group(1)
        raise RuntimeError("CSRF token not found in HTML")

    @staticmethod
    def _extract_attr(attrs: str, name: str) -> str | None:
        match = re.search(rf'{re.escape(name)}="([^"]*)"', attrs)
        return match.group(1) if match else None

    def get_login_page(self, locale: str) -> str:
        response = self.session.get(
            f"{self.base_url}/{locale}/login",
            params={"backurl": "/"},
            headers=self._headers(),
            timeout=30,
        )
        response.raise_for_status()
        self.csrf_token = self._extract_csrf(response.text)
        self.save_cookies()
        return response.text

    def login(self, locale: str, email: str, password: str) -> None:
        self.get_login_page(locale)
        response = self.session.post(
            f"{self.base_url}/{locale}/login",
            data={
                "_token": self.csrf_token,
                "backurl": "/",
                "email": email,
                "password": password,
                "remember": "on",
            },
            headers={
                **self._headers(),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            allow_redirects=True,
            timeout=30,
        )
        response.raise_for_status()
        self.csrf_token = self._extract_csrf(response.text)
        self.save_cookies()

        if re.search(r'name="password"|/login', response.text) and "Logout" not in response.text:
            raise RuntimeError("Login did not reach an authenticated page")

    def ensure_page_csrf(self, locale: str, company: str) -> None:
        response = self.session.get(
            f"{self.base_url}/{locale}/{company}/orders",
            headers=self._headers(),
            timeout=30,
        )
        if response.status_code in (401, 419) or "/login" in response.url:
            raise RuntimeError("Session is not authenticated")
        response.raise_for_status()
        self.csrf_token = self._extract_csrf(response.text)
        self.save_cookies()

    def refresh_csrf(self, force: bool = False) -> dict:
        if not force and self.csrf_timestamp and self.csrf_update_timeout_minutes:
            refresh_at = self.csrf_timestamp + self.csrf_update_timeout_minutes * 60
            now = int(time.time())
            if now < refresh_at:
                return {
                    "skipped": "csrf token is still fresh",
                    "seconds_until_refresh": refresh_at - now,
                }

        url = self.csrf_update_url or f"{self.base_url}/api/csrf-update"
        response = self.session.get(
            url,
            headers=self._headers(ajax=True),
            timeout=30,
        )
        if response.status_code == 405:
            response = self.session.post(
                url,
                headers=self._headers(ajax=True),
                timeout=30,
            )
        response.raise_for_status()
        self.save_cookies()
        try:
            payload = response.json()
        except ValueError:
            return {"raw": response.text[:300]}

        for key in ("token", "csrf_token", "csrfToken"):
            if isinstance(payload, dict) and payload.get(key):
                self.csrf_token = payload[key]
                break
        return payload

    def get_orders(
        self,
        locale: str,
        company: str,
        by_date: str,
        query: str = "",
        query_type: str = "number",
        start: int = 0,
        length: int = 25,
        draw: int = 1,
        filters: dict | None = None,
    ) -> dict:
        params = datatables_order_params(
            by_date=by_date,
            query=query,
            query_type=query_type,
            start=start,
            length=length,
            draw=draw,
            filters=filters,
        )
        response = self.session.get(
            f"{self.base_url}/{locale}/{company}/orders",
            params=params,
            headers={
                **self._headers(ajax=True),
                "Referer": f"{self.base_url}/{locale}/{company}/orders",
            },
            timeout=30,
        )
        if response.status_code in (401, 419) or "/login" in response.url:
            raise RuntimeError(f"Session expired or CSRF rejected: HTTP {response.status_code}")
        response.raise_for_status()
        self.save_cookies()
        return response.json()

    def search_order(self, locale: str, company: str, order_number: str, by_date: str) -> dict:
        return self.get_orders(
            locale=locale,
            company=company,
            by_date=by_date,
            query=order_number,
            query_type="number",
            start=0,
            length=25,
        )


