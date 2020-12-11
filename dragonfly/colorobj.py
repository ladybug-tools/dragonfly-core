# coding=utf-8
"""Module for coloring geometry with attributes."""
from __future__ import division

from .room2d import Room2D

from honeybee.colorobj import _ColorObject
from ladybug_geometry.geometry3d.pointvector import Point3D


class ColorRoom2D(_ColorObject):
    """Object for visualizing Room2D-level attributes.

    Args:
        room_2ds: An array of honeybee Room2Ds, which will be colored with the attribute.
        attr_name: A text string of an attribute that the input rooms should have.
            This can have '.' that separate the nested attributes from one another.
            For example, 'properties.energy.program_type'.
        legend_parameters: An optional LegendParameter object to change the display
            of the ColorRoom2D (Default: None).

    Properties:
        * room_2ds
        * attr_name
        * legend_parameters
        * attr_name_end
        * attributes
        * attributes_unique
        * floor_faces
        * graphic_container
        * min_point
        * max_point
    """
    __slots__ = ('_room_2ds',)

    def __init__(self, room_2ds, attr_name, legend_parameters=None):
        """Initialize ColorRoom2D."""
        try:  # check the input room_2ds
            room_2ds = tuple(room_2ds)
        except TypeError:
            raise TypeError(
                'Input room_2ds must be an array. Got {}.'.format(type(room_2ds)))
        assert len(room_2ds) > 0, 'ColorRoom2D must have at least one room.'
        for room in room_2ds:
            assert isinstance(room, Room2D), 'Expected dragonfly Room2D for ' \
                'ColorRoom2D room_2ds. Got {}.'.format(type(room))
        self._room_2ds = room_2ds
        self._calculate_min_max(room_2ds)

        # assign the legend parameters of this object
        self.legend_parameters = legend_parameters

        # get the attributes of the input rooms
        self._process_attribute_name(attr_name)
        self._process_attributes(room_2ds)

    @property
    def room_2ds(self):
        """Get a tuple of dragonfly Room2Ds assigned to this object."""
        return self._room_2ds

    @property
    def floor_faces(self):
        """Get an list with a Face3Ds for each Room2D."""
        return [room.floor_geometry for room in self._room_2ds]

    def _calculate_min_max(self, hb_objs):
        """Calculate maximum and minimum Point3D for a set of rooms."""
        st_rm_min = hb_objs[0].floor_geometry.min
        st_rm_max = hb_objs[0].floor_geometry.max
        min_pt = [st_rm_min.x, st_rm_min.y, st_rm_min.z]
        max_pt = [st_rm_max.x, st_rm_max.y, st_rm_max.z]

        for room in hb_objs[1:]:
            rm_min, rm_max = room.floor_geometry.min, room.floor_geometry.max
            if rm_min.x < min_pt[0]:
                min_pt[0] = rm_min.x
            if rm_min.y < min_pt[1]:
                min_pt[1] = rm_min.y
            if rm_min.z < min_pt[2]:
                min_pt[2] = rm_min.z
            if rm_max.x > max_pt[0]:
                max_pt[0] = rm_max.x
            if rm_max.y > max_pt[1]:
                max_pt[1] = rm_max.y
            if rm_max.z > max_pt[2]:
                max_pt[2] = rm_max.z

        self._min_point = Point3D(min_pt[0], min_pt[1], min_pt[2])
        self._max_point = Point3D(max_pt[0], max_pt[1], max_pt[2])

    def __repr__(self):
        """Color Room2D representation."""
        return 'Color Room2D: ({} Rooms() ({})'.format(
            len(self._room_2ds), self.attr_name_end)
