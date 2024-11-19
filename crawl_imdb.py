import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from concurrent import futures
import random

METAHUB_URL = 'https://images.metahub.space/poster/medium/{}/img'

waitS = 5

options = webdriver.ChromeOptions()
options.add_argument('--no-sandbox')
options.add_argument('--headless')
options.add_argument('--disable-gpu')
options.add_argument('--disable-dev-shm-usage')
options.add_argument("--window-size=700,700")

year_filter='&release_date={}-01-01,{}-12-31'
hindi_filter = '&languages=hi'

def get_imdb_titles(url, loop=40):
    with webdriver.Chrome() as driver:
        driver.get(url)
        actions = ActionChains(driver)

        xpath_next = "//span[@class='ipc-see-more__text']"
        xpath_imdb_elements = "//*[@class='ipc-metadata-list-summary-item__tc']"
        xpath_title = ".//*[@class='ipc-lockup-overlay ipc-focusable']"
        xpath_type = ".//span[contains(text(), 'TV Series')]"

        for i in range(loop):

            try:
                WebDriverWait(driver, waitS).until(EC.presence_of_element_located((By.XPATH, xpath_next)))
            except:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                break

            next_ele = WebDriverWait(driver, waitS).until(EC.presence_of_element_located((By.XPATH, xpath_next)))
            actions.move_to_element(next_ele).perform()
            next_ele = WebDriverWait(driver, waitS).until(EC.presence_of_element_located((By.XPATH, xpath_next)))
            next_ele.click()

        imdb_titles = [{"id" :  x.find_element(By.XPATH, xpath_title).get_property("href").split("/")[4], 
                        "type" : 'movie' if len(x.find_elements(By.XPATH, xpath_type))==0 else 'series', 
                        'poster' : METAHUB_URL.format(x.find_element(By.XPATH, xpath_title).get_property("href").split("/")[4])} 
                        for x in driver.find_elements(By.XPATH, xpath_imdb_elements)]
        
        return imdb_titles

def get_imdb_full(url, year_step=5):
    with webdriver.Chrome() as driver:
        imdb_full = []
        for year in range(1990, 2025, year_step):
            driver.get(url+year_filter.format(year, year+year_step-1))
            actions = ActionChains(driver)

            xpath_next = "//span[@class='ipc-see-more__text']"
            xpath_imdb_elements = "//*[@class='ipc-metadata-list-summary-item__tc']"
            xpath_title = ".//*[@class='ipc-lockup-overlay ipc-focusable']"
            xpath_type = ".//span[contains(text(), 'TV Series')]"

            while True:
            #for i in range(5):
                try:
                    WebDriverWait(driver, waitS).until(EC.presence_of_element_located((By.XPATH, xpath_next)))
                except:
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    break

                next_ele = WebDriverWait(driver, waitS).until(EC.presence_of_element_located((By.XPATH, xpath_next)))
                actions.move_to_element(next_ele).perform()
                next_ele = WebDriverWait(driver, waitS).until(EC.presence_of_element_located((By.XPATH, xpath_next)))
                next_ele.click()
            imdb_full.extend([{"id" :  x.find_element(By.XPATH, xpath_title).get_property("href").split("/")[4], 
                            "type" : 'movie' if len(x.find_elements(By.XPATH, xpath_type))==0 else 'series', 
                            'title' : x.find_element(By.XPATH, ".//*[@class='ipc-title__text']").text.split(". ",1)[1],
                            'year' : x.find_element(By.XPATH, ".//div/div/div[2]/div/span[1]").text,
                            #'rtime' : x.find_element(By.XPATH, ".//div/div/div[2]/div/span[2]").text,
                            'rating' : x.find_element(By.XPATH, ".//*[@class='ipc-rating-star--rating']").text,
                            'votes' : x.find_element(By.XPATH, ".//*[@class='ipc-rating-star--voteCount']").text,
                            #'descr' : x.find_element(By.XPATH, ".//div/div[2]/div/div").text,
                            } 
                            for x in driver.find_elements(By.XPATH, xpath_imdb_elements)])
        
        return imdb_full

### IMDB Full Details
imdb_urls = {
    "Indian Movies" : "https://www.imdb.com/search/title/?title_type=feature&num_votes=1000,&country_of_origin=IN",
    }
for key in imdb_urls.keys():
    full_imdb_dict = {key : get_imdb_full("https://www.imdb.com/search/title/?title_type=feature&num_votes=1000,&country_of_origin=IN")}

print(full_imdb_dict.keys())

imdb_titles = {
                'Top Rated' : "https://www.imdb.com/search/title/?title_type=feature&user_rating=5,10&num_votes=2000,&country_of_origin=IN",
                'Movies' : "https://www.imdb.com/search/title/?title_type=feature&country_of_origin=IN",
                'Series' : "https://www.imdb.com/search/title/?title_type=tv_series&country_of_origin=IN",
                'Netflix India' : "https://www.imdb.com/search/title/?title_type=feature,tv_series&companies=co0944055",
                'Prime Video' : "https://www.imdb.com/search/title/?title_type=feature,tv_series&companies=co0939864",
                "Disney Plus Hotstar" : "https://www.imdb.com/search/title/?title_type=feature,tv_series&companies=co0847080",
                'Jio Cinema' : "https://www.imdb.com/search/title/?title_type=feature,tv_series&companies=co0808044",
                'Zee5' : 'https://www.imdb.com/search/title/?title_type=feature,tv_series&companies=co0692549',
                'Sony Liv' : 'https://www.imdb.com/search/title/?title_type=feature,tv_series&companies=co0546496'
               }

types = [x for x in imdb_titles]
urls = [imdb_titles[x] for x in imdb_titles]

with futures.ThreadPoolExecutor(max_workers=4) as executor: # default/optimized number of threads
  title_res = list(executor.map(get_imdb_titles, urls))

imdb_dict = {}

for i in range(len(title_res)):
    imdb_dict[types[i]] = title_res[i]

with open('data.json', 'w') as f:
    json.dump(imdb_dict | full_imdb_dict, f)

print("Completed")