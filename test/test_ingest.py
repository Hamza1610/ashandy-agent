import requests

url = "https://ashandy.storeapp.com.ng/phppos/index.php/api/v1/items"

headers = {
    "Accept": "application/json",
    "X-API-KEY": "skowks8gkwgooo0os0g80goskg484ocscsckowww",
    "User-Agent": "curl/8.5.0"
}

resp = requests.get(url, headers=headers)
print(resp.status_code)
print(resp.text)
