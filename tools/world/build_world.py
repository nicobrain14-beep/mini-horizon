"""World generator for Mini Horizon (run: python3 tools/world/build_world.py). Takes ~2 minutes.

A 4 x 4 km "state" centred on the origin. X = east, Z = south (north is -Z), Y = up, metres.
Coast with a bay, a peninsula and an island to the south-east; a lake and a river; a volcano;
the Sierra to the north; Sahara dunes to the west; a red-rock canyon desert to the south-west;
farmland patchwork in the middle; the poor town San Lucero and the Festival in the centre; a big
city on the bay; a beach town on the south coast. Roads are routed with A* over a slope/water cost
map, so they wind through the hills like real roads; plus a city street web and town streets.

Writes assets/world/: height.bin (float32 N*N, rows north->south), splat0.png (grass, dirt, rock,
beach sand), splat1.png (dune sand, red desert, snow, forest), roads.png (R = distance to road edge
x4, G = road kind), map.png (styled map, 1024 px) and world.json (roads, rivers, lakes, places).
"""
import heapq, json, math, os, time
import numpy as np
from PIL import Image

ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
OUT = os.path.join(ROOT, 'assets', 'world')
SIZE, N = 4000.0, 2001
CELL = SIZE / (N - 1)
xs = np.linspace(-SIZE / 2, SIZE / 2, N)
X, Z = np.meshgrid(xs, xs)
T0 = time.time()

def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1); return t * t * (3 - 2 * t)

class Perlin:
    def __init__(self, seed):
        r = np.random.default_rng(seed); p = r.permutation(256); self.p = np.concatenate([p, p])
        a = r.random(256) * 2 * np.pi; self.g = np.stack([np.cos(a), np.sin(a)], 1)
    def __call__(self, x, y):
        xi = np.floor(x).astype(int) & 255; yi = np.floor(y).astype(int) & 255
        xf = x - np.floor(x); yf = y - np.floor(y)
        u = xf * xf * xf * (xf * (xf * 6 - 15) + 10); v = yf * yf * yf * (yf * (yf * 6 - 15) + 10)
        def dot(ix, iy, dx, dy):
            g = self.g[self.p[self.p[ix] + iy] & 255]; return g[..., 0] * dx + g[..., 1] * dy
        n00 = dot(xi, yi, xf, yf); n10 = dot(xi + 1 & 255, yi, xf - 1, yf)
        n01 = dot(xi, yi + 1 & 255, xf, yf - 1); n11 = dot(xi + 1 & 255, yi + 1 & 255, xf - 1, yf - 1)
        return (n00 * (1 - u) + n10 * u) * (1 - v) + (n01 * (1 - u) + n11 * u) * v

def fbm(n, x, y, oct=5):
    s, a, f, t = 0, 1, 1, 0
    for _ in range(oct): s = s + a * n(x * f, y * f); t += a; a *= .5; f *= 2.03
    return s / t

def ridged(n, x, y, oct=5):
    s, a, f, t, w = 0, 1, 1, 0, 1
    for _ in range(oct):
        r = 1 - np.abs(n(x * f, y * f)); r = r * r * w; w = np.clip(r * 2, 0, 1); s = s + a * r; t += a; a *= .5; f *= 2.1
    return s / t

P = [Perlin(s) for s in range(30)]
warp = 160 * fbm(P[11], X / 500, Z / 500, 3)
def gauss(cx, cz, rx, rz=None):
    rz = rz or rx; return np.exp(-(((X - cx) / rx) ** 2 + ((Z - cz) / rz) ** 2))
def blob(cx, cz, rx, rz, soft, w=1.0):
    d = np.hypot((X - cx) / rx, (Z - cz) / rz) * min(rx, rz) + warp * w
    return 1 - smooth(min(rx, rz) - soft, min(rx, rz) + soft, d)

