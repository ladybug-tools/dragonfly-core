"""dragonfly model creation commands."""
import click
import sys
import logging
import json

from ladybug_geometry.geometry2d.pointvector import Point2D
from ladybug.location import Location
from honeybee.units import UNITS_TOLERANCES
from honeybee.model import Model as HBModel
from dragonfly.windowparameter import SimpleWindowRatio
from dragonfly.model import Model

_logger = logging.getLogger(__name__)


@click.group(help='Commands for creating Dragonfly models.')
def create():
    pass


@create.command('merge-models')
@click.argument('base-model', type=click.Path(
    exists=True, file_okay=True, dir_okay=False, resolve_path=True))
@click.option(
    '--other-model', '-m', help='The other Model to be merged into the base model.',
    type=click.File('w'), multiple=True)
@click.option(
    '--output-file', '-f', help='Optional file to output the Model DFJSON string. '
    'By default it will be printed out to stdout',
    type=click.File('w'), default='-')
def merge_models_cli(base_model, other_model, output_file):
    """Create a Dragonfly Model by merging multiple models together.

    \b
    Args:
        base_model: Full path to a Dragonfly Model JSON or Pkl file that serves
            as the base into which the other model(s) will be merged. This model
            determines the units and tolerance of the output model.
    """
    try:
        merge_models(base_model, other_model, output_file)
    except Exception as e:
        _logger.exception('Model merging failed.\n{}'.format(e))
        sys.exit(1)
    else:
        sys.exit(0)


def merge_models(base_model, other_model=(), output_file=None):
    """Create a Dragonfly Model by merging multiple models together.

    Args:
        base_model: Full path to a Dragonfly Model JSON or Pkl file that serves
            as the base into which the other model(s) will be merged. This model
            determines the units and tolerance of the output model.
        other_model: A list of other Dragonfly Models to be merged into the base model.
        output_file: Optional file to output the Model DFJSON string. If None,
            the string will be returned from this method. (Default: None).
    """
    # serialize the Model and convert the units
    parsed_model = Model.from_file(base_model)
    other_models = [Model.from_file(m) for m in other_model]
    for o_model in other_models:
        parsed_model.add_model(o_model)

    # write the new model out to the file or stdout
    if output_file is None:
        return json.dumps(parsed_model.to_dict())
    output_file.write(json.dumps(parsed_model.to_dict()))


@create.command('from-honeybee')
@click.argument('base-model', type=click.Path(
    exists=True, file_okay=True, dir_okay=False, resolve_path=True))
@click.option(
    '--conversion-method', '-c', help='Text to indicate how the Honeybee Rooms '
    'should be converted to Dragonfly. Choose from: AllRoom2D, ExtrudedOnly, AllRoom3D. '
    'Note that the AllRoom2D option may result in some loss or simplification of '
    'the 3D Honeybee geometry but ensures that all of the Dragonfly features for '
    'editing the rooms can be used. The ExtrudedOnly method will convert only the '
    '3D Rooms that would have no loss or simplification of geometry when converted '
    'to Room2D. AllRoom3D keeps all detailed 3D geometry on the Building.room_3ds '
    'property, enabling you to convert the 3D Rooms to Room2D using the '
    'Building.convert_room_3ds_to_2d() method as you see fit.',
    type=str, default="ExtrudedOnly", show_default=True)
@click.option(
    '--other-model', '-m', help='Another Honeybee Model to be added as a separate '
    'Building in the resulting Dragonfly Model.',
    type=click.File('w'), multiple=True)
@click.option(
    '--output-file', '-f', help='Optional file to output the Model DFJSON string. '
    'By default it will be printed out to stdout',
    type=click.File('w'), default='-')
def from_honeybee_cli(base_model, conversion_method, other_model, output_file):
    """Create a Dragonfly Model from Honeybee Model(s).

    \b
    Args:
        base_model: Full path to a Honeybee Model JSON or Pkl file that serves
            as the base for the resulting Dragonfly Model. This model
            determines the units and tolerance of the output model.
    """
    try:
        from_honeybee(base_model, conversion_method, other_model, output_file)
    except Exception as e:
        _logger.exception('Model creation from honeybee failed.\n{}'.format(e))
        sys.exit(1)
    else:
        sys.exit(0)


