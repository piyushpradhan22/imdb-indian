import glob
import json
import logging
import os
import sys
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from concurrent import futures

logging.basicConfig(
    level=os.environ.get('CRAWL_LOG_LEVEL', 'INFO').upper(),
    format='%(asctime)s %(levelname)s [%(threadName)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('crawl_imdb.log', mode='w', encoding='utf-8'),
    ],
)
log = logging.getLogger('crawl_imdb')

METAHUB_URL = 'https://images.metahub.space/poster/medium/{}/img'

waitS = 3

VERIFICATION_MARKERS = ('verify you are human', 'human verification', 'captcha', '403 forbidden')

# Test mode: fewer pages/years/sections so a run finishes in a minute or two.
TEST_MODE = os.environ.get('CRAWL_TEST_MODE') == '1'
TEST_MAX_CLICKS = 1
if TEST_MODE:
    log.info('CRAWL_TEST_MODE enabled: limiting pages, years and sections')


def _looks_blocked(driver, url):
    """Log a warning if IMDb served a verification / 403 page instead of results."""
    title = (driver.title or '').lower()
    if any(marker in title for marker in VERIFICATION_MARKERS):
        log.warning('BLOCKED by IMDb (title=%r) for url=%s', driver.title, url)
        return True
    return False

# JS injected before page load so IMDb sees a normal human browser, not automation.
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


def _find_chromedriver():
    explicit = os.environ.get('CHROMEDRIVER_PATH')
    if explicit and os.path.exists(explicit):
        return explicit
    cache = os.path.expanduser('~/.cache/selenium/chromedriver')
    matches = sorted(glob.glob(os.path.join(cache, '**', 'chromedriver'), recursive=True))
    return matches[-1] if matches else None


def _find_chrome_binary():
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


def create_stealth_driver():
    options = webdriver.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1200,900')
    options.add_argument('--lang=en-US')
    options.add_argument('--disable-notifications')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)

    # IMDb serves 403/verification to headless Chrome; run headful under Xvfb on CI instead.
    if os.environ.get('CRAWL_HEADLESS') == '1':
        options.add_argument('--headless=new')

    binary = _find_chrome_binary()
    if binary:
        options.binary_location = binary

    driver_path = _find_chromedriver()
    service = Service(executable_path=driver_path) if driver_path else Service()

    headless = os.environ.get('CRAWL_HEADLESS') == '1'
    log.info('Launching Chrome (headless=%s, driver=%s, binary=%s)',
             headless, driver_path or 'selenium-manager', binary or 'auto')
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {'source': STEALTH_JS})
    return driver

year_filter='&release_date={}-01-01,{}-12-31'
hindi_filter = '&languages=hi'

