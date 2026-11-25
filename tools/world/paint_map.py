"""Paints the satellite-style map of Valle Alto from the world data (run after build_roads.py).

The ground is painted with real aerial and ground photo textures from Poly Haven (CC0), tiled at
map scale and colour-matched per biome: grass, fields with furrows (each field its own direction and
crop colour), forest canopy with lit tree crowns, dry plateau, volcanic ash, rock, snow, beach sand and
river mud. Relief is shaded from the north-west with ambient occlusion. Water is deep blue with
lighter shallows and a foam line. Cities get building footprints with shadows along their streets.
Roads are white with a dark edge (highways wider, dirt tracks thin and tan).

Writes assets/world/map/: tiles per zoom level (z0 1024 px, z1 2048 px, z2 4096 px; 512 px JPG tiles)
and map_1024.jpg for the minimap; plus map_preview.jpg with labels and event icons (for review).
Textures are read from TEX_DIR (raw Poly Haven 1k JPGs; see tools/world/fetch_textures.py).
"""
import json, math, os, sys, time
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
W = os.path.join(ROOT, 'assets', 'world')
OUT = os.path.join(W, 'map')
TEX_DIR = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'assets-src', 'polyhaven')
PX = 4096
T0 = time.time()
def log(*a): print(f'[{time.time() - T0:5.1f}s]', *a, flush=True)

D = json.load(open(os.path.join(W, 'world.json')))
R = json.load(open(os.path.join(W, 'roads.json')))
E = json.load(open(os.path.join(W, 'events.json')))['events']
C = np.load(os.path.join(W, 'cache.npz'))
SIZE, N = D['size'], D['n']
MPP = SIZE / PX                                                # metres per map pixel
h = np.fromfile(os.path.join(W, 'height_roads.bin'), '<f4').reshape(N, N)

def up(a):
    """Resample a world grid to the map resolution (bilinear)."""
    return np.asarray(Image.fromarray(np.asarray(a, np.float32), 'F').resize((PX, PX), Image.BILINEAR), np.float32)
H = up(h); HS = up(C['h']); log('height')
M = {k: np.clip(up(C[k]), 0, 1) for k in ('land', 'lake', 'forest', 'farmland', 'semidesert', 'metro', 'colonial', 'snow', 'rock', 'beach', 'ash', 'mud', 'farm', 'mini', 'n1', 'n2')}
M['water'] = up(C['water'].astype(np.float32))
DR = up(C['dist_r'])
log('masks')
ys, xs_ = np.mgrid[0:PX, 0:PX].astype(np.float32)
WXm = xs_ * MPP - SIZE / 2; WZm = ys * MPP - SIZE / 2          # world metres of each map pixel
rng = np.random.default_rng(5)

# ---------------------------------------------------------------- textures
def load_tex(name):
    for ext in ('jpg', 'png'):
        p = os.path.join(TEX_DIR, f'{name}_Diffuse.{ext}')
        if os.path.exists(p): return np.asarray(Image.open(p).convert('RGB'), np.float32) / 255.0
    raise FileNotFoundError(name)

def tex(name, metres, target, strength=0.75, angle=None, contrast=1.0):
    """Sample a texture over the whole map, `metres` per tile, colour-matched to `target` (sRGB 0-255)."""
    T = load_tex(name); th, tw = T.shape[:2]
    if angle is None: u, v = WXm, WZm
    else: ca, sa = np.cos(angle), np.sin(angle); u = WXm * ca + WZm * sa; v = -WXm * sa + WZm * ca
    fu = (u / metres * tw) % tw; fv = (v / metres * th) % th
    i0 = fu.astype(np.int32); j0 = fv.astype(np.int32); tu = (fu - i0)[..., None]; tv = (fv - j0)[..., None]
    i1 = (i0 + 1) % tw; j1 = (j0 + 1) % th
    s = (T[j0, i0] * (1 - tu) + T[j0, i1] * tu) * (1 - tv) + (T[j1, i0] * (1 - tu) + T[j1, i1] * tu) * tv
    lum = s @ np.array([0.299, 0.587, 0.114], np.float32)
    detail = (lum / max(float(lum.mean()), 1e-3) - 1.0) * contrast + 1.0
    tgt = np.array(target, np.float32) / 255.0
    return tgt * (1 - strength + strength * detail)[..., None]

