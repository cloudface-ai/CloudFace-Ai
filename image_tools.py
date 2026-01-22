#!/usr/bin/env python3
"""
Image Tools - Batch Watermark
Standalone tools to avoid impacting main app flows.
"""
import os
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED

from flask import Blueprint, render_template, request, send_file, jsonify
from werkzeug.utils import secure_filename

image_tools_bp = Blueprint('image_tools', __name__)


@image_tools_bp.route('/image-tools')
def image_tools_home():
    return render_template('image_tools_batch_watermark.html')


def _is_image(filename):
    ext = os.path.splitext(filename)[1].lower()
    return ext in {'.jpg', '.jpeg', '.png', '.webp'}


def _build_watermark(image, text, logo, opacity, size_pct, margin, position, offset_x=0, offset_y=0):
    from PIL import Image, ImageDraw, ImageFont

    text = (text or '').strip()
    if not text and logo is None:
        return image

    base = image.convert('RGBA')

    wm_logo = None
    if logo is not None:
        target_width = max(40, int(base.width * size_pct / 100))
        target_height = int(logo.height * (target_width / logo.width))
        wm_logo = logo.resize((target_width, target_height), Image.LANCZOS)

    font_size = max(14, int(base.width * (size_pct / 100) * 0.25))
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()

    text_image = None
    if text:
        dummy = ImageDraw.Draw(Image.new('RGBA', (1, 1)))
        bbox = dummy.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        text_image = Image.new('RGBA', (text_w + 2, text_h + 2), (0, 0, 0, 0))
        draw = ImageDraw.Draw(text_image)
        draw.text((1, 1), text, font=font, fill=(0, 0, 0, 255))
        draw.text((0, 0), text, font=font, fill=(255, 255, 255, 255))

    gap = max(6, int(base.width * 0.01))
    if wm_logo and text_image:
        wm_w = max(wm_logo.width, text_image.width)
        wm_h = wm_logo.height + gap + text_image.height
        watermark = Image.new('RGBA', (wm_w, wm_h), (0, 0, 0, 0))
        watermark.paste(wm_logo, ((wm_w - wm_logo.width) // 2, 0), wm_logo)
        watermark.paste(text_image, ((wm_w - text_image.width) // 2, wm_logo.height + gap), text_image)
    elif wm_logo:
        watermark = wm_logo
    else:
        watermark = text_image

    if watermark is None:
        return base

    if opacity < 100:
        alpha = watermark.split()[3]
        alpha = alpha.point(lambda p: int(p * opacity / 100))
        watermark.putalpha(alpha)

    max_x = max(0, base.width - watermark.width)
    max_y = max(0, base.height - watermark.height)

    if position == 'custom':
        max_x = max(0, base.width - watermark.width)
        max_y = max(0, base.height - watermark.height)
        x = int(max_x * (offset_x / 100)) if max_x else 0
        y = int(max_y * (offset_y / 100)) if max_y else 0
    else:
        if position.endswith('left'):
            x = margin
        elif position.endswith('right'):
            x = base.width - watermark.width - margin
        else:
            x = (base.width - watermark.width) // 2

        if position.startswith('top'):
            y = margin
        else:
            y = base.height - watermark.height - margin

    max_x = max(0, base.width - watermark.width)
    max_y = max(0, base.height - watermark.height)
    x = max(0, min(x, max_x))
    y = max(0, min(y, max_y))
    base.alpha_composite(watermark, (x, y))
    return base


@image_tools_bp.route('/image-tools/watermark', methods=['POST'])
def batch_watermark():
    try:
        files = request.files.getlist('images')
        if not files:
            return jsonify({'success': False, 'error': 'No images uploaded'}), 400
        if len(files) > 200:
            return jsonify({'success': False, 'error': 'Maximum 200 images per batch'}), 400

        text = request.form.get('watermark_text', '').strip()
        position = request.form.get('watermark_position', 'bottom-right')
        opacity = int(request.form.get('watermark_opacity', 70))
        size_pct = int(request.form.get('watermark_size', 15))
        margin = int(request.form.get('watermark_margin', 12))
        offset_x = float(request.form.get('watermark_offset_x', 0))
        offset_y = float(request.form.get('watermark_offset_y', 0))

        logo_file = request.files.get('watermark_logo')
        logo_image = None
        if logo_file and logo_file.filename:
            from PIL import Image
            logo_image = Image.open(logo_file.stream).convert('RGBA')

        output = BytesIO()
        with ZipFile(output, 'w', ZIP_DEFLATED) as zip_file:
            for file_obj in files:
                filename = secure_filename(file_obj.filename or '')
                if not filename or not _is_image(filename):
                    continue

                from PIL import Image
                image = Image.open(file_obj.stream).convert('RGBA')
                watermarked = _build_watermark(
                    image=image,
                    text=text,
                    logo=logo_image,
                    opacity=opacity,
                    size_pct=size_pct,
                    margin=margin,
                    position=position,
                    offset_x=offset_x,
                    offset_y=offset_y
                )

                base_name, ext = os.path.splitext(filename)
                ext = ext.lower() if ext else '.jpg'
                output_name = f"{base_name}_wm{ext}"
                buffer = BytesIO()
                if ext == '.png':
                    watermarked.save(buffer, format='PNG')
                elif ext == '.webp':
                    watermarked.save(buffer, format='WEBP', quality=85)
                else:
                    watermarked.convert('RGB').save(buffer, format='JPEG', quality=90)
                buffer.seek(0)
                zip_file.writestr(output_name, buffer.read())

        output.seek(0)
        return send_file(output, as_attachment=True, download_name='watermarked_images.zip', mimetype='application/zip')
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
