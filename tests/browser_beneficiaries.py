"""Com servidor local iniciado: python tests/browser_beneficiaries.py."""
from playwright.sync_api import sync_playwright, expect


def check_relationships(page):
    page.goto('http://127.0.0.1:8000')
    page.locator('summary').filter(has_text='IPSEMG').first.click()
    add = page.locator('#add-beneficiary')
    rows = page.locator('.beneficiary')

    def choices(row):
        return row.locator('.relationship option').evaluate_all(
            '(options) => options.filter(o => o.value && !o.hidden && !o.disabled).map(o => o.value)')

    expect(rows).to_have_count(1)
    expect(rows.first.locator('.relationship')).to_have_value('')
    expect(rows.first.locator('.beneficiary-age')).to_be_disabled()
    expect(add).to_be_disabled()
    for relationship, allowed in [('parent', ['parent']), ('sibling', ['sibling']),
                                  ('spouse', ['child']), ('child', ['spouse'])]:
        rows.first.locator('.relationship').select_option(relationship)
        expect(add).to_be_enabled()
        add.click()
        assert choices(rows.nth(1)) == allowed
        expect(rows.nth(1).locator('.relationship')).to_have_value('')
        expect(add).to_be_disabled()
        rows.nth(1).locator('.relationship').select_option(allowed[0])
        if relationship == 'sibling':
            expect(add).to_be_visible()
            expect(add).to_be_enabled()
        else:
            expect(add).to_be_hidden()
        rows.nth(1).locator('.remove').click()
        expect(add).to_be_visible()
        assert choices(rows.first) == ['child', 'spouse', 'parent', 'sibling']
    rows.first.locator('.relationship').select_option('child')
    rows.first.locator('.beneficiary-age').fill('10')
    rows.first.locator('.special-condition').check()
    request = page.evaluate('scenario()')
    assert request['health_enrolled'] is True
    assert request['beneficiaries'][0]['exemption_approved'] is True
    rows.first.locator('.relationship').select_option('parent')
    request = page.evaluate('scenario()')
    assert request['beneficiaries'][0]['eligibility_confirmed'] is True
    rows.first.locator('.relationship').select_option('')
    assert page.evaluate('scenario().beneficiaries') == []
    page.locator('[name=alimony]').evaluate("el => {el.value = '500'; el.dispatchEvent(new Event('input', {bubbles:true}));}")
    assert page.evaluate('scenario().alimony_deductible') is True
    expect(page.locator('[name=alimony_deductible]')).to_have_count(0)
    expect(page.locator('[name=age]')).to_be_enabled()
    expect(page.locator('[name=copay]')).to_be_enabled()
    for selector in ['[name=health_enrolled]', '[name=special_health]',
                     '.exemption-approved', '.eligibility-confirmed']:
        expect(page.locator(selector)).to_have_count(0)


if __name__ == '__main__':
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox'])
        for width in [390, 1366]:
            check_relationships(browser.new_page(viewport={'width': width, 'height': 900}))
        browser.close()
    print('PASS: beneficiários guiados, pressupostos e controles IPSEMG')
