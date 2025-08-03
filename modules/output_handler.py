import os

import qrcode
import requests
from bs4 import BeautifulSoup
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.flowables import Flowable


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
        border=4,
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


class ClickableImage(Flowable):
    """
    A flowable that displays an image and makes it clickable, linking to a specified URL.
    """

    def __init__(self, image_path, url, width=200, height=100):
        super().__init__()
        self.image_path = image_path
        self.url = url
        self.width = width
        self.height = height

    def wrap(self, availWidth, availHeight):
        return (self.width, self.height)

    def draw(self):
        # Receive the canvas
        self.canv.drawImage(self.image_path, 0, 0, width=self.width, height=self.height)

        # Make the area clickable
        self.canv.linkURL(self.url, (0, 0, self.width, self.height), relative=1)


def fetch_logo_and_site_name(config_ncUrl, tmp_dir):
    """
    Fetches the logo, background, and site name from the Nextcloud main page.
    :param config_ncUrl: The Nextcloud URL.
    :param tmp_dir: Temporary directory to save the logo and background images.
    """
    url = (
        f"https://{config_ncUrl}"
        if not config_ncUrl.startswith("http")
        else config_ncUrl
    )
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        # Логотип
        logo_url = url.rstrip("/") + "/" + "apps/theming/image/logoheader"
        logo_path = os.path.join(tmp_dir, "site_logo.jpg")
        if logo_url:
            img_resp = requests.get(logo_url, timeout=10)
            with open(logo_path, "wb") as f:
                f.write(img_resp.content)
        else:
            logo_path = None
        # Фон
        bg_url = url.rstrip("/") + "/" + "apps/theming/image/background"
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


def generate_pdf(
    user_data,
    qr_code_path,
    output_filepath,
    config_ncUrl,
    lang,
    multi_user=False,
    tmp_dir="tmp",
    logo_path=None,
    bg_path=None,
    site_name=None,
):
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
    # Use IBMPlexSans for default font
    font_path = os.path.join(
        os.path.dirname(__file__), "../assets/IBMPlexSans-Regular.ttf"
    )
    if os.path.exists(font_path):
        try:
            pdfmetrics.registerFont(TTFont("IBMPlexSans", font_path))
            custom_font = "IBMPlexSans"
        except Exception:
            custom_font = "Helvetica"
    else:
        custom_font = "Helvetica"

    # Load logo image
    # If logo_path is provided and exists, use it; otherwise, use the default logo
    im_site = im
    if logo_path and os.path.exists(logo_path):
        im_site = Image(logo_path, 150, 150)

    # Background image
    # If bg_path is provided and exists, use it; otherwise, set bg_image to None
    bg_image = bg_path if bg_path and os.path.exists(bg_path) else None

    def add_background(canvas, doc):
        if bg_image:
            canvas.saveState()
            canvas.drawImage(
                ImageReader(bg_image), 0, 0, width=A4[0], height=A4[1], mask="auto"
            )
            canvas.restoreState()

    doc = SimpleDocTemplate(
        output_filepath,
        pagesize=A4,
        rightMargin=72,
        leftMargin=72,
        topMargin=10,
        bottomMargin=12,
    )
    story = []
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="Justify",
            alignment=TA_JUSTIFY,
            fontName=custom_font,
            fontSize=12,
            textColor=colors.white,
        )
    )
    styles["Normal"].fontName = custom_font
    styles["Normal"].textColor = colors.white
    styles["Heading1"].fontName = custom_font
    styles["Heading1"].textColor = colors.white

    if multi_user:
        for user in user_data["users"]:
            _build_single_user_section(
                story,
                styles,
                user,
                user.get("qr_code_path"),
                config_ncUrl,
                lang,
                im_site,
                site_name,
            )
            story.append(PageBreak())
    else:
        _build_single_user_section(
            story,
            styles,
            user_data,
            qr_code_path,
            config_ncUrl,
            lang,
            im_site,
            site_name,
        )
    doc.build(story, onFirstPage=add_background, onLaterPages=add_background)


