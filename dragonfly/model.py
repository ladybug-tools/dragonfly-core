# coding: utf-8
"""Dragonfly Model."""
from __future__ import division

import os
import io
import re
import json
import datetime
try:  # check if we are in IronPython
    import cPickle as pickle
except ImportError:  # wea re in cPython
    import pickle

from ladybug_geometry.geometry2d.pointvector import Point2D
from ladybug_geometry.geometry3d.face import Face3D
from ladybug_geometry.geometry3d.pointvector import Vector3D, Point3D
from ladybug_geometry.geometry3d.plane import Plane
from ladybug_geometry.geometry3d.polyface import Polyface3D
from ladybug.futil import preparedir
from ladybug.location import Location

from honeybee.typing import float_positive, invalid_dict_error, clean_and_number_string
from honeybee.checkdup import check_duplicate_identifiers
from honeybee.units import conversion_factor_to_meters, parse_distance_string, \
    UNITS, UNITS_TOLERANCES
from honeybee.config import folders
from honeybee.facetype import Floor, RoofCeiling
from honeybee.boundarycondition import Outdoors, Surface, Ground, boundary_conditions
from honeybee.shade import Shade as HBShade
from honeybee.room import Room as HBRoom
from honeybee.model import Model as HBModel

from ._base import _BaseGeometry
from .properties import ModelProperties
from .building import Building
from .context import ContextShade
from .windowparameter import SimpleWindowRatio
from .projection import meters_to_long_lat_factors, polygon_to_lon_lat, \
    origin_long_lat_from_location, lon_lat_to_polygon
from dragonfly.config import folders as df_folders
import dragonfly.writer.model as writer


