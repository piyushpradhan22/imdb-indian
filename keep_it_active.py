import requests

try:
    requests.get("https://dekibov972-stremio.hf.space/tor/catalog/Indian/TORRENT.json").json()
    print("Stremio is running Well")
except Exception as e:
    print(f"Stremio request failed: {e}")
try:
    response = requests.get("hhttp://140.245.234.113:7860/")
    if 'content="qBittorrent WebUI' in response.text:
        print("QB is running Well")
    else:
        print("QB is not running Well", response.text)
except Exception as e:
    print(f"QB request failed: {e}")
