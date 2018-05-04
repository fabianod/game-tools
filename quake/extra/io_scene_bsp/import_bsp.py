import bpy
import bmesh
import math
import numpy
from collections import namedtuple
from mathutils import Matrix, Vector

from . import atlas_packer
from .quake.bsp import Bsp, is_bspfile
from .quake import map as Map


LightMapFaceInfo = namedtuple('LightMapStruct', ['size', 'pixels', 'uvs'])


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
            lightmap_layer = bm.loops.layers.uv.new()

            vertex_cache = {}
            lightmap_infos = []

            def create_vertex(triple):
                if triple not in vertex_cache:
                    bvert = bm.verts.new(triple)
                    bvert.co = global_matrix * bvert.co
                    vertex_cache[triple] = bvert

                return vertex_cache[triple]

            for face_index, face in enumerate(faces):
                texture_info = bsp.texture_infos[face.texture_info]
                miptex = bsp.miptextures[texture_info.miptexture_number]
                if not miptex:
                    print('Missing miptex info for face: {}'.format(face_index))
                    continue

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
                bverts = [create_vertex(v) for v in verts]
                bm.verts.ensure_lookup_table()

                # Create the face
                try:
                    bface = bm.faces.new(bverts)

                    # Apply UV coordinates to face
                    for i, loop in enumerate(bface.loops):
                        loop[uv_layer].uv = uvs[i]

                    # Apply material to face
                    mat = bpy.data.materials.find(miptex.name)
                    bface.material_index = mat

                except:
                    pass

                # Lightmaps
                vs = verts[:]
                a = numpy.subtract(vs[0], vs[1])
                b = numpy.subtract(vs[0], vs[2])
                face_normal = tuple(map(abs, numpy.cross(a, b)))
                axis = face_normal.index(max(face_normal))
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
                scale = tuple(numpy.subtract(bottom_right, top_left))
                size = scale[0] + 1, scale[1] + 1
                length = size[0] * size[1]

                # Convert luxels to pixels
                offset = face.light_offset
                pixels = []

                if offset >= 0:
                    light_data = bsp.lighting[offset:offset + length]
                    for luxel in light_data:
                        r = g = b = luxel / 255
                        pixels += r, g, b, 1.0

                else:
                    pixels = (0, 0, 0, 1.0) * length

                #img = bpy.data.images.new('Lightmap.000', *size)
                #img.pixels[:] = pixels
                #img.update()

                lightmap_uvs = []
                lightmap_offset = -min_x, -min_y
                for v in projected_verts:
                    v = numpy.add(v, lightmap_offset)
                    v = numpy.divide(v, numpy.add(numpy.multiply(scale, 16), (1, 1)))
                    lightmap_uvs.append(tuple(v))

                #for i, loop in enumerate(bface.loops):
                #    loop[lightmap_layer].uv = lightmap_uvs[i]

                info = LightMapFaceInfo(size, pixels, lightmap_uvs)
                lightmap_infos.append(info)

                bm.faces.ensure_lookup_table()

            atlas_size, atlas_offsets = atlas_packer.pack(lightmap_infos)
            lightmap_img = bpy.data.images.new('Lightmap', *atlas_size)
            lightmap_img.pixels = (1, 0, 1, 1) * atlas_size[0] * atlas_size[1]
            pixels = numpy.array(lightmap_img.pixels[:])
            w, h = atlas_size
            pixels = pixels.reshape((h, w * 4))

            for i, lightmap_info in enumerate(lightmap_infos):
                lightmap_pixels = numpy.array(lightmap_info.pixels)
                width, height = lightmap_info.size
                lightmap_pixels = lightmap_pixels.reshape((height, width * 4))

                x, y = atlas_offsets[i]
                pixels[y:y + height, x * 4:x * 4 + (width * 4)] = lightmap_pixels

            pixels = numpy.array(list(reversed(pixels)))
            pixels = pixels.reshape(len(lightmap_img.pixels))
            lightmap_img.pixels[:] = pixels
            lightmap_img.update()

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
