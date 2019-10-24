# coding: utf-8
"""Dragonfly Story."""
from ._base import _BaseGeometry
from .properties import StoryProperties
from .room2d import Room2D

from honeybee.typing import float_positive, int_in_range
from honeybee.model import Model

from ladybug_geometry.geometry3d.pointvector import Vector3D
from ladybug_geometry.geometry3d.polyface import Polyface3D


class Story(_BaseGeometry):
    """A Story of a building defined by an extruded Room2Ds.

    Properties:
        * name
        * display_name
        * room_2ds
        * floor_to_floor_height
        * multiplier
        * is_ground_floor
        * is_top_floor
        * parent
        * has_parent
        * floor_height
        * volume
        * floor_area
        * exterior_wall_area
        * exterior_aperture_area
    """
    __slots__ = ('_room_2ds', '_floor_to_floor_height', '_multiplier',
                 '_is_ground_floor', '_is_top_floor', '_parent')

    def __init__(self, name, room_2ds, floor_to_floor_height=None, multiplier=1,
                 is_ground_floor=False, is_top_floor=False):
        """A Story of a building defined by an extruded Floor2Ds.

        Args:
            name: Story name. Must be < 100 characters.
            room_2ds: A list or tuple of dragonfly Room2D objects that
                together form an entire story of a building.
            floor_to_floor_height: A number for the distance from the floor plate of
                this Story to the floor of the story above this one (if it exists).
                If None, this value will be the maximum floor_to_ceiling_height of the
                input room_2ds.
            multiplier: An integer with that denotes the number of times that this
                Story is repeated over the height of the building. Default: 1.
            is_ground_floor: A boolean to note whether this Story is a ground floor,
                in which case the floor Faces of the resulting Rooms will have a Ground
                boundary condition instead of an Adiabatic one. Default: False.
            is_top_floor: A boolean to note whether this Story is a top floor, in which
                case the ceiling Faces of the resulting Rooms will have an Outdoor
                boundary condition instead of an Adiabatic one. Default: False.
        """
        _BaseGeometry.__init__(self, name)  # process the name

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
        self.is_ground_floor = is_ground_floor
        self.is_top_floor = is_top_floor

        self._parent = None  # _parent will be set when Story is added to a Building
        self._properties = StoryProperties(self)  # properties for extensions

    @classmethod
    def from_dict(cls, data):
        """Initialize an Story from a dictionary.

        Args:
            data: A dictionary representation of a Story object.
        """
        # check the type of dictionary
        assert data['type'] == 'Story', 'Expected Story dictionary. ' \
            'Got {}.'.format(data['type'])

        rooms = [Room2D.from_dict(r_dict) for r_dict in data['room_2ds']]
        f2fh = data['floor_to_floor_height'] if 'floor_to_floor_height' in data else None
        mult = data['multiplier'] if 'multiplier' in data else 1
        gf = data['is_ground_floor'] if 'is_ground_floor' in data else False
        tf = data['is_top_floor'] if 'is_top_floor' in data else False

        story = Story(data['name'], rooms, f2fh, mult, gf, tf)
        if 'display_name' in data and data['display_name'] is not None:
            story._display_name = data['display_name']

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
        https://bigladdersoftware.com/epx/docs/9-1/tips-and-tricks-using-energyplus/
        using-multipliers-zone-and-or-window.html
        """
        return self._multiplier

    @multiplier.setter
    def multiplier(self, value):
        self._multiplier = int_in_range(value, 1, input_name='room multiplier')

    @property
    def is_ground_floor(self):
        """Get or set a boolean to note whether this Story is a ground floor."""
        return self._is_ground_floor

    @is_ground_floor.setter
    def is_ground_floor(self, value):
        self._is_ground_floor = bool(value)

    @property
    def is_top_floor(self):
        """Get or set a boolean to note whether this Story is a top floor."""
        return self._is_top_floor

    @is_top_floor.setter
    def is_top_floor(self, value):
        self._is_top_floor = bool(value)

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

    def floor_geometry(self, tolerance):
        """Get a ladybug_geometry Polyface3D object representing the floor plate.

        Args:
            tolerance: The minimum distance between points at which they are
                not considered touching.
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

    def outline_segments(self, tolerance):
        """Get a list of LineSegment3D objects for the outline of the floor plate.

        Note that these segments include both the boundary surrounding the floor
        and any holes for courtyards that exist within the floor.

        Args:
            tolerance: The minimum distance between points at which they are
                not considered touching.
        """
        return self.floor_geometry(tolerance).naked_edges

    def room_by_name(self, room_name):
        """Get a Room2D from this Story using its name.

        Result will be None if the Room2D is not found in the Story.

        Args:
            room_name: String for the name of the Room2D to be retrieved from this model.
        """
        for room in self._room_2ds:
            if room.name == room_name:
                return room
        return None

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

    def solve_room_2d_adjacency(self, tolerance):
        """Automatically solve adjacencies across the Room2Ds in this story.

        Args:
            tolerance: The minimum difference between the coordinate values of two
                faces at which they can be considered centered adjacent.
        """
        Room2D.solve_adjacency(self._room_2ds, tolerance)

    def intersect_room_2d_adjacency(self, tolerance):
        """Automatically intersect the line segments of the Story's Room2Ds.

        Note that this method effectively erases all assigned boundary conditions,
        glazing parameters and shading parameters as the original segments are
        subdivided. As such, it is recommended that this method be used before all
        other steps when creating a Story.

        Args:
            tolerance: The minimum difference between the coordinate values of two
                faces at which they can be considered centered adjacent.
        """
        self._room_2ds = Room2D.intersect_adjacency(self._room_2ds, tolerance)

    def set_outdoor_glazing_parameters(self, glazing_parameter):
        """Set all of the outdoor walls to have the same glazing parameters."""
        for room in self._room_2ds:
            room.set_outdoor_glazing_parameters(glazing_parameter)

    def set_outdoor_shading_parameters(self, shading_parameter):
        """Set all of the outdoor walls to have the same shading parameters."""
        for room in self._room_2ds:
            room.set_outdoor_shading_parameters(shading_parameter)

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

    def to_honeybee(self, use_multiplier=True, tolerance=None):
        """Convert Dragonfly Story to a Honeybee Model.

        Args:
            use_multiplier: If True, this Story's multiplier will be passed along
                to the generated Honeybee Room objects, indicating the simulation
                will be run once for the Story and then results will be multiplied.
                You will want to set this to False when exporting each Story as
                full geometry.
            tolerance: The minimum distance in z values of floor_height and
                floor_to_ceiling_height at which adjacent Faces will be split.
                If None, no splitting will occur. Default: None.
        """
        mult = self.multiplier if use_multiplier else 1
        hb_rooms = [room.to_honeybee(mult, tolerance) for room in self._room_2ds]
        return Model(self.display_name, hb_rooms)

    def to_dict(self, abridged=False, included_prop=None):
        """Return Story as a dictionary.

        Args:
            abridged: Boolean to note whether the extension properties of the
                object (ie. construciton sets) should be included in detail
                (False) or just referenced by name (True). Default: False.
            included_prop: List of properties to filter keys that must be included in
                output dictionary. For example ['energy'] will include 'energy' key if
                available in properties to_dict. By default all the keys will be
                included. To exclude all the keys from extensions use an empty list.
        """
        base = {'type': 'Story'}
        base['name'] = self.name
        base['display_name'] = self.display_name
        base['room_2ds'] = [r.to_dict(abridged, included_prop) for r in self._room_2ds]
        base['floor_to_floor_height'] = self.floor_to_floor_height
        base['multiplier'] = self.multiplier
        base['is_ground_floor'] = self.is_ground_floor
        base['is_top_floor'] = self.is_top_floor
        base['properties'] = self.properties.to_dict(abridged, included_prop)
        return base

    def __copy__(self):
        new_s = Story(self.name, tuple(room.duplicate() for room in self._room_2ds),
                      self._floor_to_floor_height, self._multiplier,
                      self._is_ground_floor, self._is_top_floor)
        new_s._display_name = self.display_name
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
