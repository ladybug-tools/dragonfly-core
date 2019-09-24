# coding: utf-8
"""Dragonfly Building."""
from ._base import _BaseGeometry
from .properties import BuildingProperties
from .story import Story

from honeybee.typing import int_in_range
from honeybee.shade import Shade
from honeybee.model import Model

from ladybug_geometry.geometry3d.pointvector import Vector3D
from ladybug_geometry.geometry3d.face import Face3D


class Building(_BaseGeometry):
    """A complete Building defined by Stories.

    Properties:
        * name
        * display_name
        * unique_stories
        * multipliers
        * all_stories
        * unique_room_2ds
        * all_room_2ds
        * height
        * height_from_first_floor
        * volume
        * floor_area
        * exterior_wall_area
        * exterior_aperture_area
    """
    __slots__ = ('_unique_stories', '_multipliers')

    def __init__(self, name, unique_stories, multipliers=None):
        """A complete Building defined by Stories.

        Args:
            name: Room name. Must be < 100 characters.
            unique_stories: A list or tuple of unique dragonfly Story objects that
                together form the entire building. Stories should generally be ordered
                from lowest floor to highest floor. Note that, if a given Story is
                repeated several times over the height of the building, the unique
                story included in this list should be the first (lowest) story
                of the repeated floors.
            multipliers: A list of integers with the same length as the input
                unique_stories that denotes the number of times that each of the
                unique_stories is repeated over the height of the building. If None,
                ir will be assumed that each story is repeated only once. Default: None.
        """
        _BaseGeometry.__init__(self, name)  # process the name

        # process the story geometry
        if not isinstance(unique_stories, tuple):
            unique_stories = tuple(unique_stories)
        assert len(unique_stories) > 0, 'Building must have at least one Story.'
        for story in unique_stories:
            assert isinstance(story, Story), \
                'Expected dragonfly Story. Got {}'.format(type(story))
            story._parent = self
        self._unique_stories = unique_stories

        # process the input multipliers
        if multipliers is None:
            self._multipliers = [1 for i in self._unique_stories]
        else:
            assert len(multipliers) == len(self._unique_stories), 'The length of ' \
                'Building multipliers must match the length of unique_stories. ' \
                '{} != {}'.format(len(multipliers), len(self._unique_stories))
            new_mults = []
            for m in multipliers:
                new_mults.append(int_in_range(m, 1, input_name='building multipliers'))
            self._multipliers = multipliers

        self._properties = BuildingProperties(self)  # properties for extensions

    @classmethod
    def from_dict(cls, data):
        """Initialize an Building from a dictionary.

        Args:
            data: A dictionary representation of a Building object.
        """
        # check the type of dictionary
        assert data['type'] == 'Building', 'Expected Building dictionary. ' \
            'Got {}.'.format(data['type'])

        stories = [Story.from_dict(s_dict) for s_dict in data['unique_stories']]
        mults = data['multipliers'] if 'multipliers' in data else None

        building = Building(data['name'], stories, mults)
        if 'display_name' in data and data['display_name'] is not None:
            building._display_name = data['display_name']

        if data['properties']['type'] == 'BuildingProperties':
            building.properties._load_extension_attr_from_dict(data['properties'])
        return building

    @property
    def unique_stories(self):
        """A tuple of only unique Story objects that form the Building."""
        return self._unique_stories

    @property
    def multipliers(self):
        """A tuple of integers denoting how many times each unique_story is repeated."""
        return tuple(self._multipliers)

    @property
    def all_stories(self):
        """A list of all Story objects that form the Building."""
        all_stories = []
        for story, m in zip(self._unique_stories, self._multipliers):
            all_stories.append(story)
            if m != 1:
                for i in range(m - 1):
                    m_vec = Vector3D(0, 0, story.floor_to_floor_height * (i + 1))
                    new_story = story.duplicate()
                    new_story.move(m_vec)
                    all_stories.append(new_story)
        return all_stories

    @property
    def unique_room_2ds(self):
        """A list of the unique Room2D objects that form the Building."""
        rooms = []
        for room in self._unique_stories:
            rooms.extend(room.room_2ds)
        return rooms

    @property
    def all_room_2ds(self):
        """A list of all Room2D objects that form the Building."""
        rooms = []
        for room in self.all_stories:
            rooms.extend(room.room_2ds)
        return rooms

    @property
    def height(self):
        """Get a number for the height of the top ceiling of the Building."""
        return self._unique_stories[-1].floor_height + \
            (self._unique_stories[-1].floor_to_floor_height * self._multipliers[-1])

    @property
    def height_from_first_floor(self):
        """Get a the height difference between the top ceiling and bottom floor."""
        return self.height - self._unique_stories[0].floor_height

    @property
    def volume(self):
        """Get a number for the volume of all the Rooms in the Building."""
        return sum([story.volume * m for story, m in
                    zip(self._unique_stories, self._multipliers)])

    @property
    def floor_area(self):
        """Get a number for the total floor area in the Building."""
        return sum([story.floor_area * m for story, m in
                    zip(self._unique_stories, self._multipliers)])

    @property
    def exterior_wall_area(self):
        """Get a number for the total exterior wall area in the Building."""
        return sum([story.exterior_wall_area * m for story, m in
                    zip(self._unique_stories, self._multipliers)])

    @property
    def exterior_aperture_area(self):
        """Get a number for the total exterior aperture area in the Building."""
        return sum([story.exterior_aperture_area * m for story, m in
                    zip(self._unique_stories, self._multipliers)])

    def shade_representation(self, tolerance):
        """A list of honeybee Shade objects representing the building geometry.

        These can be used to account for this Building's shade in the simulation of
        another nearby Building.

        Args:
            tolerance: The minimum distance between points at which they are
                not considered touching.
        """
        context_shades = []
        for story, mult in zip(self.unique_stories, self.multipliers):
            extru_vec = Vector3D(0, 0, story.floor_to_floor_height * mult)
            for i, seg in enumerate(story.outline_segments(tolerance)):
                extru_geo = Face3D.from_extrusion(seg, extru_vec)
                shd_name = '{}_{}_{}'.format(self.name, story.name, i)
                context_shades.append(Shade(shd_name, extru_geo))
            # TODO: add a Shade object to cap the extrusion once lb_geometry has polyline
        return context_shades

    def auto_assign_top_bottom_floors(self):
        """Set the first Story as the ground floor and the last to be the top.

        If the last floor in the unique_stories has a multiplier greater than 1, this
        method will automatically create a new unique story at the top of the building
        with the is_top_floor property set to True.

        Note that this method may not give the desired result if the building has
        several top floors (like towers of different heights connected by a plinth).
        For such a case, it might be better to manually assign the is_top_floor property
        of each of the relevant Stories.
        """
        self._unique_stories[0].is_ground_floor = True
        if self._multipliers[-1] == 1:
            self._unique_stories[-1].is_top_floor = True
        else:
            top = self._unique_stories[-1].duplicate()
            move_vec = Vector3D(0, 0, top.floor_to_floor_height * self._multipliers[-1])
            top.move(move_vec)
            top.is_top_floor = True
            self._unique_stories = self._unique_stories + (top,)
            self._multipliers[-1] = self._multipliers[-1] - 1
            self._multipliers.append(1)

    def set_outdoor_glazing_parameters(self, glazing_parameter):
        """Set all of the outdoor walls to have the same glazing parameters."""
        for story in self._unique_stories:
            story.set_outdoor_glazing_parameters(glazing_parameter)

    def set_outdoor_shading_parameters(self, shading_parameter):
        """Set all of the outdoor walls to have the same shading parameters."""
        for story in self._unique_stories:
            story.set_outdoor_shading_parameters(shading_parameter)

    def move(self, moving_vec):
        """Move this Building along a vector.

        Args:
            moving_vec: A ladybug_geometry Vector3D with the direction and distance
                to move the object.
        """
        for story in self._unique_stories:
            story.move(moving_vec)

    def rotate_xy(self, angle, origin):
        """Rotate this Building counterclockwise in the XY plane by a certain angle.

        Args:
            angle: An angle in degrees.
            origin: A ladybug_geometry Point3D for the origin around which the
                object will be rotated.
        """
        for story in self._unique_stories:
            story.rotate_xy(angle, origin)

    def reflect(self, plane):
        """Reflect this Building across a plane.

        Args:
            plane: A ladybug_geometry Plane across which the object will be reflected.
        """
        for story in self._unique_stories:
            story.reflect(plane)

    def scale(self, factor, origin=None):
        """Scale this Building by a factor from an origin point.

        Args:
            factor: A number representing how much the object should be scaled.
            origin: A ladybug_geometry Point3D representing the origin from which
                to scale. If None, it will be scaled from the World origin (0, 0, 0).
        """
        for story in self._unique_stories:
            story.scale(factor, origin)

    def to_honeybee(self, tolerance):
        """Convert Dragonfly Building to a Honeybee Model.

        Args:
            tolerance: The minimum distance in z values of floor_height and
                floor_to_ceiling_height at which adjacent Faces will be split.
                If None, no splitting will occur. Default: None.
        """
        # TODO: Add an option to only export unique rooms
        # once we have multipliers in honeybee-core
        hb_rooms = [room.to_honeybee(tolerance) for room in self.all_room_2ds]
        return Model(self.display_name, hb_rooms)

    def to_dict(self, abridged=False, included_prop=None):
        """Return Building as a dictionary.

        Args:
            abridged: Boolean to note whether the extension properties of the
                object (ie. construciton sets) should be included in detail
                (False) or just referenced by name (True). Default: False.
            included_prop: List of properties to filter keys that must be included in
                output dictionary. For example ['energy'] will include 'energy' key if
                available in properties to_dict. By default all the keys will be
                included. To exclude all the keys from extensions use an empty list.
        """
        base = {'type': 'Building'}
        base['name'] = self.name
        base['display_name'] = self.display_name
        base['unique_stories'] = [s.to_dict(abridged, included_prop)
                                  for s in self._unique_stories]
        base['multipliers'] = self.multipliers
        base['properties'] = self.properties.to_dict(abridged, included_prop)
        return base

    def __copy__(self):
        new_b = Building(self.name,
                         tuple(story.duplicate() for story in self._unique_stories),
                         self._multipliers)
        new_b._display_name = self.display_name
        new_b._properties._duplicate_extension_attr(self._properties)
        return new_b

    def __len__(self):
        return len(self._unique_stories)

    def __getitem__(self, key):
        return self._unique_stories[key]

    def __iter__(self):
        return iter(self._unique_stories)

    def __repr__(self):
        return 'Building: %s' % self.display_name
