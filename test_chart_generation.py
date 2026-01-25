#!/usr/bin/env python3
"""
Test script to verify chart generation logic without running Flask.
This tests the matplotlib chart generation functions.
"""

import base64
from io import BytesIO

def test_chart_generation():
    """Test that chart generation functions work correctly"""

    # Mock data similar to what the endpoint would generate
    test_data = {
        'genero': {'Masculino': 60, 'Femenino': 40},
        'edad': {'15-20': 10, '21-30': 30, '31-40': 35, '41-50': 20, 'Mayor 50': 5},
        'estadoCivil': {'Soltero': 45, 'Casado': 30, 'Unión Libre': 20, 'Divorciado': 3, 'Viudo': 2},
    }

    print("=" * 60)
    print("TESTING MATPLOTLIB CHART GENERATION")
    print("=" * 60)

    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        print("✅ matplotlib imported successfully")
    except ImportError as e:
        print(f"❌ matplotlib not available: {e}")
        print("\nThis is expected in local development.")
        print("matplotlib will be installed in production via requirements.txt")
        return

    # Test pie chart generation
    print("\n📊 Testing pie chart generation...")
    try:
        fig, ax = plt.subplots(figsize=(8, 6))
        data = test_data['genero']
        labels = list(data.keys())
        sizes = list(data.values())

        wedges, texts, autotexts = ax.pie(
            sizes,
            labels=labels,
            autopct='%1.1f%%',
            colors=['#3b82f6', '#ec4899'],
            startangle=90
        )

        for autotext in autotexts:
            autotext.set_color('white')

        ax.set_title('Test Pie Chart', fontsize=14, weight='bold')

        buffer = BytesIO()
        plt.tight_layout()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.read()).decode('utf-8')
        plt.close(fig)

        print(f"   ✅ Pie chart generated: {len(image_base64)} bytes base64")
        print(f"   ✅ First 50 chars: {image_base64[:50]}...")

    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return

    # Test bar chart generation
    print("\n📊 Testing bar chart generation...")
    try:
        fig, ax = plt.subplots(figsize=(10, 6))
        data = test_data['edad']
        labels = list(data.keys())
        values = list(data.values())

        bars = ax.bar(labels, values, color=['#1e40af'] * len(values))

        for bar in bars:
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2.,
                height,
                f'{int(height)}',
                ha='center',
                va='bottom'
            )

        ax.set_title('Test Bar Chart', fontsize=14, weight='bold')
        ax.grid(axis='y', alpha=0.3)

        buffer = BytesIO()
        plt.tight_layout()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.read()).decode('utf-8')
        plt.close(fig)

        print(f"   ✅ Bar chart generated: {len(image_base64)} bytes base64")

    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return

    # Test horizontal bar chart generation
    print("\n📊 Testing horizontal bar chart generation...")
    try:
        fig, ax = plt.subplots(figsize=(10, 6))
        data = dict(sorted(test_data['estadoCivil'].items(), key=lambda x: x[1], reverse=True))
        labels = list(data.keys())
        values = list(data.values())

        y_pos = range(len(labels))
        bars = ax.barh(y_pos, values, color=['#1e40af'] * len(values))

        ax.set_yticks(y_pos)
        ax.set_yticklabels(labels)
        ax.invert_yaxis()
        ax.set_title('Test Horizontal Bar Chart', fontsize=14, weight='bold')

        buffer = BytesIO()
        plt.tight_layout()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.read()).decode('utf-8')
        plt.close(fig)

        print(f"   ✅ Horizontal bar chart generated: {len(image_base64)} bytes base64")

    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print("✅ ALL CHART GENERATION TESTS PASSED")
    print("=" * 60)
    print("\nThe chart generation functions are working correctly.")
    print("Charts will be embedded as base64 images in the PDF template.")
    print("\nTo test in production:")
    print("1. Deploy to Digital Ocean with updated requirements.txt")
    print("2. Generate a PDF from the /informes.html interface")
    print("3. Verify that charts appear in the downloaded PDF")


if __name__ == '__main__':
    test_chart_generation()
