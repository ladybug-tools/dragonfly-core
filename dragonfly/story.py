# coding: utf-8
"""Dragonfly Story."""
from __future__ import division

from ._base import _BaseGeometry
from .properties import StoryProperties
from .room2d import Room2D
import dragonfly.writer.story as writer

from honeybee.typing import float_positive, int_in_range, clean_string, \
    invalid_dict_error
from honeybee.boundarycondition import boundary_conditions as bcs
from honeybee.boundarycondition import Outdoors, Surface
from honeybee.altnumber import autocalculate
from honeybee.shade import Shade
from honeybee.room import Room

from ladybug_geometry.geometry2d.polygon import Polygon2D
from ladybug_geometry.geometry3d.pointvector import Vector3D
from ladybug_geometry.geometry3d.ray import Ray3D
from ladybug_geometry.geometry3d.polyline import Polyline3D
from ladybug_geometry.geometry3d.face import Face3D
from ladybug_geometry.geometry3d.polyface import Polyface3D


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
            Story is repeated over the height of the building. Default: 1.

    Properties:
        * identifier
        * display_name
        * room_2ds
        * floor_to_floor_height
        * multiplier
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
        * user_data
    """
    __slots__ = ('_room_2ds', '_floor_to_floor_height', '_floor_height',
                 '_multiplier', '_parent')

    def __init__(self, identifier, room_2ds, floor_to_floor_height=None,
                 floor_height=None, multiplier=1):
        """A Story of a building defined by an extruded Floor2Ds."""
        _BaseGeometry.__init__(self, identifier)  # process the identifier

        # process the story geometry
        if not isinstance(room_2ds, tuple):
            room_2ds = tuple(room_2ds)
        assert len(room_2ds) > 0, 'Story must have at least one Room2D.'
        for room in room_2ds:
            assert isinstance(room, Room2D), \
                'Expected dragonfly Room2D. Got {}'.format(type(room))
            room._parent = self
        self._room_2ds = room_2ds

        # process the input properties
        self.floor_height = floor_height
        self.floor_to_floor_height = floor_to_floor_height
        self.multiplier = multiplier

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

        story = Story(data['identifier'], rooms, f2fh, fh, mult)
        if 'display_name' in data and data['display_name'] is not None:
            story._display_name = data['display_name']
        if 'user_data' in data and data['user_data'] is not None:
            room.user_data = data['user_data']

        if data['properties']['type'] == 'StoryProperties':
            story.properties._load_extension_attr_from_dict(data['properties'])
        return story

    @classmethod
    def from_honeybee(cls, identifier, rooms, tolerance):
        """Initialize a Story from a list of Honeybee Rooms.

        Args:
            identifier: Text string for a unique Story ID. Must be < 100 characters
                and not contain any spaces or special characters.
            rooms: A list of Honeybee Room objects.
            tolerance: The maximum difference between values at which point vertices
                are considered to be the same.
        """
        # create the Room2Ds from the Honeybee Rooms
        room_2ds = [Room2D.from_honeybee(hb_room, tolerance) for hb_room in rooms]
        room_2ds = [room for room in room_2ds if room is not None]
        # re-set the adjacencies in relation to the Room2D segments
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
                                        adj_f_1 = all_adj_faces[i]
                                        adj_f_2 = all_adj_faces[i + x + 1]
                                        adj_f_1.pop(adj_f_1.index(j))
                                        adj_f_2.pop(adj_f_2.index(k))
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
                if remove_win:
                    room_2ds[r_i]._window_parameters[seg_i] = None
        return cls(identifier, room_2ds)

    @property
    def room_2ds(self):
        """A tuple of Room2D objects that form an entire story of a building."""
        return self._room_2ds

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
        """Get or set a number for the abolute floor height of the Story.

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
        Story is run once and then the result is mutliplied by the multiplier.
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
    def parent(self):
        """Parent Building if assigned. None if not assigned."""
        return self._parent

    @property
    def has_parent(self):
        """Boolean noting whether this Story has a parent Building."""
        return self._parent is not None

    @property
    def floor_area(self):
        """Get a number for the total floor area in the Story.

        Note that this property is for one story and does NOT use the multiplier.
        """
        return sum([room.floor_area for room in self._room_2ds])

    @property
    def exterior_wall_area(self):
        """Get a number for the total exterior wall area in the Story.

        Note that this property is for one story and does NOT use the multiplier.
        """
        return sum([room.exterior_wall_area for room in self._room_2ds])

    @property
    def exterior_aperture_area(self):
        """Get a number for the total exterior aperture area in the Story.

        Note that this property is for one story and does NOT use the multiplier.
        """
        return sum([room.exterior_aperture_area for room in self._room_2ds])

    @property
    def volume(self):
        """Get a number for the volume of all the Rooms in the Story.

        Note that this property is for one story and does NOT use the multiplier.
        """
        return sum([room.volume for room in self._room_2ds])

    @property
    def is_above_ground(self):
        """Get a boolean to note if this Story is above the ground.

        The story is considered above the ground if at least one of its Room2Ds
        has an outdoor boundary condition.
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
                not considered touching. Default: 0.01, suitable for objects
                in meters.
        """
        plines = self.outline_polylines(tolerance)
        if len(plines) == 1:  # can be represented with a single Face3D
            return [Face3D(plines[0].vertices[:-1])]
        else:  # need to separate holes from distinct Face3Ds
            faces = [Face3D(pl.vertices[:-1]) for pl in plines]
            faces.sort(key=lambda x: x.area, reverse=True)
            base_face = faces[0]
            remain_faces = list(faces[1:])

            all_face3ds = []
            while len(remain_faces) > 0:
                all_face3ds.append(Room2D._match_holes_to_face(
                    base_face, remain_faces, tolerance))
                if len(remain_faces) > 1:
                    base_face = remain_faces[0]
                    del remain_faces[0]
                elif len(remain_faces) == 1:  # lone last Face3D
                    all_face3ds.append(remain_faces[0])
                    del remain_faces[0]
            return all_face3ds

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

        This method is used internally to convert from a Story with a mutliplier
        to fully-detailed Stories with unique identifiers.

        Args:
            prefix: Text that will be inserted at the start of this object's
                (and child segments') identifier and display_name. It is recommended
                that this prefix be short to avoid maxing out the 100 allowable
                characters for dragonfly identifiers.
        """
        self._identifier = clean_string('{}_{}'.format(prefix, self.identifier))
        self.display_name = '{}_{}'.format(prefix, self.display_name)
        self.properties.add_prefix(prefix)
        for room in self.room_2ds:
            room.add_prefix(prefix)

    def add_room_2d(self, room_2d):
        """Add a Room2D to this Story.

        Args:
            room_2d: A Room2D object to be added to this Story.
        """
        assert isinstance(room_2d, Room2D), \
            'Expected dragonfly Room2D. Got {}'.format(type(room_2d))
        room_2d._parent = self
        self._room_2ds = self._room_2ds + (room_2d,)

    def add_room_2ds(self, rooms_2ds):
        """Add a list of Room2Ds to this Story.

        Args:
            room_2d: A list of Room2D objects to be added to this Story.
        """
        for room in rooms_2ds:
            self.add_room_2d(room)

    def solve_room_2d_adjacency(self, tolerance=0.01):
        """Automatically solve adjacencies across the Room2Ds in this story.

        Args:
            tolerance: The minimum difference between the coordinate values of two
                faces at which they can be considered adjacent. Default: 0.01,
                suitable for objects in meters.
        """
        Room2D.solve_adjacency(self._room_2ds, tolerance)

    def intersect_room_2d_adjacency(self, tolerance=0.01):
        """Automatically intersect the line segments of the Story's Room2Ds.

        Note that this method effectively erases all assigned boundary conditions,
        window parameters and shading parameters as the original segments are
        subdivided. As such, it is recommended that this method be used before all
        other steps when creating a Story.

        Args:
            tolerance: The minimum difference between the coordinate values of two
                at which they can be considered adjacent. Default: 0.01,
                suitable for objects in meters.
        """
        self._room_2ds = Room2D.intersect_adjacency(self._room_2ds, tolerance)

    def remove_room_2d_colinear_vertices(self, tolerance=0.01):
        """Automatically remove colinear or duplicate vertices for the Story's Room2Ds.

        Note that this method effectively erases all assigned boundary conditions,
        window parameters and shading parameters as many of the original segments
        may be deleted. As such, it is recommended that this method be used before
        all other steps when creating a Story.

        Args:
            tolerance: The minimum difference between the coordinate values of two
                faces at which they can be considered adjacent. Default: 0.01,
                suitable for objects in meters.
        """
        self._room_2ds = tuple(room.remove_colinear_vertices(tolerance)
                               for room in self._room_2ds)

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
        """Set all child Room2Ds of this object to have floors in contact with the ground.

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

    def set_top_exposed_by_story_above(self, story_above, tolerance=0.01):
        """Set the child Room2Ds of this object to have ceilings exposed to the outdoors.

        Args:
            story_above: A Story object that sits above this Story. Each Room2D
                of this Story will be checked to see if it intersects the Story
                above and the top exposure will be set based on this.
            tolerance: The minimum difference between the coordinate values of two
                faces at which they can be considered adjacent. Default: 0.01,
                suitable for objects in meters.
        """
        up_vec = Vector3D(0, 0, 1)
        for room in self._room_2ds:
            face_ray = Ray3D(room._floor_geometry._point_on_face(tolerance), up_vec)
            for other_room in story_above._room_2ds:
                if other_room._floor_geometry.intersect_line_ray(face_ray) is not None:
                    room.is_top_exposed = False
                    break
            else:
                room.is_top_exposed = True

    def make_underground(self):
        """Make this Story underground by setting all Room2D segments to have Ground BCs.

        Note that this method only changes the outdoor walls of the Room2Ds to have
        Ground boundary conditions and, if the floors of the story are also in
        contact with the ground, the set_ground_contact should be used in addition
        to this method.

        Also note that this method will throw an exception if any of the Room2Ds have
        WindowParameters assigned to them (since Ground boundary conditions are)
        not compatible with windows. So using the set_outdoor_window_parameters
        method and passing None to remove all windows is often recommended
        before running this method.
        """
        for room in self._room_2ds:
            for i, bc in enumerate(room._boundary_conditions):
                if isinstance(bc, Outdoors):
                    room.set_boundary_condition(i, bcs.ground)

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
        self.properties.rotate_xy(angle, origin)

    def reflect(self, plane):
        """Reflect this Story across a plane.

        Args:
            plane: A ladybug_geometry Plane across which the object will be reflected.
        """
        for room in self._room_2ds:
            room.reflect(plane)
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
        self.properties.scale(factor, origin)

    def check_missing_adjacencies(self, raise_exception=True):
        """Check that all Room2Ds have adjacent objects that exist within this Story."""
        bc_obj_ids = []
        for room in self._room_2ds:
            for bc in room._boundary_conditions:
                if isinstance(bc, Surface):
                    bc_obj_ids.append(bc.boundary_condition_objects[-1])
        try:
            self.rooms_by_identifier(bc_obj_ids)
        except ValueError as e:
            msg = 'A Room2D has an adjacent object that is missing ' \
                'from the model:\n{}'.format(e)
            if raise_exception:
                raise ValueError(msg)
            return msg
        return ''

    def to_honeybee(self, use_multiplier=True, add_plenum=False, tolerance=0.01):
        """Convert Dragonfly Story to a list of Honeybee Rooms.

        Args:
            use_multiplier: If True, this Story's multiplier will be passed along
                to the generated Honeybee Room objects, indicating the simulation
                will be run once for the Story and then results will be multiplied.
                You will want to set this to False when exporting each Story as
                full geometry.
            add_plenum: Boolean to indicate whether ceiling/floor plenums should
                be auto-generated for the Rooms. (Default: False).
            tolerance: The minimum distance in z values of floor_height and
                floor_to_ceiling_height at which adjacent Faces will be split.
                If None, no splitting will occur. Default: 0.01, suitable for
                objects in meters.

        Returns:
            A list of honeybee Rooms that represent the Story.
        """
        # set up the multiplier
        mult = self.multiplier if use_multiplier else 1

        # convert all of the Room2Ds to honeybee Rooms
        hb_rooms = []
        adjacencies = []
        for room in self._room_2ds:
            hb_room, adj = room.to_honeybee(
                mult, add_plenum=add_plenum, tolerance=tolerance)
            if isinstance(hb_room, Room):
                hb_rooms.append(hb_room)
            else:  # list of rooms with plenums
                hb_rooms.extend(hb_room)
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
                                    adj[0].set_adjacency(face, tolerance)
                                    adj_set.add(face.identifier)
                                    break
                            break
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
        base['properties'] = self.properties.to_dict(abridged, included_prop)
        if self.user_data is not None:
            base['user_data'] = self.user_data
        return base

    @property
    def to(self):
        """Story writer object.

        Use this method to access Writer class to write the story in other formats.
        """
        return writer

    def __copy__(self):
        new_s = Story(
            self.identifier, tuple(room.duplicate() for room in self._room_2ds),
            self._floor_to_floor_height, self._floor_height, self._multiplier)
        new_s._display_name = self.display_name
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
