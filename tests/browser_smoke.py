"""Exercise the explicit demo through a real browser and capture desktop/mobile views.

Run with a dedicated demo account and server; this intentionally creates a completed
task and a reviewed evidence version in that demonstration workspace. Credentials
are read from a private local file and never printed.
"""
import argparse
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import uuid

from playwright.sync_api import sync_playwright, expect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    parser.add_argument('--username', required=True)
    parser.add_argument('--password-file', required=True, type=Path)
    parser.add_argument('--chromium', help='Optional installed Chromium executable')
    parser.add_argument('--output', type=Path, default=Path('test-results'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright, TemporaryDirectory() as temporary:
        options = {'headless': True}
        if args.chromium:
            options['executable_path'] = args.chromium
        browser = playwright.chromium.launch(**options)
        page = browser.new_page(viewport={'width': 1440, 'height': 1100})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(args.base_url + '/accounts/login/')
        page.get_by_label('Username').fill(args.username)
        page.get_by_label('Password', exact=True).fill(args.password_file.read_text().strip())
        page.get_by_role('button', name='Sign in').click()
        page.wait_for_url(args.base_url + '/')
        expect(page.locator('.demo-label')).to_have_text('DEMO DATA')
        expect(page.locator('.metric-card')).to_have_count(4)
        assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
        page.screenshot(path=str(args.output / 'dashboard-desktop.png'), full_page=True)
        for route in ['roadmap/', 'records/risks/', 'records/controls/', 'records/documents/', 'records/evidence/', 'records/audits/', 'approvals/', 'settings/']:
            response = page.goto(args.base_url + '/' + route)
            assert response.status == 200, (route, response.status)
            expect(page.locator('h1')).to_be_visible()
        page.goto(args.base_url + '/traceability/')
        expect(page.locator('.graph-node')).not_to_have_count(0)
        page.screenshot(path=str(args.output / 'traceability-desktop.png'), full_page=True)
        token = uuid.uuid4().hex[:8]
        task_title = f'Browser validation {token}'
        page.goto(args.base_url + '/records/tasks/new/')
        page.locator('#id_title').fill(task_title)
        page.locator('#id_required_output').fill('Complete the browser-driven demonstration journey.')
        page.get_by_role('button', name='Save record').click()
        expect(page.locator('h1')).to_have_text(task_title)
        page.get_by_role('button', name='Start work', exact=True).click()
        expect(page.locator('.detail-heading-meta .badge')).to_have_text('In progress')
        completion = page.locator('form[action$="/action/complete/"]')
        completion.locator('[name="reason"]').fill('Completed the representative UI journey using saved records.')
        completion.get_by_role('button').click()
        expect(page.locator('.detail-heading-meta .badge')).to_have_text('Complete')
        proof = Path(temporary) / 'browser-demo-evidence.txt'
        proof.write_text('Fictional demonstration evidence from the browser smoke test.\n')
        page.goto(args.base_url + '/records/evidence/new/')
        page.locator('#id_title').fill(f'Browser evidence {token}')
        page.locator('#id_collected_on').fill(date.today().isoformat())
        page.locator('#id_file').set_input_files(proof)
        page.get_by_role('button', name='Save record').click()
        expect(page.locator('.detail-heading-meta .badge')).to_have_text('Uploaded')
        review = page.locator('form[action$="/action/review_evidence/"]')
        review.locator('[name="reason"]').fill('Reviewed fictional file and confirmed its demonstration purpose.')
        review.get_by_role('button').click()
        expect(page.locator('.detail-heading-meta .badge')).to_have_text('Reviewed')
        with page.expect_download() as download_info:
            page.get_by_role('link', name='Download', exact=True).click()
        download = download_info.value
        downloaded_path = Path(download.path())
        assert downloaded_path.read_bytes() == proof.read_bytes()
        page.goto(args.base_url + '/records/risks/')
        for name in ['Export CSV', 'XLSX', 'PDF']:
            with page.expect_download() as result:
                page.get_by_role('link', name=name, exact=True).click()
            assert Path(result.value.path()).stat().st_size > 50
        page.goto(args.base_url + '/search/?q=' + token)
        expect(page.get_by_text(task_title, exact=True)).to_be_visible()
        page.set_viewport_size({'width': 390, 'height': 844})
        page.goto(args.base_url + '/')
        assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
        page.screenshot(path=str(args.output / 'dashboard-mobile.png'), full_page=True)
        menu = page.locator('[data-toggle-sidebar]')
        menu.click()
        expect(menu).to_have_attribute('aria-expanded', 'true')
        page.keyboard.press('Escape')
        expect(menu).to_have_attribute('aria-expanded', 'false')
        assert not errors, errors
        browser.close()
    print('Browser journey passed: login, dashboard, registers, settings, traceability, task create/start/complete, evidence upload/review/download, CSV/XLSX/PDF exports, search, and mobile navigation. No browser script errors.')


if __name__ == '__main__':
    main()