def from_honeybee(base_model, conversion_method='ExtrudedOnly',
                  other_model=(), output_file=None):
    """Create a Dragonfly Model from Honeybee Model(s).

    Args:
        base_model: Full path to a Honeybee Model JSON or Pkl file that serves
            as the base for the resulting Dragonfly Model. This model
            determines the units and tolerance of the output model.
        conversion_method: Text to indicate how the Honeybee Rooms should be
            converted to Dragonfly. Choose from: AllRoom2D, ExtrudedOnly, AllRoom3D.
            Note that the AllRoom2D option may result in some loss or simplification
            of the 3D Honeybee geometry but ensures that all of the Dragonfly
            features for editing the rooms can be used. The ExtrudedOnly method
            will convert only the 3D Rooms that would have no loss or
            simplification of geometry when converted to Room2D. AllRoom3D
            keeps all detailed 3D geometry on the Building.room_3ds property,
            enabling you to convert the 3D Rooms to Room2D using the
            Building.convert_room_3ds_to_2d() method as you see fit.
        other_model: An optional list of other Honeybee Models to be added as
            a separate Building in the resulting Dragonfly Model.
        output_file: Optional file to output the Model DFJSON string. If None,
            the string will be returned from this method. (Default: None).
    """
    # serialize the input Model(s)
    hb_model = HBModel.from_file(base_model)
    other_models = [HBModel.from_file(m) for m in other_model]

    # convert the Honeybee Model(s) to Dragonfly
    df_model = Model.from_honeybee(hb_model, conversion_method)
    for o_hb_model in other_models:
        o_df_model = Model.from_honeybee(o_hb_model, conversion_method)
        df_model.add_model(o_df_model)

    # write the new model out to the file or stdout
    if output_file is None:
        return json.dumps(df_model.to_dict())
    output_file.write(json.dumps(df_model.to_dict()))


@create.command('from-geojson')
@click.argument('geojson', type=click.Path(
    exists=True, file_okay=True, dir_okay=False, resolve_path=True))
@click.option('--location', '-l', help='An optional latitude and longitude, formatted '
              'as two floats separated by a comma, (eg. "42.3601,-71.0589"), defining '
              'the origin of the geojson file. If nothing is passed, the origin is '
              'autocalculated as the bottom-left corner of the bounding box of all '
              'building footprints in the geojson file.', type=str, default=None)
@click.option('--point', '-p', help='An optional X and Y coordinate, formatted '
              'as two floats separated by a comma, (eg. "200,200"), defining '
              'the origin of the geojson file in the space of the dragonfly model. The '
              'coordinates of this point are expected to be in the expected units '
              'of this Model.', type=str, default='0,0', show_default=True)
@click.option('--window-ratio', '-wr', help='A number between 0 and 1 (but not equal '
              'to 1) for the ratio between aperture area and wall area to be applied to '
              'all walls of all buildings. If specified, this will override the '
              'window_ratio key in the geojson.', type=float, default=None)
@click.option('--buildings-only/--all-to-buildings', ' /-all', help='Flag to indicate '
              'if all geometries in the geojson file should be considered buildings. '
              'If buildings-only, this method will only generate footprints from '
              'geometries that are defined as a "Building" in the type field of its '
              'corresponding properties.', default=True, show_default=True)
@click.option('--no-context/--existing-to-context', ' /-c', help='Flag to indicate '
              'whether polygons possessing a building_status of "Existing" under their '
              'properties should be imported as ContextShade instead of Building '
              'objects.', default=True, show_default=True)
@click.option('--separate-top-bottom/--no-separation', ' /-ns', help='Flag to indicate '
              'whether top/bottom stories of the buildings should not be separated in '
              'order to account for different boundary conditions of the roof and '
              'ground floor.', default=True, show_default=True)
@click.option('--units', '-u', help='Text for the units system in which the '
              'resulting model geometry should be. Must be (Meters, Millimeters, '
              'Feet, Inches, Centimeters).',
              type=str, default='Meters', show_default=True)
