"""dragonfly validation commands."""
import click
import sys
import logging
import json

from dragonfly.model import Model
from dragonfly.config import folders

_logger = logging.getLogger(__name__)


@click.group(help='Commands for validating Dragonfly files.')
def validate():
    pass


@validate.command('model')
@click.argument('model-file', type=click.Path(
    exists=True, file_okay=True, dir_okay=False, resolve_path=True))
@click.option(
    '--check-all/--room-overlaps', ' /-ro', help='Flag to note whether the output '
    'validation report should validate all possible issues with the model or only '
    'the Room2D overlaps of each Story should be checked. Checking for room overlaps '
    'will also check for degenerate and self-intersecting Rooms.',
    default=True, show_default=True)
@click.option(
    '--plain-text/--json', ' /-j', help='Flag to note whether the output validation '
    'report should be formatted as a JSON object instead of plain text. If set to JSON, '
    'the output object will contain several attributes. The "honeybee_core" and '
    '"honeybee_schema" attributes will note the versions of these libraries used in '
    'the validation process. An attribute called "fatal_error" is a text string '
    'containing an exception if the Model failed to serialize and will be an empty '
    'string if serialization was successful. An attribute called "errors" will '
    'contain a list of JSON objects for each invalid issue found in the model. A '
    'boolean attribute called "valid" will note whether the Model is valid or not.',
    default=True, show_default=True)
@click.option(
    '--output-file', '-f', help='Optional file to output the full report '
    'of any errors detected. By default it will be printed out to stdout',
    type=click.File('w'), default='-')
def validate_model(model_file, check_all, plain_text, output_file):
    """Validate a Model file against the Dragonfly schema.

    \b
    Args:
        model_file: Full path to either a DFJSON or DFpkl file. This can also be a
            HBJSON or a HBpkl from which a Dragonfly model should be derived.
    """
    try:
        if plain_text:
            # re-serialize the Model to make sure no errors are found
            click.echo(
                'Validating Model using dragonfly-core=={} and '
                'dragonfly-schema=={}'.format(
                    folders.dragonfly_core_version_str,
                    folders.dragonfly_schema_version_str
                )
            )
            parsed_model = Model.from_file(model_file)
            click.echo('Re-serialization passed.')
            # perform several other checks for key dragonfly model schema rules
            if check_all:
                report = parsed_model.check_all(raise_exception=False)
            else:
                r1 = parsed_model.check_degenerate_room_2ds(raise_exception=False)
                r2 = parsed_model.check_self_intersecting_room_2ds(raise_exception=False)
                r3 = parsed_model.check_no_room2d_overlaps(raise_exception=False)
                report = r1 + r2 + r3
            click.echo('Geometry and identifier checks completed.')
            # check the report and write the summary of errors
            if report == '':
                output_file.write('Congratulations! Your Model is valid!')
            else:
                error_msg = '\nYour Model is invalid for the following reasons:'
                output_file.write('\n'.join([error_msg, report]))
        else:
            out_dict = {
                'type': 'ValidationReport',
                'app_name': 'Dragonfly',
                'app_version': folders.dragonfly_core_version_str,
                'schema_version': folders.dragonfly_schema_version_str
            }
            try:
                parsed_model = Model.from_file(model_file)
                out_dict['fatal_error'] = ''
                if check_all:
                    errors = parsed_model.check_all(raise_exception=False, detailed=True)
                else:
                    err1 = parsed_model.check_degenerate_room_2ds(
                        raise_exception=False, detailed=True)
                    err2 = parsed_model.check_self_intersecting_room_2ds(
                            raise_exception=False, detailed=True)
                    err3 = parsed_model.check_no_room2d_overlaps(
                        raise_exception=False, detailed=True)
                    errors = err1 + err2 + err3
                out_dict['errors'] = errors
                out_dict['valid'] = True if len(out_dict['errors']) == 0 else False
            except Exception as e:
                out_dict['fatal_error'] = str(e)
                out_dict['errors'] = []
                out_dict['valid'] = False
            output_file.write(json.dumps(out_dict, indent=4))
    except Exception as e:
        _logger.exception('Model validation failed.\n{}'.format(e))
        sys.exit(1)
    else:
        sys.exit(0)