def add_app_store_buttons(story, styles, lang):
    """
    Adds buttons for downloading the Nextcloud Talk app from Google Play and App Store.
    :param story: The list of elements that make up the PDF content.
    :param styles: Styles for formatting the PDF.
    :param lang: The dictionary containing translations for output text.
    """
    download_text = lang.get(
        "output_handler_download_app",
        "Скачайте приложение Nextcloud Talk на своё мобильное устройство:",
    )
    story.append(Paragraph(f"<font size=14>{download_text}</font>", styles["Normal"]))
    story.append(Spacer(1, 14))
    google_play_img = os.path.join(
        os.path.dirname(__file__), "../assets/google_play.jpg"
    )
    app_store_img = os.path.join(os.path.dirname(__file__), "../assets/app_store.jpg")
    btn_width = 140
    btn_height = 45
    btn_row = []
    if os.path.exists(google_play_img):
        btn_row.append(
            ClickableImage(
                image_path=google_play_img,
                url="https://play.google.com/store/apps/details?id=com.nextcloud.talk2",
                width=btn_width,
                height=btn_height,
            )
        )
    if os.path.exists(app_store_img):
        btn_row.append(
            ClickableImage(
                image_path=app_store_img,
                url="https://itunes.apple.com/us/app/nextcloud-talk/id1296825574",
                width=btn_width,
                height=btn_height,
            )
        )
    if len(btn_row) > 0:
        btn_table = Table(
            [btn_row], colWidths=[btn_width + 10] * len(btn_row), hAlign="CENTER"
        )
        story.append(btn_table)
        story.append(Spacer(1, 24))


def add_greeting_and_password(story, styles, user_data, lang, site_name, config_ncUrl):
    """
    Adds a greeting and user credentials to the PDF.
    :param story: The list of elements that make up the PDF content.
    :param styles: Styles for formatting the PDF.
    :param user_data: Contains 'username' and 'password' for the user.
    :param lang: The dictionary containing translations for output text.
    """

    # Adds a greeting
    displayname = user_data.get("displayname", "").strip() or user_data["username"]
    ptext = f"<font size=14>{lang.get('output_handler_greeting', 'Missing translation string for: output_handler_greeting')} {displayname},</font>"
    story.append(Paragraph(ptext, styles["Justify"]))
    story.append(Spacer(1, 12))
    # Adds a message about account creation
    ptext = f"<font size=14>{lang.get('output_handler_account_created', 'Missing translation string for: output_handler_account_created')} {site_name}</font>"
    story.append(Paragraph(ptext, styles["Justify"]))
    story.append(Spacer(1, 12))
    # Instructions for login
    ptext = f"<font size=14>{lang.get('output_handler_login_instructions', 'Missing translation string for: output_handler_login_instructions')}</font>"
    story.append(Paragraph(ptext, styles["Normal"]))
    story.append(Spacer(1, 24))
    # Adds the Nextcloud URL
    ptext = f"<font size=14>{lang.get('output_handler_nc_url', 'Missing translation string for: output_handler_nc_url')}: {config_ncUrl}</font>"
    story.append(Paragraph(ptext, styles["Normal"]))
    story.append(Spacer(1, 24))
    # Adds username
    uname_table = Table([[user_data["username"]]], colWidths=[250], rowHeights=[24])
    uname_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.whitesmoke),
                ("BOX", (0, 0), (-1, -1), 1, colors.black),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("FONTSIZE", (0, 0), (-1, -1), 14),
                ("FONTNAME", (0, 0), (-1, -1), "Courier"),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    ptext = f"<font size=14>{lang.get('output_handler_username', 'Username')}:</font>"
    story.append(Paragraph(ptext, styles["Normal"]))
    story.append(Spacer(1, 10))
    story.append(uname_table)
    story.append(Spacer(1, 20))
    # Adds password table
    pwd_table = Table([[user_data["password"]]], colWidths=[250], rowHeights=[24])
    pwd_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.whitesmoke),
                ("BOX", (0, 0), (-1, -1), 1, colors.black),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("FONTSIZE", (0, 0), (-1, -1), 14),
                ("FONTNAME", (0, 0), (-1, -1), "Courier"),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    ptext = f"<font size=14>{lang.get('output_handler_password', 'Password')}:</font>"
    story.append(Paragraph(ptext, styles["Normal"]))
    story.append(Spacer(1, 10))
    story.append(pwd_table)
    story.append(Spacer(1, 20))


def _build_single_user_section(
    story, styles, user_data, qr_code_path, config_ncUrl, lang, im_site, site_name
):
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
    story.append(Spacer(1, 8))

    add_greeting_and_password(story, styles, user_data, lang, site_name, config_ncUrl)
    # QR Code
    if qr_code_path and os.path.exists(qr_code_path):
        ptext = f"<font size=14>{lang.get('output_handler_qr_code_alternative', 'Missing translation string for: output_handler_qr_code_alternative')}</font>"
        story.append(Paragraph(ptext, styles["Normal"]))
        story.append(Spacer(1, 24))
        story.append(Image(qr_code_path, 150, 150))
    story.append(Spacer(1, 24))

    add_app_store_buttons(story, styles, lang)
