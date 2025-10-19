import requests
from bs4 import BeautifulSoup
import re
import json
from concurrent.futures import ThreadPoolExecutor

def YoutubeSearch(query, max_results=5):
    url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
    response = requests.get(url)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")

    # Extract the JSON inside the script tag containing 'ytInitialData'
    scripts = soup.find_all("script")
    initial_data = None
    for script in scripts:
        if "var ytInitialData" in script.text:
            matched = re.search(r"var ytInitialData = ({.*?});", script.string or script.text)
            if matched:
                initial_data = json.loads(matched.group(1))
                break

    if not initial_data:
        print("Error: initial data not found")
        return []

    # Traverse JSON to get videos
    try:
        contents = initial_data["contents"]["twoColumnSearchResultsRenderer"]["primaryContents"] \
            ["sectionListRenderer"]["contents"]
        video_items = []
        for content in contents:
            if "itemSectionRenderer" in content:
                items = content["itemSectionRenderer"]["contents"]
                for item in items:
                    if "videoRenderer" in item:
                        video_items.append(item["videoRenderer"])
                        if len(video_items) >= max_results:
                            break
            if len(video_items) >= max_results:
                break
    except KeyError:
        print("Error: unexpected JSON structure")
        return []

    # Extract video id and title
    results = []
    for video in video_items:
        video_id = video.get("videoId", "")
        title_runs = video.get("title", {}).get("runs", [])
        title = title_runs[0]["text"] if title_runs else "No title"
        results.append({"id": video_id, "title": title})

    return results

def get_youtube_info(x):
    query = f"{x.get('name')} {x.get('year')[:4]} trailer"
    result = YoutubeSearch(query, max_results=1)
    
    if result:
        x['yt_id'] = result[0].get('id', '')
        x['yt_title'] = result[0].get('title', '')
    else:
        x['yt_id'] = ''
        x['yt_title'] = ''
    
    return x

def update_data_with_youtube_links():
    with open('data.json', 'r') as file:
        data = json.load(file)
    
    # Create new dictionary structure
    youtube_data = {}
    
    with ThreadPoolExecutor() as executor:
        for keys in data.keys():
            # Process movies and get YouTube info
            updated_movies = list(executor.map(get_youtube_info, data[keys][:2]))
            
            # Transform to new structure
            for movie in updated_movies:
                movie_id = movie.get('id', '')
                if movie_id:
                    youtube_data[movie_id] = {
                        'yt_id': movie.get('yt_id', ''),
                        'yt_title': movie.get('yt_title', '')
                    }
    
    with open('yt_meta.json', 'w') as file:
        json.dump(youtube_data, file, indent=4)
        
if __name__ == "__main__":
    update_data_with_youtube_links()