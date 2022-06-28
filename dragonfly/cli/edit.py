"""dragonfly model editing commands."""
import click
import sys
import logging
import json

from ladybug_geometry.geometry2d.ray import Ray2D
from ladybug_geometry.geometry2d.line import LineSegment2D
from honeybee.orientation import angles_from_num_orient, orient_index
from honeybee.boundarycondition import Outdoors
from honeybee.boundarycondition import boundary_conditions as bcs
from honeybee.units import parse_distance_string
try:
    ad_bc = bcs.adiabatic
except AttributeError:  # honeybee_energy is not loaded and adiabatic does not exist
    ad_bc = None

from dragonfly.model import Model
from dragonfly.windowparameter import SimpleWindowRatio

_logger = logging.getLogger(__name__)


@click.group(help='Commands for editing Dragonfly models.')
def edit():
    pass


@edit.command('convert-units')
@click.argument('model-file', type=click.Path(
    exists=True, file_okay=True, dir_okay=False, resolve_path=True))
@click.argument('units', type=str)
@click.option('--scale/--do-not-scale', ' /-ns', help='Flag to note whether the model '
              'should be scaled as it is converted to the new units system.',
              default=True, show_default=True)
@click.option('--output-file', '-f', help='Optional file to output the Model JSON string'
              ' with solved adjacency. By default it will be printed out to stdout',
              type=click.File('w'), default='-')
