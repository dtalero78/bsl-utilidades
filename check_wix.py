import requests
import json

# ID de historia clínica del paciente
wix_id = "8e7e484a-5579-4d08-a44e-360d0a7c7d89"

# Consultar datos de audiometría
audio_url = f"https://www.bsl.com.co/_functions/audiometriaPorIdGeneral?idGeneral={wix_id}"
response = requests.get(audio_url, timeout=10)
data = response.json()

print("=== DATOS DE AUDIOMETRÍA ===")
print("Response status:", response.status_code)
print("Data:", json.dumps(data, indent=2, ensure_ascii=False))
