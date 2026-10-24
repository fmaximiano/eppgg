"""Fluxo de adicionais pessoais e abertura de cenários antigos, desktop e celular."""
import os
from playwright.sync_api import sync_playwright, expect


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=os.getenv('CHROMIUM_PATH', '/usr/bin/chromium'), headless=True, args=['--no-sandbox'])
        for width, height in [(1440, 1050), (390, 844)]:
            context = browser.new_context(viewport={'width': width, 'height': height}, locale='pt-BR')
            page = context.new_page()
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.goto(os.getenv('APP_URL', 'http://127.0.0.1:8000'), wait_until='networkidle')
            old = page.request.post(page.url.rstrip('/') + '/api/calculate', data={'mode': 'real', 'name': 'Cenário anterior'}).json()['scenario']
            for key in ['personal_additions_regime', 'quinquennia', 'quinquennium_base', 'ade_percent', 'ade_base']:
                old.pop(key)
            page.evaluate("s=>localStorage.setItem('eppgg.scenarios.v1',JSON.stringify([s]))", old)
            page.reload(wait_until='networkidle')
            page.locator('[name=gdpi_evaluation]').select_option('normal')
            page.locator('[name=ai]').fill('90')
            page.locator('#personal-additions > summary').click()
            for key in ['quinquennia', 'ade_percent', 'quinquennium_base', 'ade_base']:
                expect(page.locator(f'[name={key}]')).to_be_disabled()
            page.locator('[name=personal_additions_regime]').select_option('ade_option')
            page.locator('[name=quinquennia]').fill('2')
            page.locator('[name=ade_percent]').fill('10')
            page.locator('summary').filter(has_text='IPSEMG e familiares').click()
            page.locator('[name=health_enrolled]').check()
            expect(page.locator('.stat.net .stat-value')).to_contain_text('5.440,22')
            expect(page.locator('#result')).to_contain_text('Quinquênio')
            expect(page.locator('#result')).to_contain_text('754,65')
            expect(page.locator('#result')).to_contain_text('377,32')
            page.locator('#personal-additions summary').filter(has_text='Bases específicas').click()
            page.locator('[name=quinquennium_base]').fill('5000')
            expect(page.locator('#result')).to_contain_text('1.000,00')
            page.locator('[name=personal_additions_regime]').select_option('ade')
            expect(page.locator('[name=quinquennia]')).to_be_disabled()
            expect(page.locator('[name=quinquennium_base]')).to_be_disabled()
            expect(page.locator('.stat').first.locator('.stat-value')).to_contain_text('6.794,57')
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.locator('[data-tab=compare]').click()
            page.locator('.load-scenario').click()
            expect(page.locator('[name=personal_additions_regime]')).to_have_value('none')
            expect(page.locator('[name=quinquennia]')).to_have_value('0')
            expect(page.locator('[name=ade_percent]')).to_have_value('0')
            expect(page.locator('[name=quinquennium_base]')).to_have_value('')
            expect(page.locator('.stat.net .stat-value')).to_contain_text('5.108,42')
            page.locator('#personal-additions summary').filter(has_text='Faixas máximas').click()
            page.locator('#personal-sources').click()
            expect(page.locator('#source-groups')).to_contain_text('Lei nº 14.693/2003')
            expect(page.locator('#source-groups')).to_contain_text('Emenda à Constituição Estadual nº 57/2003')
            assert not errors, errors
            print(f'PASS: adicionais pessoais {width}px; líquido, bases, campos condicionais, cenário antigo e fontes')
            context.close()
        browser.close()


if __name__ == '__main__':
    main()
