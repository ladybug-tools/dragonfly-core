# coding: utf-8
"""Extension properties for Building, Story, Room2D.

These objects hold all attributes assigned by extensions like dragonfly-radiance
and dragonfly-energy.  Note that these Property objects are not intended to exist
on their own but should have a host object.
"""
from __future__ import division

import honeybee.properties as hb_properties


class _Properties(object):
    """Base class for all Properties classes.

    Args:
        host: A dragonfly-core geometry object that hosts these properties
            (ie. Building, Story, Room2D).

    Properties:
        * host

    """
    _do_not_duplicate = ('host', 'to_dict', 'to_honeybee', 'ToString')

    def __init__(self, host):
        """Initialize properties."""
        self._host = host

    @property
    def host(self):
        """Get the object hosting these properties."""
        return self._host

    def _duplicate_extension_attr(self, original_properties):
        """Duplicate the attributes added by extensions.

        This method should be called within the duplicate or __copy__ methods of
        each dragonfly-core geometry object after the core object has been duplicated.
        This method only needs to be called on the new (duplicated) core object and
        the extension properties of the original core object should be passed to
        this method as the original_properties.

        Args:
            original_properties: The properties object of the original core
                object from which the duplicate was derived.
        """
        attr = [atr for atr in dir(self)
                if not atr.startswith('_') and atr not in self._do_not_duplicate]

        for atr in attr:
            var = getattr(original_properties, atr)
            if not hasattr(var, 'duplicate'):
                continue
            try:
                setattr(self, '_' + atr, var.duplicate(self.host))
            except Exception as e:
                import traceback
                traceback.print_exc()
                raise Exception('Failed to duplicate {}: {}'.format(var, e))

    def _add_prefix_extension_attr(self, prefix):
        """Change the identifier of attributes unique to this object by adding a prefix.

        This is particularly useful in workflows where you duplicate and edit
        a starting object and then want to combine it with the original object
        into one Model (like making a model of repeated buildings).

        Notably, this method only adds the prefix to extension attributes that must
        be unique to the object and does not add the prefix to attributes that are
        shared across several objects.

        Args:
            prefix: Text that will be inserted at the start of the extension attributes'
                identifier. It is recommended that this prefix be short to avoid maxing
                out the 100 allowable characters for honeybee identifiers.
        """
        attr = [atr for atr in dir(self)
                if not atr.startswith('_') and atr not in self._do_not_duplicate]

        for atr in attr:
            var = getattr(self, atr)
            if not hasattr(var, 'add_prefix'):
                continue
            try:
                var.add_prefix(prefix)
            except Exception as e:
                import traceback
                traceback.print_exc()
                raise Exception('Failed to add prefix to {}: {}'.format(var, e))

    def _add_extension_attr_to_honeybee(self, host, honeybee_properties):
        """Add Dragonfly properties for extensions to Honeybee extension properties.

        This method should be called within the to_honeybee method for any
        dragonfly-core geometry object that maps directly to a honeybee-core object.

        Args:
            host: A honeybee-core object that hosts these properties.
            honeybee_properties: A honeybee-core Properties object to which the
                dragonfly-core extension attributes will be added.
        """
        attr = [atr for atr in dir(self)
                if not atr.startswith('_') and atr not in self._do_not_duplicate]

        for atr in attr:
            var = getattr(self, atr)
            if not hasattr(var, 'to_honeybee'):
                continue
            try:
                setattr(honeybee_properties, '_' + atr, var.to_honeybee(host))
            except Exception as e:
                import traceback
                traceback.print_exc()
                raise Exception('Failed to translate {} to_honeybee: {}'.format(var, e))
        return honeybee_properties

    def _add_extension_attr_to_dict(self, base, abridged, include):
        """Add attributes for extensions to the base dictionary.

        This method should be called within the to_dict method of each dragonfly-core
        geometry object.

        Args:
            base: The dictionary of the core object without any extension attributes.
                This method will add extension attributes to this dictionary. For
                example, energy properties will appear under base['properties']['energy'].
            abridged: Boolean to note whether the attributes of the extensions should
                be abridged (True) or full (False). For example, if a Room's energy
                properties are abridged, the program_type attribute under the energy
                properties dictionary will just be the identifier of the program_type. If
                it is full (not abridged), the program_type will be a complete
                dictionary following the ProgramType schema. Abridged dictionaries
                should be used within the Model.to_dict but full dictionaries should
                be used within the to_dict methods of individual objects.
            include: List of properties to filter keys that must be included in
                output dictionary. For example ['energy'] will include 'energy' key if
                available in properties to_dict. By default all the keys will be
                included. To exclude all the keys from extensions use an empty list.
        """
        if include is not None:
            attr = include
        else:
            attr = [atr for atr in dir(self)
                    if not atr.startswith('_') and atr not in self._do_not_duplicate]

        for atr in attr:
            var = getattr(self, atr)
            if not hasattr(var, 'to_dict'):
                continue
            try:
                base.update(var.to_dict(abridged))
            except Exception as e:
                import traceback
                traceback.print_exc()
                raise Exception('Failed to convert {} to a dict: {}'.format(var, e))
        return base

    def _load_extension_attr_from_dict(self, property_dict):
        """Get attributes for extensions from a dictionary of the properties.

        This method should be called within the from_dict method of each dragonfly-core
        geometry object. Specifically, this method should be called on the core
        object after it has been created from a dictionary but lacks any of the
        extension attributes in the dictionary.

        Args:
            property_dict: A dictionary of properties for the object (ie.
                StoryProperties, BuildingProperties). These will be used to load
                attributes from the dictionary and assign them to the object on which
                this method is called.
        """
        attr = [atr for atr in dir(self)
                if not atr.startswith('_') and atr not in self._do_not_duplicate]

        for atr in attr:
            var = getattr(self, atr)
            if not hasattr(var, 'from_dict'):
                continue
            try:
                setattr(self, '_' + atr, var.__class__.from_dict(
                    property_dict[atr], self.host))
            except KeyError:
                pass  # the property_dict possesses no properties for that extension

    def ToString(self):
        """Overwrite .NET ToString method."""
        return self.__repr__()

    def __repr__(self):
        """Properties representation."""
        return 'BaseProperties'


