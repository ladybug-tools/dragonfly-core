# coding: utf-8
"""Shading Parameters with instructions for generating shades."""
from __future__ import division

from honeybee.typing import float_in_range, float_positive, int_positive

from ladybug_geometry.geometry2d.pointvector import Vector2D


class _ShadingParameterBase(object):
    """Base object for all shading parameters.

    This object records all of the methods that must be overwritten on a shading
    parameter object for it to be successfully be applied in dragonfly workflows.
    """
    __slots__ = ()

    def __init__(self):
        pass

    def add_shading_to_face(self, face, tolerance=0.01):
        """Add Shades to a Honeybee Face using these Window Parameters."""
        pass

    def scale(self, factor):
        """Get a scaled version of these ShadingParameters.

        This method is called within the scale methods of the Room2D.

        Args:
            factor: A number representing how much the object should be scaled.
        """
        return self

    @classmethod
    def from_dict(cls, data):
        """Create ShadingParameterBase from a dictionary.

        .. code-block:: python

            {
            "type": "ShadingParameterBase"
            }
        """
        assert data['type'] == 'ShadingParameterBase', \
            'Expected ShadingParameterBase dictionary. Got {}.'.format(data['type'])
        return cls()

    def to_dict(self):
        """Get ShadingParameterBase as a dictionary."""
        return {'type': 'ShadingParameterBase'}

    def duplicate(self):
        """Get a copy of this object."""
        return self.__copy__()

    def ToString(self):
        return self.__repr__()

    def __copy__(self):
        return _ShadingParameterBase()

    def __repr__(self):
        return 'ShadingParameterBase'


class ExtrudedBorder(_ShadingParameterBase):
    """Instructions for extruded borders over all windows in the wall.

    Args:
        depth: A number for the depth of the border.

    Properties:
        * depth
    """
    __slots__ = ('_depth',)

    def __init__(self, depth):
        """Instructions for extruded borders over all windows in the wall."""
        self._depth = float_positive(depth, 'overhang width')

    @property
    def depth(self):
        """Get a number for the depth of the border."""
        return self._depth

    def add_shading_to_face(self, face, tolerance=0.01):
        """Add Shades to a Honeybee Face using these Shading Parameters.

        Args:
            face: A honeybee-core Face object.
            tolerance: An optional value to return None if the overhang has a length less
                than the tolerance. Default: 0.01, suitable for objects in meters.
        """
        for ap in face.apertures:
            ap.extruded_border(self.depth)

    def scale(self, factor):
        """Get a scaled version of these ShadingParameters.

        This method is called within the scale methods of the Room2D.

        Args:
            factor: A number representing how much the object should be scaled.
        """
        return ExtrudedBorder(self.depth * factor)

    @classmethod
    def from_dict(cls, data):
        """Create ExtrudedBorder from a dictionary.

        .. code-block:: json

            {
            "type": "ExtrudedBorder",
            "depth": 0.5
            }
        """
        assert data['type'] == 'ExtrudedBorder', \
            'Expected ExtrudedBorder dictionary. Got {}.'.format(data['type'])
        return cls(data['depth'])

    def to_dict(self):
        """Get ExtrudedBorder as a dictionary."""
        return {'type': 'ExtrudedBorder',
                'depth': self.depth}

    def __copy__(self):
        return ExtrudedBorder(self.depth)

    def __key(self):
        """A tuple based on the object properties, useful for hashing."""
        return self.depth

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        return isinstance(other, ExtrudedBorder) and self.__key() == other.__key()

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return 'ExtrudedBorder:\n depth: {}'.format(self.depth)


