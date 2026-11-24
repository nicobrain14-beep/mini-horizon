"""World generator for Mini Horizon - the state of "Valle Alto" (run: python3 tools/world/build_world.py).

8 x 8 km, X = east, Z = south (north is -Z), Y = up, metres. A Mexican-inspired state with
original names and no geometric shapes: everything is shaped with domain-warped noise.
Phase 1 (this file): relief, sea, lake, rivers, zones and the styled draft map.
Phase 2 adds the road network.

Writes to assets/world/: height.bin (float32, N x N, rows north -> south), zones.png (packed
masks), world.json (water, places) and map_draft.png (styled satellite-like map with labels).
"""
import json, math, os, sys, time
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
OUT = os.path.join(ROOT, 'assets', 'world')
SIZE = 8000.0
N = int(sys.argv[1]) if len(sys.argv) > 1 else 2001          # 4 m spacing by default
CELL = SIZE / (N - 1)
xs = np.linspace(-SIZE / 2, SIZE / 2, N).astype(np.float32)
X, Z = np.meshgrid(xs, xs)
T0 = time.time()
def log(*a): print(f'[{time.time() - T0:5.1f}s]', *a, flush=True)

def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1); return t * t * (3 - 2 * t)

class Perlin:
    def __init__(self, seed):
        r = np.random.default_rng(seed); p = r.permutation(256); self.p = np.concatenate([p, p])
        a = r.random(256) * 2 * np.pi; self.g = np.stack([np.cos(a), np.sin(a)], 1).astype(np.float32)
    def __call__(self, x, y):
        xi = np.floor(x).astype(np.int32) & 255; yi = np.floor(y).astype(np.int32) & 255
        xf = (x - np.floor(x)).astype(np.float32); yf = (y - np.floor(y)).astype(np.float32)
        u = xf * xf * xf * (xf * (xf * 6 - 15) + 10); v = yf * yf * yf * (yf * (yf * 6 - 15) + 10)
        def dot(ix, iy, dx, dy):
            g = self.g[self.p[self.p[ix] + iy] & 255]; return g[..., 0] * dx + g[..., 1] * dy
        n00 = dot(xi, yi, xf, yf); n10 = dot((xi + 1) & 255, yi, xf - 1, yf)
        n01 = dot(xi, (yi + 1) & 255, xf, yf - 1); n11 = dot((xi + 1) & 255, (yi + 1) & 255, xf - 1, yf - 1)
        return (n00 * (1 - u) + n10 * u) * (1 - v) + (n01 * (1 - u) + n11 * u) * v

def fbm(n, x, y, oct=5, gain=0.5):
    s, a, f, t = 0, 1.0, 1.0, 0
    for _ in range(oct): s = s + a * n(x * f, y * f); t += a; a *= gain; f *= 2.03
    return s / t

def ridged(n, x, y, oct=6):
    s, a, f, t, w = 0, 1.0, 1.0, 0, 1
    for _ in range(oct):
        r = 1 - np.abs(n(x * f, y * f)); r = r * r * w; w = np.clip(r * 2, 0, 1); s = s + a * r; t += a; a *= .5; f *= 2.1
    return s / t

P = [Perlin(s) for s in range(40)]
# domain warp: every shape is drawn on bent coordinates, so nothing is straight or round
WX = X + 520 * fbm(P[0], X / 2600, Z / 2600, 4) + 140 * fbm(P[1], X / 700, Z / 700, 3)
WZ = Z + 520 * fbm(P[2], X / 2600, Z / 2600, 4) + 140 * fbm(P[3], X / 700, Z / 700, 3)
def blob(cx, cz, rx, rz, soft):
    d = np.hypot((WX - cx) / rx, (WZ - cz) / rz)
    return 1 - smooth(1 - soft, 1 + soft, d)
log('warp')

