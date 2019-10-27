# coding: utf-8
"""Extension properties for Building, Story, Room2D.

These objects hold all attributes assigned by extensions like dragonfly-radiance
and dragonfly-energy.  Note that these Property objects are not intended to exist
on their own but should have a host object.
"""
from honeybee.properties import RoomProperties


class _Properties(object):
    """Base class for all Properties classes."""
    _do_not_duplicate = ('host', 'to_dict', 'to_honeybee', 'ToString')

    def __init__(self, host):
        """Initialize properties.

        Args:
            host: A dragonfly-core geometry object that hosts these properties
                (ie. Building, Story, Room2D).
        """
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
                properties dictionary will just be the name of the program_type. If
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


class BuildingProperties(_Properties):
    """Dragonfly Building properties. This class will be extended by extensions.

    Usage:
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

    def __repr__(self):
        """Properties representation."""
        return 'BuildingProperties'


class StoryProperties(_Properties):
    """Dragonfly Story properties. This class will be extended by extensions.

    Usage:
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

    def __repr__(self):
        """Properties representation."""
        return 'StoryProperties'


class Room2DProperties(_Properties):
    """Dragonfly Room2D properties. This class will be extended by extensions.

    Usage:
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
        hb_prop = RoomProperties(host)
        return self._add_extension_attr_to_honeybee(host, hb_prop)

    def __repr__(self):
        """Properties representation."""
        return 'Room2DProperties'
