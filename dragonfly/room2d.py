# coding: utf-8
"""Dragonfly Room2D."""
from __future__ import division

import math

from ladybug_geometry.geometry2d import Point2D, Vector2D, Ray2D, LineSegment2D, \
    Polyline2D, Polygon2D
from ladybug_geometry.geometry3d import Point3D, Vector3D, Ray3D, LineSegment3D, \
    Plane, Polyline3D, Face3D, Polyface3D
from ladybug_geometry.intersection2d import closest_point2d_between_line2d
from ladybug_geometry.intersection3d import closest_point3d_on_line3d, \
    closest_point3d_on_line3d_infinite, intersect_line3d_plane_infinite
import ladybug_geometry.boolean as pb
from ladybug_geometry_polyskel.polysplit import perimeter_core_subfaces

from honeybee.typing import float_positive, clean_string, clean_and_id_string
import honeybee.boundarycondition as hbc
from honeybee.boundarycondition import boundary_conditions as bcs
from honeybee.boundarycondition import _BoundaryCondition, Outdoors, Surface, Ground
from honeybee.facetype import Floor, Wall, AirBoundary, RoofCeiling
from honeybee.facetype import face_types as ftyp
from honeybee.door import Door
from honeybee.face import Face
from honeybee.room import Room

from ._base import _BaseGeometry
from .properties import Room2DProperties
import dragonfly.windowparameter as glzpar
from dragonfly.windowparameter import _WindowParameterBase, _AsymmetricBase, \
    SimpleWindowRatio, RectangularWindows, DetailedWindows
import dragonfly.skylightparameter as skypar
from dragonfly.skylightparameter import _SkylightParameterBase, DetailedSkylights, \
    GriddedSkylightArea, GriddedSkylightRatio