# ---------------------------------------------------------------- land and water
L = 0.62 + 0.28 * fbm(P[1], X / 900, Z / 900, 5)
L -= 0.9 * smooth(1050, 1850, Z + 0.35 * X)                          # sea to the south
L -= 0.9 * smooth(1350, 1950, X - 0.2 * Z)                           # sea to the east
L -= 1.1 * gauss(1680, 700, 470, 360)                               # the city bay
L += 0.85 * np.exp(-(((X - 1350) * 0.8 + (Z - 1300) * 0.6) / 230) ** 2 - (((X - 1350) * -0.6 + (Z - 1300) * 0.8) / 520) ** 2)  # peninsula
L += 1.2 * gauss(1720, 1720, 170, 140)                              # island
L -= 0.9 * smooth(-1700, -1950, X)                                  # thin sea strip far west
land = smooth(-0.04, 0.06, L)
lake = blob(-780, -260, 260, 380, 60, 0.4) * (land > 0.5)

# ---------------------------------------------------------------- zones
north = smooth(-700, -1300, Z + 0.15 * X)
volcano_r = np.hypot(X - 1050, Z + 1180)
sahara = blob(-1450, 150, 480, 700, 160, 1.7)
desert = blob(-1050, 1150, 560, 420, 140, 1.7) * (1 - sahara)
pueblo = 1 - smooth(200, 280, np.hypot(X - 0, Z - 250))
festival = 1 - smooth(110, 170, np.hypot(X - 330, Z - 560))
city = blob(1180, 330, 420, 520, 90, 0.3) * smooth(0.2, 0.4, L)
beachtown = 1 - smooth(140, 220, np.hypot(X - 250, Z - 1380))
farm = blob(250, -350, 900, 450, 200) * (1 - north) * (1 - city)

# ---------------------------------------------------------------- heights
h = 22 + 16 * fbm(P[2], X / 700, Z / 700, 5) + 30 * smooth(0.3, 0.9, fbm(P[3], X / 1500, Z / 1500, 3) + 0.4)
ranges = 80 + 470 * ridged(P[4], X / 800, Z / 800, 6) * north
h = np.maximum(h, h + (ranges - h) * north)
cone = 560 * np.clip(1 - volcano_r / 900, 0, 1) ** 1.6 - 70 * smooth(110, 40, volcano_r)
h = np.maximum(h, cone + 10 * fbm(P[5], X / 120, Z / 120, 3) * smooth(80, 200, volcano_r))
dunes = 34 + 24 * (0.5 + 0.5 * np.sin((X * 0.8 + Z * 0.6) / 40 + 3 * fbm(P[6], X / 280, Z / 280, 3))) * (0.6 + 0.4 * fbm(P[7], X / 420, Z / 420, 3)) + 10 * fbm(P[8], X / 140, Z / 140, 3)
h = h + (dunes - h) * sahara
t = 0.5 + 0.5 * fbm(P[9], X / 320, Z / 320, 4); q = np.floor(t * 4); fr = t * 4 - q
mesas = 24 + 80 * ((q + smooth(0.75, 0.95, fr)) / 4) ** 1.4
h = h + (mesas - h) * desert
for m, lvl in ((pueblo, 30), (festival, 28), (city, 14), (beachtown, 6)):
    h = h + (lvl - h) * m
h = h + 4 * fbm(P[10], X / 90, Z / 90, 3) * (1 - pueblo) * (1 - city) * (1 - festival) * (1 - beachtown)
# farmland: flatter
h = h + ((22 + 8 * fbm(P[12], X / 900, Z / 900, 3)) - h) * farm * 0.7
# coast: beaches and a sea floor
shore = smooth(-0.02, 0.25, L)
h = np.where(L < 0.25, np.minimum(h, 1.5 + (h - 1.5) * shore), h)
h = h * land + (-16 + 5 * fbm(P[13], X / 300, Z / 300, 3)) * (1 - land)
# the lake: a basin at a fixed level with a rim around it
LAKE_LEVEL = float(np.percentile(h[lake > 0.5], 30)) if (lake > 0.5).any() else 30.0
h = np.where(lake > 0.02, np.minimum(h, LAKE_LEVEL - 6 * lake + 1.5 * (1 - lake)), h)
print('terrain', round(time.time() - T0, 1), 's; lake level', round(LAKE_LEVEL, 1))

