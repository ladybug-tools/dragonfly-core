"""dragonfly validation commands."""
import click
import sys
import logging
import json

from dragonfly.model import Model

_logger = logging.getLogger(__name__)

try:
    import dragonfly_schema.model as schema_model
except ImportError:
    _logger.exception(
        'dragonfly_schema is not installed and validation commands are unavailable.\n'
        'You must use Python 3.7 or above to run validation commands.'
    )


@click.group(help='Commands for validating Dragonfly JSON files.')
def validate():
    pass


@validate.command('model')
@click.argument('model-json', type=click.Path(
    exists=True, file_okay=True, dir_okay=False, resolve_path=True))
@click.option(
    '--output-file', '-f', help='Optional file to output the full report '
    'of any errors detected. By default it will be printed out to stdout',
    type=click.File('w'), default='-')
def validate_model(model_json, output_file):
    """Validate a Model JSON file against the Dragonfly schema.

    \b
    Args:
        model_json: Full path to a Model JSON file.
    """
    try:        
        # re-serialize the Model to make sure no errors are found in re-serialization
        click.echo('Validating Model JSON ...')
        parsed_model = Model.from_dfjson(model_json)
        click.echo('Python re-serialization passed.')
        # perform several other checks for key dragonfly model schema rules
        report = parsed_model.check_all(raise_exception=False)
        click.echo('Unique identifier and adjacency checks completed.')
        # lastly, check the JSON against the OpenAPI specification to get any last errors
        schema_model.Model.parse_file(model_json)
        click.echo('Pydantic validation passed.')
        # check the report and write the summary of errors
        if report == '':
            output_file.write('Congratulations! Your Model JSON is valid!')
        else:
            error_msg = '\nYour Model is invalid for the following reasons:'
            output_file.write('\n'.join([error_msg, report]))
    except Exception as e:
        _logger.exception('Model validation failed.\n{}'.format(e))
        sys.exit(1)
    else:
        sys.exit(0)
