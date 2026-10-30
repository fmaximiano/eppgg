"""Regression: cleared inputs, collapsed validation and stale requests."""
import os
from playwright.sync_api import sync_playwright, expect


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=os.getenv('CHROMIUM_PATH', '/usr/bin/chromium'), args=['--no-sandbox'])
        page = browser.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(os.getenv('APP_URL', 'http://127.0.0.1:8000'), wait_until='networkidle')
        expect(page.locator('#save')).to_be_enabled()
        for name in ['alimony', 'other_deductions']:
            field = page.locator(f'[name={name}]')
            field.evaluate("e => e.closest('details').open = true")
            field.fill('123')
            field.fill('')
            expect(page.locator('#save')).to_be_enabled()
        page.locator('[name=adi]').fill('')
        expect(page.locator('#calculate')).to_be_enabled()
        expect(page.locator('#save')).to_be_disabled()
        page.locator('[name=adi]').evaluate("e => { for(let n=e.parentElement;n;n=n.parentElement) if(n.tagName==='DETAILS') n.open=false; }")
        page.locator('#calculate').click()
        expect(page.locator('[name=adi]')).to_be_visible()
        page.locator('[name=adi]').fill('80')
        expect(page.locator('#save')).to_be_enabled()
        # A failed request must release the button and allow a manual retry.
        page.route('**/api/calculate', lambda route: route.abort())
        page.locator('[name=adi]').fill('81')
        expect(page.locator('#calculation-error')).to_be_visible()
        expect(page.locator('#calculate')).to_be_enabled()
        page.unroute_all(behavior='ignoreErrors')
        page.locator('#calculate').click()
        expect(page.locator('#save')).to_be_enabled()
        expect(page.locator('#calculation-error')).to_be_hidden()
        # Hold a request indefinitely, then advance the browser clock past the deadline.
        page.clock.install()
        hold_calculations = '''() => {
            window.originalFetch ||= window.fetch;
            window.fetch = (url, options) => url === '/api/calculate'
                ? new Promise((resolve, reject) => options.signal.addEventListener('abort',
                    () => reject(new DOMException('Aborted', 'AbortError'))))
                : window.originalFetch(url, options);
        }'''
        page.evaluate(hold_calculations)
        page.locator('[name=adi]').fill('82')
        page.clock.run_for(500)
        expect(page.locator('#calculate')).to_be_disabled()
        page.clock.run_for(15000)
        expect(page.locator('#calculation-error')).to_contain_text('demorou demais')
        expect(page.locator('#calculate')).to_be_enabled()
        page.unroute_all(behavior='ignoreErrors')
        page.evaluate('window.fetch = window.originalFetch')
        page.locator('#calculate').click()
        expect(page.locator('#save')).to_be_enabled()
        # Editing during an in-flight request cancels it and computes the latest input.
        page.evaluate(hold_calculations)
        page.locator('[name=adi]').fill('83')
        page.clock.run_for(500)
        expect(page.locator('#calculate')).to_be_disabled()
        page.unroute_all(behavior='ignoreErrors')
        page.evaluate('window.fetch = window.originalFetch')
        page.locator('[name=adi]').fill('84')
        page.clock.run_for(500)
        expect(page.locator('#save')).to_be_enabled()
        assert page.evaluate('lastResult.scenario.adi') == '84'
        assert not errors, errors
        browser.close()
        print('PASS: cleared optional fields, visible validation and retry after failure')


if __name__ == '__main__':
    main()
