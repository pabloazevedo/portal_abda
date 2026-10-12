"""Smoke HTTP against the running Uvicorn process (no httpx)."""
import os
import urllib.error
import urllib.parse
import urllib.request
import http.cookiejar

BASE = os.getenv("PORTAL_BASE_URL", "http://127.0.0.1:8000")


def fetch(url, data=None, jar=None, method=None):
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar or http.cookiejar.CookieJar()))
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with opener.open(req, timeout=10) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, dict(resp.headers), body, opener
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return e.code, dict(e.headers), body, opener


def main():
    jar = http.cookiejar.CookieJar()

    status, _, body, _ = fetch(f"{BASE}/login", jar=jar)
    assert status == 200, status
    assert "lang-bar" not in body
    assert "/set-lang/" not in body
    print("login OK, no lang switcher")

    # follow_redirects is automatic in urllib; check Location via HTTPError or use opener carefully
    req = urllib.request.Request(f"{BASE}/set-lang/en")
    opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler)
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    opener = urllib.request.build_opener(NoRedirect, urllib.request.HTTPCookieProcessor(jar))
    try:
        opener.open(req, timeout=10)
        raise AssertionError("expected redirect")
    except urllib.error.HTTPError as e:
        assert e.code in (302, 303, 307), e.code
        loc = e.headers.get("Location", "")
        print("set-lang unauth redirect", e.code, loc)

    status, headers, _, _ = fetch(f"{BASE}/static/css/style.css")
    assert status == 200
    status, _, body, _ = fetch(f"{BASE}/static/css/style.css")
    assert "toast-container" in body or "portal-toast" in body
    status, _, body, _ = fetch(f"{BASE}/static/js/app.js")
    assert status == 200 and "showToast" in body
    print("static assets OK")

    # login — senha padrão local é "admin" se ADMIN_PASSWORD vazio
    for password in ("admin", "admin123", os.getenv("ADMIN_PASSWORD", "")):
        if not password:
            continue
        jar = http.cookiejar.CookieJar()
        payload = urllib.parse.urlencode({"username": "admin", "password": password}).encode()
        opener = urllib.request.build_opener(NoRedirect, urllib.request.HTTPCookieProcessor(jar))
        try:
            opener.open(urllib.request.Request(f"{BASE}/login", data=payload, method="POST"), timeout=10)
            continue
        except urllib.error.HTTPError as e:
            loc = e.headers.get("Location", "")
            print("login attempt", password, e.code, loc)
            if e.code in (302, 303) and (loc.endswith("/") or loc.rstrip("/").endswith(":8000")):
                status, _, home, _ = fetch(f"{BASE}/", jar=jar)
                assert status == 200
                assert 'id="toast-root"' in home
                print("home authenticated OK")

                try:
                    opener.open(urllib.request.Request(f"{BASE}/set-lang/es"), timeout=10)
                except urllib.error.HTTPError as e2:
                    loc2 = e2.headers.get("Location", "")
                    print("set-lang admin", e2.code, loc2)
                    assert "settings" in loc2 and "idioma" in loc2

                status, _, settings, _ = fetch(f"{BASE}/settings/", jar=jar)
                assert status == 200
                assert "section-idioma" in settings
                # sidebar must not expose language picker
                assert "set-lang/pt" not in settings
                print("settings idioma OK")
                break
    else:
        print("skip authed smoke (admin credentials not available)")

    print("SMOKE PASS")


if __name__ == "__main__":
    main()
