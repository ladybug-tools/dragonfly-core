# coding: utf-8
"""Roof specification with instructions for generating sloped roofs over a Story."""
from __future__ import division
import math

from ladybug_geometry.geometry2d import Point2D, Polygon2D
from ladybug_geometry.geometry3d import Face3D


class RoofSpecification(object):
    """A roof specification with instructions for generating sloped roofs over a Story.

    Args:
        geometry: An array of Face3D objects representing the geometry of the Roof.
            Together, these Face3D should completely cover the Room2D floor_geometry
            of the Story to which the RoomSpecification is assigned.

    Properties:
        * geometry
        * boundary_geometry_2d
        * planes
        * parent
        * has_parent
        * min
        * max
    """
    __slots__ = ('_geometry', '_parent')

    def __init__(self, geometry):
        """Initialize RoofSpecification."""
        self.geometry = geometry
        self._parent = None  # will be set when RoofSpecification is added to a Story

    @classmethod
    def from_dict(cls, data):
        """Initialize an RoofSpecification from a dictionary.

        Args:
            data: A dictionary representation of an RoofSpecification object.
        """
        # check the type of dictionary
        assert data['type'] == 'RoofSpecification', 'Expected RoofSpecification ' \
            'dictionary. Got {}.'.format(data['type'])
        geometry = tuple(Face3D.from_dict(shd_geo) for shd_geo in data['geometry'])
        return cls(geometry)

    @property
    def geometry(self):
        """Get or set a tuple of Face3D objects representing the geometry of the Roof.
        """
        return self._geometry

    @geometry.setter
    def geometry(self, value):
        if not isinstance(value, tuple):
            value = tuple(value)
        assert len(value) > 0, 'RoofSpecification must have at least one Face3D.'
        for geo in value:
            assert isinstance(geo, Face3D), \
                'Expected Face3D for RoofSpecification. Got {}'.format(type(geo))
        self._geometry = value

    @property
    def boundary_geometry_2d(self):
        """Get a tuple of Polygon2D for the boundaries around each Face3D in geometry.

        These Polygons will be in the World XY coordinate system instead of the
        coordinate system of the Face3D's plane.
        """
        return tuple(
            Polygon2D(tuple(Point2D(pt.x, pt.y) for pt in geo.boundary))
            for geo in self._geometry)

    @property
    def planes(self):
        """Get a tuple of Planes for each Face3D in geometry.
        """
        return tuple(geo.plane for geo in self._geometry)

    @property
    def parent(self):
        """Parent Story if assigned. None if not assigned."""
        return self._parent

    @property
    def has_parent(self):
        """Boolean noting whether this RoofSpecification has a parent Story."""
        return self._parent is not None

    @property
    def min(self):
        """Get a Point2D for the min bounding rectangle vertex in the XY plane.

        This is useful in calculations to determine if this RoofSpecification is in
        proximity to other objects.
        """
        return self._calculate_min(self._geometry)

    @property
    def max(self):
        """Get a Point2D for the max bounding rectangle vertex in the XY plane.

        This is useful in calculations to determine if this RoofSpecification is in
        proximity to other objects.
        """
        return self._calculate_max(self._geometry)

    def move(self, moving_vec):
        """Move this RoofSpecification along a vector.

        Args:
            moving_vec: A ladybug_geometry Vector3D with the direction and distance
                to move the object.
        """
        self._geometry = tuple(geo.move(moving_vec) for geo in self._geometry)

    def rotate_xy(self, angle, origin):
        """Rotate RoofSpecification counterclockwise in the XY plane by a certain angle.

        Args:
            angle: An angle in degrees.
            origin: A ladybug_geometry Point3D for the origin around which the
                object will be rotated.
        """
        self._geometry = tuple(geo.rotate_xy(math.radians(angle), origin)
                               for geo in self._geometry)

    def reflect(self, plane):
        """Reflect this RoofSpecification across a plane.

        Args:
            plane: A ladybug_geometry Plane across which the object will be reflected.
        """
        self._geometry = tuple(geo.reflect(plane.n, plane.o) for geo in self._geometry)

    def scale(self, factor, origin=None):
        """Scale this RoofSpecification by a factor from an origin point.

        Args:
            factor: A number representing how much the object should be scaled.
            origin: A ladybug_geometry Point3D representing the origin from which
                to scale. If None, it will be scaled from the World origin (0, 0, 0).
        """
        self._geometry = tuple(geo.scale(factor, origin) for geo in self._geometry)

    def overlap_count(self, tolerance=0.01):
        """Get the number of times that the Roof geometries overlap with one another.

        This should be zero for the RoofSpecification to be valid.

        Args:
            tolerance: The minimum distance that two Roof geometries can overlap
                with one another and still be considered valid. Default: 0.01,
                suitable for objects in meters.

        Returns:
            An integer for the number of times that the roof geometries overlap
            with one another beyond the tolerance.
        """
        geo_2d = self.boundary_geometry_2d
        overlap_count = 0
        for i, poly_1 in enumerate(geo_2d):
            try:
                for poly_2 in geo_2d[i + 1:]:
                    if poly_1.polygon_relationship(poly_2, tolerance) >= 0:
                        overlap_count += 1
            except IndexError:
                pass  # we have reached the end of the list
        return overlap_count

    def to_dict(self):
        """Return RoofSpecification as a dictionary."""
        base = {'type': 'RoofSpecification'}
        base['geometry'] = [geo.to_dict() for geo in self._geometry]
        return base

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
        return RoofSpecification(self._geometry)

    def __len__(self):
        return len(self._geometry)

    def __getitem__(self, key):
        return self._geometry[key]

    def __iter__(self):
        return iter(self._geometry)

    def ToString(self):
        """Overwrite .NET ToString."""
        return self.__repr__()

    def __repr__(self):
        return 'RoofSpecification: [{} geometries]'.format(len(self._geometry))
