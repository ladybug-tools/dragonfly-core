# coding: utf-8
"""Dragonfly Building."""
from ._base import _BaseGeometry
from .properties import BuildingProperties
from .story import Story
from .room2d import Room2D

from honeybee.model import Model
from honeybee.shade import Shade
from honeybee.boundarycondition import Surface

from ladybug_geometry.geometry3d.pointvector import Vector3D
from ladybug_geometry.geometry3d.face import Face3D

try:
    from itertools import izip as zip  # python 2
except ImportError:
    xrange = range  # python 3


class Building(_BaseGeometry):
    """A complete Building defined by Stories.

    Properties:
        * name
        * display_name
        * unique_stories
        * unique_room_2ds
        * height
        * height_from_first_floor
        * volume
        * floor_area
        * exterior_wall_area
        * exterior_aperture_area
    """
    __slots__ = ('_unique_stories',)

    def __init__(self, name, unique_stories):
        """A complete Building defined by Stories.

        Args:
            name: Building name. Must be < 100 characters.
            unique_stories: A list or tuple of unique dragonfly Story objects that
                together form the entire building. Stories should generally be ordered
                from lowest floor to highest floor. Note that, if a given Story is
                repeated several times over the height of the building, the unique
                story included in this list should be the first (lowest) story
                of the repeated floors.
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

        self._properties = BuildingProperties(self)  # properties for extensions

    @classmethod
    def from_footprint(cls, name, footprint, floor_to_floor_heights, tolerance=None):
        """Initialize a Building from an array of Face3Ds representing a footprint.

        All of the resulting Room2Ds will have a floor-to-ceiling height equal to the
        Story floor-to-floor height.

        Args:
            name: Building name. Must be < 100 characters.
            footprint: An array of horizontal ladybug-geometry Face3Ds that together
                represent the the footprint of the Building.
            floor_to_floor_heights: An array of float values with a length equal
                to the number of stories in the Building. Each value in the list
                represents the floor_to_floor height of the Story starting from
                the first floor and then moving to the top floor.
            tolerance: The maximum difference between z values at which point vertices
                are considered to be in the same horizontal plane. This is used to check
                that all vertices of the input floor_geometry lie in the same horizontal
                floor plane. Default is None, which will not perform any check.
        """
        # generate the unique Room2Ds from the footprint
        room_2ds = cls._generate_room_2ds(footprint, floor_to_floor_heights[0],
                                          name, 1, tolerance)

        # generate the unique stories from the floor_to_floor_heights
        # TODO: Add an input for core_perimeter_offsets once we have straight skeletons
        stories = []
        total_height = 0
        prev_flr_to_flr = None
        for i, flr_hgt in enumerate(floor_to_floor_heights):
            if flr_hgt != prev_flr_to_flr:
                if i != 0:
                    rooms = [room.duplicate() for room in room_2ds]
                    move_vec = Vector3D(0, 0, total_height)
                    for j, room in enumerate(rooms):
                        room.move(move_vec)
                        room.floor_to_ceiling_height = flr_hgt
                        room.name = '{}_Floor{}_Room{}'.format(name, i + 1, j + 1)
                else:
                    rooms = room_2ds
                stories.append(Story('{}_Floor{}'.format(name, i + 1), rooms, flr_hgt))
            else:
                stories[-1].multiplier += 1
            total_height += flr_hgt
            prev_flr_to_flr = flr_hgt

        # automatically set the top and bottom floors
        stories[0].is_ground_floor = True
        stories[-1].is_top_floor = True

        return cls(name, stories)

    @classmethod
    def from_all_story_geometry(cls, name, all_story_geometry, floor_to_floor_heights,
                                tolerance):
        """Initialize a Building from an array of Face3Ds arrays representing all floors.

        This method will test to see which of the stories are geometrically unique
        (accouting for both the floor plate geometry and the floor_to_floor_heights).
        It will only include the unique floor geometries in the resulting Building.

        All of the resulting Room2Ds will have a floor-to-ceiling height equal to the
        Story floor-to-floor height.

        Args:
            name: Building name. Must be < 100 characters.
            all_story_geometry: An array of arrays with each sub-array possessing
                horizontal ladybug-geometry Face3Ds that representing the floor
                plates of the building. Together, these Face3Ds should represent
                all Stories of a building and each array of Face3Ds should together
                represent one Story.
            floor_to_floor_heights: An array of float values with a length equal
                to the number of stories in the Building. Each value in the list
                represents the floor_to_floor height of the Story starting from
                the first floor and then moving to the top floor.
            tolerance: The maximum difference between x, y, and z values at which
                point vertices are considered to be the same. This is required as
                a means to determine which floor geometries are equivalent to one
                another.
        """
        # generate the first story of the building
        room_2ds = cls._generate_room_2ds(
            all_story_geometry[0], floor_to_floor_heights[0], name, 1, tolerance)
        stories = [Story('{}_Floor1'.format(name), room_2ds, floor_to_floor_heights[0])]

        # generate the remaining unique stories from the floor_to_floor_heights
        # TODO: Add an input for core_perimeter_offsets once we have straight skeletons
        remaining_geo = all_story_geometry[1:]
        remaining_flr_hgts = floor_to_floor_heights[1:]
        prev_geo = all_story_geometry[0]
        prev_flr_to_flr = floor_to_floor_heights[0]
        for i, (room_geo, flr_hgt) in enumerate(zip(remaining_geo, remaining_flr_hgts)):
            # test is anything is geometrically different
            if flr_hgt != prev_flr_to_flr or len(room_geo) != len(prev_geo) or \
                    not all(cls._is_story_equivalent(rm1, rm2, tolerance)
                            for rm1, rm2 in zip(room_geo, prev_geo)):
                room_2ds = cls._generate_room_2ds(
                    room_geo, flr_hgt, name, i + 2, tolerance)
                stories.append(Story('{}_Floor{}'.format(name, i + 2), room_2ds, flr_hgt))
            else:  # geometry is the same as the floor below
                stories[-1].multiplier += 1
            prev_geo = room_geo
            prev_flr_to_flr = flr_hgt

        # automatically set the top and bottom floors
        stories[0].is_ground_floor = True
        stories[-1].is_top_floor = True

        return cls(name, stories)

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

        building = Building(data['name'], stories)
        if 'display_name' in data and data['display_name'] is not None:
            building._display_name = data['display_name']

        if data['properties']['type'] == 'BuildingProperties':
            building.properties._load_extension_attr_from_dict(data['properties'])
        return building

    @property
    def unique_stories(self):
        """Get a tuple of only unique Story objects that form the Building.

        Repeated stories are represented only once but will have a non-unity multiplier.
        """
        return self._unique_stories

    @property
    def unique_room_2ds(self):
        """Get a list of the unique Room2D objects that form the Building."""
        rooms = []
        for story in self._unique_stories:
            rooms.extend(story.room_2ds)
        return rooms

    @property
    def height(self):
        """Get a number for the height of the top ceiling of the Building."""
        last_flr = self._unique_stories[-1]
        return last_flr.floor_height + \
            (last_flr.floor_to_floor_height * last_flr.multiplier)

    @property
    def height_from_first_floor(self):
        """Get a the height difference between the top ceiling and bottom floor."""
        return self.height - self._unique_stories[0].floor_height

    @property
    def volume(self):
        """Get a number for the volume of all the Rooms in the Building.

        Note that this property uses the story multipliers.
        """
        return sum([story.volume * story.multiplier
                    for story in self._unique_stories])

    @property
    def floor_area(self):
        """Get a number for the total floor area in the Building.

        Note that this property uses the story multipliers.
        """
        return sum([story.floor_area * story.multiplier
                    for story in self._unique_stories])

    @property
    def exterior_wall_area(self):
        """Get a number for the total exterior wall area in the Building.

        Note that this property uses the story multipliers.
        """
        return sum([story.exterior_wall_area * story.multiplier
                    for story in self._unique_stories])

    @property
    def exterior_aperture_area(self):
        """Get a number for the total exterior aperture area in the Building.

        Note that this property uses the story multipliers.
        """
        return sum([story.exterior_aperture_area * story.multiplier
                    for story in self._unique_stories])

    def all_stories(self):
        """Get a list of all Story objects that form the Building.

        The Story objects in this property each have a multiplier of 1 and repeated
        stories are represented will their own Story object.

        Note that this property correctly assigns is_ground_floor and is_top_floor
        properties to the unique_stories with a multiplier. So an unique story
        with a True is_ground_floor and a multiplier of 2 will result in only
        one of the two stories having is_ground_floor set to True.
        """
        all_stories = []
        for story in self._unique_stories:
            new_story = story.duplicate()
            self._rename_story(new_story, 1)
            new_story.multiplier = 1
            if story.multiplier != 1 and story.is_top_floor:
                new_story.is_top_floor = False  # top floor is above this one
            all_stories.append(new_story)

            if story.multiplier != 1:
                for i in range(story.multiplier - 1):
                    new_story = story.duplicate()
                    self._rename_story(new_story, i + 2)
                    new_story.multiplier = 1
                    m_vec = Vector3D(0, 0, story.floor_to_floor_height * (i + 1))
                    new_story.move(m_vec)
                    if story.is_ground_floor:  # this story is above the ground floor
                        new_story.is_ground_floor = False
                    if story.is_top_floor:
                        if i + 2 != story.multiplier:
                            new_story.is_top_floor = False  # top floor is above this one
                    all_stories.append(new_story)
        return all_stories

    def all_room_2ds(self):
        """Get a list of all Room2D objects that form the Building."""
        rooms = []
        for story in self.all_stories():
            rooms.extend(story.room_2ds)
        return rooms

    def shade_representation(self, tolerance):
        """A list of honeybee Shade objects representing the building geometry.

        These can be used to account for this Building's shade in the simulation of
        another nearby Building.

        Args:
            tolerance: The minimum distance between points at which they are
                not considered touching.
        """
        context_shades = []
        for story in self.unique_stories:
            extru_vec = Vector3D(0, 0, story.floor_to_floor_height * story.multiplier)
            for i, seg in enumerate(story.outline_segments(tolerance)):
                extru_geo = Face3D.from_extrusion(seg, extru_vec)
                shd_name = '{}_{}_{}'.format(self.name, story.name, i)
                context_shades.append(Shade(shd_name, extru_geo))
            # TODO: add a Shade object to cap the extrusion once lb_geometry has polyline
        return context_shades

    def auto_assign_top_bottom_floors(self):
        """Set the first Story as the ground floor and the last to be the top.

        Note that this methods does not change the number of unique_stories.

        Also note that this method may not give the desired result if the building has
        several top floors (like towers of different heights connected by a plinth).
        For such a case, it might be better to manually assign the is_top_floor property
        of each of the relevant Stories.
        """
        self._unique_stories[0].is_ground_floor = True
        self._unique_stories[-1].is_top_floor = True

    def separate_top_bottom_floors(self):
        """Separate top/bottom stories with non-unity multipliers into their own stories.

        If any Story is found with is_ground_floor or is_top_floor set to True
        along with a multiplier greater than 1, this method will automatically
        create a new unique story at the top or bottom of the building with a
        multiplier of 1 and is_ground_floor or is_top_floor property set to True.

        This is particularly helpful when planning to use to_honeybee workflows
        with multipliers but one wants to account for the heat exchange of the
        top or bottom floors (since ground and outdoor boundary conditions are
        ignored in to_honeybee() when the multiplier is greater than 1).
        """
        new_ground_floors = []
        new_top_floors = []
        for story in self._unique_stories:
            if story.multiplier == 1:
                continue
            elif story.is_ground_floor and story.is_top_floor:
                if story.multiplier >= 3:  # separate into 3 stories
                    story.is_ground_floor = False  # no longer the ground floor
                    story.is_top_floor = False  # no longer the top floor
                    new_ground_floors.append(self._separated_ground_floor(story))
                    new_top_floors.append(self._separated_top_floor(story))
                    story.multiplier = story.multiplier - 2
                    story.move(Vector3D(0, 0, story.floor_to_floor_height))  # 2nd floor
                else:  # separate into 2 stories
                    story.is_top_floor = False  # no longer the top floor
                    new_top_floors.append(self._separated_top_floor(story))
                    story.multiplier = 1
            elif story.is_ground_floor:
                story.is_ground_floor = False  # no longer the ground floor
                new_ground_floors.append(self._separated_ground_floor(story))
                story.multiplier = story.multiplier - 1
                story.move(Vector3D(0, 0, story.floor_to_floor_height))  # 2nd floor
            elif story.is_top_floor:
                story.is_top_floor = False  # no longer the top floor
                new_top_floors.append(self._separated_top_floor(story))
                story.multiplier = story.multiplier - 1
            else:
                continue

        self._unique_stories = tuple(new_ground_floors) + self._unique_stories + \
            tuple(new_top_floors)

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

    def to_honeybee(self, use_multiplier=True, tolerance=None):
        """Convert Dragonfly Building to a Honeybee Model.

        Args:
            use_multiplier: If True, the multipliers on this Building's Stories will be
                passed along to the generated Honeybee Room objects, indicating the
                simulation will be run once for each unique room and then results
                will be multiplied. If False, full geometry objects will be written
                for each and every floor in the building that are represented through
                multipliers and all resulting multipliers will be 1. Default: True
            tolerance: The minimum distance in z values of floor_height and
                floor_to_ceiling_height at which adjacent Faces will be split.
                If None, no splitting will occur. Default: None.
        """
        if use_multiplier:
            hb_rooms = [room.to_honeybee(story.multiplier, tolerance)
                        for story in self._unique_stories for room in story]
        else:
            hb_rooms = [room.to_honeybee(1, tolerance) for room in self.all_room_2ds()]
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
        base['properties'] = self.properties.to_dict(abridged, included_prop)
        return base

    @staticmethod
    def _generate_room_2ds(face3d_array, flr_to_flr, bldg_name, flr_count, tolerance):
        """Generate Room2D objects given geometry and information about their parent."""
        room_2ds = []
        for i, room_geo in enumerate(face3d_array):
            room = Room2D('{}_Floor{}_Room{}'.format(bldg_name, flr_count, i + 1),
                          room_geo, flr_to_flr, tolerance=tolerance)
            room_2ds.append(room)
        return room_2ds

    @staticmethod
    def _is_story_equivalent(face1, face2, tolerance):
        """Check whether the area, XY centerpoint and XY first point match between Face3D.

        Args:
            face1: First Face3D to check.
            face2: Second Face3D to check.
            tolerance: The maximum difference between x, y, and z values at which
                point vertices are considered to be the same.

        Returns:
            True if face1 is geometrically equivalent to face 2 else False.
        """
        # check wether the center points match within tolerance.
        cent1 = face1.center
        cent2 = face2.center
        if abs(cent1.x - cent2.x) > tolerance or abs(cent1.y - cent2.y) > tolerance:
            return False

        # check wether the point at start matches within tolerance
        start1 = face1[0]
        start2 = face2[0]
        if abs(start1.x - start2.x) > tolerance or abs(start1.y - start2.y) > tolerance:
            return False

        # check whether areas match within tolerance
        area_tol = tolerance ** 2
        if abs(face1.area - face2.area) > area_tol:
            return False

        return True

    @staticmethod
    def _separated_ground_floor(base_story):
        """Get a separated ground floor from a base_story."""
        bottom = base_story.duplicate()  # generate a new bottom floor
        bottom.is_ground_floor = True
        bottom.multiplier = 1
        Building._rename_story(bottom, 'Ground')
        return bottom

    @staticmethod
    def _separated_top_floor(base_story):
        """Get a separated top floor from a base_story."""
        top = base_story.duplicate()  # generate a new top floor
        move_vec = Vector3D(0, 0, top.floor_to_floor_height * top.multiplier)
        top.move(move_vec)
        top.is_top_floor = True
        top.multiplier = 1
        Building._rename_story(top, 'Top')
        return top

    @staticmethod
    def _rename_story(story, id):
        """Rename a Story and all of the children Room2Ds.

        Args:
            story: A Story object to be re-named.
            id: A unique ID to be appended to all of the names.
        """
        story.name = '{}_{}'.format(story.name, id)
        for room in story.room_2ds:
            room.name = '{}_{}'.format(room.name, id)
            for i, bc in enumerate(room._boundary_conditions):
                if isinstance(bc, Surface):
                    bc_obj_name = bc.boundary_condition_object.split('..Face')
                    bc_rm_name = bc_obj_name[0]
                    face_num = bc_obj_name[1]
                    new_bc_rm_name = '{}_{}'.format(bc_rm_name, id)
                    new_face_name = '{}..Face{}'.format(new_bc_rm_name, face_num)
                    room._boundary_conditions[i] = \
                        Surface((new_face_name, new_bc_rm_name))

    def __copy__(self):
        new_b = Building(self.name,
                         tuple(story.duplicate() for story in self._unique_stories))
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
