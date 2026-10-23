"""Teste funcional opcional: pip install playwright; usa Chromium do sistema.

Execute com o servidor iniciado: python tests/browser_smoke.py
"""
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect


def main():
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=os.getenv('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
        for width,height in [(1440,1050),(390,844)]:
            context=browser.new_context(viewport={'width':width,'height':height},locale='pt-BR')
            page=context.new_page()
            errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(os.getenv('APP_URL','http://127.0.0.1:8000'),wait_until='networkidle')
            expect(page.locator('.stat.net .stat-value')).to_contain_text('5.889,55')
            page.locator('[name=adi]').fill('69')
            expect(page.locator('.big-inline').first).to_contain_text('0,00')
            page.locator('[name=adi]').fill('95')
            expect(page.locator('.stat.net .stat-value')).to_contain_text('5.889,55')
            page.locator('#save').click()
            expect(page.locator('#saved-count')).to_have_text('1')
            page.locator('[name=name]').fill('Comissão B')
            page.locator('[name=commission]').select_option('COMISSÃO DEMO')
            page.locator('[name=remuneration_option]').select_option('b')
            expect(page.locator('.stat').first.locator('.stat-value')).to_contain_text('9.906,00')
            page.locator('#save').click()
            expect(page.locator('#saved-count')).to_have_text('2')
            page.locator('[data-tab=compare]').click()
            page.locator('#run-compare').click()
            expect(page.locator('#comparison-result')).to_contain_text('Maior líquido mensal')
            page.locator('.load-scenario').last.click()
            page.locator('[name=name]').fill('Cenário editado')
            page.locator('#save').click()
            expect(page.locator('#saved-count')).to_have_text('2')
            page.locator('[data-tab=compare]').click()
            expect(page.locator('#saved-list')).to_contain_text('Cenário editado')
            page.locator('[data-tab=career]').click()
            page.locator('#future-level').select_option('III')
            page.locator('#project-career').click()
            expect(page.locator('#career-result')).to_contain_text('Diferença líquida mensal')
            page.locator('[data-tab=sources]').click()
            expect(page.locator('#sources-content')).to_contain_text('Decreto_47081_16.pdf')
            page.locator('[data-tab=calculator]').click()
            with page.expect_download() as downloaded:
                page.locator('[data-format=json]').click()
            assert downloaded.value.suggested_filename.endswith('.json')
            page.locator('[name=mode]').select_option('official')
            expect(page.locator('#calculation-error')).to_contain_text('Nenhuma tabela oficial')
            expect(page.locator('.stat-value')).to_have_count(0)
            page.locator('[name=mode]').select_option('demo')
            expect(page.locator('.stat-value')).to_have_count(3)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Overflow horizontal'
            assert not errors,errors
            if os.getenv('SCREENSHOTS_DIR'):
                directory=Path(os.environ['SCREENSHOTS_DIR']);directory.mkdir(parents=True,exist_ok=True)
                page.screenshot(path=str(directory/f'eppgg-{width}.png'),full_page=True)
            print(f'PASS: interface {width}px, cálculo, cenários, comparação, carreira, fontes, exportação e bloqueio oficial')
            context.close()
        browser.close()


if __name__=='__main__':main()
