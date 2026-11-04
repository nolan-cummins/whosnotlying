"""
Unit tests for QR Code generator.
"""

from src.qr import QRCode, generate_qr_svg


def test_qr_generation():
    url = "http://192.168.0.136:5050/join"
    qr = QRCode(url)
    assert qr.size > 20
    assert qr.modules[0][0] is True  # Top-left finder pattern corner

    svg = generate_qr_svg(url)
    assert "<svg" in svg
    assert "</svg>" in svg
    assert 'xmlns="http://www.w3.org/2000/svg"' in svg
    assert 'shape-rendering="crispEdges"' in svg


def test_qr_versions():
    # Short text -> version 1 or 2
    qr_short = QRCode("hello")
    assert qr_short.version <= 2

    # Medium URL
    qr_med = QRCode("http://192.168.1.100:5050/join")
    assert qr_med.version in (2, 3, 4)


def test_reed_solomon_standard_equivalence():
    from src.qr import rs_encode
    # Test standard known QR codeword vector
    data = [65, 230, 135, 71, 71, 3, 162, 242, 243, 19, 147, 34, 227, 19, 99, 130, 227, 2, 227, 19, 51, 99, 163, 83, 3, 83, 2, 246, 166, 246, 150, 224, 236, 17]
    ec = rs_encode(data, 10)
    expected_ec = [68, 67, 223, 140, 251, 8, 119, 118, 223, 132]
    assert ec == expected_ec, f"Expected standard EC {expected_ec}, got {ec}"

