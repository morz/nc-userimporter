import os
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY
import qrcode
from html import escape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
import requests
from bs4 import BeautifulSoup

def generate_qr_code(data, output_dir, filename):
    """
    Generates a QR code based on provided data and saves it as an image file.

    Args:
        data (str): The data to encode in the QR code.
        output_dir (str): The directory where the QR code image will be saved.
        filename (str): The name of the QR code image file (without extension).

    Returns:
        str: The full path to the saved QR code image.
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4
    )
    qr.add_data(data)
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Save QR code image as a .jpg file
    img_path = os.path.join(output_dir, f"{filename}.jpg")
    img.save(img_path)
    
    # Clear the QR object for reuse
    qr.clear()
    
    return img_path

nclogo = "assets/Nextcloud_Logo.jpg"  # Nextcloud logo
im = Image(nclogo, 150, 106)

def fetch_logo_and_site_name(config_ncUrl, tmp_dir):
    """
    Загружает логотип, фон и название сайта с главной страницы Nextcloud.
    Возвращает путь к логотипу, путь к фону и название сайта.
    """
    url = f"https://{config_ncUrl}" if not config_ncUrl.startswith("http") else config_ncUrl
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        # Логотип
        logo_url = url.rstrip('/') + '/' + "apps/theming/image/logoheader"
        logo_path = os.path.join(tmp_dir, "site_logo.jpg")
        if logo_url:
            img_resp = requests.get(logo_url, timeout=10)
            with open(logo_path, "wb") as f:
                f.write(img_resp.content)
        else:
            logo_path = None
        # Фон
        bg_url = url.rstrip('/') + '/' + "apps/theming/image/background"
        bg_path = os.path.join(tmp_dir, "site_bg.jpg")
        if bg_url:
            bg_resp = requests.get(bg_url, timeout=10)
            with open(bg_path, "wb") as f:
                f.write(bg_resp.content)
        else:
            bg_path = None
        # Название сайта
        site_name_a = soup.select_one("body > footer > p > a")
        site_name = site_name_a.text.strip() if site_name_a else config_ncUrl
        return logo_path, bg_path, site_name
    except Exception:
        return None, None, config_ncUrl


def generate_pdf(user_data, qr_code_path, output_filepath, config_ncUrl, lang, multi_user=False, tmp_dir="tmp", logo_path=None, bg_path=None, site_name=None):
    """
    Generates a PDF for either a single user or multiple users.
    
    Args:
        user_data (dict): User data, either for a single user or a list of users in multi-user mode.
        qr_code_path (str): The path to the QR code image (for single user mode).
        output_filepath (str): The output path for the generated PDF.
        config_ncUrl (str): The Nextcloud URL.
        lang (dict): The dictionary containing translations for output text.
        multi_user (bool): Whether to generate a multi-user PDF.
    """
    # Use DejaVuSans for default font
    font_path = os.path.join(os.path.dirname(__file__), '../assets/IBMPlexSans-Regular.ttf')
    if os.path.exists(font_path):
        try:
            pdfmetrics.registerFont(TTFont('IBMPlexSans', font_path))
            custom_font = 'IBMPlexSans'
        except Exception:
            custom_font = 'Helvetica'
    else:
        custom_font = 'Helvetica'

    # Получаем логотип и название сайта
    if logo_path and os.path.exists(logo_path):
        im_site = Image(logo_path, 150, 150)
    else:
        im_site = im
    # Фон
    if bg_path and os.path.exists(bg_path):
        bg_image = bg_path
    else:
        bg_image = None
    def add_background(canvas, doc):
        if bg_image:
            from reportlab.lib.utils import ImageReader
            canvas.saveState()
            canvas.drawImage(ImageReader(bg_image), 0, 0, width=A4[0], height=A4[1], mask='auto')
            canvas.restoreState()
    doc = SimpleDocTemplate(output_filepath, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=18, bottomMargin=18)
    story = []
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Justify', alignment=TA_JUSTIFY, fontName=custom_font, fontSize=12, textColor=colors.white))
    styles['Normal'].fontName = custom_font
    styles['Normal'].textColor = colors.white
    styles['Heading1'].fontName = custom_font
    styles['Heading1'].textColor = colors.white

    if multi_user:
        for user in user_data['users']:
            _build_single_user_section(story, styles, user, user.get('qr_code_path'), config_ncUrl, lang, im_site, site_name)
            story.append(PageBreak())
    else:
        _build_single_user_section(story, styles, user_data, qr_code_path, config_ncUrl, lang, im_site, site_name)
    doc.build(story, onFirstPage=add_background, onLaterPages=add_background)

def _build_single_user_section(story, styles, user_data, qr_code_path, config_ncUrl, lang, im_site, site_name):
    """
    Helper function to build the PDF content for a single user.

    Args:
        story (list): The list of elements that make up the PDF content.
        styles (StyleSheet): Styles for formatting the PDF.
        user_data (dict): Contains 'username' and 'password' for the user.
        qr_code_path (str): Path to the generated QR code image.
        config_ncUrl (str): The Nextcloud URL for the user.
        lang (dict): The dictionary containing translations for output text.
    """
    
    # Add site logo and site name at the top of the page
    story.append(im_site)
    story.append(Spacer(1, 12))
    
    # Greeting and account creation message
    displayname = user_data.get('displayname', '').strip()  # Entferne Leerzeichen
    if not displayname:
        displayname = user_data['username']  # Fallback auf den Benutzernamen

    # Add greeting
    ptext = f"<font size=14>{lang.get('output_handler_greeting', 'Missing translation string for: output_handler_greeting')} {displayname},</font>"
    story.append(Paragraph(ptext, styles["Justify"]))
    story.append(Spacer(1, 12))

    # Account creation message
    ptext = f"<font size=14>{lang.get('output_handler_account_created', 'Missing translation string for: output_handler_account_created')} {site_name}</font>"
    story.append(Paragraph(ptext, styles["Justify"]))
    story.append(Spacer(1, 12))

    # Login instructions
    ptext = f"<font size=14>{lang.get('output_handler_login_instructions', 'Missing translation string for: output_handler_login_instructions')}</font>"
    story.append(Paragraph(ptext, styles["Normal"]))
    story.append(Spacer(1, 24))

    # Nextcloud URL
    ptext = f"<font size=14>{lang.get('output_handler_nc_url', 'Missing translation string for: output_handler_nc_url')}: {config_ncUrl}</font>"
    story.append(Paragraph(ptext, styles["Normal"]))
    story.append(Spacer(1, 24))

    # Username (box)
    uname_table = Table([[user_data['username']]], colWidths=[250], rowHeights=[30])
    uname_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.whitesmoke),
        ('BOX', (0,0), (-1,-1), 1, colors.black),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTSIZE', (0,0), (-1,-1), 14),
        ('FONTNAME', (0,0), (-1,-1), 'Courier'),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6)
    ]))
    ptext = f"<font size=14>{lang.get('output_handler_username', 'Username')}:</font>"
    story.append(Paragraph(ptext, styles["Normal"]))
    story.append(Spacer(1, 12))
    story.append(uname_table)
    story.append(Spacer(1, 24))

    # Password (box)
    pwd_table = Table([[user_data['password']]], colWidths=[250], rowHeights=[30])
    pwd_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.whitesmoke),
        ('BOX', (0,0), (-1,-1), 1, colors.black),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTSIZE', (0,0), (-1,-1), 14),
        ('FONTNAME', (0,0), (-1,-1), 'Courier'),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6)
    ]))
    ptext = f"<font size=14>{lang.get('output_handler_password', 'Password')}:</font>"
    story.append(Paragraph(ptext, styles["Normal"]))
    story.append(Spacer(1, 12))
    story.append(pwd_table)
    story.append(Spacer(1, 24))

    # QR Code
    if qr_code_path and os.path.exists(qr_code_path):
        ptext = f"<font size=14>{lang.get('output_handler_qr_code_alternative', 'Missing translation string for: output_handler_qr_code_alternative')}</font>"
        story.append(Paragraph(ptext, styles["Normal"]))
        story.append(Spacer(1, 24))
        # Insert the QR code image
        story.append(Image(qr_code_path, 150, 150))

    story.append(Spacer(1, 24))

def _build_single_user_pdf(story, styles, user_data, qr_code_path, nclogo, config_ncUrl, lang):
    """
    Builds the PDF structure for a single user, including the Nextcloud logo.

    Args:
        story (list): The list of elements that make up the PDF content.
        styles (StyleSheet): Styles for formatting the PDF.
        user_data (dict): Contains 'username' and 'password' for the user.
        qr_code_path (str): Path to the generated QR code image.
        nclogo (str): Path to the Nextcloud logo.
        config_ncUrl (str): The Nextcloud URL for the user.
        lang (dict): The dictionary containing translations for output text.
    """
    _build_single_user_section(story, styles, user_data, qr_code_path, config_ncUrl, lang)