def get_imdb_titles(url, loop=40):
    log.info('get_imdb_titles START url=%s', url)
    start = time.time()
    if TEST_MODE:
        loop = TEST_MAX_CLICKS
    with create_stealth_driver() as driver:
        driver.get(url)
        _looks_blocked(driver, url)
        actions = ActionChains(driver)
        
        xpath_next = "//span[@class='ipc-see-more__text']"
        xpath_imdb_elements = "//*[@class='ipc-metadata-list-summary-item__tc']"
        xpath_title = ".//a[contains(@href, 'ref_=sr_t_')]"
        xpath_type = ".//li[contains(@class, 'ipc-inline-list__item') and (contains(text(), 'TV Series') or contains(text(), 'TV Mini Series') or contains(text(), 'TV Special') or contains(text(), 'TV series') or contains(text(), 'Mini-Series'))]"  # Enhanced to catch more TV types

        for i in range(loop):

            try:
                WebDriverWait(driver, waitS).until(EC.presence_of_element_located((By.XPATH, xpath_next)))
            except:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                log.info('No more "see more" after %d clicks for url=%s', i, url)
                break

            next_ele = WebDriverWait(driver, waitS).until(EC.presence_of_element_located((By.XPATH, xpath_next)))
            actions.move_to_element(next_ele).perform()
            next_ele = WebDriverWait(driver, waitS).until(EC.presence_of_element_located((By.XPATH, xpath_next)))
            next_ele.click()
            log.debug('Clicked "see more" #%d for url=%s', i + 1, url)

        imdb_full = []
        cards = driver.find_elements(By.XPATH, xpath_imdb_elements)
        log.info('Extracting %d cards for url=%s', len(cards), url)
        for x in cards:
                title_elem = x.find_element(By.XPATH, xpath_title)
                data = {}
                data["id"] =  f"{title_elem.get_property('href').split('/')[4]}"
                
                data["type"] = 'movie' if len(x.find_elements(By.XPATH, xpath_type))==0 else 'series'
                data['poster'] = METAHUB_URL.format(title_elem.get_property("href").split("/")[4])
                data['name'] = title_elem.text.lstrip('0123456789. ')
                
                # Try multiple possible paths for releaseInfo and runtime
                release_elem = None
                runtime_elem = None
                
                
                # IMDb now uses li elements with class ipc-inline-list__item for metadata
                metadata_items = x.find_elements(By.XPATH, ".//li[contains(@class, 'ipc-inline-list__item')]")
                
                for item in metadata_items:
                    text = item.text.strip()
                    
                    # Check for release year
                    if not release_elem and len(text) >= 4 and text[:4].isdigit() and 1800 <= int(text[:4]) <= 2100:
                        release_elem = item
                        
                    # Check for runtime (contains digits and 'h' or 'm', usually like '2h 15m')
                    elif not runtime_elem and len(text) <= 15 and any(char.isdigit() for char in text) and ('h' in text.lower() or 'm' in text.lower()):
                        if '$' not in text:
                            runtime_elem = item
                
                data['releaseInfo'] = release_elem.text if release_elem else '0'
                data['runtime'] = runtime_elem.text if runtime_elem else '0h 0m'
                if len(x.find_elements(By.XPATH, ".//*[@class='ipc-rating-star--rating']")) > 0:
                    data['imdbRating'] = x.find_element(By.XPATH, ".//*[@class='ipc-rating-star--rating']").text
                else:
                    data['imdbRating'] = '0'
                if len(x.find_elements(By.XPATH, ".//*[@class='ipc-rating-star--voteCount']")) > 0:
                    data['votes'] = x.find_element(By.XPATH, ".//*[@class='ipc-rating-star--voteCount']").text
                else:
                    data['votes'] = '0'
                if len(x.find_elements(By.XPATH, ".//div/div[2]/div/div")) > 0:
                    data['description'] = x.find_element(By.XPATH, ".//div/div[2]/div/div").text
                else:
                    data['description'] = ''
                imdb_full.append(data)

        log.info('get_imdb_titles DONE url=%s items=%d elapsed=%.1fs',
                 url, len(imdb_full), time.time() - start)
        return imdb_full

def get_imdb_full(url, year_step=2):
    log.info('get_imdb_full START url=%s', url)
    start = time.time()
    with create_stealth_driver() as driver:
        imdb_full = []
        years = list(range(1990, 2026, year_step))
        if TEST_MODE:
            years = years[-1:]  # just the most recent bucket
        for year in years:
            year_url = url + year_filter.format(year, year + year_step - 1)
            driver.get(year_url)
            _looks_blocked(driver, year_url)
            actions = ActionChains(driver)

            xpath_next = "//span[@class='ipc-see-more__text']"
            xpath_imdb_elements = "//*[@class='ipc-metadata-list-summary-item__tc']"
            xpath_title = ".//a[contains(@href, 'ref_=sr_t_')]"
            xpath_type = ".//li[contains(@class, 'ipc-inline-list__item') and (contains(text(), 'TV Series') or contains(text(), 'TV Mini Series') or contains(text(), 'TV Special') or contains(text(), 'TV series') or contains(text(), 'Mini-Series'))]"
            clicks = 0
            while True:
            #for i in range(5):
                if TEST_MODE and clicks >= TEST_MAX_CLICKS:
                    break
                try:
                    WebDriverWait(driver, waitS).until(EC.presence_of_element_located((By.XPATH, xpath_next)))
                except:
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    break

                next_ele = WebDriverWait(driver, waitS).until(EC.presence_of_element_located((By.XPATH, xpath_next)))
                actions.move_to_element(next_ele).perform()
                next_ele = WebDriverWait(driver, waitS).until(EC.presence_of_element_located((By.XPATH, xpath_next)))
                next_ele.click()
                clicks += 1
            cards = driver.find_elements(By.XPATH, xpath_imdb_elements)
            log.info('year=%d cards=%d url=%s', year, len(cards), year_url)
            for x in cards:
                title_elem = x.find_element(By.XPATH, xpath_title)
                data = {}
                data["id"] =  f"{title_elem.get_property('href').split('/')[4]}"
                data["type"] = 'movie' if len(x.find_elements(By.XPATH, xpath_type))==0 else 'series'
                data['poster'] = METAHUB_URL.format(title_elem.get_property("href").split("/")[4])
                data['name'] = title_elem.text.lstrip('0123456789. ')
                
                # Try multiple possible paths for releaseInfo and runtime
                release_elem = None
                runtime_elem = None
                
                
                # IMDb now uses li elements with class ipc-inline-list__item for metadata
                metadata_items = x.find_elements(By.XPATH, ".//li[contains(@class, 'ipc-inline-list__item')]")
                
                for item in metadata_items:
                    text = item.text.strip()
                    
                    # Check for release year
                    if not release_elem and len(text) >= 4 and text[:4].isdigit() and 1800 <= int(text[:4]) <= 2100:
                        release_elem = item
                        
                    # Check for runtime (contains digits and 'h' or 'm', usually like '2h 15m')
                    elif not runtime_elem and len(text) <= 15 and any(char.isdigit() for char in text) and ('h' in text.lower() or 'm' in text.lower()):
                        if '$' not in text:
                            runtime_elem = item
                
                data['releaseInfo'] = release_elem.text if release_elem else '0'
                data['runtime'] = runtime_elem.text if runtime_elem else '0h 0m'
                if len(x.find_elements(By.XPATH, ".//*[@class='ipc-rating-star--rating']")) > 0:
                    data['imdbRating'] = x.find_element(By.XPATH, ".//*[@class='ipc-rating-star--rating']").text
                else:
                    data['imdbRating'] = '0'
                if len(x.find_elements(By.XPATH, ".//*[@class='ipc-rating-star--voteCount']")) > 0:
                    data['votes'] = x.find_element(By.XPATH, ".//*[@class='ipc-rating-star--voteCount']").text
                else:
                    data['votes'] = '0'
                if len(x.find_elements(By.XPATH, ".//div/div[2]/div/div")) > 0:
                    data['description'] = x.find_element(By.XPATH, ".//div/div[2]/div/div").text
                else:
                    data['description'] = ''

                imdb_full.append(data)
        
        log.info('get_imdb_full DONE url=%s items=%d elapsed=%.1fs',
                 url, len(imdb_full), time.time() - start)
        return imdb_full

