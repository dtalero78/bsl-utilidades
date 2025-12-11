import requests
import json

# Usar la función de BSL que consulta Wix
url = "https://www.bsl.com.co/_functions/historiaClinicaPorNumeroId?numeroId=1023934560"

response = requests.get(url, timeout=10)
data = response.json()

print("Response status:", response.status_code)
print("Data:", json.dumps(data, indent=2, ensure_ascii=False))
