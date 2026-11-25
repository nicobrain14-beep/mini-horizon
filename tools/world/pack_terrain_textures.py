"""Packs Poly Haven textures (1k JPG: Diffuse, nor_gl, arm, Displacement) for Terrain3D:
<name>_alb_h.webp = albedo RGB + height A, <name>_nrm_r.webp = OpenGL normal RGB + roughness A (WebP, quality 92).
Usage: python3 tools/world/pack_terrain_textures.py <folder with the raw downloads>
The list order is the Terrain3D texture id used by the world importer."""
import os, sys
import numpy as np
from PIL import Image

SRC = sys.argv[1]
OUT = os.path.join(os.path.dirname(__file__), '..', '..', 'assets', 'textures', 'terrain')
TEXTURES = [  # (terrain id name, Poly Haven id)
    ('grass', 'aerial_grass_rock'), ('forest', 'forest_ground_04'), ('rock', 'rock_face_03'), ('dry', 'dry_ground_rocks'),
    ('farm', 'farm_furrows'), ('sand', 'sand_01'), ('snow', 'snow_field_aerial'), ('ash', 'cracked_red_ground'),
    ('mud', 'aerial_mud_1'), ('gravel', 'grass_path_2'),
]
IMPORT = """[remap]

importer="texture"
type="CompressedTexture2D"
metadata={{
"vram_texture": true
}}

[deps]

source_file="res://assets/textures/terrain/{f}"

[params]

compress/mode=2
compress/high_quality=false
compress/lossy_quality=0.7
compress/hdr_compression=1
compress/normal_map=2
compress/channel_pack=0
mipmaps/generate=true
mipmaps/limit=-1
roughness/mode=0
process/fix_alpha_border=false
process/premult_alpha=false
process/normal_map_invert_y=false
process/hdr_as_srgb=false
process/size_limit=0
detect_3d/compress_to=0
"""
def find(pid, kind):
    for ext in ('jpg', 'png'):
        p = os.path.join(SRC, f'{pid}_{kind}.{ext}')
        if os.path.exists(p): return p
    return None
os.makedirs(OUT, exist_ok=True)
for name, pid in TEXTURES:
    d = np.asarray(Image.open(find(pid, 'Diffuse')).convert('RGB').resize((1024, 1024), Image.LANCZOS), np.uint8)
    dp = find(pid, 'Displacement')
    hgt = np.asarray(Image.open(dp).convert('L').resize((1024, 1024), Image.LANCZOS) if dp else Image.fromarray(d).convert('L'), np.uint8)
    n = np.asarray(Image.open(find(pid, 'nor_gl')).convert('RGB').resize((1024, 1024), Image.LANCZOS), np.uint8)
    ap = find(pid, 'arm')
    rough = np.asarray(Image.open(ap).convert('RGB').resize((1024, 1024), Image.LANCZOS), np.uint8)[..., 1] if ap else np.full((1024, 1024), 200, np.uint8)
    for f, arr in ((f'{name}_alb_h.webp', np.dstack([d, hgt])), (f'{name}_nrm_r.webp', np.dstack([n, rough]))):
        Image.fromarray(arr, 'RGBA').save(os.path.join(OUT, f), quality=92, method=6)
        open(os.path.join(OUT, f + '.import'), 'w').write(IMPORT.format(f=f))
    print(name, 'ok')