def sample_h(px, pz, hh=None):
    hh = h if hh is None else hh
    fx = np.clip((np.asarray(px) + SIZE / 2) / CELL, 0, N - 1.001); fz = np.clip((np.asarray(pz) + SIZE / 2) / CELL, 0, N - 1.001)
    ix, iz = fx.astype(int), fz.astype(int); tx, tz = fx - ix, fz - iz
    a = hh[iz, ix] * (1 - tx) + hh[iz, ix + 1] * tx; b = hh[iz + 1, ix] * (1 - tx) + hh[iz + 1, ix + 1] * tx
    return a * (1 - tz) + b * tz

def resample(pts, step=4.0):
    pts = np.asarray(pts, float); d = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(pts, axis=0).T))])
    s = np.arange(0, d[-1], step); s = np.append(s, d[-1])
    return np.column_stack([np.interp(s, d, pts[:, 0]), np.interp(s, d, pts[:, 1])])

def chaikin(pts, it=3):
    p = np.asarray(pts, float)
    for _ in range(it):
        q = 0.75 * p[:-1] + 0.25 * p[1:]; r = 0.25 * p[:-1] + 0.75 * p[1:]
        p = np.vstack([p[0], np.column_stack([q, r]).reshape(-1, 2), p[-1]])
    return p

# ---------------------------------------------------------------- river: from the Sierra through the lake to the sea
river_ctrl = [(-350, -1750), (-520, -1250), (-640, -760), (-780, -260), (-720, 300), (-560, 820), (-380, 1300), (-300, 1700)]
rv = resample(chaikin(river_ctrl, 4), 4.0)
# meanders: push the river sideways with a slow wave plus noise
tang = np.gradient(rv, axis=0); tang /= np.maximum(np.linalg.norm(tang, axis=1, keepdims=True), 1e-6)
perp = np.column_stack([-tang[:, 1], tang[:, 0]]); sarc = np.arange(len(rv)) * 4.0
off = 55 * np.sin(sarc / 260.0) + 35 * fbm(P[15], sarc / 400.0, np.zeros_like(sarc) + 0.37, 3)
rv = resample(rv + perp * off[:, None], 4.0)
rh = sample_h(rv[:, 0], rv[:, 1]) - 2.5
rh = np.minimum.accumulate(rh)                                     # always flows downhill
in_lake = sample_h(rv[:, 0], rv[:, 1], lake) > 0.3
rh = np.where(in_lake, LAKE_LEVEL - 1.0, rh); rh = np.minimum.accumulate(rh); rh = np.maximum(rh, -1.0)
best = np.full(h.shape, 1e9); bed = np.zeros_like(h)
for (x, z), y in zip(rv[::2], rh[::2]):
    R = 40
    i0, i1 = max(int((z - R + SIZE / 2) / CELL), 0), min(int((z + R + SIZE / 2) / CELL) + 1, N - 1)
    j0, j1 = max(int((x - R + SIZE / 2) / CELL), 0), min(int((x + R + SIZE / 2) / CELL) + 1, N - 1)
    sub = (slice(i0, i1 + 1), slice(j0, j1 + 1)); d = np.hypot(X[sub] - x, Z[sub] - z)
    b = d < best[sub]; best[sub] = np.where(b, d, best[sub]); bed[sub] = np.where(b, y, bed[sub])
river_w = 1 - smooth(9, 34, best)
h = h + (bed - 0.8 * (1 - smooth(0, 9, best)) - h) * river_w
river = dict(pts=np.round(np.column_stack([rv[:, 0], rh + 1.6, rv[:, 1]]), 2).tolist(), hw=10.0)
water_mask = (h < 0.3) | (lake > 0.5) | (best < 9)

