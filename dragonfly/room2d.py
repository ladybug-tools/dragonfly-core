# coding: utf-8
"""Dragonfly Room2D."""
from ._base import _BaseGeometry
from .properties import Room2DProperties
import dragonfly.glazingparameter as glzpar
from dragonfly.glazingparameter import _GlazingParameterBase
import dragonfly.shadingparameter as shdpar
from dragonfly.shadingparameter import _ShadingParameterBase

from honeybee.typing import float_positive
import honeybee.boundarycondition as hbc
from honeybee.boundarycondition import boundary_conditions as bcs
from honeybee.boundarycondition import _BoundaryCondition, Outdoors, Surface
from honeybee.face import Face
from honeybee.room import Room

from ladybug_geometry.geometry2d.pointvector import Point2D, Vector2D
from ladybug_geometry.geometry2d.polygon import Polygon2D
from ladybug_geometry.geometry3d.pointvector import Point3D, Vector3D
from ladybug_geometry.geometry3d.plane import Plane
from ladybug_geometry.geometry3d.line import LineSegment3D
from ladybug_geometry.geometry3d.face import Face3D
from ladybug_geometry.geometry3d.polyface import Polyface3D

import math


class Room2D(_BaseGeometry):
    """A volume defined by an extruded floor plate, representing a single room or space.

    Properties:
        * name
        * display_name
        * floor_geometry
        * floor_to_ceiling_height
        * boundary_conditions
        * glazing_parameters
        * shading_parameters
        * parent
        * has_parent
        * floor_segments
        * floor_segments_2d
        * segment_count
        * segment_normals
        * floor_height
        * ceiling_height
        * volume
        * floor_area
        * exterior_wall_area
        * exterior_aperture_area
    """
    __slots__ = ('_floor_geometry', '_segment_count', '_floor_to_ceiling_height',
                 '_boundary_conditions', '_glazing_parameters', '_shading_parameters',
                 '_parent')

    def __init__(self, name, floor_geometry, floor_to_ceiling_height,
                 boundary_conditions=None, glazing_parameters=None,
                 shading_parameters=None, tolerance=None):
        """A volume defined by an extruded floor plate, representing a single room.

        Args:
            name: Room2D name. Must be < 100 characters.
            floor_geometry: A single horizontal Face3D object representing the
                floor plate of the Room. Note that this Face3D must be horiztional
                to be valid.
            floor_to_ceiling_height: A number for the height above the floor where the
                ceiling begins. Typical values range from 3 to 5 meters.
            boundary_conditions: A list of boundary conditions that match the number of
                segments in the input floor_geometry. These will be used to assign
                boundary conditions to each of the walls of the Room in the resulting
                model. If None, all boundary conditions will be Outdoors or Ground
                depending on whether ceiling of the room is below 0 (the assumed
                ground plane). Default: None.
            glazing_parameters: A list of GlazingParameter objects that dictate how the
                window geometries will be generated for each of the walls. If None,
                no windows will exist over the entire Room2D. Default: None.
            shading_parameters: A list of ShadingParameter objects that dictate how the
                shade geometries will be generated for each of the walls. If None,
                no shades will exist over the entire Room2D. Default: None.
            tolerance: The maximum difference between z values at which point vertices
                are considered to be in the same horizontal plane. This is used to check
                that all vertices of the input floor_geometry lie in the same horizontal
                floor plane. Default is None, which will not perform any check.
        """
        _BaseGeometry.__init__(self, name)  # process the name

        # process the floor_geometry
        assert isinstance(floor_geometry, Face3D), \
            'Expected ladybug_geometry Face3D. Got {}'.format(type(floor_geometry))
        if floor_geometry.normal.z >= 0:  # ensure upward-facing Face3D
            self._floor_geometry = floor_geometry
        else:
            self._floor_geometry = floor_geometry.flip()
            boundary_conditions = tuple(reversed(boundary_conditions)) if \
                boundary_conditions is not None else None
            glazing_parameters = tuple(reversed(glazing_parameters)) if \
                glazing_parameters is not None else None
            shading_parameters = tuple(reversed(shading_parameters)) if \
                shading_parameters is not None else None
        # ensure a global 2D origin, which helps in solve adjacency and the dict schema
        o_pl = Plane(Vector3D(0, 0, 1), Point3D(0, 0, self._floor_geometry.plane.o.z))
        self._floor_geometry = Face3D(self._floor_geometry.boundary,
                                      o_pl, self._floor_geometry.holes)
        # check that the floor_geometry lies in the same horizontal plane.
        if tolerance is not None:
            z_vals = tuple(pt.z for pt in self._floor_geometry.vertices)
            assert max(z_vals) - min(z_vals) <= tolerance, 'Not all of Room2D ' \
                '"{}" vertices lie within the same horizontal plane.'.format(name)

        # process segment count and floor-to-ceiling height
        self._segment_count = len(self.floor_segments)
        self.floor_to_ceiling_height = floor_to_ceiling_height

        # process the boundary conditions
        if boundary_conditions is None:
            bc = bcs.outdoors if self.ceiling_height > 0 else bcs.ground
            self._boundary_conditions = [bc for i in range(len(self))]
        else:
            value = self._check_wall_assinged_object(
                boundary_conditions, 'boundary_conditions')
            for val in value:
                assert isinstance(val, _BoundaryCondition), \
                    'Expected BoundaryCondition. Got {}'.format(type(value))
            self._boundary_conditions = value

        # process the glazing and shading parameters
        self.glazing_parameters = glazing_parameters
        self.shading_parameters = shading_parameters

        self._parent = None  # _parent will be set when Room2D is added to a Story
        self._properties = Room2DProperties(self)  # properties for extensions

    @classmethod
    def from_dict(cls, data):
        """Initialize an Room2D from a dictionary.

        Args:
            data: A dictionary representation of a Room2D object.
        """
        # check the type of dictionary
        assert data['type'] == 'Room2D', 'Expected Room2D dictionary. ' \
            'Got {}.'.format(data['type'])

        # re-assemble the floor_geometry
        bound_verts = [Point3D(pt[0], pt[1], data['floor_height'])
                       for pt in data['floor_boundary']]
        if 'floor_holes' in data:
            hole_verts = [[Point3D(pt[0], pt[1], data['floor_height'])
                          for pt in hole] for hole in data['floor_holes']]
        else:
            hole_verts = None
        floor_geometry = Face3D(bound_verts, None, hole_verts)

        # re-assemble boundary conditions
        if 'boundary_conditions' in data and data['boundary_conditions'] is not None:
            b_conditions = []
            for bc_dict in data['boundary_conditions']:
                try:
                    bc_class = getattr(hbc, bc_dict['type'])
                except AttributeError:
                    raise ValueError(
                        'Boundary condition "{}" is not supported in this honyebee '
                        'installation.'.format(bc_dict['type']))
                b_conditions.append(bc_class.from_dict(bc_dict))
        else:
            b_conditions = None

        # re-assemble glazing parameters
        if 'glazing_parameters' in data and data['glazing_parameters'] is not None:
            glz_pars = []
            for glz_dict in data['glazing_parameters']:
                if glz_dict is not None:
                    try:
                        glz_class = getattr(glzpar, glz_dict['type'])
                    except AttributeError:
                        raise ValueError(
                            'Glazing parameter "{}" is not supported in this honyebee '
                            'installation.'.format(glz_dict['type']))
                    glz_pars.append(glz_class.from_dict(glz_dict))
                else:
                    glz_pars.append(None)
        else:
            glz_pars = None

        # re-assemble shading parameters
        if 'shading_parameters' in data and data['shading_parameters'] is not None:
            shd_pars = []
            for shd_dict in data['shading_parameters']:
                if shd_dict is not None:
                    try:
                        shd_class = getattr(shdpar, shd_dict['type'])
                    except AttributeError:
                        raise ValueError(
                            'Shading parameter "{}" is not supported in this honyebee '
                            'installation.'.format(shd_dict['type']))
                    shd_pars.append(shd_class.from_dict(shd_dict))
                else:
                    shd_pars.append(None)
        else:
            shd_pars = None

        room = Room2D(data['name'], floor_geometry, data['floor_to_ceiling_height'],
                      b_conditions, glz_pars, shd_pars)
        if 'display_name' in data and data['display_name'] is not None:
            room._display_name = data['display_name']

        if data['properties']['type'] == 'Room2DProperties':
            room.properties._load_extension_attr_from_dict(data['properties'])
        return room

    @classmethod
    def from_polygon(cls, name, polygon, floor_height, floor_to_ceiling_height,
                     boundary_conditions=None, glazing_parameters=None,
                     shading_parameters=None):
        """Create a Room2D from a ladybug-geometry Polygon2D and a floor_height.

        Note that this method is not recommended for a Room with one or more holes
        (like a courtyard) since polygons cannot have holes within them.

        Args:
            name: Room2D name. Must be < 100 characters.
            polygon: A single Polygon2D object representing the floor plate of the Room.
            floor_height: A float value to place the polygon within 3D space.
            floor_to_ceiling_height: A number for the height above the floor where the
                ceiling begins. Typical values range from 3 to 5 meters.
            boundary_conditions: A list of boundary conditions that match the number of
                segments in the input floor_geometry. These will be used to assign
                boundary conditions to each of the walls of the Room in the resulting
                model. If None, all boundary conditions will be Outdoors or Ground
                depending on whether ceiling of the room is below 0 (the assumed
                ground plane). Default: None.
            glazing_parameters: A list of GlazingParameter objects that dictate how the
                window geometries will be generated for each of the walls. If None,
                no windows will exist over the entire Room2D. Default: None.
            shading_parameters: A list of ShadingParameter objects that dictate how the
                shade geometries will be generated for each of the walls. If None,
                no shades will exist over the entire Room2D. Default: None.
        """
        # check the input polygon and ensure it's counter-clockwise
        assert isinstance(polygon, Polygon2D), \
            'Expected ladybug_geometry Polygon2D. Got {}'.format(type(polygon))
        if polygon.is_clockwise:
            polygon = polygon.reverse()
            boundary_conditions = reversed(boundary_conditions) if \
                boundary_conditions is not None else None
            glazing_parameters = reversed(glazing_parameters) if \
                glazing_parameters is not None else None

        # build the Face3D
        base_plane = Plane(Vector3D(0, 0, 1), Point3D(0, 0, floor_height))
        vert3d = tuple(base_plane.xy_to_xyz(_v) for _v in polygon.vertices)
        floor_geometry = Face3D(vert3d, base_plane, enforce_right_hand=False)

        return cls(name, floor_geometry, floor_to_ceiling_height, boundary_conditions,
                   glazing_parameters, shading_parameters)

    @classmethod
    def from_vertices(cls, name, vertices, floor_height, floor_to_ceiling_height,
                      boundary_conditions=None, glazing_parameters=None,
                      shading_parameters=None):
        """Create a Room2D from 2D vertices with each vertex as an iterable of 2 floats.

        Note that this method is not recommended for a Room with one or more holes
        (like a courtyard) since the distinction between hole vertices and boundary
        vertices cannot be derived from a single list of vertices.

        Args:
            name: Room2D name. Must be < 100 characters.
            vertices: A flattened list of 2 or more vertices as (x, y) that trace
                the outline of the floor plate.
            floor_height: A float value to place the polygon within 3D space.
            floor_to_ceiling_height: A number for the height above the floor where the
                ceiling begins. Typical values range from 3 to 5 meters.
            boundary_conditions: A list of boundary conditions that match the number of
                segments in the input floor_geometry. These will be used to assign
                boundary conditions to each of the walls of the Room in the resulting
                model. If None, all boundary conditions will be Outdoors or Ground
                depending on whether ceiling of the room is below 0 (the assumed
                ground plane). Default: None.
            glazing_parameters: A list of GlazingParameter objects that dictate how the
                window geometries will be generated for each of the walls. If None,
                no windows will exist over the entire Room2D. Default: None.
            shading_parameters: A list of ShadingParameter objects that dictate how the
                shade geometries will be generated for each of the walls. If None,
                no shades will exist over the entire Room2D. Default: None.
        """
        polygon = Polygon2D(tuple(Point2D(*v) for v in vertices))
        return cls.from_polygon(
            name, polygon, floor_height, floor_to_ceiling_height,
            boundary_conditions, glazing_parameters, shading_parameters)

    @property
    def floor_geometry(self):
        """A horizontal Face3D object representing the floor plate of the Room."""
        return self._floor_geometry

    @property
    def floor_to_ceiling_height(self):
        """Get or set a number for the distance between the floor and the ceiling."""
        return self._floor_to_ceiling_height

    @floor_to_ceiling_height.setter
    def floor_to_ceiling_height(self, value):
        self._floor_to_ceiling_height = float_positive(value, 'floor-to-ceiling height')

    @property
    def boundary_conditions(self):
        """Get or set a list of boundary conditions for the wall boundary conditions."""
        return tuple(self._boundary_conditions)

    @boundary_conditions.setter
    def boundary_conditions(self, value):
        value = self._check_wall_assinged_object(value, 'boundary conditions')
        for val, glz in zip(value, self._glazing_parameters):
            assert val in bcs, 'Expected BoundaryCondition. Got {}'.format(type(value))
            if glz is not None:
                assert isinstance(val, (Outdoors, Surface)), \
                    '{} cannot be assigned to a wall with windows.'.format(val)
        self._boundary_condition = value

    @property
    def glazing_parameters(self):
        """Get or set a list of GlazingParameters describing how to generate windows.
        """
        return tuple(self._glazing_parameters)

    @glazing_parameters.setter
    def glazing_parameters(self, value):
        if value is not None:
            value = self._check_wall_assinged_object(value, 'glazing_parameters')
            for val, bc in zip(value, self._boundary_conditions):
                if val is not None:
                    assert isinstance(val, _GlazingParameterBase), \
                        'Expected Glazing Parameters. Got {}'.format(type(value))
                    assert isinstance(bc, (Outdoors, Surface)), \
                        '{} cannot be assigned to a wall with windows.'.format(bc)
            self._glazing_parameters = value
        else:
            self._glazing_parameters = [None for i in range(len(self))]

    @property
    def shading_parameters(self):
        """Get or set a list of ShadingParameters describing how to generate shades.
        """
        return tuple(self._shading_parameters)

    @shading_parameters.setter
    def shading_parameters(self, value):
        if value is not None:
            value = self._check_wall_assinged_object(value, 'shading_parameters')
            for val in value:
                if val is not None:
                    assert isinstance(val, _ShadingParameterBase), \
                        'Expected Shading Parameters. Got {}'.format(type(value))
            self._shading_parameters = value
        else:
            self._shading_parameters = [None for i in range(len(self))]

    @property
    def parent(self):
        """Parent Story if assigned. None if not assigned."""
        return self._parent

    @property
    def has_parent(self):
        """Boolean noting whether this Room2D has a parent Story."""
        return self._parent is not None

    @property
    def floor_segments(self):
        """A list of ladybug_geometry LineSegment3D objects for each wall of the Room."""
        return self._floor_geometry.boundary_segments if self._floor_geometry.holes is \
            None else self._floor_geometry.boundary_segments + \
            tuple(seg for hole in self._floor_geometry.hole_segments for seg in hole)

    @property
    def floor_segments_2d(self):
        """A list of ladybug_geometry LineSegment2D objects for each wall of the Room."""
        return self._floor_geometry.boundary_polygon2d.segments if \
            self._floor_geometry.holes is None else \
            self._floor_geometry.boundary_polygon2d.segments + \
            tuple(seg for hole in self._floor_geometry.hole_polygon2d
                  for seg in hole.segments)

    @property
    def segment_count(self):
        """The number of segments making up the floor geometry.

        This is equal to the number of walls making up the Room.
        """
        return self._segment_count

    @property
    def segment_normals(self):
        """A list of ladybug_geometry Vector2D objects for the normal of each segment."""
        return [Vector2D(seg.v.y, -seg.v.x).normalize() for seg in self.floor_segments]

    @property
    def floor_height(self):
        """Get a number for the height of the floor above the ground."""
        return self._floor_geometry[0].z

    @property
    def ceiling_height(self):
        """Get a number for the height of the ceiling above the ground."""
        return self.floor_height + self.floor_to_ceiling_height

    @property
    def volume(self):
        """Get a number for the volume of the Room."""
        return self.floor_area * self.floor_to_ceiling_height

    @property
    def floor_area(self):
        """Get a number for the floor area of the Room."""
        return self._floor_geometry.area

    @property
    def exterior_wall_area(self):
        """Get a the total wall area of the Room with an Outdoors boundary condition.
        """
        wall_areas = []
        for seg, bc in zip(self.floor_segments, self._boundary_conditions):
            if isinstance(bc, Outdoors):
                wall_areas.append(seg.length * self.floor_to_ceiling_height)
        return sum(wall_areas)

    @property
    def exterior_aperture_area(self):
        """Get a the total aperture area of the Room with an Outdoors boundary condition.
        """
        glz_areas = []
        for seg, bc, glz in zip(self.floor_segments, self._boundary_conditions,
                                self._glazing_parameters):
            if isinstance(bc, Outdoors) and glz is not None:
                area = glz.area_from_segment(seg, self.floor_to_ceiling_height)
                glz_areas.append(area)
        return sum(glz_areas)

    def segment_orientations(self, north_vector=Vector2D(0, 1)):
        """A list of numbers between 0 and 360 for the orientation of the segments.

        0 = North, 90 = East, 180 = South, 270 = West

        Args:
            north_vector: A ladybug_geometry Vector2D for the north direction.
                Default is the Y-axis (0, 1).
        """
        normals = (Vector2D(sg.v.y, -sg.v.x) for sg in self.floor_segments)
        return [math.degrees(north_vector.angle_clockwise(norm)) for norm in normals]

    def set_outdoor_glazing_parameters(self, glazing_parameter):
        """Set all of the outdoor walls to have the same glazing parameters."""
        assert isinstance(glazing_parameter, _GlazingParameterBase), \
            'Expected Glazing Parameters. Got {}'.format(type(glazing_parameter))
        glz_ps = []
        for bc in self._boundary_conditions:
            glz_p = glazing_parameter if isinstance(bc, Outdoors) else None
            glz_ps.append(glz_p)
        self._glazing_parameters = glz_ps

    def set_outdoor_shading_parameters(self, shading_parameter):
        """Set all of the outdoor walls to have the same shading parameters."""
        assert isinstance(shading_parameter, _ShadingParameterBase), \
            'Expected Glazing Parameters. Got {}'.format(type(shading_parameter))
        shd_ps = []
        for bc in self._boundary_conditions:
            shd_p = shading_parameter if isinstance(bc, Outdoors) else None
            shd_ps.append(shd_p)
        self._shading_parameters = shd_ps

    def generate_grid(self, x_dim, y_dim=None, offset=1.0):
        """Get a gridded Mesh3D object offset from the floor of this room.

        Note that the x_dim and y_dim refer to dimensions within the XY coordinate
        system of the floor Faces's plane. So rotating the planes of the floor geometry
        will result in rotated grid cells.

        Args:
            x_dim: The x dimension of the grid cells as a number.
            y_dim: The y dimension of the grid cells as a number. Default is None,
                which will assume the same cell dimension for y as is set for x.
            offset: A number for how far to offset the grid from the base face.
                Default is 1.0, which will not offset the grid to be 1 unit above
                the floor.
        """
        return self.floor_geometry.get_mesh_grid(x_dim, y_dim, offset, False)

    def set_adjacency(self, other_room_2d, self_seg_index, other_seg_index):
        """Set this Room2D to be adjacent to another and vice versa.

        Args:
            other_room_2d: Another Room2D object to be set adjacent to this one.
            self_seg_index: An integer for the wall segment of this Room2D that
                will be set adjacent to the other_room_2d.
            other_seg_index:An integer for the wall segment of the other_room_2d
                that will be set adjacent to this Room2D.
        """
        assert isinstance(other_room_2d, Room2D), \
            'Expected dragonfly Room2D. Got {}.'.format(type(other_room_2d))
        # set the boundary conditions of the segments
        names_1 = ('{}_Face{}'.format(self.name, self_seg_index + 1),
                   self.name)
        names_2 = ('{}_Face{}'.format(other_room_2d.name, other_seg_index + 1),
                   other_room_2d.name)
        self._boundary_conditions[self_seg_index] = Surface(names_2)
        other_room_2d._boundary_conditions[other_seg_index] = Surface(names_1)
        # check that the glazing parameters match
        if self._glazing_parameters[self_seg_index] is not None or \
                other_room_2d._glazing_parameters[other_seg_index] is not None:
            assert self._glazing_parameters[self_seg_index] == \
                other_room_2d._glazing_parameters[other_seg_index], \
                'Glazing parameters do not match between adjacent Room2Ds "{}" and ' \
                '"{}".'.format(self.name, other_room_2d.name)
            assert self.floor_to_ceiling_height == \
                other_room_2d.floor_to_ceiling_height, 'floor_to_ceiling_height does '\
                'not match between Room2Ds "{}" and "{}" with interior windows.'.format(
                    self.name, other_room_2d.name)
            assert self.floor_height == \
                other_room_2d.floor_height, 'floor_height does not match between '\
                'Room2Ds "{}" and "{}" with interior windows.'.format(
                    self.name, other_room_2d.name)

    def move(self, moving_vec):
        """Move this Room2D along a vector.

        Args:
            moving_vec: A ladybug_geometry Vector3D with the direction and distance
                to move the room.
        """
        self._floor_geometry = self._floor_geometry.move(moving_vec)

    def rotate_xy(self, angle, origin):
        """Rotate this Room2D counterclockwise in the XY plane by a certain angle.

        Args:
            angle: An angle in degrees.
            origin: A ladybug_geometry Point3D for the origin around which the
                object will be rotated.
        """
        self._floor_geometry = self._floor_geometry.rotate_xy(
            math.radians(angle), origin)

    def reflect(self, plane):
        """Reflect this Room2D across a plane.

        Args:
            plane: A ladybug_geometry Plane across which the object will be reflected.
        """
        self._floor_geometry = self._floor_geometry.reflect(plane.n, plane.o)
        if self._floor_geometry.normal.z < 0:  # ensure upward-facing Face3D
            self._floor_geometry = self._floor_geometry.flip()
            self._boundary_conditions = tuple(reversed(self._boundary_conditions))
            self._glazing_parameters = tuple(reversed(self._glazing_parameters))
            self._shading_parameters = tuple(reversed(self._shading_parameters))

    def scale(self, factor, origin=None):
        """Scale this Room2D by a factor from an origin point.

        Args:
            factor: A number representing how much the object should be scaled.
            origin: A ladybug_geometry Point3D representing the origin from which
                to scale. If None, it will be scaled from the World origin (0, 0, 0).
        """
        self._floor_geometry = self._floor_geometry.scale(factor, origin)
        self._floor_to_ceiling_height = self._floor_to_ceiling_height * factor

    def check_horizontal(self, tolerance, raise_exception=True):
        """Check whether the Room2D's floor geometry is horiztonal within a tolerance.

        tolerance: tolerance: The maximum difference between z values at which
            face vertices are considered at different heights.
        raise_exception: Boolean to note whether a ValueError should be raised
            if the room floor geometry is not horizontal.
        """
        z_vals = tuple(pt.z for pt in self._floor_geometry.vertices)
        if max(z_vals) - min(z_vals) <= tolerance:
            return True
        if raise_exception:
            raise ValueError(
                'Room "{}" is not horizontal to within {} tolerance.'.format(
                    self.display_name, tolerance))
        return False

    def to_honeybee(self, multiplier=1, tolerance=None):
        """Convert Dragonfly Room2D to a Honeybee Room.

        Args:
            multiplier: An integer greater than 0 that denotes the number of times
                the room is repeated. You may want to set this differently depending
                on whether you are exporting each room as its own geometry (in which
                case, this should be 1) or you only want to simulate the "unique" room
                once and have the results multiplied. Default: 1.
            tolerance: The minimum distance in z values of floor_height and
                floor_to_ceiling_height at which adjacent Faces will be split.
                If None, no splitting will occur. Default: None.
        """
        # create the honeybee Room
        room_polyface = Polyface3D.from_offset_face(
            self._floor_geometry, self.floor_to_ceiling_height)
        hb_room = Room.from_polyface3d(self.display_name, room_polyface)

        # assign boundary conditions, glazing and shading to walls
        for i, bc in enumerate(self._boundary_conditions):
            hb_room[i + 1]._boundary_condition = bc
        tol = 0 if tolerance is None else tolerance
        for i, glz_par in enumerate(self._glazing_parameters):
            if glz_par is not None:
                glz_par.add_glazing_to_face(hb_room[i + 1], tol)
        for i, shd_par in enumerate(self._shading_parameters):
            if shd_par is not None:
                shd_par.add_shading_to_face(hb_room[i + 1], tol)

        # ensure matching adjacent Faces across the Story if tolerance is input
        if tolerance is not None and self._parent is not None:
            new_faces = self._split_walls_along_height(hb_room, tolerance)
            if len(new_faces) != len(hb_room):  # rebuild the room with split surfaces
                hb_room = Room(self.name, new_faces, tolerance, 0.1)

        # set the multiplier
        hb_room.multiplier = multiplier

        # assign properties for the roof and floor from the parent Story
        try:
            hb_room[0].boundary_condition = bcs.adiabatic
            hb_room[-1].boundary_condition = bcs.adiabatic
        except AttributeError:
            pass  # honeybee_energy is not loaded and Adiabatic type doesn't exist
        if self._parent is not None and multiplier == 1:
            if self._parent.is_ground_floor:
                hb_room[0].boundary_condition = bcs.ground
            if self._parent.is_top_floor:
                hb_room[-1].boundary_condition = bcs.outdoors

        return hb_room

    def to_dict(self, abridged=False, included_prop=None):
        """Return Room2D as a dictionary.

        Args:
            abridged: Boolean to note whether the extension properties of the
                object (ie. program_type, construciton_set) should be included in detail
                (False) or just referenced by name (True). Default: False.
            included_prop: List of properties to filter keys that must be included in
                output dictionary. For example ['energy'] will include 'energy' key if
                available in properties to_dict. By default all the keys will be
                included. To exclude all the keys from extensions use an empty list.
        """
        base = {'type': 'Room2D'}
        base['name'] = self.name
        base['display_name'] = self.display_name
        base['properties'] = self.properties.to_dict(abridged, included_prop)
        base['floor_boundary'] = [(pt.x, pt.y) for pt in self._floor_geometry.boundary]
        if self._floor_geometry.has_holes:
            base['floor_holes'] = \
                [[(pt.x, pt.y) for pt in hole] for hole in self._floor_geometry.holes]
        base['floor_height'] = self._floor_geometry[0].z
        base['floor_to_ceiling_height'] = self._floor_to_ceiling_height

        bc_dicts = []
        for bc in self._boundary_conditions:
            if isinstance(bc, Outdoors) and 'energy' in base['properties']:
                bc_dicts.append(bc.to_dict(full=True))
            else:
                bc_dicts.append(bc.to_dict())
        base['boundary_conditions'] = bc_dicts

        if not all((param is None for param in self._glazing_parameters)):
            base['glazing_parameters'] = []
            for glz in self._glazing_parameters:
                val = glz.to_dict() if glz is not None else None
                base['glazing_parameters'].append(val)

        if not all((param is None for param in self._shading_parameters)):
            base['shading_parameters'] = []
            for shd in self._shading_parameters:
                val = shd.to_dict() if shd is not None else None
                base['shading_parameters'].append(val)

        return base

    @staticmethod
    def solve_adjacency(room_2ds, tolerance):
        """Solve for all adjacencies between a list of input Room2Ds.

        Args:
            room_2ds: A list of Room2Ds for which adjacencies will be solved.
            tolerance: The minimum difference between the coordinate values of two
                faces at which they can be considered centered adjacent.
        """
        for i, room_1 in enumerate(room_2ds):
            try:
                for room_2 in room_2ds[i + 1:]:
                    for j, seg_1 in enumerate(room_1.floor_segments_2d):
                        for k, seg_2 in enumerate(room_2.floor_segments_2d):
                            if not isinstance(room_2._boundary_conditions[k], Surface):
                                if seg_1.distance_to_point(seg_2.p1) <= tolerance and \
                                        seg_1.distance_to_point(seg_2.p2) <= tolerance:
                                    # set the boundary conditions of the segments
                                    room_1.set_adjacency(room_2, j, k)
                                    break
            except IndexError:
                pass  # we have reached the end of the list of zones

    @staticmethod
    def intersect_adjacency(room_2ds, tolerance):
        """Intersect the line segments of an array of Room2Ds to ensure matching walls.

        Note that this method effectively erases all assigned boundary conditions,
        glazing parameters and shading parameters as the original segments are
        subdivided. As such, it is recommended that this method be used before all
        other steps when creating a Story.

        Also note that this method does not actually set the walls that are next to one
        another to be adjacent. The solve_adjacency method must be used for this after
        runing this method.

        Args:
            room_2ds: A list of Room2Ds for which adjacencent segments will be solved.
            tolerance: The minimum difference between the coordinate values of two
                faces at which they can be considered centered adjacent.

        Returns:
            An array of Room2Ds that have been intersected with one another. Note
            that these Room2Ds lack all assigned boundary conditions, glazing parameters
            and shading parameters of the original Room2Ds.
        """
        # keep track of all data needed to map between 2D and 3D space
        master_plane = room_2ds[0].floor_geometry.plane
        move_dists = []
        is_holes = []
        polygon_2ds = []

        # map all Room geometry into the same 2D space
        for room in room_2ds:
            # ensure all starting room heights match
            dist = master_plane.o.z - room.floor_height
            move_dists.append(dist)  # record all distances moved
            is_holes.append(False)  # record that first Polygon doesn't have holes
            polygon_2ds.append(room._floor_geometry.boundary_polygon2d)
            # of there are holes in the face, add them as their own polygons
            if room._floor_geometry.has_holes:
                for hole in room._floor_geometry.hole_polygon2d:
                    move_dists.append(dist)  # record all distances moved
                    is_holes.append(True)  # record that first Polygon doesn't have holes
                    polygon_2ds.append(hole)

        # intersect the Room2D polygons within the 2D space
        int_poly = Polygon2D.intersect_polygon_segments(polygon_2ds, tolerance)

        # convert the resulting coordinates back to 3D space
        face_pts = []
        for poly, dist, is_hole in zip(int_poly, move_dists, is_holes):
            pt_3d = [master_plane.xy_to_xyz(pt) for pt in poly]
            if dist != 0:
                pt_3d = [Point3D(pt.x, pt.y, pt.z - dist) for pt in pt_3d]
            if not is_hole:
                face_pts.append((pt_3d, []))
            else:
                face_pts[-1][1].append(pt_3d)

        # rebuild all of the floor geometries to the input Room2Ds
        intersected_rooms = []
        for i, face_loops in enumerate(face_pts):
            if len(face_loops[1]) == 0:  # no holes
                new_geo = Face3D(face_loops[0], room_2ds[i].floor_geometry.plane)
            else:  # ensure holes are included
                new_geo = Face3D(face_loops[0], room_2ds[i].floor_geometry.plane,
                                 face_loops[1])
            rebuilt_room = Room2D(room_2ds[i].display_name, new_geo,
                                  room_2ds[i].floor_to_ceiling_height)
            intersected_rooms.append(rebuilt_room)
        return intersected_rooms

    def _check_wall_assinged_object(self, value, obj_name=''):
        """Check an input that gets assigned to all of the walls of the Room."""
        try:
            value = list(value) if not isinstance(value, list) else value
        except (ValueError, TypeError):
            raise TypeError('Input {} must be a list or a tuple'.format(obj_name))
        assert len(value) == len(self), 'Input {} length must be the ' \
            'same as the number of floor_segments. {} != {}'.format(
                obj_name, len(value), len(self))
        return value

    def _split_walls_along_height(self, hb_room, tolerance):
        """Split adjacent walls to ensure matching surface areas in to_honyebee workflow.

        Args:
            hb_room: A non-split Honeybee Room representation of this Room2D.
            tolerance: The minimum distance in z values of floor_height and
                floor_to_ceiling_height at which adjacent Faces will be split.
        """
        new_faces = [hb_room[0]]
        for i, bc in enumerate(self._boundary_conditions):
            face = hb_room[i + 1]
            if not isinstance(bc, Surface):
                new_faces.append(face)
            else:
                adj_rm = self._parent.room_by_name(bc.boundary_condition_objects[-1])
                flr_diff = adj_rm.floor_height - self.floor_height
                ciel_diff = self.ceiling_height - adj_rm.ceiling_height
                if flr_diff <= tolerance and ciel_diff <= tolerance:
                    # No need to split the surface along its height
                    new_faces.append(face)
                elif flr_diff > tolerance and ciel_diff > tolerance:
                    # split the face into to 3 smaller faces along its height
                    lseg = LineSegment3D.from_end_points(face.geometry[0],
                                                         face.geometry[1])
                    mid_dist = self.floor_to_ceiling_height - ciel_diff - flr_diff
                    vec1 = Vector3D(0, 0, flr_diff)
                    vec2 = Vector3D(0, 0, self.floor_to_ceiling_height - ciel_diff)
                    below = Face3D.from_extrusion(lseg, vec1)
                    mid = Face3D.from_extrusion(lseg.move(vec1), Vector3D(0, 0, mid_dist))
                    above = Face3D.from_extrusion(lseg.move(vec2), Vector3D(0, 0, ciel_diff))
                    mid_face = face.duplicate()
                    mid_face._geometry = mid
                    below_face = Face('{}_Below'.format(face.name), below)
                    above_face = Face('{}_Above'.format(face.name), above)
                    try:
                        below_face.boundary_condition = bcs.adiabatic
                        above_face.boundary_condition = bcs.adiabatic
                    except AttributeError:
                        pass  # honeybee_energy is not loaded
                    new_faces.extend([below_face, mid_face, above_face])
                elif flr_diff > tolerance:
                    # split the face into to 2 smaller faces along its height
                    lseg = LineSegment3D.from_end_points(face.geometry[0],
                                                         face.geometry[1])
                    mid_dist = self.floor_to_ceiling_height - flr_diff
                    vec1 = Vector3D(0, 0, flr_diff)
                    below = Face3D.from_extrusion(lseg, vec1)
                    mid = Face3D.from_extrusion(lseg.move(vec1), Vector3D(0, 0, mid_dist))
                    mid_face = face.duplicate()
                    mid_face._geometry = mid
                    below_face = Face('{}_Below'.format(face.name), below)
                    try:
                        below_face.boundary_condition = bcs.adiabatic
                    except AttributeError:
                        pass  # honeybee_energy is not loaded
                    new_faces.extend([below_face, mid_face])
                elif ciel_diff > tolerance:
                    # split the face into to 2 smaller faces along its height
                    lseg = LineSegment3D.from_end_points(face.geometry[0],
                                                         face.geometry[1])
                    mid_dist = self.floor_to_ceiling_height - ciel_diff
                    vec1 = Vector3D(0, 0, mid_dist)
                    mid = Face3D.from_extrusion(lseg, vec1)
                    above = Face3D.from_extrusion(lseg.move(vec1), Vector3D(0, 0, ciel_diff))
                    mid_face = face.duplicate()
                    mid_face._geometry = mid
                    above_face = Face('{}_Above'.format(face.name), above)
                    try:
                        above_face.boundary_condition = bcs.adiabatic
                    except AttributeError:
                        pass  # honeybee_energy is not loaded
                    new_faces.extend([mid_face, above_face])
        new_faces.append(hb_room[-1])
        return new_faces

    def __copy__(self):
        new_r = Room2D(self.name, self._floor_geometry, self.floor_to_ceiling_height,
                       self._boundary_conditions)
        new_r._display_name = self.display_name
        new_r._parent = self._parent
        new_r._glazing_parameters = self._glazing_parameters
        new_r._shading_parameters = self._shading_parameters
        new_r._properties._duplicate_extension_attr(self._properties)
        return new_r

    def __len__(self):
        return self._segment_count

    def __getitem__(self, key):
        return self.floor_segments[key]

    def __iter__(self):
        return iter(self.floor_segments)

    def __repr__(self):
        return 'Room2D: %s' % self.display_name
