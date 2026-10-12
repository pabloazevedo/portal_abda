"""
Testes automatizados de acessibilidade (axe-core via Playwright).

Executa axe-core em cada página e falha se houver violações
de impacto 'critical' ou 'serious'.
"""
import pytest
from playwright.sync_api import Page

from tests.conftest import BASE_URL, run_axe, fmt_violations

# ──────────────────────────────────────────────────────────────
# Páginas testadas (path, nome descritivo)
# ──────────────────────────────────────────────────────────────

PAGES = [
    ("/",              "Home"),
    ("/musicians/",    "Lista de Membros"),
    ("/patrimonio/",   "Lista de Patrimônio"),
    ("/users/",        "Lista de Usuários"),
    ("/design-system", "Design System"),
]

FORM_PAGES = [
    ("/musicians/new", "Formulário — Novo Membro"),
    ("/patrimonio/new", "Formulário — Novo Item"),
]


# ──────────────────────────────────────────────────────────────
# Testes
# ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("path,name", PAGES)
def test_page_no_critical_violations(page: Page, path: str, name: str):
    """Nenhuma violação crítica ou séria deve existir nas páginas listadas."""
    page.goto(f"{BASE_URL}{path}", wait_until="networkidle")
    violations = run_axe(page)
    assert len(violations) == 0, (
        f"Violações de acessibilidade em '{name}' ({path}):{fmt_violations(violations)}"
    )


@pytest.mark.parametrize("path,name", FORM_PAGES)
def test_form_page_no_critical_violations(page: Page, path: str, name: str):
    """Formulários não devem ter violações críticas/sérias."""
    page.goto(f"{BASE_URL}{path}", wait_until="networkidle")
    violations = run_axe(page)
    assert len(violations) == 0, (
        f"Violações em '{name}' ({path}):{fmt_violations(violations)}"
    )


def test_login_page_no_critical_violations(browser_ctx):
    """Página de login (sem autenticação) também deve ser acessível."""
    page = browser_ctx.new_page()
    try:
        page.goto(f"{BASE_URL}/login", wait_until="networkidle")
        violations = run_axe(page)
        assert len(violations) == 0, (
            f"Violações em Login:{fmt_violations(violations)}"
        )
    finally:
        page.close()


def test_dark_mode_no_contrast_violations(page: Page):
    """Modo escuro não deve introduzir violações de contraste."""
    page.goto(f"{BASE_URL}/musicians/", wait_until="networkidle")
    page.evaluate("document.documentElement.setAttribute('data-theme', 'dark')")
    page.evaluate("document.documentElement.setAttribute('data-bs-theme', 'dark')")

    from tests.conftest import AXE_CDN
    page.add_script_tag(url=AXE_CDN)
    page.wait_for_function("typeof axe !== 'undefined'", timeout=10_000)

    violations = page.evaluate(
        """() => new Promise((resolve, reject) => {
            axe.run(document, {
                resultTypes: ['violations'],
                rules: { 'color-contrast': { enabled: true } },
            }, (err, res) => {
                if (err) reject(err);
                else resolve(res.violations.filter(v =>
                    v.id === 'color-contrast' && ['critical','serious'].includes(v.impact)
                ));
            });
        })"""
    )
    assert len(violations) == 0, (
        f"Violações de contraste no modo escuro:{fmt_violations(violations)}"
    )


def test_global_search_keyboard_accessible(page: Page):
    """Campo de busca global deve estar acessível por teclado."""
    page.goto(f"{BASE_URL}/musicians/", wait_until="networkidle")

    # Ctrl+K deve focar o campo de busca
    page.keyboard.press("Control+k")
    focused = page.evaluate("() => document.activeElement.id")
    assert focused == "global-search", (
        f"Ctrl+K não focou o campo de busca global (focou: {focused!r})"
    )


def test_modal_focus_management(page: Page):
    """Modal de confirmação deve focar o botão Cancelar ao abrir."""
    page.goto(f"{BASE_URL}/musicians/", wait_until="networkidle")

    # Verifica se há algum botão de deleção na página
    delete_btn = page.query_selector(".btn-icon.delete")
    if delete_btn is None:
        pytest.skip("Nenhum músico cadastrado para testar o modal de deleção")

    delete_btn.click()
    page.wait_for_selector("#confirmModal.show", timeout=3_000)

    focused = page.evaluate("() => document.activeElement.id")
    assert focused == "confirmModalCancel", (
        f"Modal aberto mas foco não está no Cancelar (está em: {focused!r})"
    )