def blend(img, layer, w):
    w = np.clip(w, 0, 1)[..., None]; return img * (1 - w) + layer * w

def blur(a, r, passes=3):
    a = a.astype(np.float32)
    for _ in range(passes):
        for ax in (0, 1):
            c = np.cumsum(np.pad(a, [(r + 1, r) if i == ax else (0, 0) for i in range(a.ndim)], mode='edge'), axis=ax, dtype=np.float64)
            a = ((np.take(c, range(2 * r + 1, c.shape[ax]), axis=ax) - np.take(c, range(0, c.shape[ax] - 2 * r - 1), axis=ax)) / (2 * r + 1)).astype(np.float32)
    return a

n1, n2 = M['n1'], M['n2']
hilly = np.clip(up(C['hilly']), 0, 1)
# open land: meadows in two greens with real grass texture
meadow = tex('aerial_grass_rock', 300, (96, 120, 60), 0.55) * 0.6 + tex('grass_ground', 170, (116, 130, 68), 0.4, angle=0.6) * 0.4
meadow *= (0.88 + 0.24 * n1)[..., None]
img = meadow
log('meadow')
# fields: Voronoi parcels (irregular polygons), each its own crop tone and furrows, hedges on the borders
def worley(cell, seed):
    gx_, gz_ = (WXm + 60 * (n1 - 0.5)) / cell, (WZm + 60 * (n2 - 0.5)) / cell
    ix, iz = np.floor(gx_).astype(np.int32), np.floor(gz_).astype(np.int32)
    f1 = np.full(gx_.shape, 9.0, np.float32); f2 = np.full(gx_.shape, 9.0, np.float32); idb = np.zeros(gx_.shape, np.int64)
    for dz in (-1, 0, 1):
        for dx in (-1, 0, 1):
            cx_, cz_ = ix + dx, iz + dz
            hsh = (cx_.astype(np.int64) * 374761393 + cz_.astype(np.int64) * 668265263 + seed * 2246822519) & 0xFFFFFFFF
            hsh = ((hsh ^ (hsh >> 13)) * 1274126177) & 0xFFFFFFFF
            jx = (hsh & 0xFFFF) / 65535.0; jz = ((hsh >> 16) & 0xFFFF) / 65535.0
            d = np.hypot(gx_ - (cx_ + jx), gz_ - (cz_ + jz)).astype(np.float32)
            closer = d < f1
            f2 = np.where(closer, f1, np.minimum(f2, d)); idb = np.where(closer, hsh, idb); f1 = np.where(closer, d, f1)
    return idb, (f2 - f1)
fid, fedge = worley(150.0, 7)
crops = np.array([[118, 136, 70], [150, 152, 86], [100, 124, 60], [132, 118, 80], [160, 146, 92], [92, 118, 58], [176, 164, 104], [126, 140, 74]], np.float32) / 255
furrow = tex('farm_furrows', 26, (150, 150, 100), 0.55, angle=0.5, contrast=1.2)
fc = crops[fid % 8] * (furrow / furrow.mean((0, 1)))
fc *= (0.7 + 0.3 * np.clip(fedge / 0.08, 0, 1))[..., None]                 # darker hedgerows between parcels
fields = np.clip(M['farmland'] * 1.3, 0, 1) * (fid % 6 != 0)
img = blend(img, fc, fields)
del furrow, fc; log('fields')
# forest canopy: round tree crowns of two sizes, lit from the north-west with soft shade between them
def crowns(density, radius, seed):
    g = np.random.default_rng(seed)
    pts = (g.random((PX, PX)) < density).astype(np.float32)
    return blur(pts, radius, 3) * (2 * radius + 1) ** 2
