# coding: utf-8
"""Dragonfly Room2D."""
from __future__ import division

from ._base import _BaseGeometry
from .properties import Room2DProperties
import dragonfly.windowparameter as glzpar
from dragonfly.windowparameter import _WindowParameterBase, _AsymmetricBase
import dragonfly.shadingparameter as shdpar
from dragonfly.shadingparameter import _ShadingParameterBase
import dragonfly.writer.room2d as writer

from honeybee.typing import float_positive, clean_string
import honeybee.boundarycondition as hbc
from honeybee.boundarycondition import boundary_conditions as bcs
from honeybee.boundarycondition import _BoundaryCondition, Outdoors, Surface
from honeybee.facetype import face_types as ftyp
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

    Args:
        identifier: Text string for a unique Room2D ID. Must be < 100 characters and
            not contain any spaces or special characters.
        floor_geometry: A single horizontal Face3D object representing the
            floor plate of the Room. Note that this Face3D must be horizontal
            to be valid.
        floor_to_ceiling_height: A number for the height above the floor where the
            ceiling begins. This should be in the same units system as the input
            floor_geometry. Typical values range from 3 to 5 meters.
        boundary_conditions: A list of boundary conditions that match the number of
            segments in the input floor_geometry. These will be used to assign
            boundary conditions to each of the walls of the Room in the resulting
            model. If None, all boundary conditions will be Outdoors or Ground
            depending on whether ceiling of the room is below 0 (the assumed
            ground plane). Default: None.
        window_parameters: A list of WindowParameter objects that dictate how the
            window geometries will be generated for each of the walls. If None,
            no windows will exist over the entire Room2D. Default: None.
        shading_parameters: A list of ShadingParameter objects that dictate how the
            shade geometries will be generated for each of the walls. If None,
            no shades will exist over the entire Room2D. Default: None.
        is_ground_contact: A boolean noting whether this Room2D has its floor
            in contact with the ground. Default: False.
        is_top_exposed: A boolean noting whether this Room2D has its ceiling
            exposed to the outdoors. Default: False.
        tolerance: The maximum difference between z values at which point vertices
            are considered to be in the same horizontal plane. This is used to check
            that all vertices of the input floor_geometry lie in the same horizontal
            floor plane. Default is 0, which will not perform any check.

    Properties:
        * identifier
        * display_name
        * floor_geometry
        * floor_to_ceiling_height
        * boundary_conditions
        * window_parameters
        * shading_parameters
        * air_boundaries
        * is_ground_contact
        * is_top_exposed
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
        * min
        * max
        * user_data
    """
    __slots__ = ('_floor_geometry', '_segment_count', '_floor_to_ceiling_height',
                 '_boundary_conditions', '_window_parameters', '_shading_parameters',
                 '_air_boundaries', '_is_ground_contact', '_is_top_exposed', '_parent')

    def __init__(self, identifier, floor_geometry, floor_to_ceiling_height,
                 boundary_conditions=None, window_parameters=None,
                 shading_parameters=None, is_ground_contact=False, is_top_exposed=False,
                 tolerance=0):
        """A volume defined by an extruded floor plate, representing a single room."""
        _BaseGeometry.__init__(self, identifier)  # process the identifier

        # process the floor_geometry
        assert isinstance(floor_geometry, Face3D), \
            'Expected ladybug_geometry Face3D. Got {}'.format(type(floor_geometry))
        if floor_geometry.normal.z >= 0:  # ensure upward-facing Face3D
            self._floor_geometry = floor_geometry
        else:
            self._floor_geometry = floor_geometry.flip()
        # ensure a global 2D origin, which helps in solve adjacency and the dict schema
        o_pl = Plane(Vector3D(0, 0, 1), Point3D(0, 0, self._floor_geometry.plane.o.z))
        self._floor_geometry = Face3D(self._floor_geometry.boundary,
                                      o_pl, self._floor_geometry.holes)
        # check that the floor_geometry lies in the same horizontal plane.
        if tolerance != 0:
            z_vals = tuple(pt.z for pt in self._floor_geometry.vertices)
            assert max(z_vals) - min(z_vals) <= tolerance, 'Not all of Room2D ' \
                '"{}" vertices lie within the same horizontal plane.'.format(identifier)

        # process segment count and floor-to-ceiling height
        self._segment_count = len(self.floor_segments)
        self.floor_to_ceiling_height = floor_to_ceiling_height

        # process the boundary conditions
        if boundary_conditions is None:
            bc = bcs.outdoors if self.ceiling_height > 0 else bcs.ground
            self._boundary_conditions = [bc for i in range(len(self))]
        else:
            value = self._check_wall_assigned_object(
                boundary_conditions, 'boundary_conditions')
            for val in value:
                assert isinstance(val, _BoundaryCondition), \
                    'Expected BoundaryCondition. Got {}'.format(type(value))
            self._boundary_conditions = value

        # process the window and shading parameters
        self.window_parameters = window_parameters
        self.shading_parameters = shading_parameters

        # ensure all wall-assigned objects align with the geometry if it has been flipped
        if floor_geometry.normal.z < 0:
            new_bcs, new_win_pars, new_shd_pars = Room2D._flip_wall_assigned_objects(
                floor_geometry, self._boundary_conditions, self._window_parameters,
                self._shading_parameters)
            self._boundary_conditions = new_bcs
            self._window_parameters = new_win_pars
            self._shading_parameters = new_shd_pars

        # process the top and bottom exposure properties
        self.is_ground_contact = is_ground_contact
        self.is_top_exposed = is_top_exposed

        self._air_boundaries = None  # will be set if it's ever used
        self._parent = None  # _parent will be set when Room2D is added to a Story
        self._properties = Room2DProperties(self)  # properties for extensions

    @classmethod
    def from_dict(cls, data, tolerance=0):
        """Initialize an Room2D from a dictionary.

        Args:
            data: A dictionary representation of a Room2D object.
            tolerance: The maximum difference between z values at which point vertices
                are considered to be in the same horizontal plane. This is used to check
                that all vertices of the input floor_geometry lie in the same horizontal
                floor plane. Default is 0, which will not perform any check.
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
                        'Boundary condition "{}" is not supported in this honeybee '
                        'installation.'.format(bc_dict['type']))
                b_conditions.append(bc_class.from_dict(bc_dict))
        else:
            b_conditions = None

        # re-assemble window parameters
        if 'window_parameters' in data and data['window_parameters'] is not None:
            glz_pars = []
            for glz_dict in data['window_parameters']:
                if glz_dict is not None:
                    try:
                        glz_class = getattr(glzpar, glz_dict['type'])
                    except AttributeError:
                        raise ValueError(
                            'Window parameter "{}" is not supported in this honeybee '
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
                            'Shading parameter "{}" is not supported in this honeybee '
                            'installation.'.format(shd_dict['type']))
                    shd_pars.append(shd_class.from_dict(shd_dict))
                else:
                    shd_pars.append(None)
        else:
            shd_pars = None

        # get the top and bottom exposure properties
        grnd = data['is_ground_contact'] if 'is_ground_contact' in data else False
        top = data['is_top_exposed'] if 'is_top_exposed' in data else False

        room = Room2D(data['identifier'], floor_geometry,
                      data['floor_to_ceiling_height'],
                      b_conditions, glz_pars, shd_pars, grnd, top, tolerance)
        if 'air_boundaries' in data and data['air_boundaries'] is not None:
            room.air_boundaries = data['air_boundaries']
        if 'display_name' in data and data['display_name'] is not None:
            room._display_name = data['display_name']
        if 'user_data' in data and data['user_data'] is not None:
            room.user_data = data['user_data']

        if data['properties']['type'] == 'Room2DProperties':
            room.properties._load_extension_attr_from_dict(data['properties'])
        return room

    @classmethod
    def from_polygon(cls, identifier, polygon, floor_height, floor_to_ceiling_height,
                     boundary_conditions=None, window_parameters=None,
                     shading_parameters=None, is_ground_contact=False,
                     is_top_exposed=False):
        """Create a Room2D from a ladybug-geometry Polygon2D and a floor_height.

        Note that this method is not recommended for a Room with one or more holes
        (like a courtyard) since polygons cannot have holes within them.

        Args:
            identifier: Text string for a unique Room2D ID. Must be < 100 characters
                and not contain any spaces or special characters.
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
            window_parameters: A list of WindowParameter objects that dictate how the
                window geometries will be generated for each of the walls. If None,
                no windows will exist over the entire Room2D. Default: None.
            shading_parameters: A list of ShadingParameter objects that dictate how the
                shade geometries will be generated for each of the walls. If None,
                no shades will exist over the entire Room2D. Default: None.
            is_ground_contact: A boolean to note whether this Room2D has its floor
                in contact with the ground. Default: False.
            is_top_exposed: A boolean to note whether this Room2D has its ceiling
                exposed to the outdoors. Default: False.
        """
        # check the input polygon and ensure it's counter-clockwise
        assert isinstance(polygon, Polygon2D), \
            'Expected ladybug_geometry Polygon2D. Got {}'.format(type(polygon))
        if polygon.is_clockwise:
            polygon = polygon.reverse()
            if boundary_conditions is not None:
                boundary_conditions = list(reversed(boundary_conditions))
            if window_parameters is not None:
                new_win_pars = []
                for seg, win_par in zip(polygon.segments, reversed(window_parameters)):
                    if isinstance(win_par, _AsymmetricBase):
                        new_win_pars.append(win_par.flip(seg.length))
                    else:
                        new_win_pars.append(win_par)
                window_parameters = new_win_pars
            if shading_parameters is not None:
                shading_parameters = list(reversed(shading_parameters))

        # build the Face3D without using right-hand rule to ensure alignment w/ bcs
        base_plane = Plane(Vector3D(0, 0, 1), Point3D(0, 0, floor_height))
        vert3d = tuple(base_plane.xy_to_xyz(_v) for _v in polygon.vertices)
        floor_geometry = Face3D(vert3d, base_plane, enforce_right_hand=False)

        return cls(identifier, floor_geometry, floor_to_ceiling_height,
                   boundary_conditions, window_parameters, shading_parameters,
                   is_ground_contact, is_top_exposed)

    @classmethod
    def from_vertices(cls, identifier, vertices, floor_height, floor_to_ceiling_height,
                      boundary_conditions=None, window_parameters=None,
                      shading_parameters=None, is_ground_contact=False,
                      is_top_exposed=False):
        """Create a Room2D from 2D vertices with each vertex as an iterable of 2 floats.

        Note that this method is not recommended for a Room with one or more holes
        (like a courtyard) since the distinction between hole vertices and boundary
        vertices cannot be derived from a single list of vertices.

        Args:
            identifier: Text string for a unique Room2D ID. Must be < 100 characters
                and not contain any spaces or special characters.
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
            window_parameters: A list of WindowParameter objects that dictate how the
                window geometries will be generated for each of the walls. If None,
                no windows will exist over the entire Room2D. Default: None.
            shading_parameters: A list of ShadingParameter objects that dictate how the
                shade geometries will be generated for each of the walls. If None,
                no shades will exist over the entire Room2D. Default: None.
            is_ground_contact: A boolean to note whether this Room2D has its floor
                in contact with the ground. Default: False.
            is_top_exposed: A boolean to note whether this Room2D has its ceiling
                exposed to the outdoors. Default: False.
        """
        polygon = Polygon2D(tuple(Point2D(*v) for v in vertices))
        return cls.from_polygon(
            identifier, polygon, floor_height, floor_to_ceiling_height,
            boundary_conditions, window_parameters, shading_parameters,
            is_ground_contact, is_top_exposed)

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
        """Get or set a tuple of boundary conditions for the wall boundary conditions."""
        return tuple(self._boundary_conditions)

    @boundary_conditions.setter
    def boundary_conditions(self, value):
        value = self._check_wall_assigned_object(value, 'boundary conditions')
        for val, glz in zip(value, self._window_parameters):
            assert val in bcs, 'Expected BoundaryCondition. Got {}'.format(type(value))
            if glz is not None:
                assert isinstance(val, (Outdoors, Surface)), \
                    '{} cannot be assigned to a wall with windows.'.format(val)
        self._boundary_conditions = value

    @property
    def window_parameters(self):
        """Get or set a tuple of WindowParameters describing how to generate windows.
        """
        return tuple(self._window_parameters)

    @window_parameters.setter
    def window_parameters(self, value):
        if value is not None:
            value = self._check_wall_assigned_object(value, 'window_parameters')
            for val, bc in zip(value, self._boundary_conditions):
                if val is not None:
                    assert isinstance(val, _WindowParameterBase), \
                        'Expected Window Parameters. Got {}'.format(type(value))
                    assert isinstance(bc, (Outdoors, Surface)), \
                        '{} cannot be assigned to a wall with windows.'.format(bc)
            self._window_parameters = value
        else:
            self._window_parameters = [None for i in range(len(self))]

    @property
    def shading_parameters(self):
        """Get or set a tuple of ShadingParameters describing how to generate shades.
        """
        return tuple(self._shading_parameters)

    @shading_parameters.setter
    def shading_parameters(self, value):
        if value is not None:
            value = self._check_wall_assigned_object(value, 'shading_parameters')
            for val in value:
                if val is not None:
                    assert isinstance(val, _ShadingParameterBase), \
                        'Expected Shading Parameters. Got {}'.format(type(value))
            self._shading_parameters = value
        else:
            self._shading_parameters = [None for i in range(len(self))]

    @property
    def air_boundaries(self):
        """Get or set a tuple of booleans for whether each wall has an air boundary type.

        False values indicate a standard opaque type while True values indicate
        an AirBoundary type. All walls will be False by default. Note that any
        walls with a True air boundary must have a Surface boundary condition
        without any windows.
        """
        if self._air_boundaries is None:
            self._air_boundaries = [False] * len(self)
        return tuple(self._air_boundaries)

    @air_boundaries.setter
    def air_boundaries(self, value):
        if value is not None:
            value = self._check_wall_assigned_object(value, 'air boundaries')
            value = [bool(val) for val in value]
            all_props = zip(value, self._boundary_conditions, self._window_parameters)
            for val, bnd, glz in all_props:
                if val:
                    assert isinstance(bnd, Surface), 'Air boundaries must be assigned ' \
                        'to walls with Surface boundary conditions. Not {}.'.format(bnd)
                    assert glz is None, \
                        'Air boundaries cannot be assigned to a wall with windows.'
        self._air_boundaries = value

    @property
    def is_ground_contact(self):
        """Get or set a boolean noting whether the floor is in contact with the ground.
        """
        return self._is_ground_contact

    @is_ground_contact.setter
    def is_ground_contact(self, value):
        self._is_ground_contact = bool(value)

    @property
    def is_top_exposed(self):
        """Get or set a boolean noting whether the ceiling is exposed to the outdoors.
        """
        return self._is_top_exposed

    @is_top_exposed.setter
    def is_top_exposed(self, value):
        self._is_top_exposed = bool(value)

    @property
    def parent(self):
        """Get the parent Story if it is assigned. None if it is not assigned."""
        return self._parent

    @property
    def has_parent(self):
        """Get a boolean noting whether this Room2D has a parent Story."""
        return self._parent is not None

    @property
    def floor_segments(self):
        """Get a list of LineSegment3D objects for each wall of the Room."""
        return self._floor_geometry.boundary_segments if self._floor_geometry.holes is \
            None else self._floor_geometry.boundary_segments + \
            tuple(seg for hole in self._floor_geometry.hole_segments for seg in hole)

    @property
    def floor_segments_2d(self):
        """Get a list of LineSegment2D objects for each wall of the Room."""
        return self._floor_geometry.boundary_polygon2d.segments if \
            self._floor_geometry.holes is None else \
            self._floor_geometry.boundary_polygon2d.segments + \
            tuple(seg for hole in self._floor_geometry.hole_polygon2d
                  for seg in hole.segments)

    @property
    def segment_count(self):
        """Get the number of segments making up the floor geometry.

        This is equal to the number of walls making up the Room.
        """
        return self._segment_count

    @property
    def segment_normals(self):
        """Get a list of Vector2D objects for the normal of each segment."""
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
                                self._window_parameters):
            if isinstance(bc, Outdoors) and glz is not None:
                area = glz.area_from_segment(seg, self.floor_to_ceiling_height)
                glz_areas.append(area)
        return sum(glz_areas)

    @property
    def min(self):
        """Get a Point2D for the min bounding rectangle vertex in the XY plane.

        This is useful in calculations to determine if this Room2D is in proximity
        to other Room2Ds.
        """
        return self._floor_geometry.boundary_polygon2d.min

    @property
    def max(self):
        """Get a Point2D for the max bounding rectangle vertex in the XY plane.

        This is useful in calculations to determine if this Room2D is in proximity
        to other Room2Ds.
        """
        return self._floor_geometry.boundary_polygon2d.max

    def segment_orientations(self, north_vector=Vector2D(0, 1)):
        """A list of numbers between 0 and 360 for the orientation of the segments.

        0 = North, 90 = East, 180 = South, 270 = West

        Args:
            north_vector: A ladybug_geometry Vector2D for the north direction.
                Default is the Y-axis (0, 1).
        """
        normals = (Vector2D(sg.v.y, -sg.v.x) for sg in self.floor_segments)
        return [math.degrees(north_vector.angle_clockwise(norm)) for norm in normals]

    def set_outdoor_window_parameters(self, window_parameter):
        """Set all of the outdoor walls to have the same window parameters."""
        assert isinstance(window_parameter, _WindowParameterBase), \
            'Expected Window Parameters. Got {}'.format(type(window_parameter))
        glz_ps = []
        for bc in self._boundary_conditions:
            glz_p = window_parameter if isinstance(bc, Outdoors) else None
            glz_ps.append(glz_p)
        self._window_parameters = glz_ps

    def set_outdoor_shading_parameters(self, shading_parameter):
        """Set all of the outdoor walls to have the same shading parameters."""
        assert isinstance(shading_parameter, _ShadingParameterBase), \
            'Expected Window Parameters. Got {}'.format(type(shading_parameter))
        shd_ps = []
        for bc in self._boundary_conditions:
            shd_p = shading_parameter if isinstance(bc, Outdoors) else None
            shd_ps.append(shd_p)
        self._shading_parameters = shd_ps

    def add_prefix(self, prefix):
        """Change the identifier of this object by inserting a prefix.

        This is particularly useful in workflows where you duplicate and edit
        a starting object and then want to combine it with the original object
        into one Model (like making a model of repeated rooms) since all objects
        within a Model must have unique identifiers.

        Args:
            prefix: Text that will be inserted at the start of this object's
                (and child segments') identifier and display_name. It is recommended
                that this prefix be short to avoid maxing out the 100 allowable
                characters for dragonfly identifiers.
        """
        self._identifier = clean_string('{}_{}'.format(prefix, self.identifier))
        self.display_name = '{}_{}'.format(prefix, self.display_name)
        self.properties.add_prefix(prefix)
        for i, bc in enumerate(self._boundary_conditions):
            if isinstance(bc, Surface):
                new_face_id = '{}_{}'.format(prefix, bc.boundary_condition_objects[0])
                new_room_id = '{}_{}'.format(prefix, bc.boundary_condition_objects[1])
                self._boundary_conditions[i] = \
                    Surface((new_face_id, new_room_id))

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
        return self.floor_geometry.mesh_grid(x_dim, y_dim, offset, False)

    def set_adjacency(self, other_room_2d, self_seg_index, other_seg_index):
        """Set a segment of this Room2D to be adjacent to another and vice versa.

        Note that, adjacent segments must possess matching WindowParameters in
        order to be valid.

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
        ids_1 = ('{}..Face{}'.format(self.identifier, self_seg_index + 1),
                 self.identifier)
        ids_2 = ('{}..Face{}'.format(other_room_2d.identifier, other_seg_index + 1),
                 other_room_2d.identifier)
        self._boundary_conditions[self_seg_index] = Surface(ids_2)
        other_room_2d._boundary_conditions[other_seg_index] = Surface(ids_1)
        # check that the window parameters match between segments
        if self._window_parameters[self_seg_index] is not None or \
                other_room_2d._window_parameters[other_seg_index] is not None:
            assert self._window_parameters[self_seg_index] == \
                other_room_2d._window_parameters[other_seg_index], \
                'Window parameters do not match between adjacent Room2Ds "{}" and ' \
                '"{}".'.format(self.identifier, other_room_2d.identifier)

    def set_boundary_condition(self, seg_index, boundary_condition):
        """Set a single segment of this Room2D to have a certain boundary condition.

        Args:
            seg_index: An integer for the wall segment of this Room2D for which
                the boundary condition will be set.
            boundary_condition: A boundary condition object.
        """
        assert boundary_condition in bcs, \
            'Expected boundary condition. Got {}.'.format(type(boundary_condition))
        if self._window_parameters[seg_index] is not None:
            assert isinstance(boundary_condition, (Outdoors, Surface)), '{} cannot be ' \
                'assigned to a wall with windows.'.format(boundary_condition)
        self._boundary_conditions[seg_index] = boundary_condition

    def set_air_boundary(self, seg_index):
        """Set a single segment of this Room2D to have an air boundary type.

        Args:
            seg_index: An integer for the wall segment of this Room2D for which
                the boundary condition will be set.
        """
        self.air_boundaries  # trigger generation of values if they don't exist
        assert self._window_parameters[seg_index] is None, \
            'Air boundaries cannot be assigned to a wall with windows.'
        assert isinstance(self._boundary_conditions[seg_index], Surface), \
            'Air boundaries must be assigned to walls with Surface boundary conditions.'
        self._air_boundaries[seg_index] = True

    def move(self, moving_vec):
        """Move this Room2D along a vector.

        Args:
            moving_vec: A ladybug_geometry Vector3D with the direction and distance
                to move the room.
        """
        self._floor_geometry = self._floor_geometry.move(moving_vec)
        self.properties.move(moving_vec)

    def rotate_xy(self, angle, origin):
        """Rotate this Room2D counterclockwise in the XY plane by a certain angle.

        Args:
            angle: An angle in degrees.
            origin: A ladybug_geometry Point3D for the origin around which the
                object will be rotated.
        """
        self._floor_geometry = self._floor_geometry.rotate_xy(
            math.radians(angle), origin)
        self.properties.rotate_xy(angle, origin)

    def reflect(self, plane):
        """Reflect this Room2D across a plane.

        Args:
            plane: A ladybug_geometry Plane across which the object will be reflected.
        """
        assert plane.n.z == 0, \
            'Plane normal must be in XY plane to use it on Room2D.reflect.'
        self._floor_geometry = self._floor_geometry.reflect(plane.n, plane.o)
        if self._floor_geometry.normal.z < 0:  # ensure upward-facing Face3D
            new_bcs, new_win_pars, new_shd_pars = Room2D._flip_wall_assigned_objects(
                self._floor_geometry, self._boundary_conditions,
                self._window_parameters, self._shading_parameters)
            self._boundary_conditions = new_bcs
            self._window_parameters = new_win_pars
            self._shading_parameters = new_shd_pars
            self._floor_geometry = self._floor_geometry.flip()
        self.properties.reflect(plane)

    def scale(self, factor, origin=None):
        """Scale this Room2D by a factor from an origin point.

        Note that this will scale both the Room2D geometry and the WindowParameters
        and FacadeParameters assigned to this Room2D.

        Args:
            factor: A number representing how much the object should be scaled.
            origin: A ladybug_geometry Point3D representing the origin from which
                to scale. If None, it will be scaled from the World origin (0, 0, 0).
        """
        # scale the Room2D geometry
        self._floor_geometry = self._floor_geometry.scale(factor, origin)
        self._floor_to_ceiling_height = self._floor_to_ceiling_height * factor

        # scale the window parameters
        for i, win_par in enumerate(self._window_parameters):
            if win_par is not None:
                self._window_parameters[i] = win_par.scale(factor)

        # scale the shading parameters
        for i, shd_par in enumerate(self._shading_parameters):
            if shd_par is not None:
                self._shading_parameters[i] = shd_par.scale(factor)

        self.properties.scale(factor, origin)

    def check_horizontal(self, tolerance=0.01, raise_exception=True):
        """Check whether the Room2D's floor geometry is horizontal within a tolerance.

        Args:
            tolerance: The maximum difference between z values at which
                face vertices are considered at different heights. Default: 0.01,
                suitable for objects in meters.
            raise_exception: Boolean to note whether a ValueError should be raised
                if the room floor geometry is not horizontal.
        """
        z_vals = tuple(pt.z for pt in self._floor_geometry.vertices)
        if max(z_vals) - min(z_vals) <= tolerance:
            return ''
        msg = 'Room "{}" is not horizontal to within {} tolerance.'.format(
            self.display_name, tolerance)
        if raise_exception:
            raise ValueError(msg)
        return msg

    def remove_colinear_vertices(self, tolerance=0.01):
        """Get a version of this Room2D without colinear or duplicate vertices.

        Note that this method effectively erases all assigned boundary conditions,
        window parameters and shading parameters as many of the original segments
        may be deleted. As such, it is recommended that this method be used before
        all other steps when creating a Story.

        Args:
            tolerance: The minimum distance between a vertex and the line it lies
                upon at which point the vertex is considered colinear. Default: 0.01,
                suitable for objects in meters.
        """
        new_geo = self.floor_geometry.remove_colinear_vertices(tolerance)
        rebuilt_room = Room2D(
            self.identifier, new_geo, self.floor_to_ceiling_height,
            is_ground_contact=self.is_ground_contact,
            is_top_exposed=self.is_top_exposed)
        rebuilt_room._display_name = self.display_name
        rebuilt_room._user_data = self._user_data
        rebuilt_room._parent = self._parent
        rebuilt_room._properties._duplicate_extension_attr(self._properties)
        return rebuilt_room

    def to_honeybee(self, multiplier=1, add_plenum=False, tolerance=0.01):
        """Convert Dragonfly Room2D to a Honeybee Room.

        Args:
            multiplier: An integer greater than 0 that denotes the number of times
                the room is repeated. You may want to set this differently depending
                on whether you are exporting each room as its own geometry (in which
                case, this should be 1) or you only want to simulate the "unique" room
                once and have the results multiplied. Default: 1.
            add_plenum: Boolean to indicate whether ceiling/floor plenums should
                be auto-generated for the Room in which case this output will
                be a list instead of a single Room. The height of the ceiling plenum
                will be autocalculated as the difference between the Room2D
                ceiling height and Story ceiling height. The height of the floor
                plenum will be autocalculated as the difference between the Room2D
                floor height and Story floor height. (Default: False).
            tolerance: The minimum distance in z values of floor_height and
                floor_to_ceiling_height at which adjacent Faces will be split.
                This is also used in the generation of Windows, and to check if the
                Room ceiling is adjacent to the upper floor of the Story before
                generating a plenum. Default: 0.01, suitable for objects in meters.

        Returns:
            A tuple with the two items below.

            * hb_room -- If add_plenum is False, this will be honeybee-core Room
                representing the dragonfly Room2D. If the add_plenum argument is True,
                this item will be a list of honeybee-core Rooms, with the hb_room as
                the first item, and up to two additional items:

                * ceil_plenum -- A honeybee-core Room representing the ceiling
                    plenum. If there isn't enough space between the Story
                    floor_to_floor_height and the Room2D floor_to_ceiling height,
                    this item will be None.

                * floor_plenum -- A honeybee-core Room representing the floor plenum.
                    If there isn't enough space between the Story floor_height and
                    the Room2D floor_height, this item will be None.

            * adjacencies -- A list of tuples that record any adjacencies that
                should be set on the level of the Story to which the Room2D belongs.
                Each tuple will have a honeybee Face as the first item and a
                tuple of Surface.boundary_condition_objects as the second item.
        """
        # create the honeybee Room
        room_polyface = Polyface3D.from_offset_face(
            self._floor_geometry, self.floor_to_ceiling_height)
        hb_room = Room.from_polyface3d(self.identifier, room_polyface)

        # assign BCs and record any Surface conditions to be set on the story level
        adjacencies = []
        for i, bc in enumerate(self._boundary_conditions):
            if not isinstance(bc, Surface):
                hb_room[i + 1]._boundary_condition = bc
            else:
                adjacencies.append((hb_room[i + 1], bc.boundary_condition_objects))

        # assign windows, shading, and air boundary properties to walls
        for i, glz_par in enumerate(self._window_parameters):
            if glz_par is not None:
                glz_par.add_window_to_face(hb_room[i + 1], tolerance)
        for i, shd_par in enumerate(self._shading_parameters):
            if shd_par is not None:
                shd_par.add_shading_to_face(hb_room[i + 1], tolerance)
        if self._air_boundaries is not None:
            for i, a_bnd in enumerate(self._air_boundaries):
                if a_bnd:
                    hb_room[i + 1].type = ftyp.air_boundary

        # ensure matching adjacent Faces across the Story if tolerance is input
        if self._parent is not None:
            new_faces = self._split_walls_along_height(hb_room, tolerance)
            if len(new_faces) != len(hb_room):
                # rebuild the room with split surfaces
                hb_room = Room(self.identifier, new_faces, tolerance, 0.1)
                # update adjacencies with the new split face
                for i, adj in enumerate(adjacencies):
                    face_id = adj[0].identifier
                    for face in hb_room.faces:
                        if face.identifier == face_id:
                            adjacencies[i] = (face, adj[1])
                            break

        # set the story, multiplier, display_name, and user_data
        if self.has_parent:
            hb_room.story = self.parent.identifier
        hb_room.multiplier = multiplier
        hb_room._display_name = self._display_name
        hb_room._user_data = self._user_data

        # assign boundary conditions for the roof and floor
        try:
            hb_room[0].boundary_condition = bcs.adiabatic
            hb_room[-1].boundary_condition = bcs.adiabatic
        except AttributeError:
            pass  # honeybee_energy is not loaded and Adiabatic type doesn't exist
        if self._is_ground_contact:
            hb_room[0].boundary_condition = bcs.ground
        if self._is_top_exposed:
            hb_room[-1].boundary_condition = bcs.outdoors

        # transfer any extension properties assigned to the Room2D and return result
        hb_room._properties = self.properties.to_honeybee(hb_room)
        if not add_plenum:
            return hb_room, adjacencies

        # add plenums if requested and return results
        hb_plenums = self._honeybee_plenums(hb_room, tolerance=tolerance)
        for hb_plenum in hb_plenums:  # transfer the parent's construction set
            hb_plenum._properties = self.properties.to_honeybee(hb_plenum)
            try:  # set the program to unconditioned plenum and assign infiltration
                hb_plenum.properties.energy.program_type = None
                hb_plenum.properties.energy.hvac = None
                hb_plenum.properties.energy.infiltration = \
                    hb_room.properties.energy.infiltration
            except AttributeError:
                pass  # honeybee-energy is not loaded; ignore all these energy properties
        return [hb_room] + hb_plenums, adjacencies

    def to_dict(self, abridged=False, included_prop=None):
        """Return Room2D as a dictionary.

        Args:
            abridged: Boolean to note whether the extension properties of the
                object (ie. program_type, construction_set) should be included in detail
                (False) or just referenced by identifier (True). Default: False.
            included_prop: List of properties to filter keys that must be included in
                output dictionary. For example ['energy'] will include 'energy' key if
                available in properties to_dict. By default all the keys will be
                included. To exclude all the keys from extensions use an empty list.
        """
        base = {'type': 'Room2D'}
        base['identifier'] = self.identifier
        base['display_name'] = self.display_name
        base['properties'] = self.properties.to_dict(abridged, included_prop)
        base['floor_boundary'] = [(pt.x, pt.y) for pt in self._floor_geometry.boundary]
        if self._floor_geometry.has_holes:
            base['floor_holes'] = \
                [[(pt.x, pt.y) for pt in hole] for hole in self._floor_geometry.holes]
        base['floor_height'] = self._floor_geometry[0].z
        base['floor_to_ceiling_height'] = self._floor_to_ceiling_height
        base['is_ground_contact'] = self._is_ground_contact
        base['is_top_exposed'] = self._is_top_exposed

        bc_dicts = []
        for bc in self._boundary_conditions:
            if isinstance(bc, Outdoors) and 'energy' in base['properties']:
                bc_dicts.append(bc.to_dict(full=True))
            else:
                bc_dicts.append(bc.to_dict())
        base['boundary_conditions'] = bc_dicts

        if not all((param is None for param in self._window_parameters)):
            base['window_parameters'] = []
            for glz in self._window_parameters:
                val = glz.to_dict() if glz is not None else None
                base['window_parameters'].append(val)

        if not all((param is None for param in self._shading_parameters)):
            base['shading_parameters'] = []
            for shd in self._shading_parameters:
                val = shd.to_dict() if shd is not None else None
                base['shading_parameters'].append(val)

        if self._air_boundaries is not None:
            if not all((not param for param in self._air_boundaries)):
                base['air_boundaries'] = self._air_boundaries

        if self.user_data is not None:
            base['user_data'] = self.user_data

        return base

    @property
    def to(self):
        """Room2D writer object.

        Use this method to access Writer class to write the room2d in other formats.
        """
        return writer

    @staticmethod
    def solve_adjacency(room_2ds, tolerance=0.01):
        """Solve for all adjacencies between a list of input Room2Ds.

        Args:
            room_2ds: A list of Room2Ds for which adjacencies will be solved.
            tolerance: The minimum difference between the coordinate values of two
                faces at which they can be considered adjacent. Default: 0.01,
                suitable for objects in meters.

        Returns:
            A list of tuples with each tuple containing 2 sub-tuples for wall
            segments paired in the process of solving adjacency. Sub-tuples have
            the Room2D as the first item and the index of the adjacent wall as the
            second item. This data can be used to assign custom properties to the
            new adjacent walls (like assigning custom window parameters for
            interior windows, assigning air boundaries, or custom boundary
            conditions).
        """
        adj_info = []
        for i, room_1 in enumerate(room_2ds):
            try:
                for room_2 in room_2ds[i + 1:]:
                    if not Polygon2D.overlapping_bounding_rect(
                            room_1._floor_geometry.boundary_polygon2d,
                            room_2._floor_geometry.boundary_polygon2d, tolerance):
                        continue  # no overlap in bounding rect; adjacency impossible
                    for j, seg_1 in enumerate(room_1.floor_segments_2d):
                        for k, seg_2 in enumerate(room_2.floor_segments_2d):
                            if not isinstance(room_2._boundary_conditions[k], Surface):
                                if seg_1.distance_to_point(seg_2.p1) <= tolerance and \
                                        seg_1.distance_to_point(seg_2.p2) <= tolerance:
                                    # set the boundary conditions of the segments
                                    room_1.set_adjacency(room_2, j, k)
                                    adj_info.append(((room_1, j), (room_2, k)))
                                    break
            except IndexError:
                pass  # we have reached the end of the list of zones
        return adj_info

    @staticmethod
    def intersect_adjacency(room_2ds, tolerance=0.01):
        """Intersect the line segments of an array of Room2Ds to ensure matching walls.

        Note that this method effectively erases all assigned boundary conditions,
        window parameters and shading parameters as the original segments are
        subdivided. As such, it is recommended that this method be used before all
        other steps when creating a Story.

        Also note that this method does not actually set the walls that are next to one
        another to be adjacent. The solve_adjacency method must be used for this after
        runing this method.

        Args:
            room_2ds: A list of Room2Ds for which adjacent segments will be
                intersected.
            tolerance: The minimum difference between the coordinate values of two
                faces at which they can be considered adjacent. Default: 0.01,
                suitable for objects in meters.

        Returns:
            An array of Room2Ds that have been intersected with one another. Note
            that these Room2Ds lack all assigned boundary conditions, window parameters
            and shading parameters of the original Room2Ds. Other properties like
            extension attributes, floor_to_ceiling_height, and top_exposed/ground_contact
            are preserved.
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
            rebuilt_room = Room2D(
                room_2ds[i].identifier, new_geo, room_2ds[i].floor_to_ceiling_height,
                is_ground_contact=room_2ds[i].is_ground_contact,
                is_top_exposed=room_2ds[i].is_top_exposed)
            rebuilt_room._display_name = room_2ds[i].display_name
            rebuilt_room._user_data = None if room_2ds[i].user_data is None else \
                room_2ds[i].user_data.copy()
            rebuilt_room._parent = room_2ds[i]._parent
            rebuilt_room._properties._duplicate_extension_attr(room_2ds[i]._properties)
            intersected_rooms.append(rebuilt_room)
        return tuple(intersected_rooms)

    def _honeybee_plenums(self, hb_room, tolerance=0.01):
        """Get ceiling and/or floor plenums for the Room2D as a Honeybee Room.

        This method will check if there is a gap between the Room2D's ceiling and
        floor, and the top and bottom of it's corresponding Story, respectively.
        If there is a gap along the z axis larger then the specified tolerance,
        it will compute the necessary ceiling and/or floor plenum to fill the gap.

        Args:
            hb_room: A honeybee Room representing the dragonfly Room2D.
            tolerance: The minimum distance in z values to check if the Room ceiling
                and floor is adjacent to the upper and lower floor of the Story,
                respectively. If not adjacent, the corresponding ceiling or floor
                plenum is generated. Default: 0.01, suitable for objects in meters.

        Returns:
            A list of Honeybee Rooms with two items:

                * ceil_plenum -- A honeybee-core Room representing the ceiling
                    plenum. If there isn't enough space between the Story
                    floor_to_floor_height and the Room2D floor_to_ceiling height,
                    this item will be None.

                * floor_plenum -- A honeybee-core Room representing the floor plenum.
                    If there isn't enough space between the Story floor_height and
                    the Room2D floor_height, this item will be None.
        """
        # check to be sure that the room2d has a parent story
        hb_rooms = []
        if not self.has_parent:
            raise AttributeError(
                'Cannot add plenums to the "{}" Room because the parent Story has '
                'not been set. This is required to derive the plenum '
                'height.'.format(self.identifier))

        parent = self.parent
        parent_ceiling = parent.floor_height + parent.floor_to_floor_height
        ceil_plenum_height = parent_ceiling - self.ceiling_height
        floor_plenum_height = self.floor_height - parent.floor_height

        if ceil_plenum_height > tolerance:
            ceil_plenum = self._honeybee_plenum(
                ceil_plenum_height, plenum_type="ceiling")
            # Set the plenum and the rooms to be adjacent to one another
            hb_room[-1].set_adjacency(ceil_plenum[0], tolerance)
            hb_rooms.append(ceil_plenum)

        if floor_plenum_height > tolerance:
            floor_plenum = self._honeybee_plenum(
                floor_plenum_height, plenum_type="floor")
            # Set the plenum and the rooms to be adjacent to one another
            hb_room[0].set_adjacency(floor_plenum[-1], tolerance)
            try:
                hb_room[0].boundary_condition = bcs.adiabatic
            except AttributeError:
                pass
            hb_rooms.append(floor_plenum)

        return hb_rooms

    def _honeybee_plenum(self, plenum_height, plenum_type='ceiling'):
        """Get a ceiling or floor plenum for the Room2D as a Honeybee Room.

        The boundary condition for all plenum faces is adiabatic except for the
        ceiling and floor surfaces between the room, and any outdoor walls.

        Args:
            hb_room: A honeybee Room representing the dragonfly Room2D.
            plenum_height: The height of the plenum Room.
            plenum_type: Text for the type of plenum to be constructed.
                Choose from the following:

                * ceiling
                * floor

        Returns:
            A honeybee Room representing a plenum zone.
        """
        plenum_id = self.identifier + '_{}_plenum'.format(plenum_type)

        # create reference 2d geometry for plenums
        ref_face3d = self.floor_geometry.duplicate()
        if plenum_type == 'ceiling':
            ref_face3d = ref_face3d.move(Vector3D(0, 0, self.floor_to_ceiling_height))
        else:
            ref_face3d = ref_face3d.move(Vector3D(0, 0, -plenum_height))

        # create the honeybee Room
        plenum_hb_room = Room.from_polyface3d(
            plenum_id, Polyface3D.from_offset_face(ref_face3d, plenum_height))

        # get the boundary condition that will be used for interior surfaces
        try:
            interior_bc = bcs.adiabatic
        except AttributeError:  # honeybee_energy is not loaded; no Adiabatic BC
            interior_bc = bcs.outdoors

        # assign wall BCs based on self
        for i, bc in enumerate(self._boundary_conditions):
            if not isinstance(bc, Surface):
                plenum_hb_room[i + 1].boundary_condition = bc
            else:  # assign boundary conditions for the roof and floor
                plenum_hb_room[i + 1].boundary_condition = interior_bc

        if plenum_type == 'ceiling':  # assign ceiling BCs
            if self._is_top_exposed:
                plenum_hb_room[-1].boundary_condition = bcs.outdoors
            else:
                plenum_hb_room[-1].boundary_condition = interior_bc
        else:  # assign floor BCss
            if self._is_ground_contact:
                plenum_hb_room[0].boundary_condition = bcs.ground
            else:
                plenum_hb_room[0].boundary_condition = interior_bc

        return plenum_hb_room

    def _check_wall_assigned_object(self, value, obj_name=''):
        """Check an input that gets assigned to all of the walls of the Room."""
        try:
            value = list(value) if not isinstance(value, list) else value
        except (ValueError, TypeError):
            raise TypeError('Input {} must be a list or a tuple'.format(obj_name))
        assert len(value) == len(self), 'Input {} length must be the ' \
            'same as the number of floor_segments. {} != {}'.format(
                obj_name, len(value), len(self))
        return value

    @staticmethod
    def _flip_wall_assigned_objects(original_geo, bcs, win_pars, shd_pars):
        """Get arrays of wall-assigned parameters that are flipped/reversed.

        This method accounts for the case that a floor geometry has holes in it.
        """
        # go through the boundary and ensure detailed parameters are flipped
        new_bcs = []
        new_win_pars = []
        new_shd_pars = []
        for i, seg in enumerate(original_geo.boundary_segments):
            new_bcs.append(bcs[i])
            win_par = win_pars[i]
            if isinstance(win_par, _AsymmetricBase):
                new_win_pars.append(win_par.flip(seg.length))
            else:
                new_win_pars.append(win_par)
            new_shd_pars.append(shd_pars[i])

        # reverse the lists of wall-assigned objects on the floor boundary
        new_bcs.reverse()
        new_win_pars.reverse()
        new_shd_pars.reverse()

        # add any objects related to the holes
        if original_geo.has_holes:
            bound_len = len(original_geo.boundary)
            new_bcs = new_bcs + bcs[bound_len:]
            new_win_pars = new_win_pars + win_pars[bound_len:]
            new_shd_pars = new_shd_pars + shd_pars[bound_len:]

        # retrun the flipped lists
        return new_bcs, new_win_pars, new_shd_pars

    def _split_walls_along_height(self, hb_room, tolerance):
        """Split adjacent walls to ensure matching surface areas in to_honeybee workflow.

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
                adj_rm = self._parent.room_by_identifier(
                    bc.boundary_condition_objects[-1])
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
                    mid = Face3D.from_extrusion(
                        lseg.move(vec1), Vector3D(0, 0, mid_dist))
                    above = Face3D.from_extrusion(
                        lseg.move(vec2), Vector3D(0, 0, ciel_diff))
                    mid_face = face.duplicate()
                    mid_face._geometry = mid
                    self._reassign_split_windows(mid_face, i, tolerance)
                    below_face = Face('{}_Below'.format(face.identifier), below)
                    above_face = Face('{}_Above'.format(face.identifier), above)
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
                    mid = Face3D.from_extrusion(
                        lseg.move(vec1), Vector3D(0, 0, mid_dist))
                    mid_face = face.duplicate()
                    mid_face._geometry = mid
                    self._reassign_split_windows(mid_face, i, tolerance)
                    below_face = Face('{}_Below'.format(face.identifier), below)
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
                    above = Face3D.from_extrusion(
                        lseg.move(vec1), Vector3D(0, 0, ciel_diff))
                    mid_face = face.duplicate()
                    mid_face._geometry = mid
                    self._reassign_split_windows(mid_face, i, tolerance)
                    above_face = Face('{}_Above'.format(face.identifier), above)
                    try:
                        above_face.boundary_condition = bcs.adiabatic
                    except AttributeError:
                        pass  # honeybee_energy is not loaded
                    new_faces.extend([mid_face, above_face])
        new_faces.append(hb_room[-1])
        return new_faces

    def _reassign_split_windows(self, face, i, tolerance):
        """Re-assign WindowParamters to any base surface that has been split.

        Args:
            face: Honeybee Face to which windows will be re-assigned.
            i: The index of the window_parameters that correspond to the face
            tolerance: The tolerance, which will be used to re-assign windows.
        """
        glz_par = self._window_parameters[i]
        if glz_par is not None:
            face.remove_apertures()
            glz_par.add_window_to_face(face, tolerance)

    def __copy__(self):
        new_r = Room2D(self.identifier, self._floor_geometry,
                       self.floor_to_ceiling_height,
                       self._boundary_conditions[:])  # copy boundary condition list
        new_r._display_name = self.display_name
        new_r._user_data = None if self.user_data is None else self.user_data.copy()
        new_r._parent = self._parent
        new_r._window_parameters = self._window_parameters[:]  # copy window list
        new_r._shading_parameters = self._shading_parameters[:]  # copy shading list
        new_r._air_boundaries = self._air_boundaries[:] \
            if self._air_boundaries is not None else None
        new_r._is_ground_contact = self._is_ground_contact
        new_r._is_top_exposed = self._is_top_exposed
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
