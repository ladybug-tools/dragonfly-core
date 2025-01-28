"""dragonfly translation commands."""
import click
import sys
import os
import logging
import json

from ladybug.futil import preparedir
from ladybug.commandutil import process_content_to_output
from honeybee.units import parse_distance_string
from honeybee.config import folders as hb_folders
from honeybee.model import Model as HBModel

from dragonfly.model import Model

_logger = logging.getLogger(__name__)


@click.group(help='Commands for translating Dragonfly JSON files to honeybee.')
def translate():
    pass


@translate.command('model-to-honeybee')
@click.argument('model-file', type=click.Path(
    exists=True, file_okay=True, dir_okay=False, resolve_path=True))
@click.option('--obj-per-model', '-o', help='Text to describe how the input Model '
              'should be divided across the output Models. Choose from: District, '
              'Building, Story.', type=str, default="Building", show_default=True)
@click.option('--multiplier/--full-geometry', ' /-fg', help='Flag to note if the '
              'multipliers on each Building story should be passed along to the '
              'generated Honeybee Room objects or if full geometry objects should be '
              'written for each story in the building.', default=True, show_default=True)
@click.option('--plenum/--no-plenum', '-p/-np', help='Flag to indicate whether '
              'ceiling/floor plenum depths assigned to Room2Ds should generate '
              'distinct 3D Rooms in the translation.', default=True, show_default=True)
@click.option('--no-cap/--cap', ' /-c', help='Flag to indicate whether context shade '
              'buildings should be capped with a top face.',
              default=True, show_default=True)