@click.option('--tolerance', '-t', help='The maximum difference between x, y, and z '
              'values at which vertices are considered equivalent.',
              type=float, default=None)
@click.option('--output-file', '-f', help='Optional file to output the Model JSON '
              'string. By default it will be printed out to stdout',
              type=click.File('w'), default='-')
def from_geojson_cli(
        geojson, location, point, window_ratio, buildings_only,
        no_context, separate_top_bottom, units, tolerance, output_file):
    """Create a Dragonfly model from a geojson file with building footprints.

    \b
    Args:
        geojson: Full path to a geoJSON file with building footprints as Polygons
            or MultiPolygons.
    """
    try:
        all_to_buildings = not buildings_only
        existing_to_context = not no_context
        no_separation = not separate_top_bottom
        from_geojson(
            geojson, location, point, window_ratio, all_to_buildings,
            existing_to_context, no_separation, units, tolerance, output_file)
    except Exception as e:
        _logger.exception('Model creation from geoJSON failed.\n{}'.format(e))
        sys.exit(1)
    else:
        sys.exit(0)


def from_geojson(
        geojson, location=None, point=None, window_ratio=None,
        all_to_buildings=False, existing_to_context=False, no_separation=False,
        units='Meters', tolerance=None, output_file=None,
        buildings_only=True, no_context=True, separate_top_bottom=True):
    """Create a Dragonfly model from a geojson file with building footprints.

    Args:
        geojson: Full path to a geoJSON file with building footprints as Polygons
            or MultiPolygons.
        location: An optional latitude and longitude, formatted as two floats
            separated by a comma, (eg. "42.3601,-71.0589"), defining the origin
            of the geojson file. If None, the origin is autocalculated as the
            bottom-left corner of the bounding box of all building footprints
            in the geojson file.
        point: An optional X and Y coordinate, formatted as two floats separated
            by a comma, (eg. "200,200"), defining the origin of the geojson file
            in the space of the dragonfly model. The coordinates of this point
            are expected to be in the expected units of this Model.
        window_ratio: A number between 0 and 1 (but not equal to 1) for the
            ratio between aperture area and wall area to be applied to all walls
            of all buildings. If specified, this will override the window_ratio
            key in the geojson.
        all_to_buildings: Boolean to indicate if all geometries in the geojson
            file should be considered buildings. If buildings-only, this method
            will only generate footprints from geometries that are defined as
            a "Building" in the type field of its corresponding properties.
        existing_to_context: Boolean to indicate whether polygons possessing a
            building_status of "Existing" under their properties should be
            imported as ContextShade instead of Building objects.
        no_separation: Boolean to indicate whether polygons possessing a
            building_status of "Existing" under their properties should be
            imported as ContextShade instead of Building objects.
        units: Text for the units system in which the resulting model geometry
            should be. Must be (Meters, Millimeters, Feet, Inches, Centimeters).
        tolerance: The maximum difference between x, y, and z values at which
            vertices are considered equivalent.
        output_file: Optional file to output the Model JSON string. If None,
            The string will be returned from this method.
    """
    # parse the location and point if they are specified
    if location is not None:
        lat, lon = [float(num) for num in location.split(',')]
        location = Location(longitude=lat, latitude=lon)
    if point is None:
        point = Point2D(0, 0)
    else:
        point = Point2D(*[float(num) for num in point.split(',')])

    # create the model object
    tolerance = tolerance if tolerance is not None else UNITS_TOLERANCES[units]
    model, _ = Model.from_geojson(
        geojson, location, point, all_to_buildings, existing_to_context,
        units=units, tolerance=tolerance)

    # apply windows if the window ratio and top/bottom separation if specified
    if window_ratio is not None:
        model.set_outdoor_window_parameters(SimpleWindowRatio(window_ratio))
    if not no_separation:
        model.separate_top_bottom_floors()

    # write the model out to the file or stdout
    if output_file is None:
        return json.dumps(model.to_dict())
    output_file.write(json.dumps(model.to_dict()))
