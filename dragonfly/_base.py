# coding: utf-8
"""Base class for all geometry objects."""
from __future__ import division

from honeybee.typing import valid_string

from ladybug_geometry.geometry2d.pointvector import Point2D


class _BaseGeometry(object):
    """A base class for all geometry objects.

    Args:
        name: Object name. Must be < 100 characters.

    Properties:
        * name
        * display_name
    """
    __slots__ = ('_name', '_display_name', '_properties')

    def __init__(self, name):
        """Initialize base object."""
        self.name = name
        self._properties = None

    @property
    def name(self):
        """Get or set the object name (including only legal characters)."""
        return self._name

    @name.setter
    def name(self, value):
        self._name = valid_string(value, 'dragonfly object name')
        self._display_name = value

    @property
    def display_name(self):
        """Original input name by user.

        If there are no illegal characters in name then name and display_name will
        be the same. Legal characters are ., A-Z, a-z, 0-9, _ and -.
        Invalid characters are automatically removed from the original name for
        compatability with simulation engines.
        """
        return self._display_name

    @property
    def properties(self):
        """Object properties, including Radiance, Energy and other properties."""
        return self._properties

    def duplicate(self):
        """Get a copy of this object."""
        return self.__copy__()

    @staticmethod
    def _calculate_min(geometry_objects):
        """Calculate min Point2D around an array of geometry with min attributes.

        This is used in all functions that calculate bounding rectangles around
        dragonfly objects and assess when two objects are in close proximity.
        """
        min_pt = [geometry_objects[0].min.x, geometry_objects[0].min.y]

        for room in geometry_objects[1:]:
            if room.min.x < min_pt[0]:
                min_pt[0] = room.min.x
            if room.min.y < min_pt[1]:
                min_pt[1] = room.min.y

        return Point2D(min_pt[0], min_pt[1])

    @staticmethod
    def _calculate_max(geometry_objects):
        """Calculate max Point2D around an array of geometry with max attributes.

        This is used in all functions that calculate bounding rectangles around
        dragonfly objects and assess when two objects are in close proximity.
        """
        max_pt = [geometry_objects[0].max.x, geometry_objects[0].max.y]

        for room in geometry_objects[1:]:
            if room.max.x > max_pt[0]:
                max_pt[0] = room.max.x
            if room.max.y > max_pt[1]:
                max_pt[1] = room.max.y

        return Point2D(max_pt[0], max_pt[1])

    def __copy__(self):
        new_obj = self.__class__(self.name)
        new_obj._display_name = self.display_name
        return new_obj

    def ToString(self):
        return self.__repr__()

    def __repr__(self):
        return 'Dragonfly Base Object: %s' % self.display_name
