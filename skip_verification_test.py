"""Minimal test: open IMDb fully automated and skip the "Human Verification" page.

Run:
    python skip_verification_test.py

The stealth flags + CDP patch below make Chrome look like a normal human browser
(no navigator.webdriver, no automation switches), so IMDb serves real results
instead of the verification wall. No human interaction required.
"""
import glob
import os
import sys
import time

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

URL = 'https://www.imdb.com/search/title/?title_type=feature&num_votes=1000,&country_of_origin=IN'
RESULT_XPATH = "//*[@class='ipc-metadata-list-summary-item__tc']"
NEXT_XPATH = "//span[@class='ipc-see-more__text']"
TITLE_XPATH = ".//a[contains(@href, 'ref_=sr_t_')]"
VERIFICATION_MARKERS = ('verify you are human', 'human verification', 'captcha')

STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
window.chrome = window.chrome || {runtime: {}};
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications'
        ? Promise.resolve({state: Notification.permission})
        : originalQuery(parameters)
);
"""


def find_chromedriver():
    explicit = os.environ.get('CHROMEDRIVER_PATH')
    if explicit and os.path.exists(explicit):
        return explicit
    cache = os.path.expanduser('~/.cache/selenium/chromedriver')
    matches = sorted(glob.glob(os.path.join(cache, '**', 'chromedriver'), recursive=True))
    return matches[-1] if matches else None


def find_chrome_binary():
    explicit = os.environ.get('CHROME_BINARY')
    if explicit and os.path.exists(explicit):
        return explicit
    for candidate in (
        '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '/Applications/Chromium.app/Contents/MacOS/Chromium',
    ):
        if os.path.exists(candidate):
            return candidate
    return None


def make_stealth_driver(headless=False):
    options = webdriver.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1200,900')
    options.add_argument('--lang=en-US')
    options.add_argument('--disable-notifications')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)
    if headless:
        options.add_argument('--headless=new')

    binary = find_chrome_binary()
    if binary:
        options.binary_location = binary

    driver_path = find_chromedriver()
    service = Service(executable_path=driver_path) if driver_path else Service()

    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {'source': STEALTH_JS})
    return driver


def has_verification(driver):
    text = f'{driver.title}\n{driver.page_source}'.lower()
    return any(marker in text for marker in VERIFICATION_MARKERS)


def click_next(driver, max_clicks=3, wait_s=4):
    """Replicate the real crawler's 'see more' pagination. Returns clicks done."""
    actions = ActionChains(driver)
    clicks = 0
    for _ in range(max_clicks):
        try:
            next_ele = WebDriverWait(driver, wait_s).until(
                EC.presence_of_element_located((By.XPATH, NEXT_XPATH))
            )
        except Exception:
            break
        actions.move_to_element(next_ele).perform()
        try:
            next_ele.click()
        except Exception:
            driver.execute_script('arguments[0].click();', next_ele)
        clicks += 1
        time.sleep(2)
    return clicks


def extract_sample(driver, limit=3):
    """Replicate the real crawler's element extraction on the first few cards."""
    sample = []
    for x in driver.find_elements(By.XPATH, RESULT_XPATH)[:limit]:
        title_elem = x.find_element(By.XPATH, TITLE_XPATH)
        href = title_elem.get_property('href')
        rating = x.find_elements(By.XPATH, ".//*[@class='ipc-rating-star--rating']")
        sample.append({
            'id': href.split('/')[4],
            'name': title_elem.text.lstrip('0123456789. '),
            'rating': rating[0].text if rating else '0',
        })
    return sample


def main():
    headless = '--headless' in sys.argv
    driver = make_stealth_driver(headless=headless)
    try:
        driver.get(URL)

        deadline = time.time() + 25
        while time.time() < deadline:
            if driver.find_elements(By.XPATH, RESULT_XPATH):
                break
            time.sleep(1)

        verification = has_verification(driver)
        before = len(driver.find_elements(By.XPATH, RESULT_XPATH))

        clicks = click_next(driver, max_clicks=3)
        after = len(driver.find_elements(By.XPATH, RESULT_XPATH))
        sample = extract_sample(driver, limit=3)

        print(f'Title: {driver.title}')
        print(f'navigator.webdriver: {driver.execute_script("return navigator.webdriver")}')
        print(f'Verification shown: {verification}')
        print(f'Result cards before clicking: {before}')
        print(f'"See more" clicks performed: {clicks}')
        print(f'Result cards after clicking: {after}')
        print('Sample extracted elements:')
        for item in sample:
            print(f'  - {item}')

        ok = (not verification) and before > 0 and clicks > 0 and after > before and len(sample) > 0
        if ok:
            print('PASS: verification skipped, next clicked, more elements loaded and extracted.')
            return 0
        print('FAIL: see details above.')
        return 1
    finally:
        driver.quit()


if __name__ == '__main__':
    raise SystemExit(main())
