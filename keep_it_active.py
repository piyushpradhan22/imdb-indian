import requests

try:
    requests.get("https://dekibov972-stremio.hf.space/tor/catalog/Indian/TORRENT.json").json()
    print("Stremio is running Well")
except Exception as e:
    print(f"Stremio request failed: {e}")
try:
    response = requests.get("https://guzowskilynottmvvy49011733757114-qb.hf.space/")
    if 'content="qBittorrent WebUI' in response.text:
        print("QB is running Well")
    else:
        print("QB is not running Well", response.text)
except Exception as e:
    print(f"QB request failed: {e}")
try:
    requests.get("https://guzowskilynottmvvy49011733757114-ptn.hf.space").json()
    print("PTN is running Well")
except Exception as e:
    print(f"PTN request failed: {e}")
