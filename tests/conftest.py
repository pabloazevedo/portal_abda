"""
Fixtures compartilhadas para os testes de acessibilidade do Portal.

Pré-requisitos:
    pip install -r requirements-dev.txt
    playwright install chromium

Para rodar:
    pytest tests/ -v

O servidor deve estar rodando em BASE_URL (default: http://localhost:8000).
Defina a variável de ambiente PORTAL_BASE_URL para sobrescrever.
"""
import os
import pytest

try:
    from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
    HAS_PLAYWRIGHT = True
except ImportError:  # pytest unitário sem requirements-dev
    HAS_PLAYWRIGHT = False
    Browser = BrowserContext = Page = object  # type: ignore

BASE_URL = os.getenv("PORTAL_BASE_URL", "http://localhost:8000")
ADMIN_USER = os.getenv("PORTAL_ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("PORTAL_ADMIN_PASS", "admin123")

AXE_CDN = (
    "https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.0/axe.min.js"
)


@pytest.fixture(scope="session")
def browser_ctx():
    if not HAS_PLAYWRIGHT:
        pytest.skip("playwright não instalado (pip install -r requirements-dev.txt)")
    with sync_playwright() as pw:
        browser: Browser = pw.chromium.launch(headless=True)
        context: BrowserContext = browser.new_context(viewport={"width": 1280, "height": 800})

        # Faz login uma única vez para toda a sessão de testes
        page: Page = context.new_page()
        page.goto(f"{BASE_URL}/login")
        page.fill('input[name="username"]', ADMIN_USER)
        page.fill('input[name="password"]', ADMIN_PASS)
        page.click('button[type="submit"]')
        page.wait_for_url(f"{BASE_URL}/", timeout=10_000)
        page.close()

        yield context
        context.close()
        browser.close()


@pytest.fixture()
def page(browser_ctx: BrowserContext):
    p = browser_ctx.new_page()
    yield p
    p.close()


def run_axe(page: Page, impacts: set | None = None) -> list[dict]:
    """Injeta axe-core, executa e retorna apenas as violações nos níveis solicitados."""
    if not HAS_PLAYWRIGHT:
        pytest.skip("playwright não instalado")
    if impacts is None:
        impacts = {"critical", "serious"}

    page.add_script_tag(url=AXE_CDN)
    page.wait_for_function("typeof axe !== 'undefined'", timeout=10_000)

    violations: list[dict] = page.evaluate(
        """() => new Promise((resolve, reject) => {
            axe.run(document, { resultTypes: ['violations'] }, (err, res) => {
                if (err) reject(err);
                else resolve(res.violations);
            });
        })"""
    )
    if impacts:
        violations = [v for v in violations if v.get("impact") in impacts]
    return violations


def fmt_violations(violations: list[dict]) -> str:
    lines = []
    for v in violations:
        lines.append(f"\n  [{v['impact'].upper()}] {v['id']}: {v['description']}")
        for node in v.get("nodes", [])[:2]:
            targets = node.get("target", [])
            lines.append(f"    → {targets}")
            if node.get("failureSummary"):
                lines.append(f"      {node['failureSummary'].splitlines()[0]}")
    return "".join(lines)
