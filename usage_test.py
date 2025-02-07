import requests


headers = {
    "Authorization": f'Bearer my_token',
}

response = requests.get("http://127.0.0.1:5000/questions",  headers=headers)

response_json = response.json()
print(response.status_code)
print(response_json)