class Model(_BaseGeometry):
    """A collection of Buildings and ContextShades for an entire model.

    Args:
        identifier: Text string for a unique Model ID. Must be < 100 characters
            and not contain any spaces or special characters.
        buildings: A list of Building objects in the model.
        context_shades: A list of ContextShade objects in the model.
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
            will not be available. None indicates that the tolerance will be
            set based on the units above, with the tolerance consistently being
            between 1 cm and 1 mm (roughly the tolerance implicit in the OpenStudio
            SDK). (Default: None).
        angle_tolerance: The max angle difference in degrees that vertices are allowed
            to differ from one another in order to consider them colinear. Zero indicates
            that no angle tolerance checks should be performed. (Default: 1.0).

    Properties:
        * identifier
        * display_name
        * full_id
        * units
        * tolerance
        * angle_tolerance
        * buildings
        * context_shades
        * stories
        * room_2ds
        * room_3ds
        * average_story_count
        * average_story_count_above_ground
        * average_height
        * average_height_above_ground
        * footprint_area
        * floor_area
        * exterior_wall_area
        * exterior_aperture_area
        * volume
        * min
        * max
        * user_data
    """
    __slots__ = ('_buildings', '_context_shades',
                 '_units', '_tolerance', '_angle_tolerance')

    def __init__(self, identifier, buildings=None, context_shades=None,
                 units='Meters', tolerance=None, angle_tolerance=1.0):
        """A collection of Buildings and ContextShades for an entire model."""
        _BaseGeometry.__init__(self, identifier)  # process the identifier
        self.units = units
        self.tolerance = tolerance
        self.angle_tolerance = angle_tolerance

        self._buildings = []
        self._context_shades = []
        if buildings is not None:
            for bldg in buildings:
                assert isinstance(bldg, Building), \
                    'Expected Building. Got {}.'.format(type(bldg))
                self._buildings.append(bldg)
        if context_shades is not None:
            for shade in context_shades:
                self.add_context_shade(shade)

        self._properties = ModelProperties(self)

    @classmethod
    def from_geojson(cls, geojson_file_path, location=None, point=Point2D(0, 0),
                     all_polygons_to_buildings=False, existing_to_context=False,
                     units='Meters', tolerance=None, angle_tolerance=1.0):
        """Make a Model from a geojson file.

        Args:
            geojson_file_path: Text for the full path to the geojson file to load as
                Model.
            location: An optional ladybug location object with longitude and
                latitude data defining the origin of the geojson file. If nothing
                is passed, the origin is autocalculated as the bottom-left corner
                of the bounding box of all building footprints in the geojson file
                (Default: None).
            point: A ladybug_geometry Point2D for where the location object exists
                within the space of a scene. The coordinates of this point are
                expected to be in the expected units of this Model (Default: (0, 0)).
            all_polygons_to_buildings: Boolean to indicate if all geometries in
                the geojson file should be considered buildings. If False, this
                method will only generate footprints from geometries that are
                defined as a "Building" in the type field of its corresponding
                properties. (Default: False).
            existing_to_context: Boolean to indicate whether polygons possessing
                a building_status of "Existing" under their properties should be
                imported as ContextShade instead of Building objects. (Default: False).
            units: Text for the units system in which the model geometry
                exists. Default: 'Meters'. Choose from the following:

                * Meters
                * Millimeters
                * Feet
                * Inches
                * Centimeters

                Note that this method assumes the point coordinates are in the
                same units.
            tolerance: The maximum difference between x, y, and z values at which
                vertices are considered equivalent. Zero indicates that no tolerance
                checks should be performed and certain capabilities like to_honeybee
                will not be available. None indicates that the tolerance will be
                set based on the units above, with the tolerance consistently being
                between 1 cm and 1 mm (roughly the tolerance implicit in the OpenStudio
                SDK). (Default: None).
            angle_tolerance: The max angle difference in degrees that vertices
                are allowed to differ from one another in order to consider them
                colinear. Zero indicates that no angle tolerance checks should
                be performed. (Default: 1.0).

        Returns:
            A tuple with the two items below.

            * model -- A dragonfly Model derived from the geoJSON.

            * location -- A ladybug Location object, which contains latitude and
                longitude information and can be used to re-serialize the model
                back to geoJSON.
        """
        # parse the geoJSON into a dictionary
        with open(geojson_file_path, 'r') as fp:
            data = json.load(fp)

        # Get the list of building data
        if all_polygons_to_buildings:
            p_types = ('Polygon', 'MultiPolygon')
            bldgs_data = \
                [bldg_data for bldg_data in data['features']
                 if 'geometry' in bldg_data and bldg_data['geometry']['type'] in p_types]
        else:
            bldgs_data = []
            for bldg_data in data['features']:
                if 'type' in bldg_data['properties']:
                    if bldg_data['properties']['type'] == 'Building':
                        bldgs_data.append(bldg_data)

        # Check if buildings exist
        assert len(bldgs_data) > 0, 'No building footprints were found in {}.\n' \
            'Try setting "all_polygons_to_buildings" to True.'.format(geojson_file_path)

        # if model units is not Meters, convert non-meter user inputs to meters
        scale_to_meters = conversion_factor_to_meters(units)
        if units != 'Meters':
            point = point.scale(scale_to_meters)

        # Get long and lat in the geojson that correspond to the model origin (point).
        # If location is None, derive coordinates from the geojson geometry.
        if location is None:
            point_lon_lat = None
            if 'project' in data:
                proj_data = data['project']
                if 'latitude' in proj_data and 'longitude' in proj_data:
                    point_lon_lat = (proj_data['latitude'], proj_data['longitude'])
            if point_lon_lat is None:
                point_lon_lat = cls._bottom_left_coordinate_from_geojson(bldgs_data)
            location = Location(longitude=point_lon_lat[0], latitude=point_lon_lat[1])

        # The model point may not be at (0, 0), so shift the longitude and latitude to
        # get the equivalent point in longitude and latitude for (0, 0) in the model.
        origin_lon_lat = origin_long_lat_from_location(location, point)
        _convert_facs = meters_to_long_lat_factors(origin_lon_lat)
        convert_facs = 1 / _convert_facs[0], 1 / _convert_facs[1]

        # Extract buildings
        bldgs, contexts = cls._objects_from_geojson(
            bldgs_data, existing_to_context, scale_to_meters, origin_lon_lat,
            convert_facs)

        # Make model, in meters and then convert to user-defined units
        m_id, m_name = 'Model_1', None
        if 'project' in data:
            m_id = data['project']['id'] if 'id' in data['project'] else m_id
            m_name = data['project']['name'] if 'name' in data['project'] else m_name
        model = cls(m_id, buildings=bldgs, context_shades=contexts, units='Meters',
                    tolerance=tolerance, angle_tolerance=angle_tolerance)
        if m_name:
            model.display_name = m_name
        if units != 'Meters':
            model.convert_to_units(units)

        return model, location

    @classmethod
    def from_dict(cls, data):
        """Initialize a Model from a dictionary.

        Args:
            data: A dictionary representation of a Model object.
        """
        # check the type of dictionary
        assert data['type'] == 'Model', 'Expected Model dictionary. ' \
            'Got {}.'.format(data['type'])

        # import the units and tolerance values
        units = 'Meters' if 'units' not in data or data['units'] is None \
            else data['units']
        tol = UNITS_TOLERANCES[units] if 'tolerance' not in data or \
            data['tolerance'] is None else data['tolerance']
        angle_tol = 1.0 if 'angle_tolerance' not in data or \
            data['angle_tolerance'] is None else data['angle_tolerance']

        # import all of the geometry
        buildings = None  # import buildings
        if 'buildings' in data and data['buildings'] is not None:
            buildings = []
            for bldg in data['buildings']:
                try:
                    buildings.append(
                        Building.from_dict(bldg, tol, angle_tol, sort_stories=False))
                except Exception as e:
                    invalid_dict_error(bldg, e)
        context_shades = None  # import context shades
        if 'context_shades' in data and data['context_shades'] is not None:
            context_shades = []
            for s in data['context_shades']:
                try:
                    context_shades.append(ContextShade.from_dict(s))
                except Exception as e:
                    invalid_dict_error(s, e)

        # build the model object
        model = Model(data['identifier'], buildings, context_shades,
                      units, tol, angle_tol)
        if 'display_name' in data and data['display_name'] is not None:
            model.display_name = data['display_name']
        if 'user_data' in data and data['user_data'] is not None:
            model.user_data = data['user_data']

        # assign extension properties to the model
        model.properties.apply_properties_from_dict(data)

        # sort stories now that properties were ordered correctly during assignment
        for building in model.buildings:
            building.sort_stories()
        return model

    @classmethod
    def from_honeybee(cls, model, conversion_method='AllRoom2D'):
        """Initialize a Dragonfly Model from a Honeybee Model.

        Args:
            model: A Honeybee Model to be converted to a Dragonfly Model.
            conversion_method: Text to indicate how the Honeybee Rooms should be
                converted to Dragonfly. Note that the AllRoom2D option may result
                in some loss or simplification of the 3D Honeybee geometry but
                ensures that all of Dragonfly's features for editing the rooms can
                be used. The ExtrudedOnly method will convert only the 3D Rooms
                that would have no loss or simplification of geometry when converted
                to Room2D. AllRoom3D keeps all detailed 3D geometry on the
                Building.room_3ds property, enabling you to convert the 3D Rooms
                to Room2D using the Building.convert_room_3ds_to_2d() method as you
                see fit. (Default: AllRoom2D). Choose from the following options.

                * AllRoom2D - All Honeybee Rooms converted to Dragonfly Room2D
                * ExtrudedOnly - Only pure extrusions converted to Dragonfly Room2D
                * AllRoom3D - All Honeybee Rooms left as-is on Building.room_3ds

        """
        # translate the rooms to a dragonfly building
        bldgs = None
        if len(model.rooms) != 0:
            bldgs = [Building.from_honeybee(model, conversion_method)]
        # translate the orphaned shades to context shades
        shades = []
        for shd_grp in model.grouped_shades:
            base_obj = shd_grp[0]
            shd_geo = [s.geometry for s in shd_grp]
            con_shade = ContextShade(base_obj.identifier, shd_geo, base_obj.is_detached)
            con_shade.display_name = base_obj.display_name
            con_shade._user_data = None if base_obj.user_data is None \
                else base_obj.user_data.copy()
            con_shade.properties.from_honeybee(base_obj.properties)
            shades.append(con_shade)
        new_model = cls(model.identifier, bldgs, shades, model.units,
                        model.tolerance, model.angle_tolerance)
        new_model._display_name = model._display_name
        return new_model

    @classmethod
    def from_file(cls, df_file):
        """Initialize a Model from a DFJSON or DFpkl file, auto-sensing the type.

        This will also sense if the input is a Honeybee Model and, if so,
        the loaded Dragonfly model will be derived from the Honeybee one.

        Args:
            df_file: Path to either a DFJSON or DFpkl file. This can also be a
                HBJSON or a HBpkl from which a Dragonfly model should be derived.
        """
        # sense the file type from the first character to avoid maxing memory with JSON
        # this is needed since queenbee overwrites all file extensions
        with io.open(df_file, encoding='utf-8') as inf:
            first_char = inf.read(1)
            second_char = inf.read(1)
        is_json = True if first_char == '{' or second_char == '{' else False
        # load the file using either DFJSON pathway or DFpkl
        if is_json:
            return cls.from_dfjson(df_file)
        return cls.from_dfpkl(df_file)

    @classmethod
    def from_dfjson(cls, dfjson_file):
        """Initialize a Model from a DFJSON file.

        Args:
            dfjson_file: Path to DFJSON file. This can also be a HBJSON from which
                a Dragonfly model should be derived.
        """
        assert os.path.isfile(dfjson_file), 'Failed to find %s' % dfjson_file
        with io.open(dfjson_file, encoding='utf-8') as inf:
            inf.read(1)
            second_char = inf.read(1)
        with io.open(dfjson_file, encoding='utf-8') as inf:
            if second_char == '{':
                inf.read(1)
            data = json.load(inf)
        if 'buildings' in data or 'context_shades' in data:
            return cls.from_dict(data)
        else:  # assume that it's a Honeybee Model to translate
            hb_model = HBModel.from_dict(data)
            return cls.from_honeybee(hb_model)

    @classmethod
    def from_dfpkl(cls, dfpkl_file):
        """Initialize a Model from a DFpkl file.

        Args:
            dfpkl_file: Path to DFpkl file. This can also be a HBpkl from which
                a Dragonfly model should be derived.
        """
        assert os.path.isfile(dfpkl_file), 'Failed to find %s' % dfpkl_file
        with open(dfpkl_file, 'rb') as inf:
            data = pickle.load(inf)
        if 'buildings' in data or 'context_shades' in data:
            return cls.from_dict(data)
        else:  # assume that it's a Honeybee Model to translate
            hb_model = HBModel.from_dict(data)
            return cls.from_honeybee(hb_model)

    @property
    def units(self):
        """Get or set Text for the units system in which the model geometry exists."""
        return self._units

    @units.setter
    def units(self, value):
        assert value in UNITS, '{} is not supported as a units system. ' \
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
        self._tolerance = float_positive(value, 'model tolerance') if value is not None \
            else UNITS_TOLERANCES[self.units]

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
    def room_3ds(self):
        """Get a tuple of all 3D Honeybee Room objects in the model."""
        return tuple(room3d for building in self._buildings
                     for room3d in building._room_3ds)

    @property
    def average_story_count(self):
        """Get the average number of stories for the buildings in the model.

        Note that this will be a float and not an integer in most cases.
        """
        return sum([bldg.story_count for bldg in self._buildings]) / len(self._buildings)

    @property
    def average_story_count_above_ground(self):
        """Get the average number of above-ground stories for the buildings in the model.

        Note that this will be a float and not an integer in most cases.
        """
        return sum([bldg.story_count_above_ground for bldg in self._buildings]) / \
            len(self._buildings)

    @property
    def average_height(self):
        """Get the average height of the Buildings as an absolute Z-coordinate."""
        return sum([bldg.height for bldg in self._buildings]) / len(self._buildings)

    @property
    def average_height_above_ground(self):
        """Get the average building height relative to the first floor above ground."""
        return sum([bldg.height_above_ground for bldg in self._buildings]) / \
            len(self._buildings)

    @property
    def footprint_area(self):
        """Get a number for the total footprint area of all Buildings in the Model."""
        return sum([bldg.footprint_area for bldg in self._buildings])

    @property
    def floor_area(self):
        """Get a number for the total floor area of all Buildings in the Model."""
        return sum([bldg.floor_area for bldg in self._buildings])

    @property
    def exterior_wall_area(self):
        """Get a number for the total exterior wall area for all Buildings in the Model.
        """
        return sum([bldg.exterior_wall_area for bldg in self._buildings])

    @property
    def exterior_aperture_area(self):
        """Get a number for the total exterior aperture area for all Buildings.
        """
        return sum([bldg.exterior_aperture_area for bldg in self._buildings])

    @property
    def volume(self):
        """Get a number for the volume of all the Buildings in the Model.
        """
        return sum([bldg.volume for bldg in self._buildings])

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
        """Add another Dragonfly Model object to this one.

        In the case that Building or Story identifiers in the other_model match
        one the current model, these objects will be merged together. Room2Ds
        that have matching identifiers within a merged Story will not be added
        in order to avoid ID conflicts. Context Shades will also not be added if their
        identifier matches one that is already in the Model.
        """
        # check that the object to merge is a Model and its units are correct
        assert isinstance(other_model, Model), \
            'Expected Dragonfly Model. Got {}.'.format(type(other_model))
        if self.units != other_model.units:
            other_model.convert_to_units(self.units)
        # add the Buildings while checking to see if they should be merged
        bldg_to_add = list(self._buildings)
        for o_bldg in other_model._buildings:
            for e_bldg in bldg_to_add:
                if o_bldg.identifier == e_bldg.identifier:
                    e_bldg.add_stories(o_bldg.unique_stories)
                    e_bldg.add_room_3ds(o_bldg.room_3ds)
                    break
            else:
                bldg_to_add.append(o_bldg)
        self._buildings = bldg_to_add
        # add the ContextShades while checking for duplicate IDs
        if len(other_model._context_shades) != 0:
            new_context = self._context_shades
            exist_set = {shd.identifier for shd in self._context_shades}
            for o_shd in other_model._context_shades:
                if o_shd.identifier not in exist_set:
                    new_context.append(o_shd)
                    exist_set.add(o_shd.identifier)
            self._context_shades = new_context

    def add_building(self, obj):
        """Add a Building object to the model.

        In the case that the Building or Story identifiers of the input obj match
        one the current model, these objects will be merged together. Room2Ds
        that are identical within a merged Story will not be merged in order
        to avoid ID conflicts.
        """
        assert isinstance(obj, Building), 'Expected Building. Got {}.'.format(type(obj))
        for e_bldg in self._buildings:
            if obj.identifier == e_bldg.identifier:
                e_bldg.add_stories(obj.unique_stories)
                e_bldg.add_room_3ds(obj.room_3ds)
                break
        else:
            self._buildings.append(obj)

    def add_context_shade(self, obj):
        """Add a ContextShade object to the model."""
        assert isinstance(obj, ContextShade), \
            'Expected ContextShade. Got {}.'.format(type(obj))
        self._context_shades.append(obj)

    def buildings_by_identifier(self, identifiers):
        """Get a list of Building objects in the model given Building identifiers."""
        buildings = []
        for identifier in identifiers:
            for bldg in self._buildings:
                if bldg.identifier == identifier:
                    buildings.append(bldg)
                    break
            else:
                raise ValueError(
                    'Building "{}" was not found in the model.'.format(identifier))
        return buildings

    def stories_by_identifier(self, identifiers):
        """Get a list of Story objects in the model given Story identifiers."""
        stories, model_stories = [], self.stories
        for identifier in identifiers:
            for story in model_stories:
                if story.identifier == identifier:
                    stories.append(story)
                    break
            else:
                raise ValueError(
                    'Story "{}" was not found in the model.'.format(identifier))
        return stories

    def room_2ds_by_identifier(self, identifiers):
        """Get a list of Room2D objects in the model given Room2D identifiers."""
        room_2ds, model_room_2ds = [], self.room_2ds
        for identifier in identifiers:
            for room in model_room_2ds:
                if room.identifier == identifier:
                    room_2ds.append(room)
                    break
            else:
                raise ValueError(
                    'Room2D "{}" was not found in the model.'.format(identifier))
        return room_2ds

    def room_3ds_by_identifier(self, identifiers):
        """Get a list of 3D Honeybee Room objects in the model given Room identifiers."""
        room_3ds, model_room_3ds = [], self.room_3ds
        for identifier in identifiers:
            for room in model_room_3ds:
                if room.identifier == identifier:
                    room_3ds.append(room)
                    break
            else:
                raise ValueError(
                    'Room "{}" was not found in the model.'.format(identifier))
        return room_3ds

    def context_shade_by_identifier(self, identifiers):
        """Get a list of ContextShade objects in the model given identifiers.
        """
        context_shades = []
        for identifier in identifiers:
            for shd in self._context_shades:
                if shd.identifier == identifier:
                    context_shades.append(shd)
                    break
            else:
                raise ValueError(
                    'ContextShade "{}" was not found in the model.'.format(identifier))
        return context_shades

    def add_prefix(self, prefix):
        """Change the identifier of this object and child objects by inserting a prefix.

        This is particularly useful in workflows where you duplicate and edit
        a starting object and then want to combine it with the original object
        since all objects within a Model must have unique identifiers to be valid.

        Args:
            prefix: Text that will be inserted at the start of this object's
                (and child objects') identifier and display_name. It is recommended
                that this prefix be short to avoid maxing out the 100 allowable
                characters for identifiers.
        """
        for bldg in self._buildings:
            bldg.add_prefix(prefix)
        for shade in self._context_shades:
            shade.add_prefix(prefix)

    def resolve_id_collisions(self):
        """Resolve collisions of duplicate identifiers that exist in the Model.

        In the case that Building or Story identifiers are duplicated, these objects
        will be merged together. In the case that Room2Ds that have matching
        identifiers, an integer will be automatically appended to the Room2D ID
        to make it unique. Context Shades and 3D Rooms that collide will similarly
        have their IDs tweaked with an integer if they are duplicated.
        """
        # loop through the Buildings and Stories and combine duplicated IDs
        merged_buildings = []
        for o_bldg in self._buildings:
            for e_bldg in merged_buildings:
                if o_bldg.identifier == e_bldg.identifier:
                    e_bldg.add_stories(o_bldg.unique_stories, add_duplicate_ids=True)
                    e_bldg.add_room_3ds(o_bldg.room_3ds, add_duplicate_ids=True)
                    break
            else:
                merged_buildings.append(o_bldg)
        self._buildings = merged_buildings
        # loop through all Rooms and ensure their identifiers are unique
        rm_dict = {}
        for room_2d in self.room_2ds + self.room_3ds:
            room_2d.identifier = clean_and_number_string(
                room_2d.identifier, rm_dict, 'Room identifier')
        # loop through all ContextShades ans ensure their identifiers are unique
        shd_dict = {}
        for shade in self._context_shades:
            shade.identifier = clean_and_number_string(
                shade.identifier, shd_dict, 'Shade identifier')

    def reset_ids(self, repair_surface_bcs=True):
        """Reset the identifiers of all Model objects to be derived from display_names.

        In the event that duplicate identifiers are found, an integer will be
        automatically appended to the new ID to make it unique. This is similar
        to the routines that automatically assign unique names to OpenStudio SDK
        objects.

        Args:
            repair_surface_bcs: A Boolean to note whether all Surface boundary
                conditions across the model should be updated with the new
                identifiers that were generated from the display names. (Default: True).
        """
        # set up dictionaries to hold various pieces of information
        room_map, face_map, ap_map, dr_map = {}, {}, {}, {}
        bldg_dict, story_dict, rm_dict, shd_dict = {}, {}, {}, {}
        face_dict, ap_dict, dr_dict = {}, {}, {}

        # loop through the objects and change their identifiers
        for shade in self._context_shades:
            shade.identifier = clean_and_number_string(
                shade.display_name, shd_dict, 'Shade identifier')
        for bldg in self._buildings:
            bldg.identifier = clean_and_number_string(
                bldg.display_name, bldg_dict, 'Building identifier')
        for story in self.stories:
            story.identifier = clean_and_number_string(
                story.display_name, story_dict, 'Story identifier')
        for rm in self.room_2ds + self.room_3ds:
            new_id = clean_and_number_string(
                rm.display_name, rm_dict, 'Room identifier')
            room_map[rm.identifier] = new_id
            rm.identifier = new_id
            if isinstance(rm, HBRoom):
                for face in rm.faces:
                    new_id = clean_and_number_string(
                        face.display_name, face_dict, 'Face identifier')
                    face_map[face.identifier] = new_id
                    face.identifier = new_id
                    for ap in face.apertures:
                        new_id = clean_and_number_string(
                            ap.display_name, ap_dict, 'Aperture identifier')
                        ap_map[ap.identifier] = new_id
                        ap.identifier = new_id
                    for dr in face.doors:
                        new_id = clean_and_number_string(
                            dr.display_name, dr_dict, 'Door identifier')
                        dr_map[dr.identifier] = new_id
                        dr.identifier = new_id

        # reset all of the Surface boundary conditions if requested
        if repair_surface_bcs:
            # reset all of the Surface conditions on the Room2Ds
            for room in self.room_2ds:
                new_bcs = []
                for bc in room.boundary_conditions:
                    if isinstance(bc, Surface):
                        old_objs = bc.boundary_condition_objects
                        face_id = old_objs[0].split('..')[-1]
                        new_adj_f = '{}..{}'.format(room_map[old_objs[1]], face_id)
                        new_objs = (new_adj_f, room_map[old_objs[1]])
                        new_bc = Surface(new_objs)
                        new_bcs.append(new_bc)
                    else:
                        new_bcs.append(bc)
                room.boundary_conditions = new_bcs
            # reset all of the Surface conditions on the 3D Rooms
            for room in self.room_3ds:
                for face in room.faces:
                    if isinstance(face.boundary_condition, Surface):
                        old_objs = face.boundary_condition.boundary_condition_objects
                        new_objs = (face_map[old_objs[0]], room_map[old_objs[1]])
                        new_bc = Surface(new_objs)
                        face.boundary_condition = new_bc
                        for ap in face.apertures:
                            old_objs = ap.boundary_condition.boundary_condition_objects
                            new_objs = (ap_map[old_objs[0]], face_map[old_objs[1]],
                                        room_map[old_objs[2]])
                            new_bc = Surface(new_objs, True)
                            ap.boundary_condition = new_bc
                        for dr in face.doors:
                            old_objs = dr.boundary_condition.boundary_condition_objects
                            new_objs = (dr_map[old_objs[0]], face_map[old_objs[1]],
                                        room_map[old_objs[2]])
                            new_bc = Surface(new_objs, True)
                            dr.boundary_condition = new_bc

    def separate_top_bottom_floors(self, separate_mid=False):
        """Separate top/bottom Stories with non-unity multipliers into their own Stories.

        The resulting first and last Stories will each have a multiplier of 1 and
        duplicated middle Stories will be added as needed. This method also
        automatically assigns the first story Room2Ds to have a ground contact
        floor and the top story Room2Ds to have an outdoor-exposed roof.

        separate_mid: Boolean to note whether all mid-level Stories with non-unity
            multipliers should be separated into two or three Stories. This means
            that the top of each unique story will have outdoor-exposed roofs when
            no Room2Ds are sensed above a given room. (Default: False).
        """
        if not separate_mid:
            for bldg in self._buildings:
                bldg.separate_top_bottom_floors()
        else:
            p_tol = parse_distance_string('0.01m', self.units)
            for bldg in self._buildings:
                bldg.separate_mid_floors(p_tol)

    def set_outdoor_window_parameters(self, window_parameter):
        """Set all outdoor walls of the Buildings to have the same window parameters."""
        for bldg in self._buildings:
            bldg.set_outdoor_window_parameters(window_parameter)

    def set_outdoor_shading_parameters(self, shading_parameter):
        """Set all outdoor walls of the Buildings to have the same shading parameters."""
        for bldg in self._buildings:
            bldg.set_outdoor_shading_parameters(shading_parameter)

    def to_rectangular_windows(self):
        """Convert all of the windows of the Story to the RectangularWindows format."""
        for bldg in self._buildings:
            bldg.to_rectangular_windows()

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
        self.properties.move(moving_vec)

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
        self.properties.rotate_xy(angle, origin)

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
        self.properties.reflect(plane)

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
        self.properties.scale(factor, origin)

    def convert_to_units(self, units='Meters'):
        """Convert all of the geometry in this model to certain units.

        This involves scaling the geometry, scaling the Model tolerance, and
        changing the Model's units property.

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
            scale_fac1 = conversion_factor_to_meters(self.units)
            scale_fac2 = conversion_factor_to_meters(units)
            scale_fac = scale_fac1 / scale_fac2
            self.scale(scale_fac)
            self.tolerance = self.tolerance * scale_fac
            self.units = units

    def check_all(self, raise_exception=True, detailed=False):
        """Check all of the aspects of the Model for possible errors.

        Args:
            raise_exception: Boolean to note whether a ValueError should be raised
                if any Model errors are found. If False, this method will simply
                return a text string with all errors that were found. (Default: True).
            detailed: Boolean for whether the returned object is a detailed list of
                dicts with error info or a string with a message. (Default: False).

        Returns:
            A text string with all errors that were found. This string will be empty
            of no errors were found.
        """
        # set up defaults to ensure the method runs correctly
        detailed = False if raise_exception else detailed
        msgs = []
        assert self.tolerance != 0, \
            'Model must have a non-zero tolerance in order to perform geometry checks.'
        tol, a_tol = self.tolerance, self.angle_tolerance
        # perform checks for key dragonfly model schema rules
        msgs.append(self.check_duplicate_context_shade_identifiers(False, detailed))
        msgs.append(self.check_duplicate_room_2d_identifiers(False, detailed))
        msgs.append(self.check_duplicate_story_identifiers(False, detailed))
        msgs.append(self.check_duplicate_building_identifiers(False, detailed))
        msgs.append(self.check_degenerate_room_2ds(tol, False, detailed))
        msgs.append(self.check_self_intersecting_room_2ds(tol, False, detailed))
        msgs.append(self.check_window_parameters_valid(tol, False, detailed))
        msgs.append(self.check_missing_adjacencies(False, detailed))
        msgs.append(self.check_no_room2d_overlaps(tol, False, detailed))
        msgs.append(self.check_no_roof_overlaps(tol, False, detailed))
        msgs.append(self.check_all_room3d(tol, a_tol, False, detailed))
        # check the extension attributes
        ext_msgs = self._properties._check_extension_attr()
        if detailed:
            ext_msgs = [m for m in ext_msgs if isinstance(m, list)]
        msgs.extend(ext_msgs)
        # output a final report of errors or raise an exception
        full_msgs = [msg for msg in msgs if msg]
        if detailed:
            return [m for msg in full_msgs for m in msg]
        full_msg = '\n'.join(full_msgs)
        if raise_exception and len(full_msgs) != 0:
            raise ValueError(full_msg)
        return full_msg

    def check_duplicate_building_identifiers(self, raise_exception=True, detailed=False):
        """Check that there are no duplicate Building identifiers in the model.

        Args:
            raise_exception: Boolean to note whether a ValueError should be raised
                if duplicate identifiers are found. (Default: True).
            detailed: Boolean for whether the returned object is a detailed list of
                dicts with error info or a string with a message. (Default: False).

        Returns:
            A string with the message or a list with a dictionary if detailed is True.
        """
        return check_duplicate_identifiers(
            self._buildings, raise_exception, 'Building', detailed, '100004', 'Core',
            'Duplicate Building Identifier')

    def check_duplicate_story_identifiers(self, raise_exception=True, detailed=False):
        """Check that there are no duplicate Story identifiers in the model.

        Args:
            raise_exception: Boolean to note whether a ValueError should be raised
                if duplicate identifiers are found. (Default: True).
            detailed: Boolean for whether the returned object is a detailed list of
                dicts with error info or a string with a message. (Default: False).

        Returns:
            A string with the message or a list with a dictionary if detailed is True.
        """
        return check_duplicate_identifiers(
            self.stories, raise_exception, 'Story', detailed, '100003', 'Core',
            'Duplicate Story Identifier')

    def check_duplicate_room_2d_identifiers(self, raise_exception=True, detailed=False):
        """Check that there are no duplicate Room2D identifiers in the model.

        Args:
            raise_exception: Boolean to note whether a ValueError should be raised
                if duplicate identifiers are found. (Default: True).
            detailed: Boolean for whether the returned object is a detailed list of
                dicts with error info or a string with a message. (Default: False).

        Returns:
            A string with the message or a list with a dictionary if detailed is True.
        """
        return check_duplicate_identifiers(
            self.room_2ds, raise_exception, 'Room2D', detailed, '100002', 'Core',
            'Duplicate Room2D Identifier')

    def check_duplicate_context_shade_identifiers(
            self, raise_exception=True, detailed=False):
        """Check that there are no duplicate ContextShade identifiers in the model.

        Args:
            raise_exception: Boolean to note whether a ValueError should be raised
                if duplicate identifiers are found. (Default: True).
            detailed: Boolean for whether the returned object is a detailed list of
                dicts with error info or a string with a message. (Default: False).

        Returns:
            A string with the message or a list with a dictionary if detailed is True.
        """
        return check_duplicate_identifiers(
            self._context_shades, raise_exception, 'ContextShade', detailed,
            '100001', 'Core', 'Duplicate ContextShade Identifier')

    def check_degenerate_room_2ds(self, tolerance=None, raise_exception=True,
                                  detailed=False):
        """Check that all Room2Ds are not degenerate with zero area.

        Args:
            tolerance: The minimum difference between the coordinate values of two
                vertices at which they can be considered equivalent. If None, the
                Model tolerance will be used. (Default: None).
            raise_exception: Boolean to note whether a ValueError should be raised
                if the window parameters are not valid.
            detailed: Boolean for whether the returned object is a detailed list of
                dicts with error info or a string with a message. (Default: False).

        Returns:
            A string with the message or a list with a dictionary if detailed is True.
        """
        tolerance = self.tolerance if tolerance is None else tolerance
        detailed = False if raise_exception else detailed
        msgs = []
        for room in self.room_2ds:
            msg = room.check_degenerate(tolerance, False, detailed)
            if detailed:
                msgs.extend(msg)
            elif msg != '':
                msgs.append(msg)
        if detailed:
            return msgs
        full_msg = '\n'.join(msgs)
        if raise_exception and len(msgs) != 0:
            raise ValueError(full_msg)
        return full_msg

    def check_self_intersecting_room_2ds(self, tolerance=None, raise_exception=True,
                                         detailed=False):
        """Check that all Room2Ds do not intersect with themselves (like a bowtie).

        Note that objects that have duplicate vertices will not be considered
        self-intersecting and are valid.

        Args:
            tolerance: The minimum difference between the coordinate values of two
                vertices at which they can be considered equivalent. If None, the
                Model tolerance will be used. (Default: None).
            raise_exception: Boolean to note whether a ValueError should be raised
                if the window parameters are not valid.
            detailed: Boolean for whether the returned object is a detailed list of
                dicts with error info or a string with a message. (Default: False).

        Returns:
            A string with the message or a list with a dictionary if detailed is True.
        """
        tolerance = self.tolerance if tolerance is None else tolerance
        detailed = False if raise_exception else detailed
        msgs = []
        for room in self.room_2ds:
            msg = room.check_self_intersecting(tolerance, False, detailed)
            if detailed:
                msgs.extend(msg)
            elif msg != '':
                msgs.append(msg)
        if detailed:
            return msgs
        full_msg = '\n'.join(msgs)
        if raise_exception and len(msgs) != 0:
            raise ValueError(full_msg)
        return full_msg

    def check_window_parameters_valid(
            self, tolerance=0.01, raise_exception=True, detailed=False):
        """Check that all Room2Ds have window parameters produce valid apertures.

        This means that the resulting Apertures are completely bounded by their
        parent wall Face and attributes like window to wall ratio are accurate.

        Args:
            tolerance: The minimum difference between the coordinate values of two
                vertices at which they can be considered equivalent. (Default: 0.01,
                suitable for objects in meters).
            raise_exception: Boolean to note whether a ValueError should be raised
                if the window parameters are not valid.
            detailed: Boolean for whether the returned object is a detailed list of
                dicts with error info or a string with a message. (Default: False).

        Returns:
            A string with the message or a list with a dictionary if detailed is True.
        """
        detailed = False if raise_exception else detailed
        msgs = []
        for room in self.room_2ds:
            msg = room.check_window_parameters_valid(tolerance, False, detailed)
            if detailed:
                msgs.extend(msg)
            elif msg != '':
                msgs.append(msg)
        if detailed:
            return msgs
        full_msg = '\n'.join(msgs)
        if raise_exception and len(msgs) != 0:
            raise ValueError(full_msg)
        return full_msg

    def check_missing_adjacencies(self, raise_exception=True, detailed=False):
        """Check that all Room2Ds have adjacent objects that exist within each Story.

        Args:
            raise_exception: Boolean to note whether a ValueError should be raised
                if missing or invalid adjacencies are found. (Default: True).
            detailed: Boolean for whether the returned object is a detailed list of
                dicts with error info or a string with a message. (Default: False).

        Returns:
            A string with the message or a list with a dictionary if detailed is True.
        """
        bldg_ids = []
        for bldg in self._buildings:
            for story in bldg._unique_stories:
                adj_msg = story.check_missing_adjacencies(False, detailed)
                if adj_msg:
                    if detailed:
                        bldg_ids.extend(adj_msg)
                    else:
                        bldg_ids.append('{}\n {}'.format(story.full_id, adj_msg))
        if detailed:
            return bldg_ids
        if bldg_ids != []:
            msg = 'The following Stories have missing adjacencies in ' \
                'the Model:\n{}'.format('\n'.join(bldg_ids))
            if raise_exception:
                raise ValueError(msg)
            return msg
        return ''

    def check_no_room2d_overlaps(
            self, tolerance=None, raise_exception=True, detailed=False):
        """Check that geometries of Room2Ds do not overlap with one another.

        Overlaps in Room2Ds mean that the Room volumes will collide with one
        another during translation to Honeybee.

        Args:
            tolerance: The minimum distance that two Room2Ds geometries can overlap
                with one another and still be considered valid. If None, the Model
                tolerance will be used. (Default: None).
            raise_exception: Boolean to note whether a ValueError should be raised
                if overlapping geometries are found. (Default: True).
            detailed: Boolean for whether the returned object is a detailed list of
                dicts with error info or a string with a message. (Default: False).

        Returns:
            A string with the message or a list with a dictionary if detailed is True.
        """
        tolerance = self.tolerance if tolerance is None else tolerance
        bldg_ids = []
        for bldg in self._buildings:
            for story in bldg._unique_stories:
                ov_msg = story.check_no_room2d_overlaps(tolerance, False, detailed)
                if ov_msg:
                    if detailed:
                        bldg_ids.extend(ov_msg)
                    else:
                        bldg_ids.append('{}\n {}'.format(bldg.full_id, ov_msg))
        if detailed:
            return bldg_ids
        if bldg_ids != []:
            msg = 'The following Buildings have overlaps in their Room2D geometry' \
                ':\n{}'.format('\n'.join(bldg_ids))
            if raise_exception:
                raise ValueError(msg)
            return msg
        return ''

    def check_no_roof_overlaps(
            self, tolerance=None, raise_exception=True, detailed=False):
        """Check that geometries of RoofSpecifications do not overlap with one another.

        Overlaps make the Roof geometry unusable for translation to Honeybee.

        Args:
            tolerance: The minimum distance that two Roof geometries can overlap
                with one another and still be considered valid. If None, the Model
                tolerance will be used. (Default: None).
            raise_exception: Boolean to note whether a ValueError should be raised
                if overlapping geometries are found. (Default: True).
            detailed: Boolean for whether the returned object is a detailed list of
                dicts with error info or a string with a message. (Default: False).

        Returns:
            A string with the message or a list with a dictionary if detailed is True.
        """
        tolerance = self.tolerance if tolerance is None else tolerance
        bldg_ids = []
        for bldg in self._buildings:
            for story in bldg._unique_stories:
                ov_msg = story.check_no_roof_overlaps(tolerance, False, detailed)
                if ov_msg:
                    if detailed:
                        bldg_ids.extend(ov_msg)
                    else:
                        bldg_ids.append('{}\n {}'.format(bldg.full_id, ov_msg))
        if detailed:
            return bldg_ids
        if bldg_ids != []:
            msg = 'The following Buildings have overlaps in their roof geometry' \
                ':\n{}'.format('\n'.join(bldg_ids))
            if raise_exception:
                raise ValueError(msg)
            return msg
        return ''

    def check_all_room3d(
            self, tolerance=None, angle_tolerance=None,
            raise_exception=True, detailed=False):
        """Check all attributes of 3D Honeybee Rooms assigned to the Model's Buildings.

        This includes checking for duplicate Room/Face/Aperture/Door/Shade identifiers,
        checking planarity/self-intersection/degeneracy, checking that all rooms are,
        solid, and checking the adjacencies (among other attributes).

        Args:
            tolerance: tolerance: The maximum difference between x, y, and z values
                at which face vertices are considered equivalent. If None, the Model
                tolerance will be used. (Default: None).
            angle_tolerance: The max angle difference in degrees that vertices are
                allowed to differ from one another in order to consider them colinear.
                If None, the Model angle_tolerance will be used. (Default: None).
            raise_exception: Boolean to note whether a ValueError should be raised
                if an error is found. (Default: True).
            detailed: Boolean for whether the returned object is a detailed list of
                dicts with error info or a string with a message. (Default: False).

        Returns:
            A string with the message or a list with a dictionary if detailed is True.
        """
        room_3ds = self.room_3ds
        if len(room_3ds) != 0:
            tol = self.tolerance if tolerance is None else tolerance
            a_tol = self.angle_tolerance if angle_tolerance is None else angle_tolerance
            dummy_model = HBModel(
                'validation_model', room_3ds, units=self.units,
                tolerance=tol, angle_tolerance=a_tol)
            return dummy_model.check_all(raise_exception, detailed)
        return [] if detailed else ''

    def to_honeybee(self, object_per_model='Building', shade_distance=None,
                    use_multiplier=True, add_plenum=False, cap=False,
                    solve_ceiling_adjacencies=False, tolerance=None,
                    enforce_adj=True, enforce_solid=True):
        """Convert Dragonfly Model to an array of Honeybee Models.

        Args:
            object_per_model: Text to describe how the input Buildings should be
                divided across the output Models. (Default: 'Building'). Choose from
                the following options:

                * District - All buildings will be added to a single Honeybee Model.
                  Such a Model can take a long time to simulate so this is only
                  recommended for small numbers of buildings or cases where
                  exchange of data between Buildings is necessary.
                * Building - Each building will be exported into its own Model.
                  For each Model, the other buildings input to this component will
                  appear as context shade geometry.
                * Story - Each Story of each Building will be exported into its
                  own Model. For each Honeybee Model, the other input Buildings
                  will appear as context shade geometry as will all of the other
                  stories of the same building.

            shade_distance: An optional number to note the distance beyond which other
                objects' shade should not be exported into a given Model. This is
                helpful for reducing the simulation run time of each Model when other
                connected buildings are too far away to have a meaningful impact on
                the results. If None, all other buildings will be included as context
                shade in each and every Model. Set to 0 to exclude all neighboring
                buildings from the resulting models. (Default: None).
            use_multiplier: If True, the multipliers on this Model's Stories will be
                passed along to the generated Honeybee Room objects, indicating the
                simulation will be run once for each unique room and then results
                will be multiplied. If False, full geometry objects will be written
                for each and every floor in the building that are represented through
                multipliers and all resulting multipliers will be 1. (Default: True).
            add_plenum: Boolean to indicate whether ceiling/floor plenums should
                be auto-generated for the Rooms. (Default: False).
            cap: Boolean to note whether building shade representations should be capped
                with a top face. Usually, this is not necessary to account for
                blocked sun and is only needed when it's important to account for
                reflected sun off of roofs. (Default: False).
            solve_ceiling_adjacencies: Boolean to note whether adjacencies should be
                solved between interior stories when Room2D floor and ceiling
                geometries are coplanar. This ensures that Surface boundary
                conditions are used instead of Adiabatic ones. Note that this input
                has no effect when the object_per_model is Story. (Default: False).
            tolerance: The minimum distance in z values of floor_height and
                floor_to_ceiling_height at which adjacent Faces will be split.
                This is also used in the generation of Windows. This must be a
                positive, non-zero number. If None, the Model's own tolerance
                will be used. (Default: None).
            enforce_adj: Boolean to note whether an exception should be raised if
                an adjacency between two Room2Ds is invalid (True) or if the invalid
                Surface boundary condition should be replaced with an Outdoor
                boundary condition (False). If False, any Walls containing
                WindowParameters and an illegal boundary condition will also
                be replaced with an Outdoor boundary condition. (Default: True).
            enforce_solid: Boolean to note whether rooms should be translated
                as solid extrusions whenever translating them with custom
                roof geometry produces a non-solid result (True) or the non-solid
                room geometry should be allowed to remain in the result (False).
                The latter is useful for understanding why a particular roof
                geometry has produced a non-solid result. (Default: True).

        Returns:
            An array of Honeybee Models that together represent this Dragonfly Model.
        """
        # check the tolerance, which is required to convert to honeybee
        tolerance = self.tolerance if tolerance is None else tolerance
        assert tolerance != 0, \
            'Model tolerance must be non-zero to use Model.to_honeybee.'

        # create the model objects
        if len(self.buildings) == 0:  # model containing only context shade
            hb_shades, hb_shade_meshes = [], []
            for shd in self.context_shades:
                for s in shd.to_honeybee():
                    if isinstance(s, HBShade):
                        hb_shades.append(s)
                    else:
                        hb_shade_meshes.append(s)
            h_model = HBModel(self.identifier, orphaned_shades=hb_shades,
                              shade_meshes=hb_shade_meshes)
            h_model.display_name = self.display_name
            models = [h_model]
        elif object_per_model is None or object_per_model.title() == 'Building':
            models = Building.buildings_to_honeybee(
                self._buildings, self._context_shades, shade_distance,
                use_multiplier, add_plenum, cap, tolerance=tolerance,
                enforce_adj=enforce_adj, enforce_solid=enforce_solid)
        elif object_per_model.title() == 'Story':
            models = Building.stories_to_honeybee(
                self._buildings, self._context_shades, shade_distance,
                use_multiplier, add_plenum, cap, tolerance=tolerance,
                enforce_adj=enforce_adj, enforce_solid=enforce_solid)
        elif object_per_model.title() == 'District':
            models = [Building.district_to_honeybee(
                self._buildings, use_multiplier, add_plenum, tolerance=tolerance,
                enforce_adj=enforce_adj, enforce_solid=enforce_solid)]
            for shd_group in self._context_shades:
                for shd in shd_group.to_honeybee():
                    for model in models:
                        if isinstance(shd, HBShade):
                            model.add_shade(shd)
                        else:
                            model.add_shade_mesh(shd)
        else:
            raise ValueError('Unrecognized object_per_model input: '
                             '{}'.format(object_per_model))

        # solve ceiling adjacencies if requested
        if solve_ceiling_adjacencies and \
                object_per_model.title() in ('Building', 'District'):
            story_rel_types = {}
            for bldg in self.buildings:
                for i, story in enumerate(bldg.unique_stories):
                    rel_types = []
                    if i == 0 or bldg.unique_stories[i - 1].multiplier == 1:
                        rel_types.append(Floor)
                    if story.multiplier == 1:
                        rel_types.append(RoofCeiling)
                    story_rel_types[story.display_name] = tuple(rel_types)
            for model in models:
                self._solve_ceil_adj(model.rooms, story_rel_types,
                                     tolerance, self.angle_tolerance)

        # change the tolerance and units systems to match the dragonfly model
        for model in models:
            model.units = self.units
            model.tolerance = tolerance
            model.angle_tolerance = self.angle_tolerance

        # transfer Model extension attributes to the honeybee models
        for h_model in models:
            h_model._properties = self.properties.to_honeybee(h_model)

        return models

    def to_geojson_dict(self, location, point=Point2D(0, 0), tolerance=None):
        """Convert Dragonfly Model to a geoJSON-style Python dictionary.

        This dictionary can be written into a JSON, which is then a valid geoJSON
        that can be visualized in any geoJSON viewer. Each dragonfly Building
        will appear in the geoJSON as a single feature (either as a Polygon or
        a MultiPolygon).

        Args:
            location: A ladybug Location object possessing longitude and latitude data.
            point: A ladybug_geometry Point2D for where the location object exists
                within the space of a scene. The coordinates of this point are
                expected to be in the units of this Model. (Default: (0, 0)).
            tolerance: The minimum distance between points at which they are
                not considered touching. If None, the Model's own tolerance
                will be used. (Default: None).

        Returns:
            A Python dictionary in a geoJSON style with each Building in the Model
            as a separate feature.
        """
        # set up the base dictionary for the geoJSON
        geojson_dict = {'type': 'FeatureCollection', 'features': [], 'mappers': []}

        # ensure that the Model we are working with is in meters
        model = self
        if self.units != 'Meters':
            model = self.duplicate()  # duplicate to avoid editing this object
            model.convert_to_units('Meters')
            point = point.scale(conversion_factor_to_meters(self.units))

        # assign the site information in the project key
        project_dict = {
            'id': self.identifier,
            'name': self.display_name,
            'city': location.city,
            'country': location.country,
            'elevation': location.elevation,
            'latitude': location.latitude,
            'longitude': location.longitude,
            'time_zone': location.time_zone,
            'cad_coordinates': [point.x, point.y]
        }
        geojson_dict['project'] = project_dict

        # get the conversion factors over to (longitude, latitude)
        origin_lon_lat = origin_long_lat_from_location(location, point)
        convert_facs = meters_to_long_lat_factors(origin_lon_lat)
        tolerance = self.tolerance if tolerance is None else tolerance

        # export each building as a feature in the file
        for bldg in model.buildings:
            # create the base dictionary
            feature_dict = {'geometry': {}, 'properties': {}, 'type': 'Feature'}

            # add the geometry including coordinates
            footprint = bldg.footprint(tolerance)
            if len(footprint) == 1:
                feature_dict['geometry']['type'] = 'Polygon'
                feature_dict['geometry']['coordinates'] = \
                    self._face3d_to_geojson_coordinates(
                        footprint[0], origin_lon_lat, convert_facs)
            else:
                feature_dict['geometry']['type'] = 'MultiPolygon'
                all_coords = []
                for floor in footprint:
                    all_coords.append(
                        self._face3d_to_geojson_coordinates(
                            floor, origin_lon_lat, convert_facs))
                feature_dict['geometry']['coordinates'] = all_coords

            # add several of the properties to the geoJSON
            feature_dict['properties']['building_type'] = 'Mixed use'
            feature_dict['properties']['floor_area'] = bldg.floor_area
            feature_dict['properties']['footprint_area'] = bldg.footprint_area
            feature_dict['properties']['id'] = bldg.identifier
            feature_dict['properties']['name'] = bldg.display_name
            feature_dict['properties']['number_of_stories'] = bldg.story_count
            feature_dict['properties']['number_of_stories_above_ground'] = \
                bldg.story_count_above_ground
            feature_dict['properties']['maximum_roof_height'] = \
                bldg.height_above_ground
            feature_dict['properties']['floor_height'] = bldg.height / bldg.story_count
            feature_dict['properties']['type'] = 'Building'

            # attempt to determine the year built from the construction set
            year_built = datetime.date.today().year
            if hasattr(bldg.properties, 'energy'):
                cs_name = bldg.properties.energy.construction_set.display_name
                if len(cs_name) >= 4 and all(txt.isdigit() for txt in cs_name[:4]):
                    year_built = int(cs_name[:4])
            feature_dict['properties']['year_built'] = year_built

            # append the feature to the global dictionary
            geojson_dict['features'].append(feature_dict)

        return geojson_dict

    def to_geojson(self, location, point=Point2D(0, 0), folder=None, tolerance=None):
        """Convert Dragonfly Model to a geoJSON of buildings footprints.

        This geoJSON will be in a format that is compatible with the URBANopt SDK,
        including properties for floor_area, footprint_area, and detailed_model_filename,
        which will align with the paths to OpenStudio model (.osm) files output
        from honeybee Models translated to OSM.

        Args:
            location: A ladybug Location object possessing longitude and latitude data.
            point: A ladybug_geometry Point2D for where the location object exists
                within the space of a scene. The coordinates of this point are
                expected to be in the units of this Model. (Default: (0, 0)).
            folder: Text for the full path to where the geojson file will be written.
                If None, a sub-folder within the honeybee default simulation
                folder will be used. (Default: None).
            tolerance: The minimum distance between points at which they are
                not considered touching. If None, the Model's own tolerance
                will be used. (Default: None).

        Returns:
            The path to a geoJSON file that contains polygons for all of the
            Buildings within the dragonfly model along with their properties
            (floor area, number of stories, etc.). The polygons will also possess
            detailed_model_filename keys that align with where OpenStudio models
            would be written, assuming the input folder matches that used to
            export OpenStudio models.
        """
        # set the default simulation folder
        if folder is None:
            folder = folders.default_simulation_folder

        # get the geojson dictionary
        geojson_dict = self.to_geojson_dict(location, point, tolerance)

        # write out the dictionary to a geojson file
        project_folder = os.path.join(
            folder, re.sub(r'[^.A-Za-z0-9_-]', '_', self.display_name))
        preparedir(project_folder, remove_content=False)
        file_path = os.path.join(project_folder, '{}.geojson'.format(self.identifier))
        with open(file_path, 'w') as fp:
            json.dump(geojson_dict, fp, indent=4)
        return file_path

    def to_dict(self, included_prop=None):
        """Return Model as a dictionary.

        Args:
            included_prop: List of properties to filter keys that must be included in
                output dictionary. For example ['energy'] will include 'energy' key if
                available in properties to_dict. By default all the keys will be
                included. To exclude all the keys from extensions use an empty list.
        """
        base = {'type': 'Model'}
        base['identifier'] = self.identifier
        base['display_name'] = self.display_name
        base['properties'] = self.properties.to_dict(included_prop)
        if self._buildings != []:
            base['buildings'] = \
                [bldg.to_dict(True, included_prop) for bldg in self._buildings]
        if self._context_shades != []:
            base['context_shades'] = \
                [shd.to_dict(True, included_prop) for shd in self._context_shades]
        base['units'] = self.units
        if self.tolerance != 0:
            base['tolerance'] = self.tolerance
        if self.angle_tolerance != 0:
            base['angle_tolerance'] = self.angle_tolerance

        if self.user_data is not None:
            base['user_data'] = self.user_data
        if df_folders.dragonfly_schema_version is not None:
            base['version'] = df_folders.dragonfly_schema_version_str
        return base

    def to_dfjson(self, name=None, folder=None, indent=None, included_prop=None):
        """Write Dragonfly model to DFJSON.

        Args:
            name: A text string for the name of the DFJSON file. If None, the model
                identifier wil be used. (Default: None).
            folder: A text string for the directory where the DFJSON will be written.
                If unspecified, the default simulation folder will be used. This
                is usually at "C:\\Users\\USERNAME\\simulation" on Windows.
            indent: A positive integer to set the indentation used in the resulting
                DFJSON file. (Default: None).
            included_prop: List of properties to filter keys that must be included in
                output dictionary. For example ['energy'] will include 'energy' key if
                available in properties to_dict. By default all the keys will be
                included. To exclude all the keys from extensions use an empty list.
        """
        # create dictionary from the Dragonfly Model
        df_dict = self.to_dict(included_prop=included_prop)
        # set up a name and folder for the DFJSON
        if name is None:
            name = self.identifier
        file_name = name if name.lower().endswith('.dfjson') or \
            name.lower().endswith('.json') else '{}.dfjson'.format(name)
        folder = folder if folder is not None else folders.default_simulation_folder
        df_file = os.path.join(folder, file_name)
        # write DFJSON
        with open(df_file, 'w') as fp:
            json.dump(df_dict, fp, indent=indent)
        return df_file

    def to_dfpkl(self, name=None, folder=None, included_prop=None):
        """Writes Dragonfly model to compressed pickle file (DFpkl).

        Args:
            name: A text string for the name of the pickle file. If None, the model
                identifier wil be used. (Default: None).
            folder: A text string for the directory where the pickle will be written.
                If unspecified, the default simulation folder will be used. This
                is usually at "C:\\Users\\USERNAME\\simulation."
            included_prop: List of properties to filter keys that must be included in
                output dictionary. For example ['energy'] will include 'energy' key if
                available in properties to_dict. By default all the keys will be
                included. To exclude all the keys from extensions use an empty list.
        """
        # create dictionary from the Dragonfly Model
        df_dict = self.to_dict(included_prop=included_prop)
        # set up a name and folder for the DFpkl
        if name is None:
            name = self.identifier
        file_name = name if name.lower().endswith('.dfpkl') or \
            name.lower().endswith('.pkl') else '{}.dfpkl'.format(name)
        folder = folder if folder is not None else folders.default_simulation_folder
        df_file = os.path.join(folder, file_name)
        # write the Model dictionary into a file
        with open(df_file, 'wb') as fp:
            pickle.dump(df_dict, fp)
        return df_file

    @property
    def to(self):
        """Model writer object.

        Use this method to access Writer class to write the model in other formats.
        """
        return writer

    @staticmethod
    def model_dict_room_2d_subset(model_dict, room_2d_ids):
        """Get a dragonfly Model dictionary that has been filtered for a Room2D subset.

        This is useful when you are only interested in visualizing or exporting a
        subset of Room2Ds to a file and so it is not desirable to serialize the
        entire Dragonfly Model.

        Args:
            model_dict: A dictionary of a Dragonfly Model.
            room_2d_ids: An optional list of the identifiers for the Room2Ds
                to be included in the output dictionary.

        Returns:
            A copy of the input Dragonfly Model dictionary, which contains only
            the Room2Ds listed in the room_2d_ids. All ContextShade and 3D Honeybee
            Rooms are removed but slanted Roof geometries are included if they are
            relevant to the Room2Ds.
        """
        return Model.model_dict_subset(model_dict, room_2d_ids)

    @staticmethod
    def model_dict_subset(
            model_dict, room_2d_ids=None, room_3d_ids=None, shade_ids=None):
        """Get a dragonfly Model dictionary that has been filtered for certain objects.

        This is useful when you are only interested in visualizing or exporting a
        subset of objects to a file and so it is not desirable to serialize the
        entire Dragonfly Model.

        Args:
            model_dict: A dictionary of a Dragonfly Model.
            room_2d_ids: An optional list of the identifiers for the Room2Ds
                to be included in the output dictionary. If None, no Room2D
                dictionaries will be in the result. (Default: None).
            room_3d_ids: An optional list of the identifiers for the 3D Rooms
                to be included in the output dictionary. If None, no 3D Room
                dictionaries will be in the result. (Default: None).
            shade_ids: An optional list of the identifiers for the ContextShades
                to be included in the output dictionary. If None, no ContextShade
                dictionaries will be in the result. (Default: None).

        Returns:
            A copy of the input Dragonfly Model dictionary, which contains only
            the Room2Ds listed in the room_2d_ids, the 3D Rooms listed in the
            room_3d_ids, and ContextShades in the shade_ids. Slanted Roof geometries
            are included if they are relevant to the Room2Ds.
        """
        # build a copy of the model_dict with geometry excluded
        ex_keys = ('buildings', 'context_shades')
        filtered_model = {key: v for key, v in model_dict.items() if key not in ex_keys}
        r3_ids = None
        if room_3d_ids is not None and len(room_3d_ids) != 0:
            r3_ids = set(room_3d_ids)
        # loop through the Buildings and grab the relevant Rooms
        if room_2d_ids is not None and len(room_2d_ids) != 0:
            room_ids = set(room_2d_ids)
            if 'buildings' in model_dict and model_dict['buildings'] is not None:
                new_bldgs = []
                for b_dict in model_dict['buildings']:
                    r_2ds_found = False
                    if 'unique_stories' in b_dict and \
                            b_dict['unique_stories'] is not None:
                        new_stories = []
                        for s_dict in b_dict['unique_stories']:
                            r_dicts = [r for r in s_dict['room_2ds']
                                       if r['identifier'] in room_ids]
                            if len(r_dicts) != 0:
                                new_story = s_dict.copy()
                                new_story['room_2ds'] = r_dicts
                                new_stories.append(new_story)
                        if len(new_stories) != 0:
                            new_bldg = b_dict.copy()
                            new_bldg['unique_stories'] = new_stories
                            new_bldgs.append(new_bldg)
                            r_2ds_found = True
                    if r3_ids is not None:
                        if 'room_3ds' in b_dict and b_dict['room_3ds'] is not None:
                            new_room_3ds = []
                            for r3_dict in b_dict['room_3ds']:
                                if r3_dict['identifier'] in r3_ids:
                                    new_room_3ds.append(r3_dict)
                            if len(new_room_3ds) != 0:
                                if r_2ds_found:
                                    new_bldg = new_bldgs[-1]
                                    new_bldg['room_3ds'] = new_room_3ds
                                else:
                                    new_bldg = b_dict.copy()
                                    new_bldg['room_3ds'] = new_room_3ds
                                    new_bldgs.append(new_bldg)
                filtered_model['buildings'] = new_bldgs
        elif r3_ids is not None:  # only 3D Rooms to visualize
            if 'buildings' in model_dict and model_dict['buildings'] is not None:
                new_bldgs = []
                for b_dict in model_dict['buildings']:
                    if 'room_3ds' in b_dict and b_dict['room_3ds'] is not None:
                        new_room_3ds = []
                        for r3_dict in b_dict['room_3ds']:
                            if r3_dict['identifier'] in r3_ids:
                                new_room_3ds.append(r3_dict)
                        if len(new_room_3ds) != 0:
                            new_bldg = b_dict.copy()
                            new_bldg['room_3ds'] = new_room_3ds
                            new_bldgs.append(new_bldg)
                filtered_model['buildings'] = new_bldgs
        # loop through the ContextShades and grab the relevant objects
        if shade_ids is not None and len(shade_ids) != 0:
            cs_ids = set(shade_ids)
            if 'context_shades' in model_dict and \
                    model_dict['context_shades'] is not None:
                new_shades = []
                for cs_dict in model_dict['context_shades']:
                    if cs_dict['identifier'] in cs_ids:
                        new_shades.append(cs_dict)
                filtered_model['context_shades'] = new_shades
        return filtered_model

    @staticmethod
    def _solve_ceil_adj(rooms, story_rel_types, tolerance=0.01, angle_tolerance=1):
        """Solve Floor/Ceiling adjacencies between a list of rooms."""
        # intersect the Rooms with one another for matching adjacencies
        HBRoom.intersect_adjacency(rooms, tolerance, angle_tolerance)
        # solve all adjacencies between rooms
        relevant_types = (Floor, RoofCeiling)
        for i, room_1 in enumerate(rooms):
            try:
                for room_2 in rooms[i + 1:]:
                    if not Polyface3D.overlapping_bounding_boxes(
                            room_1.geometry, room_2.geometry, tolerance):
                        continue  # no overlap in bounding box; adjacency impossible
                    for face_1 in room_1._faces:
                        for face_2 in room_2._faces:
                            if isinstance(face_2.type, relevant_types):
                                if face_1.geometry.is_centered_adjacent(
                                        face_2.geometry, tolerance):
                                    face_1.set_adjacency(face_2)
                                    break
            except IndexError:
                pass  # we have reached the end of the list of zones
        # change any remaining Floor/Roof boundary conditions to be outdoors
        relevant_bcs = (Outdoors, Surface, Ground)
        for room in rooms:
            rel_types = story_rel_types[room.story]
            for face in room._faces:
                if isinstance(face.type, rel_types):
                    if not isinstance(face.boundary_condition, relevant_bcs):
                        face.boundary_condition = boundary_conditions.outdoors

    @staticmethod
    def _objects_from_geojson(bldgs_data, existing_to_context, scale_to_meters,
                              origin_lon_lat, convert_facs):
        """Get Dragonfly Building and ContextShade objects from a geoJSON dictionary.

        Args:
            bldgs_data: A list of geoJSON object dictionaries, including polygons
                to be turned into buildings and context.
            existing_to_context: Boolean to indicate whether polygons possessing
                a building_status of "Existing" under their properties should be
                imported as ContextShade instead of Building objects.
            scale_to_meters: Factor for converting the building heights to meters.
            origin_lon_lat: An array of two numbers in degrees for origin lat and lon.
            convert_facs: A tuple with two values used to translate between
            meters and longitude, latitude.
        """
        bldgs, contexts = [], []
        for i, bldg_data in enumerate(bldgs_data):
            # get footprints
            footprint = []
            geojson_coordinates = bldg_data['geometry']['coordinates']
            prop = bldg_data['properties']

            if bldg_data['geometry']['type'] == 'Polygon':
                face3d = Model._geojson_coordinates_to_face3d(
                    geojson_coordinates, origin_lon_lat, convert_facs)
                footprint.append(face3d)
            else:  # if MultiPolygon, account for multiple polygons
                for _geojson_coordinates in geojson_coordinates:
                    face3d = Model._geojson_coordinates_to_face3d(
                        _geojson_coordinates, origin_lon_lat, convert_facs)
                    footprint.append(face3d)

            # determine whether the footprint should be context or a building
            if existing_to_context and 'building_status' in prop \
                    and prop['building_status'] == 'Existing':
                ht = prop['maximum_roof_height'] * scale_to_meters \
                    if 'maximum_roof_height' in prop else 3.5
                extru_vec = Vector3D(0, 0, ht)
                geo = [Face3D.from_extrusion(seg, extru_vec) for face3d in footprint
                       for seg in face3d.boundary_segments]
                shd_id = 'Context_{}'.format(i) if 'id' not in prop else prop['id']
                contexts.append(ContextShade(shd_id, geo))
                continue

            # Define building heights from file or assign default single-storey building
            if 'maximum_roof_height' in prop and 'number_of_stories' in prop:
                story_height = (prop['maximum_roof_height'] * scale_to_meters) \
                    / prop['number_of_stories']
                story_heights = [story_height] * prop['number_of_stories']
            elif 'number_of_stories' in prop:
                story_heights = [3.5] * prop['number_of_stories']
            else:  # just import it as one story per building
                story_heights = [3.5]

            # make building object
            bldg_id = 'Building_{}'.format(i) if 'id' not in prop else prop['id']
            bldg = Building.from_footprint(bldg_id, footprint, story_heights)
            if 'name' in prop:
                bldg.display_name = prop['name']

            # assign windows to the buildings
            if 'window_to_wall_ratio' in prop:
                win_par = SimpleWindowRatio(prop['window_to_wall_ratio'])
                bldg.set_outdoor_window_parameters(win_par)

            # add any extension attributes and add the building to the list
            bldg.properties.apply_properties_from_geojson_dict(prop)
            bldgs.append(bldg)
        return bldgs, contexts

    @staticmethod
    def _face3d_to_geojson_coordinates(face3d, origin_lon_lat, convert_facs):
        """Convert a horizontal Face3D to geoJSON coordinates."""
        coords = [polygon_to_lon_lat(
            [(pt.x, pt.y) for pt in face3d.boundary], origin_lon_lat, convert_facs)]
        coords[0].append(coords[0][0])
        if face3d.has_holes:
            for hole in face3d.holes:
                hole_verts = polygon_to_lon_lat(
                    [(pt.x, pt.y) for pt in hole], origin_lon_lat, convert_facs)
                hole_verts.append(hole_verts[0])
                coords.append(hole_verts)
        return coords

    @staticmethod
    def _geojson_coordinates_to_face3d(geojson_coordinates, origin_lon_lat,
                                       convert_facs):
        """Convert geoJSON coordinates to a horizontal Face3D with zero height.

        Args:
            geojson_coordinates: The coordinates from the geojson file. For 'Polygon'
                geometries, this will be the list from the 'coordinates' key in the
                geojson file, for 'MultiPolygon' geometries, this will be each item
                in the list from the 'coordinates' key.
            origin_lon_lat: An array of two numbers in degrees representing the
                longitude and latitude of the scene origin in degrees.
            convert_facs: A tuple with two values used to translate between
                longitude, latitude and meters.

        Returns:
            A Face3D object in model space coordinates converted from the geojson
            coordinates. The height of the Face3D vertices will be 0.
        """
        holes = None
        coords = lon_lat_to_polygon(geojson_coordinates[0], origin_lon_lat, convert_facs)
        coords = [Point3D(pt2d[0], pt2d[1], 0) for pt2d in coords][:-1]

        # If there are more then 1 polygons, then the other polygons are holes.
        if len(geojson_coordinates) > 1:
            holes = []
            for hole_geojson_coordinates in geojson_coordinates[1:]:
                hole_coords = lon_lat_to_polygon(
                    hole_geojson_coordinates, origin_lon_lat, convert_facs)
                hole_coords = [Point3D(pt2d[0], pt2d[1], 0) for pt2d in hole_coords][:-1]
                holes.append(hole_coords)

        return Face3D(coords, plane=Plane(n=Vector3D(0, 0, 1)), holes=holes)

    @staticmethod
    def _bottom_left_coordinate_from_geojson(bldgs_data):
        """Calculate the bottom-left bounding box coordinate from geojson coordinates.

        Args:
            bldgs_data: a list of dictionaries containing geojson geometries that
                represent building footprints.

        Returns:
            The bottom-left most corner of the bounding box around the coordinates.
        """
        xs, ys = [], []
        for bldg in bldgs_data:
            bldg_coords = bldg['geometry']['coordinates']

            if bldg['geometry']['type'] == 'Polygon':
                for bldg_footprint in bldg_coords:
                    xs.extend([coords[0] for coords in bldg_footprint])
                    ys.extend([coords[1] for coords in bldg_footprint])
            else:
                for bldg_footprints in bldg_coords:
                    for bldg_footprint in bldg_footprints:
                        xs.extend([coords[0] for coords in bldg_footprint])
                        ys.extend([coords[1] for coords in bldg_footprint])

        return min(xs), min(ys)

    def __add__(self, other):
        new_model = self.duplicate()
        new_model.add_model(other)
        return new_model

    def __iadd__(self, other):
        self.add_model(other)
        return self

    def __copy__(self):
        new_model = Model(
            self.identifier,
            [bldg.duplicate() for bldg in self._buildings],
            [shade.duplicate() for shade in self._context_shades],
            self.units, self.tolerance, self.angle_tolerance)
        new_model._display_name = self.display_name
        new_model._user_data = None if self.user_data is None else self.user_data.copy()
        new_model._properties._duplicate_extension_attr(self._properties)
        return new_model

    def __repr__(self):
        return 'Dragonfly Model: %s' % self.display_name