ch = crowns(0.05, 2, 11) * 1.0 + crowns(0.09, 1, 12) * 0.7
ch = ch / (ch.max() + 1e-6)
gzc, gxc = np.gradient(ch)
lit = np.clip(0.75 + 6.0 * (-gxc * 0.7 - gzc * 0.7), 0.3, 1.5)            # light from the north-west
gap = np.clip(ch * 3.5, 0, 1)                                              # dark gaps between crowns
stand = np.clip((n2 - 0.4) * 3, 0, 1)[..., None]
green1 = np.array([30, 56, 30], np.float32) / 255; green2 = np.array([48, 78, 38], np.float32) / 255
tone = (0.85 + 0.3 * blur(np.random.default_rng(13).random((PX, PX)).astype(np.float32), 3, 2) * 2 - 0.3)[..., None]
canopy = (green1 * (1 - stand) + green2 * stand) * tone * (0.35 + 0.65 * gap)[..., None] * lit[..., None]
del gzc, gxc, tone
forest_w = np.clip(M['forest'] * 1.15, 0, 1)
woods = np.clip((n1 - 0.62) * 5, 0, 1) * (1 - M['farm']) * (1 - M['metro']) * M['land'] * 0.75     # copses in the open land
img = blend(img, canopy, np.clip(forest_w + woods, 0, 1))
del canopy, lit, ch, gap; log('forest')
dry = tex('dry_ground_rocks', 120, (152, 140, 100), 0.75) * tex('aerial_rocks_02', 330, (128, 128, 128), 0.5) / 0.5
shrub = blur((rng.random((PX, PX)) > 0.985).astype(np.float32), 1, 1) * 9
dry *= (1 - 0.55 * np.clip(shrub, 0, 1))[..., None]                         # scattered shrubs
img = blend(img, dry, M['semidesert'] * 0.85)
img = blend(img, meadow * 0.55, M['semidesert'] * np.clip((n1 - 0.55) * 4, 0, 1) * 0.6)   # darker scrub patches
del dry, shrub
img = blend(img, tex('cracked_red_ground', 140, (88, 70, 60), 0.7), M['ash'] * 0.8)
img = blend(img, tex('rocky_terrain_02', 160, (122, 108, 94), 0.9, contrast=1.7) * tex('aerial_rocks_02', 420, (128, 128, 128), 0.6, contrast=1.4) / 0.5, M['rock'])
img = blend(img, tex('snow_field_aerial', 180, (214, 220, 228), 0.55), M['snow'])
img = blend(img, tex('aerial_beach_01', 80, (222, 206, 164), 0.6), M['beach'])
img = blend(img, tex('aerial_mud_1', 60, (96, 92, 66), 0.6), M['mud'] * 0.4)
city = np.clip(M['metro'] * 1.0 + M['colonial'] * 0.95 + M['mini'] * 0.85, 0, 1)
rag = 0.42 + 0.3 * (n1 - 0.5) + 0.25 * (blur(rng.random((PX, PX)).astype(np.float32), 6, 2) - 0.5) * 4
city = np.clip((city - rag) * 9, 0, 1)                                        # ragged edge instead of a soft oval
img = blend(img, tex('aerial_asphalt_01', 70, (212, 212, 208), 0.4), city * 0.92)
log('biomes')
# relief: north-west light and ambient occlusion
HSb = blur(HS, 1, 1)
gz, gx = np.gradient(HSb, MPP)
nx, ny, nz = -gx, np.ones_like(H), -gz; nl = np.sqrt(nx * nx + ny * ny + nz * nz)
shade = np.clip((nx * -0.55 + ny * 0.62 + nz * -0.55) / nl, 0, 1) / 0.62
ao = np.clip(1 + (HSb - blur(HSb, 6)) * 0.02, 0.72, 1.15)
img *= np.minimum((0.42 + 0.72 * shade) * ao, 1.12)[..., None]
log('relief')
# water
wat = M['water'] > 0.5
landblur = blur((M['water'] < 0.5).astype(np.float32), 24, 2)
depth = np.clip(1 - landblur * 3.0, 0, 1)
ripple = (1.0 + 0.06 * blur(rng.random((PX, PX)).astype(np.float32) - 0.5, 3, 2) * 8)[..., None] * np.ones(3, np.float32)
deepc = np.array([18, 44, 78], np.float32) / 255; shal = np.array([52, 140, 150], np.float32) / 255
wcol = ripple / ripple.mean((0, 1)) * (shal * (1 - depth[..., None]) + deepc * depth[..., None])
inland = (M['lake'] > 0.35) | (DR < 0)
wcol = np.where((inland & (H > 0.4))[..., None], np.array([44, 108, 130], np.float32) / 255 * (ripple / ripple.mean((0, 1))), wcol)
img = np.where(wat[..., None], wcol, img)
shore = wat & (blur((~wat).astype(np.float32), 2, 1) > 0.05)
img = np.where(shore[..., None], img * 0.45 + np.array([0.86, 0.91, 0.92]) * 0.55, img)
img = np.clip(img, 0, 1)
log('water')

