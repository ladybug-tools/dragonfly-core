"""dragonfly model creation commands."""
import click
import sys
import logging
import json

from dragonfly.model import Model

_logger = logging.getLogger(__name__)


@click.group(help='Commands for creating Dragonfly models.')
def create():
    pass


@create.command('merge-models')
@click.argument('base-model', type=click.Path(
    exists=True, file_okay=True, dir_okay=False, resolve_path=True))
@click.option(
    '--other-model', '-m', help='The other Model to be merged into the base model.',
    type=click.File('w'), multiple=True)
@click.option(
    '--output-file', '-f', help='Optional file to output the Model JSON string'
    ' with solved adjacency. By default it will be printed out to stdout',
    type=click.File('w'), default='-')
def merge_models(base_model, other_model, output_file):
    """Create a Dragonfly Model by merging multiple models together.

    \b
    Args:
        base_model: Full path to a Dragonfly Model JSON or Pkl file that serves
            as the base into which the other model(s) will be merged. This model
            determines the units and tolerance of the output model.
    """
    try:
        # serialize the Model and convert the units
        parsed_model = Model.from_file(base_model)
        other_models = [Model.from_file(m) for m in other_model]
        for o_model in other_models:
            parsed_model.add_model(o_model)

        # write the new model out to the file or stdout
        output_file.write(json.dumps(parsed_model.to_dict()))
    except Exception as e:
        _logger.exception('Model merging failed.\n{}'.format(e))
        sys.exit(1)
    else:
        sys.exit(0)
