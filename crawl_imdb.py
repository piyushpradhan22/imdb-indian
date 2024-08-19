import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from concurrent import futures

METAHUB_URL = 'https://images.metahub.space/poster/medium/{}/img'

waitS = 5

def get_imdb_titles(url):
    with webdriver.Chrome() as driver:
        driver.set_window_size(700, 700)
        driver.get(url)
        actions = ActionChains(driver)

        xpath_next = "//span[@class='ipc-see-more__text']"
        xpath_imdb_elements = "//*[@class='ipc-metadata-list-summary-item__tc']"
        xpath_title = ".//*[@class='ipc-lockup-overlay ipc-focusable']"
        xpath_type = ".//span[contains(text(), 'TV Series')]"

        for i in range(20):

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

imdb_titles = {
                'Movies' : "https://www.imdb.com/search/title/?title_type=feature&countries=IN",
               'Series' : "https://www.imdb.com/search/title/?title_type=tv_series&countries=IN",
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
    json.dump(imdb_dict, f)