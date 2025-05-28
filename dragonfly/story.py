# coding: utf-8
"""Dragonfly Story."""
from __future__ import division
import math

from ladybug_geometry.geometry2d import Vector2D, Polygon2D
from ladybug_geometry.geometry3d import Vector3D, Point3D, Ray3D, Polyline3D, \
    Face3D, Polyface3D

from honeybee.typing import float_positive, int_in_range, clean_string, \
    clean_and_id_string, valid_string, invalid_dict_error
from honeybee.boundarycondition import boundary_conditions as bcs
from honeybee.boundarycondition import Outdoors, Surface
from honeybee.facetype import AirBoundary
from honeybee.facetype import face_types as ftyp
from honeybee.altnumber import autocalculate
from honeybee.shade import Shade

from ._base import _BaseGeometry
from .room2d import Room2D
from .roof import RoofSpecification
from .windowparameter import DetailedWindows
from .properties import StoryProperties
import dragonfly.writer.story as writer


class Story(_BaseGeometry):
    """A Story of a building defined by an extruded Room2Ds.

    Args:
        identifier: Text string for a unique Story ID. Must be < 100 characters
            and not contain any spaces or special characters.
        room_2ds: An array of dragonfly Room2D objects that together form an
            entire story of a building.
        floor_to_floor_height: A number for the distance from the floor plate of
            this Story to the floor of the story above this one (if it exists).
            This should be in the same units system as the input room_2d geometry.
            If None, this value will be the maximum floor_to_ceiling_height of the
            input room_2ds plus any difference between the Story floor height
            and the room floor heights. (Default: None)
        floor_height: A number for the absolute floor height of the Story.
            If None, this will be the minimum floor height of all the Story's
            room_2ds, which is suitable for cases where there are no floor
            plenums. (Default: None).
        multiplier: An integer that denotes the number of times that this
            Story is repeated over the height of the building. (Default: 1).
        roof: An optional RoofSpecification object containing geometry and instructions
            for generating sloped roofs over a Story. The RoofSpecification will only
            affect the child Room2Ds that have a True is_top_exposed property
            and it will only be utilized in translation to Honeybee when the Story
            multiplier is 1. If None, all Room2D ceilings will be flat. (Default: None).
        type: Text to indicate the type of story that this object represents.
            Choose from the options below. (Default: DifferentialDryBulb).

            * Standard
            * CeilingPlenum
            * FloorPlenum

    Properties:
        * identifier
        * display_name
        * full_id
        * room_2ds
        * floor_to_floor_height
        * multiplier
        * roof
        * type
        * is_plenum
        * has_plenums
        * has_zones
        * zone_dict
        * parent
        * has_parent
        * floor_height
        * floor_area
        * exterior_wall_area
        * exterior_aperture_area
        * volume
        * is_above_ground
        * min
        * max
        * median_room2d_floor_height
        * user_data
    """
    STORY_TYPES = ('Standard', 'CeilingPlenum', 'FloorPlenum')
    __slots__ = ('_room_2ds', '_floor_to_floor_height', '_floor_height',
                 '_multiplier', '_roof', '_type', '_parent')

    def __init__(self, identifier, room_2ds, floor_to_floor_height=None,
                 floor_height=None, multiplier=1, roof=None, type='Standard'):
        """A Story of a building defined by an extruded Floor2Ds."""
        _BaseGeometry.__init__(self, identifier)  # process the identifier

        # process the Room2Ds and story geometry
        self.room_2ds = room_2ds

        # process the input properties
        self.floor_height = floor_height
        self.floor_to_floor_height = floor_to_floor_height
        self.multiplier = multiplier
        self.roof = roof
        self.type = type

        self._parent = None  # _parent will be set when Story is added to a Building
        self._properties = StoryProperties(self)  # properties for extensions

    @classmethod
    def from_dict(cls, data, tolerance=0):
        """Initialize a Story from a dictionary.

        Args:
            data: A dictionary representation of a Story object.
            tolerance: The maximum difference between z values at which point vertices
                are considered to be in the same horizontal plane. This is used to check
                that all vertices of the input floor_geometry lie in the same horizontal
                floor plane. Default is 0, which will not perform any check.
        """
        # check the type of dictionary
        assert data['type'] == 'Story', 'Expected Story dictionary. ' \
            'Got {}.'.format(data['type'])

        # serialize the rooms
        rooms = []
        for r_dict in data['room_2ds']:
            try:
                rooms.append(Room2D.from_dict(r_dict, tolerance))
            except Exception as e:
                invalid_dict_error(r_dict, e)

        # check if any room boundaries were reversed
        dict_pts = [tuple(room['floor_boundary'][0]) for room in data['room_2ds']]
        room_pts = [(rm.floor_geometry[0].x, rm.floor_geometry[0].y) for rm in rooms]
        not_reversed = [dpt == rpt for dpt, rpt in zip(dict_pts, room_pts)]

        # ensure Surface boundary conditions are correct if floors were reversed
        if not all(not_reversed):  # some room floors have been reversed
            bcs_to_update = []
            for not_revd, room in zip(not_reversed, rooms):
                if not not_revd:  # double negative! reversed room boundary
                    for i, bc in enumerate(room._boundary_conditions):
                        if isinstance(bc, Surface):  # segment must be updated
                            newid = '{}..Face{}'.format(room.identifier, i + 1)
                            bc_room = bc.boundary_condition_objects[1]
                            bc_f_i = bc.boundary_condition_objects[0].split('..Face')[-1]
                            bc_tup = (bc_room, int(bc_f_i) - 1, (newid, room.identifier))
                            bcs_to_update.append(bc_tup)
            for bc_tup in bcs_to_update:  # update any reversed boundary conditions
                adj_room = bc_tup[0]
                for not_revd, room in zip(not_reversed, rooms):  # find adjacent room
                    if room.identifier == adj_room:
                        bc_to_update = room._boundary_conditions[bc_tup[1]] if not_revd \
                            else room._boundary_conditions[-1 - bc_tup[1]]
                        bc_to_update._boundary_condition_objects = bc_tup[2]

        # process the floor_to_floor_height and the multiplier
        f2fh = data['floor_to_floor_height'] if 'floor_to_floor_height' in data \
            and data['floor_to_floor_height'] != autocalculate.to_dict() else None
        fh = data['floor_height'] if 'floor_height' in data \
            and data['floor_height'] != autocalculate.to_dict() else None
        mult = data['multiplier'] if 'multiplier' in data else 1
        s_type = data['story_type'] if 'story_type' in data else 'Standard'

        # process the roof specification if it exists
        roof = RoofSpecification.from_dict(data['roof']) if 'roof' in data \
            and data['roof'] is not None else None

        # create the story object
        story = Story(data['identifier'], rooms, f2fh, fh, mult, roof, s_type)
        if 'display_name' in data and data['display_name'] is not None:
            story._display_name = data['display_name']
        if 'user_data' in data and data['user_data'] is not None:
            story.user_data = data['user_data']

        # load any extension attributes assigned to the story
        if data['properties']['type'] == 'StoryProperties':
            story.properties._load_extension_attr_from_dict(data['properties'])
        return story

    @classmethod
    def from_honeybee(cls, identifier, rooms, tolerance=0.01):
        """Initialize a Story from a list of Honeybee Rooms.

        Args:
            identifier: Text string for a unique Story ID. Must be < 100 characters
                and not contain any spaces or special characters.
            rooms: A list of Honeybee Room objects.
            tolerance: The maximum difference between values at which point vertices
                are considered to be the same. (Default: 0.01,
                suitable for objects in Meters).
        """
        # create the Room2Ds from the Honeybee Rooms
        room_2ds, rfs = [], []
        for hb_room in rooms:
            try:
                room_2ds.append(Room2D.from_honeybee(hb_room, tolerance))
                for face in hb_room.roof_ceilings:
                    if face.tilt > 1:  # use one degree tolerance
                        rfs.append(face.geometry)
            except Exception:  # invalid Honeybee Room that is not a closed solid
                msg = 'Room "{}" is not a closed solid and cannot be converted to ' \
                    'a Room2D.\nTry using the "ExtrudedOnly" option to convert ' \
                    'the Honeybee Model to Dragonfly'.format(hb_room.display_name)
                raise ValueError(msg)
        s_type = 'CeilingPlenum' \
            if all(hb_room.exclude_floor_area for hb_room in rooms) else 'Standard'

        # re-set the adjacencies in relation to the Room2D segments
        room_2ds = [room for room in room_2ds if room is not None]
        room_2ds = cls._reset_adjacencies_from_honeybee(room_2ds, tolerance)

        # create the roof geometry if it exists
        roof = RoofSpecification.from_geometry_to_join(rfs, tolerance) \
            if len(rfs) != 0 else None
        return cls(identifier, room_2ds, roof=roof, type=s_type)

    @staticmethod
    def _reset_adjacencies_from_honeybee(room_2ds, tolerance):
        """Re-set the adjacencies in relation to the Room2D segments.

        It is customary to run this method after converting the Story from Honeybee.
        This will ensure that any Surface boundary conditions from the Honeybee
        translation survive the translation process to the Dragonfly conventions
        of Surface boundary conditions.

        Args:
            room_2ds: A list of Room2Ds of the same Story for which adjacencies
                will be reset.
            tolerance: The maximum difference between values at which point vertices
                are considered to be the same.
        """
        all_adj_faces = [[x for x, bc in enumerate(room_1._boundary_conditions)
                         if isinstance(bc, Surface)] for room_1 in room_2ds]
        for i, room_1 in enumerate(room_2ds):
            try:
                for x, room_2 in enumerate(room_2ds[i + 1:]):
                    if not Polygon2D.overlapping_bounding_rect(
                            room_1._floor_geometry.boundary_polygon2d,
                            room_2._floor_geometry.boundary_polygon2d, tolerance):
                        continue  # no overlap in bounding rect; adjacency impossible
                    for j, seg_1 in enumerate(room_1.floor_segments_2d):
                        for k, seg_2 in enumerate(room_2.floor_segments_2d):
                            if isinstance(room_2._boundary_conditions[k], Surface):
                                if seg_1.distance_to_point(seg_2.p1) <= tolerance and \
                                        seg_1.distance_to_point(seg_2.p2) <= tolerance:
                                    if abs(seg_1.length - seg_2.length) <= tolerance:
                                        # set the boundary conditions of the segments
                                        room_1.set_adjacency(room_2, j, k)
                                        try:
                                            adj_f_1 = all_adj_faces[i]
                                            adj_f_2 = all_adj_faces[i + x + 1]
                                            adj_f_1.pop(adj_f_1.index(j))
                                            adj_f_2.pop(adj_f_2.index(k))
                                        except ValueError:
                                            pass  # from honeybee broke adjacency
                                        break
            except IndexError:
                pass  # we have reached the end of the list of zones
        # set any adjacencies to default that were not set
        try:
            default_adj_bc = bcs.adiabatic
            remove_win = True
        except AttributeError:
            default_adj_bc = bcs.outdoors
            remove_win = False
        for r_i, adj_faces in enumerate(all_adj_faces):
            for seg_i in adj_faces:
                room_2ds[r_i]._boundary_conditions[seg_i] = default_adj_bc
                room_2ds[r_i]._air_boundaries[seg_i] = False
                if remove_win:
                    room_2ds[r_i]._window_parameters[seg_i] = None
        return room_2ds

    @property
    def room_2ds(self):
        """Get or set a tuple of Room2D objects that form the Story."""
        return self._room_2ds

    @room_2ds.setter
    def room_2ds(self, value):
        if not isinstance(value, tuple):
            value = tuple(value)
        assert len(value) > 0, 'Story must have at least one Room2D.'
        for room in value:
            assert isinstance(room, Room2D), \
                'Expected dragonfly Room2D. Got {}'.format(type(room))
            room._parent = self
        self._room_2ds = value

    @property
    def floor_to_floor_height(self):
        """Get or set a number for the distance from this floor plate to the next one."""
        return self._floor_to_floor_height

    @floor_to_floor_height.setter
    def floor_to_floor_height(self, value):
        if value is None:
            ciel_hgt = max([room.ceiling_height for room in self._room_2ds])
            value = ciel_hgt - self.floor_height
        self._floor_to_floor_height = float_positive(value, 'floor-to-floor height')

    @property
    def floor_height(self):
        """Get or set a number for the absolute floor height of the Story.

        This will be the minimum floor height of all the Story's room_2ds unless
        specified otherwise.
        """
        return self._floor_height

    @floor_height.setter
    def floor_height(self, value):
        if value is None:
            value = min([room.floor_height for room in self._room_2ds])
        self._floor_height = float(value)

    @property
    def multiplier(self):
        """Get or set an integer noting how many times this Story is repeated.

        Multipliers are used to speed up the calculation when similar Stories are
        repeated more than once. Essentially, a given simulation with the
        Story is run once and then the result is multiplied by the multiplier.
        This comes with some inaccuracy. However, this error might not be too large
        if the Stories are similar enough and it can often be worth it since it can
        greatly speed up the calculation.

        For more information on multipliers in EnergyPlus see EnergyPlus Tips and Tricks:
        https://bigladdersoftware.com/epx/docs/9-1/tips-and-tricks-using-energyplus/\
using-multipliers-zone-and-or-window.html
        """
        return self._multiplier

    @multiplier.setter
    def multiplier(self, value):
        self._multiplier = int_in_range(value, 1, input_name='room multiplier')

    @property
    def roof(self):
        """Get or set a RoofSpecification with instructions for generating sloped roofs.

        The RoofSpecification will only affect the child Room2Ds that have a True
        is_top_exposed property and it will only be utilized in translation to
        Honeybee when the Story multiplier is 1.
        """
        return self._roof

    @roof.setter
    def roof(self, value):
        if value is not None:
            assert isinstance(value, RoofSpecification), \
                'Expected dragonfly RoofSpecification. Got {}'.format(type(value))
            value._parent = self
        self._roof = value

    @property
    def type(self):
        """Get or set text to indicate the type of Story.

        Choose from the following options:

        * Standard
        * CeilingPlenum
        * FloorPlenum
        """
        return self._type

    @type.setter
    def type(self, value):
        clean_input = valid_string(value).lower()
        for key in self.STORY_TYPES:
            if key.lower() == clean_input:
                value = key
                break
        else:
            raise ValueError(
                'Story type {} is not recognized.\nChoose from the '
                'following:\n{}'.format(value, self.STORY_TYPES))
        self._type = value

    @property
    def is_plenum(self):
        """Get a boolean for whether the Room2Ds of the Story represent plenums.

        If True, all Room2Ds in the Story are translated to 3D with a True
        exclude_floor_area property.
        """
        return self._type in ('CeilingPlenum', 'FloorPlenum')

    @property
    def has_plenums(self):
        """Get a boolean for whether Room2Ds on this Story have assigned plenum depths.
        """
        for room in self._room_2ds:
            if room.ceiling_plenum_depth != 0 or room.floor_plenum_depth != 0:
                return True
        return False

    @property
    def has_zones(self):
        """Get a boolean for whether any Rooms in the Story have zones assigned."""
        return any(room._zone is not None for room in self._room_2ds)

    @property
    def zone_dict(self):
        """Get dictionary of Rooms with zone identifiers as the keys.

        This is useful for grouping rooms by their Zone for export.
        """
        zones = {}
        for room in self._room_2ds:
            try:
                zones[room.zone].append(room)
            except KeyError:  # first room to be found in the zone
                zones[room.zone] = [room]
        return zones

    @property
    def parent(self):
        """Parent Building if assigned. None if not assigned."""
        return self._parent

    @property
    def has_parent(self):
        """Boolean noting whether this Story has a parent Building."""
        return self._parent is not None

    @property
    def highest_plenum_floor_height(self):
        """Get a number for the highest floor height in the Story including plenums.

        This property is useful for checking that roof geometries do not
        collide with a floor.
        """
        return max(room.highest_plenum_floor_height for room in self._room_2ds)

    @property
    def floor_area(self):
        """Get a number for the total floor area in the Story.

        Note that this property is for one Story and does NOT use the multiplier.
        However, if this Story is assigned to a parent Building with room_3ds,
        it will include the floor area of these 3D Rooms (without the room multiplier).
        """
        flr_area = sum([room.floor_area for room in self._room_2ds])
        if self.has_parent and self.parent.has_room_3ds:
            for r in self.parent.room_3ds_by_story(self.display_name):
                if not r.exclude_floor_area:
                    flr_area += r.floor_area
        return flr_area

    @property
    def exterior_wall_area(self):
        """Get a number for the total exterior wall area in the Story.

        Note that this property is for one story and does NOT use the multiplier.
        However, if this Story is assigned to a parent Building with room_3ds,
        it will include the wall area of these 3D Rooms (without the room multiplier).
        """
        ewa = sum([room.exterior_wall_area for room in self._room_2ds])
        if self.has_parent and self.parent.has_room_3ds:
            for r in self.parent.room_3ds_by_story(self.display_name):
                ewa += r.exterior_wall_area
        return ewa

    @property
    def exterior_aperture_area(self):
        """Get a number for the total exterior aperture area in the Story.

        Note that this property is for one story and does NOT use the multiplier.
        However, if this Story is assigned to a parent Building with room_3ds,
        it will include the exterior wall aperture area of these 3D Rooms (without
        the room multiplier).
        """
        eaa = sum([room.exterior_aperture_area for room in self._room_2ds])
        if self.has_parent and self.parent.has_room_3ds:
            for r in self.parent.room_3ds_by_story(self.display_name):
                eaa += r.exterior_wall_aperture_area
        return eaa

    @property
    def volume(self):
        """Get a number for the volume of all the Rooms in the Story.

        Note that this property is for one story and does NOT use the multiplier.
        However, if this Story is assigned to a parent Building with room_3ds,
        it will include the volume of these 3D Rooms (without the room multiplier).
        """
        vol = sum([room.volume for room in self._room_2ds])
        if self.has_parent and self.parent.has_room_3ds:
            for r in self.parent.room_3ds_by_story(self.display_name):
                vol += r.volume
        return vol

    @property
    def is_above_ground(self):
        """Get a boolean to note if this Story is above the ground.

        The story is considered above the ground if at least one of its Room2Ds
        has an outdoor boundary condition for its walls.
        """
        for room in self._room_2ds:
            for bc in room._boundary_conditions:
                if isinstance(bc, Outdoors):
                    return True
        return False

    @property
    def min(self):
        """Get a Point2D for the min bounding rectangle vertex in the XY plane.

        This is useful in calculations to determine if this Story is in proximity
        to others.
        """
        return self._calculate_min(self._room_2ds)

    @property
    def max(self):
        """Get a Point2D for the max bounding rectangle vertex in the XY plane.

        This is useful in calculations to determine if this Story is in proximity
        to others.
        """
        return self._calculate_max(self._room_2ds)

    @property
    def median_room2d_floor_height(self):
        """Get the median floor height of the Room2Ds of this Story."""
        median_i = int(len(self._room_2ds) / 2)
        flr_hgt = [room.floor_height for room in self._room_2ds]
        flr_hgt.sort()
        return flr_hgt[median_i]

    def floor_geometry(self, tolerance=0.01):
        """Get a ladybug_geometry Polyface3D object representing the floor plate.

        Args:
            tolerance: The minimum distance between points at which they are
                not considered touching. Default: 0.01, suitable for objects
                in meters.
        """
        story_height = self.floor_height
        room_floors = []
        for room in self.room_2ds:
            diff = story_height - room.floor_height
            if abs(diff) <= tolerance:
                room_floors.append(room.floor_geometry)
            else:
                room_floors.append(room.floor_geometry.move(Vector3D(0, 0, diff)))
        # TODO: consider returning a list of polyfaces if input rooms are disjointed
        return Polyface3D.from_faces(room_floors, tolerance)

    def outline_segments(self, tolerance=0.01):
        """Get a list of LineSegment3D objects for the outline of the floor plate.

        Note that these segments include both the boundary surrounding the floor
        and any holes for courtyards that exist within the floor.

        Args:
            tolerance: The minimum distance between points at which they are
                not considered touching. Default: 0.01, suitable for objects
                in meters.
        """
        return self.floor_geometry(tolerance).naked_edges

    def outline_polylines(self, tolerance=0.01):
        """Get a list of Polyline3D objects for the outline of the floor plate.

        Note that these segments include both the boundary surrounding the floor
        and any holes for courtyards that exist within the floor.

        Args:
            tolerance: The minimum distance between points at which they are
                not considered touching. Default: 0.01, suitable for objects
                in meters.
        """
        return Polyline3D.join_segments(self.outline_segments(tolerance), tolerance)

    def footprint(self, tolerance=0.01):
        """Get a list of Face3D objects for the minimum floor plate representation.

        Args:
            tolerance: The minimum distance between points at which they are
                not considered touching. (Default: 0.01, suitable for objects
                in meters).
        """
        plines = self.outline_polylines(tolerance)
        if len(plines) == 1:  # can be represented with a single Face3D
            return [Face3D(plines[0].vertices[:-1])]
        else:  # need to separate holes from distinct Face3Ds
            faces = [Face3D(pl.vertices[:-1]) for pl in plines]
            return Face3D.merge_faces_to_holes(faces, tolerance)

    def shade_representation(self, cap=False, tolerance=0.01):
        """A list of honeybee Shade objects representing the story geometry.

        This accounts for the story multiplier and can be used to account for
        this Story's shade in the simulation of another nearby Story.

        Args:
            cap: Boolean to note whether the shade representation should be capped
                with a top face. Usually, this is not necessary to account for
                blocked sun and is only needed when it's important to account for
                reflected sun off of roofs. (Default: False).
            tolerance: The minimum distance between points at which they are
                not considered touching. Default: 0.01, suitable for objects
                in meters.
        """
        context_shades = []
        extru_vec = Vector3D(0, 0, self.floor_to_floor_height * self.multiplier)
        for i, seg in enumerate(self.outline_segments(tolerance)):
            try:
                extru_geo = Face3D.from_extrusion(seg, extru_vec)
                shd_id = '{}_{}'.format(self.identifier, i)
                context_shades.append(Shade(shd_id, extru_geo))
            except ZeroDivisionError:
                pass  # duplicate vertex resulting in a segment of length 0
        if cap:
            for i, s in enumerate(self.footprint(tolerance)):
                shd_id = '{}_Top_{}'.format(self.identifier, i)
                context_shades.append(Shade(shd_id, s.move(extru_vec)))
        return context_shades

    def shade_representation_multiplier(self, exclude_index=0, cap=False,
                                        tolerance=0.01):
        """A list of honeybee Shade objects for just the "multiplier" part of the story.

        This includes all of the geometry along the height of the multiplier except
        for one of the floors (represented by the exclude_index). This will be an
        empty list if the story has a multiplier of 1.

        Args:
            exclude_index: An optional index for a story along the multiplier to
                be excluded from the shade representation. For example, if 0,
                the bottom geometry along the multiplier is excluded. (Default: 0).
            cap: Boolean to note whether the shade representation should be capped
                with a top face. Usually, this is not necessary to account for
                blocked sun and is only needed when it's important to account for
                reflected sun off of roofs. (Default: False).
            tolerance: The minimum distance between points at which they are
                not considered touching. Default: 0.01, suitable for objects
                in meters.
        """
        if self.multiplier == 1:
            return []
        # get the extrusion and moving vectors
        ftf, mult = self.floor_to_floor_height, self.multiplier
        context_shades, ceil_vecs, extru_vecs = [], [], []
        if exclude_index != 0:  # insert vectors for the bottom shade
            ceil_vecs.append(Vector3D(0, 0, 0))
            extru_vecs.append(Vector3D(0, 0, ftf * exclude_index))
        if exclude_index < mult:  # insert vectors for the top shade
            ceil_vecs.append(Vector3D(0, 0, ftf * (exclude_index + 1)))
            extru_vecs.append(Vector3D(0, 0, ftf * (mult - exclude_index - 1)))
        # loop through the segments and build up the shades
        for i, seg in enumerate(self.outline_segments(tolerance)):
            for ceil_vec, extru_vec in zip(ceil_vecs, extru_vecs):
                seg = seg.move(ceil_vec)
                try:
                    extru_geo = Face3D.from_extrusion(seg, extru_vec)
                    shd_id = '{}_{}'.format(self.identifier, i)
                    context_shades.append(Shade(shd_id, extru_geo))
                except ZeroDivisionError:
                    pass  # duplicate vertex resulting in a segment of length 0
        # cap the extrusions if requested
        if cap and exclude_index < mult:
            full_vec = Vector3D(0, 0, ftf * mult)
            for i, s in enumerate(self.footprint(tolerance)):
                shd_id = '{}_Top_{}'.format(self.identifier, i)
                context_shades.append(Shade(shd_id, s.move(full_vec)))
        return context_shades

    def room_by_identifier(self, room_identifier):
        """Get a Room2D from this Story using its identifier.

        Result will be None if the Room2D is not found in the Story.

        Args:
            room_identifier: String for the identifier of the Room2D to be
                retrieved from this story.
        """
        for room in self._room_2ds:
            if room.identifier == room_identifier:
                return room
        else:
            raise ValueError('Room2D "{}" was not found in the story "{}"'
                             '.'.format(room_identifier, self.identifier))

    def rooms_by_identifier(self, room_identifiers):
        """Get a list of Room2D objects in this story given Room2D identifiers.

        Args:
            room_identifier: Array of strings for the identifiers of the Room2D
                to be retrieved from this Story.
        """
        room_2ds = []
        for identifier in room_identifiers:
            for room in self._room_2ds:
                if room.identifier == identifier:
                    room_2ds.append(room)
                    break
            else:
                raise ValueError('Room2D "{}" was not found in the story '
                                 '"{}".'.format(identifier, self.identifier))
        return room_2ds

    def add_prefix(self, prefix):
        """Change the identifier and all child Room2D ids by inserting a prefix.

        This is particularly useful in workflows where you duplicate and edit
        a starting object and then want to combine it with the original object
        into one Model (like making a model of repeated stories) since all objects
        within a Model must have unique identifiers.

        This method is used internally to convert from a Story with a multiplier
        to fully-detailed Stories with unique identifiers.

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
        for room in self.room_2ds:
            room.add_prefix(prefix)

    def add_room_2d(self, room_2d):
        """Add a Room2D to this Story.

        No check will be performed for whether the input room_2d's identifier
        matches one in the current Story.

        Args:
            room_2d: A Room2D object to be added to this Story.
        """
        assert isinstance(room_2d, Room2D), \
            'Expected dragonfly Room2D. Got {}'.format(type(room_2d))
        room_2d._parent = self
        self._room_2ds = self._room_2ds + (room_2d,)

    def add_room_2ds(self, rooms_2ds, add_duplicate_ids=False):
        """Add a list of Room2Ds to this Story with checks for duplicate identifiers.

        Args:
            room_2d: A list of Room2D objects to be added to this Story.
            add_duplicate_ids: A boolean to note whether added Room2Ds that
                have matching identifiers within the current Story should be
                ignored (False) or they should be added to the Story creating
                an ID collision that can be resolved later (True). (Default: False).
        """
        # check to be sure that the input is composed of Room2Ds
        for o_room_2d in rooms_2ds:
            assert isinstance(o_room_2d, Room2D), \
                'Expected dragonfly Room2D. Got {}'.format(type(o_room_2d))
        # add the rooms and deal with duplicated IDs appropriately
        new_room_2ds = list(self._room_2ds)
        if add_duplicate_ids:
            for o_room_2d in rooms_2ds:
                o_room_2d._parent = self
                new_room_2ds.append(o_room_2d)
        else:
            exist_set = {rm.identifier for rm in self._room_2ds}
            for o_room_2d in rooms_2ds:
                if o_room_2d.identifier not in exist_set:
                    o_room_2d._parent = self
                    new_room_2ds.append(o_room_2d)
        # assign the new Room2Ds to this Story
        self._room_2ds = tuple(new_room_2ds)

    def reset_room_2d_boundaries(
            self, polygons, identifiers=None, display_names=None,
            floor_to_ceiling_heights=None, tolerance=0.01):
        """Rebuild the Room2Ds of the Story using boundary Polygons.

        All existing properties of segments along the boundary polygons will be
        preserved, including all window geometries. By default, the largest room
        that is identified within each of the boundary polygons will determine the
        extension properties of the resulting Room2D.

        It is recommended that the Room2Ds be aligned to the boundaries of the
        polygon and duplicate vertices be removed before using this method.

        Args:
            polygons: A list of ladybug_geometry Polygon2D, which will become
                the new boundaries of the Story's Room2Ds. Note that it is
                acceptable to include hole polygons in this list and they will
                automatically be sensed by their relationship to the other
                polygons.
            identifiers: An optional list of text that align with the polygons
                and will dictate the identifiers of the Story's Rooms. If this
                matches an existing Room2D inside of the polygon, the existing
                Room2D will be used to set the extension properties of the output
                Room2D. If None, the identifier and extension properties of the
                output Room2D will be those of the largest Room2D found inside
                of the polygon. (Default: None).
            display_names: An optional list of text that align with the
                polygons and will dictate the display_names of the Story's Rooms.
                If None, the display_name will be taken from the
                largest existing Room2D inside the polygon or the existing
                Room2D matching the identifier above. (Default: None).
            floor_to_ceiling_heights: An optional list of numbers that align with the
                polygons and will dictate the the floor-to-ceiling heights of the
                resulting Room2Ds. If None, it will be the maximum of the Room2Ds
                that are found inside each of the polygon, which ensures
                that all window geometries are included in the output. If specified
                and it is lower than the maximum Room2D height, any detailed
                windows will be automatically trimmed to accommodate the new
                floor-to-ceiling height. (Default: None).
            tolerance: The minimum distance between a vertex and the polygon
                boundary at which point the vertex is considered to lie on the
                polygon. (Default: 0.01, suitable for objects in meters).
        """
        # set defaults for identifiers and display_names
        if identifiers is None:
            identifiers = [None] * len(polygons)
        if display_names is None:
            display_names = [None] * len(polygons)
        if floor_to_ceiling_heights is None:
            floor_to_ceiling_heights = [None] * len(polygons)
        # sort the polygons so they can be correctly interpreted as holes
        p_areas = [p.area for p in polygons]
        sort_ind = [i for _, i in sorted(zip(p_areas, range(len(p_areas))))]
        sort_ind.reverse()
        sort_poly = [polygons[i] for i in sort_ind]
        sort_ids = [identifiers[i] for i in sort_ind]
        sort_names = [display_names[i] for i in sort_ind]
        sort_ftcs = [floor_to_ceiling_heights[i] for i in sort_ind]
        # loop through the polygons and make the Room2Ds
        new_room_2ds = []
        skip_i = []  # list to track hole polygons to be skipped
        zip_obj = zip(sort_poly, sort_ids, sort_names, sort_ftcs)
        for i, (poly, r_id, r_nm, ftc) in enumerate(zip_obj):
            if i in skip_i:
                continue
            holes = []
            for j, o_poly in enumerate(sort_poly[i + 1:]):
                if poly.is_polygon_inside(o_poly):
                    holes.append(o_poly)
                    skip_i.append(i + j + 1)
            new_room = Room2D.join_by_boundary(
                self._room_2ds, poly, holes, ftc, r_id, r_nm, tolerance=tolerance)
            new_room_2ds.append(new_room)
        self._room_2ds = tuple(new_room_2ds)

    def suggested_alignment_axes(
            self, distance, direction=Vector2D(0, 1), angle_tolerance=1.0):
        """Get suggested LineSegment2Ds to be used for this Story in the align methods.

        This method will return the most common axes across the Story geometry
        along with the number of Room2D segments that correspond to each axis.
        The latter can be used to filter the suggested alignment axes to get
        only the most common ones across the input Room2Ds.

        Args:
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
            angle_tolerance: The max angle difference in radians that the Room2D
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
        return Room2D.generate_alignment_axes(
            self._room_2ds, distance, direction, angle_tolerance)

    def align_room_2ds(self, line_ray, distance):
        """Move Room2D vertices within a given distance of a line to be on that line.

        Note that, when there are small Room2Ds next to the input line_ray,
        this method can create degenerate Room2Ds and so it may be wise to run
        the delete_degenerate_room_2ds method after running this one.

        Args:
            line_ray: A ladybug_geometry Ray2D or LineSegment2D to which the Room2D
                vertices will be aligned. Ray2Ds will be interpreted as being infinite
                in both directions while LineSegment2Ds will be interpreted as only
                existing between two points.
            distance: The maximum distance between a vertex and the line_ray where
                the vertex will be moved to lie on the line_ray. Vertices beyond
                this distance will be left as they are.
        """
        for room in self.room_2ds:
            room.align(line_ray, distance)

    def align(self, line_ray, distance, tolerance=0.01):
        """Move Room2D and Roof vertices within a distance of a line to be on that line.

        This method differs from the align_room_2ds method in that it will also
        align any Roof geometry (if it is present).

        Args:
            line_ray: A ladybug_geometry Ray2D or LineSegment2D to which the Room2D
                and Roof vertices will be aligned. Ray2Ds will be interpreted as being
                infinite in both directions while LineSegment2Ds will be interpreted
                as only existing between two points.
            distance: The maximum distance between a vertex and the line_ray where
                the vertex will be moved to lie on the line_ray. Vertices beyond
                this distance will be left as they are.
            tolerance: The minimum distance between vertices below which they are
                considered co-located. This is used to ensure that the alignment process
                does not create new overlaps in the roof geometry. (Default: 0.01,
                suitable for objects in meters).
        """
        self.align_room_2ds(line_ray, distance)
        if self.roof is not None:
            self.roof.align(line_ray, distance, tolerance)

    def remove_room_2d_duplicate_vertices(self, tolerance=0.01, delete_degenerate=False):
        """Remove duplicate vertices from all Room2Ds in this Story.

        All properties assigned to the Room2D will be preserved and any changed
        Surface boundary conditions will be automatically updated based on the
        removed wall segment indices.

        Args:
            tolerance: The minimum distance between a vertex and the line it lies
                upon at which point the vertex is considered duplicated. Default: 0.01,
                suitable for objects in meters).
            delete_degenerate: Boolean to note whether degenerate Room2Ds (with floor
                geometries that evaluate to less than 3 vertices at the tolerance)
                should be deleted from the Story instead of raising a ValueError.
                Note that using this option frequently creates invalid missing
                adjacencies, requiring the run of reset_adjacencies followed
                by re-running solve_adjacency. (Default: False).

        Returns:
            A list of all degenerate Room2Ds that were removed if delete_degenerate
            is True. Will be None if delete_degenerate is False.
        """
        # remove vertices from the rooms and track the removed indices
        removed_dict, removed_rooms = {}, None
        if delete_degenerate:
            new_room_2ds, removed_rooms = [], []
            for room in self.room_2ds:
                try:
                    removed_dict[room.identifier] = \
                        room.remove_duplicate_vertices(tolerance)
                    new_room_2ds.append(room)
                except ValueError:  # degenerate room found!
                    removed_rooms.append(room)
            assert len(new_room_2ds) > 0, 'All Room2Ds of Story "{}" are '\
                'degenerate.'.format(self.display_name)
            self._room_2ds = tuple(new_room_2ds)
        else:
            for room in self.room_2ds:
                removed_dict[room.identifier] = \
                    room.remove_duplicate_vertices(tolerance)

        # go through the rooms and update any changed Surface boundary conditions
        if len(self.room_2ds) != 1:
            for room in self.room_2ds:
                for j, bc in enumerate(room._boundary_conditions):
                    if isinstance(bc, Surface):
                        adj_wall, adj_room = bc.boundary_condition_objects
                        try:
                            removed_i = removed_dict[adj_room]
                        except KeyError:  # illegal boundary condition; just ignore
                            continue
                        if len(removed_i) == 0:  # no removed vertices in room
                            continue
                        current_i = int(adj_wall.split('..Face')[-1]) - 1
                        if removed_i[0] <= current_i:  # surface bc to be updated
                            bef_count = len([k for k in removed_i if k <= current_i])
                            new_i = current_i - bef_count
                            new_bc = Surface(
                                ('{}..Face{}'.format(adj_room, new_i + 1), adj_room)
                            )
                            room._boundary_conditions[j] = new_bc
        return removed_rooms

    def remove_room_2d_colinear_vertices(
            self, tolerance=0.01, preserve_wall_props=True, delete_degenerate=False):
        """Automatically remove colinear or duplicate vertices for the Story's Room2Ds.

        Args:
            tolerance: The minimum difference between the coordinate values at
                which they are considered co-located. Default: 0.01,
                suitable for objects in meters.
            preserve_wall_props: Boolean to note whether existing window parameters
                and Ground boundary conditions should be preserved as vertices are
                removed. If False, all boundary conditions are replaced with Outdoors,
                all window parameters are erased, and this method will execute quickly.
                If True, an attempt will be made to merge window parameters together
                across colinear segments, translating simple window parameters to
                rectangular ones if necessary. Also, existing Ground boundary
                conditions will be kept. (Default: True).
            delete_degenerate: Boolean to note whether degenerate Room2Ds (with
                floor geometries that evaluate to less than 3 vertices at the
                tolerance) should be deleted from the Story instead of raising
                a ValueError. (Default: False).

        Returns:
            A list of all degenerate Room2Ds that were removed if delete_degenerate
            is True. Will be None if delete_degenerate is False.
        """
        # remove vertices from the rooms and track the removed indices
        if delete_degenerate:
            new_room_2ds, removed_rooms = [], []
            for room in self.room_2ds:
                try:
                    new_r = room.remove_colinear_vertices(tolerance, preserve_wall_props)
                    new_room_2ds.append(new_r)
                except (ValueError, IndexError):  # degenerate room found!
                    removed_rooms.append(room)
            assert len(new_room_2ds) > 0, 'All Room2Ds of Story "{}" are '\
                'degenerate.'.format(self.display_name)
            self._room_2ds = tuple(new_room_2ds)
            return removed_rooms
        else:
            new_room_2ds = []
            for room in self.room_2ds:
                new_room = room.remove_colinear_vertices(tolerance, preserve_wall_props)
                new_room_2ds.append(new_room)
            self._room_2ds = tuple(new_room_2ds)

    def remove_room_2d_short_segments(self, distance, angle_tolerance=1.0):
        """Remove consecutive short segments on this Story's Room2Ds.

        To patch over the removed segments, an attempt will first be made to find the
        intersection of the two neighboring segments. If these two lines are parallel,
        they will simply be connected with a segment.

        Properties assigned to the Room2Ds will be preserved for the segments that
        are not removed. Room2Ds that have all of their walls shorter than the
        distance will be removed from the Story.

        Args:
            distance: The maximum length of a segment below which the segment
                will be considered for removal.
            angle_tolerance: The max angle difference in degrees that vertices
                are allowed to differ from one another in order to consider them
                colinear. (Default: 1).

        Returns:
            A list of all small Room2Ds that were removed.
        """
        # remove vertices from the rooms and track the removed indices
        new_room_2ds, removed_rooms = [], []
        for room in self.room_2ds:
            nr = room.remove_short_segments(distance, angle_tolerance)
            if nr is not None:
                new_room_2ds.append(nr)
            else:
                removed_rooms.append(room)
        assert len(new_room_2ds) > 0, 'All Room2Ds of Story "{}" are '\
            'are shorter than the distance {}.'.format(self.display_name, distance)
        self._room_2ds = tuple(new_room_2ds)
        return removed_rooms

    def delete_degenerate_room_2ds(self, tolerance=0.01):
        """Remove all Room2Ds with a floor_area of zero from this Story.

        This method will also automatically remove any degenerate holes in Room2D
        floor geometries, which have an area less than zero.

        Args:
            tolerance: The minimum difference between the coordinate values at
                which they are considered co-located. Default: 0.01,
                suitable for objects in meters.

        Returns:
            A list of all degenerate Room2Ds that were removed.
        """
        new_room_2ds, removed_rooms = [], []
        for room in self.room_2ds:
            max_dim = max((room.max.x - room.min.x, room.max.y - room.min.y))
            if room.floor_geometry.area < max_dim * tolerance:
                removed_rooms.append(room)
            else:
                room.remove_degenerate_holes(tolerance)
                new_room_2ds.append(room)
        assert len(new_room_2ds) > 0, 'All Room2Ds of Story "{}" are '\
            'degenerate.'.format(self.display_name)
        self._room_2ds = tuple(new_room_2ds)
        return removed_rooms

    def join_small_room_2ds(self, area_threshold, join_into_large=False,
                            tolerance=0.01):
        """Join small Room2Ds together within this Story.

        This is particularly useful when operations like automatic core/perimeter
        zoning creates several small Room2Ds from small segments in the outline
        boundary around the Story.

        Args:
            area_threshold: A number for the Room2D floor area below which it is
                considered a small room to be joined into adjacent rooms.
            join_into_large: A boolean to note whether the small Room2Ds should
                be joined into neighboring large Room2Ds as opposed to simply
                joining the small rooms to one another. (Default: False).
            tolerance: The minimum distance between vertices at which point they
                are considered equivalent. (Default: 0.01, suitable
                for objects in meters).
        """
        # first gather all of the small rooms in the model to be joined
        all_rooms = list(self._room_2ds)
        small_rooms, large_rooms = [], []
        for rm in all_rooms:
            if rm.floor_area < area_threshold:
                small_rooms.append(rm)
            else:
                large_rooms.append(rm)
        if len(small_rooms) == 0:
            return

        # join Room2Ds together that share adjacency
        joined_small_rooms = []
        room_groups = Room2D.group_by_adjacency(small_rooms)
        for r_group in room_groups:
            if len(r_group) == 1:  # no rooms to be joined together
                joined_small_rooms.extend(r_group)
                continue
            joined_rooms = Room2D.join_room_2ds(r_group, tolerance=tolerance)
            joined_small_rooms.extend(joined_rooms)
            del_is = []
            for n_rm in r_group:
                for in_i, e_rm in enumerate(all_rooms):
                    if e_rm.identifier == n_rm.identifier:
                        del_is.append(in_i)
                        break
            del_is.sort()
            for del_i in reversed(del_is):
                all_rooms.pop(del_i)
            for j_room in joined_rooms:
                all_rooms.insert(del_is[0], j_room)

        # if join_into_neighbor is selected, join the small rooms into the neighbors
        if join_into_large:
            all_rooms = Room2D.join_to_neighbor(
                large_rooms, joined_small_rooms, tolerance=tolerance)

        # set Room2Ds and re-solve adjacencies to make the result valid
        self.room_2ds = all_rooms

    def fill_holes(self, base_name='Room', area_threshold=0, tolerance=0.01):
        """Fill any holes in this Story's floor plate with new Room2Ds.

        Args:
            base_name: Text to set the display_name of the generated Room2Ds and
                will be incorporated into a unique Room2D identifier. (Default: "Room").
            area_threshold: An optional positive number that the minimum area of
                a hole for it to be filled with a Room2D. This can be used to
                ensure very small holes aren't unintentionally filled with holes.
                Setting this value to zero will result in all holes filled with
                Room2Ds. (Default: 0).
            tolerance: The minimum distance between vertices at which point they
                are considered equivalent. (Default: 0.01, suitable
                for objects in meters).

        Returns:
            A list of new Rom2Ds that were added to the Story.
        """
        # compute the horizontal boundary around the rooms
        median_i = int(len(self.room_2ds) / 2)
        ftcs = [room.floor_to_ceiling_height for room in self.room_2ds]
        ftcs.sort()
        median_height = ftcs[median_i]
        h_bounds = Room2D.grouped_horizontal_boundary(self.room_2ds, tolerance, tolerance)

        # convert holes in the resulting boundary to rooms
        new_rooms, room_count = [], 0
        for h_bound in h_bounds:
            if h_bound.has_holes:
                for hole in h_bound.holes:
                    hole_face = Face3D(hole)
                    if hole_face.area > area_threshold:
                        # create the Room2D object
                        room_name = base_name if room_count == 0 else \
                            '{}{}'.format(base_name, room_count)
                        room_id = clean_and_id_string(room_name)
                        new_room = Room2D(room_id, hole_face, median_height,
                                          tolerance=tolerance)
                        new_room.display_name = room_name

                        # assign is_top_exposed and is_ground_contact with neighbor rooms
                        neighbor_top_ex, neighbor_grd_con = [], []
                        for adj_room in self.room_2ds:
                            adj_poly = adj_room.floor_geometry.polygon2d
                            for pt in new_room.floor_geometry.polygon2d:
                                if adj_poly.distance_to_point(pt) < tolerance:
                                    neighbor_top_ex.append(adj_room.is_top_exposed)
                                    neighbor_grd_con.append(adj_room.is_ground_contact)
                                    break
                        new_room.is_top_exposed = all(neighbor_top_ex)
                        new_room.is_ground_contact = all(neighbor_grd_con)

                        # add the new rooms and the corresponding stories to the output
                        new_rooms.append(new_room)
                        room_count += 1

        # add the new rooms to this story
        self.add_room_2ds(new_rooms)
        return new_rooms

    def join_room_2ds(self, room_ids, tolerance=0.01):
        """Join Room2Ds together on this Story.

        The largest Room2D that is identified within each connected group will
        determine the extension properties of the resulting Room2D. Skylights
        will be merged across rooms if they are of the same type or if they are None.

        Args:
            room_ids: A list of Room2Ds identifiers for rooms on this Story to
                be joined together where they touch one another.
            tolerance: The minimum distance between a vertex and the polygon
                boundary at which point the vertex is considered to lie on the
                polygon. (Default: 0.01, suitable for objects in meters).

        Returns:
            A list of Room2Ds for the new rooms created through joining.
        """
        remove_ids = set(room_ids)
        final_rooms, merge_rooms = [], []
        for room in self.room_2ds:
            if room.identifier not in remove_ids:
                final_rooms.append(room)
            else:
                merge_rooms.append(room)
        new_rooms = Room2D.join_room_2ds(merge_rooms, tolerance=tolerance)
        final_rooms.extend(new_rooms)
        self.room_2ds = final_rooms
        return new_rooms

    def rebuild_detailed_windows(
            self, tolerance=0.01, match_adjacency=False, rebuild_skylights=True):
        """Rebuild all detailed windows such that they are bounded by their parent walls.

        This method will also ensure that all interior windows on adjacent wall
        segments are matched correctly with one another.

        This is useful to run after situations where Room2D vertices have been moved,
        which can otherwise disrupt the pattern of detailed windows.

        Args:
            tolerance: The minimum distance between a vertex and the edge of the
                wall segment that is considered not touching. (Default: 0.01, suitable
                for objects in meters).
            match_adjacency: A boolean to note whether this method should ensure
                that all interior windows on adjacent wall segments are matched
                correctly with one another. This is desirable when the existing
                adjacencies across the model are correct but it can create several
                unwanted cases when the adjacencies are not correct. (Default: False).
            rebuild_skylights: A boolean to note whether skylights should be offset
                and rebuilt if they lie outside their parent Room2D.
        """
        adj_dict = {}
        for room in self.room_2ds:
            new_w_pars = []
            zip_items = zip(
                room._window_parameters, room.floor_segments, room._boundary_conditions)
            for i, (w_par, seg, bc) in enumerate(zip_items):
                if isinstance(w_par, DetailedWindows):
                    new_w_par = w_par.adjust_for_segment(
                        seg, room.floor_to_ceiling_height, tolerance)
                    if match_adjacency and isinstance(bc, Surface):
                        try:
                            adj_seg = bc.boundary_condition_objects[0]
                            new_w_par = adj_dict[adj_seg].flip(seg.length)
                        except KeyError:  # first of the two adjacencies
                            this_seg = '{}..Face{}'.format(room.identifier, i + 1)
                            adj_dict[this_seg] = new_w_par
                        except AttributeError:  # all windows were removed from adjacency
                            new_w_par = None
                else:
                    new_w_par = w_par
                new_w_pars.append(new_w_par)
            room._window_parameters = new_w_pars
            if rebuild_skylights:
                room.offset_skylights_from_edges(tolerance * 2, tolerance)

    def reset_adjacency(self):
        """Set all Surface boundary conditions on the Story to be Outdoors."""
        for room in self.room_2ds:
            room.reset_adjacency()

    def intersect_room_2d_adjacency(self, tolerance=0.01):
        """Automatically intersect the line segments of the Story's Room2Ds.

        Note that this method effectively erases window parameters and shading
        parameters for any intersected segments as the original segments are
        subdivided. As such, it is recommended that this method be used before
        assigning window or shading parameters.

        Args:
            tolerance: The minimum difference between the coordinate values of two
                at which they can be considered adjacent. (Default: 0.01,
                suitable for objects in meters).
        """
        self._room_2ds = Room2D.intersect_adjacency(self._room_2ds, tolerance)

    def solve_room_2d_adjacency(
            self, tolerance=0.01, intersect=False, resolve_window_conflicts=True):
        """Automatically solve adjacencies across the Room2Ds in this Story.

        Args:
            tolerance: The minimum difference between the coordinate values of two
                faces at which they can be considered adjacent. (Default: 0.01,
                suitable for objects in meters).
            intersect: Boolean to note wether the Room2Ds should be intersected
                to obtain matching wall segments before solving adjacency. Note
                that setting this to True will result in the loss of windows and
                shades assigned to intersected segments. (Default: False).
            resolve_window_conflicts: Boolean to note whether conflicts between
                window parameters of adjacent segments should be resolved during
                adjacency setting or an error should be raised about the mismatch.
                Resolving conflicts will default to the window parameters with the
                larger are and assign them to the other segment. (Default: True).
        """
        if intersect:
            self._room_2ds = Room2D.intersect_adjacency(self._room_2ds, tolerance)
        Room2D.solve_adjacency(self._room_2ds, tolerance, resolve_window_conflicts)

    def set_adjacent_air_boundary(self, room_ids=None, guide_lines=None, tolerance=0.01):
        """Set adjacencies between Room2Ds in this Story to use air boundaries.

        Args:
            room_ids: An optional list of Room2D identifiers to specify a subset
                of rooms within the Story that will have air boundaries set
                between them. If None, all Room2Ds in the story will have
                air boundaries set if they are adjacent to another. (Default: None).
            guide_lines: An optional list of LineSegment2Ds to specify a subset
                of rooms within the Story that will have air boundaries set
                between them. If None, all Room2Ds in the story will have
                air boundaries set if they are adjacent to another. (Default: None).
            tolerance: The minimum difference between the coordinate values of two
                faces at which they can be considered adjacent. (Default: 0.01,
                suitable for objects in meters).
        """
        # gather all of the Room2Ds which will have air boundaries assigned
        rooms = self._room_2ds if room_ids is None \
            else self.rooms_by_identifier(room_ids)
        # find the adjacencies along which air boundaries will be set
        if guide_lines is None or len(guide_lines) == 0:
            adj_info = Room2D.find_adjacency(rooms, tolerance)
        else:
            adj_info = Room2D.find_adjacency_by_guide_lines(
                rooms, guide_lines, tolerance)
        # assign air boundaries to all of the pairs that were found
        for room_pair in adj_info:
            for room_adj in room_pair:
                room, wall_i = room_adj
                try:
                    room.set_window_parameter(wall_i)  # remove windows along air bound
                    room.set_air_boundary(wall_i)
                except AssertionError:  # segment with non-adjacent BC
                    pass  # ignore this particular segment

    def set_outdoor_window_parameters(self, window_parameter):
        """Set all of the outdoor walls to have the same window parameters.

        Args:
            window_parameter: A WindowParameter object that will be assigned to
                all wall segments of this story's rooms that have an Outdoors
                boundary conditions. This can also be None, to remove all
                windows from the story.
        """
        for room in self._room_2ds:
            room.set_outdoor_window_parameters(window_parameter)

    def set_outdoor_shading_parameters(self, shading_parameter):
        """Set all of the outdoor walls to have the same shading parameters.

        Args:
            shading_parameter: A ShadingParameter object that will be assigned to
                all wall segments of this story's rooms that have an Outdoors
                boundary conditions. This can also be None, to remove all
                shades from the story.
        """
        for room in self._room_2ds:
            room.set_outdoor_shading_parameters(shading_parameter)

    def to_rectangular_windows(self):
        """Convert all of the windows of the Story to the RectangularWindows format."""
        for room in self._room_2ds:
            room.to_rectangular_windows()

    def set_ground_contact(self, is_ground_contact=True):
        """Set all child Room2Ds of this object to have floors with ground contact.

        Args:
            is_ground_contact: A boolean noting whether all the Story's room_2ds
                have floors in contact with the ground. Default: True.
        """
        for room in self._room_2ds:
            room.is_ground_contact = is_ground_contact

    def set_top_exposed(self, is_top_exposed=True):
        """Set all child Room2Ds of this object to have ceilings exposed to the outdoors.

        Args:
            is_top_exposed: A boolean noting whether all the Story's room_2ds
                have ceilings exposed to the outdoors. Default: True.
        """
        for room in self._room_2ds:
            room.is_top_exposed = is_top_exposed

    def split_with_story_above(self, story_above, tolerance=0.01):
        """Split the child Room2Ds of this object with the footprint of the Story above.

        This is useful as a pre-step before running set_top_exposed_by_story_above
        as it ensures all top-exposed areas of this Story have a Room2D that can
        be set to exposed.

        Args:
            story_above: A Story object that sits above this Story. Each Room2D
                of this Story will be checked to see if it intersects the Story
                above and it will be split based on this.
            tolerance: The tolerance with which the splitting intersection will be
                computed. Default: 0.01, suitable for objects in meters.
        """
        # get the footprint geometry of the story above
        above_geos = story_above.footprint(tolerance)
        # loop through the rooms and split them
        split_rooms = []
        for room in self._room_2ds:
            # split the floor with all geometries above
            room_height = room.floor_height
            split_geo = [room.floor_geometry]
            for i, a_geo in enumerate(above_geos):
                # make sure all above geometries are at the room floor_height
                if abs(a_geo[0].z - room_height) > tolerance:
                    a_geo = a_geo.move(Vector3D(0, 0, room_height - a_geo[0].z))
                    above_geos[i] = a_geo  # set it so we hopefully don't move next time
                # split the geometries with one another
                new_geo = []
                for r_geo in split_geo:
                    floor_split, above_split = Face3D.coplanar_split(
                        r_geo, a_geo, tolerance, 1)
                    new_geo.extend(floor_split)
                split_geo = new_geo
            # create the new Room2D if necessary
            if len(split_geo) == 1:  # no room splitting needed
                split_rooms.append(room)
            else:  # the Room2D has been split
                for j, s_geo in enumerate(split_geo):
                    # check to make sure the split geometry is not degenerate
                    max_dim = max((s_geo.max.x - s_geo.min.x, s_geo.max.y - s_geo.min.y))
                    if s_geo.area < max_dim * tolerance:  # degenerate geometry found
                        continue
                    new_id = '{}_{}'.format(room.identifier, j)
                    new_room = Room2D(
                        new_id, s_geo, room.floor_to_ceiling_height,
                        is_ground_contact=room.is_ground_contact,
                        is_top_exposed=room.is_top_exposed)
                    room._match_and_transfer_wall_props(new_room, tolerance)
                    new_room._display_name = room._display_name
                    new_room._user_data = None if room.user_data is None \
                        else room.user_data.copy()
                    new_room._has_floor = room._has_floor
                    new_room._has_ceiling = room._has_ceiling
                    new_room._ceiling_plenum_depth = room._ceiling_plenum_depth
                    new_room._floor_plenum_depth = room._floor_plenum_depth
                    new_room._skylight_parameters = room._skylight_parameters
                    new_room._properties._duplicate_extension_attr(room._properties)
                    split_rooms.append(new_room)
        # set the split rooms to this story
        self.room_2ds = split_rooms

    def set_top_exposed_by_story_above(self, story_above, tolerance=0.01):
        """Set the Room2Ds of this Story to have ceilings exposed to the outdoors.

        Args:
            story_above: A Story object that sits above this Story. Each Room2D
                of this Story will be checked to see if the story_above geometry
                lies above the room and, if not, the top exposure will be set to True.
            tolerance: The tolerance that will be used to compute the point within
                the floor boundary that is used to check whether there is geometry
                above each Room2D. It is recommended that this number not be less
                than 1 centimeter to avoid long computation times. Default: 0.01,
                suitable for objects in meters.
        """
        up_vec = Vector3D(0, 0, 1)
        for room in self._room_2ds:
            rm_pt = room.floor_geometry.center if room.floor_geometry.is_convex else \
                room.floor_geometry.pole_of_inaccessibility(tolerance)
            face_ray = Ray3D(rm_pt, up_vec)
            for other_room in story_above._room_2ds:
                if other_room._floor_geometry.intersect_line_ray(face_ray) is not None:
                    room.is_top_exposed = False
                    break
            else:
                room.is_top_exposed = True

    def set_ground_contact_by_story_below(self, story_below, tolerance=0.01):
        """Set the Room2Ds of this Story to have ground contact using the story below.

        Note that this method assumes that the story_below is completely
        underground such that any Room2D of this Story will be ground contact
        if there is no Room2D below the room.

        Args:
            story_below: A Story object that sits below this Story. Each Room2D
                of this Story will be checked to see if the story_below geometry
                lies below the room and, if not, the ground contact will be set to True.
            tolerance: The tolerance that will be used to compute the point within
                the floor boundary that is used to check whether there is geometry
                above each Room2D. It is recommended that this number not be less
                than 1 centimeter to avoid long computation times. Default: 0.01,
                suitable for objects in meters.
        """
        down_vec = Vector3D(0, 0, -1)
        for room in self._room_2ds:
            rm_pt = room.floor_geometry.center if room.floor_geometry.is_convex else \
                room.floor_geometry.pole_of_inaccessibility(tolerance)
            face_ray = Ray3D(Point3D(rm_pt.x, rm_pt.y, rm_pt.z + tolerance), down_vec)
            for other_room in story_below._room_2ds:
                if other_room._floor_geometry.intersect_line_ray(face_ray) is not None:
                    room.is_ground_contact = False
                    break
            else:
                room.is_ground_contact = True

    def make_underground(self, remove_windows=False):
        """Make this Story underground by setting all Room2D segments to have Ground BCs.

        Note that this method only changes the outdoor walls of the Room2Ds to have
        Ground boundary conditions and, if the floors of the story are also in
        contact with the ground, the set_ground_contact should be used in addition
        to this method.

        Args:
            remove_windows: Boolean to note whether outdoor Room2D segments
                with windows should have their outdoor boundary conditions and
                windows kept (True) or whether the windows should be removed
                in order to assign a ground boundary condition to all
                walls (False). (Default: False).
        """
        if remove_windows:
            self.set_outdoor_window_parameters(None)
            for room in self._room_2ds:
                for i, bc in enumerate(room._boundary_conditions):
                    if isinstance(bc, Outdoors):
                        room.set_boundary_condition(i, bcs.ground)
        else:
            for room in self._room_2ds:
                zip_obj = zip(room._boundary_conditions, room._window_parameters)
                for i, (bc, wp) in enumerate(zip_obj):
                    if wp is None and isinstance(bc, Outdoors):
                        room.set_boundary_condition(i, bcs.ground)

    def automatically_zone(self, orient_count=None, north_vector=Vector2D(0, 1),
                           attr_name=None):
        """Automatically group the rooms of this Story into zones.

        Relevant properties that are used to group Room2Ds into zones include
        orientation, and additional attributes (like programs).

        Args:
            orient_count: An optional positive integer to set the number of orientation
                groups to use for zoning. For example, setting this to 4 will result
                in zones being established based on the four orientations (North,
                East, South, West). If None, the maximum number of unique groups
                will be used.
            north_vector: A ladybug_geometry Vector2D for the north direction.
                Default is the Y-axis (0, 1).
            attr_name: A string of an attribute that the input Room2Ds should have.
                This can have '.' that separate the nested attributes from one another.
                For example, 'properties.energy.program_type'.
        """
        Room2D.automatically_zone(self._room_2ds, orient_count, north_vector, attr_name)

    def generate_grid(self, x_dim, y_dim=None, offset=1.0):
        """Get a list of gridded Mesh3D objects offset from the floors of this story.

        Args:
            x_dim: The x dimension of the grid cells as a number.
            y_dim: The y dimension of the grid cells as a number. Default is None,
                which will assume the same cell dimension for y as is set for x.
            offset: A number for how far to offset the grid from the base face.
                Default is 1.0, which will not offset the grid to be 1 unit above
                the floor.
        """
        return [room.generate_grid(x_dim, y_dim, offset) for room in self._room_2ds]

    def move(self, moving_vec):
        """Move this Story along a vector.

        Args:
            moving_vec: A ladybug_geometry Vector3D with the direction and distance
                to move the object.
        """
        for room in self._room_2ds:
            room.move(moving_vec)
        self._floor_height = self._floor_height + moving_vec.z
        if self._roof is not None:
            self._roof.move(moving_vec)
        self.properties.move(moving_vec)

    def rotate_xy(self, angle, origin):
        """Rotate this Story counterclockwise in the XY plane by a certain angle.

        Args:
            angle: An angle in degrees.
            origin: A ladybug_geometry Point3D for the origin around which the
                object will be rotated.
        """
        for room in self._room_2ds:
            room.rotate_xy(angle, origin)
        if self._roof is not None:
            self._roof.rotate_xy(angle, origin)
        self.properties.rotate_xy(angle, origin)

    def reflect(self, plane):
        """Reflect this Story across a plane.

        Args:
            plane: A ladybug_geometry Plane across which the object will be reflected.
        """
        for room in self._room_2ds:
            room.reflect(plane)
        if self._roof is not None:
            self._roof.reflect(plane)
        self.properties.reflect(plane)

    def scale(self, factor, origin=None):
        """Scale this Story by a factor from an origin point.

        Args:
            factor: A number representing how much the object should be scaled.
            origin: A ladybug_geometry Point3D representing the origin from which
                to scale. If None, it will be scaled from the World origin (0, 0, 0).
        """
        for room in self._room_2ds:
            room.scale(factor, origin)
        self._floor_to_floor_height = self._floor_to_floor_height * factor
        self._floor_height = self._floor_height * factor
        if self._roof is not None:
            self._roof.scale(factor, origin)
        self.properties.scale(factor, origin)

    def check_room2d_floor_heights_valid(self, raise_exception=True, detailed=False):
        """Check that all Room2Ds have floor elevations in range to be on the same Story.

        Args:
            raise_exception: Boolean to note whether a ValueError should be raised
                if rooms with inappropriate floor elevations are found. (Default: True).
            detailed: Boolean for whether the returned object is a detailed list of
                dicts with error info or a string with a message. (Default: False).

        Returns:
            A string with the message or a list with a dictionary if detailed is True.
        """
        if not self.room_2d_story_geometry_valid(self.room_2ds):
            # determine if are more offending rooms above or below average floor height
            flr_hts = [rm.floor_height for rm in self.room_2ds]
            flr_hts, rooms = zip(*sorted(zip(flr_hts, self.room_2ds),
                                         key=lambda pair: pair[0]))
            sum_ftc = sum([rm.floor_to_ceiling_height for rm in self.room_2ds])
            avg_ftc = sum_ftc / len(self.room_2ds)
            rms_below = []
            for flr_ht, room in zip(flr_hts, rooms):
                f_dif = flr_hts[-1] - flr_ht
                if f_dif >= avg_ftc:
                    r_info = (room, round(f_dif, 3),
                              round(flr_ht + (f_dif - avg_ftc), 3))
                    rms_below.append(r_info)
                else:
                    break
            rms_above = []
            for flr_ht, room in zip(reversed(flr_hts), reversed(rooms)):
                f_dif = flr_ht - flr_hts[0]
                if f_dif >= avg_ftc:
                    r_info = (room, round(f_dif, 3),
                              round(flr_ht - (f_dif - avg_ftc), 3))
                    rms_above.append(r_info)
                else:
                    break
            # prepare to give an exception message
            detailed = False if raise_exception else detailed
            msg1 = 'Story "{}" has Room floor elevations that are too different from ' \
                'one another to be a part of the same Story.'.format(self.display_name)
            msg2t = '  The following Rooms have an elevation {} the others:\n{}'
            msg3t = 'The Room "{}" has an elevation that is {} {} the others. ' \
                'Changing the floor elevation to something {} {} would make it valid.'
            # create the exception messages
            msgs = []
            if detailed:
                if len(rms_below) < len(rms_above):
                    for b_room in rms_below:
                        msg = msg3t.format(b_room[0].display_name, b_room[1],
                                           'below', 'above', b_room[2])
                        msg = self._validation_message_child(
                            msg, b_room[0], detailed, '100106',
                            error_type='Invalid Room Floor Elevation')
                        msgs.append(msg)
                else:
                    for a_room in rms_above:
                        msg = msg3t.format(a_room[0].display_name, a_room[1],
                                           'above', 'below', a_room[2])
                        msg = self._validation_message_child(
                            msg, a_room[0], detailed, '100106',
                            error_type='Invalid Room Floor Elevation')
                        msgs.append(msg)
                return msgs
            else:
                rms_below = ['   {} - distance: -{}'.format(rm[0].display_name, rm[1])
                             for rm in rms_below]
                rms_above = ['   {} - distance: +{}'.format(rm[0].display_name, rm[1])
                             for rm in rms_above]
                msg2 = msg2t.format('below', '\n'.join(rms_below)) \
                    if len(rms_below) < len(rms_above) else \
                    msg2t.format('above', '\n'.join(rms_above))
                msg = '{}\n{}'.format(msg1, msg2)
                if raise_exception:
                    raise ValueError(msg)
                return msg
        else:  # no error to report
            return [] if detailed else ''

    def check_missing_adjacencies(self, raise_exception=True, detailed=False):
        """Check that all Room2Ds have adjacent objects that exist within this Story.

        Args:
            raise_exception: Boolean to note whether a ValueError should be raised
                if missing or invalid adjacencies are found. (Default: True).
            detailed: Boolean for whether the returned object is a detailed list of
                dicts with error info or a string with a message. (Default: False).

        Returns:
            A string with the message or a list with a dictionary if detailed is True.
        """
        detailed = False if raise_exception else detailed
        # gather all of the Surface boundary conditions
        srf_bc_dict, rid_map = {}, {}
        for room in self._room_2ds:
            for bc, w_par in zip(room._boundary_conditions, room._window_parameters):
                if isinstance(bc, Surface):
                    bc_objs = bc.boundary_condition_objects
                    try:
                        bc_ind = int(bc_objs[0].split('..Face')[-1]) - 1
                        srf_bc_dict[(bc_objs[-1], bc_ind)] = \
                            (room.identifier, bc_objs[0], w_par, room)
                    except ValueError:  # Surface BC not following dragonfly convention
                        # this will be reported as a missing adjacency later
                        srf_bc_dict[(bc_objs[-1], 10000)] = \
                            (room.identifier, bc_objs[0], w_par, room)
            rid_map[room.identifier] = room.full_id
        # check the adjacencies for all Surface boundary conditions
        msgs = []
        for key, val in srf_bc_dict.items():
            rm_id = key[0]
            for room in self._room_2ds:
                if room.identifier == rm_id:
                    try:
                        rm_bc = room._boundary_conditions[key[1]]
                        rm_w_par = room._window_parameters[key[1]]
                    except IndexError:  # referenced wall segment does not exist
                        try:
                            r1, r2 = rid_map[val[0]], rid_map[rm_id]
                        except KeyError:  # completely missing from the model
                            r1, r2 = val[0], rm_id
                        msg = 'Room2D "{}" has an adjacency referencing a missing ' \
                            'wall segment on Room2D "{}".'.format(r1, r2)
                        msg = self._validation_message_child(
                            msg, val[3], detailed, '100203',
                            error_type='Missing Adjacency')
                        if detailed:
                            msg['element_id'].append(room.identifier)
                            msg['element_name'].append(room.display_name)
                            msg['parents'].append(msg['parents'][0])
                        msgs.append(msg)
                        break
                    if not isinstance(rm_bc, Surface):
                        try:
                            r1, r2 = rid_map[rm_id], rid_map[val[1]]
                        except KeyError:  # completely missing from the model
                            r1, r2 = rm_id, val[1]
                        msg = 'Room2D "{}" does not have a Surface boundary condition ' \
                            'at "{}" but its adjacent object does.'.format(r1, r2)
                        msg = self._validation_message_child(
                            msg, room, detailed, '100201',
                            error_type='Mismatched Adjacency')
                        if detailed:
                            msg['element_id'].append(val[3].identifier)
                            msg['element_name'].append(val[3].display_name)
                            msg['parents'].append(msg['parents'][0])
                        msgs.append(msg)
                    if val[2] != rm_w_par:
                        try:
                            r1, r2 = rid_map[val[0]], rid_map[rm_id]
                        except KeyError:  # completely missing from the model
                            r1, r2 = val[0], rm_id
                        msg = 'Window parameters do not match between ' \
                            'adjacent Room2Ds "{}" and "{}".'.format(r1, r2)
                        msg = self._validation_message_child(
                            msg, room, detailed, '100202',
                            error_type='Mismatched WindowParameter Adjacency')
                        if detailed:
                            msg['element_id'].append(val[3].identifier)
                            msg['element_name'].append(val[3].display_name)
                            msg['parents'].append(msg['parents'][0])
                        msgs.append(msg)
                    break
            else:
                try:
                    r1, r2 = rid_map[val[0]], rid_map[rm_id]
                except KeyError:  # completely missing from the model
                    r1, r2 = val[0], rm_id
                msg = 'Room2D "{}" has a missing adjacency for Room2D "{}".'.format(
                    r1, r2)
                msg = self._validation_message_child(
                    msg, val[3], detailed, '100203', error_type='Missing Adjacency')
                msgs.append(msg)
        # report any errors
        if detailed:
            return msgs
        full_msg = '\n '.join(msgs)
        if raise_exception and len(msgs) != 0:
            raise ValueError(full_msg)
        return full_msg

    def check_no_room2d_overlaps(
            self, tolerance=0.01, raise_exception=True, detailed=False):
        """Check that geometries of Room2Ds do not overlap with one another.

        Overlaps in Room2Ds mean that the Room volumes will collide with one
        another during translation to Honeybee.

        Args:
            tolerance: The minimum distance that two Room2Ds geometries can overlap
                with one another and still be considered valid. (Default: 0.01,
                suitable for objects in meters).
            raise_exception: Boolean to note whether a ValueError should be raised
                if overlapping geometries are found. (Default: True).
            detailed: Boolean for whether the returned object is a detailed list of
                dicts with error info or a string with a message. (Default: False).

        Returns:
            A string with the message or a list with a dictionary if detailed is True.
        """
        # find the number of overlaps across the Room2Ds
        msgs = []
        rooms = self.room_2ds
        for i, room_1 in enumerate(rooms):
            poly_1 = room_1.floor_geometry.polygon2d
            try:
                for room_2 in rooms[i + 1:]:
                    poly_2 = room_2.floor_geometry.polygon2d
                    if poly_1.polygon_relationship(poly_2, tolerance) >= 0:
                        msg = 'Room2D "{}" overlaps with Room2D "{}" more than the '\
                            'tolerance ({}) on Story "{}".'.format(
                                room_1.display_name, room_2.display_name,
                                tolerance, self.display_name)
                        msg = self._validation_message_child(
                            msg, room_1, detailed, '100104',
                            error_type='Overlapping Room Geometries')
                        if detailed:
                            msg['element_id'].append(room_2.identifier)
                            msg['element_name'].append(room_2.display_name)
                            msg['parents'].append(msg['parents'][0])
                        msgs.append(msg)
            except IndexError:
                pass  # we have reached the end of the list
        # report any errors
        if detailed:
            return msgs
        full_msg = '\n '.join(msgs)
        if raise_exception and len(msgs) != 0:
            raise ValueError(full_msg)
        return full_msg

    def check_roofs_above_rooms(
            self, tolerance=0.01, raise_exception=True, detailed=False):
        """Check that geometries of RoofSpecifications all lie above the Room2D geometry.

        Roofs that lie below or intersect the Room2D floor plates (or the plenum floors)
        will cause an invalid calculation of the Room volume when translated
        to Honeybee. Roofs touching the edges of floor plates within the tolerance
        are permitted and can be translated to closed Honeybee Room volumes.

        Args:
            tolerance: The minimum distance between coordinate values that is
                considered a meaningful difference. (Default: 0.01, suitable
                for objects in meters).
            raise_exception: Boolean to note whether a ValueError should be raised if
                roof geometries are found below the Room2D geometries. (Default: True).
            detailed: Boolean for whether the returned object is a detailed list of
                dicts with error info or a string with a message. (Default: False).

        Returns:
            A string with the message or a list with dictionaries if detailed is True.
        """
        # find the number of cases where the roof is below the story floor
        msgs = []
        if self.multiplier == 1 and self.roof is not None:
            if self.roof.min_height < self.highest_plenum_floor_height:
                messages, bad_rooms = self.roof.check_roof_above_rooms(
                    self.room_2ds, tolerance)
                for msg, bad_rm in zip(messages, bad_rooms):
                    msg = self._validation_message_child(
                        msg, bad_rm, detailed, '100105', error_type='Invalid Roof')
                    msgs.append(msg)
        # report any errors
        if detailed:
            return msgs
        full_msg = '\n '.join(msgs)
        if raise_exception and len(msgs) != 0:
            raise ValueError(full_msg)
        return full_msg

    def check_collision_with_story(self, other_story, tolerance=0.01,
                                   raise_exception=True, detailed=False):
        """Check that the Room2Ds of this Story do not collide with those on another.

        The check is performed by first determining whether the rooms have any overlap
        in vertical space, which is greater than the tolerance. If so, a check is
        performed to evaluate whether the two room polygons overlap in plan, thereby
        indicating a collision.

        Args:
            other_story: The other Story object for which collisions with this
                Story will be evaluated.
            tolerance: The minimum distance that two Room2Ds geometries can collide
                with one another and still be considered valid. (Default: 0.01,
                suitable for objects in meters).
            raise_exception: Boolean to note whether a ValueError should be raised
                if colliding geometries are found. (Default: True).
            detailed: Boolean for whether the returned object is a detailed list of
                dicts with error info or a string with a message. (Default: False).

        Returns:
            A string with the message or a list with a dictionary if detailed is True.
        """
        # find the collisions across the Room2Ds
        msgs = []
        for room_1 in self.room_2ds:
            fh1, ch1 = room_1.floor_height, room_1.ceiling_height
            poly_1 = room_1.floor_geometry.polygon2d
            for room_2 in other_story.room_2ds:
                fh2, ch2 = room_2.floor_height, room_2.ceiling_height
                v_overlap = 0
                if fh1 < fh2 and ch1 - tolerance > fh2:
                    v_overlap = ch1 - fh2
                elif fh2 < fh1 and ch2 - tolerance > fh1:
                    v_overlap = ch2 - fh1
                if v_overlap != 0:
                    poly_2 = room_2.floor_geometry.polygon2d
                    if poly_1.polygon_relationship(poly_2, tolerance) >= 0:
                        msg = 'Room2D "{}" on Story "{}" collides with Room2D "{}" ' \
                            'on Story "{}" with a vertical overlap of {}.'.format(
                                room_1.display_name, self.display_name,
                                room_2.display_name, other_story.display_name, v_overlap)
                        msg = self._validation_message_child(
                            msg, room_1, detailed, '100108',
                            error_type='Colliding Rooms Between Stories')
                        if detailed:
                            msg['element_id'].append(room_2.identifier)
                            msg['element_name'].append(room_2.display_name)
                            msg['parents'].append(msg['parents'][0])
                        msgs.append(msg)
        # report any errors
        if detailed:
            return msgs
        full_msg = '\n '.join(msgs)
        if raise_exception and len(msgs) != 0:
            raise ValueError(full_msg)
        return full_msg

    def check_no_roof_overlaps(
            self, tolerance=0.01, raise_exception=True, detailed=False):
        """Check that geometries of RoofSpecifications do not overlap with one another.

        This is NOT a requirement for the Model to be valid but it is sometimes
        useful to check when trying to make the simplest and cleanest
        representation of the roofs.

        Args:
            tolerance: The minimum distance that two Roof geometries can overlap
                with one another and still be considered valid. Default: 0.01,
                suitable for objects in meters.
            raise_exception: Boolean to note whether a ValueError should be raised
                if overlapping geometries are found. (Default: True).
            detailed: Boolean for whether the returned object is a detailed list of
                dicts with error info or a string with a message. (Default: False).

        Returns:
            A string with the message or a list with a dictionary if detailed is True.
        """
        # find the number of overlaps in the Roof specification
        msgs = []
        if self.roof is not None:
            over_count = self.roof.overlap_count(tolerance)
            if over_count > 0:
                msg = 'Story "{}" has RoofSpecification geometry with {} overlaps ' \
                    'in it.'.format(self.display_name, over_count)
                msg = self._validation_message_child(
                    msg, self.roof, detailed, '100105', error_type='Invalid Roof')
                msgs.append(msg)
        # report any errors
        if detailed:
            return msgs
        full_msg = '\n '.join(msgs)
        if raise_exception and len(msgs) != 0:
            raise ValueError(full_msg)
        return full_msg

    def to_honeybee(self, use_multiplier=True, tolerance=0.01,
                    enforce_adj=True, enforce_solid=True):
        """Convert Dragonfly Story to a list of Honeybee Rooms.

        Args:
            use_multiplier: If True, this Story's multiplier will be passed along
                to the generated Honeybee Room objects, indicating the simulation
                will be run once for the Story and then results will be multiplied.
                You will want to set this to False when exporting each Story as
                full geometry.
            tolerance: The minimum distance in z values of floor_height and
                floor_to_ceiling_height at which adjacent Faces will be split.
                If None, no splitting will occur. (Default: 0.01, suitable for
                objects in meters).
            enforce_adj: Boolean to note whether an exception should be raised if
                an adjacency between two Room2Ds is invalid (True) or if the invalid
                Surface boundary condition should be replaced with an Outdoor
                boundary condition (False). If False, any Walls containing
                WindowParameters and an illegal boundary condition will also
                be replaced with an Outdoor boundary condition. (Default: True).
            enforce_solid: Boolean to note whether rooms should be translated
                as solid extrusions whenever translating them with custom
                roof geometry produces a non-solid result (True) or the non-solid
                room geometry should be allowed to remain in the result (False).
                The latter is useful for understanding why a particular roof
                geometry has produced a non-solid result. (Default: True).

        Returns:
            A list of honeybee Rooms that represent the Story.
        """
        # set up the multiplier
        mult = self.multiplier if use_multiplier else 1

        # if this story has any overlaps, resolve them before translation
        original_roof = None
        if self.roof is not None:
            if any(room.is_top_exposed for room in self._room_2ds):
                original_roof = self.roof
                res_roof_geo = self.roof.resolved_geometry(tolerance)
                res_roof = RoofSpecification(res_roof_geo)
                res_roof._is_resolved = True
                self.roof = res_roof

        # convert all of the Room2Ds to honeybee Rooms
        hb_rooms = []
        adjacencies = []
        for room in self._room_2ds:
            hb_room, adj = room.to_honeybee(mult, tolerance=tolerance,
                                            enforce_bc=enforce_adj,
                                            enforce_solid=enforce_solid)
            hb_rooms.append(hb_room)
            adjacencies.extend(adj)

        # assign adjacent boundary conditions that could not be set on the room level
        if len(adjacencies) != 0:
            adj_set = set()
            for adj in adjacencies:
                if adj[0].identifier not in adj_set:
                    for room in hb_rooms:
                        adj_room = adj[1][-1]
                        if room.identifier == adj_room:
                            for face in room.faces:
                                adj_face = adj[1][-2]
                                if face.identifier == adj_face:
                                    self._match_apertures(adj[0], face)
                                    other_resolve = False
                                    if self.roof is not None:  # two roofs may meet
                                        tol_area = math.sqrt(face.area) * tolerance
                                        if abs(face.area - adj[0].area) > tol_area:
                                            self._resolve_roof_adj(
                                                face, adj[0], tolerance)
                                            other_resolve = True
                                    if not other_resolve:
                                        try:
                                            adj[0].set_adjacency(face, tolerance)
                                        except (AssertionError, ValueError) as e:
                                            if enforce_adj:
                                                raise e
                                            face.boundary_condition = bcs.outdoors
                                            adj[0].boundary_condition = bcs.outdoors
                                    adj_set.add(face.identifier)
                                    break
                            break
        # put back the original roof to avoid mutating the story
        if original_roof is not None:
            self.roof = original_roof
        return hb_rooms

    def to_dict(self, abridged=False, included_prop=None):
        """Return Story as a dictionary.

        Args:
            abridged: Boolean to note whether the extension properties of the
                object (ie. construction sets) should be included in detail
                (False) or just referenced by identifier (True). Default: False.
            included_prop: List of properties to filter keys that must be included in
                output dictionary. For example ['energy'] will include 'energy' key if
                available in properties to_dict. By default all the keys will be
                included. To exclude all the keys from extensions use an empty list.
        """
        base = {'type': 'Story'}
        base['identifier'] = self.identifier
        base['display_name'] = self.display_name
        base['room_2ds'] = [r.to_dict(abridged, included_prop) for r in self._room_2ds]
        base['floor_to_floor_height'] = self.floor_to_floor_height
        base['floor_height'] = self.floor_height
        base['multiplier'] = self.multiplier
        base['story_type'] = self.type
        if self.roof is not None:
            base['roof'] = self.roof.to_dict()
        if self.user_data is not None:
            base['user_data'] = self.user_data
        base['properties'] = self.properties.to_dict(abridged, included_prop)
        return base

    @property
    def to(self):
        """Story writer object.

        Use this method to access Writer class to write the story in other formats.
        """
        return writer

    @staticmethod
    def room_2d_story_geometry_valid(room_2ds):
        """Check that a set of Room2Ds have geometry that makes a valid Story.

        This means that all of the floors of the Room2Ds are close enough to
        one another in elevation that their walls could touch each other.

        Args:
            room_2ds: An array of Room2Ds that will be checked to ensure their
                geometry makes a valid Story.

        Returns:
            True if the Room2D geometries make a valid Story. False if they do not.
        """
        if len(room_2ds) == 1:
            return True
        flr_hts = sorted([rm.floor_height for rm in room_2ds])
        avg_ftc = sum([rm.floor_to_ceiling_height for rm in room_2ds]) / len(room_2ds)
        return True if flr_hts[-1] - flr_hts[0] < avg_ftc else False

    def _room_roofs(self, room_2d, tolerance):
        """Get a RoofSpecification to be used for a specific Room2D in the Story.

        This will account for the case that a Room2D extends to the roof of
        another Story within the parent Buildings.

        Args:
            room_2d: A Room2D object within the Story for which RoofSpecifications
                will be evaluated.
        """
        # first check whether it's possible for the room to be shaped by a roof
        if not room_2d.is_top_exposed or self.multiplier != 1:
            return None  # it's impossible for the room to be shaped by a roof
        # determine all roof specifications that can influence the Room2D
        room_roofs = []
        if self._roof is not None:
            room_roofs.append(self._roof)
        if self._parent is not None:
            room_ch = room_2d.ceiling_height
            story_roofs = self._parent._story_roofs(self)
            for hgt, rf in story_roofs:
                if room_ch > hgt:  # the room extends into the roof
                    room_roofs.append(rf)
        # if there is only one or no roofs, the solution is simple
        if len(room_roofs) == 0:
            return None  # no relevant roofs were found
        if len(room_roofs) == 1:  # just return a variation of the lone roof
            if room_roofs[0]._is_resolved:
                return room_roofs[0]
            else:  # the roof of another story; we must resolve it
                res_roof_geo = room_roofs[0].resolved_geometry(tolerance)
                res_roof = RoofSpecification(res_roof_geo)
                res_roof._is_resolved = True
                return res_roof
        # if we have multiple roofs, create a new roof with everything resolved
        all_geo = [g for roof in room_roofs for g in roof]
        base_roof = RoofSpecification(all_geo)
        res_roof_geo = base_roof.resolved_geometry(tolerance)
        res_roof = RoofSpecification(res_roof_geo)
        res_roof._is_resolved = True
        return res_roof

    @staticmethod
    def _match_apertures(face_1, face2):
        for ap1, ap2 in zip(face_1.apertures, face2.apertures):
            ap1._is_operable, ap2._is_operable = False, False
            try:
                ap1.properties.energy.vent_opening = None
                ap2.properties.energy.vent_opening = None
            except AttributeError:
                pass  # honeybee-energy extension is not loaded

    @staticmethod
    def _resolve_roof_adj(face_1, face_2, tol):
        """Resolve incorrect adjacency where walls of two roofs meet."""
        # remove air boundaries so the split result is valid
        use_ab = False
        if isinstance(face_1.type, AirBoundary) or isinstance(face_2.type, AirBoundary):
            face_1.type = ftyp.wall
            face_2.type = ftyp.wall
            use_ab = True

        # split the adjacent walls with one another to get a match
        room_1, room_2 = face_1.parent, face_2.parent
        new_faces1 = room_1.coplanar_split([face_2.geometry], tol)
        new_faces2 = room_2.coplanar_split([face_1.geometry], tol)
        new_faces1 = [face_1] if len(new_faces1) == 0 else new_faces1
        new_faces2 = [face_2] if len(new_faces2) == 0 else new_faces2

        # find the adjacency and set it
        adj_geo = None
        for j, f_1 in enumerate(new_faces1):
            for k, f_2 in enumerate(new_faces2):
                if f_1.geometry.is_centered_adjacent(f_2.geometry, tol):
                    if f_1.has_sub_faces or f_2.has_sub_faces:
                        f_1.remove_sub_faces()
                        f_2.remove_sub_faces()
                    f_1.set_adjacency(f_2)
                    adj_geo = f_1.geometry
                    if use_ab:
                        f_1.type = ftyp.air_boundary
                        f_2.type = ftyp.air_boundary
                    new_faces1.pop(j)
                    new_faces2.pop(k)
                    break

        # set the boundary conditions of the other newly-created Faces
        for nf in new_faces1:
            for of in room_2.faces:
                if nf.geometry.is_centered_adjacent(of.geometry, tol):
                    if nf.has_sub_faces or of.has_sub_faces:
                        nf.remove_sub_faces()
                        of.remove_sub_faces()
                    nf.set_adjacency(of)
                    if use_ab:
                        nf.type = ftyp.air_boundary
                        of.type = ftyp.air_boundary
                    break
            else:
                if adj_geo is not None:
                    if nf.center.z < adj_geo.center.z:
                        if not isinstance(room_2[0].boundary_condition, Outdoors):
                            nf.remove_sub_faces()
                        nf.boundary_condition = room_2[0].boundary_condition
                    elif nf.center.z > adj_geo.center.z:
                        if not isinstance(room_2[-1].boundary_condition, Outdoors):
                            nf.remove_sub_faces()
                        nf.boundary_condition = room_2[-1].boundary_condition
        for nf in new_faces2:
            for of in room_1.faces:
                if nf.geometry.is_centered_adjacent(of.geometry, tol):
                    if nf.has_sub_faces or of.has_sub_faces:
                        nf.remove_sub_faces()
                        of.remove_sub_faces()
                    nf.set_adjacency(of)
                    if use_ab:
                        nf.type = ftyp.air_boundary
                        of.type = ftyp.air_boundary
                    break
            else:
                if adj_geo is not None:
                    if nf.center.z < adj_geo.center.z:
                        if not isinstance(room_1[0].boundary_condition, Outdoors):
                            nf.remove_sub_faces()
                        nf.boundary_condition = room_1[0].boundary_condition
                    elif nf.center.z > adj_geo.center.z:
                        if not isinstance(room_1[-1].boundary_condition, Outdoors):
                            nf.remove_sub_faces()
                        nf.boundary_condition = room_1[-1].boundary_condition

    def __copy__(self):
        new_s = Story(
            self.identifier, tuple(room.duplicate() for room in self._room_2ds),
            self._floor_to_floor_height, self._floor_height, self._multiplier,
            None, self._type)
        new_s._roof = None if self._roof is None else self._roof.duplicate()
        new_s._display_name = self._display_name
        new_s._user_data = None if self.user_data is None else self.user_data.copy()
        new_s._parent = self._parent
        new_s._properties._duplicate_extension_attr(self._properties)
        return new_s

    def __len__(self):
        return len(self._room_2ds)

    def __getitem__(self, key):
        return self._room_2ds[key]

    def __iter__(self):
        return iter(self._room_2ds)

    def __repr__(self):
        return 'Story: %s' % self.display_name
