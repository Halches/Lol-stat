"""Static artwork for the blossom desktop theme; no text or game data in assets.

Nine-slice resizing preserves the rim thickness at different window sizes.
Source art is bundled with the EXE and decoded once, with bounded render caches.
"""
from functools import lru_cache
from pathlib import Path
from PIL import Image, ImageEnhance, ImageFilter
import render


@lru_cache(maxsize=3)
def source(name):
    try:
        with Image.open(Path(render.HERE) / 'ui_assets' / name) as image:
            return image.convert('RGBA')
    except (OSError, ValueError):
        # Optional visual assets must never prevent the application starting.
        return None


def nine_slice(image, width, height, cut, border):
    """Keep four corners, stretch edge strips and the central material."""
    width, height = max(1, width), max(1, height)
    bx, by = min(border, width // 2), min(border, height // 2)
    sx = (0, cut, image.width-cut, image.width)
    sy = (0, cut, image.height-cut, image.height)
    dx, dy = (0, bx, width-bx, width), (0, by, height-by, height)
    result = Image.new('RGBA', (width, height))
    for y in range(3):
        for x in range(3):
            size = (dx[x+1]-dx[x], dy[y+1]-dy[y])
            if min(size) <= 0:
                continue
            part = image.crop((sx[x], sy[y], sx[x+1], sy[y+1]))
            part = part.resize(size, Image.Resampling.LANCZOS)
            result.paste(part, (dx[x], dy[y]))
    return result


@lru_cache(maxsize=2)
def shell(width, height, scale=1):
    image = source('blossom-shell-v1.png')
    if image is None:
        return None
    return nine_slice(image, width, height, 60, round(54*scale)).convert('RGB')


@lru_cache(maxsize=2)
def backdrop(width, height, scale=1):
    image = shell(width, height, scale)
    if image is None:
        return None
    # Scrollable content may sample outside the client area before it is shown.
    # Never bake the outer frame into those rows or it would scroll with them.
    edge = min(round(54*scale), (width-1)//2, (height-1)//2)
    result = image.copy()
    if edge:
        # Extend interior edge pixels across the full corner/bevel footprint.
        # The shell artwork has asymmetric highlights; a narrow uniform crop
        # can otherwise leave a bright bottom-rim stripe inside scrolled rows.
        result.paste(image.crop((edge,0,edge+1,height)).resize((edge,height)), (0,0))
        result.paste(image.crop((width-edge-1,0,width-edge,height)).resize((edge,height)), (width-edge,0))
        result.paste(result.crop((0,edge,width,edge+1)).resize((width,edge)), (0,0))
        result.paste(result.crop((0,height-edge-1,width,height-edge)).resize((width,edge)), (0,height-edge))
    return result


@lru_cache(maxsize=24)
def panel(width, height, active=False, compact=False):
    tall = width < height*4 and not compact
    image = source('blossom-card-v1.png' if tall else 'blossom-panel-v2.png')
    if image is None:
        return None
    # Transparent export margins are excluded; keep the shadow below the rim.
    face = image if tall else image.crop((30, 268, 2142, 462))
    drop_shadow = not compact and not tall
    face = nine_slice(face, width, max(1,height-4) if drop_shadow else height, 80 if tall else 64, 16 if compact else 26)
    alpha = face.getchannel('A')
    if active:
        face = ImageEnhance.Brightness(face).enhance(1.85)
        face = ImageEnhance.Color(face).enhance(1.25)
    elif compact:
        face = ImageEnhance.Brightness(face).enhance(.88)
    face.putalpha(alpha.point(lambda a: round(a * (.93 if active else .88))))
    if drop_shadow:
        shadow=Image.new('L',(width,height));shadow.paste(face.getchannel('A'),(0,3))
        shadow=shadow.filter(ImageFilter.GaussianBlur(2.5)).point(lambda a:round(a*.42))
        result=Image.new('RGBA',(width,height),(5,2,10,0));result.putalpha(shadow)
        result.alpha_composite(face);return result
    return face
