"""dragonfly model editing commands."""
import click
import sys
import logging
import json

from ladybug_geometry.geometry2d import Ray2D, LineSegment2D, Polygon2D
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
@click.option('--resolve-window-conflicts/--show-window-conflicts', ' /-w',
              help='Flag to note whether conflicts between window parameters of '
              'adjacent segments should be resolved during adjacency setting or an '
              'error should be raised about the mismatch. Resolving conflicts will '
              'default to the window parameters with the larger are and assign them '
              'to the other segment.', default=True, show_default=True)
@click.option('--output-file', '-f', help='Optional file to output the Model JSON string'
              ' with solved adjacency. By default it will be printed out to stdout',
              type=click.File('w'), default='-')
def solve_adjacency(
        model_file, surface, no_intersect, resolve_window_conflicts, output_file):
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
                adj_info = story.solve_room_2d_adjacency(
                    tol, resolve_window_conflicts=resolve_window_conflicts)
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


@edit.command('reset-room-boundaries')
@click.argument('model-file', type=click.Path(
    exists=True, file_okay=True, dir_okay=False, resolve_path=True))
@click.argument('polygon-file', type=click.Path(
    exists=True, file_okay=True, dir_okay=False, resolve_path=True))
@click.option(
    '--distance', '-d', help='A number for the maximum distance between a vertex '
    'and the polygon where the vertex will be moved to lie on the polygon. Setting '
    'this to zero assumes that all relevant Room2D segments are completely colinear '
    'with the polygons within the Model tolerance. This input can include the units '
    'of the distance (eg. 1ft) or, if no units are provided, the value will be '
    'interpreted in the dragonfly model units.',
    type=str, default='0.15m', show_default=True)
@click.option(
    '--keep-colinear/--merge-colinear', ' /-c', help='Flag to note whether colinear '
    'wall segments of the resulting Room2Ds should be merged with one another after '
    'the room boundaries have been reset. This is particularly helpful when the '
    'input polygon file represents an exterior envelope.',
    default=True, show_default=True)
@click.option(
    '--output-file', '-f', help='Optional file to output the Model JSON string'
    ' with aligned Room2Ds. By default it will be printed out to stdout',
    type=click.File('w'), default='-')
def reset_room_boundaries(
        model_file, polygon_file, distance, keep_colinear, output_file):
    """Rebuild the Room2Ds of a Model using boundary Polygons.

    All existing properties of segments along the boundary polygons will be preserved,
    including all window geometries. By default, the largest room that is identified
    within each of the boundary polygons will determine the extension properties
    of the resulting Room2D.

    \b
    Args:
        model_file: Full path to a Dragonfly Model JSON or Pkl file.
        polygon_file: Full path to a JSON file containing an array of ladybug_geometry
            Polygon2D objects to which the Room2D segments will be reset. The array
            of Polygon2Ds can contain both outer boundaries and holes in the floor
            plate and this command will automatically distinguish holes from boundaries.
            This JSON can also be a dictionary where the keys are the identifiers
            of Stories in the Model and the values are arrays of Polygon2D objects
            to be applied only to that Story. This dictionary can also contain
            an __all__ key, which can contain a list of Polygon2D to be applied to
            all Stories in the Model. Any Polygon2D JSON objects that contain
            "identifier" or "display_name" properties will be used to determine the
            identifier and display_name of the resulting Room2D. Otherwise, these
            identifiers are taken from the largest existing Room2D inside each polygon.
            Any Polygon2D JSON objects that contain a "floor_to_ceiling_height"
            property will be used to determine the floor_to_ceiling_height of
            the resulting Room2D. Otherwise, it will be the maximum of the Room2Ds
            that are found inside the polygon, which ensures that all window
            geometries are included in the output. If the specified height is
            lower than the maximum Room2D height, any detailed windows will be
            automatically trimmed to accommodate the new floor-to-ceiling height.
    """
    try:
        # serialize the Model and check tolerance
        model = Model.from_file(model_file)
        tol = model.tolerance
        assert tol != 0, \
            'Model must have a non-zero tolerance to use reset-room-boundaries.'
        # interpret the distance input
        distance = parse_distance_string(distance, model.units)
        # serialize the polygon_file
        with open(polygon_file) as inf:
            data = json.load(inf)
        if isinstance(data, list):
            rel_stories = model.stories
            p_geo, p_ids, p_names, p_ftc = _serialize_polygons(data, tol)
            polygons = [p_geo] * len(rel_stories)
            identifiers = [p_ids] * len(rel_stories)
            names = [p_names] * len(rel_stories)
            ftcs = [p_ftc] * len(rel_stories)
        elif isinstance(data, dict):
            story_ids, polygons, identifiers, names, ftcs = [], [], [], [], []
            all_polygons, all_identifiers, all_names = None, None, None
            for st_id, st_lin in data.items():
                if st_id == '__all__':
                    all_polygons, all_identifiers, all_names, all_ftc = \
                        _serialize_polygons(st_lin, tol)
                else:
                    story_ids.append(st_id)
                    p_geo, p_ids, p_names, p_ftc = _serialize_polygons(st_lin, tol)
                    polygons.append(p_geo)
                    identifiers.append(p_ids)
                    names.append(p_names)
                    ftcs.append(p_ftc)
            rel_stories = model.stories_by_identifier(story_ids)
            if all_polygons is not None:
                for story in model.stories:
                    rel_stories.append(story)
                    polygons.append(all_polygons)
                    identifiers.append(all_identifiers)
                    names.append(all_names)
                    ftcs.append(all_ftc)

        # loop through the stories and reset the rooms
        zip_obj = zip(rel_stories, polygons, identifiers, names, ftcs)
        for d_story, p_gons, p_id, p_n, ftc in zip_obj:
            # align the rooms to the polygon segments
            if distance != 0:
                line_rays = []
                for p_gon in p_gons:
                    line_rays.extend(p_gon.segments)
                for line in line_rays:
                    d_story.align(line, distance, tol)
            # perform some extra cleanup operations
            d_story.remove_room_2d_duplicate_vertices(tol, delete_degenerate=True)
            d_story.delete_degenerate_room_2ds(tol)
            d_story.rebuild_detailed_windows(tol)
            # reset the room boundaries
            d_story.reset_room_2d_boundaries(p_gons, p_id, p_n, ftc, tolerance=tol)
            if not keep_colinear:
                d_story.remove_room_2d_colinear_vertices(tolerance=tol)

        # write the new model out to the file or stdout
        output_file.write(json.dumps(model.to_dict()))
    except Exception as e:
        _logger.exception('Model reset-room-boundaries failed.\n{}'.format(e))
        sys.exit(1)
    else:
        sys.exit(0)