class ModelProperties(_Properties):
    """Dragonfly Model Properties. This class will be extended by extensions.

    Usage:

    .. code-block:: python

        model = Model('South Boston District', list_of_buildings)
        model.properties -> ModelProperties
        model.properties.radiance -> ModelRadianceProperties
        model.properties.energy -> ModelEnergyProperties
    """

    def to_dict(self, include=None):
        """Convert properties to dictionary.

        Args:
            include: A list of keys to be included in dictionary.
                If None all the available keys will be included.
        """
        base = {
            'type': 'ModelProperties'
        }
        if include is not None:
            attr = include
        else:
            attr = [atr for atr in dir(self)
                    if not atr.startswith('_') and atr != 'host']

        for atr in attr:
            var = getattr(self, atr)
            if not hasattr(var, 'to_dict'):
                continue
            try:
                base.update(var.to_dict())  # no abridged dictionary for model
            except Exception as e:
                import traceback
                traceback.print_exc()
                raise Exception('Failed to convert {} to a dict: {}'.format(var, e))
        return base

    def apply_properties_from_dict(self, data):
        """Apply extension properties from a Model dictionary to the host Model.

        Args:
            data: A dictionary representation of an entire dragonfly-core Model.
        """
        attr = [atr for atr in dir(self)
                if not atr.startswith('_') and atr not in self._do_not_duplicate]

        for atr in attr:
            if atr not in data['properties'] or data['properties'][atr] is None:
                continue
            var = getattr(self, atr)
            if not hasattr(var, 'apply_properties_from_dict'):
                continue
            try:
                var.apply_properties_from_dict(data)
            except Exception as e:
                import traceback
                traceback.print_exc()
                raise Exception(
                    'Failed to apply {} properties to the Model: {}'.format(atr, e))

    def to_honeybee(self, host):
        """Convert this Model's extension properties to honeybee Model properties.

        Args:
            host: A honeybee-core Model object that hosts these properties.
        """
        hb_prop = hb_properties.ModelProperties(host)
        return self._add_extension_attr_to_honeybee(host, hb_prop)

    def __repr__(self):
        """Properties representation."""
        return 'ModelProperties'


class ContextShadeProperties(_Properties):
    """Dragonfly ContextShade properties. This class will be extended by extensions.

    Usage:

    .. code-block:: python

        canopy = ContextShade('Outdoor Canopy', canopy_geo)
        canopy.properties -> ContextShadeProperties
        canopy.properties.radiance -> ContextShadeRadianceProperties
        canopy.properties.energy -> ContextShadeEnergyProperties
    """

    def to_dict(self, abridged=False, include=None):
        """Convert properties to dictionary.

        Args:
            abridged: Boolean to note whether the full dictionary describing the
                object should be returned (False) or just an abridged version (True).
                Default: False.
            include: A list of keys to be included in dictionary.
                If None all the available keys will be included.
        """
        base = {'type': 'ContextShadeProperties'} if not abridged else \
            {'type': 'ContextShadePropertiesAbridged'}

        base = self._add_extension_attr_to_dict(base, abridged, include)
        return base

    def to_honeybee(self, host):
        """Convert this ContextShade's extension properties to honeybee Shade properties.

        Args:
            host: A honeybee-core Shade object that hosts these properties.
        """
        hb_prop = hb_properties.ShadeProperties(host)
        return self._add_extension_attr_to_honeybee(host, hb_prop)

    def add_prefix(self, prefix):
        """Change the identifier of attributes unique to this object by adding a prefix.

        Notably, this method only adds the prefix to extension attributes that must
        be unique to the ContextShade and does not add the prefix to attributes that are
        shared across several ContextShades.

        Args:
            prefix: Text that will be inserted at the start of extension
                attribute identifiers.
        """
        self._add_prefix_extension_attr(prefix)

    def __repr__(self):
        """Properties representation."""
        return 'ContextShadeProperties'


