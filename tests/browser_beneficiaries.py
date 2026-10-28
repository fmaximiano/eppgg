"""Com servidor local iniciado: python tests/browser_beneficiaries.py."""
from playwright.sync_api import sync_playwright, expect


def check_relationships(page):
    page.goto('http://127.0.0.1:8000')
    page.locator('summary').filter(has_text='IPSEMG').first.click()
    page.locator('[name=health_enrolled]').check()
    add = page.locator('#add-beneficiary')
    rows = page.locator('.beneficiary')

    def choices(row):
        return row.locator('.relationship option').evaluate_all(
            '(options) => options.filter(o => !o.hidden && !o.disabled).map(o => o.value)')

    add.click()
    assert choices(rows.first) == ['child', 'spouse', 'parent', 'sibling']
    for relationship, allowed in [('parent', ['parent']), ('sibling', ['sibling']),
                                  ('spouse', ['child', 'spouse']), ('child', ['child', 'spouse'])]:
        rows.first.locator('.relationship').select_option(relationship)
        add.click()
        assert choices(rows.nth(1)) == allowed
        assert choices(rows.first) == allowed
        assert rows.nth(1).locator('.relationship').input_value() == allowed[0]
        rows.nth(1).locator('.remove').click()
        assert choices(rows.first) == ['child', 'spouse', 'parent', 'sibling']
    rows.first.locator('.remove').click()
    add.click()
    expect(rows.first.locator('.relationship')).to_have_value('child')


if __name__ == '__main__':
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox'])
        check_relationships(browser.new_page())
        browser.close()
    print('PASS: parentescos compatíveis após inclusão, alteração e remoção')