# ---------------------------------------------------------------- land and sea
coast_n = 650 * fbm(P[4], X / 3200, Z / 3200, 3) + 260 * fbm(P[18], X / 1100, Z / 1100, 4) + 80 * fbm(P[19], X / 320, Z / 320, 3)
L = np.ones_like(X)
L -= smooth(-2650, -3350, WX + 0.28 * WZ + coast_n)                       # west coast (runs south-east)
L -= smooth(2250, 2950, WZ - 0.3 * WX + coast_n)                          # south coast (rises to the east)
L -= smooth(3000, 3700, WX - 0.2 * WZ + coast_n)                          # east coast
L -= 1.2 * blob(-2350, 2650, 800, 520, 0.4)                              # Puerto Chico cove
L -= 0.9 * blob(-3300, -1500, 650, 900, 0.45)                            # north-west gulf
L -= 1.0 * blob(-3150, 900, 700, 420, 0.5)                               # west bay
L += 0.8 * blob(-2900, 1800, 520, 300, 0.5)                              # a cape south of it
L -= 0.8 * blob(1250, 3050, 900, 380, 0.5)                               # a cove under the volcano
bay = blob(3050, 650, 1050, 700, 0.35)                                    # the metropolis bay
L -= 1.3 * bay
pen = np.exp(-(((WX - 2650) * 0.7 + (WZ - 2900) * 0.7) / 420) ** 2 - (((WX - 2650) * -0.7 + (WZ - 2900) * 0.7) / 1150) ** 2)
L += 1.4 * pen                                                            # south-east peninsula
L += 1.5 * blob(-1300, 3300, 220, 160, 0.5)                               # Isla Gaviota
land = smooth(0.42, 0.58, L)
LX = X + 380 * fbm(P[34], X / 900, Z / 900, 4); LZ = Z + 380 * fbm(P[35], X / 900, Z / 900, 4)
LX = LX + 160 * fbm(P[25], X / 300, Z / 300, 3); LZ = LZ + 160 * fbm(P[26], X / 300, Z / 300, 3)
lake = (1 - smooth(0.8, 1.15, np.hypot((LX + 2050) / 620, (LZ + 350) / 1000))) * land
lake *= 1 - (1 - smooth(0.6, 1.0, np.hypot((X + 2150) / 160, (Z + 150) / 110)))        # an island in the lake
log('land')

# ---------------------------------------------------------------- relief
lowland = 35 + 45 * fbm(P[5], X / 3000, Z / 3000, 4) + 18 * fbm(P[6], X / 800, Z / 800, 4)
hills = 70 * smooth(0.0, 0.6, fbm(P[7], X / 1600, Z / 1600, 4)) * (0.6 + 0.4 * fbm(P[8], X / 500, Z / 500, 3))
h = lowland + hills
sierra = blob(-2300, -2700, 2100, 1500, 0.45) * smooth(-900, -1700, WZ)
h += sierra * (180 + 900 * ridged(P[9], X / 1900, Z / 1900, 6))
plateau = blob(400, -2750, 1700, 950, 0.3)
h += plateau * (260 + 40 * fbm(P[10], X / 900, Z / 900, 3)) * (1 - sierra)
ne_high = blob(2600, -2500, 1500, 1300, 0.35)
h += ne_high * (300 + 120 * ridged(P[11], X / 1400, Z / 1400, 4)) * (1 - plateau)
# the volcano: asymmetric cone with radial gullies and a crater, south of centre
VX, VZ = 650, 1750
vr = np.hypot((X - VX) * 1.0, (Z - VZ) * 1.12)
ang = np.arctan2(Z - VZ, X - VX)
# irregular gullies: ridged noise in polar coordinates, of varying width, fading near the top
gul = ridged(P[12], np.cos(ang) * 6 + vr / 900, np.sin(ang) * 6 + 0.3 * fbm(P[36], X / 500, Z / 500, 2), 4)
gullies = 1 - 0.03 * gul * smooth(250, 900, vr) * (0.6 + 0.4 * fbm(P[37], X / 400, Z / 400, 2))
lobes = 1 + 0.12 * fbm(P[38], np.cos(ang) * 2.2, np.sin(ang) * 2.2, 3)       # not a perfect cone
cone = 1480 * np.clip(1 - vr / (2500 * lobes), 0, 1) ** 1.85 * gullies * (0.94 + 0.06 * fbm(P[13], X / 600, Z / 600, 3))
cone = np.maximum(cone, 520 * np.clip(1 - np.hypot(X - 1500, Z - 1350) / 900, 0, 1) ** 1.6)   # a side cone
crater = 120 * (1 - smooth(70, 190, vr))
h = np.maximum(h, cone - crater)
# plains for farmland: flatten gently
farm = blob(1700, -1050, 1300, 800, 0.4) * (1 - ne_high * 0.6) * (1 - plateau)
h = h + ((45 + 12 * fbm(P[14], X / 2000, Z / 2000, 3)) - h) * farm * 0.75
# city sites: flatter ground
METRO = (2250, 520); COLONIAL = (-1650, 1350)
metro = blob(METRO[0], METRO[1], 900, 750, 0.35) * smooth(0.5, 0.75, L)
colonial = blob(COLONIAL[0], COLONIAL[1], 420, 360, 0.3)
h = h + ((18 + 6 * fbm(P[15], X / 900, Z / 900, 2)) - h) * metro * 0.85
h = h + ((90 + 10 * fbm(P[16], X / 500, Z / 500, 2)) - h) * colonial * 0.7
# coast: beaches, cliffs on the peninsula, sea floor
shore = smooth(0.45, 1.0, L) ** 0.8                                    # a wide, low coastal plain
cliffs = pen * 0.8 * smooth(0.4, 0.7, fbm(P[24], X / 800, Z / 800, 3) + 0.5)
h = h * (shore * (1 - cliffs) + cliffs) + 1.4 * (1 - shore) * (1 - cliffs)
sea_floor = -30 + 10 * fbm(P[17], X / 900, Z / 900, 3) - 40 * smooth(0.4, 0.0, L)
h = h * land + sea_floor * (1 - land)
LAKE_LEVEL = 42.0
h = np.where(lake > 0.02, h * (1 - lake) + (LAKE_LEVEL - 4 - 14 * lake) * lake, h)
rim = smooth(0.0, 0.02, lake) * (1 - smooth(0.02, 0.3, lake))
h = np.where((lake > 0) & (lake < 0.3), np.maximum(h, LAKE_LEVEL + 1.5), h)
log('relief', round(float(h.min()), 1), round(float(h.max()), 1))