# ---------------------------------------------------------------- places
places = [
    ('pueblo', 'San Lucero', 0, 250), ('festival', 'Festival Horizonte', 330, 560), ('ciudad', 'Ciudad Alta', 1180, 330),
    ('puerto', 'Puerto Alto', 1300, 860), ('playa', 'Playa Dorada', 250, 1380), ('peninsula', 'Punta Azul', 1420, 1420),
    ('lago', 'Lago Espejo', -480, -420), ('oasis', 'Oasis', -1450, 120), ('canon', 'Cañón Rojo', -1050, 1150),
    ('sierra', 'Pueblo Alto', -250, -1150), ('mirador', 'Mirador', -520, -1700), ('antena', 'La Antena', 180, -1620),
    ('volcan', 'Volcán Tizón', 820, -900), ('crater', 'Cráter', 1050, -1110), ('rancho1', 'Rancho Viejo', 520, -380),
    ('rancho2', 'Los Magueyes', -250, -420), ('rancho3', 'Granja Norte', 600, -760), ('costa_o', 'Faro Oeste', -560, 1380),
    ('valle', 'Valle Verde', 700, 950), ('dunas', 'Dunas Altas', -1650, -500),
]
PL = {p[0]: (p[2], p[3]) for p in places}

# ---------------------------------------------------------------- road routing (A* over a 10 m cost grid)
G = 10.0; GN = int(SIZE / G) + 1
gx_ = np.linspace(-SIZE / 2, SIZE / 2, GN)
GX, GZ = np.meshgrid(gx_, gx_)
gh_ = sample_h(GX.ravel(), GZ.ravel()).reshape(GN, GN)
gwater = sample_h(GX.ravel(), GZ.ravel(), water_mask.astype(float)).reshape(GN, GN) > 0.4
griver = sample_h(GX.ravel(), GZ.ravel(), (best < 12).astype(float)).reshape(GN, GN) > 0.4
road_pen = np.zeros((GN, GN))                                       # cheaper to follow existing roads

def astar(a, b, max_grade, water_ok=False):
    sx, sz = int(round((a[0] + SIZE / 2) / G)), int(round((a[1] + SIZE / 2) / G))
    tx, tz = int(round((b[0] + SIZE / 2) / G)), int(round((b[1] + SIZE / 2) / G))
    INF = 1e18; dist = np.full((GN, GN), INF); prev = -np.ones((GN, GN), np.int64)
    dist[sz, sx] = 0; pq = [(0.0, sz, sx)]
    nb = [(-1, 0, 1), (1, 0, 1), (0, -1, 1), (0, 1, 1), (-1, -1, 1.414), (-1, 1, 1.414), (1, -1, 1.414), (1, 1, 1.414)]
    while pq:
        f, z, x = heapq.heappop(pq)
        if z == tz and x == tx: break
        dz0 = dist[z, x]
        for dz, dx, c in nb:
            nz, nx = z + dz, x + dx
            if nz < 1 or nx < 1 or nz >= GN - 1 or nx >= GN - 1: continue
            if gwater[nz, nx] and not griver[nz, nx]: continue
            grade = abs(gh_[nz, nx] - gh_[z, x]) / (G * c)
            step = G * c * (1 + (grade / max_grade) ** 2 * 6 + (8 if griver[nz, nx] else 0)) * (0.6 if road_pen[nz, nx] else 1)
            if grade > max_grade * 2.2: step *= 6
            nd = dz0 + step
            if nd < dist[nz, nx]:
                dist[nz, nx] = nd; prev[nz, nx] = z * GN + x
                heapq.heappush(pq, (nd + math.hypot(tz - nz, tx - nx) * G, nz, nx))
    path = []; cur = tz * GN + tx
    while cur >= 0:
        z, x = divmod(int(cur), GN); path.append((gx_[x], gx_[z])); cur = prev[z, x]
        if z == sz and x == sx: path.append((gx_[x], gx_[z])); break
    path = path[::-1]
    for x, z in path:
        road_pen[int(round((z + SIZE / 2) / G)), int(round((x + SIZE / 2) / G))] = 1
    return path