### IMDB Full Details
imdb_urls = {
    "Indian Movies" : "https://www.imdb.com/search/title/?title_type=feature&num_votes=1000,&country_of_origin=IN",
    "Hindi Language" : "https://www.imdb.com/search/title/?title_type=feature,tv_series&primary_language=hi"
    }

log.info('=== Crawl started ===')
if TEST_MODE:
    imdb_urls = dict(list(imdb_urls.items())[:1])
full_imdb_dict = {}
for key in imdb_urls.keys():
    log.info('Full details: %s', key)
    full_imdb_dict[key] = get_imdb_full(imdb_urls[key])

log.info('Full detail sections done: %s', list(full_imdb_dict.keys()))

imdb_titles = {
                'Top Rated' : "https://www.imdb.com/search/title/?title_type=feature&user_rating=5,10&num_votes=2000,&country_of_origin=IN",
                'Movies' : "https://www.imdb.com/search/title/?title_type=feature&country_of_origin=IN",
                'Series' : "https://www.imdb.com/search/title/?title_type=tv_series&country_of_origin=IN",
                'Netflix India' : "https://www.imdb.com/search/title/?title_type=feature,tv_series&companies=co0944055",
                'Prime Video' : "https://www.imdb.com/search/title/?title_type=feature,tv_series&companies=co0939864",
                "Disney Plus Hotstar" : "https://www.imdb.com/search/title/?title_type=feature,tv_series&companies=co0847080",
                'Jio Cinema' : "https://www.imdb.com/search/title/?title_type=feature,tv_series&companies=co0808044",
                'Jio Hotstar' : "https://www.imdb.com/search/title/?title_type=feature,tv_series&companies=co1113006",
                'Zee5' : 'https://www.imdb.com/search/title/?title_type=feature,tv_series&companies=co0692549',
                'Sony Liv' : 'https://www.imdb.com/search/title/?title_type=feature,tv_series&companies=co0546496'
               }

types = [x for x in imdb_titles]
urls = [imdb_titles[x] for x in imdb_titles]

if TEST_MODE:
    types = types[:2]
    urls = urls[:2]

log.info('Title crawl: %d sections in parallel', len(urls))
with futures.ThreadPoolExecutor(max_workers=4) as executor: # default/optimized number of threads
  title_res = list(executor.map(get_imdb_titles, urls))

imdb_dict = {}

for i in range(len(title_res)):
    imdb_dict[types[i]] = title_res[i]

out_file = 'data.test.json' if TEST_MODE else 'data.json'
with open(out_file, 'w') as f:
    json.dump(imdb_dict | full_imdb_dict, f)

log.info('Wrote %s (%d title sections, %d full sections)',
         out_file, len(imdb_dict), len(full_imdb_dict))
log.info('=== Completed ===')