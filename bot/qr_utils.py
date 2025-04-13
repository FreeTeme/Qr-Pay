from io import BytesIO
import qrcode

def generate_qr(business_id: int) -> BytesIO:
    qr = qrcode.make(f"https://t.me/QrPay_oficial_bot?start=business_{business_id}")
    buffer = BytesIO()
    qr.save(buffer, format="PNG")
    buffer.seek(0)  # Сброс указателя в начало
    return buffer