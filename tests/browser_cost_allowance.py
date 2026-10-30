"""Ajuda de custo: alternativas exclusivas, atualização e persistência."""
import os
from playwright.sync_api import sync_playwright, expect


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=os.getenv('CHROMIUM_PATH', '/usr/bin/chromium'), args=['--no-sandbox'])
        for width in [1440, 390]:
            page = browser.new_page(viewport={'width': width, 'height': 1000})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(os.getenv('APP_URL', 'http://127.0.0.1:8003'), wait_until='networkidle')
            days = page.locator('[name=cost_allowance_days]')
            goals = page.locator('[name=cost_allowance_goals]')
            monthly = page.locator('[name=cost_allowance_monthly]')
            daily = page.locator('[name=cost_allowance_daily]')
            expect(page.locator('#cost-days-help')).to_contain_text('6h diárias e 30h semanais')
            days.fill('20')
            goals.fill('80')
            expect(monthly).to_be_disabled()
            expect(daily).to_be_disabled()
            expect(page.locator('#save')).to_be_enabled()
            assert page.evaluate("lastResult.monthly.earnings.find(r=>r.name==='Ajuda de custo').amount") == '1800.00'
            goals.fill('')
            daily.fill('75.50')
            expect(goals).to_be_disabled()
            expect(monthly).to_be_disabled()
            expect(days).to_be_enabled()
            expect(page.locator('#save')).to_be_enabled()
            assert page.evaluate("lastResult.monthly.earnings.find(r=>r.name==='Ajuda de custo').amount") == '1510.00'
            daily.fill('')
            monthly.fill('999.99')
            expect(days).to_be_disabled()
            expect(page.locator('#save')).to_be_enabled()
            assert page.evaluate("lastResult.monthly.earnings.find(r=>r.name==='Ajuda de custo').amount") == '999.99'
            page.locator('#save').click()
            page.locator('#reset').click()
            expect(monthly).to_have_value('')
            expect(days).to_be_enabled()
            page.locator('[data-tab=compare]').click()
            page.locator('.load-scenario').click()
            expect(monthly).to_have_value('999.99')
            expect(days).to_be_disabled()
            monthly.fill('')
            expect(days).to_be_enabled()
            expect(goals).to_be_enabled()
            expect(daily).to_be_enabled()
            goals.fill('0')
            expect(monthly).to_be_disabled()
            expect(page.locator('#save')).to_be_disabled()
            days.fill('10')
            expect(page.locator('#save')).to_be_enabled()
            assert page.evaluate("lastResult.monthly.earnings.find(r=>r.name==='Ajuda de custo').amount") == '500.00'
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            assert not errors, errors
            page.close()
            print(f'PASS: ajuda de custo {width}px')
        browser.close()


if __name__ == '__main__':
    main()
