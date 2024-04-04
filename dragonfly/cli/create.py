"""dragonfly model creation commands."""
import click
import sys
import logging
import json

from honeybee.model import Model as HBModel
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
    '--output-file', '-f', help='Optional file to output the Model DFJSON string. '
    'By default it will be printed out to stdout',
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


@create.command('from-honeybee')
@click.argument('base-model', type=click.Path(
    exists=True, file_okay=True, dir_okay=False, resolve_path=True))
@click.option(
    '--other-model', '-m', help='Another Honeybee Model to be added as a separate '
    'Building in the resulting Dragonfly Model.',
    type=click.File('w'), multiple=True)
@click.option(
    '--conversion-method', '-c', help='Text to indicate how the Honeybee Rooms '
    'should be converted to Dragonfly. Choose from: AllRoom2D, ExtrudedOnly, AllRoom3D. '
    'Note that the AllRoom2D option may result in some loss or simplification of '
    'the 3D Honeybee geometry but ensures that all of the Dragonfly features for '
    'editing the rooms can be used. The ExtrudedOnly method will convert only the '
    '3D Rooms that would have no loss or simplification of geometry when converted '
    'to Room2D. AllRoom3D keeps all detailed 3D geometry on the Building.room_3ds '
    'property, enabling you to convert the 3D Rooms to Room2D using the '
    'Building.convert_room_3ds_to_2d() method as you see fit.',
    type=str, default="ExtrudedOnly", show_default=True)
@click.option(
    '--output-file', '-f', help='Optional file to output the Model DFJSON string. '
    'By default it will be printed out to stdout',
    type=click.File('w'), default='-')
def from_honeybee(base_model, conversion_method, other_model, output_file):
    """Create a Dragonfly Model from Honeybee Model(s).

    \b
    Args:
        base_model: Full path to a Honeybee Model JSON or Pkl file that serves
            as the base for the resulting Dragonfly Model. This model
            determines the units and tolerance of the output model.
    """
    try:
        # serialize the input Model(s)
        hb_model = HBModel.from_file(base_model)
        other_models = [HBModel.from_file(m) for m in other_model]

        # convert the Honeybee Model(s) to Dragonfly
        df_model = Model.from_honeybee(hb_model, conversion_method)
        for o_hb_model in other_models:
            o_df_model = Model.from_honeybee(o_hb_model, conversion_method)
            df_model.add_model(o_df_model)

        # write the new model out to the file or stdout
        output_file.write(json.dumps(df_model.to_dict()))
    except Exception as e:
        _logger.exception('Model creation from honeybee failed.\n{}'.format(e))
        sys.exit(1)
    else:
        sys.exit(0)
