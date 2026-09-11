import os
import tempfile
import qrcode
from PIL import Image, ImageDraw, ImageFont

def generate_and_print_receipt(receipt_data, user):
    """
    Generates a thermal printer sized receipt image (e.g. 58mm or 80mm).
    We use Pillow to draw text and QR code to properly support Indic fonts
    which ESC/POS printers usually struggle with natively.
    """
    width = 400  # pixels for ~58mm thermal printer
    height = 600
    
    img = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(img)
    
    try:
        # Try to load a default Windows font that supports Indic if needed.
        # Arial Unicode MS or Nirmala UI are common on Windows.
        font = ImageFont.truetype("arial.ttf", 16)
        title_font = ImageFont.truetype("arialbd.ttf", 20)
    except IOError:
        font = ImageFont.load_default()
        title_font = font

    y = 20
    draw.text((100, y), "SAHAKAR SEVA RECEIPT", font=title_font, fill="black")
    y += 40
    
    draw.text((20, y), f"User: {user.get('name', 'Unknown')}", font=font, fill="black")
    y += 30
    
    for k, v in receipt_data.items():
        text_line = f"{str(k).capitalize()}: {str(v)}"
        draw.text((20, y), text_line, font=font, fill="black")
        y += 30
        
    y += 20
    # Generate QR Code
    qr = qrcode.QRCode(box_size=4, border=2)
    qr.add_data(str(receipt_data.get('reference', 'N/A')))
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    # Paste QR
    qr_img = qr_img.convert('RGB')
    qr_w, qr_h = qr_img.size
    box = ((width - qr_w) // 2, y, (width - qr_w) // 2 + qr_w, y + qr_h)
    img.paste(qr_img, box)
    
    tmp_fd, img_path = tempfile.mkstemp(suffix=".png", prefix="receipt_")
    os.close(tmp_fd)
    
    img.save(img_path)
    print(f"Receipt generated at {img_path}")
    
    # Attempt silent print on Windows
    print("\n[PRINTER] Simulating thermal print (Hardware printing disabled for prototype).")
    print(f"[PRINTER] Would print receipt: {img_path}\n")
        
    return img_path
