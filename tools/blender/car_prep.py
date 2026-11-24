# Prepare the Sketchfab "Generic Sport Coupe Car" (CC-BY, MMC Works) for Godot:
# bake the rig pose, drop helper meshes, one Body mesh + four Wheel_* meshes with the
# origin at the wheel centre, model origin on the ground between the axles, front = +Y
# (glTF -Z = Godot forward), metres, GLB out.
import bpy, mathutils, sys
SRC, DST = sys.argv[-2], sys.argv[-1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
dg = bpy.context.evaluated_depsgraph_get()

def wbox(o):
    ws = [o.matrix_world @ mathutils.Vector(c) for c in o.bound_box]
    return mathutils.Vector([min(v[i] for v in ws) for i in range(3)]), mathutils.Vector([max(v[i] for v in ws) for i in range(3)])

# 1. bake every mesh into world space as a plain mesh (applies the armature pose)
meshes = [o for o in bpy.data.objects if o.type == 'MESH']
baked = []
for o in meshes:
    e = o.evaluated_get(dg)
    m = bpy.data.meshes.new_from_object(e, preserve_all_data_layers=True, depsgraph=dg)
    m.transform(e.matrix_world)
    n = bpy.data.objects.new(o.name, m)
    bpy.context.scene.collection.objects.link(n)
    baked.append(n)
for o in list(bpy.data.objects):
    if o not in baked:
        bpy.data.objects.remove(o, do_unlink=True)

# 2. drop helper meshes below the ground (rig widgets) and report
for o in list(bpy.data.objects):
    mn, mx = wbox(o)
    if mx.z < 0.05 or mn.z < -0.3 or o.name.startswith(('SHP', 'WGT', 'Icosphere')):
        print('drop', o.name, round(mx.z, 2))
        bpy.data.objects.remove(o, do_unlink=True)

# 3. which way is the front? headlights
hl = [o for o in bpy.data.objects if o.name.startswith('headlight')]
front_sign = 1.0 if sum((wbox(o)[0].y + wbox(o)[1].y) / 2 for o in hl) > 0 else -1.0
print('front is', '+Y' if front_sign > 0 else '-Y')
if front_sign < 0:
    for o in bpy.data.objects:
        o.data.transform(mathutils.Matrix.Rotation(3.14159265, 4, 'Z'))

# 4. wheels: tire + rim + disc per corner, joined, origin at the tire centre
tires = [o for o in bpy.data.objects if o.name.startswith('tire-low')]
centers = []
for t in tires:
    mn, mx = wbox(t); centers.append((mn + mx) / 2)
radius = sum((wbox(t)[1].z - wbox(t)[0].z) / 2 for t in tires) / len(tires)
parts = {i: [] for i in range(len(tires))}
for o in list(bpy.data.objects):
    if o.name.startswith(('tire-low', 'wheel-full', 'brake-disc')):
        mn, mx = wbox(o); c = (mn + mx) / 2
        i = min(range(len(centers)), key=lambda k: (centers[k] - c).length)
        parts[i].append(o)
wheel_info = []
for i, objs in parts.items():
    c = centers[i]
    name = 'Wheel_' + ('F' if c.y > 0 else 'R') + ('L' if c.x < 0 else 'R')
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs: o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    w = bpy.context.view_layer.objects.active
    w.name = name; w.data.name = name
    w.data.transform(mathutils.Matrix.Translation(-c))
    w.location = c
    wheel_info.append((name, tuple(round(v, 3) for v in c)))

# 5. everything else is the body
body = [o for o in bpy.data.objects if not o.name.startswith('Wheel_')]
bpy.ops.object.select_all(action='DESELECT')
for o in body: o.select_set(True)
bpy.context.view_layer.objects.active = body[0]
bpy.ops.object.join()
b = bpy.context.view_layer.objects.active
b.name = 'Body'; b.data.name = 'Body'

# 6. origin: ground under the middle of the axles
fy = [c.y for c in centers]; mid_y = (max(fy) + min(fy)) / 2
ground = min(wbox(o)[0].z for o in bpy.data.objects)
shift = mathutils.Vector((0.0, -mid_y, -ground))
for o in bpy.data.objects:
    if o.name.startswith('Wheel_'):
        o.location += shift
    else:
        o.data.transform(mathutils.Matrix.Translation(shift))
for o in bpy.data.objects:
    if o.name.startswith('Wheel_'):
        print('wheel', o.name, tuple(round(v, 3) for v in o.location))
mn = mathutils.Vector((1e9,) * 3); mx = -mn
for o in bpy.data.objects:
    a, z = wbox(o); mn = mathutils.Vector(map(min, mn, a)); mx = mathutils.Vector(map(max, mx, z))
print('size', tuple(round(v, 3) for v in (mx - mn)), 'radius', round(radius, 3), 'faces', sum(len(o.data.polygons) for o in bpy.data.objects))
bpy.ops.export_scene.gltf(filepath=DST, export_format='GLB', export_yup=True, export_apply=True,
                          export_animations=False, export_skins=False, export_morph=False)
print('exported', DST)
