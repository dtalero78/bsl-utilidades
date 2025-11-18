#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for Twilio-BSL WhatsApp integration
Tests all endpoints and functionality
"""

import os
import sys
import requests
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
BASE_URL = os.getenv('TEST_BASE_URL', 'http://localhost:5001')
TEST_PHONE = os.getenv('TEST_PHONE', '+573001234567')

def test_health_check():
    """Test health check endpoint"""
    print("\n" + "="*60)
    print("TEST: Health Check")
    print("="*60)

    try:
        response = requests.get(f'{BASE_URL}/health', timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")

        if response.status_code == 200:
            print("✅ Health check PASSED")
            return True
        else:
            print("❌ Health check FAILED")
            return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

def test_get_conversaciones():
    """Test get all conversations"""
    print("\n" + "="*60)
    print("TEST: Get All Conversations")
    print("="*60)

    try:
        response = requests.get(f'{BASE_URL}/api/conversaciones', timeout=30)
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"Success: {data.get('success')}")
            print(f"Total conversations: {data.get('total')}")

            if data.get('conversaciones'):
                print(f"\nFirst conversation:")
                first_key = list(data['conversaciones'].keys())[0]
                first_conv = data['conversaciones'][first_key]
                print(f"  Number: {first_key}")
                print(f"  Name: {first_conv.get('nombre', 'N/A')}")
                print(f"  Twilio messages: {len(first_conv.get('twilio_messages', []))}")
                print(f"  Stop bot: {first_conv.get('stopBot', False)}")

            print("✅ Get conversations PASSED")
            return True
        else:
            print(f"Response: {response.text}")
            print("❌ Get conversations FAILED")
            return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

def test_get_conversacion(numero):
    """Test get specific conversation"""
    print("\n" + "="*60)
    print(f"TEST: Get Specific Conversation ({numero})")
    print("="*60)

    # Remove + prefix if present
    numero_clean = numero.replace('+', '')

    try:
        response = requests.get(f'{BASE_URL}/api/conversacion/{numero_clean}', timeout=30)
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"Success: {data.get('success')}")
            print(f"Number: {data.get('numero')}")

            if data.get('wix_data'):
                wix = data['wix_data']
                print(f"Wix messages: {len(wix.get('mensajes', []))}")
                print(f"Stop bot: {wix.get('stopBot', False)}")
                print(f"Observations: {wix.get('observaciones', 'None')}")

            print(f"Twilio messages: {len(data.get('twilio_messages', []))}")

            print("✅ Get conversation PASSED")
            return True
        else:
            print(f"Response: {response.text}")
            print("⚠️ Get conversation FAILED (may be normal if no conversation exists)")
            return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

def test_enviar_mensaje(numero, mensaje):
    """Test sending message"""
    print("\n" + "="*60)
    print(f"TEST: Send Message to {numero}")
    print("="*60)
    print(f"Message: {mensaje}")

    # Ask for confirmation
    confirm = input("\n⚠️ This will send a real WhatsApp message. Continue? (y/N): ")
    if confirm.lower() != 'y':
        print("❌ Test SKIPPED by user")
        return False

    try:
        payload = {
            'to': numero,
            'message': mensaje
        }

        response = requests.post(
            f'{BASE_URL}/api/enviar-mensaje',
            json=payload,
            timeout=30
        )

        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")

        if response.status_code == 200 and response.json().get('success'):
            print("✅ Send message PASSED")
            return True
        else:
            print("❌ Send message FAILED")
            return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

def test_web_interface():
    """Test web interface loads"""
    print("\n" + "="*60)
    print("TEST: Web Interface")
    print("="*60)

    try:
        response = requests.get(f'{BASE_URL}/', timeout=10)
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            html = response.text
            if 'Twilio-BSL WhatsApp Chat' in html:
                print("✅ Web interface PASSED")
                print(f"\n📱 Access the interface at: {BASE_URL}/")
                return True
            else:
                print("❌ Web interface content incorrect")
                return False
        else:
            print("❌ Web interface FAILED")
            return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

def test_static_files():
    """Test static files are accessible"""
    print("\n" + "="*60)
    print("TEST: Static Files")
    print("="*60)

    files_to_test = [
        '/static/twilio/css/chat.css',
        '/static/twilio/js/chat.js'
    ]

    all_passed = True

    for file_path in files_to_test:
        try:
            response = requests.get(f'{BASE_URL}{file_path}', timeout=10)
            status = "✅" if response.status_code == 200 else "❌"
            print(f"{status} {file_path} - Status: {response.status_code}")

            if response.status_code != 200:
                all_passed = False
        except Exception as e:
            print(f"❌ {file_path} - Error: {str(e)}")
            all_passed = False

    if all_passed:
        print("\n✅ All static files PASSED")
    else:
        print("\n❌ Some static files FAILED")

    return all_passed

def run_all_tests():
    """Run all tests"""
    print("\n" + "="*60)
    print("TWILIO-BSL TEST SUITE")
    print("="*60)
    print(f"Base URL: {BASE_URL}")
    print(f"Test Phone: {TEST_PHONE}")

    results = {
        'Health Check': test_health_check(),
        'Web Interface': test_web_interface(),
        'Static Files': test_static_files(),
        'Get Conversations': test_get_conversaciones(),
        'Get Specific Conversation': test_get_conversacion(TEST_PHONE)
    }

    # Optional: Test sending message
    if input("\n\nRun send message test? (y/N): ").lower() == 'y':
        test_message = "[TEST] Mensaje de prueba desde Twilio-BSL"
        results['Send Message'] = test_enviar_mensaje(TEST_PHONE, test_message)

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status} - {test_name}")

    print("\n" + "="*60)
    print(f"TOTAL: {passed}/{total} tests passed")
    print("="*60)

    return passed == total

if __name__ == '__main__':
    print("\n🧪 Twilio-BSL Test Suite\n")

    # Check if service is running
    try:
        requests.get(f'{BASE_URL}/health', timeout=5)
    except Exception:
        print(f"❌ ERROR: Service not reachable at {BASE_URL}")
        print(f"\nMake sure the service is running:")
        print(f"  python twilio_bsl.py")
        sys.exit(1)

    # Run tests
    success = run_all_tests()

    sys.exit(0 if success else 1)