def convert_units(model_file, units, scale, output_file):
    """Convert a Model to a given units system.

    \b
    Args:
        model_file: Full path to a Model JSON or Pkl file.
        units: Text for the units system to which the model will be converted.
            Choose from (Meters, Millimeters, Feet, Inches, Centimeters).
    """
    try:
        # serialize the Model and convert the units
        parsed_model = Model.from_file(model_file)
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
@click.argument('model-file', type=click.Path(
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
def solve_adjacency(model_file, surface, no_intersect, output_file):
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
        model_file: Full path to a Model JSON or Pkl file.
    """
    try:
        # serialize the Model and check tolerance
        parsed_model = Model.from_file(model_file)
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


@edit.command('align')
@click.argument('model-file', type=click.Path(
    exists=True, file_okay=True, dir_okay=False, resolve_path=True))
@click.argument('line-ray-file', type=click.Path(
    exists=True, file_okay=True, dir_okay=False, resolve_path=True))
@click.option(
    '--distance', '-d', help='A number for the maximum distance between a vertex '
    'and the line_ray where the vertex will be moved to lie on the line_ray. Vertices '
    'beyond this distance will be left as they are. This input can include the units '
    'of the distance (eg. 3ft) or, if no units are provided, the value will be '
    'interpreted in the honeybee model units.',
    type=str, default='0.5m', show_default=True)
@click.option(
    '--story', '-s', multiple=True, help='An optional identifier of a particular '
    'Story to be aligned in the model. If unspecified, all stories in the model '
    'will be aligned.')
@click.option(
    '--output-file', '-f', help='Optional file to output the Model JSON string'
    ' with aligned Room2Ds. By default it will be printed out to stdout',
    type=click.File('w'), default='-')
@click.option(
    '--log-file', '-log', help='Optional file to output the list of any Room2Ds that '
    'became degenerate and were deleted after alignment. By default it will be '
    'printed out to stdout', type=click.File('w'), default='-')
def align_room_2ds(model_file, line_ray_file, distance, story, output_file, log_file):
    """Move Room2D vertices within a given distance of a line or ray to be on that line.

    \b
    Args:
        model_file: Full path to a Model JSON or Pkl file.
        line_ray_file: Full path to a JSON file containing an array of ladybug_geometry
            Ray2D or LineSegment2D objects to which the Room2D vertices will be
            aligned. Ray2Ds will be interpreted as being infinite in both directions
            while LineSegment2Ds will be interpreted as only existing between two points.
    """
    try:
        # serialize the Model and check tolerance
        model = Model.from_file(model_file)
        assert model.tolerance != 0, \
            'Model must have a non-zero tolerance to use solve-adjacency.'
        # serialize the line_ray_file
        line_rays = []
        with open(line_ray_file) as inf:
            data = json.load(inf)
            for geo_obj in data:
                if geo_obj['type'] == 'LineSegment2D':
                    line_rays.append(LineSegment2D.from_dict(geo_obj))
                elif geo_obj['type'] == 'Ray2D':
                    line_rays.append(Ray2D.from_dict(geo_obj))
                else:
                    msg = 'Objects in line-ray-file must be LineSegment2D or Ray2D. ' \
                        'Not {}'.format(geo_obj['type'])
                    raise TypeError(msg)
        # interpret the distance input
        distance = parse_distance_string(distance)

        # filter the stories if --story is specified
        all_stories = model.stories
        if len(story) != 0:
            all_stories = [s for s in all_stories if s.identifier in story]

        # loop through the stories and align them
        for d_story in all_stories:
            for line in line_rays:
                d_story.align_room_2ds(line, distance)
            # perform some extra cleanup operations
            del_rooms = d_story.remove_room_2d_duplicate_vertices(
                model.tolerance, delete_degenerate=True)
            del_rooms.extend(d_story.delete_degenerate_room_2ds())
            d_story.rebuild_detailed_windows(model.tolerance)
            # report any deleted rooms
            if len(del_rooms) != 0:
                del_ids = ['{}[{}]'.format(r.display_name, r.identifier)
                           for r in del_rooms]
                msg = 'The following Room2Ds were degenerate after aligning and ' \
                    'were deleted:\n{}'.format('\n'.join(del_ids))
                log_file.write(msg)

        # write the new model out to the file or stdout
        output_file.write(json.dumps(model.to_dict()))
    except Exception as e:
        _logger.exception('Model align failed.\n{}'.format(e))
        sys.exit(1)
    else:
        sys.exit(0)


@edit.command('windows-by-ratio')
@click.argument('model-file', type=click.Path(
    exists=True, file_okay=True, dir_okay=False, resolve_path=True))
@click.argument('ratio', type=float, nargs=-1)
@click.option('--output-file', '-f', help='Optional file to output the Model JSON string'
              ' with windows. By default it will be printed out to stdout',
              type=click.File('w'), default='-')
def windows_by_ratio(model_file, ratio, output_file):
    """Add windows to all outdoor walls of a model given a ratio.

    Note that this method removes any existing WindowParameters.

    \b
    Args:
        model_file: Full path to a Dragonfly DFJSON or DFpkl file.
        ratio: A number between 0 and 1 (but not perfectly equal to 1) for the
            desired ratio between window area and wall area. If multiple values
            are input here, different WindowParameters will be assigned based on
            cardinal direction, starting with north and moving clockwise.
    """
    try:
        # serialize the Model and convert ratios to window parameters
        model = Model.from_file(model_file)
        win_par = [SimpleWindowRatio(rat) for rat in ratio]

        # add the window parameters
        if len(win_par) == 1:  # one window parameter for all
            model.set_outdoor_window_parameters(win_par[0])
        else:  # different window parameters by cardinal direction
            angles = angles_from_num_orient(len(win_par))
            rooms = [room for bldg in model.buildings for room in bldg.unique_room_2ds]
            for rm in rooms:
                room_win_par = []
                for bc, orient in zip(rm.boundary_conditions, rm.segment_orientations()):
                    orient_i = orient_index(orient, angles)
                    win_p = win_par[orient_i] if isinstance(bc, Outdoors) else None
                    room_win_par.append(win_p)
                rm.window_parameters = room_win_par

        # write the new model out to the file or stdout
        output_file.write(json.dumps(model.to_dict()))
    except Exception as e:
        _logger.exception('Model windows by ratio failed.\n{}'.format(e))
        sys.exit(1)
    else:
        sys.exit(0)