# ---------------------------------------------------------------- buildings and roads (vector drawing)
base = Image.fromarray((img * 255).astype(np.uint8), 'RGB')
del img, ripple, wcol
def mp(x, z): return ((x + SIZE / 2) / MPP, (z + SIZE / 2) / MPP)
CITIES = D['cities']
mmask, cmask, nmask = M['metro'], M['colonial'], M['mini']
shadow = Image.new('RGBA', (PX, PX), (0, 0, 0, 0)); sdraw = ImageDraw.Draw(shadow)
roofs = Image.new('RGBA', (PX, PX), (0, 0, 0, 0)); rdraw = ImageDraw.Draw(roofs)
ROOF_METRO = [(232, 232, 228), (214, 216, 218), (196, 198, 200), (240, 238, 232), (176, 180, 184), (222, 214, 200)]
ROOF_COLONIAL = [(184, 96, 64), (196, 112, 76), (170, 84, 58), (226, 214, 196), (200, 120, 80)]
ROOF_MINI = [(206, 200, 188), (184, 104, 70), (222, 220, 212), (150, 156, 162), (200, 176, 140)]
mx, mz = CITIES['ciudad']['x'], CITIES['ciudad']['z']
for r in R['roads']:
    if r['kind'] not in ('street', 'calle', 'avenue'): continue
    P = np.array(r['pts'])[:, [0, 2]]
    for i in range(2, len(P) - 2, 3 if r['kind'] != 'calle' else 4):
        x, z = P[i]; px_, pz_ = int((x + SIZE / 2) / MPP), int((z + SIZE / 2) / MPP)
        if not (0 <= px_ < PX and 0 <= pz_ < PX): continue
        m_, c_, n_ = mmask[pz_, px_], cmask[pz_, px_], nmask[pz_, px_]
        if city[pz_, px_] < 0.5: continue
        if n2[pz_, px_] > 0.78 and m_ > 0.5: continue                      # parks
        d = P[i + 1] - P[i - 1]; d /= max(np.linalg.norm(d), 1e-6); nrm = np.array([-d[1], d[0]])
        for side in (-1, 1):
            if rng.random() < 0.05: continue
            if m_ > 0.5:
                core = max(0.0, 1 - math.hypot(x - mx, z - mz) / 900)
                wlen, dep = rng.uniform(14, 34) * (1 + core), rng.uniform(12, 26) * (1 + core); hgt = 2 + core * 10 * rng.random()
                col = ROOF_METRO[rng.integers(len(ROOF_METRO))]
            elif c_ > 0.5:
                wlen, dep, hgt = rng.uniform(9, 16), rng.uniform(10, 18), 1.2; col = ROOF_COLONIAL[rng.integers(len(ROOF_COLONIAL))]
            else:
                wlen, dep, hgt = rng.uniform(8, 13), rng.uniform(8, 12), 1.0; col = ROOF_MINI[rng.integers(len(ROOF_MINI))]
            ctr = np.array([x, z]) + nrm * side * (r['hw'] + 3 + dep / 2)
            corners = [ctr + d * a * wlen / 2 + nrm * b * dep / 2 for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
            poly = [mp(*q) for q in corners]
            off = hgt * 0.9
            sdraw.polygon([(p[0] + off, p[1] + off) for p in poly], fill=(0, 0, 0, 90))
            shade_c = tuple(int(cc * (0.9 + 0.2 * rng.random())) for cc in col)
            rdraw.polygon(poly, fill=shade_c + (255,), outline=tuple(int(cc * 0.7) for cc in col) + (255,))
# the port: piers into the bay along the city shore, container stacks on them
wat_s = C['water']; mt = C['metro']
step = 34
for zi in range(step, N - step, step):
    for xi in range(step, N - step, step):
        if not wat_s[zi, xi] or mt[zi, xi] < 0.15: continue
        win = wat_s[zi - 8:zi + 9, xi - 8:xi + 9]
        if win.all() or not win.any(): continue
        gzw, gxw = np.gradient(win.astype(np.float32)); nx_, nz_ = gxw.sum(), gzw.sum(); nl_ = math.hypot(nx_, nz_)
        if nl_ < 1e-3: continue
        nx_, nz_ = nx_ / nl_, nz_ / nl_                                        # points out into the water
        x0 = xi * (SIZE / (N - 1)) - SIZE / 2; z0 = zi * (SIZE / (N - 1)) - SIZE / 2
        L_, Wd = rng.uniform(140, 300), rng.uniform(45, 80)
        tx_, tz_ = -nz_, nx_
        quad = [(x0 + tx_ * a * Wd / 2 + nx_ * b, z0 + tz_ * a * Wd / 2 + nz_ * b) for a, b in ((-1, -20), (1, -20), (1, L_), (-1, L_))]
        sdraw.polygon([(mp(*q)[0] + 3, mp(*q)[1] + 3) for q in quad], fill=(0, 0, 0, 110))
        rdraw.polygon([mp(*q) for q in quad], fill=(204, 202, 196, 255), outline=(150, 150, 146, 255))
        for k in range(int(L_ / 22)):
            for side in (-0.5, 0.5):
                cxp = x0 + nx_ * (10 + k * 22) + tx_ * side * Wd * 0.5; czp = z0 + nz_ * (10 + k * 22) + tz_ * side * Wd * 0.5
                cc = [(196, 70, 50), (60, 110, 170), (220, 170, 60), (90, 140, 90), (200, 200, 200)][rng.integers(5)]
                box = [(cxp + tx_ * a * 8 + nx_ * b * 7, czp + tz_ * a * 8 + nz_ * b * 7) for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
                rdraw.polygon([mp(*q) for q in box], fill=cc + (255,))
# a stadium on the west side of the city
sx_, sz_ = CITIES['ciudad']['x'] - 700, CITIES['ciudad']['z'] - 250
for rr, col in ((150, (236, 236, 232, 255)), (118, (120, 160, 90, 255)), (88, (96, 150, 76, 255))):
    rdraw.ellipse([mp(sx_ - rr * 1.25, sz_ - rr), mp(sx_ + rr * 1.25, sz_ + rr)], fill=col)
sdraw.ellipse([(mp(sx_ - 190, sz_ - 150)[0] + 5, mp(sx_ - 190, sz_ - 150)[1] + 5), (mp(sx_ + 190, sz_ + 150)[0] + 5, mp(sx_ + 190, sz_ + 150)[1] + 5)], fill=(0, 0, 0, 90))
base = Image.alpha_composite(base.convert('RGBA'), shadow); base = Image.alpha_composite(base, roofs)
del shadow, roofs; log('buildings')
lines = Image.new('RGBA', (PX, PX), (0, 0, 0, 0)); ldraw = ImageDraw.Draw(lines)
STYLE = {'hwy': ((252, 252, 250), 10), 'ring': ((252, 252, 250), 9), 'avenue': ((244, 244, 242), 5), 'road': ((242, 242, 240), 5.5),
         'calle': ((228, 228, 226), 3), 'street': ((224, 224, 222), 2.5), 'dirt': ((190, 112, 52), 3)}    # clear hierarchy: highway > road > street > dirt
MINOR = ('calle', 'street')        # city streets: no dark edge, softer colour, so blocks read as texture
order = ['dirt', 'street', 'calle', 'road', 'avenue', 'ring', 'hwy']
for pass_ in ('edge', 'fill'):
    for kind in order:
        colr, wpx = STYLE[kind]
        for r in R['roads']:
            if r['kind'] != kind: continue
            P = [mp(p[0], p[2]) for p in r['pts']]
            if pass_ == 'edge' and (kind in MINOR or kind == 'dirt'): continue
            if pass_ == 'edge':
                ldraw.line(P, fill=(20, 26, 22, 110), width=int(round(wpx + 3)), joint='curve')
            elif kind == 'dirt':
                ldraw.line(P, fill=colr + (230,), width=int(round(wpx)), joint='curve')
            else:
                ldraw.line(P, fill=colr + ((200,) if kind in MINOR else (255,)), width=max(1, int(round(wpx))), joint='curve')
base = Image.alpha_composite(base, lines).convert('RGB')
del lines; log('roads')

# ---------------------------------------------------------------- tiles and minimap
os.makedirs(OUT, exist_ok=True)
for z, size in ((0, 1024), (1, 2048), (2, 4096)):
    im = base if size == PX else base.resize((size, size), Image.LANCZOS)
    d = os.path.join(OUT, f'z{z}'); os.makedirs(d, exist_ok=True)
    for ty in range(size // 512):
        for tx in range(size // 512):
            im.crop((tx * 512, ty * 512, tx * 512 + 512, ty * 512 + 512)).save(os.path.join(d, f'{tx}_{ty}.jpg'), quality=86, optimize=True)
base.resize((1024, 1024), Image.LANCZOS).save(os.path.join(OUT, 'map_1024.jpg'), quality=88, optimize=True)
log('tiles')

# ---------------------------------------------------------------- review image: labels + event icons
pv = base.resize((2048, 2048), Image.LANCZOS); dr = ImageDraw.Draw(pv); S = 2048 / SIZE
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
COLORS = {'asfalto': (40, 120, 255), 'tierra': (196, 110, 40), 'desafio': (150, 70, 220), 'especial': (240, 190, 30),
          'historia': (40, 190, 90), 'exploracion': (240, 90, 170), 'festival': (255, 255, 255)}
def icon(x, y, t):
    c = COLORS[t]; r = 9
    if t == 'desafio': pts = [(x, y - r), (x + r, y), (x, y + r), (x - r, y)]; dr.polygon(pts, fill=c, outline=(255, 255, 255), width=2)
    elif t == 'especial':
        pts = [(x + r * math.cos(a) * (1 if k % 2 == 0 else .45), y + r * math.sin(a) * (1 if k % 2 == 0 else .45)) for k, a in enumerate(np.linspace(-math.pi / 2, 1.5 * math.pi, 11)[:-1])]
        dr.polygon(pts, fill=c, outline=(255, 255, 255))
    elif t == 'exploracion': dr.rectangle((x - r + 2, y - r + 2, x + r - 2, y + r - 2), fill=c, outline=(255, 255, 255), width=2)
    elif t == 'festival': dr.ellipse((x - r - 3, y - r - 3, x + r + 3, y + r + 3), fill=(255, 255, 255), outline=(40, 40, 40), width=3)
    else: dr.ellipse((x - r, y - r, x + r, y + r), fill=c, outline=(255, 255, 255), width=2)
for e in E:
    x, _, z = e['pos']; icon((x + SIZE / 2) * S, (z + SIZE / 2) * S, e['type'])
for p in D['places']:
    imp = p['importance']; f = ImageFont.truetype(FONT, {1: 17, 2: 22, 3: 32}[imp])
    dr.text(((p['x'] + SIZE / 2) * S, (p['z'] + SIZE / 2) * S - 18), p['name'].upper() if imp > 1 else p['name'], font=f, fill=(255, 255, 255), anchor='mm', stroke_width=3, stroke_fill=(18, 24, 30))
legend = [('asfalto', 'Carreras de asfalto'), ('tierra', 'Tierra y rally'), ('desafio', 'Desafíos'), ('especial', 'Exhibiciones'), ('historia', 'Misiones'), ('exploracion', 'Exploración'), ('festival', 'Festival')]
lx, ly = 40, 1660; dr.rounded_rectangle((lx - 18, ly - 22, lx + 290, ly + 22 + 32 * len(legend)), 14, fill=(14, 20, 26))
f = ImageFont.truetype(FONT, 18)
for i, (t, name) in enumerate(legend):
    icon(lx + 6, ly + 10 + i * 32, t); dr.text((lx + 30, ly + 10 + i * 32), name, font=f, fill=(240, 240, 240), anchor='lm')
pv.save(os.path.join(OUT, 'map_preview.jpg'), quality=88)
log('done')
