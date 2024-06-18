# coding: utf-8
"""Dragonfly Context Shade."""
from __future__ import division
import math

from ladybug_geometry.geometry3d import Point3D, Face3D, Mesh3D

from honeybee.shade import Shade
from honeybee.shademesh import ShadeMesh
from honeybee.typing import clean_string

from ._base import _BaseGeometry
from .properties import ContextShadeProperties
import dragonfly.writer.context as writer


class ContextShade(_BaseGeometry):
    """A Context Shade object defined by an array of Face3Ds and/or Mesh3Ds.

    Args:
        identifier: Text string for a unique ContextShade ID. Must be < 100 characters
            and not contain any spaces or special characters.
        geometry: An array of ladybug_geometry Face3D and/or Mesh3D objects
            that together represent the context shade.
        is_detached: Boolean to note whether this object is detached from other
            geometry. Cases where this should be True include shade representing
            surrounding buildings or context. (Default: True).

    Properties:
        * identifier
        * display_name
        * geometry
        * is_detached
        * area
        * min
        * max
        * user_data
    """
    __slots__ = ('_geometry', '_is_detached')

    def __init__(self, identifier, geometry, is_detached=True):
        """Initialize ContextShade."""
        _BaseGeometry.__init__(self, identifier)  # process the identifier

        # process the geometry
        if not isinstance(geometry, tuple):
            geometry = tuple(geometry)
        assert len(geometry) > 0, 'ContextShade must have at least one geometry.'
        for shd_geo in geometry:
            assert isinstance(shd_geo, (Face3D, Mesh3D)), 'Expected ladybug_geometry ' \
                'Face3D or Mesh3D. Got {}'.format(type(shd_geo))
        self._geometry = geometry
        self.is_detached = is_detached

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

        is_detached = data['is_detached'] if 'is_detached' in data else True
        geometry = []
        for shd_geo in data['geometry']:
            if shd_geo['type'] == 'Face3D':
                geometry.append(Face3D.from_dict(shd_geo))
            else:
                geometry.append(Mesh3D.from_dict(shd_geo))
        shade = cls(data['identifier'], geometry, is_detached)
        if 'display_name' in data and data['display_name'] is not None:
            shade.display_name = data['display_name']
        if 'user_data' in data and data['user_data'] is not None:
            shade.user_data = data['user_data']

        if data['properties']['type'] == 'ContextShadeProperties':
            shade.properties._load_extension_attr_from_dict(data['properties'])
        return shade

    @classmethod
    def from_honeybee(cls, shade):
        """Initialize an ContextShade from a Honeybee Shade or ShadeMesh.

        Args:
            shade: A Honeybee Shade or ShadeMesh object.
        """
        con_shade = cls(shade.identifier, [shade.geometry], shade.is_detached)
        con_shade._display_name = shade.display_name
        con_shade._user_data = None if shade.user_data is None \
            else shade.user_data.copy()
        con_shade.properties.from_honeybee(shade.properties)
        return con_shade

    @property
    def geometry(self):
        """Get a tuple of Face3D and/or Mesh3D objects that represent the context shade.
        """
        return self._geometry

    @property
    def is_detached(self):
        """Get or set a boolean for whether this object is detached from other geometry.
        """
        return self._is_detached

    @is_detached.setter
    def is_detached(self, value):
        try:
            self._is_detached = bool(value)
        except TypeError:
            raise TypeError(
                'Expected boolean for ContextShade.is_detached. Got {}.'.format(value))

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

    def snap_to_grid(self, grid_increment, tolerance=0.01):
        """Snap this object to the nearest XY grid node defined by an increment.

        Note that, even though ContextShade geometry is defined using 3D vertices,
        only the X and Y coordinates will be snapped, which is consistent with
        how the Room2D.snap_to_grid method works.

        All properties assigned to the ContextShade will be preserved and any
        degenerate geometries are automatically cleaned out of the result.

        Args:
            grid_increment: A positive number for dimension of each grid cell. This
                typically should be equal to the tolerance or larger but should
                not be larger than the smallest detail of the ContextShade that you
                wish to resolve.
            tolerance: The minimum difference between the coordinate values at
                which they are considered co-located. (Default: 0.01,
                suitable for objects in meters).
        """
        # define a list to hold all of the new geometry
        new_geometry = []

        # loop through the current geometry and snap the vertices
        for geo in self._geometry:
            if isinstance(geo, Face3D):
                new_boundary, new_holes = [], None
                for pt in geo.boundary:
                    new_x = grid_increment * round(pt.x / grid_increment)
                    new_y = grid_increment * round(pt.y / grid_increment)
                    new_boundary.append(Point3D(new_x, new_y, pt.z))
                if geo.holes is not None:
                    new_holes = []
                    for hole in geo.holes:
                        new_hole = []
                        for pt in hole:
                            new_x = grid_increment * round(pt.x / grid_increment)
                            new_y = grid_increment * round(pt.y / grid_increment)
                            new_hole.append(Point3D(new_x, new_y, pt.z))
                        new_holes.append(new_hole)
                n_geo = Face3D(new_boundary, geo.plane, new_holes)
                try:  # catch all degeneracy in the process
                    n_geo = n_geo.remove_duplicate_vertices(tolerance)
                    new_geometry.append(n_geo)
                except AssertionError:  # degenerate geometry
                    pass
            elif isinstance(geo, Mesh3D):
                new_vertices = []
                for pt in geo.vertices:
                    new_x = grid_increment * round(pt.x / grid_increment)
                    new_y = grid_increment * round(pt.y / grid_increment)
                    new_vertices.append(Point3D(new_x, new_y, pt.z))
                n_geo = Mesh3D(new_vertices, geo.faces)
                new_geometry.append(n_geo)

        # rebuild the new floor geometry and assign it to the Room2D
        if len(new_geometry) != 0:
            self._geometry = new_geometry

    def to_honeybee(self):
        """Convert Dragonfly ContextShade to a list of Honeybee Shades and ShadeMeshes.
        """
        shades = []
        for i, shd_geo in enumerate(self._geometry):
            if isinstance(shd_geo, Face3D):
                shade = Shade('{}_{}'.format(self.identifier, i), shd_geo,
                              is_detached=self.is_detached)
                shade._properties = self.properties.to_honeybee(shade, False)
            else:
                shade = ShadeMesh('{}_{}'.format(self.identifier, i), shd_geo,
                                  is_detached=self.is_detached)
                shade._properties = self.properties.to_honeybee(shade, True)
            shade.display_name = self.display_name
            shade.user_data = None if self.user_data is None else self.user_data.copy()
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
        base['geometry'] = [shd_geo.to_dict() for shd_geo in self._geometry]
        if not self.is_detached:
            base['is_detached'] = self.is_detached
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
        new_shd = ContextShade(self.identifier, self._geometry, self.is_detached)
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