import dragonfly.shadingparameter as shdpar
from dragonfly.shadingparameter import _ShadingParameterBase
import dragonfly.writer.room2d as writer


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
        * full_id
        * floor_geometry
        * floor_to_ceiling_height
        * boundary_conditions
        * window_parameters
        * shading_parameters
        * air_boundaries
        * is_ground_contact
        * is_top_exposed
        * skylight_parameters
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
        * is_core
        * is_perimeter
        * min
        * max
        * center
        * user_data
    """
    __slots__ = ('_floor_geometry', '_segment_count', '_floor_to_ceiling_height',
                 '_boundary_conditions', '_window_parameters', '_shading_parameters',
                 '_air_boundaries', '_is_ground_contact', '_is_top_exposed',
                 '_skylight_parameters', '_parent', '_abridged_properties')

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
            self._boundary_conditions = [bc] * len(self)
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
        self._skylight_parameters = None

        self._air_boundaries = None  # will be set if it's ever used
        self._parent = None  # _parent will be set when Room2D is added to a Story
        self._abridged_properties = None  # will be set when originating from abridged
        self._properties = Room2DProperties(self)  # properties for extensions

    @classmethod
    def from_dict(cls, data, tolerance=0, persist_abridged=False):
        """Initialize a Room2D from a dictionary.

        Args:
            data: A dictionary representation of a Room2D object.
            tolerance: The maximum difference between z values at which point vertices
                are considered to be in the same horizontal plane. This is used to check
                that all vertices of the input floor_geometry lie in the same horizontal
                floor plane. Default is 0, which will not perform any check.
            persist_abridged: Set to True when the properties of the Room2D dictionary
                are abridged and you want to ensure that these exact same abridged
                properties persist into the output of Room2D.to_dict(abridged=True).
                It is useful when trying to edit the Room2D independently of a
                Model and there are no plans to edit any extension properties of
                the Room2D. THIS IS AN ADVANCED OPTION. (Default: False).
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
            for i, glz_dict in enumerate(data['window_parameters']):
                if glz_dict is not None:
                    if glz_dict['type'] == 'DetailedWindows':
                        segment = cls.floor_segment_by_index(floor_geometry, i)
                        glz_pars.append(DetailedWindows.from_dict(glz_dict, segment))
                    else:
                        try:
                            glz_class = getattr(glzpar, glz_dict['type'])
                        except AttributeError:
                            raise ValueError(
                                'Window parameter "{}" is not recognized.'.format(
                                    glz_dict['type']))
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
                            'Shading parameter "{}" is not recognized.'.format(
                                shd_dict['type']))
                    shd_pars.append(shd_class.from_dict(shd_dict))
                else:
                    shd_pars.append(None)
        else:
            shd_pars = None

        # get the top and bottom exposure properties
        grnd = data['is_ground_contact'] if 'is_ground_contact' in data else False
        top = data['is_top_exposed'] if 'is_top_exposed' in data else False

        # create the Room2D object
        room = Room2D(data['identifier'], floor_geometry,
                      data['floor_to_ceiling_height'],
                      b_conditions, glz_pars, shd_pars, grnd, top, tolerance)

        # assign any skylight parameters if they are specified
        if 'skylight_parameters' in data and data['skylight_parameters'] is not None:
            try:
                sky_class = getattr(skypar, data['skylight_parameters']['type'])
            except AttributeError:
                raise ValueError(
                    'Skylight parameter "{}" is not recognized.'.format(
                        data['skylight_parameters']['type']))
            room.skylight_parameters = sky_class.from_dict(data['skylight_parameters'])

        # set all of the other optional properties
        if 'air_boundaries' in data and data['air_boundaries'] is not None:
            room.air_boundaries = data['air_boundaries']
        if 'display_name' in data and data['display_name'] is not None:
            room._display_name = data['display_name']
        if 'user_data' in data and data['user_data'] is not None:
            room.user_data = data['user_data']

        if data['properties']['type'] == 'Room2DProperties':
            room.properties._load_extension_attr_from_dict(data['properties'])
        elif persist_abridged and \
                data['properties']['type'] == 'Room2DPropertiesAbridged':
            room._abridged_properties = data['properties']
        return room

    @classmethod
    def from_honeybee(cls, room, tolerance):
        """Initialize a Room2D from a Honeybee Room.

        Note that Dragonfly Room2Ds are abstractions of Honeybee Rooms and there
        will be loss of information if the Honeybee Room is not an extruded floor
        plate or if extension properties are assigned to individual Faces
        or Apertures instead of at the Room level.

        If the Honeybee Room contains no Floor Faces, None will be returned.

        Args:
            room: A Honeybee Room object.
            tolerance: The maximum difference between values at which point vertices
                are considered to be the same.
        """
        # first get the floor_geometry for the Room2D using the horizontal boundary
        try:
            flr_geo = room.horizontal_boundary(match_walls=True, tolerance=tolerance)
        except ValueError as e:  # not a closed volume; maybe using the floors could work
            flr_geos = room.horizontal_floor_boundaries(
                match_walls=True, tolerance=tolerance)
            if len(flr_geos) == 0:  # degenerate room
                raise ValueError(e)
            flr_geos = sorted(flr_geos, key=lambda x: x.area, reverse=True)
            flr_geo = flr_geos[0]  # use the geometry with the largest area
        flr_geo = flr_geo if flr_geo.normal.z >= 0 else flr_geo.flip()

        # match the segments of the floor geometry to walls of the Room
        segs = flr_geo.boundary_segments if flr_geo.holes is None else \
            flr_geo.boundary_segments + \
            tuple(seg for hole in flr_geo.hole_segments for seg in hole)
        boundary_conditions = [bcs.outdoors] * len(segs)
        window_parameters = [None] * len(segs)
        air_bounds = [False] * len(segs)
        for i, seg in enumerate(segs):
            wall_f = cls._segment_wall_face(room, seg, tolerance)
            if wall_f is not None:
                boundary_conditions[i] = wall_f.boundary_condition
                if len(wall_f._apertures) != 0 or len(wall_f._doors) != 0:
                    sf_objs = wall_f._apertures + wall_f._doors
                    w_geos = [sf.geometry for sf in sf_objs]
                    is_drs = [isinstance(sf, Door) for sf in sf_objs]
                    if abs(wall_f.normal.z) <= 0.01:  # vertical wall
                        window_parameters[i] = DetailedWindows.from_face3ds(
                            w_geos, seg, is_drs)
                    else:  # angled wall; scale the Y to covert to vertical
                        w_p = Plane(Vector3D(seg.v.y, -seg.v.x, 0), seg.p, seg.v)
                        w3d = [Face3D([p.project(w_p.n, w_p.o) for p in geo.boundary])
                               for geo in w_geos]
                        window_parameters[i] = DetailedWindows.from_face3ds(
                            w3d, seg, is_drs)
                if isinstance(wall_f.type, AirBoundary):
                    air_bounds[i] = True

        # determine the ceiling height, and top/bottom boundary conditions
        floor_to_ceiling_height = room.geometry.max.z - room.geometry.min.z
        is_ground_contact = all([isinstance(f.boundary_condition, Ground)
                                 for f in room.faces if isinstance(f.type, Floor)])
        is_top_exposed = all([isinstance(f.boundary_condition, Outdoors)
                              for f in room.faces if isinstance(f.type, RoofCeiling)])

        # create the Dragonfly Room2D
        room_2d = cls(
            room.identifier, flr_geo, floor_to_ceiling_height,
            boundary_conditions, window_parameters, None,
            is_ground_contact, is_top_exposed, tolerance)

        # check if there are any skylights to be added
        skylights, are_doors = [], []
        for f in room.faces:
            if isinstance(f.type, RoofCeiling):
                sf_objs = f._apertures + f._doors
                for sf in sf_objs:
                    verts2d = tuple(Point2D(pt.x, pt.y) for pt in sf.geometry.boundary)
                    skylights.append(Polygon2D(verts2d))
                    are_doors.append(isinstance(sf, Door))
        if len(skylights) != 0:
            room_2d.skylight_parameters = DetailedSkylights(skylights, are_doors)

        # add the extra optional attributes
        final_ab = []
        for v, bc in zip(air_bounds, room_2d._boundary_conditions):
            v_f = v if isinstance(bc, Surface) else False
            final_ab.append(v_f)
        room_2d.air_boundaries = final_ab
        room_2d._display_name = room._display_name
        room_2d._user_data = None if room.user_data is None else room.user_data.copy()
        room_2d.properties.from_honeybee(room.properties)
        return room_2d

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
        assert self._floor_to_ceiling_height != 0, 'Room2D floor-to-ceiling height ' \
            'cannot be zero.'

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
    def skylight_parameters(self):
        """Get or set SkylightParameters describing how to generate skylights.
        """
        return self._skylight_parameters

    @skylight_parameters.setter
    def skylight_parameters(self, value):
        if value is not None:
            assert isinstance(value, _SkylightParameterBase), \
                'Expected Skylight Parameters. Got {}'.format(type(value))
        self._skylight_parameters = value

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
    def interior_wall_area(self):
        """Get a the total wall area of the Room without an Outdoors or Ground BC.
        """
        wall_areas = []
        for seg, bc in zip(self.floor_segments, self._boundary_conditions):
            if not isinstance(bc, (Outdoors, Ground)):
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
    def is_core(self):
        """Get a boolean for whether the Room2D is in the core of a story.

        Core Room2Ds have no walls exposed to the outdoors.
        """
        return self.exterior_wall_area == 0

    @property
    def is_perimeter(self):
        """Get a boolean for whether the Room2D is on the perimeter of a story.

        Perimeter Room2Ds have walls exposed to the outdoors.
        """
        return self.exterior_wall_area != 0

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

    @property
    def center(self):
        """Get a Point2D for the center bounding rectangle vertex in the XY plane.

        This is useful in calculations to determine if this Room2D is inside
        other polygons.
        """
        return self._floor_geometry.boundary_polygon2d.center

    def label_point(self, tolerance=0.01):
        """Get a Point3D to label this Room2D in 3D space.

        This point will always lie within the polygon formed by the floor_geometry
        regardless of whether this geometry is concave or has holes.

        Args:
            tolerance: The tolerance to which the pole_of_inaccessibility will
                be computed in the event that the floor_geometry is concave or
                has holes. Note that this does not need to be equal to the Model
                tolerance and should usually be larger than the Model tolerance
                to avoid long calculation times. (Default: 0.01).
        """
        return self.floor_geometry.center if self.floor_geometry.is_convex else \
            self.floor_geometry.pole_of_inaccessibility(tolerance)

    def segment_orientations(self, north_vector=Vector2D(0, 1)):
        """A list of numbers between 0 and 360 for the orientation of the segments.

        0 = North, 90 = East, 180 = South, 270 = West

        Args:
            north_vector: A ladybug_geometry Vector2D for the north direction.
                Default is the Y-axis (0, 1).
        """
        normals = (Vector2D(sg.v.y, -sg.v.x) for sg in self.floor_segments)
        return [math.degrees(north_vector.angle_clockwise(norm)) for norm in normals]

    def overlap_area(self, other_room2d, tolerance=0.01):
        """Get the area of this Room2D that overlaps with another Room2D.

        This is useful for helping identify cases where a given Room2D might be an
        updated version of this Room2D (in the same location within a larger Story)
        and should therefore replace this Room2D. This method first performs a
        bounding rectangle check between the Room2Ds to evaluate whether an overlap
        is possible before computing the percentage, making it efficient to run
        with large groups of Room2Ds.

        Args:
            other_room_2d: Another Room2D object to be checked for overlap with
                this one.
            tolerance: The minimum difference in coordinate values that the
                room vertices must have for them to be considered
                overlapping. (Default: 0.01).
        """
        # first check whether the bounding rectangles around the geometry overlap
        self_face, other_face = self.floor_geometry, other_room2d.floor_geometry
        poly_1, poly_2 = self_face.boundary_polygon2d, other_face.boundary_polygon2d
        if not Polygon2D.overlapping_bounding_rect(poly_1, poly_2, tolerance):
            return 0  # no overlap in bounding rect; gap impossible
        # perform a boolean intersection operation between the two floor Face3Ds
        self._floor_geometry
        ang_tol = math.radians(1)
        new_geos = Face3D.coplanar_intersection(
            self_face, other_face, tolerance, ang_tol)
        if new_geos is None or len(new_geos) == 0:
            return 0  # the Face3Ds did not overlap with one another
        return sum(f.area for f in new_geos)

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

    def to_rectangular_windows(self):
        """Convert all of the windows of the Room2D to the RectangularWindows format."""
        glz_ps = []
        for seg, glz in zip(self.floor_segments, self._window_parameters):
            if glz is not None:
                glz = glz.to_rectangular_windows(seg, self.floor_to_ceiling_height)
            glz_ps.append(glz)
        self._window_parameters = glz_ps

    def to_detailed_windows(self):
        """Convert all of the windows of the Room2D to the DetailedWindows format."""
        glz_ps = []
        for seg, glz in zip(self.floor_segments, self._window_parameters):
            if glz is not None and not isinstance(glz, DetailedWindows):
                glz = glz.to_rectangular_windows(seg, self.floor_to_ceiling_height)
                glz = glz.to_detailed_windows()
            glz_ps.append(glz)
        self._window_parameters = glz_ps

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
        if self._display_name is not None:
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

    def set_adjacency(
            self, other_room_2d, self_seg_index, other_seg_index,
            resolve_window_conflicts=True):
        """Set a segment of this Room2D to be adjacent to another and vice versa.

        Note that, adjacent segments must possess matching WindowParameters in
        order to be valid.

        Args:
            other_room_2d: Another Room2D object to be set adjacent to this one.
            self_seg_index: An integer for the wall segment of this Room2D that
                will be set adjacent to the other_room_2d.
            other_seg_index:An integer for the wall segment of the other_room_2d
                that will be set adjacent to this Room2D.
            resolve_window_conflicts: Boolean to note whether conflicts between
                window parameters of adjacent segments should be resolved during
                adjacency setting or an error should be raised about the mismatch.
                Resolving conflicts will default to the window parameters with the
                larger are and assign them to the other segment. (Default: True).
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
        wp1 = self._window_parameters[self_seg_index]
        wp2 = other_room_2d._window_parameters[other_seg_index]
        if wp1 is not None or wp2 is not None:
            if wp1 != wp2 or isinstance(wp1, _AsymmetricBase):
                if resolve_window_conflicts:
                    ftc1 = self.floor_to_ceiling_height
                    ftc2 = other_room_2d.floor_to_ceiling_height
                    min_ftc = min((ftc1, ftc2))
                    seg1 = self.floor_segments[self_seg_index]
                    a1 = wp1.area_from_segment(seg1, min_ftc) if wp1 is not None else 0
                    seg2 = other_room_2d.floor_segments[other_seg_index]
                    a2 = wp2.area_from_segment(seg2, min_ftc) if wp2 is not None else 0
                    if a1 > a2:
                        other_room_2d._window_parameters[other_seg_index] = \
                            wp1.flip(seg2.length) if isinstance(wp1, _AsymmetricBase) \
                            else wp1
                    else:
                        self._window_parameters[self_seg_index] = wp2.flip(seg1.length) \
                            if isinstance(wp2, _AsymmetricBase) else wp2
                else:
                    if wp1 != wp2:
                        msg = 'Window parameters do not match between adjacent ' \
                            'Rooms "{}" and "{}".'.format(
                                self.identifier, other_room_2d.identifier)
                        raise AssertionError(msg)

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

    def set_window_parameter(self, seg_index, window_parameter=None):
        """Set a single segment of this Room2D to have a certain window parameter.

        Args:
            seg_index: An integer for the wall segment of this Room2D for which
                the window parameter will be set.
            window_parameter: A window parameter object to be assigned to the segment.
                If None, any existing WindowParameters assigned to the segment
                will be removed. (Default: None).
        """
        if window_parameter is not None:
            assert isinstance(window_parameter, _WindowParameterBase), \
                'Expected Window Parameters. Got {}'.format(type(window_parameter))
            accept_bc = (Outdoors, Surface)
            assert isinstance(self._boundary_conditions[seg_index], accept_bc), \
                'Windows cannot be assigned to a wall with {} boundary ' \
                'condition.'.format(self._boundary_conditions[seg_index])
        self._window_parameters[seg_index] = window_parameter

    def offset_skylight_parameters(self, offset_distance=0.05, tolerance=0.01):
        """Offset detailed skylights so all vertices are inside the Room2D.

        Args:
            offset_distance: Distance from the edge of the room that
                the polygons will be offset to. (Default: 0.05, suitable for
                objects in meters).
            tolerance: The maximum difference between point values for them to be
                considered distinct. (Default: 0.01, suitable for objects in meters).
        """
        if isinstance(self._skylight_parameters, DetailedSkylights):
            self._skylight_parameters.offset_polygons_for_face(
                self.floor_geometry, offset_distance, tolerance)

    def reset_adjacency(self):
        """Set all Surface boundary conditions of this Room2D to be Outdoors."""
        for i, bc in enumerate(self._boundary_conditions):
            if isinstance(bc, Surface):
                self._boundary_conditions[i] = bcs.outdoors

    def move(self, moving_vec):
        """Move this Room2D along a vector.

        Args:
            moving_vec: A ladybug_geometry Vector3D with the direction and distance
                to move the room.
        """
        self._floor_geometry = self._floor_geometry.move(moving_vec)
        if isinstance(self._skylight_parameters, DetailedSkylights):
            self._skylight_parameters = self._skylight_parameters.move(moving_vec)
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
        if isinstance(self._skylight_parameters, DetailedSkylights):
            self._skylight_parameters = self._skylight_parameters.rotate(angle, origin)
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
        if isinstance(self._skylight_parameters, DetailedSkylights):
            self._skylight_parameters = self._skylight_parameters.reflect(plane)
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

        # scale the skylight parameters
        if self._skylight_parameters is not None:
            self._skylight_parameters = self._skylight_parameters.scale(factor, origin) \
                if isinstance(self._skylight_parameters, DetailedSkylights) else \
                self._skylight_parameters.scale(factor)

        self.properties.scale(factor, origin)

    def snap_to_grid(self, grid_increment):
        """Snap this Room2D's vertices to the nearest grid node defined by an increment.

        All properties assigned to the Room2D will be preserved and the number of
        vertices will remain constant. This means that this method can often create
        duplicate vertices and it might be desirable to run the remove_duplicate_vertices
        method after running this one.

        Args:
            grid_increment: A positive number for dimension of each grid cell. This
                typically should be equal to the tolerance or larger but should
                not be larger than the smallest detail of the Room2D that you
                wish to resolve.
        """
        # loop through the vertices and snap them
        new_boundary, new_holes = [], None
        for pt in self._floor_geometry.boundary:
            new_x = grid_increment * round(pt.x / grid_increment)
            new_y = grid_increment * round(pt.y / grid_increment)
            new_boundary.append(Point3D(new_x, new_y, pt.z))
        if self._floor_geometry.holes is not None:
            new_holes = []
            for hole in self._floor_geometry.holes:
                new_hole = []
                for pt in hole:
                    new_x = grid_increment * round(pt.x / grid_increment)
                    new_y = grid_increment * round(pt.y / grid_increment)
                    new_hole.append(Point3D(new_x, new_y, pt.z))
                new_holes.append(new_hole)

        # rebuild the new floor geometry and assign it to the Room2D
        self._floor_geometry = Face3D(
            new_boundary, self._floor_geometry.plane, new_holes)

    def snap_to_points(self, points, distance):
        """Snap this Room2D's vertices to a list of points.

        All properties assigned to this Room2D will be preserved and the number of
        vertices will remain constant. This means that this method can often create
        duplicate vertices and it might be desirable to run the remove_duplicate_vertices
        method after running this one.

        Args:
            points: A list of ladybug_geometry Point2Ds to which the Room2D
                vertices will be snapped if they are near.
            distance: The maximum distance between a Room2D vertex and the input
                point where the vertex will be moved to lie on the polyline.
                Vertices beyond this distance will be left as they are.
        """
        # create a 3D version of the points
        if len(points) == 0:
            return
        vertices = []
        for pt in points:
            if isinstance(pt, Point2D):
                vertices.append(Point3D(pt.x, pt.y, self.floor_height))
            else:
                msg = 'Expected point2D. Got {}.'.format(type(pt))
                raise TypeError(msg)

        # get lists of vertices for the Room2D.floor_geometry to be edited
        edit_boundary = self._floor_geometry.boundary
        edit_holes = self._floor_geometry.holes \
            if self._floor_geometry.has_holes else None

        # perform the snapping operation
        new_boundary, new_holes = [], None
        for pt in edit_boundary:
            dists = [pt.distance_to_point(pt_3d) for pt_3d in vertices]
            sort_pt = sorted(zip(dists, vertices), key=lambda pair: pair[0])
            if sort_pt[0][0] <= distance:
                new_boundary.append(sort_pt[0][1])
            else:
                new_boundary.append(pt)
        if edit_holes is not None:
            new_holes = []
            for hole in edit_holes:
                new_hole = []
                for pt in hole:
                    dists = [pt.distance_to_point(pt_3d) for pt_3d in vertices]
                    sort_pt = sorted(zip(dists, vertices), key=lambda pair: pair[0])
                    if sort_pt[0][0] <= distance:
                        new_hole.append(sort_pt[0][1])
                    else:
                        new_hole.append(pt)
                new_holes.append(new_hole)

        # rebuild the new floor geometry and assign it to the Room2D
        self._floor_geometry = Face3D(
            new_boundary, self._floor_geometry.plane, new_holes)

    def snap_to_line_end_points(self, line, distance):
        """Snap this Room2D's vertices to the endpoints of a line segment.

        All properties assigned to this Room2D will be preserved and the number of
        vertices will remain constant. This means that this method can often create
        duplicate vertices and it might be desirable to run the remove_duplicate_vertices
        method after running this one.

        Args:
            line: A ladybug_geometry LineSegment2D to which the Room2D
                vertices will be snapped if they are near the end points.
            distance: The maximum distance between a Room2D vertex and the polyline where
                the vertex will be moved to lie on the polyline. Vertices beyond
                this distance will be left as they are.
        """
        # create a 3D version of the line segment
        if isinstance(line, LineSegment2D):
            line_ray_3d = LineSegment3D(
                Point3D(line.p.x, line.p.y, self.floor_height),
                Vector3D(line.v.x, line.v.y, 0)
            )
        else:
            msg = 'Expected LineSegment2D. Got {}.'.format(type(line))
            raise TypeError(msg)

        # get lists of vertices for the Room2D.floor_geometry to be edited
        edit_boundary = self._floor_geometry.boundary
        edit_holes = self._floor_geometry.holes \
            if self._floor_geometry.has_holes else None

        # perform the snapping operation
        vertices = line_ray_3d.endpoints
        new_boundary, new_holes = [], None
        for pt in edit_boundary:
            dists = [pt.distance_to_point(pt_3d) for pt_3d in vertices]
            sort_pt = sorted(zip(dists, vertices), key=lambda pair: pair[0])
            if sort_pt[0][0] <= distance:
                new_boundary.append(sort_pt[0][1])
            else:
                new_boundary.append(pt)
        if edit_holes is not None:
            new_holes = []
            for hole in edit_holes:
                new_hole = []
                for pt in hole:
                    dists = [pt.distance_to_point(pt_3d) for pt_3d in vertices]
                    sort_pt = sorted(zip(dists, vertices), key=lambda pair: pair[0])
                    if sort_pt[0][0] <= distance:
                        new_hole.append(sort_pt[0][1])
                    else:
                        new_hole.append(pt)
                new_holes.append(new_hole)

        # rebuild the new floor geometry and assign it to the Room2D
        self._floor_geometry = Face3D(
            new_boundary, self._floor_geometry.plane, new_holes)

    def align(self, line_ray, distance):
        """Move any Room2D vertices within a given distance of a line to be on that line.

        This is useful to clean up cases where wall segments have a lot of
        zig zags in them.

        All properties assigned to the Room2D will be preserved and the number of
        vertices will remain constant. This means that this method can often create
        duplicate vertices and it might be desirable to run the remove_duplicate_vertices
        method after running this one.

        Args:
            line_ray: A ladybug_geometry Ray2D or LineSegment2D to which the Room2D
                vertices will be aligned. Ray2Ds will be interpreted as being infinite
                in both directions while LineSegment2Ds will be interpreted as only
                existing between two points.
            distance: The maximum distance between a vertex and the line_ray where
                the vertex will be moved to lie on the line_ray. Vertices beyond
                this distance will be left as they are.
        """
        # create a 3D version of the line_ray for the closest point calculation
        if isinstance(line_ray, Ray2D):
            line_ray_3d = Ray3D(
                Point3D(line_ray.p.x, line_ray.p.y, self.floor_height),
                Vector3D(line_ray.v.x, line_ray.v.y, 0)
            )
            closest_func = closest_point3d_on_line3d_infinite
        elif isinstance(line_ray, LineSegment2D):
            line_ray_3d = LineSegment3D(
                Point3D(line_ray.p.x, line_ray.p.y, self.floor_height),
                Vector3D(line_ray.v.x, line_ray.v.y, 0)
            )
            closest_func = closest_point3d_on_line3d
        else:
            msg = 'Expected Ray2D or LineSegment2D. Got {}.'.format(type(line_ray))
            raise TypeError(msg)

        # loop through the vertices and align them
        new_boundary, new_holes = [], None
        for pt in self._floor_geometry.boundary:
            close_pt = closest_func(pt, line_ray_3d)
            if pt.distance_to_point(close_pt) <= distance:
                new_boundary.append(close_pt)
            else:
                new_boundary.append(pt)
        if self._floor_geometry.holes is not None:
            new_holes = []
            for hole in self._floor_geometry.holes:
                new_hole = []
                for pt in hole:
                    close_pt = closest_func(pt, line_ray_3d)
                    if pt.distance_to_point(close_pt) <= distance:
                        new_hole.append(close_pt)
                    else:
                        new_hole.append(pt)
                new_holes.append(new_hole)

        # rebuild the new floor geometry and assign it to the Room2D
        self._floor_geometry = Face3D(
            new_boundary, self._floor_geometry.plane, new_holes)

    def pull_to_segments(self, line_segments, distance, snap_vertices=True,
                         constrain_edges=False, tolerance=0.01):
        """Pull this Room2D's vertices to several LineSegment2D.

        This includes both an alignment to the line segments as well as an optional
        snapping to the line end points.

        All properties assigned to this Room2D will be preserved.

        The benefit of calling this method as opposed to iterating over the
        segments and calling align (and snap_to_line_end_points) is that this
        method will only align (and snap) to the closest segment across all of
        the input line_segments. This often helps avoid snapping to undesirable
        line segments, particularly when there are two ore more segments that
        are within the distance.

        Args:
            line_segments: A list of ladybug_geometry LineSegment2D to which this
                Room2D's vertices will be pulled.
            distance: The maximum distance between a Room2D vertex and the line_segments
                where the vertex will be moved to lie on the segments. Vertices beyond
                this distance will be left as they are.
            snap_vertices: A boolean to note whether Room2D vertices that are
                close to the segment end points within the distance should be snapped
                to the end point instead of simply being aligned to the nearest
                segment. (Default: True).
            constrain_edges: A boolean to note whether all axes of the edges that
                were not pulled to the Room2D should be preserved. This is
                accomplished by evaluating the changed vertices after all pulling
                operations are performed and identifying stretches of vertices
                that changed. For each stretch of changed vertices, the start and end
                points of this stretch will be moved to the intersection between
                the new pulled room segment and the adjacent original room
                segment whose axis is to be preserved. (Default: False).
            tolerance: The minimum difference between the coordinate values at
                which they are considered co-located. (Default: 0.01,
                suitable for objects in meters).
        """
        # create a 3D version of the relevant line segments
        lines_3d = []
        for line in line_segments:
            if isinstance(line, LineSegment2D):
                line_3d = LineSegment3D(
                    Point3D(line.p.x, line.p.y, self.floor_height),
                    Vector3D(line.v.x, line.v.y, 0)
                )
                lines_3d.append(line_3d)
            else:
                msg = 'Expected LineSegment2D. Got {}.'.format(type(line))
                raise TypeError(msg)
        if len(lines_3d) == 0:
            return

        # get lists of vertices for the Room2D.floor_geometry to be edited
        edit_boundary = self._floor_geometry.boundary
        edit_holes = self._floor_geometry.holes \
            if self._floor_geometry.has_holes else None

        # loop through the Room2D vertices and align them to the segments
        new_boundary = []
        for pt in edit_boundary:
            dists, c_pts = [], []
            for line_ray_3d in lines_3d:
                close_pt = closest_point3d_on_line3d(pt, line_ray_3d)
                c_pts.append(close_pt)
                dists.append(pt.distance_to_point(close_pt))
            sort_pt = sorted(zip(dists, c_pts), key=lambda pair: pair[0])
            if sort_pt[0][0] <= distance:
                new_boundary.append(sort_pt[0][1])
            else:
                new_boundary.append(pt)
        edit_boundary = new_boundary
        if edit_holes is not None:
            new_holes = []
            for hole in edit_holes:
                new_hole = []
                for pt in hole:
                    dists, c_pts = [], []
                    for line_ray_3d in lines_3d:
                        close_pt = closest_point3d_on_line3d(pt, line_ray_3d)
                        c_pts.append(close_pt)
                        dists.append(pt.distance_to_point(close_pt))
                    sort_pt = sorted(zip(dists, c_pts), key=lambda pair: pair[0])
                    if sort_pt[0][0] <= distance:
                        new_hole.append(sort_pt[0][1])
                    else:
                        new_hole.append(pt)
                new_holes.append(new_hole)
            edit_holes = new_holes

        # if snap_vertices was requested, perform an additional operation to snap them
        if snap_vertices:
            vertices = []
            for line in lines_3d:
                vertices.append(line.p1)
                vertices.append(line.p2)
            new_boundary = []
            for pt in edit_boundary:
                dists = [pt.distance_to_point(pt_3d) for pt_3d in vertices]
                sort_pt = sorted(zip(dists, vertices), key=lambda pair: pair[0])
                if sort_pt[0][0] <= distance:
                    new_boundary.append(sort_pt[0][1])
                else:
                    new_boundary.append(pt)
            edit_boundary = new_boundary
            if edit_holes is not None:
                new_holes = []
                for hole in edit_holes:
                    new_hole = []
                    for pt in hole:
                        dists = [pt.distance_to_point(pt_3d) for pt_3d in vertices]
                        sort_pt = sorted(zip(dists, vertices), key=lambda pair: pair[0])
                        if sort_pt[0][0] <= distance:
                            new_hole.append(sort_pt[0][1])
                        else:
                            new_hole.append(pt)
                    new_holes.append(new_hole)
                edit_holes = new_holes

        # rebuild the new floor geometry and assign it to the Room2D
        f_geo = self._floor_geometry
        self._floor_geometry = Face3D(edit_boundary, f_geo.plane, edit_holes)
        # if constrain_edges is true, move the end points of each stretch
        if constrain_edges:
            self._constrain_edges(f_geo, tolerance)

    def pull_to_polyline(self, polyline, distance, snap_vertices=True,
                         constrain_edges=False, tolerance=0.01):
        """Pull this Room2D's vertices to a Polyline2D.

        This includes both an alignment to the polyline's segments as well as an
        optional snapping to the polyline's vertices.

        All properties assigned to this Room2D will be preserved.

        Note that this method can often create duplicate vertices and degenerate
        geometry. So it might be desirable to run the remove_colinear_vertices or the
        remove_degenerate_holes method after running this one.

        Args:
            polyline: A ladybug_geometry Polyline2D to which this Room2D's vertices
                will be pulled.
            distance: The maximum distance between a Room2D vertex and the polyline where
                the vertex will be moved to lie on the polyline. Vertices beyond
                this distance will be left as they are.
            snap_vertices: A boolean to note whether Room2D vertices that are
                close to the polyline vertices within the distance should be snapped
                to the polyline vertex instead of simply being aligned to the nearest
                polyline segment. (Default: True).
            constrain_edges: A boolean to note whether all axes of the edges that
                were not pulled to the Room2D should be preserved. This is
                accomplished by evaluating the changed vertices after all pulling
                operations are performed and identifying stretches of vertices
                that changed. For each stretch of changed vertices, the start and end
                points of this stretch will be moved to the intersection between
                the new pulled room segment and the adjacent original room
                segment whose axis is to be preserved. (Default: False).
            tolerance: The minimum difference between the coordinate values at
                which they are considered co-located. (Default: 0.01,
                suitable for objects in meters).
        """
        # create LineSegment3Ds from the polyline
        line_segs = []
        for seg in polyline.segments:
            pt_3d = Point3D(seg.p.x, seg.p.y, self.floor_height)
            line_ray_3d = LineSegment3D(pt_3d, Vector3D(seg.v.x, seg.v.y, 0))
            line_segs.append(line_ray_3d)
        line_segs.append(line_segs[0].flip())  # ensure last vertex is counted

        # pull this Room2D to the segments
        self._pull_to_poly_segments(line_segs, distance, snap_vertices,
                                    constrain_edges, tolerance)

    def pull_to_polygon(self, polygon, distance, snap_vertices=True,
                        constrain_edges=False, tolerance=0.01):
        """Pull this Room2D's vertices to a Polygon2D.

        This includes both an alignment to the polygon's segments as well as an
        optional snapping to the polygon's vertices.

        All properties assigned to this Room2D will be preserved.

        Note that this method can often create duplicate vertices and degenerate
        geometry. So it might be desirable to run the remove_colinear_vertices or the
        remove_degenerate_holes method after running this one.

        Args:
            polygon: A ladybug_geometry Polygon2D to which this Room2D's vertices
                will be pulled.
            distance: The maximum distance between a Room2D vertex and the polygon where
                the vertex will be moved to lie on the polygon. Vertices beyond
                this distance will be left as they are.
            snap_vertices: A boolean to note whether Room2D vertices that are
                close to the polygon vertices within the distance should be snapped
                to the polygon vertex instead of simply being aligned to the nearest
                polygon segment. (Default: True).
            constrain_edges: A boolean to note whether all axes of the edges that
                were not pulled to the Room2D should be preserved. This is
                accomplished by evaluating the changed vertices after all pulling
                operations are performed and identifying stretches of vertices
                that changed. For each stretch of changed vertices, the start and end
                points of this stretch will be moved to the intersection between
                the new pulled room segment and the adjacent original room
                segment whose axis is to be preserved. (Default: False).
            tolerance: The minimum difference between the coordinate values at
                which they are considered co-located. (Default: 0.01,
                suitable for objects in meters).
        """
        # create LineSegment3Ds from the polygon
        line_segs = []
        for seg in polygon.segments:
            pt_3d = Point3D(seg.p.x, seg.p.y, self.floor_height)
            line_ray_3d = LineSegment3D(pt_3d, Vector3D(seg.v.x, seg.v.y, 0))
            line_segs.append(line_ray_3d)

        # pull this Room2D to the segments
        self._pull_to_poly_segments(line_segs, distance, snap_vertices,
                                    constrain_edges, tolerance)

    def pull_to_room_2d(self, room_2d, distance, coordinate_vertices=True,
                        constrain_edges=False, tolerance=0.01):
        """Pull this Room2D's vertices to another Room2D.

        This includes both an alignment to the other Room2D's segments as well
        as an optional snapping to the Room2D's vertices. Furthermore, if
        coordinate_vertices is True, any vertices of the neighboring input room_2d
        that are within the specified distance but cannot be matched to a vertex
        on this Room2D within the tolerance will be inserted into this Room2D,
        splitting the wall segment in the process.

        All properties assigned to this Room2D will be preserved.

        Note that this method can often create duplicate vertices and degenerate
        geometry. So it might be desirable to run the remove_colinear_vertices or the
        remove_degenerate_holes method after running this one.

        Args:
            room_2d: A Room2D to which this Room2D's vertices will be pulled.
            distance: The maximum distance between a Room2D vertex and the other
                Room2D where the vertex will be moved to lie on the other Room2D.
                Vertices beyond this distance will be left as they are.
            coordinate_vertices: A boolean to note whether Room2D vertices that are
                close to the other Room2D vertices within the distance should be snapped
                to the Room2D vertex instead of simply being aligned to the nearest
                Room2D segment. Additionally, any vertices of the neighboring room_2d
                that are within the specified distance but cannot be matched to a vertex
                on this Room2D within the tolerance will be inserted into this Room2D,
                splitting the wall segment in the process. (Default: True).
            constrain_edges: A boolean to note whether all axes of the edges that
                were not pulled to the Room2D should be preserved. This is
                accomplished by evaluating the changed vertices after all pulling
                operations are performed and identifying stretches of vertices
                that changed. For each stretch of changed vertices, the start and end
                points of this stretch will be moved to the intersection between
                the new pulled room segment and the adjacent original room
                segment whose axis is to be preserved. (Default: False).
            tolerance: The minimum difference between the coordinate values at
                which they are considered co-located. (Default: 0.01,
                suitable for objects in meters).
        """
        # convert the other Room2D to a list of polygons
        original_geo = self.floor_geometry
        f_geo = room_2d.floor_geometry
        other_room_polys = [Polygon2D([Point2D(pt.x, pt.y) for pt in f_geo.boundary])]
        if f_geo.has_holes:
            for hole in f_geo.holes:
                h_poly = Polygon2D([Point2D(pt.x, pt.y) for pt in hole])
                other_room_polys.append(h_poly)
        # pull this Room2D to each of the polygons
        for o_poly in other_room_polys:
            self.pull_to_polygon(o_poly, distance, coordinate_vertices)
        # if coordinate_vertices is True, insert extra vertices
        if coordinate_vertices:
            self.coordinate_room_2d_vertices(room_2d, distance, tolerance)
        # if constrain_edges is true, move the end points of each stretch
        if constrain_edges:
            self._constrain_edges(original_geo, tolerance)

    def _pull_to_poly_segments(self, line_segments, distance, snap_vertices=True,
                               constrain_edges=False, tolerance=0.01):
        """Pull this Room2D's vertices to LineSegment3D originating from a poly-line/gon.

        Args:
            line_segments: A list of ladybug_geometry LineSegment3D with Z-values at
                this Room2D's floor_height to which this Room2D's vertices
                will be pulled.
            distance: The maximum distance between a Room2D vertex and the line_segments
                where the vertex will be moved to lie on the segments. Vertices beyond
                this distance will be left as they are.
            snap_vertices: A boolean to note whether Room2D vertices that are
                close to the segment end points within the distance should be snapped
                to the end point instead of simply being aligned to the nearest
                segment. (Default: True).
            constrain_edges: A boolean to note whether all axes of the edges that
                were not pulled to the Room2D should be preserved. This is
                accomplished by evaluating the changed vertices after all pulling
                operations are performed and identifying stretches of vertices
                that changed. For each stretch of changed vertices, the start and end
                points of this stretch will be moved to the intersection between
                the new pulled room segment and the adjacent original room
                segment whose axis is to be preserved. (Default: False).
            tolerance: The minimum difference between the coordinate values at
                which they are considered co-located. (Default: 0.01,
                suitable for objects in meters).
        """
        # first make sure that there are line segments to be pulled to
        if len(line_segments) == 0:
            return
        # get lists of vertices for the Room2D.floor_geometry to be edited
        edit_boundary = self._floor_geometry.boundary
        edit_holes = self._floor_geometry.holes \
            if self._floor_geometry.has_holes else None

        # loop through the Room2D vertices and align them to the segments
        new_boundary = []
        for pt in edit_boundary:
            dists, c_pts = [], []
            for line_ray_3d in line_segments:
                close_pt = closest_point3d_on_line3d(pt, line_ray_3d)
                c_pts.append(close_pt)
                dists.append(pt.distance_to_point(close_pt))
            sort_pt = sorted(zip(dists, c_pts), key=lambda pair: pair[0])
            if sort_pt[0][0] <= distance:
                new_boundary.append(sort_pt[0][1])
            else:
                new_boundary.append(pt)
        edit_boundary = new_boundary
        if edit_holes is not None:
            new_holes = []
            for hole in edit_holes:
                new_hole = []
                for pt in hole:
                    dists, c_pts = [], []
                    for line_ray_3d in line_segments:
                        close_pt = closest_point3d_on_line3d(pt, line_ray_3d)
                        c_pts.append(close_pt)
                        dists.append(pt.distance_to_point(close_pt))
                    sort_pt = sorted(zip(dists, c_pts), key=lambda pair: pair[0])
                    if sort_pt[0][0] <= distance:
                        new_hole.append(sort_pt[0][1])
                    else:
                        new_hole.append(pt)
                new_holes.append(new_hole)
            edit_holes = new_holes

        # if snap_vertices was requested, perform an additional operation to snap them
        if snap_vertices:
            vertices = [line.p for line in line_segments]
            new_boundary = []
            for pt in edit_boundary:
                dists = [pt.distance_to_point(pt_3d) for pt_3d in vertices]
                sort_pt = sorted(zip(dists, vertices), key=lambda pair: pair[0])
                if sort_pt[0][0] <= distance:
                    new_boundary.append(sort_pt[0][1])
                else:
                    new_boundary.append(pt)
            edit_boundary = new_boundary
            if edit_holes is not None:
                new_holes = []
                for hole in edit_holes:
                    new_hole = []
                    for pt in hole:
                        dists = [pt.distance_to_point(pt_3d) for pt_3d in vertices]
                        sort_pt = sorted(zip(dists, vertices), key=lambda pair: pair[0])
                        if sort_pt[0][0] <= distance:
                            new_hole.append(sort_pt[0][1])
                        else:
                            new_hole.append(pt)
                    new_holes.append(new_hole)
                edit_holes = new_holes

        # rebuild the new floor geometry and assign it to the Room2D
        f_geo = self._floor_geometry
        self._floor_geometry = Face3D(edit_boundary, f_geo.plane, edit_holes)
        # if constrain_edges is true, move the end points of each stretch
        if constrain_edges:
            self._constrain_edges(f_geo, tolerance)

    def _constrain_edges(self, original_floor_geo, tolerance):
        """Move vertices of this Room2D to preserve original edges."""
        # get all of the vertices and segments needed for the operation
        new_verts = self._floor_geometry.boundary
        old_verts = original_floor_geo.boundary
        new_segs = self._floor_geometry.boundary_polygon2d.segments
        old_segs = original_floor_geo.boundary_polygon2d.segments

        # loop through the vertices and figure out which ones have changed
        pts_moved, any_moved = [], False
        for pt in new_verts:
            for o_pt in old_verts:
                if pt.is_equivalent(o_pt, tolerance):
                    pts_moved.append(False)
                    break
            else:
                pts_moved.append(True)
                any_moved = True
        if not any_moved:
            return

        # set a maximum distance for which constrained points can move
        o_geo = original_floor_geo
        max_dist = max((o_geo.max.x - o_geo.min.x, o_geo.max.y - o_geo.min.y))
        max_d = max_dist * 10

        # identify the start and end points of each stretch and move them
        edit_boundary = []
        last_vert_i = len(new_verts) - 1
        for i, (pt, moved) in enumerate(zip(new_verts, pts_moved)):
            if moved:
                prev_i = i - 1
                next_i = i + 1 if i != last_vert_i else 0
                if pts_moved[prev_i] and pts_moved[next_i]:  # middle of a stretch
                    edit_boundary.append(pt)
                elif not pts_moved[prev_i] and not pts_moved[next_i]:  # lone moved point
                    edit_boundary.append(pt)
                elif pts_moved[prev_i]:  # the end of a stretch
                    prev_seg, next_new_seg = new_segs[prev_i], new_segs[i]
                    for o_seg in old_segs:
                        if o_seg.p2.is_equivalent(next_new_seg.p2, tolerance):
                            next_seg = o_seg
                            break
                    else:  # failed to find the original segment
                        edit_boundary.append(pt)
                        continue
                    ray_1 = Ray2D(prev_seg.p1, prev_seg.v)
                    ray_2 = Ray2D(next_seg.p2, -next_seg.v)
                    int_pt = ray_1.intersect_line_ray(ray_2)
                    if int_pt is None or int_pt.distance_to_point(next_seg.p1) > max_d:
                        edit_boundary.append(pt)
                    else:
                        edit_boundary.append(Point3D(int_pt.x, int_pt.y, pt.z))
                else:  # the beginning of a stretch
                    prev_new_seg, next_seg = new_segs[prev_i], new_segs[i]
                    for o_seg in old_segs:
                        if o_seg.p1.is_equivalent(prev_new_seg.p1, tolerance):
                            prev_seg = o_seg
                            break
                    else:  # failed to find the original segment
                        edit_boundary.append(pt)
                        continue
                    ray_1 = Ray2D(prev_seg.p1, prev_seg.v)
                    ray_2 = Ray2D(next_seg.p2, -next_seg.v)
                    int_pt = ray_1.intersect_line_ray(ray_2)
                    if int_pt is None or int_pt.distance_to_point(next_seg.p1) > max_d:
                        edit_boundary.append(pt)
                    else:
                        edit_boundary.append(Point3D(int_pt.x, int_pt.y, pt.z))
            else:
                edit_boundary.append(pt)

        # rebuild the floor_geometry of this room and add back any holes
        self._floor_geometry = Face3D(
            edit_boundary, self._floor_geometry.plane, self._floor_geometry.holes)

    def coordinate_room_2d_vertices(self, room_2d, distance, tolerance=0.01):
        """Insert vertices to this Room2D to coordinate this Room2D with another Room2D.

        This is sometimes a useful operation to run after using the pull_to_room_2d
        method in order to address the case that the Room2D to which this one was
        pulled has more vertices along the adjacency boundary than this Room2D.
        In this case, the adjacency between the two Room2Ds will not be clean and
        extra vertices must be inserted into this Room2D so that geometry matches
        along the room adjacency.

        Any vertices of the neighboring input room_2d that are within the specified
        distance but cannot be matched to a vertex on this Room2D within the tolerance
        will be inserted into this Room2D, splitting the wall segment in the process.

        Args:
            room_2d: A Room2D with which the vertices of this Room2D will be coordinated.
            distance: The maximum distance between a Room2D vertex and the other
                Room2D where the vertex will be moved to lie on the other Room2D.
                Vertices beyond this distance will be left as they are.
            tolerance: The minimum difference between the coordinate values at
                which they are considered co-located. (Default: 0.01,
                suitable for objects in meters).
        """
        # determine all of the vertices of the other Room2D that should be inserted
        self_segs = list(self.floor_segments_2d)
        self_pts_2d = [seg.p for seg in self_segs]
        other_pts_2d = [seg.p for seg in room_2d.floor_segments_2d]
        insert_pts = []
        for o_pt in other_pts_2d:
            possible_insert = False
            for i, seg in enumerate(self_segs):
                if seg.distance_to_point(o_pt) < distance:
                    possible_insert = True
                    break
            if possible_insert:
                for s_pt in self_pts_2d:
                    if s_pt.distance_to_point(o_pt) <= tolerance:
                        break
                else:
                    insert_pts.append((i, o_pt))

        # loop through the segments and split them if insertion points were found
        if len(insert_pts) == 0:
            return
        sort_int_pts = sorted(insert_pts, key=lambda x: x[0], reverse=True)
        edit_code = ['K'] * len(self_segs)
        for ins_ind, pt in sort_int_pts:
            split_seg = self_segs[ins_ind]
            new_seg1 = LineSegment2D.from_end_points(split_seg.p1, pt)
            new_seg2 = LineSegment2D.from_end_points(pt, split_seg.p2)
            self_segs[ins_ind] = new_seg2
            self_segs.insert(ins_ind, new_seg1)
            edit_code.insert(ins_ind, 'A')

        # create a new floor_geometry Face3D and update the geometry with the edit code
        z_val = self.floor_geometry.boundary[0].z
        if not self.floor_geometry.has_holes:
            pts = [Point3D(seg.p.x, seg.p.y, z_val) for seg in self_segs]
            new_geo = Face3D(pts, self.floor_geometry.plane)
        else:
            joined_segs = Polyline2D.join_segments(self_segs, tolerance)
            new_loops = []
            for p_line in joined_segs:
                pts = [Point3D(pt.x, pt.y, z_val) for pt in p_line.vertices[:-1]]
                new_loops.append(pts)
            new_geo = Face3D(new_loops[0], self.floor_geometry.plane, new_loops[1:])
        self.update_floor_geometry(new_geo, edit_code, tolerance)

    def remove_duplicate_vertices(self, tolerance=0.01):
        """Remove duplicate vertices from this Room2D.

        All properties assigned to the Room2D will be preserved.

        Args:
            tolerance: The minimum distance between a vertex and the line it lies
                upon at which point the vertex is considered colinear. (Default: 0.01,
                suitable for objects in meters).

        Returns:
            A list of integers for the indices of segments that have been removed.
        """
        # loop through the vertices and remove any duplicates
        exist_abs = self.air_boundaries
        new_bound, new_bcs, new_win, new_shd, new_abs = [], [], [], [], []
        b_pts = self.floor_geometry.boundary
        b_pts = b_pts[1:] + (b_pts[0],)
        removed_indices = []
        for i, vert in enumerate(b_pts):
            if not vert.is_equivalent(b_pts[i - 1], tolerance):
                new_bound.append(b_pts[i - 1])
                new_bcs.append(self._boundary_conditions[i])
                new_win.append(self._window_parameters[i])
                new_shd.append(self._shading_parameters[i])
                new_abs.append(exist_abs[i])
            else:
                removed_indices.append(i)
        new_holes = None
        if self.floor_geometry.has_holes:
            new_holes, seg_count = [], len(b_pts)
            for hole in self.floor_geometry.holes:
                new_h_pts = []
                h_pts = hole[1:] + (hole[0],)
                for i, vert in enumerate(h_pts):
                    if not vert.is_equivalent(h_pts[i - 1], tolerance):
                        new_h_pts.append(h_pts[i - 1])
                        new_bcs.append(self._boundary_conditions[seg_count + i])
                        new_win.append(self._window_parameters[seg_count + i])
                        new_shd.append(self._shading_parameters[seg_count + i])
                        new_abs.append(exist_abs[i])
                    else:
                        removed_indices.append(i)
                new_holes.append(new_h_pts)
                seg_count += len(h_pts)

        # assign the geometry and properties
        try:
            self._floor_geometry = Face3D(
                new_bound, self.floor_geometry.plane, new_holes)
        except AssertionError as e:  # usually a sliver face of some kind
            raise ValueError(
                'Room2D "{}" is degenerate with dimensions less than the '
                'tolerance.\n{}'.format(self.display_name, e))
        self._segment_count = len(new_bcs)
        self._boundary_conditions = new_bcs
        self._window_parameters = new_win
        self._shading_parameters = new_shd
        self._air_boundaries = new_abs
        return removed_indices

    def remove_degenerate_holes(self, tolerance=0.01):
        """Remove any holes in this Room2D with an area that evaluates to zero.

        All properties assigned to the Room2D will be preserved.

        Args:
            tolerance: The minimum difference between the coordinate values at
                which they are considered co-located. (Default: 0.01,
                suitable for objects in meters).
        """
        if self.floor_geometry.has_holes:  # first identify any zero-area holes
            holes_to_remove = []
            for i, hole in enumerate(self.floor_geometry.holes):
                tf = Face3D(hole, self.floor_geometry.plane)
                max_dim = max((tf.max.x - tf.min.x, tf.max.y - tf.min.y))
                if tf.area < max_dim * tolerance:
                    holes_to_remove.append(i)
            # if zero-area holes were found, rebuild the Room2D
            if len(holes_to_remove) > 0:
                self._remove_holes(holes_to_remove)

    def remove_small_holes(self, area_threshold):
        """Remove any holes in this Room2D that are below a certain area threshold.

        All properties assigned to the Room2D will be preserved.

        Args:
            area_threshold: A number for the area below which holes will be removed.
        """
        if self.floor_geometry.has_holes:  # first identify any holes to remove
            holes_to_remove = []
            for i, hole in enumerate(self.floor_geometry.holes):
                tf = Face3D(hole, self.floor_geometry.plane)
                if tf.area < area_threshold:
                    holes_to_remove.append(i)
            # if removable holes were found, rebuild the Room2D
            if len(holes_to_remove) > 0:
                self._remove_holes(holes_to_remove)

    def _remove_holes(self, holes_to_remove):
        """Remove holes in the Room2D given the indices of the holes.

        Args:
            holes_to_remove: A list of integers for the indices of holes to be removed.
        """
        # first collect the properties of the boundary
        exist_abs = self.air_boundaries
        new_bcs, new_win, new_shd, new_abs = [], [], [], []
        seg_count = len(self.floor_geometry.boundary)
        for i in range(seg_count):
            new_bcs.append(self._boundary_conditions[i])
            new_win.append(self._window_parameters[i])
            new_shd.append(self._shading_parameters[i])
            new_abs.append(exist_abs[i])
        # collect the properties of the new holes
        new_holes = []
        for hi, hole in enumerate(self.floor_geometry.holes):
            if hi not in holes_to_remove:
                for i, vert in enumerate(hole):
                    new_bcs.append(self._boundary_conditions[seg_count + i])
                    new_win.append(self._window_parameters[seg_count + i])
                    new_shd.append(self._shading_parameters[seg_count + i])
                    new_abs.append(exist_abs[i])
                new_holes.append(hole)
            seg_count += len(hole)
        # reset the properties of the Room2D
        self._floor_geometry = Face3D(
            self.floor_geometry.boundary, self.floor_geometry.plane, new_holes)
        self._segment_count = len(new_bcs)
        self._boundary_conditions = new_bcs
        self._window_parameters = new_win
        self._shading_parameters = new_shd
        self._air_boundaries = new_abs

    def update_floor_geometry(self, new_floor_geometry, edit_code, tolerance=0.01):
        """Change the floor_geometry of the Room2D with segment-altering specifications.

        This method is intended to be used when the floor geometry has been edited
        by some external means and this Room2D should be updated for coordination.

        The method tries to infer whether an removed floor segment means that an
        original segment has been merged into another or removed completely using
        the colinearity of the original segments. A removed segment that is colinear
        with its neighbor will be merged into it while a removed segment that was
        not colinear will simply be deleted. Similarly, the method will infer if
        an added segment indicates a split in an original segment using colinearity.
        When the result in the new_floor_geometry is two colinear segments,
        properties of the original segment will be split across the new segments.
        Otherwise the new segment will receive default properties.

        Args:
            new_floor_geometry: A Face3D for the new floor_geometry of this Room2D.
                Note that this method expects the plane of this Face3D to match
                the original floor_geometry Face3D and for the counter-clockwise
                vertex ordering of the segments to be the same as the original
                floor geometry (though segments can obviously be added or removed).
            edit_code: A text string that indicates the operations that were
                performed on the original floor_geometry segments to yield the
                new_floor_geometry. The following letters are used in this code
                to indicate the following:

                * K = a segment that has been kept (possibly moved but not removed)
                * X = a segment that has been removed
                * A = a segment that has been added

                For example, KXKAKKA means that the first segment was kept, the
                next removed, the next kept, the next added, followed by two kept
                segments and ending in an added segment.
            tolerance: The minimum difference between the coordinate values at
                which they are considered co-located, used to determine
                colinearity. Default: 0.01, suitable for objects in meters.
        """
        # process the new floor geometry so that it abides by Room2D rules
        if new_floor_geometry.normal.z <= 0:  # ensure upward-facing Face3D
            new_floor_geometry = new_floor_geometry.flip()
        o_pl = Plane(Vector3D(0, 0, 1), Point3D(0, 0, new_floor_geometry.plane.o.z))
        new_floor_geometry = Face3D(new_floor_geometry.boundary, o_pl,
                                    new_floor_geometry.holes)

        # get the original and the new floor segments
        orig_segs = self.floor_segments
        new_segs = new_floor_geometry.boundary_segments if new_floor_geometry.holes is \
            None else new_floor_geometry.boundary_segments + \
            tuple(seg for hole in new_floor_geometry.hole_segments for seg in hole)

        # figure out the new properties based on the edit code
        new_bcs, new_win, new_shd = [], [], []
        last_o_seg = orig_segs[-1]
        orig_i, new_i = 0, 0
        for edit_val in edit_code:
            if edit_val == 'K':
                new_bcs.append(self._boundary_conditions[orig_i])
                new_win.append(self._window_parameters[orig_i])
                new_shd.append(self._shading_parameters[orig_i])
                last_o_seg = orig_segs[orig_i]
                orig_i += 1
                new_i += 1
            elif edit_val == 'X':
                # determine if the removed segment is colinear
                del_seg = orig_segs[orig_i]
                full_line = LineSegment3D.from_end_points(last_o_seg.p1, del_seg.p2)
                if full_line.distance_to_point(del_seg.p1) <= tolerance:  # colinear!
                    if len(new_bcs) != 0:
                        # TODO: figure out a strategy to merge first to end of the list
                        new_bcs[-1] = bcs.outdoors
                        new_win[-1] = DetailedWindows.merge(
                            (new_win[-1], self._window_parameters[orig_i]),
                            (last_o_seg, del_seg), self.floor_to_ceiling_height)
                    last_o_seg = full_line
                orig_i += 1
            elif edit_val == 'A':
                # determine if the added segment is colinear and within the original
                add_seg = new_segs[new_i]
                if last_o_seg.distance_to_point(add_seg.p1) <= tolerance and \
                        last_o_seg.distance_to_point(add_seg.p2) <= tolerance:
                    # colinear!
                    orig_i = -1 if orig_i >= len(self._boundary_conditions) - 1 \
                        else orig_i
                    new_bcs.append(self._boundary_conditions[orig_i])
                    if len(new_win) != 0 and new_win[-1] is not None:
                        # TODO: figure out a strategy to split the end of the list
                        p_lin = LineSegment3D.from_end_points(last_o_seg.p1, add_seg.p1)
                        a_lin = LineSegment3D.from_end_points(add_seg.p1, last_o_seg.p2)
                        w_to_spl = new_win.pop(-1)
                        new_win.extend(w_to_spl.split((p_lin, a_lin), tolerance))
                        last_o_seg = a_lin
                    else:
                        new_win.append(None)
                    new_shd.append(self._shading_parameters[orig_i])
                else:  # not colinear; use default properties
                    new_bcs.append(bcs.outdoors)
                    new_win.append(None)
                    new_shd.append(None)
                new_i += 1

        # assign the updated properties to this Room2D
        self._floor_geometry = new_floor_geometry
        self._segment_count = len(new_segs)
        assert self._segment_count == len(new_bcs), 'The operations in the edit_code ' \
            'denote a geometry with {} segments but the new_floor_geometry has {} ' \
            'segments.'.format(len(new_bcs), self._segment_count)
        self._boundary_conditions = new_bcs
        self._window_parameters = new_win
        self._shading_parameters = new_shd
        self._air_boundaries = None  # reset to avoid any conflicts

    def remove_colinear_vertices(self, tolerance=0.01, preserve_wall_props=True):
        """Get a version of this Room2D without colinear or duplicate vertices.

        Args:
            tolerance: The minimum distance between a vertex and the line it lies
                upon at which point the vertex is considered colinear. Default: 0.01,
                suitable for objects in meters.
            preserve_wall_props: Boolean to note whether existing window parameters
                and Ground boundary conditions should be preserved as vertices are
                removed. If False, all boundary conditions are replaced with Outdoors,
                all window parameters are erased, and this method will execute quickly.
                If True, an attempt will be made to merge window parameters together
                across colinear segments, translating simple window parameters to
                rectangular ones if necessary. Also, existing Ground boundary
                conditions will be kept. (Default: True).

        Returns:
            A new Room2D derived from this one with its colinear vertices removed.
        """
        if not preserve_wall_props:
            try:  # remove colinear vertices from the Room2D
                new_geo = self.floor_geometry.remove_colinear_vertices(tolerance)
            except AssertionError as e:  # usually a sliver face of some kind
                raise ValueError(
                    'Room2D "{}" is degenerate with dimensions less than the '
                    'tolerance.\n{}'.format(self.display_name, e))
            rebuilt_room = Room2D(
                self.identifier, new_geo, self.floor_to_ceiling_height,
                is_ground_contact=self.is_ground_contact,
                is_top_exposed=self.is_top_exposed)
        else:
            ftc_height = self.floor_to_ceiling_height
            if not self.floor_geometry.has_holes:  # only need to evaluate one list
                pts_3d = self.floor_geometry.vertices
                pts_2d = self.floor_geometry.polygon2d
                segs_2d = pts_2d.segments
                bound_cds = self.boundary_conditions
                win_pars = self.window_parameters
                bound_verts, new_bcs, new_w_par = self._remove_colinear_props(
                    pts_3d, pts_2d, segs_2d, bound_cds, win_pars, ftc_height, tolerance)
                holes = None
            else:
                pts_3d = self.floor_geometry.boundary
                pts_2d = self.floor_geometry.boundary_polygon2d
                segs_2d = pts_2d.segments
                st_i = len(pts_3d)
                bound_cds = self.boundary_conditions[:st_i]
                win_pars = self.window_parameters[:st_i]
                bound_verts, new_bcs, new_w_par = self._remove_colinear_props(
                    pts_3d, pts_2d, segs_2d, bound_cds, win_pars, ftc_height, tolerance)
                holes = []
                for i, pts_3d in enumerate(self.floor_geometry.holes):
                    pts_2d = self.floor_geometry.hole_polygon2d[i]
                    segs_2d = pts_2d.segments
                    bound_cds = self.boundary_conditions[st_i:st_i + len(pts_3d)]
                    win_pars = self.window_parameters[st_i:st_i + len(pts_3d)]
                    st_i += len(pts_3d)
                    h_verts, h_bcs, h_w_par = self._remove_colinear_props(
                        pts_3d, pts_2d, segs_2d, bound_cds, win_pars,
                        ftc_height, tolerance)
                    holes.append(h_verts)
                    new_bcs.extend(h_bcs)
                    new_w_par.extend(h_w_par)

            # create the new Room2D
            new_geo = Face3D(bound_verts, holes=holes)
            rebuilt_room = Room2D(
                self.identifier, new_geo, self.floor_to_ceiling_height,
                boundary_conditions=new_bcs, window_parameters=new_w_par,
                is_ground_contact=self.is_ground_contact,
                is_top_exposed=self.is_top_exposed)

        # assign overall properties to the rebuilt room
        rebuilt_room._skylight_parameters = self._skylight_parameters
        rebuilt_room._display_name = self._display_name
        rebuilt_room._user_data = self._user_data
        rebuilt_room._parent = self._parent
        rebuilt_room._abridged_properties = self._abridged_properties
        rebuilt_room._properties._duplicate_extension_attr(self._properties)
        return rebuilt_room

    def remove_short_segments(self, distance, angle_tolerance=1.0):
        """Get a version of this Room2D with consecutive short segments removed.

        To patch over the segments, an attempt will first be made to find the
        intersection of the two neighboring segments. If these two lines are parallel,
        they will simply be connected with a segment.

        Properties assigned to the Room2D will be preserved for the segments that
        are not removed.

        Args:
            distance: The maximum length of a segment below which the segment
                will be considered for removal.
            angle_tolerance: The max angle difference in degrees that vertices
                are allowed to differ from one another in order to consider them
                colinear. (Default: 1).
        """
        # first check if there are contiguous short segments to be removed
        segs = [self._floor_geometry.boundary_segments]
        if self._floor_geometry.has_holes:
            for hole in self._floor_geometry.hole_segments:
                segs.append(hole)
        sh_seg_i = [[i for i, s in enumerate(sg) if s.length <= distance] for sg in segs]
        if len(segs[0]) - len(sh_seg_i[0]) < 3:
            return None  # large distance means the whole Face becomes removed
        if all(len(s) <= 1 for s in sh_seg_i):
            return self  # no short segments to remove
        del_seg_i = []
        for sh_seg in sh_seg_i:
            del_seg = set()
            for i, seg_i in enumerate(sh_seg):
                test_val = seg_i - sh_seg[i - 1]
                if test_val == 1 or (seg_i == 0 and test_val < 0):
                    del_seg.add(sh_seg[i - 1])
                    del_seg.add(seg_i)
            if 0 in sh_seg and len(sh_seg) - 1 in sh_seg:
                del_seg.add(0)
                del_seg.add(len(sh_seg) - 1)
            del_seg_i.append(sorted(list(del_seg)))
        if all(len(s) == 0 for s in del_seg_i):
            return self  # there are short segments but they're not contiguous

        # contiguous short segments found
        # collect the vertices and indices of properties to be removed
        a_tol = math.radians(angle_tolerance)
        prev_i, final_pts, del_prop_i = 0, [], []
        for p_segs, del_i in zip(segs, del_seg_i):
            if len(del_i) != 0:
                # set up variables to handle getting the last vertex to connect to
                new_points, in_del, post_del = [], False, False
                if 0 in del_i and len(p_segs) - 1 in del_i:
                    last_i, in_del = -1, True
                    try:
                        while del_i[last_i] - del_i[last_i - 1] == 1:
                            last_i -= 1
                    except IndexError:  # entire hole to be removed
                        for i in range(len(p_segs)):
                            del_prop_i.append(prev_i + i)
                        p_segs = []
                # loop through the segments and delete the short ones
                for i, lin in enumerate(p_segs):
                    if i in del_i:
                        if not in_del:
                            last_i = i
                        in_del = True
                        del_prop_i.append(prev_i + i)
                        rel_i = i + 1 if i + 1 != len(p_segs) else 0
                        if rel_i not in del_i:  # we are at the end of the deletion
                            # see if we can repair the hole by extending segments
                            l3a, l3b = p_segs[last_i - 1], p_segs[rel_i]
                            l2a = Ray2D(Point2D(l3a.p.x, l3a.p.y),
                                        Vector2D(l3a.v.x, l3a.v.y))
                            l2b = Ray2D(Point2D(l3b.p.x, l3b.p.y),
                                        Vector2D(l3b.v.x, l3b.v.y))
                            v_ang = l2a.v.angle(l2b.v)
                            if v_ang <= a_tol or v_ang >= math.pi - a_tol:  # parallel
                                new_points.append(p_segs[last_i].p)
                                del_prop_i.pop(-1)  # put back the last property
                            else:  # extend lines to the intersection
                                int_pt = self._intersect_line2d_infinite(l2a, l2b)
                                int_pt3 = Point3D(int_pt.x, int_pt.y, self.floor_height)
                                new_points.append(int_pt3)
                                post_del = True
                            in_del = False
                    else:
                        if not post_del:
                            new_points.append(lin.p)
                        post_del = False
                if post_del:
                    new_points.pop(0)  # put back the last property
                if len(new_points) != 0:
                    final_pts.append(new_points)
            else:  # no short segments to remove on this hole or boundary
                final_pts.append([lin.p for lin in p_segs])
            prev_i += len(p_segs)

        # create the geometry and convert properties for the new segments
        holes = None if len(final_pts) == 1 else final_pts[1:]
        new_geo = Face3D(final_pts[0], self.floor_geometry.plane, holes)
        new_bcs = self._boundary_conditions[:]
        new_win = self._window_parameters[:]
        new_shd = self._shading_parameters[:]
        new_abs = list(self.air_boundaries)
        all_props = (new_bcs, new_win, new_shd, new_abs)
        for prop_list in all_props:
            for di in reversed(del_prop_i):
                prop_list.pop(di)

        # create the final rebuilt Room2D and return it
        rebuilt_room = Room2D(
            self.identifier, new_geo, self.floor_to_ceiling_height, new_bcs, new_win,
            new_shd, self.is_ground_contact, self.is_top_exposed)
        rebuilt_room._air_boundaries = new_abs
        rebuilt_room._skylight_parameters = self._skylight_parameters
        rebuilt_room._display_name = self._display_name
        rebuilt_room._user_data = self._user_data
        rebuilt_room._parent = self._parent
        rebuilt_room._abridged_properties = self._abridged_properties
        rebuilt_room._properties._duplicate_extension_attr(self._properties)
        return rebuilt_room

    def subtract_room_2ds(self, room_2ds, tolerance=0.01):
        """Get (a) version(s) of this Room2D with other Room2Ds subtracted from it.

        This is useful for resolving overlaps between Room2Ds of the same Story.

        Args:
            room_2d: A Room2D that will be subtracted from this Room2D.
            tolerance: The maximum difference between point values for them to be
                considered distinct from one another. (Default: 0.01; suitable
                for objects in Meters).

        Returns:
            A list of Room2D for the result of splitting this Room2D with the
            input line. Will be a list with only the current Room2D if the line
            does not split it into two or more pieces.
        """
        # first check that the two geometries have the same Z coordinate
        self_face = self.floor_geometry
        z_v = self_face[0].z
        other_faces = []
        for room_2d in room_2ds:
            face2 = room_2d.floor_geometry
            if abs(self_face[0].z - face2[0].z) > tolerance:
                new_bound = [Point3D(pt.x, pt.y, z_v) for pt in face2.boundary]
                new_orig = Point3D(face2[0].x, face2[0].y, z_v)
                new_plane = Plane(n=face2.plane.n, o=new_orig)
                new_holes = [[Point3D(p.x, p.y, z_v) for p in h] for h in face2.holes] \
                    if face2.has_holes else None
                face2 = Face3D(new_bound, new_plane, new_holes)
            other_faces.append(face2)

        # subtract the other Room2Ds from this one
        ang_tol = math.radians(1)
        new_geos = self_face.coplanar_difference(other_faces, tolerance, ang_tol)
        if len(new_geos) == 1 and new_geos[0] is self_face:
            return [self]  # the Face3D did not overlap with one another
        new_geos.sort(key=lambda x: x.area, reverse=True)

        # create the final rebuilt Room2Ds and return them
        new_rooms = []
        for i, new_geo in enumerate(new_geos):
            rm_id = self.identifier if i == 0 else '{}{}'.format(self.identifier, i)
            rebuilt_room = Room2D(
                rm_id, new_geo, self.floor_to_ceiling_height,
                is_ground_contact=self.is_ground_contact,
                is_top_exposed=self.is_top_exposed)
            self._match_and_transfer_wall_props(rebuilt_room, tolerance)
            if i == 0:
                rebuilt_room._skylight_parameters = self._skylight_parameters
            rebuilt_room._display_name = self._display_name
            rebuilt_room._user_data = self._user_data
            rebuilt_room._parent = self._parent
            rebuilt_room._abridged_properties = self._abridged_properties
            rebuilt_room._properties._duplicate_extension_attr(self._properties)
            new_rooms.append(rebuilt_room)
        return new_rooms

    def split_with_line(self, line, tolerance=0.01):
        """Get versions of this Room2D that are split by a line.

        If the input line does not intersect this Room2D in a manner that splits
        it into two or more pieces, a list with only the current room will be
        returned.

        Args:
            line: A LineSegment2D object that will be used to split this Room2D
                into two or more pieces.
            tolerance: The maximum difference between point values for them to be
                considered distinct from one another. (Default: 0.01; suitable
                for objects in Meters).

        Returns:
            A list of Room2D for the result of splitting this Room2D with the
            input line. Will be a list with only the current Room2D if the line
            does not split it into two or more pieces.
        """
        # create a 3D version of the line for the closest point calculation
        if isinstance(line, LineSegment2D):
            # check if the coordinate values are too high to resolve with tolerance
            t_up = tolerance * 1e6
            if line.p.x > t_up or line.p.y > t_up or line.v.x > t_up or line.v.y > t_up:
                min_pt, max_pt = self.min, self.max
                base, hgt = max_pt.x - min_pt.x, max_pt.y - min_pt.y
                bound_rect = Polygon2D.from_rectangle(min_pt, Vector2D(0, 1), base, hgt)
                inter_pts = bound_rect.intersect_line_ray(line)
                if len(inter_pts) == 2:
                    line = LineSegment2D.from_end_points(inter_pts[0], inter_pts[1])
            line_3d = LineSegment3D(Point3D(line.p.x, line.p.y, self.floor_height),
                                    Vector3D(line.v.x, line.v.y, 0))
        else:
            msg = 'Expected LineSegment2D. Got {}.'.format(type(line))
            raise TypeError(msg)
        # split the Room2D with the line
        new_geos = self.floor_geometry.split_with_line(line_3d, tolerance)
        if new_geos is None or len(new_geos) == 1:
            return [self]  # the Face3D did not overlap with one another
        # create the final Room2Ds
        return self._create_split_rooms(new_geos, tolerance)

    def split_with_polyline(self, polyline, tolerance=0.01):
        """Get versions of this Room2D that are split into two or more by a polyline.

        If the input polyline does not intersect this Room2D in a manner that splits
        it into two or more pieces, a list with only the current room will be
        returned.

        Args:
            polyline: A Polyline2D object that will be used to split this Room2D
                into two or more pieces.
            tolerance: The maximum difference between point values for them to be
                considered distinct from one another. (Default: 0.01; suitable
                for objects in Meters).

        Returns:
            A list of Room2D for the result of splitting this Room2D with the
            input polyline. Will be a list with only the current Room2D if the
            polyline does not split it into two or more pieces.
        """
        # create a 3D version of the polyline for the closest point calculation
        if isinstance(polyline, Polyline2D):
            polyline_3d = Polyline3D(
                [Point3D(pt.x, pt.y, self.floor_height) for pt in polyline])
        else:
            msg = 'Expected Polyline2D. Got {}.'.format(type(polyline))
            raise TypeError(msg)
        # split the Room2D with the polyline
        new_geos = self.floor_geometry.split_with_polyline(polyline_3d, tolerance)
        if new_geos is None or len(new_geos) == 1:
            return [self]  # the Face3D did not overlap with one another
        # create the final Room2Ds
        return self._create_split_rooms(new_geos, tolerance)

    def split_with_polygon(self, polygon, tolerance=0.01):
        """Get versions of this Room2D that are split into two or more by a polygon.

        If the input polygon does not intersect this Room2D in a manner that splits
        it into two or more pieces, a list with only the current room will be
        returned.

        Args:
            polygon: A Polygon2D object that will be used to split this Room2D
                into two or more pieces.
            tolerance: The maximum difference between point values for them to be
                considered distinct from one another. (Default: 0.01; suitable
                for objects in Meters).

        Returns:
            A list of Room2D for the result of splitting this Room2D with the
            input polygon. Will be a list with only the current Room2D if the
            polygon does not split it into two or more pieces.
        """
        # create a 3D version of the polygon for the closest point calculation
        if isinstance(polygon, Polygon2D):
            face_3d = Face3D(
                [Point3D(pt.x, pt.y, self.floor_height) for pt in polygon])
        else:
            msg = 'Expected Polygon2D. Got {}.'.format(type(polygon))
            raise TypeError(msg)
        # split the Room2D with the polygon
        ang_tol = math.radians(1)
        new_geos, _ = Face3D.coplanar_split(
            self.floor_geometry, face_3d, tolerance, ang_tol)
        if new_geos is None or len(new_geos) == 1:
            return [self]  # the Face3D did not overlap with one another
        # create the final Room2Ds
        return self._create_split_rooms(new_geos, tolerance)

    def _create_split_rooms(self, face_3ds, tolerance):
        """Create Room2Ds from Face3Ds that were split from this Room2D."""
        # create the Room2Ds
        new_rooms = []
        for i, new_geo in enumerate(face_3ds):
            rm_id = '{}{}'.format(self.identifier, i)
            rebuilt_room = Room2D(
                rm_id, new_geo, self.floor_to_ceiling_height,
                is_ground_contact=self.is_ground_contact,
                is_top_exposed=self.is_top_exposed)
            self._match_and_transfer_wall_props(rebuilt_room, tolerance)
            rebuilt_room._display_name = self._display_name
            rebuilt_room._user_data = self._user_data
            rebuilt_room._parent = self._parent
            rebuilt_room._abridged_properties = self._abridged_properties
            rebuilt_room._properties._duplicate_extension_attr(self._properties)
            new_rooms.append(rebuilt_room)

        # split the skylights if they exist
        if self.skylight_parameters is not None:
            room_faces = [r.floor_geometry for r in new_rooms]
            new_skys = self.skylight_parameters.split(room_faces, tolerance)
            for room, sky_par in zip(new_rooms, new_skys):
                room.skylight_parameters = sky_par

        return new_rooms

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

    def check_degenerate(self, tolerance=0.01, raise_exception=True, detailed=False):
        """Check whether the Room2D's floor geometry is degenerate with zero area.

        Args:
            tolerance: The minimum difference between the coordinate values of two
                vertices at which they can be considered equivalent. (Default: 0.01,
                suitable for objects in meters).
            raise_exception: If True, a ValueError will be raised if the object
                intersects with itself. (Default: True).
            detailed: Boolean for whether the returned object is a detailed list of
                dicts with error info or a string with a message. (Default: False).

        Returns:
            A string with the message or a list with a dictionary if detailed is True.
        """
        degenerate = False
        try:
            self.floor_geometry.remove_colinear_vertices(tolerance)
        except AssertionError:  # degenerate geometry found!
            degenerate = True

        if degenerate:
            msg = 'Room2D "{}" has degenerate floor geometry with zero ' \
                'area.'.format(self.display_name)
            if raise_exception:
                raise ValueError(msg)
            full_msg = self._validation_message_child(
                msg, self, detailed, '100101',
                error_type='Degenerate Room Geometry')
            if detailed:
                return [full_msg]
            if raise_exception:
                raise ValueError(full_msg)
            return full_msg
        return [] if detailed else ''

    def check_self_intersecting(self, tolerance=0.01, raise_exception=True,
                                detailed=False):
        """Check whether the Room2D's floor geometry intersects itself (like a bowtie).

        Note that objects that have duplicate vertices will not be considered
        self-intersecting and are valid.

        Args:
            tolerance: The minimum difference between the coordinate values of two
                vertices at which they can be considered equivalent. (Default: 0.01,
                suitable for objects in meters).
            raise_exception: If True, a ValueError will be raised if the object
                intersects with itself. (Default: True).
            detailed: Boolean for whether the returned object is a detailed list of
                dicts with error info or a string with a message. (Default: False).

        Returns:
            A string with the message or a list with a dictionary if detailed is True.
        """
        if self.floor_geometry.is_self_intersecting:
            msg = 'Room2D "{}" has floor geometry with self-intersecting ' \
                'edges.'.format(self.display_name)
            try:  # see if it is self-intersecting because of a duplicate vertex
                new_geo = self.floor_geometry.remove_duplicate_vertices(tolerance)
                if not new_geo.is_self_intersecting:
                    return [] if detailed else ''  # valid with removed dup vertex
            except AssertionError:
                pass  # zero area face; treat it as self-intersecting
            full_msg = self._validation_message_child(
                msg, self, detailed, '100102',
                error_type='Self-Intersecting Room Geometry')
            if detailed:
                return [full_msg]
            if raise_exception:
                raise ValueError(full_msg)
            return full_msg
        return [] if detailed else ''

    def check_window_parameters_valid(
            self, tolerance=0.01, raise_exception=True, detailed=False):
        """Check whether the window and skylight parameters produce valid apertures.

        This means that this Room's windows do not overlap with one another and,
        in the case of detailed windows, the polygons do not self-intersect. It
        also means that skylights do not extend past the boundary of the room.

        Args:
            tolerance: The minimum difference between the coordinate values of two
                vertices at which they can be considered equivalent. (Default: 0.01,
                suitable for objects in meters).
            raise_exception: Boolean to note whether a ValueError should be raised
                if the window parameters are not valid.
            detailed: Boolean for whether the returned object is a detailed list of
                dicts with error info or a string with a message. (Default: False).

        Returns:
            A string with the message or a list with a dictionary if detailed is True.
        """
        detailed = False if raise_exception else detailed
        msgs = []
        checkable_par = (RectangularWindows, DetailedWindows)
        for i, wp in enumerate(self._window_parameters):
            if wp is not None and isinstance(wp, checkable_par):
                msg = wp.check_window_overlaps(tolerance)
                if msg != '':
                    msgs.append(' Segment ({}) - {}'.format(i, msg))
                if isinstance(wp, DetailedWindows):
                    msg = wp.check_self_intersecting(tolerance)
                    if msg != '':
                        msgs.append(' Segment ({}) - {}'.format(i, msg))
        if isinstance(self._skylight_parameters, DetailedSkylights):
            msg = self._skylight_parameters.check_valid_for_face(self.floor_geometry)
            if msg != '':
                msgs.append(' Skylights - {}'.format(msg))
            msg = self._skylight_parameters.check_overlaps(tolerance)
            if msg != '':
                msgs.append(' Skylights - {}'.format(msg))
            msg = self._skylight_parameters.check_self_intersecting(tolerance)
            if msg != '':
                msgs.append(' Skylights - {}'.format(msg))
        if len(msgs) == 0:
            return [] if detailed else ''
        full_msg = 'Room2D "{}" contains invalid window parameters.' \
            '\n  {}'.format(self.display_name, '\n  '.join(msgs))
        full_msg = self._validation_message_child(
            full_msg, self, detailed, '100103', error_type='Invalid Window Parameters')
        if detailed:
            return [full_msg]
        if raise_exception:
            raise ValueError(full_msg)
        return full_msg

    def to_core_perimeter(self, perimeter_offset, air_boundary=False, tolerance=0.01):
        """Translate this Room2D into a list of Room2Ds separated by core and perimeter.

        All of the resulting Room2Ds will have the same properties as this initial
        Room2D with all windows and boundary conditions conserved. All of the
        newly-created interior walls between the core and perimeter Room2Ds will
        have Surface boundary conditions.

        Args:
            perimeter_offset: An optional positive number that will be used to offset
                the perimeter of the all_story_geometry to create core/perimeter
                zones. If this value is 0, no offset will occur and each story
                will be represented with a single Room2D per polygon.
            air_boundary: A boolean to note whether all of the new wall adjacencies
                should be set to an AirBoundary type. (Default: False).
            tolerance: The maximum difference between x, y, and z values at which
                point vertices are considered to be the same. This is also needed as
                a means to determine which floor geometries are equivalent to one
                another and should be a part the same Story. Default: 0.01, suitable
                for objects in meters.

        Returns:
            A list of Room2D for core Room2Ds followed by perimeter Room2Ds. If the
            current Room2D cannot be converted into core and perimeter Room2Ds,
            a list with the current Room2D instance will be returned.
        """
        # create the floor Face3Ds from this Room2D's floor_geometry
        tol = tolerance
        try:
            perimeter, core = perimeter_core_subfaces(
                self.floor_geometry, perimeter_offset, tol)
            new_face3d_array = perimeter + core
        except Exception:  # the generation of the polyskel failed; possibly neg offset
            return [self]  # just use existing floor

        # create the new Room2D objects from the result
        parent_zip = (
            self.floor_segments_2d, self.boundary_conditions,
            self.window_parameters, self.shading_parameters, self.air_boundaries
        )
        new_rooms = []
        for i, floor_geo in enumerate(new_face3d_array):
            # determine the segments of the new Room2D
            if floor_geo.normal.z < 0:  # ensure upward-facing Face3D
                floor_geo = floor_geo.flip()
            o_p = Plane(Vector3D(0, 0, 1), Point3D(0, 0, floor_geo.plane.o.z))
            floor_geo = Face3D(floor_geo.boundary, o_p, floor_geo.holes)
            new_room_seg = floor_geo.boundary_polygon2d.segments \
                if not floor_geo.has_holes \
                else floor_geo.boundary_polygon2d.segments + \
                tuple(seg for hole in floor_geo.hole_polygon2d for seg in hole.segments)
            # match the new segments to the existing properties
            new_bcs, new_win, new_shd, new_abs = [], [], [], []
            for new_seg in new_room_seg:
                p1, p2 = new_seg.p1, new_seg.p2
                for seg, bc, wp, sp, ab in zip(*parent_zip):
                    if seg.distance_to_point(p1) <= tol and \
                            seg.distance_to_point(p2) <= tol:
                        new_bcs.append(bc)
                        new_win.append(wp)
                        new_shd.append(sp)
                        new_abs.append(ab)
                        break
                else:
                    new_bcs.append(bcs.outdoors)
                    new_win.append(None)
                    new_shd.append(None)
                    new_abs.append(False)
            new_id = '{}_{}'.format(self.identifier, i)
            new_room = Room2D(
                new_id, floor_geo, self.floor_to_ceiling_height, new_bcs, new_win,
                new_shd, self.is_ground_contact, self.is_top_exposed, tol)
            new_room.air_boundaries = new_abs
            new_room.display_name = '{}_{}'.format(self.display_name, i)
            new_room._properties._duplicate_extension_attr(self._properties)
            new_rooms.append(new_room)

        # re-assign skylights if they exist
        if self.skylight_parameters is not None:
            room_faces = [r.floor_geometry for r in new_rooms]
            new_skys = self.skylight_parameters.split(room_faces, tol)
            for room, sky_par in zip(new_rooms, new_skys):
                room.skylight_parameters = sky_par

        # solve adjacency between the Room2Ds
        new_rooms = Room2D.intersect_adjacency(new_rooms, tol)
        adj_info = Room2D.solve_adjacency(new_rooms, tol)
        if air_boundary:  # set air boundary type if requested
            for room_pair in adj_info:
                for room_adj in room_pair:
                    room, wall_i = room_adj
                    room.set_air_boundary(wall_i)
        return new_rooms

    def to_honeybee(
            self, multiplier=1, add_plenum=False, tolerance=0.01,
            enforce_bc=True, enforce_solid=True):
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
            enforce_bc: Boolean to note whether an exception should be raised if
                apertures are assigned to Wall with an illegal boundary conditions
                (True) or if the invalid boundary condition should be replaced
                with an Outdoor boundary condition (False). (Default: True).
            enforce_solid: Boolean to note whether the room should be translated
                as a solid extrusion whenever translating the room with custom
                roof geometry produces a non-solid result (True) or the non-solid
                room geometry should be allowed to remain in the result (False).
                The latter is useful for understanding why a particular roof
                geometry has produced a non-solid result. (Default: True).

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
        has_roof = False
        if self._parent is not None and self._parent._roof is not None:
            # generate the room volume from the slanted roof
            if self.is_top_exposed and multiplier == 1:
                room_polyface, roof_face_i = \
                    self._room_volume_with_roof(self._parent._roof, tolerance)
                if room_polyface is None:  # complete failure to interpret roof
                    has_roof = False
                elif enforce_solid and not room_polyface.is_solid:
                    has_roof = False
                else:
                    has_roof = True
        if not has_roof:  # generate the Room volume normally through extrusion
            room_polyface = Polyface3D.from_offset_face(
                self._floor_geometry, self.floor_to_ceiling_height)
            roof_face_i = [-1]

        # create the honeybee Room and set the RoofCeiling faces
        hb_room = Room.from_polyface3d(
            self.identifier, room_polyface, ground_depth=self.floor_height - 1)
        roof_faces = []
        for i in roof_face_i:
            rfc = hb_room[i]
            rfc.type = ftyp.roof_ceiling
            roof_faces.append(rfc)

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
                hb_face = hb_room[i + 1]
                try:
                    glz_par.add_window_to_face(hb_face, tolerance)
                except AssertionError as e:
                    if enforce_bc:
                        raise e
                    hb_room[i + 1]._boundary_condition = bcs.outdoors
                    hb_room[i + 1].remove_sub_faces()
                    glz_par.add_window_to_face(hb_face, tolerance)
                if has_roof and isinstance(glz_par, _AsymmetricBase):
                    valid_ap = []
                    for ap in hb_face._apertures:
                        if hb_face.geometry._is_sub_face(ap.geometry):
                            valid_ap.append(ap)
                    if len(hb_face._apertures) != len(valid_ap):
                        hb_face.remove_apertures()
                        hb_face.add_apertures(valid_ap)
        for i, shd_par in enumerate(self._shading_parameters):
            if shd_par is not None:
                shd_par.add_shading_to_face(hb_room[i + 1], tolerance)
        if self._air_boundaries is not None:
            for i, a_bnd in enumerate(self._air_boundaries):
                if a_bnd:
                    hb_room[i + 1].type = ftyp.air_boundary

        # ensure matching adjacent Faces across the Story
        if self._parent is not None and not has_roof:
            new_faces = self._split_walls_along_height(hb_room, tolerance, add_plenum)
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
            hb_room.story = self.parent.display_name
        hb_room.multiplier = multiplier
        hb_room._display_name = self._display_name
        hb_room._user_data = self._user_data

        # assign boundary conditions for the roof and floor
        try:
            hb_room[0].boundary_condition = bcs.adiabatic
            for rf in roof_faces:
                rf.boundary_condition = bcs.adiabatic
        except AttributeError:
            pass  # honeybee_energy is not loaded and Adiabatic type doesn't exist
        if self._is_ground_contact:
            hb_room[0].boundary_condition = bcs.ground
        if self._is_top_exposed:
            for rf in roof_faces:
                rf.boundary_condition = bcs.outdoors

        # transfer any extension properties assigned to the Room2D and return result
        hb_room._properties = self.properties.to_honeybee(hb_room)
        if not add_plenum or has_roof:
            if self._skylight_parameters is not None:
                if self._is_top_exposed:
                    for rf in roof_faces:
                        self._skylight_parameters.add_skylight_to_face(rf, tolerance)
            return hb_room, adjacencies

        # add plenums if requested and return results
        hb_plenums = self._honeybee_plenums(hb_room, tolerance=tolerance)
        for hb_plenum in hb_plenums:  # transfer the parent's construction set
            hb_plenum._properties = self.properties.to_honeybee(hb_plenum)
            hb_plenum.exclude_floor_area = True
            try:  # set the program to unconditioned plenum and assign infiltration
                hb_plenum.properties.energy.program_type = None
                hb_plenum.properties.energy.hvac = None
                hb_plenum.properties.energy._shw = None
                hb_plenum.properties.energy.infiltration = \
                    hb_room.properties.energy.infiltration
            except AttributeError:
                pass  # honeybee-energy is not loaded; ignore all these energy properties

        # set the skylights if top is exposed and there's no ceiling plenum
        if self._skylight_parameters is not None:
            if self._is_top_exposed:
                if len(hb_plenums) == 0:
                    self._skylight_parameters.add_skylight_to_face(
                        hb_room[-1], tolerance)
                elif len(hb_plenums) == 1 and \
                        hb_plenums[0].identifier.endswith('floor_plenum'):
                    self._skylight_parameters.add_skylight_to_face(
                        hb_room[-1], tolerance)

        # return the rooms and the adjacency information
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
        if abridged and self._abridged_properties is not None:
            base['properties'] = self._abridged_properties
        else:
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

        if self._skylight_parameters is not None:
            base['skylight_parameters'] = self.skylight_parameters.to_dict()

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
    def find_adjacency_gaps(room_2ds, gap_distance=0.1, tolerance=0.01):
        """Identify gaps between a list of Room2Ds that are smaller than a gap_distance.

        This is useful for identifying cases where gaps can result in failed
        intersections between Room2Ds of adjacent stories or failed adjacency
        solving within each story.

        Args:
            room_2ds: A list of Room2Ds for which adjacency gaps will be identified.
            gap_distance: The maximum distance between two Room2Ds that is considered
                an adjacency gap. Differences between Room2Ds that are higher than
                this distance are considered meaningful gaps to be preserved.
                This value should be higher than the tolerance to be
                meaningful. (Default: 0.1, suitable for objects in meters).
            tolerance: The minimum difference between the coordinate values at
                which point they are considered equivalent. (Default: 0.01,
                suitable for objects in meters).

        Returns:
            A list of Point2Ds that note the location of any gaps between the input
            room_2ds, which are larger than the tolerance but less than the
            gap_distance.
        """
        gap_points = []
        for i, room_1 in enumerate(room_2ds):
            try:
                for room_2 in room_2ds[i + 1:]:
                    poly_1 = room_1._floor_geometry.boundary_polygon2d
                    poly_2 = room_2._floor_geometry.boundary_polygon2d
                    if not Polygon2D.overlapping_bounding_rect(
                            poly_1, poly_2, gap_distance):
                        continue  # no overlap in bounding rect; gap impossible
                    # check the first polygon against the second
                    for pt_1 in poly_1:
                        pt_dist = poly_2.distance_from_edge_to_point(pt_1)
                        if tolerance < pt_dist <= gap_distance:
                            gap_points.append(pt_1)
                    # check the second polygon against the first
                    for pt_2 in poly_2:
                        pt_dist = poly_1.distance_from_edge_to_point(pt_2)
                        if tolerance < pt_dist <= gap_distance:
                            gap_points.append(pt_2)
            except IndexError:
                pass  # we have reached the end of the list of rooms
        return gap_points

    @staticmethod
    def solve_adjacency(room_2ds, tolerance=0.01, resolve_window_conflicts=True):
        """Solve for all adjacencies between a list of input Room2Ds.

        Args:
            room_2ds: A list of Room2Ds for which adjacencies will be solved.
            tolerance: The minimum difference between the coordinate values of two
                faces at which they can be considered adjacent. (Default: 0.01,
                suitable for objects in meters).
            resolve_window_conflicts: Boolean to note whether conflicts between
                window parameters of adjacent segments should be resolved during
                adjacency setting or an error should be raised about the mismatch.
                Resolving conflicts will default to the window parameters with the
                larger are and assign them to the other segment. (Default: True).

        Returns:
            A list of tuples with each tuple containing 2 sub-tuples for wall
            segments paired in the process of solving adjacency. Sub-tuples have
            the Room2D as the first item and the index of the adjacent wall as the
            second item. This data can be used to assign custom properties to the
            new adjacent walls (like assigning custom window parameters for
            interior windows, assigning air boundaries, or custom boundary
            conditions).
        """
        rwc = resolve_window_conflicts
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
                                    room_1.set_adjacency(room_2, j, k, rwc)
                                    adj_info.append(((room_1, j), (room_2, k)))
                                    break
            except IndexError:
                pass  # we have reached the end of the list of rooms
        return adj_info

    @staticmethod
    def find_adjacency(room_2ds, tolerance=0.01):
        """Get a list with all adjacent pairs of segments between input Room2Ds.

        Note that this method does not change any boundary conditions of the input
        Room2Ds or mutate them in any way. It's purely a geometric analysis of the
        segments between Room2Ds.

        Args:
            room_2ds: A list of Room2Ds for which adjacencies will be solved.
            tolerance: The minimum difference between the coordinate values of two
                faces at which they can be considered adjacent. (Default: 0.01,
                suitable for objects in meters).

        Returns:
            A list of tuples for each discovered adjacency. Each tuple contains
            2 sub-tuples with two elements. The first element is the Room2D and
            the second is the index of the wall segment that is adjacent.
        """
        adj_info = []  # lists of adjacencies to track
        for i, room_1 in enumerate(room_2ds):
            try:
                for room_2 in room_2ds[i + 1:]:
                    if not Polygon2D.overlapping_bounding_rect(
                            room_1._floor_geometry.boundary_polygon2d,
                            room_2._floor_geometry.boundary_polygon2d, tolerance):
                        continue  # no overlap in bounding rect; adjacency impossible
                    for j, seg_1 in enumerate(room_1.floor_segments_2d):
                        for k, seg_2 in enumerate(room_2.floor_segments_2d):
                            if seg_1.distance_to_point(seg_2.p1) <= tolerance and \
                                    seg_1.distance_to_point(seg_2.p2) <= tolerance:
                                adj_info.append(((room_1, j), (room_2, k)))
                                break
            except IndexError:
                pass  # we have reached the end of the list of rooms
        return adj_info

    @staticmethod
    def intersect_adjacency(room_2ds, tolerance=0.01, preserve_wall_props=True):
        """Intersect the line segments of an array of Room2Ds to ensure matching walls.

        Also note that this method does not actually set the walls that are next to one
        another to be adjacent. The solve_adjacency method must be used for this after
        running this method.

        Args:
            room_2ds: A list of Room2Ds for which adjacent segments will be
                intersected.
            tolerance: The minimum difference between the coordinate values of two
                faces at which they can be considered adjacent. Default: 0.01,
                suitable for objects in meters.
            preserve_wall_props: Boolean to note whether existing window parameters,
                shading parameters and boundary conditions should be preserved as
                vertices are added during intersection. If False, all boundary
                conditions are replaced with Outdoors, all window parameters are
                erased, and this method will execute quickly. If True, an attempt
                will be made to split window parameters new across colinear segments.
                Existing boundary conditions will also be kept. (Default: True).

        Returns:
            An array of Room2Ds that have been intersected with one another.
        """
        # keep track of all data needed to map between 2D and 3D space
        master_plane = room_2ds[0].floor_geometry.plane
        move_dists = []
        is_holes = []
        polygon_2ds = []
        tol = tolerance

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
        int_poly = Polygon2D.intersect_polygon_segments(polygon_2ds, tol)

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
            rebuilt_room._skylight_parameters = room_2ds[i].skylight_parameters
            rebuilt_room._display_name = room_2ds[i]._display_name
            rebuilt_room._user_data = None if room_2ds[i].user_data is None else \
                room_2ds[i].user_data.copy()
            rebuilt_room._parent = room_2ds[i]._parent
            rebuilt_room._abridged_properties = room_2ds[i]._abridged_properties
            rebuilt_room._properties._duplicate_extension_attr(room_2ds[i]._properties)
            intersected_rooms.append(rebuilt_room)

        # transfer the wall properties if requested
        if preserve_wall_props:
            for orig_r, new_r in zip(room_2ds, intersected_rooms):
                orig_r._match_and_transfer_wall_props(new_r, tolerance)

        return tuple(intersected_rooms)

    @staticmethod
    def group_by_adjacency(rooms):
        """Group Room2Ds together that are connected by adjacencies.

        This is useful for separating rooms in the case where a Story contains
        multiple towers or sections that are separated by outdoor boundary conditions.

        Args:
            rooms: A list of Room2Ds to be grouped by their adjacency.

        Returns:
            A list of list with each sub-list containing rooms that share adjacencies.
        """
        return Room2D._adjacency_grouping(rooms, Room2D._find_adjacent_rooms)

    @staticmethod
    def group_by_air_boundary_adjacency(rooms):
        """Group Room2Ds together that share air boundaries.

        This is useful for understanding the radiant enclosures that will exist
        when a model is exported to EnergyPlus.

        Args:
            rooms: A list of Room2Ds to be grouped by their air boundary adjacency.

        Returns:
            A list of list with each sub-list containing Room2Ds that share adjacent
            air boundaries. If a Room has no air boundaries it will the the only
            item within its sub-list.
        """
        return Room2D._adjacency_grouping(
            rooms, Room2D._find_adjacent_air_boundary_rooms)

    @staticmethod
    def join_room_2ds(room_2ds, min_separation=0, tolerance=0.01):
        """Join Room2Ds together that are touching one another within a min_separation.

        When the min_separation is less than or equal to the tolerance, all
        properties of segments for the input Room2Ds will be preserved. When
        the min_separation is larger than the tolerance, an attempt is made to
        preserve all wall properties but there is a risk of losing some windows
        just in the region where two Room2Ds are joined together across a gap
        between them. This risk can be overcome by inserting Room2D vertices
        around where the gap will be crossed between that Room2D and the
        other Room2D.

        The largest Room2D that is identified within each connected group will
        determine the extension properties of the resulting Room2D. Skylights
        will be merged across rooms if they are of the same type or if they are None.

        Args:
            room_2ds: A list of Room2Ds which will be joined together where they
                touch one another.
            min_separation: A number for the minimum distance between Room2Ds that
                is considered a meaningful separation. Gaps between Room2Ds that
                are less than this distance will result in the Room2Ds being
                joined across the gap. When the input Room2Ds have floor_geometry
                representing the boundaries defined by the interior wall finishes,
                this input can be thought of as the maximum interior wall thickness.
                When Room2Ds are perfectly touching one another within the tolerance
                (with Room2D floor_geometry drawn to the center lines of interior
                walls), this value can be set to zero or anything less than or
                equal to the tolerance. Doing so will yield a cleaner result for the
                boundary, which will be faster and more reliable. Note that care
                should be taken not to set this value higher than the length of any
                meaningful exterior wall segments. Otherwise, the exterior segments
                will be ignored in the result. This can be particularly dangerous
                around curved exterior walls that have been planarized through
                subdivision into small segments. (Default: 0).
            tolerance: The minimum distance between a vertex and the polygon
                boundary at which point the vertex is considered to lie on the
                polygon. (Default: 0.01, suitable for objects in meters).
        """
        # get the horizontal boundaries around the input Room2Ds
        h_bnds = Room2D.grouped_horizontal_boundary(room_2ds, min_separation, tolerance)
        if len(h_bnds) == len(room_2ds):  # no Room2Ds to join; return them as they are
            return room_2ds

        # ensure Room2D vertices at the boundary exist
        if min_separation <= tolerance:
            room_2ds = Room2D.intersect_adjacency(room_2ds, tolerance)
        else:  # we have to figure out if new vertices were added to cross the boundary
            # gather all vertices across the horizontal boundaries
            bnd_verts = []
            for h_bnd in h_bnds:
                bnd_verts.extend([Point2D(pt.x, pt.y) for pt in h_bnd.boundary])
                if h_bnd.has_holes:
                    for hole in h_bnd.holes:
                        bnd_verts.extend([Point2D(pt.x, pt.y) for pt in hole])
            # loop through rooms and identify vertices to insert
            inter_rooms = []
            search_dist = tolerance * 2
            for room in room_2ds:
                floor_segs = [room.floor_geometry.boundary_polygon2d.segments]
                if room.floor_geometry.has_holes:
                    for hole in room.floor_geometry.hole_polygon2d:
                        floor_segs.append(hole.segments)
                pts_2d, edit_code = [], []
                for loop in floor_segs:
                    loop_pts_2d = []
                    for seg in loop:
                        loop_pts_2d.append(seg.p1)
                        edit_code.append('K')
                        for bnd_pt in bnd_verts:
                            if seg.distance_to_point(bnd_pt) <= search_dist:
                                if not seg.p1.is_equivalent(bnd_pt, tolerance) and \
                                        not seg.p2.is_equivalent(bnd_pt, tolerance):
                                    loop_pts_2d.append(bnd_pt)  # vertex to insert !
                                    edit_code.append('A')
                    pts_2d.append(loop_pts_2d)
                edit_code = ''.join(edit_code)
                if 'A' in edit_code:  # room geometry must be updated
                    room = room.duplicate()  # duplicate to avoid editing original geo
                    z_v = room.floor_height
                    pts_3d = []
                    for loop in pts_2d:
                        pts_3d.append([Point3D(pt.x, pt.y, z_v) for pt in loop])
                    new_geo = Face3D(pts_3d[0]) if len(pts_3d) == 1 else \
                        Face3D(pts_3d[0], holes=pts_3d[1:])
                    room.update_floor_geometry(new_geo, edit_code, search_dist)
                inter_rooms.append(room)
            room_2ds = inter_rooms

        # join the Room2Ds according to the horizontal boundaries that were found
        joined_rooms = []
        for h_bnd in h_bnds:
            bnd_p_gon = Polygon2D([Point2D(pt.x, pt.y) for pt in h_bnd.boundary])
            h_p = None
            if h_bnd.has_holes:
                h_p = []
                for hole in h_bnd.holes:
                    h_p.append(Polygon2D([Point2D(pt.x, pt.y) for pt in hole]))
            new_room = Room2D.join_by_boundary(
                room_2ds, bnd_p_gon, h_p, tolerance=tolerance)
            joined_rooms.append(new_room)
        return joined_rooms

    @staticmethod
    def join_by_boundary(
            room_2ds, polygon, hole_polygons=None, floor_to_ceiling_height=None,
            identifier=None, display_name=None, tolerance=0.01):
        """Join several Room2D together using a boundary Polygon as a guide.

        All properties of segments along the boundary polygon will be preserved.
        The largest Room2D that is identified within the boundary polygon will
        determine the extension properties of the resulting Room unless the supplied
        identifier matches an existing Room2D inside the polygon. Skylights
        will be merged if they are of the same type or if they are None.

        It is recommended that the Room2Ds be aligned to the boundaries
        of the polygon and duplicate vertices be removed before passing them
        through this method. However, colinear vertices should not be removed
        where possible. This helps ensure that relevant Room2D segments
        are colinear with the polygon and so they can influence the result.

        Args:
            room_2ds: A list of Room2Ds which will be joined together using the polygon.
            polygon: A ladybug_geometry Polygon2D which will become the boundary
                of the output joined Room2D.
            hole_polygons: An optional list of hole polygons, which will add
                holes into the output joined Room2D polygon. (Default: None).
            floor_to_ceiling_height: An optional number to set the floor-to-ceiling
                height of the resulting Room2D. If None, it will be the maximum
                of the Room2Ds that are found inside the polygon, which ensures
                that all window geometries are included in the output. If specified
                and it is lower than the maximum Room2D height, any detailed
                windows will be automatically trimmed to accommodate the new
                floor-to-ceiling height. (Default: None).
            identifier: An optional text string for the identifier of the new
                joined Room2D. If this matches an existing Room2D inside of the
                polygon, the existing Room2D will be used to set the extension
                properties of the output Room2D. If None, the identifier
                and extension properties of the output Room2D will be those of
                the largest Room2D found inside of the polygon. (Default: None).
            display_name: An optional text string for the display_name of the new
                joined Room2D. If None, the display_name will be taken from the
                largest existing Room2D inside the polygon or the existing
                Room2D matching the identifier above. (Default: None).
            tolerance: The minimum distance between a vertex and the polygon
                boundary at which point the vertex is considered to lie on the
                polygon. (Default: 0.01, suitable for objects in meters).
        """
        tol = tolerance
        # ensure that all polygons are counterclockwise
        polygon = polygon.reverse() if polygon.is_clockwise else polygon
        if hole_polygons is not None:
            cc_hole_polygons = []
            for p in hole_polygons:
                p = p.reverse() if p.is_clockwise else p
                cc_hole_polygons.append(p)
            hole_polygons = cc_hole_polygons

        # identify all Room2Ds inside of the polygon
        rel_rooms, rel_ids, rel_a, rel_fh, rel_ch = [], [], [], [], []
        test_vec = Vector2D(0.99, 0.01)
        for room in room_2ds:
            if room.floor_geometry.is_convex:
                rm_pt = room.center
            else:
                rm_pt_3d = room.floor_geometry._point_on_face(tol)
                rm_pt = Point2D(rm_pt_3d.x, rm_pt_3d.y)
            if polygon.is_point_inside_bound_rect(rm_pt, test_vec):
                rel_rooms.append(room)
                rel_ids.append(room.identifier)
                rel_a.append(room.floor_area)
                rel_fh.append(room.floor_height)
                rel_ch.append(room.floor_to_ceiling_height)

        # if no rooms are inside the polygon, just return a dummy room from the polygon
        if len(rel_rooms) == 0:
            fh = sum([r.floor_height for r in room_2ds]) / len(room_2ds)
            ftc = sum([r.floor_to_ceiling_height for r in room_2ds]) / len(room_2ds) \
                if floor_to_ceiling_height is None else floor_to_ceiling_height
            bound_verts = [Point3D(p.x, p.y, fh) for p in polygon.vertices]
            all_hole_verts = None
            if hole_polygons is not None and len(hole_polygons) != 0:
                all_hole_verts = []
                for hole in hole_polygons:
                    all_hole_verts.append([Point3D(p.x, p.y, fh) for p in hole.vertices])
            new_geo = Face3D(bound_verts, holes=all_hole_verts)
            r_id = clean_and_id_string('Room') if identifier is None else identifier
            return Room2D(r_id, new_geo, ftc)

        # determine the new floor heights using max/average across relevant rooms
        new_flr_height = sum(rel_fh) / len(rel_fh)
        max_ftc = max(rel_ch)
        new_ftc = max_ftc if floor_to_ceiling_height is None else floor_to_ceiling_height

        # determine a primary room to set help set properties or the resulting room
        if identifier is None or identifier not in rel_ids:
            # find the largest room of the relevant rooms
            sort_inds = [i for _, i in sorted(zip(rel_a, range(len(rel_a))))]
            primary_room = rel_rooms[sort_inds[-1]]
            if identifier is None:
                identifier = primary_room.identifier
        else:  # draw properties from the room with the matching identifier
            for r_id, rm in zip(rel_ids, rel_rooms):
                if r_id == identifier:
                    primary_room = rm
                    break
        if display_name is None:
            display_name = primary_room.display_name

        # gather all segments and properties of relevant rooms
        rel_segs, rel_bcs, rel_win, rel_shd, rel_abs = [], [], [], [], []
        for room in rel_rooms:
            rel_segs.extend(room.floor_segments_2d)
            rel_bcs.extend(room.boundary_conditions)
            rel_shd.extend(room.shading_parameters)
            rel_abs.extend(room.air_boundaries)
            w_par = room.window_parameters
            in_range = new_ftc - tol < room.floor_to_ceiling_height < new_ftc + tol
            if not in_range:  # adjust window ratios to preserve area
                new_w_par = []
                for i, wp in enumerate(w_par):
                    if isinstance(wp, SimpleWindowRatio):
                        w_area = wp.area_from_segment(
                            rel_segs[i], room.floor_to_ceiling_height)
                        new_ratio = w_area / (new_ftc * rel_segs[i].length)
                        new_wp = wp.duplicate()
                        new_wp._window_ratio = new_ratio if new_ratio <= 0.99 else 0.99
                        new_w_par.append(new_wp)
                    else:
                        new_w_par.append(wp)
                w_par = new_w_par
            rel_win.extend(w_par)

        # find all of the Room2Ds segments that lie on each polygon segment
        new_bcs, new_win, new_shd, new_abs = [], [], [], []
        bound_verts = Room2D._segments_along_polygon(
            polygon, rel_segs, rel_bcs, rel_win, rel_shd, rel_abs,
            new_bcs, new_win, new_shd, new_abs, new_flr_height, tol)
        if hole_polygons is not None and len(hole_polygons) != 0:
            all_hole_verts = []
            for hole in hole_polygons:
                hole_verts = Room2D._segments_along_polygon(
                    hole, rel_segs, rel_bcs, rel_win, rel_shd, rel_abs,
                    new_bcs, new_win, new_shd, new_abs, new_flr_height, tol)
                all_hole_verts.append(hole_verts)
            new_geo = Face3D(bound_verts, holes=all_hole_verts)
        else:
            new_geo = Face3D(bound_verts)

        # merge skylights across the input rooms if they are of the same type
        new_sky_lights, new_areas = [], []
        for room in rel_rooms:
            if room.skylight_parameters is not None:
                new_sky_lights.append(room.skylight_parameters)
                new_areas.append(room.floor_area)
        new_sky_light = None
        if all(isinstance(sl, DetailedSkylights) for sl in new_sky_lights):
            try:
                new_polys = new_sky_lights[0].polygons
                new_is_dr = new_sky_lights[0].are_doors
                for sl in new_sky_lights[1:]:
                    new_polys += sl.polygons
                    new_is_dr += sl.are_doors
                new_sky_light = DetailedSkylights(new_polys, new_is_dr)
            except IndexError:
                pass  # skylight with no polygons
        elif all(isinstance(sl, GriddedSkylightArea) for sl in new_sky_lights):
            new_area = sum(sl.skylight_area for sl in new_sky_lights)
            new_sky_light = GriddedSkylightArea(new_area)
        elif all(isinstance(sl, GriddedSkylightRatio) for sl in new_sky_lights):
            zip_obj = zip(new_sky_lights, new_areas)
            new_area = sum(sl.skylight_ratio * fa for sl, fa in zip_obj)
            new_ratio = new_area / sum(room.floor_area for room in rel_rooms)
            new_sky_light = GriddedSkylightRatio(new_ratio)

        # merge all segments and properties into a single Room2D
        new_room = Room2D(
            identifier, new_geo, new_ftc, new_bcs, new_win, new_shd,
            primary_room.is_ground_contact, primary_room.is_top_exposed, tol)
        new_room.skylight_parameters = new_sky_light
        new_room.air_boundaries = new_abs
        new_room.display_name = display_name
        new_room._properties._duplicate_extension_attr(primary_room._properties)

        # if the floor-to-ceiling height is lower than the max, re-trim windows
        if new_ftc < max_ftc:
            new_w_pars = []
            for w_par, seg in zip(new_room._window_parameters, new_room.floor_segments):
                if isinstance(w_par, DetailedWindows):
                    new_w_par = w_par.adjust_for_segment(seg, new_ftc, tolerance)
                else:
                    new_w_par = w_par
                new_w_pars.append(new_w_par)
            new_room._window_parameters = new_w_pars

        return new_room

    @staticmethod
    def grouped_horizontal_boundary(room_2ds, min_separation=0, tolerance=0.01):
        """Get a list of Face3D for the horizontal boundary around several Room2Ds.

        This method will attempt to produce a boundary that follows along the
        walls of the Room2Ds and it is not suitable for groups of Room2Ds that
        overlap one another in plan. This method may return an empty list if the
        min_separation is so large that a continuous boundary could not be determined
        or if overlaps between input Room2Ds result in failure.

        Args:
            room_2ds: A list of Room2Ds for which the horizontal boundary will
                be computed.
            min_separation: A number for the minimum distance between Room2Ds that
                is considered a meaningful separation. Gaps between Room2Ds that
                are less than this distance will be ignored and the boundary
                will continue across the gap. When the input Room2Ds have floor_geometry
                representing the boundaries defined by the interior wall finishes,
                this input can be thought of as the maximum interior wall thickness,
                which should be ignored in the calculation of the overall boundary
                of the Room2Ds. When Room2Ds are touching one another (with Room2D
                floor_geometry drawn to the center lines of interior walls), this
                value can be set to zero or anything less than or equal to the
                tolerance. Doing so will yield a cleaner result for the
                boundary, which will be faster. Note that care should be taken
                not to set this value higher than the length of any meaningful
                exterior wall segments. Otherwise, the exterior segments
                will be ignored in the result. This can be particularly dangerous
                around curved exterior walls that have been planarized through
                subdivision into small segments. (Default: 0).
            tolerance: The maximum difference between coordinate values of two
                vertices at which they can be considered equivalent. (Default: 0.01,
                suitable for objects in meters).
        """
        # get the floor geometry of the rooms
        floor_geos = [room.floor_geometry for room in room_2ds]

        # remove colinear vertices and degenerate rooms
        clean_floor_geos = []
        for geo in floor_geos:
            try:
                clean_floor_geos.append(geo.remove_colinear_vertices(tolerance))
            except AssertionError:  # degenerate geometry to ignore
                pass
        if len(clean_floor_geos) == 0:
            return []  # no Room boundary to be found

        # convert the floor Face3Ds into counterclockwise Polygon2Ds
        floor_polys, z_vals = [], []
        for flr_geo in clean_floor_geos:
            z_vals.append(flr_geo.min.z)
            b_poly = Polygon2D([Point2D(pt.x, pt.y) for pt in flr_geo.boundary])
            floor_polys.append(b_poly)
            if flr_geo.has_holes:
                for hole in flr_geo.holes:
                    h_poly = Polygon2D([Point2D(pt.x, pt.y) for pt in hole])
                    floor_polys.append(h_poly)
        z_min = min(z_vals)

        # if the min_separation is small, use the more reliable intersection method
        if min_separation <= tolerance:
            closed_polys = Polygon2D.joined_intersected_boundary(floor_polys, tolerance)
        else:  # otherwise, use the more intense and less reliable gap crossing method
            closed_polys = Polygon2D.gap_crossing_boundary(
                floor_polys, min_separation, tolerance)

        # remove colinear vertices from the resulting polygons
        clean_polys = []
        for poly in closed_polys:
            try:
                clean_polys.append(poly.remove_colinear_vertices(tolerance))
            except AssertionError:
                pass  # degenerate polygon to ignore

        # figure out if polygons represent holes in the others and make Face3D
        if len(clean_polys) == 0:
            return []
        elif len(clean_polys) == 1:  # can be represented with a single Face3D
            pts3d = [Point3D(pt.x, pt.y, z_min) for pt in clean_polys[0]]
            return [Face3D(pts3d)]
        else:  # need to separate holes from distinct Face3Ds
            bound_faces = []
            for poly in clean_polys:
                pts3d = tuple(Point3D(pt.x, pt.y, z_min) for pt in poly)
                bound_faces.append(Face3D(pts3d))
            return Face3D.merge_faces_to_holes(bound_faces, tolerance)

    @staticmethod
    def generate_alignment_axes(room_2ds, distance, direction=Vector2D(0, 1),
                                angle_tolerance=1.0):
        """Get suggested LineSegment2Ds for the Room2D.align method.

        This method will return the most common axes across the input Room2D
        geometry along with the number of Room2D segments that correspond to
        each axis. The latter can be used to filter the suggested alignment axes
        to get only the most common ones across the input Room2Ds.

        Args:
            room_2ds: A list of Room2D objects for which common axes will be evaluated.
            distance: A number for the distance that will be used in the alignment
                operation. This will be used to determine the resolution at which
                alignment axes are generated and evaluated. Smaller alignment
                distances will result in the generation of more common_axes since
                a finer resolution can differentiate common that would typically be
                grouped together. For typical building geometry, an alignment distance
                of 0.3 meters or 1 foot is typically suitable for eliminating
                unwanted details while not changing the geometry too much from
                its original location.
            direction: A Vector2D object to represent the direction in which the
                common axes will be evaluated and generated.
            angle_tolerance: The max angle difference in degrees that the Room2D
                segment direction can differ from the input direction before the
                segments are not factored into this calculation of common axes.

            Returns:
                A tuple with two elements.

            -   common_axes: A list of LineSegment2D objects for the common
                axes across the input Room2Ds.

            -   axis_values: A list of integers that aligns with the common_axes
                and denotes how many segments of the input Room2D each axis
                relates to. Higher numbers indicate that that the axis is more
                commonly aligned across the Room2Ds.
        """
        # process the inputs
        min_distance, merge_distance = distance / 3, distance
        ang_tol = math.radians(angle_tolerance)
        polygons = []
        for room in room_2ds:
            polygons.append(room.floor_geometry.boundary_polygon2d)
            if room.floor_geometry.has_holes:
                for hole in room.floor_geometry.hole_polygon2d:
                    polygons.append(hole)
        # return the common axes and values
        return Polygon2D.common_axes(
            polygons, direction, min_distance, merge_distance, ang_tol)

    @staticmethod
    def floor_segment_by_index(geometry, segment_index):
        """Get a particular LineSegment3D from a Face3D object.

        The logic applied by this method to select the segment is the same that is
        used to assign lists of values to the floor_geometry (eg. boundary conditions).

        Args:
            geometry: A Face3D representing floor geometry.
            segment_index: An integer for the index of the segment to return.
        """
        segs = geometry.boundary_segments if geometry.holes is \
            None else geometry.boundary_segments + \
            tuple(seg for hole in geometry.hole_segments for seg in hole)
        return segs[segment_index]

    def _room_volume_with_roof(self, roof_spec, tolerance):
        """Get a Polyface3D for the Room volume given a roof_spec above the room.

        Args:
            roof_spec: A Dragonfly RoofSpecification that describes the Roof
                above the room geometry.
            tolerance: The minimum distance from roof polygon edges at which a
                point is considered to lie on the edge.

        Returns:
            A tuple with the two items below.

            * room_polyface -- A Polyface3D object for the Room volume. This will
                be None whenever the Room has no Roof geometries above it or the
                roof calculation otherwise failed.

            * roof_face_i -- A list of integers for the indices of the faces in
                the Polyface3D that correspond to the roof. Will be None whenever
                the roof is not successfully applied to the Room.
        """
        # get the roof polygons and the bounding Room2D polygon
        roof_polys = roof_spec.boundary_geometry_2d
        roof_planes = roof_spec.planes
        room_pts2d = [Point2D(pt.x, pt.y) for pt in self.floor_geometry.boundary]
        room_poly = Polygon2D(room_pts2d)

        # gather all of the relevant roof polygons for the Room2D
        rel_rf_polys, rel_rf_planes, is_full_bound = [], [], False
        for rf_py, rf_pl in zip(roof_polys, roof_planes):
            poly_rel = rf_py.polygon_relationship(room_poly, tolerance)
            if poly_rel >= 0:
                rel_rf_polys.append(rf_py)
                rel_rf_planes.append(rf_pl)
            if poly_rel == 1:  # simple solution of one roof
                is_full_bound = True
                rel_rf_polys = [rel_rf_polys[-1]]
                rel_rf_planes = [rel_rf_planes[-1]]
                break

        # make the room volume
        p_faces = [self.floor_geometry.flip()]  # a list of Room volume faces
        proj_dir = Vector3D(0, 0, 1)  # direction to project onto Roof planes

        # when fully bounded, simply project the segments onto the single Roof face
        if is_full_bound:
            roof_plane = rel_rf_planes[0]
            roof_verts = []
            for seg in self.floor_segments:
                p1, p2 = seg.p1, seg.p2
                p3 = roof_plane.project_point(p2, proj_dir)
                p4 = roof_plane.project_point(p1, proj_dir)
                p_faces.append(Face3D((p1, p2, p3, p4)))
                roof_verts.append(p4)
            if not self.floor_geometry.has_holes:
                p_faces.append(Face3D(roof_verts))
            else:
                v_count = len(self.floor_geometry.boundary)
                part_roof_verts = [roof_verts[:v_count]]
                for hole in self.floor_geometry.holes:
                    part_roof_verts.append(roof_verts[v_count:v_count + len(hole)])
                    v_count += len(hole)
                p_faces.append(Face3D(part_roof_verts[0], holes=part_roof_verts[1:]))
            return Polyface3D.from_faces(p_faces, tolerance), [-1]

        # when multiple roofs, each segment must be intersected with the roof polygons
        # gather polygons that account for all of the Room2D holes
        all_room_poly = [room_poly]
        flr_segs = self.floor_segments
        if self.floor_geometry.has_holes:
            v_count = len(room_poly)
            all_segments = [flr_segs[:v_count]]
            for hole in self.floor_geometry.holes:
                hole_poly = Polygon2D([Point2D(pt.x, pt.y) for pt in hole])
                all_room_poly.append(hole_poly)
                all_segments.append(flr_segs[v_count:v_count + len(hole)])
                v_count += len(hole)
        else:
            all_segments = [flr_segs]

        # get the roof faces using polygon boolean operations
        roof_faces = self._roof_faces(
            all_room_poly, rel_rf_polys, rel_rf_planes, tolerance)
        if roof_faces is None:  # invalid roof geometry
            return None, None

        # create the walls from the segments by intersecting them with the roof
        if len(roof_faces) > len(rel_rf_polys):  # new roofs added; rebuild polygons
            rel_rf_polys = [
                Polygon2D(tuple(Point2D(pt.x, pt.y) for pt in geo.boundary))
                for geo in roof_faces]
            rel_rf_planes = [geo.plane for geo in roof_faces]
        walls = self._wall_faces_with_roof(
            all_room_poly, all_segments, rel_rf_polys, rel_rf_planes, tolerance)
        if walls is None:  # invalid roof geometry
            return None, None

        # combine all of the room volume faces together
        p_faces.extend(walls)
        roof_face_i = list(range(-1, -len(roof_faces) - 1, -1))
        p_faces.extend(roof_faces)

        # create the Polyface3D and try to repair it if it is not solid
        room_polyface = Polyface3D.from_faces(p_faces, tolerance)
        ang_tol = math.radians(1)

        # make sure that overlapping edges are merged so we don't get false readings
        if not room_polyface.is_solid:
            room_polyface = room_polyface.merge_overlapping_edges(tolerance, ang_tol)

        # try to patch any vertical gaps between roofs with new walls
        if not room_polyface.is_solid:
            room_polyface, roof_face_i = \
                self._patch_vertical_gaps(room_polyface, roof_face_i, tolerance)
            if not room_polyface.is_solid:
                room_polyface = room_polyface.merge_overlapping_edges(tolerance, ang_tol)

        # remove disconnected roof geometries from the Polyface (eg. dormers)
        if not room_polyface.is_solid:
            room_polyface, roof_face_i, _ = \
                self._separate_disconnected_faces(room_polyface, roof_face_i, tolerance)
            if not room_polyface.is_solid:
                room_polyface = room_polyface.merge_overlapping_edges(tolerance, ang_tol)

        # lastly, try to patch any remaining planar holes by capping them
        if not room_polyface.is_solid:
            room_polyface, roof_face_i = \
                self._cap_planar_holes(room_polyface, roof_face_i, tolerance)
            if not room_polyface.is_solid:
                room_polyface = room_polyface.merge_overlapping_edges(tolerance, ang_tol)

        return room_polyface, roof_face_i

    def _wall_faces_with_roof(self, all_room_poly, all_segments,
                              rel_rf_polys, rel_rf_planes, tolerance):
        """Generate Face3D for the Room Walls when there are multiple Roof Polygons.

        Args:
            all_room_poly: A list of Polygon2D where each polygon represents either
                the boundary of the room or a hole.
            all_segments: A list of lists where each sub-list contains LineSegment2D
                objects for each polygon in all_room_poly.
            rel_rf_polys: A list of Polygon2D for the Roof geometries that are
                relevant to the Room2D.
            rel_rf_planes: A list of Plane objects for each Roof geometry that
                is relevant to the Room2D.
            tolerance: The distance value for absolute tolerance.

        Returns:
            A list of Face3D for the Walls of the Room. Will be None if the Roof
            geometries are invalid.
        """
        wall_faces = []
        proj_dir = Vector3D(0, 0, 1)  # direction to project onto Roof planes

        # loop through holes and boundary polygons and generate walls from them
        for rm_poly, rm_segs in zip(all_room_poly, all_segments):
            # find the polygon that the first room vertex is located in
            current_poly, current_plane = None, None
            other_poly, other_planes = rel_rf_polys[:], rel_rf_planes[:]  # copy lists
            pt1 = rm_poly[0]
            for i, (rf_py, rf_pl) in enumerate(zip(rel_rf_polys, rel_rf_planes)):
                if rf_py.point_relationship(pt1, tolerance) >= 0:
                    current_poly, current_plane = rf_py, rf_pl
                    other_poly.pop(i)
                    other_planes.pop(i)
                    break
            if current_poly is None:  # first point not inside a roof, invalid roof
                return None

            # loop through segments and add vertices if they cross outside the roof face
            rot_poly = rm_poly.vertices[1:] + (pt1,)
            for pt2, seg in zip(rot_poly, rm_segs):
                face_pts = [seg.p1, seg.p2]
                # see if the segment ends in the same face it starts in
                if current_poly.point_relationship(pt2, tolerance) >= 0:  # project seg
                    face_pts.append(current_plane.project_point(seg.p2, proj_dir))
                    face_pts.append(current_plane.project_point(seg.p1, proj_dir))
                else:
                    int_pts, int_pls = [(seg.p1, 0)], [current_plane]
                    # find where the segment leaves the polygon
                    seg_2d = LineSegment2D.from_array(((pt1.x, pt1.y), (pt2.x, pt2.y)))
                    for rf_seg in current_poly.segments:
                        int_pt = seg_2d.intersect_line_ray(rf_seg)
                        if int_pt is None:
                            dist, cls_pts = closest_point2d_between_line2d(
                                seg_2d, rf_seg)
                            if dist <= tolerance:
                                int_pt = cls_pts[0]
                        if int_pt is not None:
                            int_pts.append((int_pt, 0))
                            int_pls.append(current_plane)
                    # find where it intersects the other relevant polygons
                    for o_poly, o_pl in zip(other_poly, other_planes):
                        for o_seg in o_poly.segments:
                            int_pt = seg_2d.intersect_line_ray(o_seg)
                            if int_pt is None:
                                d, cls_pts = closest_point2d_between_line2d(
                                    seg_2d, o_seg)
                                if d <= tolerance:
                                    int_pt = cls_pts[0]
                            if int_pt is not None:
                                int_pts.append((int_pt, 1))
                                int_pls.append(o_pl)
                    # sort the intersections points along the segment
                    pt_dists = [(ipt[1], seg_2d.p1.distance_to_point(ipt[0]))
                                for ipt in int_pts]
                    pts_pls = [(i_pt[0], i_pl) for i_pt, i_pl in zip(int_pts, int_pls)]
                    sort_obj = sorted(zip(pt_dists, pts_pls), key=lambda pair: pair[0])
                    sort_pts_pls = [x for _, x in sort_obj]
                    # if two points are equivalent, reorder with the previous point plane
                    ord_pts = [x[0] for x in sort_pts_pls]
                    ord_pls = [x[1] for x in sort_pts_pls]
                    for i, (pt, pln) in enumerate(sort_pts_pls[1:]):
                        if pt.distance_to_point(ord_pts[i]) < tolerance:
                            prev_pl = ord_pls[i - 1]
                            if pln == prev_pl and ord_pls[i] != prev_pl:  # reorder
                                ord_pts[i], ord_pts[i + 1] = ord_pts[i + 1], ord_pts[i]
                                ord_pls[i], ord_pls[i + 1] = ord_pls[i + 1], ord_pls[i]
                    # project the points onto the planes
                    rf_pts = [ipl.project_point(Point3D.from_point2d(ipt), proj_dir)
                              for ipt, ipl in zip(ord_pts, ord_pls)]
                    # add a vertex for where the segment ends in the polygon
                    for i, (rf_py, rf_pl) in enumerate(zip(other_poly, other_planes)):
                        if rf_py.point_relationship(pt2, tolerance) >= 0:
                            other_poly.pop(i)
                            other_poly.append(current_poly)
                            other_planes.pop(i)
                            other_planes.append(current_plane)
                            current_poly, current_plane = rf_py, rf_pl
                            rf_pts.append(
                                rf_pl.project_point(Point3D.from_point2d(pt2), proj_dir))
                            break
                    # remove duplicated vertices from the list
                    rf_pts = [pt for i, pt in enumerate(rf_pts)
                              if not pt.is_equivalent(rf_pts[i - 1], tolerance)]
                    if current_poly is None or len(rf_pts) < 2:
                        return None  # point not inside a roof; invalid roof
                    # check that the first two vertices are not a sliver
                    if abs(rf_pts[0].x - rf_pts[1].x) < tolerance and \
                            abs(rf_pts[0].y - rf_pts[1].y) < tolerance:
                        rf_pts.pop(0)
                    # add the points to the Face3D vertices
                    rf_pts.reverse()
                    face_pts.extend(rf_pts)
                # make the final Face3D
                if len(face_pts) == 2:  # second point not inside a roof, invalid roof
                    return None
                wall_faces.append(Face3D(face_pts))
                pt1 = pt2  # increment for next segment

        return wall_faces

    def _roof_faces(self, all_room_poly, rel_rf_polys, rel_rf_planes, tolerance):
        """Generate Face3D for the Room Roofs when there are multiple Roof Polygons.

        Args:
            all_room_poly: A list of Polygon2D where each polygon represents either
                the boundary of the room or a hole.
            rel_rf_polys: A list of Polygon2D for the Roof geometries that are
                relevant to the Room2D.
            rel_rf_planes: A list of Plane objects for each Roof geometry that
                is relevant to the Room2D.
            tolerance: The distance value for absolute tolerance.

        Returns:
            A list of Face3D for the Roofs of the Room. Will be None if computing
            the roof geometry failed.
        """
        roof_faces = []
        proj_dir = Vector3D(0, 0, 1)  # direction to project onto Roof planes

        # create a BooleanPolygon for the Room2D
        room_polys = []
        for rom_poly in all_room_poly:
            rom_poly = rom_poly.remove_colinear_vertices(tolerance)
            room_polys.append((pb.BooleanPoint(pt.x, pt.y) for pt in rom_poly.vertices))
        b_room_poly = pb.BooleanPolygon(room_polys)
        room_poly_area = all_room_poly[0].area - sum(h.area for h in all_room_poly[1:])

        # find the boolean intersection with each roof polygon and project the result
        int_tol = tolerance / 100  # intersection tolerance must be finer
        roof_poly_area = 0
        for rf_poly, rf_plane in zip(rel_rf_polys, rel_rf_planes):
            # snap the polygons to one another to avoid tolerance issues
            rf_poly = rf_poly.remove_colinear_vertices(tolerance)
            for rom_poly in all_room_poly:
                rf_poly = rom_poly.snap_to_polygon(rf_poly, tolerance)
            rf_pts = (pb.BooleanPoint(pt.x, pt.y) for pt in rf_poly.vertices)
            b_rf_poly = pb.BooleanPolygon([rf_pts])
            try:
                int_result = pb.intersect(b_room_poly, b_rf_poly, int_tol)
            except Exception:  # intersection failed for some reason
                return None
            polys = [Polygon2D(tuple(Point2D(pt.x, pt.y) for pt in new_poly))
                     for new_poly in int_result.regions]
            if self.floor_geometry.has_holes and len(polys) > 1:
                # sort the polygons by area and check if any are inside the others
                polys.sort(key=lambda x: x.area, reverse=True)
                poly_groups = [[polys[0]]]
                for sub_poly in polys[1:]:
                    for i, pg in enumerate(poly_groups):
                        if pg[0].is_polygon_inside(sub_poly):  # it's a hole
                            poly_groups[i].append(sub_poly)
                            break
                    else:  # it's a separate Face3D
                        poly_groups.append([sub_poly])
                # convert all vertices to 3D and append the roof Face3D
                for pg in poly_groups:
                    roof_poly_area += pg[0].area - sum(h.area for h in pg[1:])
                    pg_3d = []
                    for shp in pg:
                        pt3s = tuple(
                            rf_plane.project_point(Point3D.from_point2d(pt2), proj_dir)
                            for pt2 in shp.vertices)
                        pg_3d.append(pt3s)
                    roof_faces.append(Face3D(pg_3d[0], rf_plane, holes=pg_3d[1:]))
            else:  # no holes are possible in the result; project all polygons directly
                for sub_poly in polys:
                    roof_poly_area += sub_poly.area
                    pt3s = tuple(
                        rf_plane.project_point(Point3D.from_point2d(pt2), proj_dir)
                        for pt2 in sub_poly.vertices)
                    roof_faces.append(Face3D(pt3s, rf_plane))

        # if all of the polygons didn't cover the Room2D, add extra horizontal roof faces
        tol_area = math.sqrt(all_room_poly[0].area) * tolerance
        if abs(room_poly_area - roof_poly_area) > tol_area:  # room not covered by roofs
            rm_z = self.ceiling_height
            subtract_geo = []
            for rf_face in roof_faces:
                proj_pts = [Point3D(pt.x, pt.y, rm_z) for pt in rf_face.boundary]
                if rf_face.has_holes:
                    hole_pts = [[Point3D(pt.x, pt.y, rm_z) for pt in hole]
                                for hole in rf_face.holes]
                    subtract_geo.append(Face3D(proj_pts, holes=hole_pts))
                else:
                    subtract_geo.append(Face3D(proj_pts))
            ang_tol = math.radians(1)
            ceil_vec = Vector3D(0, 0, self.floor_to_ceiling_height)
            ceil_geo = self.floor_geometry.move(ceil_vec)
            cover_faces = ceil_geo.coplanar_difference(subtract_geo, tolerance, ang_tol)
            roof_faces.extend(cover_faces)

        return roof_faces

    def _patch_vertical_gaps(self, room_polyface, roof_face_i, tolerance):
        """Patch any vertical gaps in a room_polyface.

        This method should fill all cases of vertical gaps within a Polyface3D.
        The only exception is if the vertical gap happens between two edges that
        overlap in plan but they share no end points. To catch this particular
        type of edge case, the _cap_planar_holes method should be used.

        Args:
            room_polyface: The non-solid Polyface3D to be patched with planar
                vertical Faces.
            roof_face_i: The indices of the polyface that correspond to the roof.
            tolerance: The distance value for absolute tolerance.

        Returns:
            The patched Room Polyface3D followed by an updated list of face indices
            that should become Roofs.
        """
        # get the faces and naked edges
        p_faces = list(room_polyface.faces)
        edges = [ed for ed in room_polyface.naked_edges
                 if not ed.is_vertical(tolerance)]
        vertical_faces = []

        # loop through the naked edges and try to match them
        matched_segs = set()
        edge_indices = list(range(len(edges)))
        for i, edge_1 in enumerate(edges):
            edge_1_2d = LineSegment2D.from_end_points(
                Point2D(edge_1.p1.x, edge_1.p1.y), Point2D(edge_1.p2.x, edge_1.p2.y))
            other_edges = edges[:i] + edges[i + 1:]
            other_is = edge_indices[:i] + edge_indices[i + 1:]
            for oi, edge_2 in zip(other_is, other_edges):
                e2p1 = Point2D(edge_2.p1.x, edge_2.p1.y)
                e2p2 = Point2D(edge_2.p2.x, edge_2.p2.y)
                if edge_1_2d.distance_to_point(e2p1) <= tolerance and \
                        edge_1_2d.distance_to_point(e2p2) <= tolerance:
                    # check to be sure that the segments have not been aired already
                    edge_pair_1, edge_pair_2 = (i, oi), (oi, i)
                    if edge_pair_1 in matched_segs:
                        continue
                    matched_segs.add(edge_pair_1)
                    matched_segs.add(edge_pair_2)
                    # build the points of the vertical face
                    norm = Vector3D(edge_1.v.x, edge_1.v.y, 0)
                    int_pl_1 = Plane(n=norm, o=edge_2.p1)
                    int_pl_2 = Plane(n=norm, o=edge_2.p2)
                    edge_1_1 = intersect_line3d_plane_infinite(edge_1, int_pl_1)
                    edge_1_2 = intersect_line3d_plane_infinite(edge_1, int_pl_2)
                    new_face3d = Face3D((edge_1_1, edge_1_2, edge_2.p1, edge_2.p2))
                    # find the grouping of points that is not self intersecting
                    if not new_face3d.is_self_intersecting and \
                            new_face3d.area > tolerance:
                        vertical_faces.append(new_face3d)
                    else:
                        new_face3d = Face3D((edge_1_1, edge_1_2, edge_2.p2, edge_2.p1))
                        if not new_face3d.is_self_intersecting and \
                                new_face3d.area > tolerance:
                            vertical_faces.append(new_face3d)
                        else:
                            f_poly = new_face3d.polygon2d
                            fs1, fs2 = f_poly.segments[0], f_poly.segments[2]
                            int_pt2d = fs1.intersect_line_ray(fs2)
                            if int_pt2d is not None:
                                int_pt = new_face3d.plane.xy_to_xyz(int_pt2d)
                                new_face3d1 = Face3D((edge_2.p1, int_pt, edge_1_1))
                                new_face3d2 = Face3D((edge_2.p2, int_pt, edge_1_2))
                                if new_face3d1.area > tolerance:
                                    vertical_faces.append(new_face3d1)
                                if new_face3d2.area > tolerance:
                                    vertical_faces.append(new_face3d2)

        # remove duplicated vertices in the resulting vertical faces
        clean_vert_faces = []
        for f in vertical_faces:
            try:
                clean_vert_faces.append(f.remove_duplicate_vertices(tolerance))
            except AssertionError:
                pass  # invalid sliver face

        # rebuild the room polyface
        st_v = -len(clean_vert_faces) - 1
        roof_face_i = list(range(st_v, st_v - len(roof_face_i), -1))
        p_faces.extend(clean_vert_faces)
        room_polyface = Polyface3D.from_faces(p_faces, tolerance)
        return room_polyface, roof_face_i

    def _cap_planar_holes(self, room_polyface, roof_face_i, tolerance):
        """Cap all planar holes in a room_polyface.

        Args:
            room_polyface: The non-solid Polyface3D to be patched with planar
                vertical Faces.
            roof_face_i: The indices of the polyface that correspond to the roof.
            tolerance: The distance value for absolute tolerance.

        Returns:
            The capped Room Polyface3D followed by an updated list of face indices
            that should become Roofs.
        """
        # join all of the naked edges into closed loops
        naked_edges = room_polyface.naked_edges
        if len(naked_edges) == 0:
            return room_polyface, roof_face_i
        joined_loops = Polyline3D.join_segments(naked_edges, tolerance)

        # create Face3D from any closed planar loops
        cap_faces = []
        for loop in joined_loops:
            if isinstance(loop, Polyline3D) and loop.is_closed(tolerance):
                cap_face = Face3D(loop.vertices[:-1])
                if cap_face.check_planar(tolerance, raise_exception=False):
                    cap_faces.append(cap_face)

        # remove duplicated vertices in the resulting cap faces
        clean_cap_faces = []
        for f in cap_faces:
            try:
                clean_cap_faces.append(f.remove_duplicate_vertices(tolerance))
            except AssertionError:
                pass  # invalid sliver face
        if len(clean_cap_faces) == 0:
            return room_polyface, roof_face_i

        # rebuild the room polyface
        st_v = -len(clean_cap_faces) + roof_face_i[0]
        roof_face_i = list(range(st_v, st_v - len(roof_face_i), -1))
        p_faces = list(room_polyface.faces) + clean_cap_faces
        room_polyface = Polyface3D.from_faces(p_faces, tolerance)
        return room_polyface, roof_face_i

    def _separate_disconnected_faces(self, room_polyface, roof_face_i, tolerance):
        """Separate Face3Ds from a room_polyface, with are not connected to the solid.

        This will also remove all degenerate faces from the Polyface3D geometry.

        Args:
            room_polyface: The non-solid Polyface3D for which disconnected faces
                will be separated out.
            roof_face_i: The indices of the polyface that correspond to the roof.
            tolerance: The distance value for absolute tolerance.

        Returns:
            A tuple with three elements.

                * room_polyface -- The new Room Polyface3D.

                * roof_face_i -- An updated list of roof face indices in the polyface.

                * disconnect_geometry -- A list of Face3D objects, which are
                    disconnected and were removed from the Polyface3D.
        """
        # remove disconnected roof geometries from the Polyface (eg. dormers)
        disconnect_geometry, room_ind, disconnect_i = [], [], []
        edge_i, edge_t = room_polyface.edge_indices, room_polyface.edge_types
        zip_obj = zip(room_polyface.face_indices, room_polyface.faces)
        for f_ind, (face, f3d) in enumerate(zip_obj):
            fe_types = []
            for fi in face:
                for i, vi in enumerate(fi):
                    try:
                        ind = edge_i.index((vi, fi[i - 1]))
                        et = edge_t[ind]
                    except ValueError:  # make sure reversed edge isn't there
                        try:
                            ind = edge_i.index((fi[i - 1], vi))
                            et = edge_t[ind]
                        except ValueError:  # an edge that was merged in overlapping
                            et = 1
                    fe_types.append(et)
            if sum(fe_types) <= 1:  # disconnected face found!
                disconnect_i.append(f_ind)
            else:
                try:
                    f3d.remove_duplicate_vertices(tolerance)
                    room_ind.append(f_ind)
                except AssertionError:  # degenerate sliver face to be removed
                    disconnect_i.append(f_ind)

        if len(disconnect_i) != 0:
            # process the roof indices
            new_roof_face_i = []
            for exist_i in roof_face_i:
                pos_ei = exist_i + len(room_polyface)
                for del_i in reversed(disconnect_i):
                    if del_i == pos_ei:  # deleted roof
                        break
                else:
                    new_roof_face_i.append(exist_i)
            roof_face_i = new_roof_face_i
            # rebuild the Polyface3D
            p_faces = [room_polyface.faces[f_ind] for f_ind in room_ind]
            disconnect_geometry = [room_polyface.faces[f_ind] for f_ind in disconnect_i]
            room_polyface = Polyface3D.from_faces(p_faces, tolerance)
        return room_polyface, roof_face_i, disconnect_geometry

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

        # return the flipped lists
        return new_bcs, new_win_pars, new_shd_pars

    def _split_walls_along_height(self, hb_room, tolerance, plenums=False):
        """Split adjacent walls to ensure matching surface areas in to_honeybee workflow.

        Args:
            hb_room: A non-split Honeybee Room representation of this Room2D.
            tolerance: The minimum distance in z values of floor_height and
                floor_to_ceiling_height at which adjacent Faces will be split.
            plenums: A boolean to note whether the resulting model has auto-generated
                plenums, which will determine the default boundary condition of
                any split wall segments. (Default: False).
        """
        new_faces = [hb_room[0]]
        for i, bc in enumerate(self._boundary_conditions):
            face = hb_room[i + 1]
            if not isinstance(bc, Surface):
                new_faces.append(face)
            else:
                try:
                    adj_rm = self._parent.room_by_identifier(
                        bc.boundary_condition_objects[-1])
                except ValueError:  # missing adjacency in Story; just pass invalid BC
                    new_faces.append(face)
                    continue
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
                        below_face.boundary_condition = bcs.ground \
                            if self.is_ground_contact and not plenums else bcs.adiabatic
                    except AttributeError:
                        pass  # honeybee_energy is not loaded; no adiabatic BC
                    try:
                        below_face.boundary_condition = bcs.outdoors \
                            if adj_rm.is_top_exposed and not plenums else bcs.adiabatic
                    except AttributeError:
                        pass  # honeybee_energy is not loaded; no adiabatic BC
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
                        below_face.boundary_condition = bcs.ground \
                            if self.is_ground_contact and not plenums else bcs.adiabatic
                    except AttributeError:
                        pass  # honeybee_energy is not loaded; no adiabatic BC
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
                        above_face.boundary_condition = bcs.outdoors \
                            if adj_rm.is_top_exposed and not plenums else bcs.adiabatic
                    except AttributeError:
                        pass  # honeybee_energy is not loaded; no adiabatic BC
                    new_faces.extend([mid_face, above_face])
        new_faces.append(hb_room[-1])
        return new_faces

    def _reassign_split_windows(self, face, i, tolerance):
        """Re-assign WindowParameters to any base surface that has been split.

        Args:
            face: Honeybee Face to which windows will be re-assigned.
            i: The index of the window_parameters that correspond to the face
            tolerance: The tolerance, which will be used to re-assign windows.
        """
        glz_par = self._window_parameters[i]
        if glz_par is not None:
            face.remove_sub_faces()
            glz_par.add_window_to_face(face, tolerance)

    @staticmethod
    def _segment_wall_face(room, segment, tolerance):
        """Get a Wall Face that corresponds with a certain wall segment.

        Args:
            room: A Honeybee Room from which a wall Face will be returned.
            segment: A LineSegment3D along one of the walls of the room.
            tolerance: The maximum difference between values at which point vertices
                are considered to be the same.
        """
        for face in room.faces:
            if isinstance(face.type, (Wall, AirBoundary)):
                fg = face.geometry
                try:
                    verts = fg._remove_colinear(
                        fg._boundary, fg.boundary_polygon2d, tolerance)
                except AssertionError:
                    return None
                for v1 in verts:
                    if segment.p1.is_equivalent(v1, tolerance):
                        p2 = segment.p2
                        for v2 in verts:
                            if p2.is_equivalent(v2, tolerance):
                                return face

    def _match_and_transfer_wall_props(self, new_room, tolerance):
        """Transfer wall properties of matching segments between this room and a new one.

        All wall properties are transferred exactly as they are when segments
        are perfectly equal between this room and the new room. When segments
        are colinear/overlapping but the segment on the new_room is shorter than
        that on this room, the wall properties on this room will be split in
        order to assign them correctly to the new room. When a given segment
        of the new_room is not overlapping/colinear with any segment of this
        room, it will be given default properties with an outdoor boundary
        condition.

        This all makes this method suitable for preserving properties across
        operations that trim or split the original room to make the new_room.

        Args:
            new_room: An new Room2D to which wall properties will be transferred.
        """
        # get the relevant original segments by copying the lists on this Room2D
        rel_segs = self.floor_segments
        rel_win = self._window_parameters
        rel_shd = self._shading_parameters
        rel_abs = self.air_boundaries
        rel_bcs = []
        for bc in self._boundary_conditions:
            if not isinstance(bc, Surface):
                rel_bcs.append(bc)
            else:  # Surface boundary conditions can mess up window splitting
                rel_bcs.append(bcs.outdoors)
        # build up new lists of parameters if the segments match
        new_bcs, new_win, new_shd, new_abs = {}, {}, {}, {}
        for k, seg1 in enumerate(rel_segs):
            m_win_segs, m_i = [], []
            for i, seg2 in enumerate(new_room.floor_segments):
                if seg1.distance_to_point(seg2.p1) <= tolerance and \
                        seg1.distance_to_point(seg2.p2) <= tolerance:  # colinear
                    new_bcs[i] = rel_bcs[k]
                    new_shd[i] = rel_shd[k]
                    new_abs[i] = rel_abs[k]
                    m_win_segs.append(seg2)
                    m_i.append(i)
            # split the window parameters across the matched segments
            wp_par_to_split = rel_win[k]
            if wp_par_to_split is None:
                for i in m_i:
                    new_win[i] = None
            else:
                full_len = sum(sg.length for sg in m_win_segs)
                if abs(seg1.length - full_len) <= tolerance:  # all segments accounted
                    if len(m_i) == 1:  # no change to the segment
                        new_win[m_i[0]] = wp_par_to_split
                    else:  # windows to be split
                        split_par = wp_par_to_split.split(m_win_segs, tolerance)
                        for i, w_par in zip(m_i, split_par):
                            new_win[i] = w_par
                else:  # not all segment accounted; trim each window par from original
                    for i, n_seg in zip(m_i, m_win_segs):
                        new_win[i] = wp_par_to_split.trim(seg1, n_seg, tolerance)

        # assign the matched properties to the new room
        final_bcs, final_win, final_shd, final_abs = [], [], [], []
        for i in range(len(new_room)):
            try:
                final_bcs.append(new_bcs[i])
                final_win.append(new_win[i])
                final_shd.append(new_shd[i])
                final_abs.append(new_abs[i])
            except KeyError:  # segment not matched to any in existing room
                final_bcs.append(bcs.outdoors)
                final_win.append(None)
                final_shd.append(None)
                final_abs.append(False)
        new_room.boundary_conditions = final_bcs
        new_room.window_parameters = final_win
        new_room.shading_parameters = final_shd
        new_room.air_boundaries = final_abs

    @staticmethod
    def _remove_colinear_props(
            pts_3d, pts_2d, segs_2d, bound_cds, win_pars, ftc_height, tolerance):
        """Remove colinear vertices across a boundary while merging window properties."""
        new_vertices, new_bcs, new_w_par = [], [], []
        skip = 0  # track the number of vertices being skipped/removed
        m_segs, m_bcs, m_w_par = [], [], []
        # loop through vertices and remove all cases of colinear verts
        for i, _v in enumerate(pts_2d):
            m_segs.append(segs_2d[i - 2])
            m_bcs.append(bound_cds[i - 2])
            m_w_par.append(win_pars[i - 2])
            _a = pts_2d[i - 2 - skip].determinant(pts_2d[i - 1]) + \
                pts_2d[i - 1].determinant(_v) + _v.determinant(pts_2d[i - 2 - skip])
            if abs(_a) >= tolerance:  # vertex is not colinear; add vertex and merge
                new_vertices.append(pts_3d[i - 1])
                if all(not isinstance(bc, Ground) for bc in m_bcs):
                    new_bcs.append(bcs.outdoors)
                    if all(wp is None for wp in m_w_par):
                        new_w_par.append(None)
                    elif len(m_w_par) == 1:
                        new_w_par.append(m_w_par[0])
                    else:
                        new_wp = DetailedWindows.merge(m_w_par, m_segs, ftc_height)
                        new_w_par.append(new_wp)
                else:
                    new_bcs.append(bcs.ground)
                    new_w_par.append(None)
                skip = 0
                m_bcs, m_w_par, m_segs = [], [], []
            else:  # vertex is colinear; continue
                skip += 1
        # catch case of last two vertices being equal but distinct from first point
        if skip != 0 and pts_3d[-2].is_equivalent(pts_3d[-1], tolerance):
            _a = pts_2d[-3].determinant(pts_2d[-1]) + \
                pts_2d[-1].determinant(pts_2d[0]) + pts_2d[0].determinant(pts_2d[-3])
            if abs(_a) >= tolerance:
                new_vertices.append(pts_3d[-1])
                if not isinstance(bound_cds[-2], Ground):
                    new_bcs.append(bcs.outdoors)
                    new_w_par.append(win_pars[-2])
                else:
                    new_bcs.append(bcs.ground)
                    new_w_par.append(None)
        elif skip != 0:
            w_par_for_merge = m_w_par + [new_w_par[0]]
            if not all(wp is None for wp in w_par_for_merge):
                segs_for_merge = m_segs + [segs_2d[-1]]
                new_w_par[0] = DetailedWindows.merge(
                    w_par_for_merge, segs_for_merge, ftc_height)
        # move the first properties to the end to match with the vertices
        new_bcs.append(new_bcs.pop(0))
        new_w_par.append(new_w_par.pop(0))
        return new_vertices, new_bcs, new_w_par

    @staticmethod
    def _adjacency_grouping(rooms, adj_finding_function):
        """Group Room2Ds together according to an adjacency finding function.

        Args:
            rooms: A list of Room2Ds to be grouped by their adjacency.
            adj_finding_function: A function that denotes which rooms are adjacent
                to another.

        Returns:
            A list of list with each sub-list containing rooms that share adjacencies.
        """
        # create a room lookup table and duplicate the list of rooms
        room_lookup = {rm.identifier: rm for rm in rooms}
        all_rooms = list(rooms)
        adj_network = []

        # loop through the rooms and find air boundary adjacencies
        for room in all_rooms:
            adj_ids = adj_finding_function(room)
            if len(adj_ids) == 0:  # a room that is its own solar enclosure
                adj_network.append([room])
            else:  # there are other adjacent rooms to find
                local_network = [room]
                local_ids, first_id = set(adj_ids), room.identifier
                while len(adj_ids) != 0:
                    # add the current rooms to the local network
                    adj_objs = [room_lookup[rm_id] for rm_id in adj_ids]
                    local_network.extend(adj_objs)
                    adj_ids = []  # reset the list of new adjacencies
                    # find any rooms that are adjacent to the adjacent rooms
                    for obj in adj_objs:
                        all_new_ids = adj_finding_function(obj)
                        new_ids = [rid for rid in all_new_ids
                                   if rid not in local_ids and rid != first_id]
                        for rm_id in new_ids:
                            local_ids.add(rm_id)
                        adj_ids.extend(new_ids)
                # after the local network is understood, clean up duplicated rooms
                adj_network.append(local_network)
                i_to_remove = [i for i, room_obj in enumerate(all_rooms)
                               if room_obj.identifier in local_ids]
                for i in reversed(i_to_remove):
                    all_rooms.pop(i)
        return adj_network

    @staticmethod
    def _find_adjacent_rooms(room):
        """Find the identifiers of all rooms with adjacency to a room."""
        adj_rooms = []
        for bc in room._boundary_conditions:
            if isinstance(bc, Surface):
                adj_rooms.append(bc.boundary_condition_objects[-1])
        return adj_rooms

    @staticmethod
    def _find_adjacent_air_boundary_rooms(room):
        """Find the identifiers of all rooms with air boundary adjacency to a room."""
        adj_rooms = []
        for bc, ab in zip(room._boundary_conditions, room.air_boundaries):
            if ab and isinstance(bc, Surface):
                adj_rooms.append(bc.boundary_condition_objects[-1])
        return adj_rooms

    @staticmethod
    def _segments_along_polygon(
            polygon, rel_segs, rel_bcs, rel_win, rel_shd, rel_abs,
            new_bcs, new_win, new_shd, new_abs, new_flr_height, tol):
        """Find the segments along a polygon and add their properties to new lists."""
        new_segs = []
        for seg in polygon.segments:
            seg_segs, seg_bcs, seg_win, seg_shd, seg_abs = [], [], [], [], []
            # collect the room segments and properties along the boundary
            for i, rs in enumerate(rel_segs):
                if seg.distance_to_point(rs.p1) <= tol and \
                        seg.distance_to_point(rs.p2) <= tol:  # colinear
                    seg_segs.append(rs)
                    seg_bcs.append(rel_bcs[i])
                    seg_win.append(rel_win[i])
                    seg_shd.append(rel_shd[i])
                    seg_abs.append(rel_abs[i])
            if len(seg_segs) == 0:
                Room2D._add_dummy_segment(
                    seg.p1, seg.p2, new_segs, new_bcs, new_win, new_shd, new_abs)
                continue
            # sort the Room2D segments along the polygon segment
            seg_dists = [seg.p1.distance_to_point(s.p1) for s in seg_segs]
            sort_ind = [i for _, i in sorted(zip(seg_dists, range(len(seg_dists))))]
            seg_segs = [seg_segs[i] for i in sort_ind]
            seg_bcs = [seg_bcs[i] for i in sort_ind]
            seg_win = [seg_win[i] for i in sort_ind]
            seg_shd = [seg_shd[i] for i in sort_ind]
            seg_abs = [seg_abs[i] for i in sort_ind]
            # identify any gaps and add dummy segments
            p1_dists = sorted(seg_dists)
            p2_dists = [seg.p1.distance_to_point(s.p2) for s in seg_segs]
            last_d, last_seg = 0, None
            for i, (p1d, p2d) in enumerate(zip(p1_dists, p2_dists)):
                if p1d < last_d - tol:  # overlapping segment; ignore it
                    continue
                elif p1d > last_d + tol:  # add a dummy segment for the gap
                    st_pt = last_seg.p2 if last_seg is not None else seg.p1
                    Room2D._add_dummy_segment(
                        st_pt, seg_segs[i].p1, new_segs, new_bcs,
                        new_win, new_shd, new_abs)
                # add the segment
                new_segs.append(seg_segs[i])
                new_bcs.append(seg_bcs[i])
                new_win.append(seg_win[i])
                new_shd.append(seg_shd[i])
                new_abs.append(seg_abs[i])
                last_d = p2d
                last_seg = seg_segs[i]
        return [Point3D(s.p1.x, s.p1.y, new_flr_height) for s in new_segs]

    @staticmethod
    def _add_dummy_segment(p1, p2, new_segs, new_bcs, new_win, new_shd, new_abs):
        """Add a dummy segment to lists of properties that are being built."""
        new_segs.append(LineSegment2D.from_end_points(p1, p2))
        new_bcs.append(bcs.outdoors)
        new_win.append(None)
        new_shd.append(None)
        new_abs.append(False)

    @staticmethod
    def _intersect_line2d_infinite(line_ray_a, line_ray_b):
        """Get the intersection between a Ray2Ds extended infinitely.

        Args:
            line_ray_a: A Ray2D object.
            line_ray_b: Another Ray2D object.

        Returns:
            Point2D of intersection if it exists. None if lines are parallel.
        """
        d = line_ray_b.v.y * line_ray_a.v.x - line_ray_b.v.x * line_ray_a.v.y
        if d == 0:
            return None
        dy = line_ray_a.p.y - line_ray_b.p.y
        dx = line_ray_a.p.x - line_ray_b.p.x
        ua = (line_ray_b.v.x * dy - line_ray_b.v.y * dx) / d
        return Point2D(line_ray_a.p.x + ua * line_ray_a.v.x,
                       line_ray_a.p.y + ua * line_ray_a.v.y)

    def __copy__(self):
        new_r = Room2D(self.identifier, self._floor_geometry,
                       self.floor_to_ceiling_height,
                       self._boundary_conditions[:])  # copy boundary condition list
        new_r._display_name = self._display_name
        new_r._user_data = None if self.user_data is None else self.user_data.copy()
        new_r._parent = self._parent
        new_wp = []
        for wp in self._window_parameters:
            nwp = wp.duplicate() if wp is not None else None
            new_wp.append(nwp)
        new_r._window_parameters = new_wp
        new_r._shading_parameters = self._shading_parameters[:]  # copy shading list
        new_r._air_boundaries = self._air_boundaries[:] \
            if self._air_boundaries is not None else None
        new_r._is_ground_contact = self._is_ground_contact
        new_r._is_top_exposed = self._is_top_exposed
        new_r._skylight_parameters = self._skylight_parameters.duplicate() \
            if self._skylight_parameters is not None else None
        new_r._abridged_properties = self._abridged_properties
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
