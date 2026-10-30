"""Compact controls, percentage conversion and saved rubric metadata."""
import os
from playwright.sync_api import sync_playwright, expect


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=os.getenv('CHROMIUM_PATH', '/usr/bin/chromium'), args=['--no-sandbox'])
        for width in [1440, 390]:
            page = browser.new_page(viewport={'width': width, 'height': 1000})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(os.getenv('APP_URL', 'http://127.0.0.1:8005'), wait_until='networkidle')
            page.locator('#scenario-form summary').filter(has_text='IPSEMG').click()
            row = page.locator('.beneficiary').first
            expect(row.locator('.beneficiary-age')).to_be_visible()
            relationship_box = row.locator('.relationship').bounding_box()
            age_box = row.locator('.beneficiary-age').bounding_box()
            assert abs(relationship_box['y'] - age_box['y']) < 3
            page.locator('#scenario-form summary').filter(has_text='Previdência e contribuição').click()
            expect(page.locator('.complementary-settings [name=complementary_deductible]')).to_have_count(1)
            boxes = page.locator('.complementary-settings > label').evaluate_all('nodes=>nodes.map(n=>({left:n.getBoundingClientRect().left,right:n.getBoundingClientRect().right}))')
            assert boxes[1]['left'] >= boxes[0]['right']
            expect(page.get_by_text('A opção remuneratória e a contribuição facultativa são escolhas independentes.', exact=False)).to_have_count(0)
            page.locator('#scenario-form summary').filter(has_text='Rubricas e proporcionalidade').click()
            fraction = page.locator('[name=fraction]')
            expect(fraction).to_have_value('100')
            fraction.fill('50')
            expect(page.locator('#save')).to_be_enabled()
            assert page.evaluate('lastResult.scenario.fraction') == '0.5'
            page.locator('#save').click()
            page.locator('#reset').click()
            expect(fraction).to_have_value('100')
            page.locator('[data-tab=compare]').click()
            page.locator('.load-scenario').click()
            expect(fraction).to_have_value('50')
            expect(page.locator('#save')).to_be_enabled()
            page.locator('#add-rubric').click()
            page.locator('.rubric-name-input').fill('Verba de teste')
            page.locator('.rubric-amount').fill('200')
            page.locator('.rubric [data-flag=proportional]').check()
            expect(page.locator('.rubric-source')).to_have_count(0)
            expect(page.locator('#save')).to_be_enabled()
            assert page.evaluate("lastResult.monthly.earnings.find(r=>r.name==='Verba de teste').amount") == '100.00'
            legacy = page.evaluate('lastResult.scenario')
            legacy['rubrics'][0]['source'] = 'Fundamento do cenário antigo'
            page.evaluate('s=>loadScenario(s)', legacy)
            expect(page.locator('#save')).to_be_enabled()
            assert page.evaluate('lastResult.scenario.rubrics[0].source') == 'Fundamento do cenário antigo'
            page.locator('[data-tab=sources]').click()
            page.locator('#source-search').fill('48.113')
            expect(page.locator('#source-groups')).to_contain_text('Decreto nº 48.113')
            page.locator('#source-search').fill('COFIN')
            expect(page.locator('#source-groups')).to_contain_text('23 de outubro de 2026')
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            assert not errors, errors
            print(f'PASS: campos compactos, porcentagem, rubricas e legislação {width}px')
            page.close()
        browser.close()


if __name__ == '__main__':
    main()
