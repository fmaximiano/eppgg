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
            for key in ['personal_additions_regime', 'quinquennia', 'quinquennium_base', 'ade_percent', 'ade_base', 'ade_calculation', 'ade_entry_year', 'ade_evaluations']:
                old.pop(key)
            page.evaluate("s=>localStorage.setItem('eppgg.scenarios.v1',JSON.stringify([s]))", old)
            page.reload(wait_until='networkidle')
            page.locator('[name=gdpi_evaluation]').select_option('normal')
            page.locator('[name=ai]').fill('90')
            expect(page.locator('#personal-additions')).to_be_visible()
            expect(page.locator('#personal-additions > h3')).to_be_visible()
            expect(page.locator('#evaluation-hint,#personal-additions-help,#personal-sources')).to_have_count(0)
            expect(page.locator('summary').filter(has_text='Faixas máximas do ADE')).to_have_count(0)
            for key in ['quinquennia', 'ade_calculation', 'ade_entry_year', 'ade_evaluations', 'quinquennium_base', 'ade_base']:
                expect(page.locator(f'[name={key}]')).to_be_disabled()
            page.locator('[name=personal_additions_regime]').select_option('ade_option')
            page.locator('[name=quinquennia]').fill('2')
            page.locator('[name=ade_entry_year]').fill('2021')
            page.locator('summary').filter(has_text='IPSEMG e familiares').click()
            page.locator('[name=health_enrolled]').check()
            # ADE = faixa × ADI: 3773,24 × 10% × 0,95 = 358,46.
            expect(page.locator('.stat.net .stat-value')).to_contain_text('5.429,20')
            expect(page.locator('#result')).to_contain_text('Quinquênio')
            expect(page.locator('#result')).to_contain_text('754,65')
            expect(page.locator('#result')).to_contain_text('358,46')
            # ADI própria do ADE, com vírgula: 3773,24 × 10% × 0,805 = 303,75.
            page.locator('[name=ade_adi]').press_sequentially('80,5')
            expect(page.locator('#result')).to_contain_text('303,75')
            expect(page.locator('[name=ade_adi]')).to_have_value('80,5')
            page.locator('[name=ade_adi]').fill('')
            expect(page.locator('#result')).to_contain_text('358,46')
            page.locator('#personal-additions summary').filter(has_text='Bases específicas').click()
            page.locator('[name=quinquennium_base]').fill('5000')
            expect(page.locator('#result')).to_contain_text('1.000,00')
            page.locator('[name=personal_additions_regime]').select_option('ade')
            expect(page.locator('[name=quinquennia]')).to_be_disabled()
            expect(page.locator('[name=quinquennium_base]')).to_be_disabled()
            expect(page.locator('.stat').first.locator('.stat-value')).to_contain_text('6.775,71')
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.locator('[data-tab=compare]').click()
            page.locator('.load-scenario').click()
            expect(page.locator('[name=personal_additions_regime]')).to_have_value('none')
            expect(page.locator('[name=quinquennia]')).to_have_value('0')
            expect(page.locator('[name=ade_calculation]')).to_have_value('entry_year')
            expect(page.locator('[name=ade_entry_year]')).to_have_value('')
            expect(page.locator('[name=quinquennium_base]')).to_have_value('')
            expect(page.locator('.stat.net .stat-value')).to_contain_text('5.108,42')
            page.locator('[name=personal_additions_regime]').select_option('ade')
            page.locator('[name=ade_calculation]').select_option('evaluations')
            expect(page.locator('[name=ade_entry_year]')).to_be_disabled()
            page.locator('[name=ade_evaluations]').fill('10')
            # 3773,24 × 20% × 0,95 = 716,92.
            expect(page.locator('#result')).to_contain_text('716,92')
            expect(page.locator('#result')).to_contain_text('10 avaliações satisfatórias')
            page.locator('[data-tab=sources]').click()
            expect(page.locator('#source-search')).to_be_visible()
            page.locator('#source-search').fill('Quinquênio')
            expect(page.locator('#source-groups')).to_contain_text('Lei nº 14.693/2003')
            expect(page.locator('#source-groups')).to_contain_text('Emenda à Constituição Estadual nº 57/2003')
            legacy = {**old, 'personal_additions_regime': 'ade', 'ade_percent': '10'}
            page.evaluate("s=>localStorage.setItem('eppgg.scenarios.v1',JSON.stringify([s]))", legacy)
            page.reload(wait_until='networkidle')
            page.locator('[data-tab=compare]').click()
            page.locator('.load-scenario').click()
            expect(page.locator('[name=ade_calculation]')).to_have_value('granted_percentage')
            expect(page.locator('.stat').first.locator('.stat-value')).to_contain_text('6.794,57')
            expect(page.locator('[name=ade_percent]')).not_to_be_visible()
            assert not errors, errors
            print(f'PASS: adicionais pessoais {width}px; líquido, bases, campos condicionais, cenário antigo e fontes')
            context.close()
        browser.close()


if __name__ == '__main__':
    main()
