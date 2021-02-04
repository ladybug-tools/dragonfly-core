"""dragonfly translation commands."""
import click
import sys
import os
import logging
import json

from ladybug.futil import preparedir
from honeybee.config import folders as hb_folders
from dragonfly.model import Model

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
@click.option('--shade-dist', '-sd', help='An optional number to note the distance '
              'beyond which other buildings shade should not be exported into a Model. '
              'This number should be in meters regardless of the input model units. '
              'If None, all other buildings will be included as context shade in '
              'each and every Model. Set to 0 to exclude all neighboring buildings '
              'from the resulting models.', type=float, default=None, show_default=True)
@click.option('--folder', '-f', help='Folder on this computer, into which the HBJSON '
              'files will be written. If None, the files will be output '
              'to the honeybee default simulation folder and placed in a project '
              'folder with the same name as the model json.',
              default=None, show_default=True,
              type=click.Path(file_okay=False, dir_okay=True, resolve_path=True))
@click.option('--log-file', '-log', help='Optional log file to output a JSON array of '
              'dictionaries with information about each of the genrated HBJSONs, '
              'including their file paths. By default the list will be printed out to '
              'stdout', type=click.File('w'), default='-', show_default=True)
def model_to_honeybee(model_json, obj_per_model, multiplier, no_plenum, no_cap,
                      shade_dist, folder, log_file):
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
                hb_folders.default_simulation_folder, proj_name, 'Honeybee')
        preparedir(folder, remove_content=False)

        # re-serialize the Dragonfly Model
        with open(model_json) as json_file:
            data = json.load(json_file)
        model = Model.from_dict(data)
        model.convert_to_units('Meters')

        # convert Dragonfly Model to Honeybee
        add_plenum = not no_plenum
        cap = not no_cap
        hb_models = model.to_honeybee(
            obj_per_model, shade_dist, multiplier, add_plenum, cap)

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
