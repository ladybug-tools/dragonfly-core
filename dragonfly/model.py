# coding: utf-8
"""Dragonfly Model."""
from ._base import _BaseGeometry
from .properties import ModelProperties
from .building import Building
from .context import ContextShade

from honeybee.model import Model as hb_model
from honeybee.shade import Shade
from honeybee.boundarycondition import Surface
from honeybee.typing import float_in_range, float_positive

from ladybug_geometry.geometry2d.pointvector import Vector2D

import math


class Model(_BaseGeometry):
    """A collection of Buildings and ContextShades for an entire model.

    Args:
        name: Model name. Must be < 100 characters.
        buildings: A list of Building objects in the model.
        context_shades: A list of ContextShade objects in the model.
        north_angle: An number between 0 and 360 to set the clockwise north
            direction in degrees. Default is 0.
        units: Text for the units system in which the model geometry
            exists. Default: 'Meters'. Choose from the following:

            * Meters
            * Millimeters
            * Feet
            * Inches
            * Centimeters

        tolerance: The maximum difference between x, y, and z values at which
            vertices are considered equivalent. Zero indicates that no tolerance
            checks should be performed and certain capabilities like to_honeybee
            will not be available. Default: 0.
        angle_tolerance: The max angle difference in degrees that vertices are
            allowed to differ from one another in order to consider them colinear.
            Zero indicates that no angle tolerance checks should be performed.
            Default: 0.

    Properties:
        * name
        * display_name
        * north_angle
        * north_vector
        * units
        * tolerance
        * angle_tolerance
        * buildings
        * context_shades
        * stories
        * room_2ds
        * min
        * max
    """
    __slots__ = ('_buildings', '_context_shades', '_north_angle', '_north_vector',
                 '_units', '_tolerance', '_angle_tolerance')

    UNITS = hb_model.UNITS

    def __init__(self, name, buildings=None, context_shades=None, north_angle=0,
                 units='Meters', tolerance=0, angle_tolerance=0):
        """A collection of Buildings and ContextShades for an entire model."""
        self.name = name
        self.north_angle = north_angle
        self.units = units
        self.tolerance = tolerance
        self.angle_tolerance = angle_tolerance

        self._buildings = []
        self._context_shades = []
        if buildings is not None:
            for bldg in buildings:
                self.add_building(bldg)
        if context_shades is not None:
            for shade in context_shades:
                self.add_context_shade(shade)

        self._properties = ModelProperties(self)

    @classmethod
    def from_dict(cls, data):
        """Initialize a Model from a dictionary.

        Args:
            data: A dictionary representation of a Model object.
        """
        # check the type of dictionary
        assert data['type'] == 'Model', 'Expected Model dictionary. ' \
            'Got {}.'.format(data['type'])

        # import the tolerance values
        tol = 0 if 'tolerance' not in data else data['tolerance']
        angle_tol = 0 if 'angle_tolerance' not in data else data['angle_tolerance']

        buildings = None  # import buildings
        if 'buildings' in data and data['buildings'] is not None:
            buildings = [Building.from_dict(bldg, tol) for bldg in data['buildings']]
        context_shades = None  # import context shades
        if 'context_shades' in data and data['context_shades'] is not None:
            context_shades = [ContextShade.from_dict(s) for s in data['context_shades']]

        # import the north angle and units
        north_angle = 0 if 'north_angle' not in data else data['north_angle']
        units = 'Meters' if 'units' not in data else data['units']

        # build the model object
        model = Model(data['name'], buildings, context_shades, north_angle,
                      units, tol, angle_tol)
        assert model.display_name == model.name, \
            'Model name "{}" has invalid characters.'.format(data['name'])
        if 'display_name' in data and data['display_name'] is not None:
            model._display_name = data['display_name']

        # assign extension properties to the model
        model.properties.apply_properties_from_dict(data)
        return model

    @property
    def north_angle(self):
        """Get or set a number between 0 and 360 for the north direction in degrees."""
        return self._north_angle

    @north_angle.setter
    def north_angle(self, value):
        self._north_angle = float_in_range(value, 0.0, 360.0, 'model north angle')
        self._north_vector = Vector2D(0, 1).rotate(math.radians(-self._north_angle))

    @property
    def north_vector(self):
        """Get or set a ladybug_geometry Vector2D for the north direction."""
        return self._north_vector

    @north_vector.setter
    def north_vector(self, value):
        assert isinstance(value, Vector2D), \
            'Expected Vector2D for north_vector. Got {}.'.format(type(value))
        self._north_vector = value
        self._north_angle = \
            math.degrees(Vector2D(0, 1).angle_clockwise(self._north_vector))

    @property
    def units(self):
        """Get or set Text for the units system in which the model geometry exists."""
        return self._units

    @units.setter
    def units(self, value):
        assert value in self.UNITS, '{} is not supported as a units system. ' \
            'Choose from the following: {}'.format(value, self.units)
        self._units = value

    @property
    def tolerance(self):
        """Get or set a number for the max meaningful difference between x, y, z values.

        This value should be in the Model's units. Zero indicates cases where
        no tolerance checks should be performed.
        """
        return self._tolerance

    @tolerance.setter
    def tolerance(self, value):
        self._tolerance = float_positive(value, 'model tolerance')

    @property
    def angle_tolerance(self):
        """Get or set a number for the max meaningful angle difference in degrees.

        Face3D normal vectors differing by this amount are not considered parallel
        and Face3D segments that differ from 180 by this amount are not considered
        colinear. Zero indicates cases where no angle_tolerance checks should be
        performed.
        """
        return self._angle_tolerance

    @angle_tolerance.setter
    def angle_tolerance(self, value):
        self._angle_tolerance = float_positive(value, 'model angle_tolerance')

    @property
    def buildings(self):
        """Get a tuple of all Building objects in the model."""
        return tuple(self._buildings)

    @property
    def context_shades(self):
        """Get a tuple of all ContextShade objects in the model."""
        return tuple(self._context_shades)

    @property
    def stories(self):
        """Get a tuple of all unique Story objects in the model."""
        return tuple(story for building in self._buildings
                     for story in building._unique_stories)

    @property
    def room_2ds(self):
        """Get a tuple of all unique Room2D objects in the model."""
        return tuple(room2d for building in self._buildings
                     for story in building._unique_stories
                     for room2d in story._room_2ds)

    @property
    def min(self):
        """Get a Point2D for the min bounding rectangle vertex in the XY plane.

        This is useful in calculations to determine if this Model is in proximity
        to other objects.
        """
        return self._calculate_min(self._buildings + self._context_shades)

    @property
    def max(self):
        """Get a Point2D for the max bounding rectangle vertex in the XY plane.

        This is useful in calculations to determine if this Model is in proximity
        to other objects.
        """
        return self._calculate_max(self._buildings + self._context_shades)

    def add_model(self, other_model):
        """Add another Dragonfly Model object to this one."""
        assert isinstance(other_model, Model), \
            'Expected Dragonfly Model. Got {}.'.format(type(other_model))
        self._buildings =  self._buildings + other_model._buildings
        self._context_shades = self._context_shades + other_model._context_shades

    def add_building(self, obj):
        """Add a Building object to the model."""
        assert isinstance(obj, Building), 'Expected Building. Got {}.'.format(type(obj))
        self._buildings.append(obj)

    def add_context_shade(self, obj):
        """Add a ContextShade object to the model."""
        assert isinstance(obj, ContextShade), \
                'Expected ContextShade. Got {}.'.format(type(obj))
        self._context_shades.append(obj)

    def buildings_by_name(self, names):
        """Get a list of Building objects in the model given Building names."""
        buildings = []
        for name in names:
            for bldg in self._buildings:
                if bldg.name == name:
                    buildings.append(bldg)
                    break
            else:
                raise ValueError(
                    'Building "{}" was not found in the model.'.format(name))
        return buildings

    def context_shade_by_name(self, names):
        """Get a list of ContextShade objects in the model given ContextShade names.
        """
        context_shades = []
        for name in names:
            for shd in self._context_shades:
                if shd.name == name:
                    context_shades.append(shd)
                    break
            else:
                raise ValueError(
                    'ContextShade "{}" was not found in the model.'.format(name))
        return context_shades

    def move(self, moving_vec):
        """Move this Model along a vector.

        Args:
            moving_vec: A ladybug_geometry Vector3D with the direction and distance
                to move the model.
        """
        for bldg in self._buildings:
            bldg.move(moving_vec)
        for shade in self._context_shades:
            shade.move(moving_vec)

    def rotate_xy(self, angle, origin):
        """Rotate this Model counterclockwise in the world XY plane by a certain angle.

        Args:
            angle: An angle in degrees.
            origin: A ladybug_geometry Point3D for the origin around which the
                object will be rotated.
        """
        for bldg in self._buildings:
            bldg.rotate_xy(angle, origin)
        for shade in self._context_shades:
            shade.rotate_xy(angle, origin)

    def reflect(self, plane):
        """Reflect this Model across a plane with the input normal vector and origin.

        Args:
            plane: A ladybug_geometry Plane across which the object will
                be reflected.
        """
        for bldg in self._buildings:
            bldg.reflect(plane)
        for shade in self._context_shades:
            shade.reflect(plane)

    def scale(self, factor, origin=None):
        """Scale this Model by a factor from an origin point.

        Args:
            factor: A number representing how much the object should be scaled.
            origin: A ladybug_geometry Point3D representing the origin from which
                to scale. If None, it will be scaled from the World origin (0, 0, 0).
        """
        for bldg in self._buildings:
            bldg.scale(factor, origin)
        for shade in self._context_shades:
            shade.scale(factor, origin)

    def convert_to_units(self, units='Meters'):
        """Convert all of the geometry in this model to certain units.

        Thins involves both scaling the geometry and changing the Model's
        units property.

        Args:
            units: Text for the units to which the Model geometry should be
                converted. Default: Meters. Choose from the following:

                * Meters
                * Millimeters
                * Feet
                * Inches
                * Centimeters
        """
        if self.units != units:
            scale_fac1 = hb_model.conversion_factor_to_meters(self.units)
            scale_fac2 = hb_model.conversion_factor_to_meters(units)
            scale_fac = scale_fac1 / scale_fac2
            self.scale(scale_fac)
            self.units = units

    def check_duplicate_building_names(self, raise_exception=True):
        """Check that there are no duplicate Building names in the model."""
        bldg_names = set()
        duplicate_names = set()
        for bldg in self._buildings:
            if bldg.name not in bldg_names:
                bldg_names.add(bldg.name)
            else:
                duplicate_names.add(bldg.name)
        if len(duplicate_names) != 0:
            if raise_exception:
                raise ValueError('The model has the following duplicated '
                                 'Building names:\n{}'.format('\n'.join(duplicate_names)))
            return False
        return True

    def check_duplicate_context_shade_names(self, raise_exception=True):
        """Check that there are no duplicate ContextShade names in the model."""
        shade_names = set()
        duplicate_names = set()
        for shade in self._context_shades:
            if shade.name not in shade_names:
                shade_names.add(shade.name)
            else:
                duplicate_names.add(shade.name)
        if len(duplicate_names) != 0:
            if raise_exception:
                raise ValueError('The model has the following duplicated ConstextShade'
                                 ' names:\n{}'.format('\n'.join(duplicate_names)))
            return False
        return True

    def check_missing_adjacencies(self, raise_exception=True):
        """Check that all Room2Ds have adjacent objects that exist within each Story."""
        bldg_names = []
        for bldg in self._buildings:
            for story in bldg._unique_stories:
                if not story.check_missing_adjacencies(False):
                    bldg_names.append(bldg.name)
        if bldg_names != []:
            if raise_exception:
                raise ValueError('The following buildings have missing adjacencies in '
                                 'the Model:\n{}'.format('\n'.join(bldg_names)))
            return False
        return True

    def to_honeybee(self, object_per_model='Building', shade_distance=None,
                    use_multiplier=True, tolerance=None):
        """Convert Dragonfly Mdel to an array of Honeybee Models.

        Args:
            object_per_model: Text to describe how the input Buildings should be
                divided across the output Models. Default: 'Building'. Choose from
                the following options:

                * District - All buildings will be added to a single Honeybee Model.
                  Such a Model can take a long time to simulate so this is only
                  recommended for small numbers of buildings or cases where
                  exchange of data between Buildings is necessary.
                * Building - Each input building will be exported into its own Model.
                  For each Model, the other buildings input to this component will
                  appear as context shade geometry. Thus, each Model is its own
                  simulate-able unit.

            shade_distance: An optional number to note the distance beyond which other
                objects' shade should not be exported into a given Model. This is
                helpful for reducing the simulation run time of each Model when other
                connected buildings are too far away to have a meaningful impact on
                the results. If None, all other buildings will be included as context
                shade in each and every Model. Set to 0 to exclude all neighboring
                buildings from the resulting models. Default: None.
            use_multiplier: If True, the multipliers on this Building's Stories will be
                passed along to the generated Honeybee Room objects, indicating the
                simulation will be run once for each unique room and then results
                will be multiplied. If False, full geometry objects will be written
                for each and every floor in the building that are represented through
                multipliers and all resulting multipliers will be 1. Default: True
            tolerance: The minimum distance in z values of floor_height and
                floor_to_ceiling_height at which adjacent Faces will be split.
                This is also used in the generation of Windows. This must be a
                positive, non-zero number. If None, the Model's own tolerance
                will be used. Default: None.

        Returns:
            An array of Honeybee Models that together represent this Dragonfly Model.
        """
        # check the tolerance, which is required to convert to honeybee
        tolerance = self.tolerance if tolerance is None else tolerance
        assert tolerance != 0, \
            'Model tolerance must be non-zero to use Model.to_honeybee.'

        # create the model objects
        if object_per_model is None or object_per_model.title() == 'Building':
            models = Building.buildings_to_honeybee_self_shade(
                self._buildings, self._context_shades, shade_distance, use_multiplier,
                tolerance)
        elif object_per_model.title() == 'District':
            models = [Building.buildings_to_honeybee(
                self._buildings, use_multiplier, tolerance)]
            for shd_group in self._context_shades:
                for shd in shd_group.to_honeybee():
                    for model in models:
                        model.add_shade(shd)
        else:
            raise ValueError('Unrecognized object_per_model input: '
                            '{}'.format(object_per_model))

        # change the north if the one on this model is not the default
        if self._north_angle != 0 and self._north_angle != 360:
            for model in models:
                model.north_angle = self._north_angle

        # change the tolerance and untis systems to match the dragonfly model
        for model in models:
            model.units = self.units
            model.tolerance = tolerance
            model.angle_tolerance = self.angle_tolerance

        # transfer Model extension attributes to the honeybee models
        for hb_model in models:
            hb_model._properties = self.properties.to_honeybee(hb_model)

        return models

    def to_dict(self, included_prop=None):
        """Return Model as a dictionary.

        Args:
            included_prop: List of properties to filter keys that must be included in
                output dictionary. For example ['energy'] will include 'energy' key if
                available in properties to_dict. By default all the keys will be
                included. To exclude all the keys from extensions use an empty list.
        """
        base = {'type': 'Model'}
        base['name'] = self.name
        base['display_name'] = self.display_name
        base['properties'] = self.properties.to_dict(included_prop)
        if self._buildings != []:
            base['buildings'] = \
                [bldg.to_dict(True, included_prop) for bldg in self._buildings]
        if self._context_shades != []:
            base['context_shades'] = \
                [shd.to_dict(True, included_prop) for shd in self._context_shades]
        if self.north_angle != 0:
            base['north_angle'] = self.north_angle

        return base

    def __add__(self, other):
        new_model = self.duplicate()
        new_model.add_model(other)
        return new_model

    def __iadd__(self, other):
        self.add_model(other)
        return self

    def __copy__(self):
        new_model = Model(
            self.name,
            [bldg.duplicate() for bldg in self._buildings],
            [shade.duplicate() for shade in self._context_shades],
            self.north_angle)
        new_model._display_name = self.display_name
        new_model._properties._duplicate_extension_attr(self._properties)
        return new_model

    def __repr__(self):
        return 'Dragonfly Model: %s' % self.display_name
