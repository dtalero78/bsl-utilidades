#!/usr/bin/env python3
"""
Script de prueba para la integración de Whapi
"""

import sys
import requests

# Configuración
WHAPI_TOKEN = 'due3eWCwuBM2Xqd6cPujuTRqSbMb68lt'
WHAPI_BASE_URL = 'https://gate.whapi.cloud'
WHAPI_PHONE_NUMBER = '573008021701'

def test_obtener_chats():
    """Prueba obtener lista de chats de Whapi"""
    print("\n" + "="*60)
    print("TEST: Obtener chats de Whapi")
    print("="*60)

    try:
        url = f"{WHAPI_BASE_URL}/chats"
        headers = {
            "accept": "application/json",
            "authorization": f"Bearer {WHAPI_TOKEN}"
        }

        print(f"URL: {url}")
        print(f"Token: {WHAPI_TOKEN[:20]}...")

        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        data = response.json()
        chats = data.get('chats', [])

        print(f"\n✅ SUCCESS: Obtenidos {len(chats)} chats")

        if chats:
            print(f"\nPrimeros 3 chats:")
            for i, chat in enumerate(chats[:3], 1):
                chat_id = chat.get('id', 'N/A')
                name = chat.get('name', 'Sin nombre')
                last_msg = chat.get('last_message', {})
                last_msg_text = last_msg.get('text', {}).get('body', '(sin texto)') if last_msg else '(sin mensajes)'

                print(f"\n{i}. Chat ID: {chat_id}")
                print(f"   Nombre: {name}")
                print(f"   Último mensaje: {last_msg_text[:50]}...")

        return True
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_obtener_mensajes(chat_id=None):
    """Prueba obtener mensajes de un chat específico"""
    print("\n" + "="*60)
    print("TEST: Obtener mensajes de un chat")
    print("="*60)

    if not chat_id:
        # Primero obtener un chat_id de ejemplo
        try:
            url = f"{WHAPI_BASE_URL}/chats"
            headers = {
                "accept": "application/json",
                "authorization": f"Bearer {WHAPI_TOKEN}"
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            chats = data.get('chats', [])

            if chats:
                chat_id = chats[0].get('id')
                print(f"Usando chat de ejemplo: {chat_id}")
            else:
                print("❌ No hay chats disponibles para probar")
                return False
        except Exception as e:
            print(f"❌ Error obteniendo chats: {str(e)}")
            return False

    try:
        url = f"{WHAPI_BASE_URL}/messages/list/{chat_id}"
        headers = {
            "accept": "application/json",
            "authorization": f"Bearer {WHAPI_TOKEN}"
        }
        params = {
            "count": 5  # Últimos 5 mensajes
        }

        print(f"URL: {url}")
        print(f"Chat ID: {chat_id}")

        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()
        messages = data.get('messages', [])

        print(f"\n✅ SUCCESS: Obtenidos {len(messages)} mensajes")

        if messages:
            print(f"\nPrimeros 3 mensajes:")
            for i, msg in enumerate(messages[:3], 1):
                msg_id = msg.get('id', 'N/A')
                from_me = msg.get('from_me', False)
                msg_type = msg.get('type', 'unknown')
                body = msg.get('text', {}).get('body', '(no texto)') if msg_type == 'text' else f'({msg_type})'

                print(f"\n{i}. Mensaje ID: {msg_id}")
                print(f"   De mí: {from_me}")
                print(f"   Tipo: {msg_type}")
                print(f"   Contenido: {body[:50]}...")

        return True
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("\n" + "="*60)
    print("PRUEBA DE INTEGRACIÓN CON WHAPI")
    print(f"Línea WhatsApp: {WHAPI_PHONE_NUMBER}")
    print("="*60)

    # Test 1: Obtener chats
    test1_passed = test_obtener_chats()

    # Test 2: Obtener mensajes
    test2_passed = test_obtener_mensajes()

    # Resumen
    print("\n" + "="*60)
    print("RESUMEN DE PRUEBAS")
    print("="*60)
    print(f"Test 1 (Obtener chats): {'✅ PASS' if test1_passed else '❌ FAIL'}")
    print(f"Test 2 (Obtener mensajes): {'✅ PASS' if test2_passed else '❌ FAIL'}")

    if test1_passed and test2_passed:
        print("\n✅ Todas las pruebas pasaron exitosamente!")
        print("La integración con Whapi está funcionando correctamente.")
        return 0
    else:
        print("\n❌ Algunas pruebas fallaron.")
        print("Revisa los logs arriba para más detalles.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
