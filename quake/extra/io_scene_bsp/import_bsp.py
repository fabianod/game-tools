import bpy
import bmesh
import math
import numpy
from mathutils import Matrix, Vector

from .quake.bsp import Bsp, is_bspfile
from .quake import map as Map


def load(operator, context, filepath='',
         global_scale=1.0,
         use_worldspawn_entity=True,
         use_brush_entities=True,
         use_point_entities=True):

    if not is_bspfile(filepath):
        operator.report(
            {'ERROR'},
            '{} not a recognized BSP file'.format(filepath)
        )
        return {'CANCELLED'}

    bsp = Bsp.open(filepath)
    bsp.close()

    point_entities = Map.loads(bsp.entities)

    # Create materials
    images = bsp.images()
    for i, image in enumerate(images):
        if image is None:
            img = bpy.data.images.new('IMG', 0, 0)
            name = 'missing %d' % i
        else:
            name = bsp.miptextures[i].name

            image_index = bpy.data.images.find(name)

            if image_index < 0:
                img = bpy.data.images.new(name, image.width, image.height)
                pixels = list(map(lambda x: x / 255, image.pixels))
                img.pixels[:] = pixels
                img.update()
            else:
                img = bpy.data.images[image_index]

        texture_index = bpy.data.textures.find(name)

        if texture_index < 0:
            tex = bpy.data.textures.new(name, 'IMAGE')
            tex.image = img
        else:
            tex = bpy.data.textures[texture_index]

        material_index = bpy.data.materials.find(name)

        if material_index < 0:
            mat = bpy.data.materials.new(name)
            mat.diffuse_color = 1, 1, 1
            mat.specular_intensity = 0
            mat.use_shadeless = True

            tex_slot = mat.texture_slots.add()
            tex_slot.texture = tex
            tex_slot.texture_coords = 'UV'

    global_matrix  = Matrix.Scale(global_scale, 4)

    # Create point entities
    if use_point_entities:
        for entity in [_ for _ in point_entities if hasattr(_, 'origin')]:
            vec = tuple(map(int, entity.origin.split(' ')))
            ob = bpy.data.objects.new(entity.classname + '.000', None)
            ob.location = Vector(vec) * global_scale
            ob.empty_draw_size = 16 * global_scale
            ob.empty_draw_type = 'CUBE'
            bpy.context.scene.objects.link(ob)

    # Create meshes
    if True:
        for model in bsp.models:
            faces = bsp.faces[model.first_face:model.first_face + model.number_of_faces]

            me = bpy.data.meshes.new('model.000')
            bm = bmesh.new()
            uv_layer = bm.loops.layers.uv.new()

            vertex_cache = {}

            def create_vertex(index):
                if index not in vertex_cache:
                    bvert = bm.verts.new(bsp.vertexes[index][:])
                    vertex_cache[index] = bvert

                return vertex_cache[index]

            def create_vertex(triple):
                if triple not in vertex_cache:
                    bvert = bm.verts.new(triple)
                    bvert.co = global_matrix * bvert.co
                    vertex_cache[triple] = bvert

                return vertex_cache[triple]

            for face in faces:
                texture_info = bsp.texture_infos[face.texture_info]
                miptex = bsp.miptextures[texture_info.miptexture_number]

                s = texture_info.s
                ds = texture_info.s_offset
                t = texture_info.t
                dt = texture_info.t_offset

                w = miptex.width
                h = miptex.height

                edges = bsp.surf_edges[face.first_edge:face.first_edge + face.number_of_edges]

                verts = []
                for edge in edges:
                    v = bsp.edges[abs(edge)].vertexes

                    # Flip edges with negative ids
                    v0, v1 = v if edge > 0 else reversed(v)

                    if len(verts) == 0:
                        verts.append(v0)

                    if v1 != verts[0]:
                        verts.append(v1)

                # Convert Vertexes to three-tuples and reverse their order
                verts = [tuple(bsp.vertexes[i][:]) for i in reversed(verts)]

                # Convert ST coordinate space to UV coordinate space
                uvs = [((numpy.dot(v, s) + ds) / w, -(numpy.dot(v, t) + dt) / h) for v in verts]

                # Create the vertexes
                verts = [create_vertex(v) for v in verts]

                bm.verts.ensure_lookup_table()

                # Create the face
                try:
                    f0 = bm.faces.new(verts)

                    # Apply UV coordinates to face
                    for i, loop in enumerate(f0.loops):
                        loop[uv_layer].uv = uvs[i]

                    # Apply material to face
                    mat = bpy.data.materials.find(miptex.name)
                    f0.material_index = mat

                    # Lightmaps
                    vs = [v.co for f in verts]
                    a = numpy.subtract(vs[0], vs[1])
                    b = numpy.subtract(vs[0], vs[2])
                    nor = tuple(numpy.cross(a, b))
                    axis = nor.index(max(nor))
                    projected_verts = [v[:axis] + v[axis + 1:] for v in vs]

                    min_x, min_y = projected_verts[0]
                    max_x, max_y = projected_verts[0]

                    for v in projected_verts[1:]:
                        min_x = min(min_x, v[0])
                        min_y = min(min_y, v[1])
                        max_x = max(max_x, v[0])
                        max_y = max(max_y, v[1])

                    top_left = math.floor(min_x / 16), math.floor(min_y / 16)
                    bottom_right = math.ceil(max_x / 16), math.floor(max_y / 16)
                    size = tuple(numpy.subtract(bottom_right, top_left))
                    length = size[0] * size[1]
                    offset = face.light_offset
                    light_data = bsp.lighting[offset:offset+length]

                except:
                    pass

                bm.faces.ensure_lookup_table()

            bm.to_mesh(me)
            bm.free()

            mesh_name = 'model.000'

            if bsp.models.index(model) == 0:
                mesh_name = 'worldspawn'

            ob = bpy.data.objects.new(mesh_name, me)

            # Ensure correct behavior in texture view mode
            for miptexture_index in range(len(bsp.miptextures)):
                ob.data.materials.append(bpy.data.materials[miptexture_index])

            bpy.context.scene.objects.link(ob)


    else:
        for mesh_index, mesh in enumerate(bsp.meshes()):
            # Worldspawn is always mesh 0
            if mesh_index == 0 and not use_worldspawn_entity:
                continue

            # Brush entities are the remaining meshes
            if mesh_index > 0 and not use_brush_entities:
                break

            me = bpy.data.meshes.new('model %d' % mesh_index)
            bm = bmesh.new()

            for vertex_index, vertex in enumerate(mesh.vertices):
                v0 = bm.verts.new(vertex)
                v0.normal = mesh.normals[vertex_index]
                v0.co = global_matrix * v0.co

            bm.verts.ensure_lookup_table()
            uv_layer = bm.loops.layers.uv.new()

            for triangle in mesh.triangles:
                t0 = bm.verts[triangle[0]]
                t1 = bm.verts[triangle[1]]
                t2 = bm.verts[triangle[2]]

                try:
                    face = bm.faces.new((t0, t1, t2))

                    face.loops[0][uv_layer].uv = mesh.uvs[triangle[0]]
                    face.loops[1][uv_layer].uv = mesh.uvs[triangle[1]]
                    face.loops[2][uv_layer].uv = mesh.uvs[triangle[2]]

                except:
                    # Ignore triangles that are defined multiple times
                    pass

            bm.faces.ensure_lookup_table()

            for sub_mesh_index, sub_mesh in enumerate(mesh.sub_meshes):
                if not sub_mesh:
                    continue

                name = bsp.miptextures[sub_mesh_index].name
                mat = bpy.data.materials.find(name)

                for triangle in sub_mesh:
                    bm.faces[triangle].material_index = mat

            bm.to_mesh(me)
            bm.free()

            mesh_name = 'brush_entity.000'

            if mesh_index == 0:
                mesh_name = 'worldspawn'

            ob = bpy.data.objects.new(mesh_name, me)

            for miptexture_index in range(len(bsp.miptextures)):
                ob.data.materials.append(bpy.data.materials[miptexture_index])

            bpy.context.scene.objects.link(ob)

    # Apply textures to faces
    for ob in [o for o in bpy.data.objects if o.type == 'MESH']:
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        bm.faces.ensure_lookup_table()

        for mi, m in enumerate(ob.data.uv_textures[0].data):
            face = bm.faces[mi]
            mat_index = face.material_index
            mat = bpy.data.materials[mat_index]
            tex = mat.texture_slots[0].texture
            m.image = tex.image

    return {'FINISHED'}