def sample(px, pz, grid):
    fx = np.clip((np.asarray(px) + SIZE / 2) / CELL, 0, N - 1.001); fz = np.clip((np.asarray(pz) + SIZE / 2) / CELL, 0, N - 1.001)
    ix, iz = fx.astype(int), fz.astype(int); tx, tz = fx - ix, fz - iz
    a = grid[iz, ix] * (1 - tx) + grid[iz, ix + 1] * tx; b = grid[iz + 1, ix] * (1 - tx) + grid[iz + 1, ix + 1] * tx
    return a * (1 - tz) + b * tz

def box_blur(a, r, passes=3):
    a = a.astype(np.float32)
    for _ in range(passes):
        for ax in (0, 1):
            c = np.cumsum(np.pad(a, [(r + 1, r) if i == ax else (0, 0) for i in range(2)], mode='edge'), axis=ax, dtype=np.float64)
            a = ((np.take(c, range(2 * r + 1, c.shape[ax]), axis=ax) - np.take(c, range(0, c.shape[ax] - 2 * r - 1), axis=ax)) / (2 * r + 1)).astype(np.float32)
    return a

def chaikin(pts, it=4):
    p = np.asarray(pts, float)
    for _ in range(it):
        q = 0.75 * p[:-1] + 0.25 * p[1:]; r = 0.25 * p[:-1] + 0.75 * p[1:]
        p = np.vstack([p[0], np.column_stack([q, r]).reshape(-1, 2), p[-1]])
    return p

def resample(pts, step):
    pts = np.asarray(pts, float); d = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(pts, axis=0).T))])
    s = np.append(np.arange(0, d[-1], step), d[-1])
    return np.column_stack([np.interp(s, d, pts[:, 0]), np.interp(s, d, pts[:, 1])])

