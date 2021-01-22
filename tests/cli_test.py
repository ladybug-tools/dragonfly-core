"""Test cli."""
from click.testing import CliRunner

from dragonfly.cli import viz
from dragonfly.cli.edit import convert_units, solve_adjacency
from dragonfly.cli.translate import model_to_honeybee

from dragonfly.model import Model
from honeybee.boundarycondition import Surface

import json
import os


def test_viz():
    runner = CliRunner()
    result = runner.invoke(viz)
    assert result.exit_code == 0
    assert result.output.startswith('vi')
    assert result.output.endswith('z!\n')


def test_convert_units():
    input_model = './tests/json/sample_revit_model.dfjson'
    runner = CliRunner()
    result = runner.invoke(convert_units, [input_model, 'Feet'])
    assert result.exit_code == 0

    model_dict = json.loads(result.output)
    new_model = Model.from_dict(model_dict)
    assert new_model.units == 'Feet'


def test_edit_solve_adjacency():
    input_model = './tests/json/sample_revit_model.dfjson'
    runner = CliRunner()
    result = runner.invoke(solve_adjacency, [input_model, '-i'])
    assert result.exit_code == 0

    result_model = Model.from_dict(json.loads(result.output))
    rooms = result_model.buildings[0].unique_room_2ds
    assert isinstance(rooms[0].boundary_conditions[0], Surface)


def test_model_to_honeybee():
    input_model = './tests/json/sample_revit_model.dfjson'
    runner = CliRunner()
    result = runner.invoke(model_to_honeybee, [input_model])
    assert result.exit_code == 0

    for model_info in json.loads(result.output):
        assert os.path.isfile(model_info['full_path'])
