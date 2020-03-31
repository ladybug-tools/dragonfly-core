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
except: # honeybee_energy is not loaded and adiabatic does not exist
    ad_bc = None


import sys
import os
import logging
import json

_logger = logging.getLogger(__name__)


@click.group(help='Commands for editing Dragonfly models.')
def edit():
    pass


@edit.command('solve-adjacency')
@click.argument('model-json')
@click.argument('adiabatic', type=bool, default=False)
@click.option('--included-prop', help='List of properties to filter keys that must '
              'be included in output JSON. For example ["energy"] will include '
              '"energy" key if available. By default, all the keys will be'
              'included. To exclude all the keys from extensions, use an empty list.',
              type=list, default=None)
@click.option('--log-file', help='Optional log file to output the Model JSON string'
              ' with solved adjacency. By default it will be printed out to stdout',
              type=click.File('w'), default='-')
def solve_adjacency(model_json, adiabatic, included_prop, log_file):
    """Solve adjacency between Room2Ds of a Model JSON file. This includes 3 steps.\n
    1. Remove colinear vertices from the Room2D polygons.\n
    2. Intersect adjacent segments of the same Story with one another.\n
    3. Set Surface boundary conditions for all matching segments across each Story.\n
    \n
    Note that this command removes all existing boundary_conditions, window_parameters,
    and shading_parameters so it is recommended that this method be used at the
    beginning of model creation.
    \n
    Args:
        model_json: Full path to a Model JSON file.\n
        adiabatic: Boolean to note whether adjacencies should be adiabatic.
    """
    try:
        assert os.path.isfile(model_json), 'No JSON file found at {}.'.format(model_json)

        # serialze the Model to Python
        with open(model_json) as json_file:
            data = json.load(json_file)
        parsed_model = Model.from_dict(data)

        # check the Model tolerance
        assert parsed_model.tolerance != 0, \
            'Model must have a non-zero tolerance to use solve-adjacency.'
        tol = parsed_model.tolerance

        # process the adjacency of each story
        for bldg in parsed_model.buildings:
            for story in bldg.unique_stories:
                story.remove_room_2d_colinear_vertices(tol)
                story.intersect_room_2d_adjacency(tol)
                adj_info = story.solve_room_2d_adjacency(tol)
                if adiabatic and ad_bc:
                    for face_pair in adj_info:
                        face_pair[0][0].set_boundary_condition(face_pair[0][1], ad_bc)
                        face_pair[1][0].set_boundary_condition(face_pair[1][1], ad_bc)
        
        # write the new model out to the file or stdout
        log_file.write(json.dumps(parsed_model.to_dict(included_prop)))

    except Exception as e:
        _logger.exception('Model solve adjacency failed.\n{}'.format(e))
        sys.exit(1)
    else:
        sys.exit(0)
