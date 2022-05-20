"""dragonfly validation commands."""
import click
import sys
import logging
import json

from dragonfly.model import Model
from dragonfly.config import folders

_logger = logging.getLogger(__name__)


@click.group(help='Commands for validating Dragonfly JSON files.')
def validate():
    pass


@validate.command('model')
@click.argument('model-json', type=click.Path(
    exists=True, file_okay=True, dir_okay=False, resolve_path=True))
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
def validate_model(model_json, plain_text, output_file):
    """Validate a Model JSON file against the Dragonfly schema.

    \b
    Args:
        model_json: Full path to a Model JSON file.
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
            parsed_model = Model.from_dfjson(model_json)
            click.echo('Re-serialization passed.')
            # perform several other checks for key dragonfly model schema rules
            report = parsed_model.check_all(raise_exception=False)
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
                'dragonfly_core': folders.dragonfly_core_version_str,
                'dragonfly_schema': folders.dragonfly_schema_version_str
            }
            try:
                parsed_model = Model.from_dfjson(model_json)
                out_dict['fatal_error'] = ''
                out_dict['errors'] = \
                    parsed_model.check_all(raise_exception=False, detailed=True)
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