# ---------------------------------------------------------------- rivers (meandering, always downhill)
RIVERS = [
    ('Río Frío', [(-2700, -3900), (-2550, -3000), (-2350, -2200), (-2250, -1500)], 14, 0),
    ('Río Lento', [(-2700, 200), (-3050, 350), (-3500, 420)], 18, 1),
    ('Río de la Barranca', [(1300, -3950), (1750, -3350), (1650, -2900), (2250, -2550), (2450, -2050), (2950, -1950), (3250, -1550), (3900, -1450)], 16, 2),
    ('Río Manso', [(900, -1700), (1350, -900), (1750, -150), (2350, 300), (2750, 560)], 20, 3),
    ('Arroyo del Volcán', [(420, 2500), (300, 2850), (180, 3300)], 9, 4),
]
river_out = []; rmask = np.zeros_like(h); dist_r = np.full(h.shape, 1e9, np.float32)
for name, ctrl, hw, seed in RIVERS:
    pts = resample(chaikin(ctrl, 4), 6.0)
    tg = np.gradient(pts, axis=0); tg /= np.maximum(np.linalg.norm(tg, axis=1, keepdims=True), 1e-6)
    pp = np.column_stack([-tg[:, 1], tg[:, 0]]); s_ = np.arange(len(pts)) * 6.0
    off = 90 * np.sin(s_ / 380 + seed) * (0.6 + 0.4 * np.sin(s_ / 1700)) + 60 * fbm(P[20 + seed], s_ / 450, np.zeros_like(s_) + .3, 4)
    pts = resample(pts + pp * off[:, None], 6.0)
    hs0 = sample(pts[:, 0], pts[:, 1], h)
    wet = np.nonzero(hs0 < 0.5)[0]                                        # stop where it reaches the sea
    if len(wet) and wet[0] > 10: pts = pts[:wet[0] + 3]
    y = sample(pts[:, 0], pts[:, 1], h) - 3.0
    y = np.minimum.accumulate(y); y = np.maximum(y, -1.0)
    inl = sample(pts[:, 0], pts[:, 1], lake) > 0.3
    y = np.where(inl, LAKE_LEVEL - 1, y); y = np.minimum.accumulate(y)
    bed = np.zeros_like(h); best = np.full(h.shape, 1e9, np.float32)
    canyon = 1.0 if seed == 2 else 0.0
    for (x, z), yy in zip(pts[::2], y[::2]):
        R = hw + (260 if canyon else 60)
        i0, i1 = max(int((z - R + SIZE / 2) / CELL), 0), min(int((z + R + SIZE / 2) / CELL) + 1, N - 1)
        j0, j1 = max(int((x - R + SIZE / 2) / CELL), 0), min(int((x + R + SIZE / 2) / CELL) + 1, N - 1)
        sub = (slice(i0, i1 + 1), slice(j0, j1 + 1)); d = np.hypot(X[sub] - x, Z[sub] - z)
        b = d < best[sub]; best[sub] = np.where(b, d, best[sub]); bed[sub] = np.where(b, yy, bed[sub])
    if canyon:   # the barranca: steep walls up to the high ground
        wall = 1 - smooth(hw, hw + 230, best + 40 * fbm(P[30], X / 300, Z / 300, 3))
        h = h + (bed - 1.0 - h) * np.clip(wall ** 0.6, 0, 1)
    else:
        bank = 1 - smooth(hw, hw + 50, best)
        h = h + (bed - 1.0 - h) * bank
    dist_r = np.minimum(dist_r, best - hw)
    river_out.append(dict(name=name, hw=hw, pts=np.round(np.column_stack([pts[:, 0], y + 2.0, pts[:, 1]]), 1).tolist()))
water = (h < 0.4) | (lake > 0.35) | (dist_r < 0)
log('rivers')

# ---------------------------------------------------------------- biomes (weights 0..1)
gz, gx = np.gradient(h, CELL)
slope = np.degrees(np.arctan(np.hypot(gx, gz)))
n1 = 0.5 + 0.5 * fbm(P[31], X / 220, Z / 220, 4)
n2 = 0.5 + 0.5 * fbm(P[32], X / 1300, Z / 1300, 4)
snow = smooth(1000, 1150, h + 120 * (n1 - .5) + 90 * gul * smooth(2500, 1200, vr)) * smooth(46, 30, slope)
rock = np.clip(smooth(28, 42, slope) + smooth(850, 1000, h) * 0.5, 0, 1) * (1 - snow)
semidesert = plateau * (0.7 + 0.3 * n2) * (1 - sierra)
forest = np.clip((sierra * smooth(200, 320, h) * smooth(1000, 820, h) + smooth(250, 420, h) * smooth(1000, 820, h) * smooth(2600, 1500, vr)) * (0.45 + 0.75 * n1)
                 + 0.55 * blob(-400, -1500, 900, 600, 0.4) * smooth(0.45, 0.7, n1), 0, 1) * (1 - semidesert)
farmland = farm * (1 - forest) * (1 - semidesert)
beach = smooth(6, 2, h) * land * (1 - pen * 0.7)
city = np.clip(metro * 0.95 + colonial * 0.8, 0, 1)
ash = smooth(1700, 900, vr) * smooth(250, 500, h) * (1 - snow)                # dark volcanic soil
mud = smooth(40, 0, dist_r) * (1 - water) * 0.7
log('biomes')