def _serialize_polygons(polygon_dicts, tol):
    """Serialize an array of Polygon2Ds."""
    polygons, p_ids, p_names, p_ftc = [], [], [], []
    for geo_obj in polygon_dicts:
        if geo_obj['type'] == 'Polygon2D':
            p_geo = Polygon2D.from_dict(geo_obj)
            p_geo = p_geo.remove_colinear_vertices(tol)
            polygons.append(p_geo)
            if 'identifier' in geo_obj:
                p_ids.append(geo_obj['identifier'])
            else:
                p_ids.append(None)
            if 'display_name' in geo_obj:
                p_names.append(geo_obj['display_name'])
            else:
                p_names.append(None)
            if 'floor_to_ceiling_height' in geo_obj:
                p_ftc.append(geo_obj['floor_to_ceiling_height'])
            else:
                p_ftc.append(None)
        else:
            msg = 'Objects in polygon-file must be Polygon2D. ' \
                'Not {}'.format(geo_obj['type'])
            raise TypeError(msg)
    return polygons, p_ids, p_names, p_ftc


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
    'interpreted in the dragonfly model units.',
    type=str, default='0.5m', show_default=True)
@click.option(
    '--remove-distance', '-r', help='An optional number for the maximum length of a '
    'segment below which the segment will be removed. This operation is performed '
    'before the alignment. This input can include the units of the distance (eg. 3ft) '
    'or, if no units are provided, the value will be interpreted in the dragonfly '
    'model units.', type=str, default=None, show_default=True)
@click.option(
    '--keep-colinear/--merge-colinear', ' /-c', help='Flag to note whether colinear '
    'wall segments of the resulting Room2Ds should be merged with one another after '
    'the alignment has been performed.', default=True, show_default=True)
@click.option(
    '--output-file', '-f', help='Optional file to output the Model JSON string'
    ' with aligned Room2Ds. By default it will be printed out to stdout',
    type=click.File('w'), default='-')
@click.option(
    '--log-file', '-log', help='Optional file to output the list of any Room2Ds that '
    'became degenerate and were deleted after alignment. By default it will be '
    'printed out to stdout', type=click.File('w'), default='-')