class Overhang(_ShadingParameterBase):
    """Instructions for a single overhang over an entire wall.

    Args:
        depth: A number for the overhang depth.
        angle: A number for the for an angle to rotate the overhang in degrees.
            Positive values indicate a downward rotation. Negative values indicate
            an upward rotation. Default is 0 for no rotation.

    Properties:
        * depth
        * angle
    """
    __slots__ = ('_depth', '_angle')

    def __init__(self, depth, angle=0):
        """Instructions for a single overhang over an entire wall."""
        self._depth = float_positive(depth, 'overhang width')
        self._angle = float_in_range(angle, -90, 90, 'overhang angle')

    @property
    def depth(self):
        """Get a number for the overhang depth."""
        return self._depth

    @property
    def angle(self):
        """Get a number for the overhang angle."""
        return self._angle

    def add_shading_to_face(self, face, tolerance=0.01):
        """Add Shades to a Honeybee Face using these Shading Parameters.

        Args:
            face: A honeybee-core Face object.
            tolerance: An optional value to return None if the overhang has a length less
                than the tolerance. Default: 0.01, suitable for objects in meters.
        """
        face.overhang(self.depth, self.angle, False, tolerance)

    def scale(self, factor):
        """Get a scaled version of these ShadingParameters.

        This method is called within the scale methods of the Room2D.

        Args:
            factor: A number representing how much the object should be scaled.
        """
        return Overhang(self.depth * factor, self.angle)

    @classmethod
    def from_dict(cls, data):
        """Create Overhang from a dictionary.

        .. code-block:: python

            {
            "type": "Overhang",
            "depth": 1.5,
            "angle": 0
            }
        """
        assert data['type'] == 'Overhang', \
            'Expected Overhang dictionary. Got {}.'.format(data['type'])
        angle = data['angle'] if 'angle' in data else 0
        return cls(data['depth'], angle)

    def to_dict(self):
        """Get Overhang as a dictionary."""
        return {'type': 'Overhang',
                'depth': self.depth,
                'angle': self.angle}

    def __copy__(self):
        return Overhang(self.depth, self.angle)

    def __key(self):
        """A tuple based on the object properties, useful for hashing."""
        return (self.depth, self.angle)

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        return isinstance(other, Overhang) and self.__key() == other.__key()

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return 'Overhang:\n depth: {}\n angle: {}'.format(self.depth, self.angle)


class _LouversBase(_ShadingParameterBase):
    """Instructions for a series of louvered Shades over a Face.

    Args:
        depth: A number for the depth to extrude the louvers.
        offset: A number for the distance to louvers from this Face.
            Default is 0 for no offset.
        angle: A number for the for an angle to rotate the louvers in degrees.
            Default is 0 for no rotation.
        contour_vector: A Vector2D for the direction along which contours
            are generated. This 2D vector will be interpreted into a 3D vector
            within the plane of this Face. (0, 1) will usually generate
            horizontal contours in 3D space, (1, 0) will generate vertical
            contours, and (1, 1) will generate diagonal contours. Default: (0, 1).
        flip_start_side: Boolean to note whether the side the louvers start from
            should be flipped. Default is False to have contours on top or right.
            Setting to True will start contours on the bottom or left.

    Properties:
        * depth
        * offset
        * angle
        * contour_vector
        * flip_start_side
    """
    __slots__ = ('_depth', '_offset', '_angle', '_contour_vector', '_flip_start_side')

    def __init__(self, depth, offset=0, angle=0, contour_vector=Vector2D(0, 1),
                 flip_start_side=False):
        """Initialize LouversBase."""
        self._depth = float_positive(depth, 'louver depth')
        self._offset = float_positive(offset, 'louver offset')
        self._angle = float_in_range(angle, -90, 90, 'overhang angle')
        assert isinstance(contour_vector, Vector2D), 'Expected Vector2D for ' \
            'LouversByDistance contour_vector. Got {}.'.format(type(contour_vector))
        self._contour_vector = contour_vector
        self._flip_start_side = bool(flip_start_side)

    @property
    def depth(self):
        """Get a number for the depth to extrude the louvers."""
        return self._depth

    @property
    def offset(self):
        """Get a number for the distance to louvers from this Face."""
        return self._offset

    @property
    def angle(self):
        """Get a number for an angle to rotate the louvers in degrees."""
        return self._angle

    @property
    def contour_vector(self):
        """Get a Vector2D for the direction along which contours are generated."""
        return self._contour_vector

    @property
    def flip_start_side(self):
        """Get a boolean to note whether the side the louvers start from is flipped."""
        return self._flip_start_side

    @staticmethod
    def _default_dict_parameters(data):
        """Get defaulted parameters from a base dictionary."""
        offset = data['offset'] if 'offset' in data else 0
        angle = data['angle'] if 'angle' in data else 0
        contr = Vector2D.from_array(data['contour_vector']) if 'contour_vector' in data \
            else Vector2D(0, 1)
        flip = data['flip_start_side'] if 'flip_start_side' in data else False
        return offset, angle, contr, flip

    def __copy__(self):
        return _LouversBase(self.depth, self.offset, self.angle,
                            self.contour_vector, self.flip_start_side)

    def __key(self):
        """A tuple based on the object properties, useful for hashing."""
        return (self.depth, self.offset, self.angle,
                self.contour_vector, self.flip_start_side)

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        return isinstance(other, _LouversBase) and self.__key() == other.__key()

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return 'LouversBase:'


