"""dragonfly model editing commands."""

try:
    import click
except ImportError:
    raise ImportError(
        'click is not installed. Try `pip install . [cli]` command.'
    )

from dragonfly.model import Model
from honeybee.boundarycondition import boundary_conditions as bcs
try:
    ad_bc = bcs.adiabatic
except AttributeError:  # honeybee_energy is not loaded and adiabatic does not exist
    ad_bc = None


import sys
import os
import logging
import json

_logger = logging.getLogger(__name__)


@click.group(help='Commands for editing Dragonfly models.')
def edit():
    pass


@edit.command('convert-units')
@click.argument('model-json', type=click.Path(
    exists=True, file_okay=True, dir_okay=False, resolve_path=True))
@click.argument('units', type=str)
@click.option('--scale/--do-not-scale', ' /-ns', help='Flag to note whether the model '
              'should be scaled as it is converted to the new units system.',
              default=True, show_default=True)
@click.option('--output-file', '-f', help='Optional file to output the Model JSON string'
              ' with solved adjacency. By default it will be printed out to stdout',
              type=click.File('w'), default='-')
def convert_units(model_json, units, scale, output_file):
    """Convert a Model to a given units system.

    \b
    Args:
        model_json: Full path to a Model JSON file.
        units: Text for the units system to which the model will be converted.
            Choose from (Meters, Millimeters, Feet, Inches, Centimeters).
    """
    try:
        # serialize the Model to Python
        with open(model_json) as json_file:
            data = json.load(json_file)
        parsed_model = Model.from_dict(data)

        # convert the units of the model
        if scale:
            parsed_model.convert_to_units(units)
        else:
            parsed_model.units = units

        # write the new model out to the file or stdout
        output_file.write(json.dumps(parsed_model.to_dict()))
    except Exception as e:
        _logger.exception('Model unit conversion failed.\n{}'.format(e))
        sys.exit(1)
    else:
        sys.exit(0)


@edit.command('solve-adjacency')
@click.argument('model-json', type=click.Path(
    exists=True, file_okay=True, dir_okay=False, resolve_path=True))
@click.option('--surface/--adiabatic', ' /-a', help='Flag to note whether the '
              'adjacencies should be surface or adiabatic.',
              default=True, show_default=True)
@click.option('--no-intersect/--intersect', ' /-i', help='Flag to note whether the '
              'segments of the Room2Ds should be intersected with one another before '
              'the adjacencies are solved.', default=True, show_default=True)
@click.option('--output-file', '-f', help='Optional file to output the Model JSON string'
              ' with solved adjacency. By default it will be printed out to stdout',
              type=click.File('w'), default='-')
def solve_adjacency(model_json, surface, no_intersect, output_file):
    """Solve adjacency between Room2Ds of a Model JSON file.

    This involves setting Surface or Adiabatic boundary conditions for all matching
    segments across each Story.

    \b
    If the --intersect option is selected, this will involve involve the following.
    1. Remove colinear vertices from the Room2D polygons.
    2. Intersect adjacent segments of the same Story with one another.
    Note that the --intersect option removes all existing boundary_conditions,
    window_parameters, and shading_parameters.

    \b
    Args:
        model_json: Full path to a Model JSON file.
    """
    try:
        # serialize the Model to Python
        with open(model_json) as json_file:
            data = json.load(json_file)
        parsed_model = Model.from_dict(data)

        # check the Model tolerance
        assert parsed_model.tolerance != 0, \
            'Model must have a non-zero tolerance to use solve-adjacency.'
        tol = parsed_model.tolerance

        # intersect adjacencies if requested
        if not no_intersect:
            for bldg in parsed_model.buildings:
                for story in bldg.unique_stories:
                    story.remove_room_2d_colinear_vertices(tol)
                    story.intersect_room_2d_adjacency(tol)

        # solve the adjacency of each story
        for bldg in parsed_model.buildings:
            for story in bldg.unique_stories:
                adj_info = story.solve_room_2d_adjacency(tol)
                if not surface and ad_bc:
                    for face_pair in adj_info:
                        face_pair[0][0].set_boundary_condition(face_pair[0][1], ad_bc)
                        face_pair[1][0].set_boundary_condition(face_pair[1][1], ad_bc)

        # write the new model out to the file or stdout
        output_file.write(json.dumps(parsed_model.to_dict()))
    except Exception as e:
        _logger.exception('Model solve adjacency failed.\n{}'.format(e))
        sys.exit(1)
    else:
        sys.exit(0)
