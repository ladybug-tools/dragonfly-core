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
def validate_model(model_json):
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
        parsed_model.check_duplicate_building_identifiers(raise_exception=True)
        parsed_model.check_duplicate_context_shade_identifiers(raise_exception=True)
        parsed_model.check_missing_adjacencies(raise_exception=True)
        click.echo('Unique identifier and adjacency checks passed.')
        # lastly, check the JSON against the OpenAPI specification to get any last errors
        schema_model.Model.parse_file(model_json)
        click.echo('Pydantic validation passed.')
        click.echo('Congratulations! Your Model JSON is valid!')
    except Exception as e:
        _logger.exception('Model validation failed.\n{}'.format(e))
        sys.exit(1)
    else:
        sys.exit(0)
