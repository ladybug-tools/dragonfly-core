# coding: utf-8
"""Dragonfly Story."""
from __future__ import division

from ._base import _BaseGeometry
from .properties import StoryProperties
from .room2d import Room2D

from honeybee.typing import float_positive, int_in_range, clean_string
from honeybee.boundarycondition import Surface
from honeybee.model import Model

from ladybug_geometry.geometry3d.pointvector import Vector3D
from ladybug_geometry.geometry3d.polyline import Polyline3D
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
            If None, this value will be the maximum floor_to_ceiling_height of the
            input room_2ds.
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
        * volume
        * floor_area
        * exterior_wall_area
        * exterior_aperture_area
        * min
        * max
        * user_data
    """
    __slots__ = ('_room_2ds', '_floor_to_floor_height', '_multiplier', '_parent')

    def __init__(self, identifier, room_2ds, floor_to_floor_height=None, multiplier=1):
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
        self.floor_to_floor_height = floor_to_floor_height
        self.multiplier = multiplier

        self._parent = None  # _parent will be set when Story is added to a Building
        self._properties = StoryProperties(self)  # properties for extensions

    @classmethod
    def from_dict(cls, data, tolerance=0):
        """Initialize an Story from a dictionary.

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

        # TODO: Ensure Surface boundary conditions are updated if the serialization of
        # Room2Ds automatically flips the Room bounday polygon.
        rooms = [Room2D.from_dict(r_dict, tolerance) for r_dict in data['room_2ds']]
        f2fh = data['floor_to_floor_height'] if 'floor_to_floor_height' in data else None
        mult = data['multiplier'] if 'multiplier' in data else 1

        story = Story(data['identifier'], rooms, f2fh, mult)
        if 'display_name' in data and data['display_name'] is not None:
            story._display_name = data['display_name']
        if 'user_data' in data and data['user_data'] is not None:
            room.user_data = data['user_data']

        if data['properties']['type'] == 'StoryProperties':
            story.properties._load_extension_attr_from_dict(data['properties'])
        return story

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
            value = max([room.floor_to_ceiling_height for room in self._room_2ds])
        self._floor_to_floor_height = float_positive(value, 'floor-to-floor height')

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
    def floor_height(self):
        """Get a number for the height of the Story above the ground.

        Note that this number is always the minimum floor height of all the Story's
        room_2ds.
        """
        return min([room.floor_height for room in self._room_2ds])

    @property
    def volume(self):
        """Get a number for the volume of all the Rooms in the Story.

        Note that this property is for one story and does NOT use the multiplier.
        """
        return sum([room.volume for room in self._room_2ds])

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
        """Set all of the outdoor walls to have the same window parameters."""
        for room in self._room_2ds:
            room.set_outdoor_window_parameters(window_parameter)

    def set_outdoor_shading_parameters(self, shading_parameter):
        """Set all of the outdoor walls to have the same shading parameters."""
        for room in self._room_2ds:
            room.set_outdoor_shading_parameters(shading_parameter)

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

    def rotate_xy(self, angle, origin):
        """Rotate this Story counterclockwise in the XY plane by a certain angle.

        Args:
            angle: An angle in degrees.
            origin: A ladybug_geometry Point3D for the origin around which the
                object will be rotated.
        """
        for room in self._room_2ds:
            room.rotate_xy(angle, origin)

    def reflect(self, plane):
        """Reflect this Story across a plane.

        Args:
            plane: A ladybug_geometry Plane across which the object will be reflected.
        """
        for room in self._room_2ds:
            room.reflect(plane)

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
            if raise_exception:
                raise ValueError('A Room2D has an adjacent object that is missing '
                                 'from the model:\n{}'.format(e))
            return False
        return True

    def to_honeybee(self, use_multiplier=True, tolerance=0.01):
        """Convert Dragonfly Story to a Honeybee Model.

        Args:
            use_multiplier: If True, this Story's multiplier will be passed along
                to the generated Honeybee Room objects, indicating the simulation
                will be run once for the Story and then results will be multiplied.
                You will want to set this to False when exporting each Story as
                full geometry.
            tolerance: The minimum distance in z values of floor_height and
                floor_to_ceiling_height at which adjacent Faces will be split.
                If None, no splitting will occur. Default: 0.01, suitable for
                objects in meters.
        """
        mult = self.multiplier if use_multiplier else 1
        hb_rooms = [room.to_honeybee(mult, tolerance) for room in self._room_2ds]
        hb_mod = Model(self.identifier, hb_rooms)
        hb_mod._display_name = self._display_name
        hb_mod._user_data = self._user_data
        return hb_mod

    def to_dict(self, abridged=False, included_prop=None):
        """Return Story as a dictionary.

        Args:
            abridged: Boolean to note whether the extension properties of the
                object (ie. construciton sets) should be included in detail
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
        base['multiplier'] = self.multiplier
        base['properties'] = self.properties.to_dict(abridged, included_prop)
        if self.user_data is not None:
            base['user_data'] = self.user_data
        return base

    def __copy__(self):
        new_s = Story(self.identifier, tuple(room.duplicate() for room in self._room_2ds),
                      self._floor_to_floor_height, self._multiplier)
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
