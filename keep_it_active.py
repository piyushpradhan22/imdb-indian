import requests

try:
    requests.get("https://hellopiyush0003-stremio.hf.space/tor/catalog/Indian/TORRENT.json").json()
    print("Stremio is running Well")
except Exception as e:
    print(f"Stremio request failed: {e}")
try:
    response = requests.get("https://hellopiyush0003-qb.hf.space/")
    if 'content="qBittorrent WebUI' in response.text:
        print("QB is running Well")
    else:
        print("QB is not running Well", response.text)
except Exception as e:
    print(f"QB request failed: {e}")