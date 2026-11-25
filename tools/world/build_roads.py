"""Road network for Valle Alto (run after build_world.py: python3 tools/world/build_roads.py).

- Highways, the metropolis ring road, mountain roads, dirt tracks and farm spurs are routed with A*
  over a 16 m cost grid (slope, water, river crossings), so they wind through the land like real roads.
- City streets are grown per district: each district (colonia) gets its own street angle, block size
  and a slight wobble, clipped to its own area, so cities look grown, not drawn on a grid.
- The terrain is flattened under every road with soft embankments.
- The network is saved as a graph (junction nodes + edges) for the GPS (AStar3D in Godot).
- Races, challenges, missions and collectibles are spread over the whole state.

Reads assets/world/cache.npz + world.json. Writes assets/world/roads.json, events.json and
height_roads.bin (float32, carved terrain).
"""
import heapq, json, math, os, time
import numpy as np

ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
W = os.path.join(ROOT, 'assets', 'world')
T0 = time.time()
def log(*a): print(f'[{time.time() - T0:5.1f}s]', *a, flush=True)

D = json.load(open(os.path.join(W, 'world.json')))
C = np.load(os.path.join(W, 'cache.npz'))
SIZE, N = D['size'], D['n']; CELL = SIZE / (N - 1)
h = C['h'].astype(np.float32); water = C['water']; dist_r = C['dist_r']
xs = np.linspace(-SIZE / 2, SIZE / 2, N).astype(np.float32)
X, Z = np.meshgrid(xs, xs)
rng = np.random.default_rng(42)

def sample(px, pz, grid):
    fx = np.clip((np.asarray(px, float) + SIZE / 2) / CELL, 0, N - 1.001); fz = np.clip((np.asarray(pz, float) + SIZE / 2) / CELL, 0, N - 1.001)
    ix, iz = fx.astype(int), fz.astype(int); tx, tz = fx - ix, fz - iz
    g = grid.astype(np.float32) if grid.dtype != np.float32 else grid
    a = g[iz, ix] * (1 - tx) + g[iz, ix + 1] * tx; b = g[iz + 1, ix] * (1 - tx) + g[iz + 1, ix + 1] * tx
    return a * (1 - tz) + b * tz

def chaikin(pts, it=3):
    p = np.asarray(pts, float)
    for _ in range(it):
        q = 0.75 * p[:-1] + 0.25 * p[1:]; r = 0.25 * p[:-1] + 0.75 * p[1:]
        p = np.vstack([p[0], np.column_stack([q, r]).reshape(-1, 2), p[-1]])
    return p

def resample(pts, step=4.0):
    pts = np.asarray(pts, float)
    if len(pts) < 2: return pts
    d = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(pts, axis=0).T))])
    if d[-1] < step: return pts[[0, -1]]
    s = np.append(np.arange(0, d[-1], step), d[-1])
    return np.column_stack([np.interp(s, d, pts[:, 0]), np.interp(s, d, pts[:, 1])])

# ---------------------------------------------------------------- A* cost grid
G = 16.0; GN = int(SIZE / G) + 1
gx = np.linspace(-SIZE / 2, SIZE / 2, GN)
GX, GZ = np.meshgrid(gx, gx)
gh = sample(GX.ravel(), GZ.ravel(), h).reshape(GN, GN)
river_g = sample(GX.ravel(), GZ.ravel(), (dist_r < 6).astype(np.float32)).reshape(GN, GN) > 0.3
wet = sample(GX.ravel(), GZ.ravel(), water.astype(np.float32)).reshape(GN, GN) > 0.35
blocked = wet & ~river_g                                            # sea and lake: never; rivers: bridges
used = np.zeros((GN, GN), bool)
NB = [(-1, 0, 1.0), (1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0), (-1, -1, 1.414), (-1, 1, 1.414), (1, -1, 1.414), (1, 1, 1.414),
      (-2, -1, 2.236), (-2, 1, 2.236), (2, -1, 2.236), (2, 1, 2.236), (-1, -2, 2.236), (1, -2, 2.236), (-1, 2, 2.236), (1, 2, 2.236)]

def gcell(p): return int(round((p[1] + SIZE / 2) / G)), int(round((p[0] + SIZE / 2) / G))

