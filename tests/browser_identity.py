"""Identificação sem nome próprio, logo transparente e contraste por tema."""
import os
from playwright.sync_api import sync_playwright, expect


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=os.getenv('CHROMIUM_PATH', '/usr/bin/chromium'), args=['--no-sandbox'])
        for width in [1440, 390, 320]:
            page = browser.new_page(viewport={'width': width, 'height': 1000})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(os.getenv('APP_URL', 'http://127.0.0.1:8008'), wait_until='networkidle')
            expect(page.locator('.brand')).to_contain_text('Calculadora de Salário')
            expect(page.locator('.brand-sub').first).to_have_text('EPPGG . MINAS GERAIS')
            expect(page.locator('.brand-sub').first).to_be_visible()
            expect(page.locator('footer strong')).to_have_text('Calculadora de Salário')
            expect(page.locator('footer .brand-sub')).to_have_text('EPPGG . MINAS GERAIS')
            assert 'horizonte' not in page.content().lower()
            assert page.locator('.brand-icon').get_attribute('viewBox') == '0 0 336 336'
            colors = []
            for theme in ['light', 'dark']:
                page.evaluate('theme=>{localStorage.setItem("eppgg.theme",theme);document.documentElement.dataset.theme=theme}', theme)
                colors.append(page.locator('.logo-bars path').first.evaluate('e=>getComputedStyle(e).fill'))
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                screenshot_dir = os.getenv('SCREENSHOTS_DIR')
                if screenshot_dir:
                    page.locator('header').screenshot(path=f'{screenshot_dir}/identity-{width}-{theme}.png')
            assert colors[0] != colors[1], colors
            assert not errors, errors
            print(f'PASS: identificação e logo claro/escuro {width}px')
            page.close()
        browser.close()


if __name__ == '__main__':
    main()