KINDS = {'hwy': (7.5, 0.06, 0), 'road': (5.0, 0.09, 1), 'street': (4.0, 0.12, 2), 'avenue': (7.0, 0.05, 3), 'dirt': (4.0, 0.14, 4), 'sand': (5.0, 0.12, 5)}
ROUTES = [  # (id, kind, from, to, name)
    ('hwy_centro', 'hwy', 'ciudad', 'festival', 'Autopista Central'), ('hwy_oeste', 'hwy', 'festival', 'lago', 'Autopista del Lago'),
    ('hwy_puerto', 'hwy', 'ciudad', 'puerto', 'Vía del Puerto'), ('hwy_norte', 'hwy', 'ciudad', 'rancho3', 'Autopista Norte'),
    ('hwy_volcan', 'hwy', 'rancho3', 'volcan', 'Ruta del Volcán'), ('playa', 'road', 'festival', 'playa', 'Bajada a la Playa'),
    ('pueblo_fest', 'road', 'pueblo', 'festival', 'Calle Real'), ('costa_este', 'road', 'playa', 'valle', 'Costera Sur'),
    ('valle_puerto', 'road', 'valle', 'puerto', 'Camino del Valle'), ('peninsula', 'road', 'puerto', 'peninsula', 'Carretera de Punta Azul'),
    ('costa_oeste', 'road', 'playa', 'costa_o', 'Costera Oeste'), ('canon', 'dirt', 'costa_o', 'canon', 'Brecha del Cañón'),
    ('oasis_canon', 'dirt', 'canon', 'oasis', 'Ruta del Desierto'), ('oasis_lago', 'sand', 'oasis', 'lago', 'Camino de las Dunas'),
    ('dunas', 'sand', 'oasis', 'dunas', 'Mar de Dunas'), ('sierra', 'road', 'lago', 'sierra', 'Carretera de la Sierra'),
    ('mirador', 'road', 'sierra', 'mirador', 'Subida al Mirador'), ('antena', 'dirt', 'sierra', 'antena', 'Subida a la Antena'),
    ('crater', 'road', 'volcan', 'crater', 'Cumbre del Volcán'), ('rancho_a', 'road', 'pueblo', 'rancho2', 'Camino de los Magueyes'),
    ('rancho_b', 'dirt', 'rancho2', 'lago', 'Brecha del Lago'), ('rancho_c', 'road', 'pueblo', 'rancho1', 'Camino del Rancho'),
    ('rancho_d', 'dirt', 'rancho1', 'rancho3', 'Terracería Norte'), ('antena_volcan', 'dirt', 'antena', 'rancho3', 'Brecha de la Sierra'),
    ('lago_sur', 'road', 'lago', 'costa_o', 'Ribera del Lago'), ('sahara_norte', 'sand', 'dunas', 'mirador', 'Paso de Arena'),
    ('fest_valle', 'road', 'festival', 'valle', 'Camino al Valle'), ('ciudad_rancho', 'road', 'ciudad', 'rancho1', 'Salida Poniente'),
]
road_paths = []
for rid, kind, a, b, name in ROUTES:
    path = astar(PL[a], PL[b], KINDS[kind][1] * 1.4)
    road_paths.append((rid, kind, name, resample(chaikin(path[::2], 3), 4.0)))
print('main roads', round(time.time() - T0, 1), 's')
# farm and scenic spurs: short roads from random points to random land
rng = np.random.default_rng(7)
spurs = 0
for k in range(260):
    if spurs >= 40: break
    rid, kind, name, pts = road_paths[rng.integers(len(road_paths))]
    if kind in ('sand',): continue
    p = pts[rng.integers(len(pts))]; ang = rng.random() * 6.283; dist = 250 + rng.random() * 400
    q = (p[0] + math.cos(ang) * dist, p[1] + math.sin(ang) * dist)
    if abs(q[0]) > 1850 or abs(q[1]) > 1850: continue
    if sample_h(np.array([q[0]]), np.array([q[1]]), water_mask.astype(float))[0] > 0.2: continue
    if sample_h(np.array([q[0]]), np.array([q[1]]), city)[0] > 0.3: continue
    path = astar(tuple(p), q, 0.16)
    if len(path) < 15: continue
    road_paths.append((f'brecha{spurs}', 'dirt', '', resample(chaikin(path[::2], 3), 4.0))); spurs += 1