class BuildingProperties(_Properties):
    """Dragonfly Building properties. This class will be extended by extensions.

    Usage:

    .. code-block:: python

        building = Building('Office Tower', unique_stories)
        building.properties -> BuildingProperties
        building.properties.radiance -> BuildingRadianceProperties
        building.properties.energy -> BuildingEnergyProperties
    """

    def to_dict(self, abridged=False, include=None):
        """Convert properties to dictionary.

        Args:
            abridged: Boolean to note whether the full dictionary describing the
                object should be returned (False) or just an abridged version (True).
                Default: False.
            include: A list of keys to be included in dictionary.
                If None all the available keys will be included.
        """
        base = {'type': 'BuildingProperties'} if not abridged else \
            {'type': 'BuildingPropertiesAbridged'}

        base = self._add_extension_attr_to_dict(base, abridged, include)
        return base

    def add_prefix(self, prefix):
        """Change the identifier of attributes unique to this object by adding a prefix.

        Notably, this method only adds the prefix to extension attributes that must
        be unique to the Building and does not add the prefix to attributes that are
        shared across several Buildings.

        Args:
            prefix: Text that will be inserted at the start of extension
                attribute identifiers.
        """
        self._add_prefix_extension_attr(prefix)

    def __repr__(self):
        """Properties representation."""
        return 'BuildingProperties'


class StoryProperties(_Properties):
    """Dragonfly Story properties. This class will be extended by extensions.

    Usage:

    .. code-block:: python

        story = Story('Ground Floor Retail', room_2ds)
        story.properties -> StoryProperties
        story.properties.radiance -> StoryRadianceProperties
        story.properties.energy -> StoryEnergyProperties
    """

    def to_dict(self, abridged=False, include=None):
        """Convert properties to dictionary.

        Args:
            abridged: Boolean to note whether the full dictionary describing the
                object should be returned (False) or just an abridged version (True).
                Default: False.
            include: A list of keys to be included in dictionary.
                If None all the available keys will be included.
        """
        base = {'type': 'StoryProperties'} if not abridged else \
            {'type': 'StoryPropertiesAbridged'}

        base = self._add_extension_attr_to_dict(base, abridged, include)
        return base

    def add_prefix(self, prefix):
        """Change the identifier of attributes unique to this object by adding a prefix.

        Notably, this method only adds the prefix to extension attributes that must
        be unique to the Story and does not add the prefix to attributes that are
        shared across several Stories.

        Args:
            prefix: Text that will be inserted at the start of extension
                attribute identifiers.
        """
        self._add_prefix_extension_attr(prefix)

    def __repr__(self):
        """Properties representation."""
        return 'StoryProperties'


class Room2DProperties(_Properties):
    """Dragonfly Room2D properties. This class will be extended by extensions.

    Usage:

    .. code-block:: python

        room = Room2D('Office', geometry)
        room.properties -> Room2DProperties
        room.properties.radiance -> Room2DRadianceProperties
        room.properties.energy -> Room2DEnergyProperties
    """

    def to_dict(self, abridged=False, include=None):
        """Convert properties to dictionary.

        Args:
            abridged: Boolean to note whether the full dictionary describing the
                object should be returned (False) or just an abridged version (True).
                Default: False.
            include: A list of keys to be included in dictionary.
                If None all the available keys will be included.
        """
        base = {'type': 'Room2DProperties'} if not abridged else \
            {'type': 'Room2DPropertiesAbridged'}

        base = self._add_extension_attr_to_dict(base, abridged, include)
        return base

    def to_honeybee(self, host):
        """Convert this Room2D's extension properties to honeybee Room properties.

        Args:
            host: A honeybee-core Room object that hosts these properties.
        """
        hb_prop = hb_properties.RoomProperties(host)
        return self._add_extension_attr_to_honeybee(host, hb_prop)

    def add_prefix(self, prefix):
        """Change the identifier of attributes unique to this object by adding a prefix.

        Notably, this method only adds the prefix to extension attributes that must
        be unique to the Room2D (eg. single-room HVAC systems) and does not add
        the prefix to attributes that are shared across several Rooms2Ds (eg.
        ConstructionSets).

        Args:
            prefix: Text that will be inserted at the start of extension
                attribute identifiers.
        """
        self._add_prefix_extension_attr(prefix)

    def __repr__(self):
        """Properties representation."""
        return 'Room2DProperties'