# ---------------------------------------------------------------- styled draft map (satellite look, painted from the data)
R_ = np.random.default_rng(11)
city_hint = np.clip(metro + colonial, 0, 1)
def col(*c): return np.array(c, np.float32) / 255.0
img = np.zeros(h.shape + (3,), np.float32)
n3 = 0.5 + 0.5 * fbm(P[39], X / 600, Z / 600, 4)
grass = col(98, 128, 66) * (0.85 + 0.3 * n1[..., None]) + (col(156, 152, 88) - col(98, 128, 66)) * (smooth(0.35, 0.75, n2) * 0.8)[..., None]
grass = grass * (0.9 + 0.2 * n3[..., None])
img[:] = grass
woods = np.clip(smooth(0.55, 0.64, n3) * smooth(0.25, 0.55, n1) + 0.6 * smooth(0.6, 0.7, 0.5 + 0.5 * fbm(P[27], X / 250, Z / 250, 4)), 0, 1) * land * (1 - farm) * (1 - city_hint)
# farmland: fields in a few directions per district, each field its own crop colour
fdir = np.floor((0.5 + 0.5 * fbm(P[33], X / 1800, Z / 1800, 2)) * 4)
ang_f = 0.35 + fdir * 0.55
u = (X * np.cos(ang_f) + Z * np.sin(ang_f) + 0.2 * (WX - X)) / 150
v = (-X * np.sin(ang_f) + Z * np.cos(ang_f) + 0.2 * (WZ - Z)) / 95
fid = (np.floor(u).astype(np.int64) * 73856093 ^ np.floor(v).astype(np.int64) * 19349663 ^ fdir.astype(np.int64) * 83492791) % 997
crop = np.array([[176, 166, 86], [128, 150, 72], [150, 124, 84], [196, 184, 112], [96, 128, 64], [142, 140, 76], [120, 104, 74]], np.float32) / 255
fc = crop[fid % 7] * (0.92 + 0.16 * n1[..., None])
edge = np.minimum(np.minimum(u - np.floor(u), 1 - (u - np.floor(u))), np.minimum(v - np.floor(v), 1 - (v - np.floor(v))))
fc *= (0.78 + 0.22 * smooth(0.0, 0.06, edge))[..., None]
img = img * (1 - farmland[..., None]) + fc * farmland[..., None]
# forest: dark canopy speckle
speck = R_.random(h.shape).astype(np.float32)
speck = np.asarray(Image.fromarray((speck * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8)), np.float32) / 255
fcol = col(44, 76, 42) * (0.7 + 0.6 * speck[..., None]) * (0.85 + 0.3 * n1[..., None])
img = img * (1 - forest[..., None]) + fcol * forest[..., None]
img = img * (1 - woods[..., None] * 0.8) + fcol * woods[..., None] * 0.8
sd = col(178, 152, 108) * (0.85 + 0.25 * n1[..., None]) + (col(150, 136, 92) - col(178, 152, 108)) * smooth(0.6, 0.9, speck)[..., None] * 0.6
img = img * (1 - semidesert[..., None]) + sd * semidesert[..., None]
ashc = col(92, 70, 60) * (0.85 + 0.3 * n1[..., None])
img = img * (1 - ash[..., None] * 0.85) + ashc * ash[..., None] * 0.85
rk = col(128, 118, 106) * (0.8 + 0.4 * n1[..., None])
img = img * (1 - rock[..., None]) + rk * rock[..., None]
img = img * (1 - snow[..., None]) + col(240, 244, 248) * snow[..., None]
img = img * (1 - beach[..., None]) + col(226, 210, 168) * beach[..., None]
img = img * (1 - mud[..., None] * 0.5) + col(98, 92, 66) * mud[..., None] * 0.5
cityc = col(168, 166, 160) * (0.8 + 0.25 * speck[..., None])
img = img * (1 - city[..., None] * 0.85) + cityc * city[..., None] * 0.85
# relief: hillshade from the north-west plus a soft ambient term
lx, ly, lz = -0.55, 0.62, -0.55
nrm = np.stack([-gx, np.ones_like(h), -gz], -1); nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
shade = np.clip(nrm[..., 0] * lx + nrm[..., 1] * ly + nrm[..., 2] * lz, 0, 1) / ly
hb = box_blur(h, 4)
ao = np.clip(1 + (h - hb) * 0.012, 0.75, 1.15)
img *= ((0.55 + 0.55 * shade) * ao)[..., None]
# water: deep blue, lighter near the shore, a pale line on the beach
depth = np.clip(-h / 35, 0, 1)
wcol = col(36, 96, 126) * (1 - depth[..., None]) + col(14, 42, 72) * depth[..., None]
wcol = np.where((((lake > 0.35) | (dist_r < 0)) & (h > 0.4))[..., None], col(40, 104, 128), wcol)
img = np.where(water[..., None], wcol, img)
foam = water & (np.asarray(Image.fromarray((~water).astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(5)), np.uint8) > 0)
img = np.where(foam[..., None], img * 0.4 + col(214, 230, 232) * 0.6, img)
img = np.clip(img, 0, 1)
im = Image.fromarray((img * 255).astype(np.uint8), 'RGB')
MAP_PX = 2048
im = im.resize((MAP_PX, MAP_PX), Image.LANCZOS)
im = im.filter(ImageFilter.UnsharpMask(radius=1.2, percent=60, threshold=2))