def astar(a, b, max_grade, reuse=0.6, margin=1600.0):
    sz, sx = gcell(a); tz, tx = gcell(b)
    z0 = max(min(sz, tz) - int(margin / G), 1); z1 = min(max(sz, tz) + int(margin / G), GN - 2)
    x0 = max(min(sx, tx) - int(margin / G), 1); x1 = min(max(sx, tx) + int(margin / G), GN - 2)
    W_, H_ = x1 - x0 + 1, z1 - z0 + 1
    dist = np.full(H_ * W_, np.inf); prev = np.full(H_ * W_, -1, np.int64)
    s = (sz - z0) * W_ + (sx - x0); t = (tz - z0) * W_ + (tx - x0)
    dist[s] = 0; pq = [(0.0, s)]
    while pq:
        f, cur = heapq.heappop(pq)
        if cur == t: break
        cz, cx = divmod(cur, W_); d0 = dist[cur]; zg, xg = cz + z0, cx + x0
        if f - math.hypot(tz - zg, tx - xg) * G > d0 + 1e-6: continue
        for dz, dx, c in NB:
            nz, nx = zg + dz, xg + dx
            if nz < z0 or nz > z1 or nx < x0 or nx > x1 or blocked[nz, nx]: continue
            if c > 2 and (blocked[zg + (dz // 2 if abs(dz) == 2 else dz), xg + (dx // 2 if abs(dx) == 2 else dx)]): continue
            run = G * c; grade = abs(gh[nz, nx] - gh[zg, xg]) / run
            step = run * (1 + 7 * (grade / max_grade) ** 2)
            if grade > max_grade * 1.6: step *= 12
            if river_g[nz, nx]: step += 260
            if used[nz, nx]: step *= reuse
            nd = d0 + step; ni = (nz - z0) * W_ + (nx - x0)
            if nd < dist[ni]:
                dist[ni] = nd; prev[ni] = cur
                heapq.heappush(pq, (nd + math.hypot(tz - nz, tx - nx) * G, ni))
    path = []; cur = t
    while cur >= 0:
        cz, cx = divmod(cur, W_); path.append((gx[cx + x0], gx[cz + z0])); cur = prev[cur]
    path = path[::-1]
    if len(path) < 2 or path[0] != (gx[sx], gx[sz]): return None
    for x, z in path: used[gcell((x, z))] = True
    return [a] + path[1:-1] + [b]

KIND = {  # half width, max grade, smoothing (point stride, chaikin passes)
    'hwy': (8.0, 0.05, 5, 5), 'ring': (7.5, 0.05, 4, 5), 'avenue': (6.5, 0.07, 3, 4), 'road': (5.0, 0.09, 3, 4),
    'street': (4.0, 0.13, 1, 2), 'calle': (5.0, 0.11, 1, 2), 'dirt': (3.8, 0.15, 3, 4)}
roads = []
def add_route(rid, kind, way, name=''):
    """Routes through the waypoints; a leg that cannot be routed splits the road instead of jumping."""
    way = [land_pt(p) for p in way]
    pieces, pts = [], []
    for a, b in zip(way[:-1], way[1:]):
        p = astar(a, b, KIND[kind][1] * 1.5)
        if p is None:
            log('  no route', rid, a, b)
            if len(pts) > 2: pieces.append(pts)
            pts = []; continue
        pts += p if not pts else p[1:]
    if len(pts) > 2: pieces.append(pts)
    made = None
    for k, pts in enumerate(pieces):
        stride, passes = KIND[kind][2], KIND[kind][3]
        sm = chaikin(np.array(pts[::stride] + ([pts[-1]] if (len(pts) - 1) % stride else [])), passes)
        if len(sm) > 12:                                         # a moving average removes the grid zigzag
            k_ = 9; pad = np.vstack([np.repeat(sm[:1], k_, 0), sm, np.repeat(sm[-1:], k_, 0)])
            ker = np.ones(2 * k_ + 1) / (2 * k_ + 1)
            sm = np.column_stack([np.convolve(pad[:, 0], ker, 'same'), np.convolve(pad[:, 1], ker, 'same')])[k_:-k_]
            sm[0], sm[-1] = pts[0], pts[-1]
        rs = resample(sm, 4.0)
        if len(rs) > 30 and kind not in ('street', 'calle'):     # second pass at 4 m: irons out the small grid zigzags
            k_ = 12 if kind in ('road', 'dirt') else 18
            pad = np.vstack([np.repeat(rs[:1], k_, 0), rs, np.repeat(rs[-1:], k_, 0)]); ker = np.ones(2 * k_ + 1) / (2 * k_ + 1)
            sm2 = np.column_stack([np.convolve(pad[:, 0], ker, 'same'), np.convolve(pad[:, 1], ker, 'same')])[k_:-k_]
            sm2[0], sm2[-1] = rs[0], rs[-1]; rs = resample(sm2, 4.0)
        r = dict(id=rid if k == 0 else f'{rid}_{k}', kind=kind, name=name, pts2=rs); roads.append(r); made = made or r
    return made

PL = {p['id']: (p['x'], p['z']) for p in D['places']}
CITIES = D['cities']
WATERF = water.astype(np.float32)
def land_pt(p, reach=1200):
    """The closest point on dry land (waypoints that fall in the sea or the lake are moved ashore)."""
    if sample(p[0], p[1], WATERF) < 0.05 and abs(p[0]) < 3950 and abs(p[1]) < 3950: return p
    for r in range(40, reach, 40):
        for a in np.linspace(0, 2 * np.pi, 24, endpoint=False):
            q = (p[0] + r * math.cos(a), p[1] + r * math.sin(a))
            if sample(q[0], q[1], WATERF) < 0.05 and abs(q[0]) < 3950 and abs(q[1]) < 3950: return q
    return p
# the real centre of the metropolis: the middle of its built-up land (the bay eats the east side)
_mm = C['metro'].astype(np.float32) * (~water)
CITIES['ciudad']['x'] = float((_mm * X).sum() / _mm.sum()); CITIES['ciudad']['z'] = float((_mm * Z).sum() / _mm.sum())
def cxz(k): return land_pt((CITIES[k]['x'], CITIES[k]['z']))
def off(p, dx, dz): return (p[0] + dx, p[1] + dz)

# ---------------------------------------------------------------- main network
log('routing highways')
FEST = PL['festival']
add_route('autopista_valle', 'hwy', [off(cxz('san_lucero'), 250, -120), FEST, off(cxz('ciudad'), -700, -200)], 'Autopista del Valle')
add_route('autopista_costa', 'hwy', [off(cxz('puerto_chico'), 160, -60), off(cxz('san_lucero'), -300, 120)], 'Autopista de la Costa')
add_route('autopista_norte', 'hwy', [off(cxz('ciudad'), -250, -750), off(cxz('los_magueyes'), 220, 120), (900, -2400)], 'Autopista del Norte')
# the ring road of Ciudad Alta: points around the centre, skipping the bay
mx, mz = cxz('ciudad'); ring = []
for a in np.linspace(0, 2 * np.pi, 16, endpoint=False):
    p = (mx + 1350 * math.cos(a), mz + 1100 * math.sin(a))
    if sample(p[0], p[1], water.astype(np.float32)) < 0.2 and abs(p[0]) < 3900 and abs(p[1]) < 3900: ring.append((a, p))
ring.sort(); rp = [p for _, p in ring]
gaps = [i for i in range(len(ring)) if (ring[(i + 1) % len(ring)][0] - ring[i][0]) % (2 * np.pi) > 0.6]
start = (gaps[0] + 1) % len(rp) if gaps else 0
rp = rp[start:] + rp[:start]
add_route('periferico', 'ring', rp, 'Periférico')
log('routing roads')
ROADS = [
    ('carretera_lago', 'road', [FEST, off(PL['tlacotal'], 140, 60)], 'Carretera del Lago'),
    ('ribera_norte', 'road', [off(PL['tlacotal'], 60, -160), (-1900, -1500), (-2650, -1300), (-2750, -400)], 'Ribera Norte'),
    ('ribera_sur', 'road', [(-2750, -400), (-2500, 650), (-1650, 600), off(PL['tlacotal'], 80, 120)], 'Ribera Sur'),
    ('sierra', 'road', [off(PL['tlacotal'], 0, -200), PL['montana'], (-1500, -3150)], 'Carretera de la Sierra'),
    ('mirador', 'road', [PL['montana'], (-2650, -3500)], 'Subida al Mirador'),
    ('meseta', 'road', [PL['montana'], (-600, -2500), (400, -2900), (900, -2400)], 'Cruce de la Meseta'),
    ('barranca_borde', 'road', [off(PL['los_magueyes'], 200, -200), (2000, -2900), (2700, -3500)], 'Camino de la Barranca'),
    ('volcan', 'road', [off(cxz('san_lucero'), 450, 150), (-200, 2300), (200, 1950)], 'Subida al Volcán'),
    ('costera_sur', 'road', [off(cxz('puerto_chico'), 200, 220), (-1400, 2650), (-300, 2700), (900, 2950), (2000, 2250), off(cxz('ciudad'), 100, 760)], 'Costera del Sur'),
    ('punta_azul', 'road', [(2000, 2250), (2750, 3000), (2950, 3350)], 'Carretera de Punta Azul'),
    ('valle_norte', 'road', [FEST, (300, -900), off(PL['los_magueyes'], -150, 80)], 'Camino del Llano'),
    ('san_lucero_lago', 'road', [off(cxz('san_lucero'), 0, -350), (-1700, 100), off(PL['tlacotal'], 40, 200)], 'Camino Viejo'),
]
for rid, kind, way, name in ROADS: add_route(rid, kind, way, name)
log('routing dirt tracks')
DIRT = [
    ('antena', [(400, -2900), (450, -3500)], 'Subida a la Antena'), ('crater', [(200, 1950), (560, 1520)], 'Brecha del Cráter'),
    ('rally_bosque', [(-1500, -3150), (-900, -3700), (-300, -3300)], 'Brecha del Bosque'),
    ('playa_oeste', [off(cxz('puerto_chico'), -60, 300), (-2900, 1300), (-2950, 600)], 'Brecha de la Playa'),
    ('rio', [(300, -900), (1100, -400), (1500, 300)], 'Brecha del Río'), ('ceniza', [(-200, 2300), (900, 2500), (1500, 1900)], 'Ruta de la Ceniza'),
]
for rid, way, name in DIRT: add_route(rid, 'dirt', way, name)
# hamlets (rancherías) scattered over the state, then each place is linked to its nearest neighbours
GSLOPE = np.degrees(np.arctan(np.hypot(*np.gradient(gh, G))))
urban = (C['metro'].astype(np.float32) + C['colonial'].astype(np.float32) + C['mini'].astype(np.float32))
towns = [cxz(k) for k in CITIES] + [FEST]
hamlets = []
for _ in range(6000):
    if len(hamlets) >= 16: break
    q = (rng.uniform(-3700, 3700), rng.uniform(-3700, 3700))
    zi, xi = gcell(q)
    if blocked[zi, xi] or wet[zi, xi] or GSLOPE[zi, xi] > 14 or sample(q[0], q[1], urban) > 0.1: continue
    if sample(q[0], q[1], h) > 950: continue
    if min(math.hypot(q[0] - t[0], q[1] - t[1]) for t in towns + hamlets) < 1100: continue
    hamlets.append(q)
log('hamlets', len(hamlets))
nodes_ = towns + hamlets + [(-2650, -3500), (450, -3500), (560, 1520), (2700, -3500), (2950, 3350)]
links = set()
for i, a in enumerate(nodes_):
    d = sorted(((math.hypot(a[0] - b[0], a[1] - b[1]), j) for j, b in enumerate(nodes_) if j != i))
    for dist_, j in d[:2]:
        if dist_ < 2600: links.add((min(i, j), max(i, j)))
nt = len(towns)
for li, (i, j) in enumerate(sorted(links)):
    kind = 'road' if (i < nt or j < nt or rng.random() < 0.6) and j < len(towns) + len(hamlets) else 'dirt'
    add_route(f'link{li}', kind, [nodes_[i], nodes_[j]])
log('links', len(links))
# farm, forest and scenic spurs from existing roads: mostly dirt (orange on the map), some paved
spurs = 0; tries = 0
used_before = used.copy()
while spurs < 45 and tries < 900:
    tries += 1
    r = roads[rng.integers(len(roads))]
    if r['kind'] in ('hwy', 'ring'): continue
    p = r['pts2'][rng.integers(len(r['pts2']))]; ang = rng.random() * 6.283; dd = 400 + rng.random() * 700
    q = (p[0] + math.cos(ang) * dd, p[1] + math.sin(ang) * dd)
    if abs(q[0]) > 3850 or abs(q[1]) > 3850 or sample(q[0], q[1], WATERF) > 0.1: continue
    if sample(q[0], q[1], C['metro'].astype(np.float32)) > 0.3: continue
    r_new = add_route(f'brecha{spurs}', 'dirt', [tuple(p), q])
    if r_new is None: continue
    # drop spurs that mostly run alongside an existing road
    near = 0; P2 = r_new['pts2'][::4]
    for x, z in P2:
        zi, xi = gcell((x, z))
        if used_before[max(zi - 2, 0):zi + 3, max(xi - 2, 0):xi + 3].any(): near += 1
    if near > 0.3 * len(P2):
        roads.remove(r_new); continue
    used_before[:] = used
    spurs += 1
log('main network', len(roads), 'roads')

# ---------------------------------------------------------------- organic city streets (districts)
def districts(cid, mask, center, radius, n_districts, spacing, kind, center_kind, wobble):
    cxp, czp = center
    seeds = [center]
    for _ in range(4000):
        if len(seeds) >= n_districts: break
        a = rng.random() * 6.283; rr = radius * math.sqrt(rng.random())
        p = (cxp + rr * math.cos(a), czp + rr * math.sin(a))
        if sample(p[0], p[1], mask) < 0.5 or sample(p[0], p[1], water.astype(np.float32)) > 0.1: continue
        if min(math.hypot(p[0] - s[0], p[1] - s[1]) for s in seeds) < radius / math.sqrt(n_districts) * 0.9: continue
        seeds.append(p)
    S = np.array(seeds)
    made = 0
    for k, (sx, sz) in enumerate(seeds):
        ang = rng.random() * math.pi
        if k == 0: sp = (spacing[0] * 0.65, spacing[0] * 0.55)
        else: sp = (rng.uniform(*spacing), rng.uniform(spacing[0] * 0.7, spacing[1] * 0.8))
        ca, sa = math.cos(ang), math.sin(ang); ext = radius * 0.9
        ph = rng.random(2) * 1000
        for axis, step in ((0, sp[0]), (1, sp[1])):
            for o in np.arange(-ext, ext + 1, step):
                line = []
                for t in np.arange(-ext, ext + 1, 6.0):
                    u, v = (o, t) if axis == 0 else (t, o)
                    wob = wobble * math.sin((t + ph[axis]) / 70.0) + wobble * 0.5 * math.sin((o + t) / 37.0 + ph[1 - axis])
                    u += wob if axis == 0 else 0; v += wob if axis == 1 else 0
                    x = sx + u * ca - v * sa; z = sz + u * sa + v * ca
                    d2 = (S[:, 0] - x) ** 2 + (S[:, 1] - z) ** 2
                    rag = 0.35 + 0.55 * float(sample(x, z, N1))
                    inside = int(np.argmin(d2)) == k and sample(x, z, mask) > rag and sample(x, z, WATERF) < 0.1 and abs(x) < 3950 and abs(z) < 3950
                    if inside: line.append((x, z))
                    else:
                        if len(line) > 6:
                            roads.append(dict(id=f'{cid}_{made}', kind=center_kind if k == 0 else kind, name='', pts2=resample(np.array(line), 4.0))); made += 1
                        line = []
                if len(line) > 6:
                    roads.append(dict(id=f'{cid}_{made}', kind=center_kind if k == 0 else kind, name='', pts2=resample(np.array(line), 4.0))); made += 1
    return made, len(seeds)

N1 = C['n1'].astype(np.float32)
log('city streets')
metro_m = C['metro'].astype(np.float32); col_m = C['colonial'].astype(np.float32); mini_m = C['mini'].astype(np.float32)
print('  ciudad', districts('ciudad', metro_m, cxz('ciudad'), 1600, 34, (80, 130), 'calle', 'street', 9))
print('  san_lucero', districts('san_lucero', col_m, cxz('san_lucero'), 800, 13, (55, 90), 'street', 'street', 7))
for m in ('tlacotal', 'puerto_chico', 'los_magueyes'):
    print('  ', m, districts(m, mini_m, cxz(m), CITIES[m]['r'] * 1.15, 6, (50, 85), 'street', 'street', 6))
# radial avenues of Ciudad Alta: from the centre out to the ring road
for i, p in enumerate(rp[::2]):
    add_route(f'avenida{i}', 'avenue', [off(cxz('ciudad'), 40, 30), p], ['Av. Juárez', 'Av. del Puerto', 'Av. de la Sierra', 'Av. Reforma', 'Av. Volcán', 'Av. Hidalgo', 'Av. Morelos', 'Av. Libertad'][i % 8])
log('streets done, total roads', len(roads))

# ---------------------------------------------------------------- profiles (heights) with crossings pinned, then carving
PIN = {}
def pin_key(x, z): return (int(x // 8), int(z // 8))
def pin_get(x, z):
    best, bd = None, 9.0
    kx, kz = pin_key(x, z)
    for i in (-1, 0, 1):
        for j in (-1, 0, 1):
            for (px, pz, py) in PIN.get((kx + i, kz + j), ()):
                d = math.hypot(px - x, pz - z)
                if d < bd: bd, best = d, py
    return best
order = ['hwy', 'ring', 'avenue', 'road', 'calle', 'street', 'dirt']
roads.sort(key=lambda r: order.index(r['kind']))
for r in roads:
    pts = r['pts2']; hw, grade = KIND[r['kind']][0], KIND[r['kind']][1]
    hs = np.maximum(sample(pts[:, 0], pts[:, 1], h), 1.5)
    pinned = np.array([pin_get(x, z) if True else None for x, z in pts], dtype=object)
    pmask = np.array([v is not None for v in pinned]); pv = np.array([v if v is not None else 0 for v in pinned], float)
    k = 5
    for _ in range(30):
        pad = np.concatenate([np.full(k, hs[0]), hs, np.full(k, hs[-1])])
        hs = np.convolve(pad, np.ones(2 * k + 1) / (2 * k + 1), 'same')[k:-k]
        hs[pmask] = pv[pmask]
    seg = np.maximum(np.hypot(*np.diff(pts, axis=0).T), 0.1)
    for _ in range(3):
        for i in range(1, len(hs)): hs[i] = np.clip(hs[i], hs[i - 1] - grade * seg[i - 1], hs[i - 1] + grade * seg[i - 1])
        for i in range(len(hs) - 2, -1, -1): hs[i] = np.clip(hs[i], hs[i + 1] - grade * seg[i], hs[i + 1] + grade * seg[i])
        hs[pmask] = pv[pmask]
    over_river = sample(pts[:, 0], pts[:, 1], (dist_r < 4).astype(np.float32)) > 0.3   # bridges: keep the deck above the water
    hs = np.where(over_river, np.maximum(hs, sample(pts[:, 0], pts[:, 1], h) + 4.0), hs)
    for (x, z), y in zip(pts, hs):
        PIN.setdefault(pin_key(x, z), []).append((x, z, float(y)))
    r['pts'] = np.round(np.column_stack([pts[:, 0], hs, pts[:, 1]]), 2)
    r['hw'] = hw; r['bridge'] = over_river
log('profiles')
best_d = np.full(h.shape, 1e9, np.float32); best_h = np.zeros_like(h)
for r in roads:
    hw = r['hw']; R = hw + 18
    for (x, y, z), br in zip(r['pts'][::2], r['bridge'][::2]):
        if br: continue
        i0, i1 = max(int((z - R + SIZE / 2) / CELL), 0), min(int((z + R + SIZE / 2) / CELL) + 1, N - 1)
        j0, j1 = max(int((x - R + SIZE / 2) / CELL), 0), min(int((x + R + SIZE / 2) / CELL) + 1, N - 1)
        if i0 > i1 or j0 > j1: continue
        sub = (slice(i0, i1 + 1), slice(j0, j1 + 1)); d = np.hypot(X[sub] - x, Z[sub] - z) - hw
        b = d < best_d[sub]; best_d[sub] = np.where(b, d, best_d[sub]); best_h[sub] = np.where(b, y, best_h[sub])
w = 1 - np.clip((best_d - 1.0) / 16.0, 0, 1) ** 2 * (3 - 2 * np.clip((best_d - 1.0) / 16.0, 0, 1))
w = np.where(best_d > 17, 0, w)
h2 = h + (best_h - 0.15 - h) * w * (~water)
h2.astype('<f4').tofile(os.path.join(W, 'height_roads.bin'))
log('carved')

# ---------------------------------------------------------------- graph: junctions and edges
HJ = {}
for ri, r in enumerate(roads):
    for pi, (x, y, z) in enumerate(r['pts']):
        HJ.setdefault((int(x // 6), int(z // 6)), []).append((ri, pi, x, z))
junction = [set() for _ in roads]
for ri, r in enumerate(roads):
    for pi, (x, y, z) in enumerate(r['pts']):
        kx, kz = int(x // 6), int(z // 6)
        for i in (-1, 0, 1):
            for j in (-1, 0, 1):
                for (rj, pj, qx, qz) in HJ.get((kx + i, kz + j), ()):
                    if rj != ri and math.hypot(qx - x, qz - z) < 7.0:
                        junction[ri].add(pi); break
nodes = []; NH = {}
def node_at(x, y, z):
    kx, kz = int(x // 12), int(z // 12)
    for i in (-1, 0, 1):
        for j in (-1, 0, 1):
            for ni in NH.get((kx + i, kz + j), ()):
                if math.hypot(nodes[ni][0] - x, nodes[ni][2] - z) < 12: return ni
    nodes.append((round(float(x), 1), round(float(y), 1), round(float(z), 1))); NH.setdefault((kx, kz), []).append(len(nodes) - 1); return len(nodes) - 1
edges = []
for ri, r in enumerate(roads):
    P = r['pts']; js = sorted(junction[ri] | {0, len(P) - 1})
    # collapse runs of junction points into one
    keep = [js[0]] + [b for a, b in zip(js[:-1], js[1:]) if b - a > 3]
    if keep[-1] != len(P) - 1: keep.append(len(P) - 1)
    for a, b in zip(keep[:-1], keep[1:]):
        na, nb = node_at(*P[a]), node_at(*P[b])
        if na == nb: continue
        L = float(np.sum(np.hypot(*np.diff(P[a:b + 1, [0, 2]], axis=0).T)))
        edges.append([na, nb, ri, int(a), int(b), round(L, 1)])
log('graph', len(nodes), 'nodes', len(edges), 'edges')

# ---------------------------------------------------------------- events spread over the state
def road_by(rid): return next((r for r in roads if r['id'] == rid), None)
def at(rid, t):
    if road_by(rid) is None: return None
    P = road_by(rid)['pts']; i = int(np.clip(t, 0, 1) * (len(P) - 1)); return [round(float(P[i][0]), 1), round(float(P[i][1]), 1), round(float(P[i][2]), 1)]
def curvy_spot(rid):
    if road_by(rid) is None: return 0.5
    P = road_by(rid)['pts'][:, [0, 2]]
    if len(P) < 60: return 0.5
    ang = np.unwrap(np.arctan2(*np.diff(P, axis=0).T[::-1]))
    curv = np.abs(np.convolve(np.diff(ang), np.ones(25), 'same'))
    return float(np.argmax(curv) / len(P))
def straight_spot(rid):
    if road_by(rid) is None: return 0.5
    P = road_by(rid)['pts'][:, [0, 2]]
    ang = np.unwrap(np.arctan2(*np.diff(P, axis=0).T[::-1]))
    curv = np.abs(np.convolve(np.diff(ang), np.ones(40), 'same'))
    return float(np.argmin(curv[20:-20]) + 20) / len(P) if len(curv) > 60 else 0.5
EV = []
def ev(eid, kind, name, pos, **kw):
    if pos is None: log('  skipped event', eid); return
    EV.append(dict(id=eid, type=kind, name=name, pos=pos, **kw))
ev('festival', 'festival', 'Festival Horizonte', [FEST[0], round(float(sample(*FEST, h)), 1), FEST[1]])
ev('primer_dia', 'historia', 'El Primer Día', at('autopista_valle', 0.47), idea=51)
ev('entrega_urgente', 'historia', 'Entrega Urgente', at('autopista_valle', 0.1), idea=52, goal='Lleva el paquete de San Lucero a Ciudad Alta sin dañarlo')
ev('taxi', 'historia', 'Taxi de Ciudad Alta', at('avenida0', 0.3), idea=53)
ev('llega_tiempo', 'historia', 'Llega a Tiempo', at('carretera_lago', 0.9), idea=58, goal='Llega de Tlacotal a la boda en Puerto Chico antes de que empiece')
ev('mecanico', 'historia', 'El Mecánico', at('valle_norte', 0.85), idea=54)
ev('sprint_sierra', 'asfalto', 'Sprint de la Sierra', at('mirador', 0.0), idea=2, route='mirador')
ev('bajada_mirador', 'asfalto', 'Bajada del Mirador', at('mirador', 1.0), idea=3, route='mirador', reverse=True)
ev('autopista_fondo', 'asfalto', 'Autopista a Fondo', at('autopista_norte', 0.2), idea=4, route='autopista_norte')
ev('circuito_lucero', 'asfalto', 'Circuito de San Lucero', at('san_lucero_lago', 0.05), idea=1)
ev('periferico', 'asfalto', 'Vuelta al Periférico', at('periferico', 0.1), idea=8, route='periferico')
ev('costera', 'asfalto', 'Sprint de la Costa', at('costera_sur', 0.05), idea=47, route='costera_sur')
ev('rally_bosque', 'tierra', 'Rally del Bosque', at('rally_bosque', 0.0), idea=13, route='rally_bosque')
ev('brecha_rio', 'tierra', 'Brecha del Río', at('rio', 0.0), idea=14, route='rio')
ev('subida_antena', 'tierra', 'Subida a la Antena', at('antena', 0.0), idea=18, route='antena')
ev('ruta_ceniza', 'tierra', 'Escape del Volcán', at('ceniza', 0.0), idea=41, route='ceniza')
ev('playa', 'tierra', 'Carrera de la Playa', at('playa_oeste', 0.0), idea=78, route='playa_oeste')
ev('magueyes', 'tierra', 'Ruta de los Magueyes', at('brecha0', 0.0), idea=75)
ev('barranca', 'tierra', 'La Barranca', at('barranca_borde', 0.2), idea=76, route='barranca_borde')
ev('cumbre', 'desafio', 'Escalera al Cielo', at('volcan', 0.0), idea=31, route='volcan')
for i, rid in enumerate(['autopista_valle', 'autopista_norte', 'costera_sur']):
    ev(f'radar{i}', 'desafio', 'Radar de Velocidad', at(rid, straight_spot(rid)), idea=23)
for i, rid in enumerate(['sierra', 'volcan', 'meseta']):
    ev(f'derrape{i}', 'desafio', 'Zona de Derrape', at(rid, curvy_spot(rid)), idea=26)
for i, rid in enumerate(['autopista_costa', 'ribera_norte']):
    ev(f'zona_vel{i}', 'desafio', 'Zona de Velocidad', at(rid, 0.5), idea=24)
for i, rid in enumerate(['crater', 'playa_oeste']):
    ev(f'salto{i}', 'desafio', 'Salto Largo', at(rid, 0.6), idea=25)
ev('cometa', 'especial', 'El Cometa', at('punta_azul', 1.0), idea=38)
ev('leyenda', 'especial', 'Carrera de Leyenda', at('ribera_sur', 0.5), idea=40)
hi = [('mirador_sierra', (-2650, -3500)), ('mirador_volcan', (560, 1520)), ('mirador_antena', (450, -3500)), ('mirador_punta', (2950, 3350))]
for eid, p in hi: ev(eid, 'exploracion', 'Mirador', [p[0], round(float(sample(*p, h)), 1), p[1]], idea=45)
dirt = [r for r in roads if r['kind'] == 'dirt']
for i in range(12):
    r = dirt[rng.integers(len(dirt))]; P = r['pts'][rng.integers(len(r['pts']))]
    ev(f'letrero{i}', 'exploracion', 'Letrero de Bonus', [round(float(P[0]), 1), round(float(P[1]), 1), round(float(P[2]), 1)], idea=44)
for i in range(3):
    r = dirt[rng.integers(len(dirt))]; P = r['pts'][-1]
    ev(f'granero{i}', 'exploracion', 'Granero Olvidado', [round(float(P[0]), 1), round(float(P[1]), 1), round(float(P[2]), 1)], idea=43)
log('events', len(EV))

out_roads = [dict(id=r['id'], kind=r['kind'], name=r['name'], hw=r['hw'], pts=r['pts'].tolist(),
                  bridge=[int(i) for i in np.nonzero(r['bridge'])[0]]) for r in roads]
json.dump(dict(roads=out_roads, graph=dict(nodes=nodes, edges=edges)), open(os.path.join(W, 'roads.json'), 'w'), separators=(',', ':'))
json.dump(dict(events=EV), open(os.path.join(W, 'events.json'), 'w'), ensure_ascii=False, indent=1)
log('done', len(roads), 'roads,', sum(len(r['pts']) for r in out_roads), 'points')