# the city: a warped street web inside the city blob, plus the town streets
def street_web(cx, cz, spacing, extent, angle, kind, prefix, mask, amp):
    ca, sa = math.cos(angle), math.sin(angle); n = 0
    for axis in (0, 1):
        for o in np.arange(-extent, extent + 1, spacing):
            line = []
            for s in np.arange(-extent, extent + 1, 8.0):
                u, v = (o, s) if axis == 0 else (s, o)
                wx = cx + u * ca - v * sa; wz = cz + u * sa + v * ca
                wx += amp * float(fbm(P[20], np.array([wx / 300]), np.array([wz / 300]), 2)[0])
                wz += amp * float(fbm(P[21], np.array([wx / 300]), np.array([wz / 300]), 2)[0])
                inside = sample_h(np.array([wx]), np.array([wz]), mask)[0] > 0.55 and not (sample_h(np.array([wx]), np.array([wz]), water_mask.astype(float))[0] > 0.2)
                if inside: line.append((wx, wz))
                elif len(line) > 6:
                    road_paths.append((f'{prefix}{n}', kind, '', resample(line, 4.0))); n += 1; line = []
                else: line = []
            if len(line) > 6: road_paths.append((f'{prefix}{n}', kind, '', resample(line, 4.0))); n += 1
    return n
nc = street_web(1180, 330, 130, 560, 0.35, 'avenue', 'av', city, 30)
npb = street_web(0, 250, 60, 220, -0.2, 'street', 'calle', pueblo, 10)
nbt = street_web(250, 1380, 70, 200, 0.1, 'street', 'playa_calle', beachtown, 8)
print('streets', nc, npb, nbt, round(time.time() - T0, 1), 's')

# ---------------------------------------------------------------- road profiles and carving
road_out = []
pin_pts, pin_h = np.zeros((0, 2)), np.zeros(0)
order = sorted(road_paths, key=lambda r: ['hwy', 'avenue', 'road', 'street', 'dirt', 'sand'].index(r[1]))
for rid, kind, name, pts in order:
    hw, grade, kid = KINDS[kind]
    hs = np.maximum(sample_h(pts[:, 0], pts[:, 1]), 2.0)
    pinned = np.full(len(pts), np.nan)
    if len(pin_pts):
        for i, p in enumerate(pts):
            d = np.hypot(pin_pts[:, 0] - p[0], pin_pts[:, 1] - p[1]); j = np.argmin(d)
            if d[j] < 10: pinned[i] = pin_h[j]
    for _ in range(40):
        k = 6
        pad = np.concatenate([np.full(k, hs[0]), hs, np.full(k, hs[-1])])
        hs = np.convolve(pad, np.ones(2 * k + 1) / (2 * k + 1), 'same')[k:-k]
        ok = ~np.isnan(pinned); hs[ok] = pinned[ok]
    seg = np.maximum(np.hypot(*np.diff(pts, axis=0).T), 0.1)
    for _ in range(4):
        for i in range(1, len(hs)): hs[i] = np.clip(hs[i], hs[i - 1] - grade * seg[i - 1], hs[i - 1] + grade * seg[i - 1])
        for i in range(len(hs) - 2, -1, -1): hs[i] = np.clip(hs[i], hs[i + 1] - grade * seg[i], hs[i + 1] + grade * seg[i])
        ok = ~np.isnan(pinned); hs[ok] = pinned[ok]
    pin_pts = np.concatenate([pin_pts, pts]); pin_h = np.concatenate([pin_h, hs])
    road_out.append(dict(id=rid, kind=kind, name=name, hw=hw, pts=np.round(np.column_stack([pts[:, 0], hs, pts[:, 1]]), 2).tolist()))
