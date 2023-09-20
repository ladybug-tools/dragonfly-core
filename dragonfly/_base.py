# coding: utf-8
"""Base class for all geometry objects."""
from __future__ import division

from honeybee.typing import valid_string

from ladybug_geometry.geometry2d.pointvector import Point2D


class _BaseGeometry(object):
    """A base class for all geometry objects.

    Args:
        identifier: Text string for a unique object ID. Must be < 100 characters and
            not contain any spaces or special characters.

    Properties:
        * identifier
        * display_name
        * full_id
        * user_data
    """
    __slots__ = ('_identifier', '_display_name', '_properties', '_user_data')

    def __init__(self, identifier):
        """Initialize base object."""
        self.identifier = identifier
        self._display_name = None
        self._properties = None
        self._user_data = None

    @property
    def identifier(self):
        """Get or set a text string for the unique object identifier.

        This identifier remains constant as the object is mutated, copied, and
        serialized to different formats (eg. dict, idf, rad). This property is also
        used to reference the object across a Model.
        """
        return self._identifier

    @identifier.setter
    def identifier(self, value):
        self._identifier = valid_string(value, 'dragonfly object identifier')

    @property
    def display_name(self):
        """Get or set a string for the object name without any character restrictions.

        If not set, this will be equal to the identifier.
        """
        if self._display_name is None:
            return self._identifier
        return self._display_name

    @display_name.setter
    def display_name(self, value):
        if value is not None:
            try:
                value = str(value)
            except UnicodeEncodeError:  # Python 2 machine lacking the character set
                self._display_name = value  # keep it as unicode
        self._display_name = value

    @property
    def full_id(self):
        """Get a string with both the object display_name and identifier.

        This is formatted as display_name[identifier].

        This is useful in error messages to give users an easy means of finding
        invalid objects within models. If there is no display_name assigned,
        only the identifier will be returned.
        """
        if self._display_name is None:
            return self._identifier
        else:
            return '{}[{}]'.format(self._display_name, self._identifier)

    @property
    def properties(self):
        """Object properties, including Radiance, Energy and other properties."""
        return self._properties

    @property
    def user_data(self):
        """Get or set an optional dictionary for additional meta data for this object.

        This will be None until it has been set. All keys and values of this
        dictionary should be of a standard Python type to ensure correct
        serialization of the object to/from JSON (eg. str, float, int, list dict)
        """
        return self._user_data

    @user_data.setter
    def user_data(self, value):
        if value is not None:
            assert isinstance(value, dict), 'Expected dictionary for honeybee ' \
                'object user_data. Got {}.'.format(type(value))
        self._user_data = value

    def duplicate(self):
        """Get a copy of this object."""
        return self.__copy__()

    @staticmethod
    def _validation_message_child(
            message, child_obj, detailed=False, code='000000', extension='Core',
            error_type='Unknown Error'):
        """Process a validation error message of a child object.

        Args:
            message: Text for the error message.
            child_obj: The child object instance for which the error message is for.
            detailed: Boolean for whether the returned object is a detailed list of
                dicts with error info or a string with a message. (Default: False).
            code: Text for the error code. (Default: 000000).
            extension: Text for the name of the Dragonfly extension for which duplicate
                identifiers are being evaluated. (Default: Core).
            error_type: Text for the type of error. This should be directly linked
                to the error code and should simply be a human-readable version of
                the error code. (Default: Unknown Error).

        Returns:
            A string with the message or a dictionary if detailed is True.
        """
        # first check whether an exception should be raised or the message returned
        if not detailed:
            return message
        # if not, then assemble a dictionary with detailed error information
        error_dict = {
            'type': 'ValidationError',
            'code': code,
            'error_type': error_type,
            'extension_type': extension,
            'element_type': child_obj.__class__.__name__
        }
        try:
            error_dict['element_id'] = [child_obj.identifier]
            error_dict['element_name'] = [child_obj.display_name]
        except AttributeError:  # it's a RoofSpecification or something with no id
            pass
        error_dict['message'] = message
        # add parents to the error dictionary
        parents = []
        rel_obj = child_obj
        while getattr(rel_obj, '_parent', None) is not None:
            rel_obj = getattr(rel_obj, '_parent')
            par_dict = {
                'parent_type': rel_obj.__class__.__name__,
                'id': rel_obj.identifier,
                'name': rel_obj.display_name
            }
            parents.append(par_dict)
        error_dict['parents'] = [parents]
        return error_dict

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
        new_obj = self.__class__(self.identifier)
        new_obj._display_name = self._display_name
        new_obj._user_data = None if self.user_data is None else self.user_data.copy()
        return new_obj

    def ToString(self):
        """Overwrite .NET ToString."""
        return self.__repr__()

    def __repr__(self):
        return 'Dragonfly Base Object: %s' % self.display_name
