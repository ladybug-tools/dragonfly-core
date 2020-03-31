"""Test cli."""
from click.testing import CliRunner

from dragonfly.cli import viz
from dragonfly.cli.validate import validate_model
from dragonfly.cli.edit import solve_adjacency

from dragonfly.model import Model
from honeybee.boundarycondition import Surface

import json


def test_viz():
    runner = CliRunner()
    result = runner.invoke(viz)
    assert result.exit_code == 0
    assert result.output.startswith('vi')
    assert result.output.endswith('z!\n')


def test_edit_solve_adjacency():
    input_model = './tests/json/sample_revit_model.json'
    runner = CliRunner()
    result = runner.invoke(solve_adjacency, [input_model])
    assert result.exit_code == 0

    result_model = Model.from_dict(json.loads(result.output))
    rooms = result_model.buildings[0].unique_room_2ds
    assert isinstance(rooms[0].boundary_conditions[0], Surface)