best_d = np.full(h.shape, 1e9); best_h = np.zeros_like(h); best_k = np.zeros(h.shape, np.uint8)
for r in road_out:
    hw = r['hw']; R = hw + 20; kid = KINDS[r['kind']][2]
    for x, y, z in r['pts'][::2]:
        i0, i1 = max(int((z - R + SIZE / 2) / CELL), 0), min(int((z + R + SIZE / 2) / CELL) + 1, N - 1)
        j0, j1 = max(int((x - R + SIZE / 2) / CELL), 0), min(int((x + R + SIZE / 2) / CELL) + 1, N - 1)
        if i0 > i1 or j0 > j1: continue
        sub = (slice(i0, i1 + 1), slice(j0, j1 + 1)); d = np.hypot(X[sub] - x, Z[sub] - z) - hw
        b = d < best_d[sub]
        best_d[sub] = np.where(b, d, best_d[sub]); best_h[sub] = np.where(b, y, best_h[sub]); best_k[sub] = np.where(b, kid, best_k[sub])
w = 1 - smooth(1.0, 18, best_d)
h = h + (best_h - 0.12 - h) * w
print('roads carved', len(road_out), round(time.time() - T0, 1), 's')

# ---------------------------------------------------------------- texture weights
gz, gx = np.gradient(h, CELL)
slope = np.degrees(np.arctan(np.hypot(gx, gz)))
n1 = 0.5 + 0.5 * fbm(P[14], X / 80, Z / 80, 3)
# farmland patchwork: rotated, slightly warped rectangular fields, each one grass, crop or bare soil
fr = np.random.default_rng(3); fv = fr.random((200, 200))
u = (X * 0.94 + Z * 0.34 + 0.25 * warp) / 140.0; v = (-X * 0.34 + Z * 0.94 + 0.25 * warp) / 95.0
field = fv[np.floor(u).astype(int) % 200, np.floor(v).astype(int) % 200]
snow = smooth(330, 400, h + 50 * (n1 - .5)) * smooth(42, 26, slope) * (volcano_r > 140)
volc = smooth(700, 350, volcano_r) * smooth(60, 140, h)
rock = np.clip(smooth(26, 40, slope) + north * smooth(260, 340, h) * 0.6 + desert * smooth(10, 22, slope) + volc * 0.7, 0, 1) * (1 - snow)
forest = np.clip(north * smooth(60, 100, h) * smooth(330, 260, h) * (0.4 + 0.6 * n1) + 0.6 * blob(-200, -800, 500, 300, 150) * n1, 0, 1)
sand_beach = np.clip(smooth(4, 1.5, h) * land + (1 - land), 0, 1)
dune = sahara
red = np.clip(desert + volc * 0.8, 0, 1)
dirt = np.clip(farm * smooth(0.55, 0.62, field) * 0.9 + festival * 0.8 + (best_k >= 4) * smooth(9, 3, best_d) + 0.15 * smooth(0.6, 0.9, n1), 0, 1)
W = np.stack([np.ones_like(h) * 0.6, dirt * 1.4, rock * 2.5, sand_beach * 2.8, dune * 2.5, red * 2.2, snow * 3.0, forest * 1.8], 0)
W[0] *= (1 - np.clip(sand_beach + dune + red + snow, 0, 1))
W[0] *= 0.75 + 0.5 * (farm * smooth(0.3, 0.32, field) * (field < 0.55))
W = W / np.maximum(W.sum(0, keepdims=True), 1e-4)
W8 = (W * 255 + 0.5).astype(np.uint8)

