"""Test cli."""
from click.testing import CliRunner

from dragonfly.cli import viz
from dragonfly.cli.edit import convert_units, solve_adjacency, align_room_2ds, \
    remove_short_segments, windows_by_ratio
from dragonfly.cli.translate import model_to_honeybee, model_from_geojson
from dragonfly.cli.validate import validate_model

from dragonfly.model import Model
from honeybee.boundarycondition import Surface

import json
import os
import sys


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


def test_align_room_2ds():
    input_model = './tests/json/Level03.dfjson'
    input_lines = './tests/json/line_rays.json'
    output_model = './tests/json/FixedLevel03.dfjson'
    runner = CliRunner()
    cmds = [input_model, input_lines, '--output-file', output_model]
    result = runner.invoke(align_room_2ds, cmds)
    assert result.exit_code == 0

    assert os.path.isfile(output_model)
    result_model = Model.from_file(output_model)
    rooms = result_model.buildings[0].unique_room_2ds
    assert len(rooms) == 144
    os.remove(output_model)


def test_remove_room_2d_short_segments():
    input_model = './tests/json/Level03.dfjson'
    output_model = './tests/json/CleanerLevel03.dfjson'
    runner = CliRunner()
    cmds = [input_model, '--output-file', output_model]
    result = runner.invoke(remove_short_segments, cmds)

    assert result.exit_code == 0

    assert os.path.isfile(output_model)
    result_model = Model.from_file(output_model)
    rooms = result_model.buildings[0].unique_room_2ds
    assert len(rooms) == 138
    os.remove(output_model)


def test_windows_by_ratio():
    input_model = './tests/json/sample_revit_model.dfjson'
    runner = CliRunner()
    result = runner.invoke(windows_by_ratio, [input_model, '0.4', '0.2', '0.6', '0.2'])
    assert result.exit_code == 0

    result_model = Model.from_dict(json.loads(result.output))
    rooms = result_model.buildings[0].unique_room_2ds
    assert rooms[0].window_parameters[0] is not None


def test_model_to_honeybee():
    input_model = './tests/json/sample_revit_model.dfjson'
    runner = CliRunner()
    result = runner.invoke(model_to_honeybee, [input_model])
    assert result.exit_code == 0

    for model_info in json.loads(result.output):
        assert os.path.isfile(model_info['full_path'])


def test_model_from_geojson():
    input_model = './tests/geojson/TestGeoJSON.geojson'
    runner = CliRunner()
    result = runner.invoke(model_from_geojson, [input_model, '-wr', '0.4'])
    assert result.exit_code == 0

    model_dict = json.loads(result.output)
    df_model = Model.from_dict(model_dict)
    assert isinstance(df_model, Model)


def test_validate_model():
    input_model = './tests/json/sample_revit_model.dfjson'
    incorrect_input_model = './tests/json/bad_adjacency_model.dfjson'
    if (sys.version_info >= (3, 7)):
        runner = CliRunner()
        result = runner.invoke(validate_model, [input_model])
        assert result.exit_code == 0
        runner = CliRunner()
        result = runner.invoke(validate_model, [incorrect_input_model])
        outp = result.output
        assert 'Your Model is invalid for the following reasons' in outp
        assert 'does not have a Surface boundary condition' in outp


def test_validate_model_json():
    input_model = './tests/json/sample_revit_model.dfjson'
    incorrect_input_model = './tests/json/bad_adjacency_model.dfjson'
    if (sys.version_info >= (3, 7)):
        runner = CliRunner()
        result = runner.invoke(validate_model, [input_model, '--json'])
        assert result.exit_code == 0
        outp = result.output
        valid_report = json.loads(outp)
        assert valid_report['valid']
        runner = CliRunner()
        result = runner.invoke(validate_model, [incorrect_input_model, '--json'])
        outp = result.output
        valid_report = json.loads(outp)
        assert not valid_report['valid']
        assert len(valid_report['errors']) != 0