class LouversByDistance(_LouversBase):
    """Instructions for a series of louvered Shades at a given distance between.

    Args:
        distance: A number for the approximate distance between each louver.
        depth: A number for the depth to extrude the louvers.
        offset: A number for the distance to louvers from the wall.
            Default is 0 for no offset.
        angle: A number for the for an angle to rotate the louvers in degrees.
            Default is 0 for no rotation.
        contour_vector: A Vector2D for the direction along which contours
            are generated. This 2D vector will be interpreted into a 3D vector
            within the plane of the wall. (0, 1) will usually generate
            horizontal contours in 3D space, (1, 0) will generate vertical
            contours, and (1, 1) will generate diagonal contours. Default: (0, 1).
        flip_start_side: Boolean to note whether the side the louvers start from
            should be flipped. Default is False to have contours on top or right.
            Setting to True will start contours on the bottom or left.

    Properties:
        * distance
        * depth
        * offset
        * angle
        * contour_vector
        * flip_start_side
    """
    __slots__ = ('_distance',)

    def __init__(self, distance, depth, offset=0, angle=0,
                 contour_vector=Vector2D(0, 1), flip_start_side=False):
        """Initialize LouversByDistance."""
        self._distance = float_positive(distance, 'louver separation distance')
        _LouversBase.__init__(self, depth, offset, angle,
                              contour_vector, flip_start_side)

    @property
    def distance(self):
        """Get a number for the approximate distance between each louver."""
        return self._distance

    def add_shading_to_face(self, face, tolerance=0.01):
        """Add Shades to a Honeybee Face using these Shading Parameters.

        Args:
            face: A honeybee-core Face object.
            tolerance: An optional value to remove any louvers with a length less
                than the tolerance. Default: 0.01, suitable for objects in meters.
        """
        face.louvers_by_distance_between(
            self.distance, self.depth, self.offset, self.angle, self.contour_vector,
            self.flip_start_side, False, tolerance)

    def scale(self, factor):
        """Get a scaled version of these ShadingParameters.

        This method is called within the scale methods of the Room2D.

        Args:
            factor: A number representing how much the object should be scaled.
        """
        return LouversByDistance(
            self.distance * factor, self.depth * factor, self.offset * factor,
            self.angle, self.contour_vector, self.flip_start_side)

    @classmethod
    def from_dict(cls, data):
        """Create LouversByDistance from a dictionary.

        .. code-block:: python

            {
            "type": "LouversByDistance",
            "distance": 0.3,
            "depth": 0.1,
            "offset": 0.3,
            "angle": 0,
            "contour_vector": [0, 1],  # array of (x, y) values
            "flip_start_side": False
            }
        """
        assert data['type'] == 'LouversByDistance', \
            'Expected LouversByDistance dictionary. Got {}.'.format(data['type'])
        offset, angle, contr, flip = cls._default_dict_parameters(data)
        return cls(data['distance'], data['depth'], offset, angle, contr, flip)

    def to_dict(self):
        """Get LouversByDistance as a dictionary."""
        return {'type': 'LouversByDistance',
                'distance': self.distance,
                'depth': self.depth,
                'offset': self.offset,
                'angle': self.angle,
                'contour_vector': self.contour_vector.to_array(),
                'flip_start_side': self.flip_start_side}

    def __copy__(self):
        return LouversByDistance(self.distance, self.depth, self.offset, self.angle,
                                 self.contour_vector, self.flip_start_side)

    def __key(self):
        """A tuple based on the object properties, useful for hashing."""
        return (self.distance, self.depth, self.offset, self.angle,
                self.contour_vector, self.flip_start_side)

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        return isinstance(other, LouversByDistance) and self.__key() == other.__key()

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return 'LouversByDistance:\n distance: {}\n depth: {}\n offset: {}\n angle: {}' \
            '\n contour: {}\n flip: {}'.format(
                self.distance, self.depth, self.offset, self.angle,
                self.contour_vector, self.flip_start_side)