os.makedirs(OUT, exist_ok=True)
h.astype('<f4').tofile(os.path.join(OUT, 'height.bin'))
Image.fromarray(np.stack(list(W8[0:4]), -1), 'RGBA').save(os.path.join(OUT, 'splat0.png'), optimize=True)
Image.fromarray(np.stack(list(W8[4:8]), -1), 'RGBA').save(os.path.join(OUT, 'splat1.png'), optimize=True)
road_dist = np.clip(best_d * 4, 0, 255).astype(np.uint8)
kind_img = np.where(best_d < 64, best_k * 40 + 20, 0).astype(np.uint8)
Image.fromarray(np.stack([road_dist, kind_img, (water_mask * 255).astype(np.uint8)], -1), 'RGB').save(os.path.join(OUT, 'roads.png'), optimize=True)

# ---------------------------------------------------------------- styled map (satellite-like, like the festival map)
pal = np.array([[78, 112, 58], [128, 108, 74], [118, 114, 108], [222, 204, 160], [226, 174, 104], [168, 86, 58], [238, 242, 246], [42, 74, 44]], float)
col = np.tensordot(W.transpose(1, 2, 0), pal, axes=1)
col *= (0.92 + 0.16 * (field[..., None] - 0.5) * farm[..., None])
shade = np.clip(0.78 + 0.9 * (-gx * 0.55 - gz * 0.45), 0.45, 1.25)[..., None]
col = col * shade
deep = smooth(-16, 0, h)[..., None]
water_col = np.array([24, 62, 98]) * (1 - deep) + np.array([52, 128, 150]) * deep
col = np.where(water_mask[..., None], water_col, col)
cityish = (city > 0.5)[..., None] & ~water_mask[..., None]
col = np.where(cityish, col * 0.55 + np.array([150, 150, 150]) * 0.45, col)
col = np.where((best_d < 0)[..., None], np.array([240, 240, 236]), col)
col = np.where(((best_d < 0) & (best_k >= 4))[..., None], np.array([216, 190, 146]), col)
img = Image.fromarray(np.clip(col, 0, 255).astype(np.uint8), 'RGB').resize((1024, 1024), Image.LANCZOS)
img.save(os.path.join(OUT, 'map.png'), optimize=True)

def gh(x, z): return round(float(sample_h(np.array([x]), np.array([z]))[0]), 2)
zones = [
    dict(id='pueblo', name='San Lucero', kind='pueblo', x=0, z=250, r=260), dict(id='ciudad', name='Ciudad Alta', kind='ciudad', x=1180, z=330, r=520),
    dict(id='playa', name='Playa Dorada', kind='playa', x=250, z=1380, r=500), dict(id='sahara', name='Mar de Dunas', kind='sahara', x=-1450, z=150, r=600),
    dict(id='desierto', name='Cañón Rojo', kind='desierto', x=-1050, z=1150, r=480), dict(id='sierra', name='Sierra Alta', kind='sierra', x=-300, z=-1350, r=700),
    dict(id='volcan', name='Volcán Tizón', kind='volcan', x=1050, z=-1180, r=600), dict(id='lago', name='Lago Espejo', kind='lago', x=-780, z=-260, r=380),
    dict(id='campo', name='Llanura Verde', kind='campo', x=250, z=-350, r=800), dict(id='festival', name='Festival Horizonte', kind='festival', x=330, z=560, r=150),
]
pl = {k: dict(name=n, x=x, z=z, y=gh(x, z)) for k, n, x, z in places}
pl['spawn'] = dict(name='Festival', x=330, z=520, y=gh(330, 520), h=math.pi)
json.dump(dict(v=2, size=SIZE, n=N, spacing=CELL, sea=0.0, lake=dict(level=round(LAKE_LEVEL, 2), x=-780, z=-260, rx=300, rz=420),
               river=river, roads=road_out, zones=zones, places=pl),
          open(os.path.join(OUT, 'world.json'), 'w'), separators=(',', ':'))
print('done', N, 'x', N, 'h', round(float(h.min()), 1), '..', round(float(h.max()), 1), 'roads', len(road_out), round(time.time() - T0, 1), 's')
