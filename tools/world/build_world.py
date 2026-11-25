"""World generator for Mini Horizon - the state of "Valle Alto" (run: python3 tools/world/build_world.py).

8 x 8 km, X = east, Z = south (north is -Z), Y = up, metres. A Mexican-inspired state with
original names and no geometric shapes: everything is shaped with domain-warped noise.
Phase 1 (this file): relief, sea, lake, rivers, zones and the styled draft map.
Phase 2 adds the road network.

Writes to assets/world/: height.bin (float32, N x N, rows north -> south), cache.npz (masks for the
road builder and the map painter) and world.json (water, places). Then run build_roads.py and paint_map.py.
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
coast_n = 650 * fbm(P[4], X / 3200, Z / 3200, 3) + 340 * fbm(P[18], X / 1100, Z / 1100, 4) + 150 * fbm(P[19], X / 380, Z / 380, 4) + 40 * fbm(P[23], X / 110, Z / 110, 3)
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
for ix, (cx_, cz_, rr) in enumerate([(-3550, -2600, 160), (-3600, 1500, 120), (3550, 2300, 150), (3350, -2900, 110), (600, 3500, 140), (-2200, 3350, 90), (3750, 1900, 80)]):
    L += 1.5 * blob(cx_, cz_, rr, rr * 0.8, 0.5)                             # islets along the coast
land = smooth(0.42, 0.58, L)
LX = X + 380 * fbm(P[34], X / 900, Z / 900, 4); LZ = Z + 380 * fbm(P[35], X / 900, Z / 900, 4)
LX = LX + 160 * fbm(P[25], X / 300, Z / 300, 3); LZ = LZ + 160 * fbm(P[26], X / 300, Z / 300, 3)
lake = (1 - smooth(0.8, 1.15, np.hypot((LX + 2050) / 620, (LZ + 350) / 1000))) * land
# islands in the lake: irregular, elongated, with a smaller islet beside the big one
IX = X + 70 * fbm(P[30], X / 140, Z / 140, 3); IZ = Z + 70 * fbm(P[31], X / 140, Z / 140, 3)
isl = 1 - smooth(0.75, 1.0, np.hypot(((IX + 2120) * 0.82 + (IZ + 180) * 0.57) / 230, ((IX + 2120) * -0.57 + (IZ + 180) * 0.82) / 105))
isl = np.maximum(isl, 1 - smooth(0.7, 1.0, np.hypot((IX + 1880) / 55, (IZ + 20) / 40)))
lake *= 1 - isl
log('land')

# ---------------------------------------------------------------- relief
lowland = 30 + 40 * fbm(P[5], X / 3000, Z / 3000, 4) + 14 * fbm(P[6], X / 800, Z / 800, 4)
hilliness = smooth(-0.25, 0.35, fbm(P[7], X / 2200, Z / 2200, 3))            # where the land is hilly (most of it)
hills = (60 + 230 * ridged(P[8], X / 1300, Z / 1300, 6)) * hilliness + 25 * fbm(P[28], X / 350, Z / 350, 4) * hilliness
h = lowland + hills
sierra = blob(-2300, -2700, 2100, 1500, 0.45) * smooth(-900, -1700, WZ)
h += sierra * (180 + 900 * ridged(P[9], X / 1900, Z / 1900, 6))
plateau = blob(400, -2750, 1700, 950, 0.3)
h += plateau * (250 + 40 * fbm(P[10], X / 900, Z / 900, 3) + 70 * ridged(P[27], X / 700, Z / 700, 4)) * (1 - sierra)
ne_high = blob(2600, -2500, 1500, 1300, 0.35)
h += ne_high * (300 + 120 * ridged(P[11], X / 1400, Z / 1400, 4)) * (1 - plateau)
# the volcano: asymmetric cone with radial gullies and a crater, south of centre
VX, VZ = 650, 1750
vr = np.hypot((X - VX) * 1.0, (Z - VZ) * 1.12)
ang = np.arctan2(Z - VZ, X - VX)
# irregular gullies: ridged noise in polar coordinates, of varying width, fading near the top
gul = ridged(P[12], (X - VX) / 380 + 0.6 * fbm(P[36], X / 900, Z / 900, 2), (Z - VZ) / 380, 5)
gullies = 1 - 0.012 * gul * smooth(500, 1200, vr) * (0.6 + 0.4 * fbm(P[37], X / 400, Z / 400, 2))
lobes = 1 + 0.08 * fbm(P[38], np.cos(ang) * 1.1 + 3.3, np.sin(ang) * 1.1 + 1.7, 2)   # not a perfect cone (slow, no rays)
cone = 1480 * np.clip(1 - vr / (2500 * lobes), 0, 1) ** 1.85 * gullies * (0.94 + 0.06 * fbm(P[13], X / 600, Z / 600, 3))
cone = np.maximum(cone, 520 * np.clip(1 - np.hypot(X - 1500, Z - 1350) / 900, 0, 1) ** 1.6)   # a side cone
crater = 90 * (1 - smooth(60, 200, vr + 30 * fbm(P[29], X / 80, Z / 80, 2)))
h = np.maximum(h, cone - crater)
# plains for farmland: flatten gently
farm = blob(1700, -1050, 1300, 800, 0.4) * (1 - ne_high * 0.6) * (1 - plateau)
h = h + ((45 + 12 * fbm(P[14], X / 2000, Z / 2000, 3)) - h) * farm * 0.75
# city sites: flatter ground
METRO = (2350, 300); COLONIAL = (-1650, 1350)
metro = blob(METRO[0], METRO[1], 1550, 1250, 0.45)
metro = smooth(0.35, 0.55, metro + 0.45 * fbm(P[21], X / 700, Z / 700, 3) + 0.15 * fbm(P[22], X / 220, Z / 220, 3)) * smooth(0.5, 0.75, L)
colonial = blob(COLONIAL[0], COLONIAL[1], 760, 640, 0.45)
colonial = smooth(0.35, 0.55, colonial + 0.45 * fbm(P[24], X / 450, Z / 450, 3) + 0.15 * fbm(P[25], X / 160, Z / 160, 3))
h = h + ((18 + 10 * fbm(P[15], X / 900, Z / 900, 2)) - h) * metro * 0.9
h = h + ((70 + 14 * fbm(P[16], X / 500, Z / 500, 2)) - h) * colonial * 0.8
# coast: beaches, cliffs on the peninsula, sea floor
shore = smooth(0.45, 1.25, L) ** 0.65                                   # a wide, low coastal plain
cliffs = pen * 0.8 * smooth(0.4, 0.7, fbm(P[24], X / 800, Z / 800, 3) + 0.5)
h = h * (shore * (1 - cliffs) + cliffs) + 1.4 * (1 - shore) * (1 - cliffs)
sea_floor = -4 - 26 * smooth(0.42, 0.05, L) + 2 * fbm(P[17], X / 900, Z / 900, 3) - 20 * smooth(0.1, -0.4, L)
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

MINIS = {'tlacotal': (-1350, -700, 420), 'puerto_chico': (-2600, 2000, 420), 'los_magueyes': (1300, -1500, 420)}
hb_city = box_blur(h, 25)
mini_mask = np.zeros_like(h)
for _id, (cx, cz, r) in MINIS.items():
    m = (1 - smooth(r * 0.6, r * 1.2, np.hypot(X - cx, Z - cz) + 0.5 * (WX - X) + 160 * fbm(P[26], X / 260, Z / 260, 3))) * smooth(0.5, 0.7, L)
    mini_mask = np.maximum(mini_mask, m)
    h = h + (np.maximum(hb_city, 3.0) - h) * m * 0.9

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
snow = smooth(880, 1040, h + 160 * (n1 - .5)) * smooth(72, 58, slope)
rock = np.clip(smooth(38, 52, slope) + smooth(950, 1100, h) * 0.6, 0, 1) * (1 - snow)
semidesert = plateau * (0.7 + 0.3 * n2) * (1 - sierra)
beach_hint = smooth(8, 2, h)
open_land = np.clip(farm * 0.9 + metro + colonial + beach_hint + smooth(0.68, 0.8, n1) * 0.8, 0, 1)      # clearings come from noise, not from flat ground
forest = np.clip(0.75 + 0.5 * hilliness + sierra * 0.8 + 0.4 * (n2 - 0.5), 0, 1)
forest = forest * smooth(1050, 880, h) * (1 - np.clip(open_land, 0, 1)) * (1 - semidesert * 0.7) * (1 - smooth(560, 760, h) * smooth(1700, 1200, vr))
farmland = farm * (1 - forest) * (1 - semidesert)
beach = smooth(6, 2, h) * land * (1 - pen * 0.7)
city = np.clip(metro * 0.95 + colonial * 0.8, 0, 1)
ash = smooth(1500, 900, vr) * smooth(560, 760, h + 60 * (n1 - 0.5)) * (1 - snow)   # bare volcanic soil above the tree line
mud = smooth(40, 0, dist_r) * (1 - water) * 0.7
log('biomes')

PLACES = [
    ('ciudad', 'CIUDAD ALTA', METRO[0], METRO[1], 3), ('colonial', 'SAN LUCERO', COLONIAL[0], COLONIAL[1], 2),
    ('volcan', 'VOLCÁN TIZÓN', VX, VZ - 250, 3), ('lago', 'LAGO ESPEJO', -2150, -350, 2),
    ('sierra', 'SIERRA DEL NORTE', -2300, -2900, 2), ('barranca', 'LA BARRANCA', 2550, -2350, 2),
    ('meseta', 'MESETA SECA', 400, -2750, 2), ('campos', 'LLANO DE LOS MAGUEYES', 1700, -1150, 2),
    ('tlacotal', 'Tlacotal', -1430, -700, 2), ('montana', 'Real de Piedra', -1950, -2350, 1),
    ('puerto_chico', 'Puerto Chico', -2750, 2080, 2), ('los_magueyes', 'Los Magueyes', 1300, -1500, 2),
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
os.makedirs(OUT, exist_ok=True)
h.astype('<f4').tofile(os.path.join(OUT, 'height.bin'))
f16 = lambda a: np.asarray(a, np.float16)
np.savez_compressed(os.path.join(OUT, 'cache.npz'), h=h.astype(np.float32), land=f16(land), lake=f16(lake), water=water, dist_r=dist_r.astype(np.float32),
    forest=f16(forest), farmland=f16(farmland), semidesert=f16(semidesert), metro=f16(metro), colonial=f16(colonial), snow=f16(snow), rock=f16(rock),
    beach=f16(beach), ash=f16(ash), mud=f16(mud), pen=f16(pen), farm=f16(farm), mini=f16(mini_mask), hilly=f16(hilliness), vr=vr.astype(np.float32), n1=f16(n1), n2=f16(n2), WX=WX.astype(np.float32), WZ=WZ.astype(np.float32))
json.dump(dict(v=3, name='Valle Alto', size=SIZE, n=N, spacing=CELL, sea=0.0, lake=dict(level=LAKE_LEVEL), rivers=river_out,
               cities=dict(ciudad=dict(tier='grande', x=METRO[0], z=METRO[1], r=900), san_lucero=dict(tier='mediana', x=COLONIAL[0], z=COLONIAL[1], r=430),
                           **{k: dict(tier='mini', x=v[0], z=v[1], r=v[2]) for k, v in MINIS.items()}),
               volcano=dict(x=VX, z=VZ),
               places=[dict(id=p[0], name=p[1], x=round(float(p[2]), 1), z=round(float(p[3]), 1), importance=p[4], y=round(float(sample(p[2], p[3], h)), 1)) for p in PLACES]),
          open(os.path.join(OUT, 'world.json'), 'w'), separators=(',', ':'))
log('done', N, 'x', N)
