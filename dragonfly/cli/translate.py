"""dragonfly translation commands."""
import click
import sys
import os
import logging
import json

from ladybug_geometry.geometry2d.pointvector import Point2D
from ladybug.location import Location
from ladybug.futil import preparedir
from honeybee.units import parse_distance_string, UNITS_TOLERANCES
from honeybee.config import folders as hb_folders

from dragonfly.model import Model
from dragonfly.windowparameter import SimpleWindowRatio

_logger = logging.getLogger(__name__)


@click.group(help='Commands for translating Dragonfly JSON files to honeybee.')
def translate():
    pass


@translate.command('model-to-honeybee')
@click.argument('model-json', type=click.Path(
    exists=True, file_okay=True, dir_okay=False, resolve_path=True))
@click.option('--obj-per-model', '-o', help='Text to describe how the input Model '
              'should be divided across the output Models. Choose from: District, '
              'Building, Story.', type=str, default="Building", show_default=True)
@click.option('--multiplier/--full-geometry', ' /-fg', help='Flag to note if the '
              'multipliers on each Building story should be passed along to the '
              'generated Honeybee Room objects or if full geometry objects should be '
              'written for each story in the building.', default=True, show_default=True)
@click.option('--no-plenum/--plenum', ' /-p', help='Flag to indicate whether '
              'ceiling/floor plenums should be auto-generated for the Rooms.',
              default=True, show_default=True)
@click.option('--no-cap/--cap', ' /-c', help='Flag to indicate whether context shade '
              'buildings should be capped with a top face.',
              default=True, show_default=True)
@click.option('--no-ceil-adjacency/--ceil-adjacency', ' /-a', help='Flag to indicate '
              'whether adjacencies should be solved between interior stories when '
              'Room2Ds perfectly match one another in their floor plate. This ensures '
              'that Surface boundary conditions are used instead of Adiabatic ones. '
              'Note that this input has no effect when the object-per-model is Story.',
              default=True, show_default=True)
@click.option('--shade-dist', '-sd', help='An optional number to note the distance '
              'beyond which other buildings shade should not be exported into a Model. '
              'This can include the units of the distance (eg. 100ft) or, if no units '
              'are  provided, the value will be interpreted in the dragonfly model '
              'units. If None, all other buildings will be included as context shade in '
              'each and every Model. Set to 0 to exclude all neighboring buildings '
              'from the resulting models.', type=str, default=None, show_default=True)
@click.option('--enforce-adj-check/--bypass-adj-check', ' /-bc', help='Flag to note '
              'whether an exception should be raised if an adjacency between two '
              'Room2Ds is invalid or if the check should be bypassed and the invalid '
              'Surface boundary condition should be replaced with an Outdoor boundary '
              'condition. If bypass is selected, any Walls containing WindowParameters '
              'and an illegal boundary condition will also be replaced with an '
              'Outdoor boundary condition.', default=True, show_default=True)
@click.option('--folder', '-f', help='Folder on this computer, into which the HBJSON '
              'files will be written. If None, the files will be output '
              'to the honeybee default simulation folder and placed in a project '
              'folder with the same name as the model json.',
              default=None, show_default=True,
              type=click.Path(file_okay=False, dir_okay=True, resolve_path=True))
@click.option('--log-file', '-log', help='Optional log file to output a JSON array of '
              'dictionaries with information about each of the generated HBJSONs, '
              'including their file paths. By default the list will be printed out to '
              'stdout', type=click.File('w'), default='-', show_default=True)
def model_to_honeybee(model_json, obj_per_model, multiplier, no_plenum, no_cap,
                      no_ceil_adjacency, shade_dist, enforce_adj_check,
                      folder, log_file):
    """Translate a Dragonfly Model JSON file into several Honeybee Models.

    \b
    Args:
        model_json: Path to a Dragonfly Model JSON file.
    """
    try:
        # set the default folder to the default if it's not specified
        if folder is None:
            proj_name = \
                os.path.basename(model_json).replace('.json', '').replace('.dfjson', '')
            folder = os.path.join(
                hb_folders.default_simulation_folder, proj_name, 'honeybee')
        preparedir(folder, remove_content=False)

        # re-serialize the Dragonfly Model and convert Dragonfly Model to Honeybee
        model = Model.from_file(model_json)
        if shade_dist is not None:
            shade_dist = parse_distance_string(shade_dist, model.units)
        add_plenum = not no_plenum
        cap = not no_cap
        ceil_adjacency = not no_ceil_adjacency
        hb_models = model.to_honeybee(
            obj_per_model, shade_dist, multiplier, add_plenum, cap, ceil_adjacency,
            enforce_adj=enforce_adj_check)

        # write out the honeybee JSONs and collect the info about them
        hb_jsons = []
        for hb_model in hb_models:
            model_dict = hb_model.to_dict(triangulate_sub_faces=True)
            file_name = '{}.hbjson'.format(hb_model.identifier)
            file_path = os.path.join(folder, file_name)
            with open(file_path, 'w') as fp:
                json.dump(model_dict, fp)
            hb_info = {
                'id': hb_model.identifier,
                'path': file_name,
                'full_path': os.path.abspath(file_path)
            }
            hb_jsons.append(hb_info)
        log_file.write(json.dumps(hb_jsons, indent=4))
    except Exception as e:
        _logger.exception('Model translation failed.\n{}'.format(e))
        sys.exit(1)
    else:
        sys.exit(0)


@translate.command('model-from-geojson')
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
              'window_ratio key in the geojson', type=float, default=None)
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
@click.option('--units', '-u', help=' Text for the units system in which the model '
              'geometry exists. Must be (Meters, Millimeters, Feet, Inches, '
              'Centimeters).', type=str, default='Meters', show_default=True)
@click.option('--tolerance', '-t', help='The maximum difference between x, y, and z '
              'values at which vertices are considered equivalent.',
              type=float, default=None)
@click.option('--output-file', '-f', help='Optional file to output the Model JSON '
              'string. By default it will be printed out to stdout',
              type=click.File('w'), default='-')
def model_from_geojson(geojson, location, point, window_ratio, buildings_only,
                       no_context, separate_top_bottom, units, tolerance, output_file):
    """Create a Dragonfly model from a geojson file with building footprints.

    \b
    Args:
        geojson: Full path to a geoJSON file with building footprints as Polygons
            or MultiPolygons.
    """
    try:
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
        all_polygons_to_buildings = not buildings_only
        existing_to_context = not no_context
        model, _ = Model.from_geojson(
            geojson, location, point, all_polygons_to_buildings, existing_to_context,
            units=units, tolerance=tolerance)

        # apply windows if the window ratio and top/bottom separation if specified
        if window_ratio is not None:
            model.set_outdoor_window_parameters(SimpleWindowRatio(window_ratio))
        if separate_top_bottom:
            model.separate_top_bottom_floors()

        # write the model out to the file or stdout
        output_file.write(json.dumps(model.to_dict()))
    except Exception as e:
        _logger.exception('Model creation from geoJSON failed.\n{}'.format(e))
        sys.exit(1)
    else:
        sys.exit(0)
