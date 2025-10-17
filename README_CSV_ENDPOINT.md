# Endpoint de Procesamiento de CSV

## Descripción

Nuevo endpoint completamente independiente para procesar archivos CSV con información de personas. Este endpoint lee un archivo CSV, separa los nombres completos en sus componentes individuales y extrae campos específicos.

## Endpoint

```
POST /procesar-csv
```

## Parámetros

El endpoint acepta un archivo CSV mediante `multipart/form-data`:

- **file**: Archivo CSV (requerido)

## Estructura del CSV

El archivo CSV debe contener las siguientes columnas:

| Columna              | Descripción                           | Campo de salida | Alternativas aceptadas |
|---------------------|---------------------------------------|-----------------|------------------------|
| NOMBRES APELLIDOS Y | Nombre completo de la persona        | Se separa en 4 campos | NOMBRES COMPLETOS, NOMBRES Y APELLIDOS |
| No IDENTIFICACION   | Número de identificación             | numeroId        | - |
| CARGO               | Cargo o posición                     | cargo           | - |
| TELEFONOS           | Número de teléfono/celular          | celular         | - |
| CIUDAD              | Ciudad                               | ciudad          | - |

**Nota:** El endpoint acepta cualquiera de estos nombres para la columna de nombres completos:
- `NOMBRES APELLIDOS Y` ✅
- `NOMBRES COMPLETOS` ✅
- `NOMBRES Y APELLIDOS` ✅

## Lógica de Separación de Nombres

El nombre completo se separa automáticamente en:

- **primerNombre**: Primer nombre
- **segundoNombre**: Segundo nombre (si existe)
- **primerApellido**: Primer apellido
- **segundoApellido**: Segundo apellido (si existe)

### Ejemplos de separación:

- `JUAN PEREZ` → primerNombre: "JUAN", primerApellido: "PEREZ"
- `MARIA FERNANDA RODRIGUEZ` → primerNombre: "MARIA", segundoNombre: "FERNANDA", primerApellido: "RODRIGUEZ"
- `JUAN CARLOS PEREZ GOMEZ` → primerNombre: "JUAN", segundoNombre: "CARLOS", primerApellido: "PEREZ", segundoApellido: "GOMEZ"

## Respuesta

### Respuesta exitosa (200 OK):

```json
{
  "success": true,
  "total_registros": 5,
  "message": "CSV procesado exitosamente. 5 registros encontrados.",
  "datos": [
    {
      "fila": 1,
      "nombreCompleto": "JUAN CARLOS PEREZ GOMEZ",
      "primerNombre": "JUAN",
      "segundoNombre": "CARLOS",
      "primerApellido": "PEREZ",
      "segundoApellido": "GOMEZ",
      "numeroId": "1234567890",
      "cargo": "Ingeniero de Sistemas",
      "celular": "3001234567",
      "ciudad": "Bogotá"
    },
    {
      "fila": 2,
      "nombreCompleto": "MARIA FERNANDA RODRIGUEZ",
      "primerNombre": "MARIA",
      "segundoNombre": "FERNANDA",
      "primerApellido": "RODRIGUEZ",
      "segundoApellido": "",
      "numeroId": "9876543210",
      "cargo": "Gerente de Ventas",
      "celular": "3109876543",
      "ciudad": "Medellín"
    }
  ]
}
```

### Respuesta de error (500):

```json
{
  "success": false,
  "error": "Descripción del error"
}
```

## Ejemplo de Uso con cURL

```bash
curl -X POST http://localhost:8080/procesar-csv \
  -F "file=@ejemplo_csv_personas.csv"
```

## Ejemplo de Uso con Python

```python
import requests

url = "http://localhost:8080/procesar-csv"
files = {'file': open('ejemplo_csv_personas.csv', 'rb')}

response = requests.post(url, files=files)
data = response.json()

if data['success']:
    print(f"Total de registros procesados: {data['total_registros']}")
    for persona in data['datos']:
        print(f"- {persona['primerNombre']} {persona['primerApellido']}: {persona['cargo']}")
else:
    print(f"Error: {data['error']}")
```

## Ejemplo de Uso con JavaScript/Fetch

```javascript
const formData = new FormData();
const fileInput = document.querySelector('input[type="file"]');
formData.append('file', fileInput.files[0]);

fetch('http://localhost:8080/procesar-csv', {
  method: 'POST',
  body: formData
})
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      console.log(`Total de registros: ${data.total_registros}`);
      data.datos.forEach(persona => {
        console.log(`${persona.primerNombre} ${persona.primerApellido}: ${persona.cargo}`);
      });
    } else {
      console.error(`Error: ${data.error}`);
    }
  })
  .catch(error => console.error('Error:', error));
```

## CORS

El endpoint tiene CORS habilitado para todos los orígenes (`Access-Control-Allow-Origin: *`), permitiendo llamadas desde cualquier dominio.

## Manejo de Errores

El endpoint maneja los siguientes errores:

1. **No se envió archivo**: Si no se incluye el campo `file` en la petición
2. **Archivo vacío**: Si el nombre del archivo está vacío
3. **Formato incorrecto**: Si el archivo no tiene extensión `.csv`
4. **Errores de procesamiento**: Si hay problemas leyendo el CSV o procesando las filas

Los errores individuales en filas específicas se registran en la consola pero no detienen el procesamiento del resto del archivo.

## Archivo de Ejemplo

Se ha creado un archivo de ejemplo `ejemplo_csv_personas.csv` con el formato correcto para probar el endpoint.

## Notas Importantes

- El endpoint es completamente independiente de los demás endpoints del sistema
- No requiere autenticación
- El archivo CSV debe estar codificado en UTF-8
- Los nombres de columnas deben coincidir exactamente con los especificados
- Si una fila tiene errores, se incluirá en la respuesta con información del error