def align_room_2ds(model_file, line_ray_file, distance, remove_distance, keep_colinear,
                   output_file, log_file):
    """Move Room2D vertices within a given distance of a line or ray to be on that line.

    By default, all Stories in the Model will be aligned but the input line-ray-file
    can be structured to only specify line-rays for specific stories if desired.

    \b
    Args:
        model_file: Full path to a Model JSON or Pkl file.
        line_ray_file: Full path to a JSON file containing an array of ladybug_geometry
            Ray2D or LineSegment2D objects to which the Room2D vertices will be
            aligned. Ray2Ds will be interpreted as being infinite in both directions
            while LineSegment2Ds will be interpreted as only existing between two points.
            This JSON can also be a dictionary where the keys are the identifiers
            of Stories in the Model and the values are arrays of Ray2D or LineSegment2D
            objects to be applied only to that Story. This dictionary can also contain
            an __all__ key, which can contain a list of Ray2D or LineSegment2D to be
            applied to all Stories in the Model.
    """
    try:
        # serialize the Model and check tolerance
        model = Model.from_file(model_file)
        assert model.tolerance != 0, \
            'Model must have a non-zero tolerance to use align.'
        # interpret the distance input
        distance = parse_distance_string(distance, model.units)
        # serialize the line_ray_file
        with open(line_ray_file) as inf:
            data = json.load(inf)
        if isinstance(data, list):
            rel_stories = model.stories
            story_lines = [_serialize_line_rays(data)] * len(rel_stories)
        elif isinstance(data, dict):
            story_ids, story_lines, all_story_lines = [], [], None
            for st_id, st_lin in data.items():
                if st_id == '__all__':
                    all_story_lines = _serialize_line_rays(st_lin)
                else:
                    story_ids.append(st_id)
                    story_lines.append(_serialize_line_rays(st_lin))
            rel_stories = model.stories_by_identifier(story_ids)
            if all_story_lines is not None:
                for story in model.stories:
                    rel_stories.append(story)
                    story_lines.append(all_story_lines)

        # remove short segments if requested
        del_rooms = []
        if remove_distance is not None and remove_distance != '':
            rem_dist = parse_distance_string(remove_distance, model.units)
            for d_story in model.stories:
                d_rooms = d_story.remove_room_2d_short_segments(
                    rem_dist, model.angle_tolerance)
                del_rooms.extend(d_rooms)

        # loop through the stories and align them
        for d_story, line_rays in zip(rel_stories, story_lines):
            for line in line_rays:
                d_story.align(line, distance, model.tolerance)
            # perform some extra cleanup operations
            d_rooms = d_story.remove_room_2d_duplicate_vertices(
                model.tolerance, delete_degenerate=True)
            d_rooms.extend(d_story.delete_degenerate_room_2ds(model.tolerance))
            d_story.rebuild_detailed_windows(model.tolerance)
            del_rooms.extend(d_rooms)
            if not keep_colinear:
                d_story.remove_room_2d_colinear_vertices(tolerance=model.tolerance)

        # report any deleted rooms
        if len(del_rooms) != 0:
            del_ids = ['{}[{}]'.format(r.display_name, r.identifier)
                       for r in del_rooms]
            msg = 'The following Room2Ds were degenerate after the operation and ' \
                'were deleted:\n{}'.format('\n'.join(del_ids))
            log_file.write(msg)

        # write the new model out to the file or stdout
        output_file.write(json.dumps(model.to_dict()))
    except Exception as e:
        _logger.exception('Model align failed.\n{}'.format(e))
        sys.exit(1)
    else:
        sys.exit(0)


def _serialize_line_rays(line_ray_dicts):
    """Serialize an array of LineSegment2Ds and Ray2Ds."""
    line_rays = []
    for geo_obj in line_ray_dicts:
        if geo_obj['type'] == 'LineSegment2D':
            line_rays.append(LineSegment2D.from_dict(geo_obj))
        elif geo_obj['type'] == 'Ray2D':
            line_rays.append(Ray2D.from_dict(geo_obj))
        else:
            msg = 'Objects in line-ray-file must be LineSegment2D or Ray2D. ' \
                'Not {}'.format(geo_obj['type'])
            raise TypeError(msg)
    return line_rays


@edit.command('remove-short-segments')
@click.argument('model-file', type=click.Path(
    exists=True, file_okay=True, dir_okay=False, resolve_path=True))
@click.option(
    '--distance', '-d', help='The maximum length of a segment below which the '
    'segment will be considered for removal. This input can include the units '
    'of the distance (eg. 3ft) or, if no units are provided, the value will be '
    'interpreted in the dragonfly model units.',
    type=str, default='0.5m', show_default=True)
@click.option(
    '--output-file', '-f', help='Optional file to output the Model JSON string'
    ' with aligned Room2Ds. By default it will be printed out to stdout',
    type=click.File('w'), default='-')
@click.option(
    '--log-file', '-log', help='Optional file to output the list of any Room2Ds that '
    'became degenerate and were deleted after alignment. By default it will be '
    'printed out to stdout', type=click.File('w'), default='-')
def remove_short_segments(model_file, distance, output_file, log_file):
    """Remove consecutive short segments on a Model's Room2Ds.

    \b
    Args:
        model_file: Full path to a Model JSON or Pkl file.
    """
    try:
        # serialize the Model and check tolerance
        model = Model.from_file(model_file)
        assert model.angle_tolerance != 0, \
            'Model must have a non-zero angle_tolerance to use remove-short-segments.'
        # interpret the distance input
        distance = parse_distance_string(distance, model.units)

        # loop through the stories and remove the short segments
        del_rooms = []
        for d_story in model.stories:
            d_rooms = d_story.remove_room_2d_short_segments(
                distance, model.angle_tolerance)
            del_rooms.extend(d_rooms)

        # report any deleted rooms
        if len(del_rooms) != 0:
            del_ids = ['{}[{}]'.format(r.display_name, r.identifier)
                       for r in del_rooms]
            msg = 'The following Room2Ds were degenerate after the operation and ' \
                'were deleted:\n{}'.format('\n'.join(del_ids))
            log_file.write(msg)

        # write the new model out to the file or stdout
        output_file.write(json.dumps(model.to_dict()))
    except Exception as e:
        _logger.exception('Model remove-short-segments failed.\n{}'.format(e))
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