PLACES = [
    ('ciudad', 'CIUDAD ALTA', METRO[0], METRO[1], 3), ('colonial', 'SAN LUCERO', COLONIAL[0], COLONIAL[1], 2),
    ('volcan', 'VOLCÁN TIZÓN', VX, VZ - 250, 3), ('lago', 'LAGO ESPEJO', -2150, -350, 2),
    ('sierra', 'SIERRA DEL NORTE', -2300, -2900, 2), ('barranca', 'LA BARRANCA', 2550, -2350, 2),
    ('meseta', 'MESETA SECA', 400, -2750, 2), ('campos', 'LLANO DE LOS MAGUEYES', 1700, -1150, 2),
    ('pescadores', 'Tlacotal', -1450, -700, 1), ('montana', 'Real de Piedra', -1950, -2350, 1),
    ('costa', 'Puerto Chico', -2650, 2300, 1), ('magueyes', 'Los Magueyes', 1300, -1500, 1),
    ('festival', 'FESTIVAL HORIZONTE', -350, 250, 2), ('peninsula', 'PUNTA AZUL', 2750, 3000, 2),
    ('isla', 'Isla Gaviota', -1330, 3230, 1), ('bahia', 'Bahía Alta', 3100, 750, 1),
]
def on_land(x, z):
    if sample(x, z, h) > 2 and not sample(x, z, water.astype(np.float32)) > 0.3: return x, z
    for r in range(80, 1600, 80):
        for a in np.linspace(0, 2 * np.pi, 24, endpoint=False):
            qx, qz = x + r * np.cos(a), z + r * np.sin(a)
            if sample(qx, qz, h) > 3 and sample(qx, qz, water.astype(np.float32)) < 0.1: return float(qx), float(qz)
    return x, z
PLACES = [(p[0], p[1], *on_land(p[2], p[3]), p[4]) if p[0] not in ('lago', 'bahia', 'isla') else p for p in PLACES]
draw = ImageDraw.Draw(im)
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
for pid, label, x, z, imp in PLACES:
    px = (x + SIZE / 2) / SIZE * MAP_PX; pz = (z + SIZE / 2) / SIZE * MAP_PX
    f = ImageFont.truetype(FONT, {1: 18, 2: 24, 3: 34}[imp])
    draw.text((px, pz), label, font=f, fill=(255, 255, 255), anchor='mm', stroke_width=3 if imp > 1 else 2, stroke_fill=(20, 28, 34))
os.makedirs(OUT, exist_ok=True)
im.save(os.path.join(OUT, 'map_draft.png'), optimize=True)
h.astype('<f4').tofile(os.path.join(OUT, 'height.bin'))
zones = np.stack([forest, farmland, semidesert, city], -1)
Image.fromarray((np.clip(zones, 0, 1) * 255).astype(np.uint8), 'RGBA').save(os.path.join(OUT, 'zones.png'), optimize=True)
json.dump(dict(v=3, name='Valle Alto', size=SIZE, n=N, spacing=CELL, sea=0.0, lake=dict(level=LAKE_LEVEL), rivers=river_out,
               places=[dict(id=p[0], name=p[1], x=p[2], z=p[3], importance=p[4], y=round(float(sample(p[2], p[3], h)), 1)) for p in PLACES]),
          open(os.path.join(OUT, 'world.json'), 'w'), separators=(',', ':'))
log('done', N, 'x', N)