@click.option('--no-ceil-adjacency/--ceil-adjacency', ' /-a', help='Flag to indicate '
              'whether adjacencies should be solved between interior stories when '
              'Room2D floor and ceiling geometries are coplanar. This ensures '
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
@click.option('--enforce-solid/--permit-non-solid', ' /-pns', help='Flag to note '
              'whether rooms should be translated as solid extrusions whenever '
              'translating them with custom roof geometry produces a non-solid '
              'result or the non-solid room geometry should be allowed to remain '
              'in the result. The latter is useful for understanding why a '
              'particular roof geometry has produced a non-solid result.',
              default=True, show_default=True)
@click.option('--folder', '-f', help='Folder on this computer, into which the HBJSON '
              'files will be written. By default, the files will be output '
              'to the honeybee default simulation folder and placed in a project '
              'folder with the same name as the model json.',
              default=None, show_default=True,
              type=click.Path(file_okay=False, dir_okay=True, resolve_path=True))
@click.option('--log-file', '-log', help='Optional log file to output a JSON array of '
              'dictionaries with information about each of the generated HBJSONs, '
              'including their file paths. By default the list will be printed out to '
              'stdout', type=click.File('w'), default='-', show_default=True)
def model_to_honeybee_cli(
        model_file, obj_per_model, multiplier, plenum, no_cap,
        no_ceil_adjacency, shade_dist, enforce_adj_check, enforce_solid,
        folder, log_file):
    """Translate a Dragonfly Model file into one or more Honeybee Models.

    \b
    Args:
        model_file: Full path to a Dragonfly Model JSON or Pkl file.
    """
    try:
        full_geometry = not multiplier
        no_plenum = not plenum
        cap = not no_cap
        ceil_adjacency = not no_ceil_adjacency
        bypass_adj_check = not enforce_adj_check
        permit_non_solid = not enforce_solid
        model_to_honeybee(
            model_file, obj_per_model, full_geometry, no_plenum, cap, ceil_adjacency,
            shade_dist, bypass_adj_check, permit_non_solid, folder, log_file)
    except Exception as e:
        _logger.exception('Model translation failed.\n{}'.format(e))
        sys.exit(1)
    else:
        sys.exit(0)


def model_to_honeybee(
        model_file, obj_per_model='Building', full_geometry=False, no_plenum=False,
        cap=False, ceil_adjacency=False, shade_dist=None,
        bypass_adj_check=False, permit_non_solid=False,
        folder=None, log_file=None,
        multiplier=True, plenum=True, no_cap=True, no_ceil_adjacency=True,
        enforce_adj_check=True, enforce_solid=True):
    """Translate a Dragonfly Model file into one or more Honeybee Models.

    Args:
        model_file: Full path to a Dragonfly Model JSON or Pkl file.
        full_geometry: Boolean to note if the multipliers on each Story should
            be passed along to the generated Honeybee Room objects or if full
            geometry objects should be written for each story in the
            building. (Default: False).
        no_plenum: Boolean to indicate whether ceiling/floor plenum depths
            assigned to Room2Ds should generate distinct 3D Rooms in the
            translation. (Default: False).
        cap: Boolean to indicate whether context shade buildings should be
            capped with a top face. (Default: False).
        ceil_adjacency: Boolean to indicate whether adjacencies should be solved
            between interior stories when Room2D floor and ceiling geometries
            are coplanar. This ensures that Surface boundary conditions are used
            instead of Adiabatic ones. (Default: False).
        shade_dist: An optional number to note the distance beyond which other
            buildings shade should not be exported into a Model. This can include
            the units of the distance (eg. 100ft) or, if no units are provided,
            the value will be interpreted in the dragonfly model units. If None,
            all other buildings will be included as context shade in each and
            every Model. Set to 0 to exclude all neighboring buildings from the
            resulting models. (Default: None).
        bypass_adj_check: Boolean to note whether an exception should be raised
            if an adjacency between two Room2Ds is invalid or if the check
            should be bypassed and the invalid Surface boundary condition should
            be replaced with an Outdoor boundary condition. If bypass is selected,
            any Walls containing WindowParameters and an illegal boundary
            condition will also be replaced with an Outdoor boundary
            condition. (Default: False).
        permit_non_solid: Boolean to note whether rooms should be translated as
            solid extrusions whenever translating them with custom roof geometry
            produces a non-solid result or the non-solid room geometry should
            be allowed to remain in the result. The latter is useful for
            understanding why a particular roof geometry has produced a
            non-solid result. (Default: False).
        folder: Folder on this computer, into which the HBJSON files will be written.
            If None, the files will be output to the honeybee default simulation
            folder and placed in a project folder with the same name as the
            model json. (Default: None).
        log_file: Optional log file to output a JSON array of dictionaries with
            information about each of the generated HBJSONs, including their
            file paths. If None, the string will be returned from this method.
    """
    # set the default folder to the default if it's not specified
    if folder is None:
        proj_name = \
            os.path.basename(model_file).replace('.json', '').replace('.dfjson', '')
        folder = os.path.join(
            hb_folders.default_simulation_folder, proj_name, 'honeybee')
    preparedir(folder, remove_content=False)

    # re-serialize the Dragonfly Model and convert Dragonfly Model to Honeybee
    model = Model.from_file(model_file)
    if shade_dist is not None:
        shade_dist = parse_distance_string(shade_dist, model.units)
    multiplier = not full_geometry
    enforce_adj_check = not bypass_adj_check
    enforce_solid = not permit_non_solid
    hb_models = model.to_honeybee(
        obj_per_model, shade_dist, multiplier, no_plenum, cap, ceil_adjacency,
        enforce_adj=enforce_adj_check, enforce_solid=enforce_solid)

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
    if log_file is None:
        return json.dumps(hb_jsons, indent=4)
    log_file.write(json.dumps(hb_jsons, indent=4))


@translate.command('model-to-honeybee-file')
@click.argument('model-file', type=click.Path(
    exists=True, file_okay=True, dir_okay=False, resolve_path=True))
@click.option(
    '--multiplier/--full-geometry', ' /-fg', help='Flag to note if the '
    'multipliers on each Building story should be passed along to the '
    'generated Honeybee Room objects or if full geometry objects should be '
    'written for each story in the building.', default=True, show_default=True)
@click.option(
    '--plenum/--no-plenum', '-p/-np', help='Flag to indicate whether '
    'ceiling/floor plenum depths assigned to Room2Ds should generate '
    'distinct 3D Rooms in the translation.', default=True, show_default=True)
@click.option(
    '--no-ceil-adjacency/--ceil-adjacency', ' /-a', help='Flag to indicate '
    'whether adjacencies should be solved between interior stories when '
    'Room2D floor and ceiling geometries are coplanar. This ensures '
    'that Surface boundary conditions are used instead of Adiabatic ones.',
    default=True, show_default=True)
@click.option(
    '--enforce-adj-check/--bypass-adj-check', ' /-bc', help='Flag to note '
    'whether an exception should be raised if an adjacency between two '
    'Room2Ds is invalid or if the check should be bypassed and the invalid '
    'Surface boundary condition should be replaced with an Outdoor boundary '
    'condition. If bypass is selected, any Walls containing WindowParameters '
    'and an illegal boundary condition will also be replaced with an '
    'Outdoor boundary condition.', default=True, show_default=True)
@click.option(
    '--enforce-solid/--permit-non-solid', ' /-pns', help='Flag to note '
    'whether rooms should be translated as solid extrusions whenever '
    'translating them with custom roof geometry produces a non-solid '
    'result or the non-solid room geometry should be allowed to remain '
    'in the result. The latter is useful for understanding why a '
    'particular roof geometry has produced a non-solid result.',
    default=True, show_default=True)
@click.option(
    '--output-file', '-f', help='Optional file to output the Honeybee Model JSON string'
    ' with solved adjacency. By default it will be printed out to stdout',
    type=click.File('w'), default='-')
def model_to_honeybee_file_cli(
        model_file, multiplier, plenum, no_ceil_adjacency,
        enforce_adj_check, enforce_solid, output_file):
    """Translate a Dragonfly Model into a single Honeybee Model.

    \b
    Args:
        model_file: Full path to a Dragonfly Model JSON or Pkl file.
    """
    try:
        full_geometry = not multiplier
        no_plenum = not plenum
        ceil_adjacency = not no_ceil_adjacency
        bypass_adj_check = not enforce_adj_check
        permit_non_solid = not enforce_solid
        model_to_honeybee_file(
            model_file, full_geometry, no_plenum, ceil_adjacency,
            bypass_adj_check, permit_non_solid, output_file)
    except Exception as e:
        _logger.exception('Model translation failed.\n{}'.format(e))
        sys.exit(1)
    else:
        sys.exit(0)


def model_to_honeybee_file(
        model_file, full_geometry=False, no_plenum=False, ceil_adjacency=False,
        bypass_adj_check=False, permit_non_solid=False, output_file=None,
        multiplier=True, plenum=True, no_ceil_adjacency=True,
        enforce_adj_check=True, enforce_solid=True):
    """Translate a Dragonfly Model into a single Honeybee Model.

    Args:
        model_file: Full path to a Dragonfly Model JSON or Pkl file.
        full_geometry: Boolean to note if the multipliers on each Story should
            be passed along to the generated Honeybee Room objects or if full
            geometry objects should be written for each story in the
            building. (Default: False).
        no_plenum: Boolean to indicate whether ceiling/floor plenum depths
            assigned to Room2Ds should generate distinct 3D Rooms in the
            translation. (Default: False).
        ceil_adjacency: Boolean to indicate whether adjacencies should be solved
            between interior stories when Room2D floor and ceiling geometries
            are coplanar. This ensures that Surface boundary conditions are used
            instead of Adiabatic ones. (Default: False).
        bypass_adj_check: Boolean to note whether an exception should be raised
            if an adjacency between two Room2Ds is invalid or if the check
            should be bypassed and the invalid Surface boundary condition should
            be replaced with an Outdoor boundary condition. If bypass is selected,
            any Walls containing WindowParameters and an illegal boundary
            condition will also be replaced with an Outdoor boundary
            condition. (Default: False).
        permit_non_solid: Boolean to note whether rooms should be translated as
            solid extrusions whenever translating them with custom roof geometry
            produces a non-solid result or the non-solid room geometry should
            be allowed to remain in the result. The latter is useful for
            understanding why a particular roof geometry has produced a
            non-solid result. (Default: False).
        output_file: Optional file to output the string of the HBJSON. If None,
            the string will simply be returned from this method.
    """
    # serialize the Model
    parsed_model = Model.from_file(model_file)
    # convert the dragonfly Model to Honeybee
    multiplier = not full_geometry
    enforce_adj_check = not bypass_adj_check
    enforce_solid = not permit_non_solid
    hb_model = parsed_model.to_honeybee(
        object_per_model='District', use_multiplier=multiplier,
        exclude_plenums=no_plenum, solve_ceiling_adjacencies=ceil_adjacency,
        enforce_adj=enforce_adj_check, enforce_solid=enforce_solid)[0]
    # write the new model out to the file or stdout
    model_str = json.dumps(hb_model.to_dict())
    return process_content_to_output(model_str, output_file)


@translate.command('merge-models-to-honeybee')
@click.argument('base-model', type=click.Path(
    exists=True, file_okay=True, dir_okay=False, resolve_path=True))
@click.option(
    '--dragonfly-model', '-d', help='Other Dragonfly Model to be merged into '
    'the base model.',
    type=click.Path(exists=True, file_okay=True, dir_okay=False, resolve_path=True),
    multiple=True)
@click.option(
    '--honeybee-model', '-h', help='Other Honeybee Model to be merged into '
    'the base model.',
    type=click.Path(exists=True, file_okay=True, dir_okay=False, resolve_path=True),
    multiple=True)
@click.option(
    '--multiplier/--full-geometry', ' /-fg', help='Flag to note if the '
    'multipliers on each Building story should be passed along to the '
    'generated Honeybee Room objects or if full geometry objects should be '
    'written for each story in the building.', default=True, show_default=True)
@click.option(
    '--plenum/--no-plenum', '-p/-np', help='Flag to indicate whether '
    'ceiling/floor plenum depths assigned to Room2Ds should generate '
    'distinct 3D Rooms in the translation.', default=True, show_default=True)
@click.option(
    '--default-adjacency/--solve-adjacency', ' /-sa', help='Flag to indicate '
    'whether all boundary conditions of the original models should be left as they '
    'are or whether adjacencies should be solved across the final model when '
    'everything is merged together. In this case, solving adjacencies will involve '
    'merging all coplanar faces across the Dragonfly/Honeybee Models, intersecting '
    'coplanar Faces to get matching areas, and setting Surface boundary conditions '
    'for all matching coplanar faces.', default=True, show_default=True)
@click.option(
    '--enforce-adj-check/--bypass-adj-check', ' /-bc', help='Flag to note '
    'whether an exception should be raised if an adjacency between two '
    'Room2Ds is invalid or if the check should be bypassed and the invalid '
    'Surface boundary condition should be replaced with an Outdoor boundary '
    'condition. If bypass is selected, any Walls containing WindowParameters '
    'and an illegal boundary condition will also be replaced with an '
    'Outdoor boundary condition.', default=True, show_default=True)
@click.option(
    '--enforce-solid/--permit-non-solid', ' /-pns', help='Flag to note '
    'whether rooms should be translated as solid extrusions whenever '
    'translating them with custom roof geometry produces a non-solid '
    'result or the non-solid room geometry should be allowed to remain '
    'in the result. The latter is useful for understanding why a '
    'particular roof geometry has produced a non-solid result.',
    default=True, show_default=True)
@click.option(
    '--output-file', '-f', help='Optional file to output the Honeybee Model JSON string'
    ' with solved adjacency. By default it will be printed out to stdout',
    type=click.File('w'), default='-')
def merge_models_to_honeybee_cli(
        base_model, dragonfly_model, honeybee_model, multiplier, plenum,
        default_adjacency, enforce_adj_check, enforce_solid, output_file):
    """Merge multiple Dragonfly and/or Honeybee Models into a single Honeybee Model.

    \b
    Args:
        base_model: Full path to a Dragonfly Model JSON or Pkl file that serves
            as the base into which the other model(s) will be merged.
    """
    try:
        full_geometry = not multiplier
        no_plenum = not plenum
        solve_adjacency = not default_adjacency
        bypass_adj_check = not enforce_adj_check
        permit_non_solid = not enforce_solid
        merge_models_to_honeybee(
            base_model, dragonfly_model, honeybee_model,
            full_geometry, no_plenum, solve_adjacency,
            bypass_adj_check, permit_non_solid, output_file)
    except Exception as e:
        _logger.exception('Model merging failed.\n{}'.format(e))
        sys.exit(1)
    else:
        sys.exit(0)


def merge_models_to_honeybee(
        base_model, dragonfly_model=(), honeybee_model=(),
        full_geometry=False, no_plenum=False, solve_adjacency=False,
        bypass_adj_check=False, permit_non_solid=False, output_file=None,
        multiplier=True, plenum=True, default_adjacency=True,
        enforce_adj_check=True, enforce_solid=True):
    """Merge multiple Dragonfly and/or Honeybee Models into a single Honeybee Model.

    Args:
        base_model: Full path to a Dragonfly Model JSON or Pkl file that serves
            as the base into which the other model(s) will be merged.
        dragonfly_model: List of other Dragonfly Models to be merged into the
            base model.
        honeybee_model: List of other Honeybee Models to be merged into the
            base model.
        full_geometry: Boolean to note if the multipliers on each Story should
            be passed along to the generated Honeybee Room objects or if full
            geometry objects should be written for each story in the
            building. (Default: False).
        no_plenum: Boolean to indicate whether ceiling/floor plenum depths
            assigned to Room2Ds should generate distinct 3D Rooms in the
            translation. (Default: False).
        solve_adjacency: Boolean to indicate whether all boundary conditions of
            the original models should be left as they are or whether adjacencies
            should be solved across the final model when everything is merged
            together. In this case, solving adjacencies will involve merging all
            coplanar faces across the Dragonfly/Honeybee Models, intersecting
            coplanar Faces to get matching areas, and setting Surface boundary
            conditions for all matching coplanar faces. (Default: False).
        bypass_adj_check: Boolean to note whether an exception should be raised
            if an adjacency between two Room2Ds is invalid or if the check
            should be bypassed and the invalid Surface boundary condition should
            be replaced with an Outdoor boundary condition. If bypass is selected,
            any Walls containing WindowParameters and an illegal boundary
            condition will also be replaced with an Outdoor boundary
            condition. (Default: False).
        permit_non_solid: Boolean to note whether rooms should be translated as
            solid extrusions whenever translating them with custom roof geometry
            produces a non-solid result or the non-solid room geometry should
            be allowed to remain in the result. The latter is useful for
            understanding why a particular roof geometry has produced a
            non-solid result. (Default: False).
        output_file: Optional file to output the string of the HBJSON. If None,
            the string will simply be returned from this method.
    """
    # serialize the Model and convert the units
    parsed_model = Model.from_file(base_model)
    other_df_models = [Model.from_file(m) for m in dragonfly_model]
    for o_model in other_df_models:
        parsed_model.add_model(o_model)
    tol = parsed_model.tolerance
    multiplier = not full_geometry
    enforce_adj_check = not bypass_adj_check
    enforce_solid = not permit_non_solid

    # if solve dragonfly wall adjacencies if requested
    if solve_adjacency:
        for bldg in parsed_model.buildings:
            for story in bldg.unique_stories:
                story.remove_room_2d_colinear_vertices(tol)
                story.intersect_room_2d_adjacency(tol)
        for bldg in parsed_model.buildings:
            for story in bldg.unique_stories:
                story.solve_room_2d_adjacency(tol, resolve_window_conflicts=True)

    # convert the dragonfly Model to Honeybee
    hb_model = parsed_model.to_honeybee(
        object_per_model='District', use_multiplier=multiplier,
        exclude_plenums=no_plenum, solve_ceiling_adjacencies=solve_adjacency,
        enforce_adj=enforce_adj_check, enforce_solid=enforce_solid)[0]

    # merge the honeybee models
    other_hb_models = [HBModel.from_file(m) for m in honeybee_model]
    for o_model in other_hb_models:
        if solve_adjacency:
            for room in o_model.rooms:
                room.merge_coplanar_faces(o_model.tolerance, o_model.angle_tolerance)
        hb_model.add_model(o_model)

    # perform a final solve adjacency if requested
    if solve_adjacency and len(other_hb_models) != 0:
        hb_model.solve_adjacency(intersect=True)

    # write the new model out to the file or stdout
    model_str = json.dumps(hb_model.to_dict())
    return process_content_to_output(model_str, output_file)
