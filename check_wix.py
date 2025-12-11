# Simular el mapeo
MAPEO_EXAMENES = {
    "Examen Médico Osteomuscular": "EXAMEN MÉDICO OCUPACIONAL OSTEOMUSCULAR",
}

textos_examenes = {
    "EXAMEN MÉDICO OCUPACIONAL OSTEOMUSCULAR": "Texto osteomuscular...",
}

examen_original = "Examen Médico Osteomuscular"
examen_normalizado = MAPEO_EXAMENES.get(examen_original.strip(), examen_original.strip())

print(f"Examen original: '{examen_original}'")
print(f"Examen normalizado: '{examen_normalizado}'")
print(f"Existe en textos_examenes: {examen_normalizado in textos_examenes}")
print(f"Resultado búsqueda: {textos_examenes.get(examen_normalizado, 'NO ENCONTRADO')}")