class LouversByCount(_LouversBase):
    """Instructions for a specific number of louvered Shades over a wall.

    Args:
        louver_count: A positive integer for the number of louvers to generate.
        depth: A number for the depth to extrude the louvers.
        offset: A number for the distance to louvers from  the wall.
            Default is 0 for no offset.
        angle: A number for the for an angle to rotate the louvers in degrees.
            Default is 0 for no rotation.
        contour_vector: A Vector2D for the direction along which contours
            are generated. This 2D vector will be interpreted into a 3D vector
            within the plane of the wall. (0, 1) will usually generate
            horizontal contours in 3D space, (1, 0) will generate vertical
            contours, and (1, 1) will generate diagonal contours. Default: (0, 1).
        flip_start_side: Boolean to note whether the side the louvers start from
            should be flipped. Default is False to have contours on top or right.
            Setting to True will start contours on the bottom or left.

    Properties:
        * louver_count
        * depth
        * offset
        * angle
        * contour_vector
        * flip_start_side
    """
    __slots__ = ('_louver_count',)

    def __init__(self, louver_count, depth, offset=0, angle=0,
                 contour_vector=Vector2D(0, 1), flip_start_side=False):
        """Initialize LouversByCount."""
        self._louver_count = int_positive(louver_count, 'louver count')
        _LouversBase.__init__(self, depth, offset, angle,
                              contour_vector, flip_start_side)

    @property
    def louver_count(self):
        """Get a integer for the number of louvers to generate."""
        return self._louver_count

    def add_shading_to_face(self, face, tolerance=0.01):
        """Add Shades to a Honeybee Face using these Shading Parameters.

        Args:
            face: A honeybee-core Face object.
            tolerance: An optional value to remove any louvers with a length less
                than the tolerance. Default: 0.01, suitable for objects in meters.
        """
        face.louvers_by_count(
            self.louver_count, self.depth, self.offset, self.angle, self.contour_vector,
            self.flip_start_side, False, tolerance)

    def scale(self, factor):
        """Get a scaled version of these ShadingParameters.

        This method is called within the scale methods of the Room2D.

        Args:
            factor: A number representing how much the object should be scaled.
        """
        return LouversByCount(
            self.louver_count, self.depth * factor, self.offset * factor,
            self.angle, self.contour_vector, self.flip_start_side)

    @classmethod
    def from_dict(cls, data):
        """Create LouversByCount from a dictionary.

        .. code-block:: python

            {
            "type": "LouversByCount",
            "louver_count": 10,
            "depth": 0.1,
            "offset": 0.3,
            "angle": 0,
            "contour_vector": [0,  1],  # array of (x, y) values
            "flip_start_side": False
            }
        """
        assert data['type'] == 'LouversByCount', \
            'Expected LouversByCount dictionary. Got {}.'.format(data['type'])
        offset, angle, contr, flip = cls._default_dict_parameters(data)
        return cls(data['louver_count'], data['depth'], offset, angle, contr, flip)

    def to_dict(self):
        """Get LouversByCount as a dictionary."""
        return {'type': 'LouversByCount',
                'louver_count': self.louver_count,
                'depth': self.depth,
                'offset': self.offset,
                'angle': self.angle,
                'contour_vector': self.contour_vector.to_array(),
                'flip_start_side': self.flip_start_side}

    def __copy__(self):
        return LouversByCount(self.louver_count, self.depth, self.offset, self.angle,
                              self.contour_vector, self.flip_start_side)

    def __key(self):
        """A tuple based on the object properties, useful for hashing."""
        return (self.louver_count, self.depth, self.offset, self.angle,
                self.contour_vector, self.flip_start_side)

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        return isinstance(other, LouversByCount) and self.__key() == other.__key()

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return 'LouversByCount:\n count: {}\n depth: {}\n offset: {}\n angle: {}' \
            '\n contour: {}\n flip: {}'.format(
                self.louver_count, self.depth, self.offset, self.angle,
                self.contour_vector, self.flip_start_side)
