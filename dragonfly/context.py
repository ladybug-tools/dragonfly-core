# coding: utf-8
"""Dragonfly Context Shade."""
from __future__ import division

from ._base import _BaseGeometry
from .properties import ContextShadeProperties
import dragonfly.writer.context as writer

from honeybee.shade import Shade
from honeybee.typing import clean_string

from ladybug_geometry.geometry3d.face import Face3D

import math


class ContextShade(_BaseGeometry):
    """A Context Shade object defined by an array of Face3Ds (eg. canopy, trees, etc.).

    Args:
        identifier: Text string for a unique ContextShade ID. Must be < 100 characters
            and not contain any spaces or special characters.
        geometry: An array of ladybug_geometry Face3D objects that together
            represent the context shade.

    Properties:
        * identifier
        * display_name
        * geometry
        * area
        * min
        * max
        * user_data
    """
    __slots__ = ('_geometry',)

    def __init__(self, identifier, geometry):
        """A Context Shade object defined by an array of Face3Ds."""
        _BaseGeometry.__init__(self, identifier)  # process the identifier

        # process the geometry
        if not isinstance(geometry, tuple):
            geometry = tuple(geometry)
        assert len(geometry) > 0, 'ContextShade must have at least one Face3D.'
        for shd_geo in geometry:
            assert isinstance(shd_geo, Face3D), \
                'Expected ladybug_geometry Face3D. Got {}'.format(type(shd_geo))
        self._geometry = geometry

        self._properties = ContextShadeProperties(self)  # properties for extensions

    @classmethod
    def from_dict(cls, data):
        """Initialize an ContextShade from a dictionary.

        Args:
            data: A dictionary representation of an ContextShade object.
        """
        # check the type of dictionary
        assert data['type'] == 'ContextShade', 'Expected ContextShade dictionary. ' \
            'Got {}.'.format(data['type'])

        geometry = tuple(Face3D.from_dict(shd_geo) for shd_geo in data['geometry'])
        shade = cls(data['identifier'], geometry)
        if 'display_name' in data and data['display_name'] is not None:
            shade.display_name = data['display_name']
        if 'user_data' in data and data['user_data'] is not None:
            shade.user_data = data['user_data']

        if data['properties']['type'] == 'ContextShadeProperties':
            shade.properties._load_extension_attr_from_dict(data['properties'])
        return shade

    @property
    def geometry(self):
        """Get a tuple of Face3D objects that together represent the context shade."""
        return self._geometry

    @property
    def area(self):
        """Get a number for the total surface area of the ContextShade."""
        return sum([geo.area for geo in self._geometry])

    @property
    def min(self):
        """Get a Point2D for the min bounding rectangle vertex in the XY plane.

        This is useful in calculations to determine if this ContextShade is in
        proximity to other objects.
        """
        return self._calculate_min(self._geometry)

    @property
    def max(self):
        """Get a Point2D for the max bounding rectangle vertex in the XY plane.

        This is useful in calculations to determine if this ContextShade is in
        proximity to other objects.
        """
        return self._calculate_max(self._geometry)

    def add_prefix(self, prefix):
        """Change the identifier of this object by inserting a prefix.

        This is particularly useful in workflows where you duplicate and edit
        a starting object and then want to combine it with the original object
        into one Model (like making a model of repeated shades) since all objects
        within a Model must have unique identifiers.

        Args:
            prefix: Text that will be inserted at the start of this object's identifier
                and display_name. It is recommended that this prefix be short to
                avoid maxing out the 100 allowable characters for dragonfly identifiers.
        """
        self._identifier = clean_string('{}_{}'.format(prefix, self.identifier))
        self.display_name = '{}_{}'.format(prefix, self.display_name)
        self.properties.add_prefix(prefix)

    def move(self, moving_vec):
        """Move this ContextShade along a vector.

        Args:
            moving_vec: A ladybug_geometry Vector3D with the direction and distance
                to move the object.
        """
        self._geometry = tuple(shd_geo.move(moving_vec) for shd_geo in self._geometry)
        self.properties.move(moving_vec)

    def rotate_xy(self, angle, origin):
        """Rotate this ContextShade counterclockwise in the XY plane by a certain angle.

        Args:
            angle: An angle in degrees.
            origin: A ladybug_geometry Point3D for the origin around which the
                object will be rotated.
        """
        self._geometry = tuple(shd_geo.rotate_xy(math.radians(angle), origin)
                               for shd_geo in self._geometry)
        self.properties.rotate_xy(angle, origin)

    def reflect(self, plane):
        """Reflect this ContextShade across a plane.

        Args:
            plane: A ladybug_geometry Plane across which the object will be reflected.
        """
        self._geometry = tuple(shd_geo.reflect(plane.n, plane.o)
                               for shd_geo in self._geometry)
        self.properties.reflect(plane)

    def scale(self, factor, origin=None):
        """Scale this ContextShade by a factor from an origin point.

        Args:
            factor: A number representing how much the object should be scaled.
            origin: A ladybug_geometry Point3D representing the origin from which
                to scale. If None, it will be scaled from the World origin (0, 0, 0).
        """
        self._geometry = tuple(shd_geo.scale(factor, origin)
                               for shd_geo in self._geometry)
        self.properties.scale(factor, origin)

    def to_honeybee(self):
        """Convert Dragonfly ContextShade to an array of Honeybee Shades."""
        shades = []
        for i, shd_geo in enumerate(self._geometry):
            # create the shade object
            shade = Shade('{}_{}'.format(self.identifier, i), shd_geo, is_detached=True)
            shade.display_name = '{}_{}'.format(self.display_name, i)
            # transfer any extension properties assigned to the Shade
            shade._properties = self.properties.to_honeybee(shade)
            shades.append(shade)
        return shades

    def to_dict(self, abridged=False, included_prop=None):
        """Return ContextShade as a dictionary.

        Args:
            abridged: Boolean to note whether the extension properties of the
                object (ie. materials, transmittance schedule) should be included in
                detail (False) or just referenced by identifier (True). Default: False.
            included_prop: List of properties to filter keys that must be included in
                output dictionary. For example ['energy'] will include 'energy' key if
                available in properties to_dict. By default all the keys will be
                included. To exclude all the keys from extensions use an empty list.
        """
        base = {'type': 'ContextShade'}
        base['identifier'] = self.identifier
        base['display_name'] = self.display_name
        base['properties'] = self.properties.to_dict(abridged, included_prop)
        enforce_upper_left = True if 'energy' in base['properties'] else False
        base['geometry'] = [shd_geo.to_dict(False, enforce_upper_left)
                            for shd_geo in self._geometry]
        if self.user_data is not None:
            base['user_data'] = self.user_data
        return base

    @property
    def to(self):
        """ContextShade writer object.

        Use this method to access Writer class to write the context in other formats.
        """
        return writer

    def __copy__(self):
        new_shd = ContextShade(self.identifier, self._geometry)
        new_shd._display_name = self.display_name
        new_shd._user_data = None if self.user_data is None else self.user_data.copy()
        new_shd._properties._duplicate_extension_attr(self._properties)
        return new_shd

    def __len__(self):
        return len(self._geometry)

    def __getitem__(self, key):
        return self._geometry[key]

    def __iter__(self):
        return iter(self._geometry)

    def __repr__(self):
        return 'ContextShade: %s' % self.display_name
