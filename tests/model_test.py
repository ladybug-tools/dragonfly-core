# coding=utf-8
import pytest
import json
import os

from ladybug.location import Location
from ladybug_geometry.geometry2d import Vector2D, Point2D, LineSegment2D, \
    Polyline2D, Polygon2D
from ladybug_geometry.geometry3d import Point3D, Vector3D, Plane, Face3D
from ladybug.futil import nukedir

import honeybee.model as hb_model
from honeybee.room import Room
from honeybee.shade import Shade
from honeybee.facetype import RoofCeiling
from honeybee.boundarycondition import Surface, Outdoors

from dragonfly.model import Model
from dragonfly.building import Building
from dragonfly.story import Story
from dragonfly.room2d import Room2D
from dragonfly.context import ContextShade
from dragonfly.windowparameter import SimpleWindowRatio
from dragonfly.projection import meters_to_long_lat_factors


def test_model_init():
    """Test the initialization of Model objects and basic properties."""
    pts_1 = (Point3D(0, 0, 3), Point3D(0, 10, 3), Point3D(10, 10, 3), Point3D(10, 0, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(20, 10, 3), Point3D(20, 0, 3))
    pts_3 = (Point3D(0, 10, 3), Point3D(0, 20, 3), Point3D(10, 20, 3), Point3D(10, 10, 3))
    pts_4 = (Point3D(10, 10, 3), Point3D(10, 20, 3), Point3D(20, 20, 3), Point3D(20, 10, 3))
    room2d_1 = Room2D('Office1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office2', Face3D(pts_2), 3)
    room2d_3 = Room2D('Office3', Face3D(pts_3), 3)
    room2d_4 = Room2D('Office4', Face3D(pts_4), 3)
    story = Story('Office_Floor', [room2d_1, room2d_2, room2d_3, room2d_4])
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.multiplier = 4
    building = Building('Office_Building', [story])

    tree_canopy_geo1 = Face3D.from_regular_polygon(6, 6, Plane(o=Point3D(5, -10, 6)))
    tree_canopy_geo2 = Face3D.from_regular_polygon(6, 2, Plane(o=Point3D(-5, -10, 3)))
    tree_canopy = ContextShade('Tree_Canopy', [tree_canopy_geo1, tree_canopy_geo2])

    model = Model('New_Development', [building], [tree_canopy])
    str(model)  # test the string representation of the object

    assert model.identifier == 'New_Development'
    assert model.display_name == 'New_Development'
    assert model.units == 'Meters'
    assert model.tolerance == 0.01
    assert model.angle_tolerance == 1.0
    assert len(model.buildings) == 1
    assert isinstance(model.buildings[0], Building)
    assert len(model.context_shades) == 1
    assert isinstance(model.context_shades[0], ContextShade)

    assert model.average_story_count == 4
    assert model.average_story_count_above_ground == 4
    assert model.average_height == 15
    assert model.average_height_above_ground == 12
    assert model.footprint_area == 100 * 4
    assert model.floor_area == 100 * 4 * 4
    assert model.exterior_wall_area == 60 * 4 * 4
    assert model.exterior_aperture_area == 60 * 4 * 4 * 0.4
    assert model.volume == 100 * 3 * 4 * 4
    assert model.min.x == pytest.approx(-6.73, rel=1e-2)
    assert model.min.y == pytest.approx(-16, rel=1e-2)
    assert model.max == Point2D(20, 20)


def test_properties():
    """Test various properties on the model."""
    pts_1 = (Point3D(0, 0, 3), Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(0, 10, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(20, 0, 3), Point3D(20, 10, 3), Point3D(10, 10, 3))
    pts_3 = (Point3D(0, 20, 3), Point3D(20, 20, 3), Point3D(20, 30, 3), Point3D(0, 30, 3))
    room2d_1 = Room2D('Office1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office2', Face3D(pts_2), 3)
    room2d_3 = Room2D('Office3', Face3D(pts_3), 3)
    story_big = Story('OfficeFloorBig', [room2d_3])
    story = Story('OfficeFloor', [room2d_1, room2d_2])
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.multiplier = 4
    building = Building('OfficeBuilding', [story])
    story_big.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story_big.multiplier = 2
    building_big = Building('OfficeBuildingBig', [story_big])

    model = Model('NewDevelopment', [building, building_big])

    assert model.average_story_count == 3
    assert model.average_story_count_above_ground == 3
    assert model.average_height == 12
    assert model.average_height_above_ground == 9
    assert model.footprint_area == 100 * 4
    assert model.floor_area == (100 * 2 * 4) + (200 * 2)
    assert model.exterior_wall_area == (90 * 2 * 4) + (180 * 2)
    assert model.exterior_aperture_area == (90 * 2 * 4 * 0.4) + (180 * 2 * 0.4)
    assert model.volume == (100 * 2 * 4 * 3) + (200 * 2 * 3)


def test_model_properties_setability():
    """Test the setting of properties on the Model."""
    pts_1 = (Point3D(0, 0, 3), Point3D(0, 10, 3), Point3D(10, 10, 3), Point3D(10, 0, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(20, 10, 3), Point3D(20, 0, 3))
    pts_3 = (Point3D(0, 10, 3), Point3D(0, 20, 3), Point3D(10, 20, 3), Point3D(10, 10, 3))
    pts_4 = (Point3D(10, 10, 3), Point3D(10, 20, 3), Point3D(20, 20, 3), Point3D(20, 10, 3))
    room2d_1 = Room2D('Office1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office2', Face3D(pts_2), 3)
    room2d_3 = Room2D('Office3', Face3D(pts_3), 3)
    room2d_4 = Room2D('Office4', Face3D(pts_4), 3)
    story = Story('OfficeFloor', [room2d_1, room2d_2, room2d_3, room2d_4])
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.multiplier = 4
    building = Building('OfficeBuilding', [story])

    model = Model('NewDevelopment', [building])
    model.to_rectangular_windows()

    model.display_name = 'TestBuilding'
    assert model.display_name == 'TestBuilding'
    model.units = 'Feet'
    assert model.units == 'Feet'
    model.tolerance = 0.1
    assert model.tolerance == 0.1
    model.angle_tolerance = 0.01
    assert model.angle_tolerance == 0.01
    model.tolerance = 0.01
    assert model.tolerance == 0.01


def test_model_add_objects():
    """Test the addition of objects to a Model and getting objects by identifier."""
    pts_1 = (Point3D(0, 0, 3), Point3D(0, 10, 3), Point3D(10, 10, 3), Point3D(10, 0, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(20, 10, 3), Point3D(20, 0, 3))
    pts_3 = (Point3D(0, 20, 3), Point3D(0, 30, 3), Point3D(10, 30, 3), Point3D(10, 20, 3))
    pts_4 = (Point3D(10, 20, 3), Point3D(10, 30, 3), Point3D(20, 30, 3), Point3D(20, 20, 3))
    room2d_1 = Room2D('Office1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office2', Face3D(pts_2), 3)
    room2d_3 = Room2D('Office3', Face3D(pts_3), 3)
    room2d_4 = Room2D('Office4', Face3D(pts_4), 3)
    story_1 = Story('OfficeFloor1', [room2d_1, room2d_2])
    story_2 = Story('OfficeFloor2', [room2d_3, room2d_4])
    story_1.solve_room_2d_adjacency(0.01)
    story_1.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story_1.multiplier = 4
    story_2.solve_room_2d_adjacency(0.01)
    story_2.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story_2.multiplier = 2
    building_1 = Building('OfficeBuilding1', [story_1])
    building_2 = Building('OfficeBuilding2', [story_2])

    tree_canopy_geo1 = Face3D.from_regular_polygon(6, 6, Plane(o=Point3D(5, -10, 6)))
    tree_canopy_geo2 = Face3D.from_regular_polygon(6, 2, Plane(o=Point3D(-5, -10, 3)))
    tree_canopy_1 = ContextShade('TreeCanopy1', [tree_canopy_geo1])
    tree_canopy_2 = ContextShade('TreeCanopy2', [tree_canopy_geo2])

    model = Model('NewDevelopment', [building_1], [tree_canopy_1])
    assert len(model.buildings) == 1
    assert len(model.context_shades) == 1
    with pytest.raises(AssertionError):
        model.add_building(tree_canopy_2)
    model.add_building(building_2)
    assert len(model.buildings) == 2
    with pytest.raises(AssertionError):
        model.add_context_shade(building_2)
    model.add_context_shade(tree_canopy_2)
    assert len(model.context_shades) == 2

    assert len(model.buildings_by_identifier(['OfficeBuilding1'])) == 1
    with pytest.raises(ValueError):
        model.buildings_by_identifier(['NotABuilding'])
    assert len(model.context_shade_by_identifier(['TreeCanopy1'])) == 1
    with pytest.raises(ValueError):
        model.context_shade_by_identifier(['NotAShade'])


def test_model_add_model():
    """Test the addition of one Model to another."""
    pts_1 = (Point3D(0, 0, 3), Point3D(0, 10, 3), Point3D(10, 10, 3), Point3D(10, 0, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(20, 10, 3), Point3D(20, 0, 3))
    pts_3 = (Point3D(0, 20, 3), Point3D(0, 30, 3), Point3D(10, 30, 3), Point3D(10, 20, 3))
    pts_4 = (Point3D(10, 20, 3), Point3D(10, 30, 3), Point3D(20, 30, 3), Point3D(20, 20, 3))
    room2d_1 = Room2D('Office1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office2', Face3D(pts_2), 3)
    room2d_3 = Room2D('Office3', Face3D(pts_3), 3)
    room2d_4 = Room2D('Office4', Face3D(pts_4), 3)
    story_1 = Story('OfficeFloor1', [room2d_1, room2d_2])
    story_2 = Story('OfficeFloor2', [room2d_3, room2d_4])
    story_1.solve_room_2d_adjacency(0.01)
    story_1.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story_1.multiplier = 4
    story_2.solve_room_2d_adjacency(0.01)
    story_2.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story_2.multiplier = 2
    building_1 = Building('OfficeBuilding1', [story_1])
    building_2 = Building('OfficeBuilding2', [story_2])

    tree_canopy_geo1 = Face3D.from_regular_polygon(6, 6, Plane(o=Point3D(5, -10, 6)))
    tree_canopy_geo2 = Face3D.from_regular_polygon(6, 2, Plane(o=Point3D(-5, -10, 3)))
    tree_canopy_1 = ContextShade('TreeCanopy1', [tree_canopy_geo1])
    tree_canopy_2 = ContextShade('TreeCanopy2', [tree_canopy_geo2])

    model_1 = Model('NewDevelopment1', [building_1], [tree_canopy_1])
    model_2 = Model('NewDevelopment2', [building_2], [tree_canopy_2])

    assert len(model_1.buildings) == 1
    assert len(model_1.context_shades) == 1
    assert len(model_2.buildings) == 1
    assert len(model_2.context_shades) == 1

    combined_model = model_1 + model_2
    assert len(combined_model.buildings) == 2
    assert len(combined_model.context_shades) == 2

    assert len(model_1.buildings) == 1
    assert len(model_1.context_shades) == 1
    model_1 += model_2
    assert len(model_1.buildings) == 2
    assert len(model_1.context_shades) == 2

    # check that duplicated ids are handled
    model_3 = Model('NewDevelopment3', [building_1], [tree_canopy_1])
    model_4 = Model('NewDevelopment4', [building_1], [tree_canopy_1])
    assert len(model_3.buildings) == 1
    assert len(model_3.context_shades) == 1
    assert len(model_4.buildings) == 1
    assert len(model_4.context_shades) == 1
    combined_model = model_3 + model_4
    assert len(combined_model.buildings) == 1
    assert len(combined_model.stories) == 1
    assert len(combined_model.room_2ds) == 2
    assert len(combined_model.context_shades) == 1


def test_model_add_prefix():
    """Test the Model.add_prefix method."""
    pts_1 = (Point3D(0, 0, 3), Point3D(0, 10, 3), Point3D(10, 10, 3), Point3D(10, 0, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(20, 10, 3), Point3D(20, 0, 3))
    pts_3 = (Point3D(0, 10, 3), Point3D(0, 20, 3), Point3D(10, 20, 3), Point3D(10, 10, 3))
    pts_4 = (Point3D(10, 10, 3), Point3D(10, 20, 3), Point3D(20, 20, 3), Point3D(20, 10, 3))
    room2d_1 = Room2D('Office1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office2', Face3D(pts_2), 3)
    room2d_3 = Room2D('Office3', Face3D(pts_3), 3)
    room2d_4 = Room2D('Office4', Face3D(pts_4), 3)
    story = Story('Office_Floor', [room2d_1, room2d_2, room2d_3, room2d_4])
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.multiplier = 4
    building = Building('Office_Building', [story])

    tree_canopy_geo1 = Face3D.from_regular_polygon(6, 6, Plane(o=Point3D(5, -10, 6)))
    tree_canopy_geo2 = Face3D.from_regular_polygon(6, 2, Plane(o=Point3D(-5, -10, 3)))
    tree_canopy = ContextShade('Tree_Canopy', [tree_canopy_geo1, tree_canopy_geo2])

    model = Model('Development', [building], [tree_canopy])
    prefix = 'New'
    model.add_prefix(prefix)

    assert building.identifier.startswith(prefix)
    for story in building.unique_stories:
        assert story.identifier.startswith(prefix)
        for rm in story.room_2ds:
            assert rm.identifier.startswith(prefix)
    for shd in model.context_shades:
        assert shd.identifier.startswith(prefix)


def test_reset_ids():
    """Test the reset_ids method."""
    model_json = './tests/json/model_with_doors_skylights.dfjson'
    parsed_model = Model.from_dfjson(model_json)

    new_model = parsed_model.duplicate()
    new_model.reset_ids(True)

    assert new_model.room_2ds[0].identifier != parsed_model.room_2ds[0].identifier
    assert new_model.check_missing_adjacencies() == ''


def test_move():
    """Test the Model move method."""
    pts_1 = (Point3D(0, 0, 3), Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(0, 10, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(20, 0, 3), Point3D(20, 10, 3), Point3D(10, 10, 3))
    room2d_1 = Room2D('Office1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office2', Face3D(pts_2), 3)
    story = Story('OfficeFloor', [room2d_1, room2d_2])
    story.solve_room_2d_adjacency(0.01)
    story.multiplier = 4
    building = Building('OfficeBuilding', [story])
    awning_geo1 = Face3D.from_rectangle(6, 6, Plane(o=Point3D(5, -10, 6)))
    awning_geo2 = Face3D.from_rectangle(2, 2, Plane(o=Point3D(-5, -10, 3)))
    awning_canopy_1 = ContextShade('AwningCanopy1', [awning_geo1])
    awning_canopy_2 = ContextShade('AwningCanopy2', [awning_geo2])

    model = Model('NewDevelopment', [building], [awning_canopy_1, awning_canopy_2])

    vec_1 = Vector3D(2, 2, 2)
    new_m = model.duplicate()
    model.move(vec_1)
    assert model.buildings[0].unique_stories[0].room_2ds[0].floor_geometry[0] == Point3D(2, 2, 5)
    assert model.buildings[0].unique_stories[0].room_2ds[0].floor_geometry[1] == Point3D(12, 2, 5)
    assert model.buildings[0].unique_stories[0].room_2ds[0].floor_geometry[2] == Point3D(12, 12, 5)
    assert model.buildings[0].unique_stories[0].room_2ds[0].floor_geometry[3] == Point3D(2, 12, 5)
    assert model.buildings[0].unique_stories[0].room_2ds[1].floor_geometry[0] == Point3D(12, 2, 5)
    assert model.buildings[0].unique_stories[0].room_2ds[1].floor_geometry[1] == Point3D(22, 2, 5)
    assert model.buildings[0].unique_stories[0].room_2ds[1].floor_geometry[2] == Point3D(22, 12, 5)
    assert model.buildings[0].unique_stories[0].room_2ds[1].floor_geometry[3] == Point3D(12, 12, 5)
    assert model.buildings[0].floor_area == new_m.buildings[0].floor_area

    assert model.context_shades[0][0][0] == Point3D(7, -8, 8)
    assert model.context_shades[1][0][0] == Point3D(-3, -8, 5)


def test_scale():
    """Test the Model scale method."""
    pts_1 = (Point3D(0, 0, 3), Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(0, 10, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(20, 0, 3), Point3D(20, 10, 3), Point3D(10, 10, 3))
    room2d_1 = Room2D('Office1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office2', Face3D(pts_2), 3)
    story = Story('OfficeFloor', [room2d_1, room2d_2])
    story.solve_room_2d_adjacency(0.01)
    story.multiplier = 4
    building = Building('OfficeBuilding', [story])
    awning_geo1 = Face3D.from_rectangle(6, 6, Plane(o=Point3D(5, -10, 6)))
    awning_geo2 = Face3D.from_rectangle(2, 2, Plane(o=Point3D(-5, -10, 3)))
    awning_canopy_1 = ContextShade('AwningCanopy1', [awning_geo1])
    awning_canopy_2 = ContextShade('AwningCanopy2', [awning_geo2])

    model = Model('NewDevelopment', [building], [awning_canopy_1, awning_canopy_2])

    new_m = model.duplicate()
    new_m.scale(2)
    assert new_m.buildings[0].unique_stories[0].room_2ds[0].floor_geometry[0] == Point3D(0, 0, 6)
    assert new_m.buildings[0].unique_stories[0].room_2ds[0].floor_geometry[1] == Point3D(20, 0, 6)
    assert new_m.buildings[0].unique_stories[0].room_2ds[0].floor_geometry[2] == Point3D(20, 20, 6)
    assert new_m.buildings[0].unique_stories[0].room_2ds[0].floor_geometry[3] == Point3D(0, 20, 6)
    assert new_m.buildings[0].unique_stories[0].room_2ds[1].floor_geometry[0] == Point3D(20, 0, 6)
    assert new_m.buildings[0].unique_stories[0].room_2ds[1].floor_geometry[1] == Point3D(40, 0, 6)
    assert new_m.buildings[0].unique_stories[0].room_2ds[1].floor_geometry[2] == Point3D(40, 20, 6)
    assert new_m.buildings[0].unique_stories[0].room_2ds[1].floor_geometry[3] == Point3D(20, 20, 6)
    assert new_m.buildings[0].floor_area == building.floor_area * 2 ** 2

    assert new_m.context_shades[0][0][0] == Point3D(10, -20, 12)
    assert new_m.context_shades[1][0][0] == Point3D(-10, -20, 6)


def test_convert_to_units():
    """Test the Model convert_to_units method."""
    pts_1 = (Point3D(0, 0), Point3D(120, 0), Point3D(120, 120), Point3D(0, 120))
    pts_2 = (Point3D(120, 0), Point3D(240, 0), Point3D(240, 120), Point3D(120, 120))
    room2d_1 = Room2D('Office1', Face3D(pts_1), 96)
    room2d_2 = Room2D('Office2', Face3D(pts_2), 96)
    story = Story('OfficeFloor', [room2d_1, room2d_2])
    story.solve_room_2d_adjacency(0.01)
    story.multiplier = 4
    building = Building('OfficeBuilding', [story])
    model = Model('NewDevelopment', [building], units='Inches')

    inches_conversion = hb_model.Model.conversion_factor_to_meters('Inches')
    model.convert_to_units('Meters')

    assert room2d_1.floor_area == pytest.approx(120 * 120 * (inches_conversion ** 2), rel=1e-3)
    assert room2d_1.volume == pytest.approx(120 * 120 * 96 * (inches_conversion ** 3), rel=1e-3)
    assert model.units == 'Meters'


def test_rotate_xy():
    """Test the Model rotate_xy method."""
    pts = (Point3D(1, 1, 2), Point3D(2, 1, 2), Point3D(2, 2, 2), Point3D(1, 2, 2))
    plane = Plane(Vector3D(0, 0, 1), Point3D(0, 0, 2))
    room = Room2D('SquareShoebox', Face3D(pts, plane), 3)
    story = Story('OfficeFloor', [room])
    story.multiplier = 4
    building = Building('OfficeBuilding', [story])
    pts = (Point3D(1, 1, 2), Point3D(2, 1, 2), Point3D(2, 2, 2), Point3D(1, 2, 2))
    plane_1 = Plane(Vector3D(0, 0, 1), Point3D(0, 0, 0))
    awning_canopy = ContextShade('AwningCanopy', [Face3D(pts, plane_1)])

    model = Model('NewDevelopment', [building], [awning_canopy])

    origin_1 = Point3D(1, 1, 0)
    test_1 = model.duplicate()
    test_1.rotate_xy(180, origin_1)
    assert test_1.buildings[0].unique_stories[0].room_2ds[0].floor_geometry[0].x == \
        pytest.approx(1, rel=1e-3)
    assert test_1.buildings[0].unique_stories[0].room_2ds[0].floor_geometry[0].y == \
        pytest.approx(1, rel=1e-3)
    assert test_1.buildings[0].unique_stories[0].room_2ds[0].floor_geometry[0].z == \
        pytest.approx(2, rel=1e-3)
    assert test_1.buildings[0].unique_stories[0].room_2ds[0].floor_geometry[2].x == \
        pytest.approx(0, rel=1e-3)
    assert test_1.buildings[0].unique_stories[0].room_2ds[0].floor_geometry[2].y == \
        pytest.approx(0, rel=1e-3)
    assert test_1.buildings[0].unique_stories[0].room_2ds[0].floor_geometry[2].z == \
        pytest.approx(2, rel=1e-3)

    assert test_1.context_shades[0][0][0].x == pytest.approx(1, rel=1e-3)
    assert test_1.context_shades[0][0][0].y == pytest.approx(1, rel=1e-3)
    assert test_1.context_shades[0][0][0].z == pytest.approx(2, rel=1e-3)
    assert test_1.context_shades[0][0][2].x == pytest.approx(0, rel=1e-3)
    assert test_1.context_shades[0][0][2].y == pytest.approx(0, rel=1e-3)
    assert test_1.context_shades[0][0][2].z == pytest.approx(2, rel=1e-3)


def test_reflect():
    """Test the Model reflect method."""
    pts = (Point3D(1, 1, 2), Point3D(2, 1, 2), Point3D(2, 2, 2), Point3D(1, 2, 2))
    plane = Plane(Vector3D(0, 0, 1), Point3D(0, 0, 2))
    room = Room2D('SquareShoebox', Face3D(pts, plane), 3)
    story = Story('OfficeFloor', [room])
    story.multiplier = 4
    building = Building('OfficeBuilding', [story])
    pts = (Point3D(1, 1, 2), Point3D(2, 1, 2), Point3D(2, 2, 2), Point3D(1, 2, 2))
    plane = Plane(Vector3D(0, 0, 1), Point3D(0, 0, 2))
    awning_canopy = ContextShade('AwningCanopy', [Face3D(pts, plane)])

    model = Model('NewDevelopment', [building], [awning_canopy])

    origin_1 = Point3D(1, 0, 2)
    normal_1 = Vector3D(1, 0, 0)
    plane_1 = Plane(normal_1, origin_1)

    test_1 = model.duplicate()
    test_1.reflect(plane_1)
    assert test_1.buildings[0].unique_stories[0].room_2ds[0].floor_geometry[-1].x == \
        pytest.approx(1, rel=1e-3)
    assert test_1.buildings[0].unique_stories[0].room_2ds[0].floor_geometry[-1].y == \
        pytest.approx(1, rel=1e-3)
    assert test_1.buildings[0].unique_stories[0].room_2ds[0].floor_geometry[-1].z == \
        pytest.approx(2, rel=1e-3)
    assert test_1.buildings[0].unique_stories[0].room_2ds[0].floor_geometry[1].x == \
        pytest.approx(0, rel=1e-3)
    assert test_1.buildings[0].unique_stories[0].room_2ds[0].floor_geometry[1].y == \
        pytest.approx(2, rel=1e-3)
    assert test_1.buildings[0].unique_stories[0].room_2ds[0].floor_geometry[1].z == \
        pytest.approx(2, rel=1e-3)

    assert test_1.context_shades[0][0][-1].x == pytest.approx(1, rel=1e-3)
    assert test_1.context_shades[0][0][-1].y == pytest.approx(1, rel=1e-3)
    assert test_1.context_shades[0][0][-1].z == pytest.approx(2, rel=1e-3)
    assert test_1.context_shades[0][0][1].x == pytest.approx(0, rel=1e-3)
    assert test_1.context_shades[0][0][1].y == pytest.approx(2, rel=1e-3)
    assert test_1.context_shades[0][0][1].z == pytest.approx(2, rel=1e-3)


def test_reset_room_2d_boundaries():
    """Test the reset_room_2d_boundaries method on Stories."""
    model_file = './tests/json/model_with_doors_skylights.dfjson'
    model = Model.from_file(model_file)
    bound_dict = {
        "type": "Polygon2D",
        "vertices": [
            [-4.8880684825623826, -3.3025939785814966],
            [13.162931517437627, -3.3025939785814966],
            [13.162931517437627, 2.8994060214182316],
            [-4.8880684825623826, 2.8994060214182316]
        ]
    }
    story_bnd = [Polygon2D.from_dict(bound_dict)]

    second_story = model.stories[1]
    new_story = second_story.duplicate()
    new_story.reset_room_2d_boundaries(story_bnd)

    assert len(new_story.room_2ds) == 1
    assert len(new_story.room_2ds[0].skylight_parameters) == 2
    assert second_story.exterior_aperture_area == \
        pytest.approx(new_story.exterior_aperture_area, rel=1e-3)


def test_room_2ds_pulling_methods():
    """Test the methods that pull Room2Ds to target objects."""
    model_file = './tests/json/model_for_pulling.dfjson'
    original_model = Model.from_file(model_file)

    model = original_model.duplicate()
    all_rooms = model.room_2ds
    all_rooms[1].pull_to_room_2d(all_rooms[0], 1.8)
    all_rooms[1].remove_duplicate_vertices(model.tolerance)
    all_rooms = Room2D.intersect_adjacency([all_rooms[0], all_rooms[1]], model.tolerance)
    Room2D.solve_adjacency(all_rooms, model.tolerance)
    assert all_rooms[0].interior_wall_area == pytest.approx(474.199, rel=1e-3)
    assert all_rooms[1].interior_wall_area == pytest.approx(474.199, rel=1e-3)

    model = original_model.duplicate()
    all_rooms = list(model.room_2ds)
    p_line_dict = {
        "vertices": [
            [41.948730157743668, -158.55282855259856],
            [40.342412085619216, -155.436554667964],
            [38.964213381250516, -152.21289386009886],
            [37.266824978903102, -146.93482869788193],
            [36.179711222359543, -141.49816768901238],
            [35.716933133643359, -135.97323007075525],
            [35.884476409153223, -130.43147687380934],
            [36.545268095082271, -125.63224336825779],
            [38.495343179376093, -118.87011597488173],
            [42.69922884129204, -107.96430429448071]
        ],
        "type": "Polyline2D"
    }
    p_line = Polyline2D.from_dict(p_line_dict)
    for i, room in enumerate(all_rooms):
        room.pull_to_polyline(p_line, 1.8)
        all_rooms[i] = room.remove_colinear_vertices(model.tolerance)
    all_rooms = Room2D.intersect_adjacency(all_rooms, model.tolerance)
    Room2D.solve_adjacency(all_rooms, model.tolerance)
    assert all_rooms[0].interior_wall_area == pytest.approx(659.7238, rel=1e-3)
    assert all_rooms[1].interior_wall_area == pytest.approx(1088.794, rel=1e-3)
    assert all_rooms[2].interior_wall_area == pytest.approx(801.180, rel=1e-3)

    model = original_model.duplicate()
    all_rooms = list(model.room_2ds)
    line_seg = LineSegment2D.from_end_points(p_line[0], p_line[1])
    for i, room in enumerate(all_rooms):
        room.snap_to_line_end_points(line_seg, 1.8)
        all_rooms[i] = room.remove_colinear_vertices(model.tolerance)


def test_join_room_2ds():
    """Test the Room2d.join_room_2ds method."""
    model_file = './tests/json/model_with_doors_skylights.dfjson'
    model = Model.from_file(model_file)

    second_story = model.stories[1]
    joined_rooms = Room2D.join_room_2ds(second_story.room_2ds)

    assert len(joined_rooms) == 1
    assert len(joined_rooms[0].skylight_parameters) == 2
    assert second_story.exterior_aperture_area == \
        pytest.approx(joined_rooms[0].exterior_aperture_area, rel=1e-3)

    clean_joined_room = joined_rooms[0].remove_colinear_vertices()
    cp_rooms = clean_joined_room.to_core_perimeter(2)
    assert len(cp_rooms) == 5
    clean_ap_area = sum(r.exterior_aperture_area for r in cp_rooms)
    assert second_story.exterior_aperture_area == pytest.approx(clean_ap_area, rel=1e-3)


def test_join_room_2ds_separation():
    """Test the Room2d.join_room_2ds method with a separation distance."""
    model_file = './tests/json/model_with_with_separation.dfjson'
    model = Model.from_file(model_file)

    second_story = model.stories[0]
    joined_room_2ds = Room2D.join_room_2ds(
        second_story.room_2ds, min_separation=0.3, tolerance=model.tolerance)
    assert len(joined_room_2ds) == 1
    joined_room = joined_room_2ds[0]
    window_count = sum(1 for wp in joined_room.window_parameters if wp is not None)
    assert window_count == 7
    assert len(joined_room.skylight_parameters) == 2


def test_suggested_alignment_axes():
    """Test the suggested_alignment_axes method on Buildings and Stories."""
    model_file = './tests/json/model_with_doors_skylights.dfjson'
    model = Model.from_file(model_file)

    bldg = model.buildings[0]
    common_axes, axes_weights = bldg.suggested_alignment_axes(0.03)
    assert len(common_axes) == len(axes_weights)
    assert max(axes_weights) > 5

    story = bldg.unique_stories[0]
    common_axes, axes_weights = story.suggested_alignment_axes(0.03)
    assert len(common_axes) == len(axes_weights)
    assert max(axes_weights) < 5


def test_skylight_merge_and_simplify():
    """Test the merge_and_simplify method."""
    model_file = './tests/json/Room_with_complex_skylights.dfjson'
    model = Model.from_file(model_file)
    room = model.room_2ds[0]
    assert len(room.skylight_parameters) == 5

    new_room = room.duplicate()
    new_room.skylight_parameters.merge_and_simplify(0.1)
    assert len(new_room.skylight_parameters) == 3

    new_room = room.duplicate()
    new_room.skylight_parameters.merge_and_simplify(0.5)
    assert len(new_room.skylight_parameters) == 2


def test_skylight_merge_to_bounding_rectangle():
    """Test the merge_to_bounding_rectangle method."""
    model_file = './tests/json/overlapping_skylights.dfjson'
    model = Model.from_file(model_file)
    room = model.room_2ds[0]
    assert len(room.skylight_parameters) == 42

    new_room = room.duplicate()
    assert len(new_room.skylight_parameters) == 42
    new_room.skylight_parameters.merge_and_simplify(0.01, 0.01)
    assert len(new_room.skylight_parameters) == 12
    new_room.skylight_parameters.union_overlaps(0.01)
    assert len(new_room.skylight_parameters) == 3

    new_room = room.duplicate()
    assert len(new_room.skylight_parameters) == 42
    new_room.skylight_parameters.merge_to_bounding_rectangle(0.01)
    assert len(new_room.skylight_parameters) == 3


def test_snap_to_grid():
    """Test the snap_to_grid method on Room2Ds."""
    model_file = './tests/json/Level03.dfjson'
    model = Model.from_file(model_file)

    assert len(model.room_2ds) == 180
    for room in model.room_2ds:
        room.snap_to_grid(0.1)
        room .reset_adjacency()
    assert len(model.room_2ds) == 180


def test_process_alleys():
    """Test the Building.process_alleys method."""
    model_file = './tests/json/alleyway_detailed.dfjson'
    model = Model.from_file(model_file)
    Building.process_alleys(model.buildings, adiabatic=True)

    ad_count = 0
    for story in model.buildings[0]:
        for room in story:
            for bc in room.boundary_conditions:
                if not isinstance(bc, (Outdoors, Surface)):
                    ad_count += 1
    assert ad_count == 2

    ad_count = 0
    for story in model.buildings[1]:
        for room in story:
            for bc in room.boundary_conditions:
                if not isinstance(bc, (Outdoors, Surface)):
                    ad_count += 1
    assert ad_count == 2


def test_check_duplicate_identifiers():
    """Test check_duplicate_building_identifiers."""
    pts_1 = (Point3D(0, 0, 3), Point3D(0, 10, 3), Point3D(10, 10, 3), Point3D(10, 0, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(20, 10, 3), Point3D(20, 0, 3))
    pts_3 = (Point3D(0, 20, 3), Point3D(0, 30, 3), Point3D(10, 30, 3), Point3D(10, 20, 3))
    pts_4 = (Point3D(10, 20, 3), Point3D(10, 30, 3), Point3D(20, 30, 3), Point3D(20, 20, 3))
    room2d_1 = Room2D('Office1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office2', Face3D(pts_2), 3)
    room2d_3 = Room2D('Office1', Face3D(pts_3), 3)
    room2d_4 = Room2D('Office2', Face3D(pts_4), 3)
    story_1 = Story('OfficeFloor1', [room2d_1, room2d_2])
    story_2 = Story('OfficeFloor2', [room2d_3, room2d_4])
    story_1.solve_room_2d_adjacency(0.01)
    story_1.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story_1.multiplier = 4
    story_2.solve_room_2d_adjacency(0.01)
    story_2.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story_2.multiplier = 2
    building_1 = Building('OfficeBuilding', [story_1])
    building_2 = Building('OfficeBuilding', [story_2])

    tree_canopy_geo1 = Face3D.from_regular_polygon(6, 6, Plane(o=Point3D(5, -10, 6)))
    tree_canopy_geo2 = Face3D.from_regular_polygon(6, 2, Plane(o=Point3D(-5, -10, 3)))
    tree_canopy_1 = ContextShade('TreeCanopy', [tree_canopy_geo1])
    tree_canopy_2 = ContextShade('TreeCanopy', [tree_canopy_geo2])

    model_1 = Model('NewDevelopment1', [building_1], [tree_canopy_1])

    assert model_1.check_duplicate_building_identifiers(False) == ''
    assert model_1.check_duplicate_context_shade_identifiers(False) == ''

    model_1.add_building(building_2)
    model_1.add_context_shade(tree_canopy_2)
    assert model_1.check_duplicate_room_2d_identifiers(False) != ''
    with pytest.raises(ValueError):
        model_1.check_duplicate_room_2d_identifiers(True)
    assert model_1.check_duplicate_context_shade_identifiers(False) != ''
    with pytest.raises(ValueError):
        model_1.check_duplicate_context_shade_identifiers(True)

    model_1.resolve_id_collisions()
    assert model_1.check_duplicate_room_2d_identifiers(False) == ''
    assert model_1.check_duplicate_context_shade_identifiers(False) == ''

    model_2 = Model('NewDevelopment1', [building_1, building_2], [tree_canopy_1])
    assert model_2.check_duplicate_building_identifiers(False) != ''
    with pytest.raises(ValueError):
        model_2.check_duplicate_building_identifiers(True)

    model_2.resolve_id_collisions()
    assert model_1.check_duplicate_building_identifiers(False) == ''


def test_to_honeybee():
    """Test the to_honeybee method."""
    pts_1 = (Point3D(0, 0, 3), Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(0, 10, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(20, 0, 3), Point3D(20, 10, 3), Point3D(10, 10, 3))
    pts_3 = (Point3D(0, 20, 3), Point3D(20, 20, 3), Point3D(20, 30, 3), Point3D(0, 30, 3))
    room2d_1 = Room2D('Office1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office2', Face3D(pts_2), 3)
    room2d_3 = Room2D('Office3', Face3D(pts_3), 3)
    story_big = Story('OfficeFloorBig', [room2d_3])
    story = Story('OfficeFloor', [room2d_1, room2d_2])
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.multiplier = 4
    building = Building('OfficeBuilding', [story])
    story_big.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story_big.multiplier = 4
    building_big = Building('OfficeBuildingBig', [story_big])

    tree_canopy_geo1 = Face3D.from_regular_polygon(6, 6, Plane(o=Point3D(5, -10, 6)))
    tree_canopy_geo2 = Face3D.from_regular_polygon(6, 2, Plane(o=Point3D(-5, -10, 3)))
    tree_canopy = ContextShade('TreeCanopy', [tree_canopy_geo1, tree_canopy_geo2])

    model = Model('NewDevelopment', [building, building_big], [tree_canopy])

    hb_models = model.to_honeybee('District', None, False, tolerance=0.01)
    assert len(hb_models) == 1
    assert isinstance(hb_models[0], hb_model.Model)
    assert len(hb_models[0].rooms) == 12
    assert len(hb_models[0].rooms[-1]) == 6
    assert hb_models[0].rooms[-1].volume == 600
    assert hb_models[0].rooms[-1].floor_area == 200
    assert hb_models[0].rooms[-1].exterior_wall_area == 180
    assert len(hb_models[0].orphaned_shades) == 2

    hb_models = model.to_honeybee('Building', None, False, tolerance=0.01)
    assert len(hb_models) == 2

    hb_models = model.to_honeybee('Story', None, False, tolerance=0.01)
    assert len(hb_models) == 8
    assert all(isinstance(mod, hb_model.Model) for mod in hb_models)

    hb_models = model.to_honeybee('Story', None, True, cap=True, tolerance=0.01)
    assert len(hb_models) == 2
    assert all(isinstance(mod, hb_model.Model) for mod in hb_models)


def test_to_honeybee_multiple_models():
    """Test to_honeybee with multiple honeybee models."""
    pts_1 = (Point3D(0, 0, 3), Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(0, 10, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(20, 0, 3), Point3D(20, 10, 3), Point3D(10, 10, 3))
    pts_3 = (Point3D(0, 20, 3), Point3D(20, 20, 3), Point3D(20, 30, 3), Point3D(0, 30, 3))
    room2d_1 = Room2D('Office1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office2', Face3D(pts_2), 3)
    room2d_3 = Room2D('Office3', Face3D(pts_3), 3)
    story_big = Story('OfficeFloorBig', [room2d_3])
    story = Story('OfficeFloor', [room2d_1, room2d_2])
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.multiplier = 4
    building = Building('OfficeBuilding', [story])
    story_big.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story_big.multiplier = 4
    building_big = Building('OfficeBuildingBig', [story_big])

    tree_canopy_geo1 = Face3D.from_regular_polygon(6, 6, Plane(o=Point3D(5, -10, 6)))
    tree_canopy_geo2 = Face3D.from_regular_polygon(6, 2, Plane(o=Point3D(-5, -10, 3)))
    tree_canopy = ContextShade('TreeCanopy', [tree_canopy_geo1, tree_canopy_geo2])

    model = Model('NewDevelopment', [building, building_big], [tree_canopy])

    hb_models = model.to_honeybee('Building', 10, False, tolerance=0.01)
    assert len(hb_models) == 2
    assert isinstance(hb_models[0], hb_model.Model)
    assert isinstance(hb_models[-1], hb_model.Model)
    assert len(hb_models[-1].rooms) == 4
    assert len(hb_models[-1].rooms[-1]) == 6
    assert hb_models[-1].rooms[-1].volume == 600
    assert hb_models[-1].rooms[-1].floor_area == 200
    assert hb_models[-1].rooms[-1].exterior_wall_area == 180
    assert len(hb_models[0].orphaned_shades) == 6
    assert len(hb_models[-1].orphaned_shades) == 6


def test_to_honeybee_missing_adjacency():
    """Test the to_honeybee method with a missing adjacency."""
    pts_1 = (Point3D(0, 0, 3), Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(0, 10, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(20, 0, 3), Point3D(20, 10, 3), Point3D(10, 10, 3))
    pts_3 = (Point3D(0, 20, 3), Point3D(20, 20, 3), Point3D(20, 30, 3), Point3D(0, 30, 3))
    room2d_1 = Room2D('Office1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office2', Face3D(pts_2), 3)
    room2d_3 = Room2D('Office3', Face3D(pts_3), 3)
    story_big = Story('OfficeFloorBig', [room2d_3])
    Room2D.solve_adjacency([room2d_1, room2d_2])
    story = Story('OfficeFloor', [room2d_1])
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.multiplier = 4
    building = Building('OfficeBuilding', [story])
    story_big.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story_big.multiplier = 4
    building_big = Building('OfficeBuildingBig', [story_big])

    model = Model('NewDevelopment', [building, building_big])

    hb_models = model.to_honeybee('District', None, False, tolerance=0.01)

    assert len(hb_models) == 1
    assert isinstance(hb_models[0], hb_model.Model)


def test_remove_colinear_vertices_edge_case():
    """Test the remove_colinear_vertices method with an edge case."""
    model_file = './tests/json/room_for_remove_colinear.dfjson'
    model = Model.from_file(model_file)
    test_room = model.buildings[0][0][0]
    assert len(test_room) == 6
    assert len(test_room.window_parameters[0]) == 50
    assert test_room.window_parameters[1] is None

    cleaned_room = test_room.remove_colinear_vertices(0.01)
    assert len(cleaned_room) == 4
    assert len(cleaned_room.window_parameters[0]) == 48
    assert len(cleaned_room.window_parameters[1]) == 50


def test_to_honeybee_doors_skylights_roof():
    """Test the to_honeybee method with doors, skylights, and a sloped roof."""
    model_file = './tests/json/model_with_doors_skylights.dfjson'
    model = Model.from_file(model_file)
    upper_story = model.buildings[0][-1]
    assert upper_story.roof is not None

    hb_models = model.to_honeybee('District', None, False, tolerance=0.01)

    assert len(hb_models) == 1
    assert isinstance(hb_models[0], hb_model.Model)

    skylights = [
        f.apertures for f in hb_models[0].faces
        if isinstance(f.type, RoofCeiling) and len(f.apertures) != 0]
    assert len(skylights) == 2
    assert len(skylights[0]) == 1

    int_doors = [
        f.doors for f in hb_models[0].faces
        if isinstance(f.boundary_condition, Surface) and len(f.doors) != 0]
    assert len(int_doors) != 0

    roof_alts = [
        f.altitude for f in hb_models[0].faces
        if isinstance(f.type, RoofCeiling) and isinstance(f.boundary_condition, Outdoors)
    ]
    assert not all(89 < alt < 91 for alt in roof_alts)


def test_to_honeybee_holes_and_roof():
    """Test the to_honeybee method with doors, skylights, and a sloped roof."""
    model_file = './tests/json/model_with_roof_and_holes.dfjson'
    model = Model.from_file(model_file)
    upper_story = model.buildings[0][-1]
    assert upper_story.roof is not None

    hb_models = model.to_honeybee('District', None, False, tolerance=0.01)

    assert len(hb_models) == 1
    assert isinstance(hb_models[0], hb_model.Model)

    roof_alts = [
        f.altitude for f in hb_models[0].faces
        if isinstance(f.type, RoofCeiling) and isinstance(f.boundary_condition, Outdoors)
    ]
    assert not all(89 < alt < 91 for alt in roof_alts)


def test_to_honeybee_hip_roof():
    """Test the to_honeybee method with hip roof."""
    model_file = './tests/json/test_hip_roof.dfjson'
    model = Model.from_file(model_file)
    upper_story = model.buildings[0][-1]
    assert upper_story.roof is not None

    hb_models = model.to_honeybee('District', None, False, tolerance=0.01)
    assert len(hb_models) == 1


def test_to_honeybee_vertical_gap():
    """Test the to_honeybee method with hip roof."""
    model_file = './tests/json/roof_with_vertical_gap.dfjson'
    model = Model.from_file(model_file)
    upper_story = model.buildings[0][-1]
    assert upper_story.roof is not None

    hb_models = model.to_honeybee('District', None, False, tolerance=0.01)
    hb_room = hb_models[0].rooms[-1]
    assert hb_models[0].rooms[0].geometry.is_solid
    assert hb_room.check_self_intersecting(0.01, False) == ''


def test_to_honeybee_roof_with_dormer():
    """Test the to_honeybee method with a dormer roof."""
    model_file = './tests/json/roof_with_dormer.dfjson'
    model = Model.from_file(model_file)
    upper_story = model.buildings[0][-1]
    assert upper_story.roof is not None

    hb_models = model.to_honeybee('District', None, False, tolerance=0.01)
    assert len(hb_models[0].rooms[0].shades) == 2

    # try moving the dormer to see if it still translates successfully
    roof_polys = upper_story.roof.boundary_geometry_2d
    for i, r_poly in enumerate(roof_polys):
        if r_poly.area < 8:
            move_pt = Point2D(-6.71, -31.26)
            new_poly_pts = []
            for pt in r_poly.vertices:
                new_pt = pt if not pt.is_equivalent(move_pt, 0.01) \
                    else pt.move(Vector2D(5, 0))
                new_poly_pts.append(new_pt)
            upper_story.roof.update_geometry_2d(Polygon2D(new_poly_pts), i)

    hb_models = model.to_honeybee('District', None, False, tolerance=0.01)
    assert len(hb_models[0].rooms[0].shades) == 2


def test_to_honeybee_invalid_roof_1():
    """Test to_honeybee with an invalid roof to ensure all exceptions are caught."""
    model_file = './tests/json/invalid_roof_1.dfjson'
    model = Model.from_file(model_file)
    upper_story = model.buildings[0][-1]
    assert upper_story.roof is not None

    hb_models = model.to_honeybee('District', None, False, tolerance=0.01)
    assert len(hb_models) == 1


def test_to_honeybee_invalid_roof_2():
    """Test to_honeybee with an invalid roof to ensure all exceptions are caught."""
    model_file = './tests/json/invalid_roof_2.dfjson'
    model = Model.from_file(model_file)
    upper_story = model.buildings[0][-1]
    assert upper_story.roof is not None

    hb_models = model.to_honeybee('District', None, False, tolerance=0.01)
    assert len(hb_models) == 1


def test_model_with_room3ds():
    """Test to_honeybee with an invalid roof to ensure all exceptions are caught."""
    # load up the model
    model_file = './tests/json/model_with_room3ds.dfjson'
    model = Model.from_file(model_file)

    # test the properties with only 3D rooms in the building
    room3ds = model.buildings[0].room_3ds
    assert len(room3ds) == 10
    assert all(isinstance(r, Room) for r in room3ds)

    assert len(model.buildings) == 1
    assert isinstance(model.buildings[0], Building)

    assert model.average_story_count == 2
    assert model.average_story_count_above_ground == 2
    assert model.average_height == pytest.approx(7.5, rel=1e-2)
    assert model.average_height_above_ground == pytest.approx(7.5, rel=1e-2)
    assert model.footprint_area == pytest.approx(35 * 25, rel=1e-3)
    assert model.floor_area == pytest.approx(1334, rel=1e-3)

    assert model.exterior_wall_area == pytest.approx(784.403, rel=1e-3)
    assert model.exterior_aperture_area == pytest.approx(784.403 * 0.4, rel=1e-3)
    assert model.volume == pytest.approx(4342, rel=1e-3)
    assert isinstance(model.min, Point2D)
    assert isinstance(model.max, Point2D)

    hb_models = model.to_honeybee('District', None, False, tolerance=0.01)
    assert len(hb_models[0].rooms) == 10

    # test the properties of the model with a mix of Room2Ds and 3D Rooms
    r_ids = [r.identifier for r in model.buildings[0].room_3ds if r.story == 'Floor2']
    model.buildings[0].convert_room_3ds_to_2d(r_ids)
    new_rids = [r.identifier for r in model.buildings[0].room_3ds]
    assert r_ids != new_rids

    assert len(model.buildings[0].room_3ds) == 5
    assert len(model.buildings[0].unique_room_2ds) == 5
    assert all(isinstance(r, Room) for r in model.buildings[0].room_3ds)
    assert all(isinstance(r, Room2D) for r in model.buildings[0].unique_room_2ds)

    assert len(model.buildings) == 1
    assert isinstance(model.buildings[0], Building)

    assert model.average_story_count == 2
    assert model.average_story_count_above_ground == 2
    assert model.average_height == pytest.approx(7.5, rel=1e-2)
    assert model.average_height_above_ground == pytest.approx(7.5, rel=1e-2)
    assert model.footprint_area == pytest.approx(459.0, rel=1e-3)
    assert model.floor_area == pytest.approx(1334, rel=1e-3)

    assert model.exterior_wall_area == pytest.approx(786.099, rel=1e-3)
    assert model.exterior_aperture_area == pytest.approx(304.8396, rel=1e-3)
    assert model.volume == pytest.approx(4594.0, rel=1e-3)
    assert isinstance(model.min, Point2D)
    assert isinstance(model.max, Point2D)

    # test the model converted entirely to Room2D
    model.buildings[0].convert_all_room_3ds_to_2d(extrusion_rooms_only=False)

    assert len(model.buildings[0].room_3ds) == 0
    assert len(model.buildings[0].unique_room_2ds) == 10
    assert all(isinstance(r, Room2D) for r in model.buildings[0].unique_room_2ds)

    assert len(model.buildings) == 1
    assert isinstance(model.buildings[0], Building)

    assert model.average_story_count == 2
    assert model.average_story_count_above_ground == 2
    assert model.average_height == pytest.approx(7.5, rel=1e-2)
    assert model.average_height_above_ground == pytest.approx(7.5, rel=1e-2)
    assert model.footprint_area == pytest.approx(35 * 25, rel=1e-3)
    assert model.floor_area == pytest.approx(1334, rel=1e-3)

    assert model.exterior_wall_area == pytest.approx(772, rel=1e-3)
    assert model.exterior_aperture_area == pytest.approx(290.8, rel=1e-3)
    assert model.volume == pytest.approx(4898.5, rel=1e-3)
    assert isinstance(model.min, Point2D)
    assert isinstance(model.max, Point2D)


def test_to_dict():
    """Test the Model to_dict method."""
    pts_1 = (
        Point3D(0, 0, 3), Point3D(0, 10, 3), Point3D(10, 10, 3), Point3D(10, 0, 3))
    pts_2 = (
        Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(20, 10, 3), Point3D(20, 0, 3))
    pts_3 = (
        Point3D(0, 10, 3), Point3D(0, 20, 3), Point3D(10, 20, 3), Point3D(10, 10, 3))
    pts_4 = (
        Point3D(10, 10, 3), Point3D(10, 20, 3), Point3D(20, 20, 3), Point3D(20, 10, 3))
    room2d_1 = Room2D('Office1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office2', Face3D(pts_2), 3)
    room2d_3 = Room2D('Office3', Face3D(pts_3), 3)
    room2d_4 = Room2D('Office4', Face3D(pts_4), 3)
    story = Story('OfficeFloor', [room2d_1, room2d_2, room2d_3, room2d_4])
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.multiplier = 4
    building = Building('OfficeBuilding', [story])

    tree_canopy_geo1 = Face3D.from_regular_polygon(6, 6, Plane(o=Point3D(5, -10, 6)))
    tree_canopy_geo2 = Face3D.from_regular_polygon(6, 2, Plane(o=Point3D(-5, -10, 3)))
    tree_canopy = ContextShade('TreeCanopy', [tree_canopy_geo1, tree_canopy_geo2])

    model = Model('NewDevelopment', [building], [tree_canopy])
    model.tolerance = 0.01
    model.angle_tolerance = 1

    model_dict = model.to_dict()
    assert model_dict['type'] == 'Model'
    assert model_dict['identifier'] == 'NewDevelopment'
    assert model_dict['display_name'] == 'NewDevelopment'
    assert 'buildings' in model_dict
    assert len(model_dict['buildings']) == 1
    assert 'context_shades' in model_dict
    assert len(model_dict['context_shades']) == 1
    assert 'tolerance' in model_dict
    assert model_dict['tolerance'] == 0.01
    assert 'angle_tolerance' in model_dict
    assert model_dict['angle_tolerance'] == 1
    assert 'properties' in model_dict
    assert model_dict['properties']['type'] == 'ModelProperties'


def test_to_from_dict_methods():
    """Test the to/from dict methods."""
    pts_1 = (Point3D(0, 0, 3), Point3D(0, 10, 3), Point3D(10, 10, 3), Point3D(10, 0, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(20, 10, 3), Point3D(20, 0, 3))
    pts_3 = (Point3D(0, 10, 3), Point3D(0, 20, 3), Point3D(10, 20, 3), Point3D(10, 10, 3))
    pts_4 = (Point3D(10, 10, 3), Point3D(10, 20, 3), Point3D(20, 20, 3), Point3D(20, 10, 3))
    room2d_1 = Room2D('Office1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office2', Face3D(pts_2), 3)
    room2d_3 = Room2D('Office3', Face3D(pts_3), 3)
    room2d_4 = Room2D('Office4', Face3D(pts_4), 3)
    story = Story('OfficeFloor', [room2d_1, room2d_2, room2d_3, room2d_4])
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.multiplier = 4
    building = Building('OfficeBuilding', [story])

    tree_canopy_geo1 = Face3D.from_regular_polygon(6, 6, Plane(o=Point3D(5, -10, 6)))
    tree_canopy_geo2 = Face3D.from_regular_polygon(6, 2, Plane(o=Point3D(-5, -10, 3)))
    tree_canopy = ContextShade('TreeCanopy', [tree_canopy_geo1, tree_canopy_geo2])

    model = Model('NewDevelopment', [building], [tree_canopy])

    model_dict = model.to_dict()
    new_model = Model.from_dict(model_dict)
    assert model_dict == new_model.to_dict()


def test_to_from_dfjson_methods():
    """Test the to/from dfjson methods."""
    pts_1 = (Point3D(0, 0, 3), Point3D(0, 10, 3), Point3D(10, 10, 3), Point3D(10, 0, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(20, 10, 3), Point3D(20, 0, 3))
    pts_3 = (Point3D(0, 10, 3), Point3D(0, 20, 3), Point3D(10, 20, 3), Point3D(10, 10, 3))
    pts_4 = (Point3D(10, 10, 3), Point3D(10, 20, 3), Point3D(20, 20, 3), Point3D(20, 10, 3))
    room2d_1 = Room2D('Office1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office2', Face3D(pts_2), 3)
    room2d_3 = Room2D('Office3', Face3D(pts_3), 3)
    room2d_4 = Room2D('Office4', Face3D(pts_4), 3)
    story = Story('OfficeFloor', [room2d_1, room2d_2, room2d_3, room2d_4])
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.multiplier = 4
    building = Building('OfficeBuilding', [story])

    tree_canopy_geo1 = Face3D.from_regular_polygon(6, 6, Plane(o=Point3D(5, -10, 6)))
    tree_canopy_geo2 = Face3D.from_regular_polygon(6, 2, Plane(o=Point3D(-5, -10, 3)))
    tree_canopy = ContextShade('TreeCanopy', [tree_canopy_geo1, tree_canopy_geo2])

    model = Model('NewDevelopment', [building], [tree_canopy])

    model_dfjson = model.to_dfjson('test')
    assert os.path.isfile(model_dfjson)
    new_model = Model.from_dfjson(model_dfjson)
    assert isinstance(new_model, Model)
    os.remove(model_dfjson)


def test_to_from_dfpkl_methods():
    """Test the to/from dfpkl methods."""
    pts_1 = (Point3D(0, 0, 3), Point3D(0, 10, 3), Point3D(10, 10, 3), Point3D(10, 0, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(20, 10, 3), Point3D(20, 0, 3))
    pts_3 = (Point3D(0, 10, 3), Point3D(0, 20, 3), Point3D(10, 20, 3), Point3D(10, 10, 3))
    pts_4 = (Point3D(10, 10, 3), Point3D(10, 20, 3), Point3D(20, 20, 3), Point3D(20, 10, 3))
    room2d_1 = Room2D('Office1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office2', Face3D(pts_2), 3)
    room2d_3 = Room2D('Office3', Face3D(pts_3), 3)
    room2d_4 = Room2D('Office4', Face3D(pts_4), 3)
    story = Story('OfficeFloor', [room2d_1, room2d_2, room2d_3, room2d_4])
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.multiplier = 4
    building = Building('OfficeBuilding', [story])

    tree_canopy_geo1 = Face3D.from_regular_polygon(6, 6, Plane(o=Point3D(5, -10, 6)))
    tree_canopy_geo2 = Face3D.from_regular_polygon(6, 2, Plane(o=Point3D(-5, -10, 3)))
    tree_canopy = ContextShade('TreeCanopy', [tree_canopy_geo1, tree_canopy_geo2])

    model = Model('NewDevelopment', [building], [tree_canopy])

    model_dfpkl = model.to_dfpkl('test')
    assert os.path.isfile(model_dfpkl)
    new_model = Model.from_dfpkl(model_dfpkl)
    assert isinstance(new_model, Model)
    os.remove(model_dfpkl)


def test_from_dict_nulls():
    """Test the re-serialization of a Model with null extension properties."""
    test_json = './tests/json/model_with_nulls.json'
    with open(test_json) as json_file:
        data = json.load(json_file)
    model = Model.from_dict(data)

    assert isinstance(model, Model)


def test_to_geojson():
    """Test the Model to_geojson method."""
    pts_1 = (Point3D(50, 50, 3), Point3D(60, 50, 3), Point3D(60, 60, 3), Point3D(50, 60, 3))
    pts_2 = (Point3D(60, 50, 3), Point3D(70, 50, 3), Point3D(70, 60, 3), Point3D(60, 60, 3))
    pts_3 = (Point3D(50, 70, 3), Point3D(70, 70, 3), Point3D(70, 80, 3), Point3D(50, 80, 3))
    room2d_1 = Room2D('Residence1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Residence2', Face3D(pts_2), 3)
    room2d_3 = Room2D('Retail', Face3D(pts_3), 3)
    story_big = Story('RetailFloor', [room2d_3])
    story = Story('ResidenceFloor', [room2d_1, room2d_2])
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.multiplier = 3
    building = Building('ResidenceBuilding', [story])
    story_big.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story_big.multiplier = 1
    building_big = Building('RetailBuildingBig', [story_big])

    pts_1 = (Point3D(0, 0, 3), Point3D(0, 5, 3), Point3D(15, 5, 3), Point3D(15, 0, 3))
    pts_2 = (Point3D(15, 0, 3), Point3D(15, 15, 3), Point3D(20, 15, 3), Point3D(20, 0, 3))
    pts_3 = (Point3D(0, 5, 3), Point3D(0, 20, 3), Point3D(5, 20, 3), Point3D(5, 5, 3))
    pts_4 = (Point3D(5, 15, 3), Point3D(5, 20, 3), Point3D(20, 20, 3), Point3D(20, 15, 3))
    pts_5 = (Point3D(-5, -5, 3), Point3D(-10, -5, 3), Point3D(-10, -10, 3), Point3D(-5, -10, 3))
    room2d_1 = Room2D('Office1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office2', Face3D(pts_2), 3)
    room2d_3 = Room2D('Office3', Face3D(pts_3), 3)
    room2d_4 = Room2D('Office4', Face3D(pts_4), 3)
    room2d_5 = Room2D('Office5', Face3D(pts_5), 3)
    int_rms = Room2D.intersect_adjacency(
        [room2d_1, room2d_2, room2d_3, room2d_4, room2d_5], 0.01)
    story = Story('OfficeFloor', int_rms)
    story.rotate_xy(5, Point3D(0, 0, 0))
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.multiplier = 5
    building_mult = Building('OfficeBuilding', [story])

    tree_canopy_geo1 = Face3D.from_regular_polygon(6, 6, Plane(o=Point3D(5, -10, 6)))
    tree_canopy_geo2 = Face3D.from_regular_polygon(6, 2, Plane(o=Point3D(-5, -10, 3)))
    tree_canopy = ContextShade('TreeCanopy', [tree_canopy_geo1, tree_canopy_geo2])

    model = Model('TestGeoJSON', [building, building_big, building_mult], [tree_canopy])

    location = Location('Boston', 'MA', 'USA', 42.366151, -71.019357)
    geojson_folder = './tests/geojson/'
    model.to_geojson(location, folder=geojson_folder)

    geo_fp = os.path.join(
        geojson_folder, model.identifier, '{}.geojson'.format(model.identifier))
    assert os.path.isfile(geo_fp)
    nukedir(os.path.join(geojson_folder, model.identifier), True)


def test_from_minimal_geojson():
    """Test the Model from_geojson method with a minimal geojson file."""

    # Load test geojson
    geojson_folder = os.path.join(os.getcwd(), 'tests', 'geojson')
    geo_fp = os.path.join(geojson_folder, 'TestGeoJSON_minimal.geojson')
    location = Location('Boston', 'MA', 'USA', 42.366151, -71.019357)
    model, loc = \
        Model.from_geojson(geo_fp, all_polygons_to_buildings=True, location=location)

    # Check model non-geometry properties
    assert model.identifier == 'Model_1'
    assert model.display_name == 'Model_1'

    # Check model buildings (features)
    assert len(model.buildings) == 3, len(model.buildings)

    bldgs = []
    for bldg in model.buildings:
        if abs(bldg.floor_area - 200.0) < 1e-5:
            # Formerly ResidentialBuilding, or RetailBuildingBig
            bldgs.append(bldg)
        else:
            # Formerly OfficeBuilding
            bldgs.append(bldg)

    # Check properties
    assert 200.0 == pytest.approx(bldgs[0].floor_area, abs=1e-5)
    assert 200.0 == pytest.approx(bldgs[0].footprint_area, abs=1e-5)
    assert bldgs[0].story_count == 1
    assert bldgs[0].unique_stories[0].floor_to_floor_height == \
        pytest.approx(3.5, abs=1e-10)

    # Check properties
    assert 200.0 == pytest.approx(bldgs[1].floor_area, abs=1e-5)
    assert 200.0 == pytest.approx(bldgs[1].footprint_area, abs=1e-5)
    assert bldgs[1].story_count == 1
    assert bldgs[1].unique_stories[0].floor_to_floor_height == \
        pytest.approx(3.5, abs=1e-10)

    # Check properties
    assert 325.0 == pytest.approx(bldgs[2].floor_area, abs=1e-5)
    assert 325.0 == pytest.approx(bldgs[2].footprint_area, abs=1e-5)
    assert bldgs[2].story_count == 1
    assert bldgs[2].unique_stories[0].floor_to_floor_height == \
        pytest.approx(3.5, abs=1e-10)


def test_from_geojson():
    """Test the Model from_geojson method."""

    # Load test geojson
    geojson_folder = os.path.join(os.getcwd(), 'tests', 'geojson')
    geo_fp = os.path.join(geojson_folder, 'TestGeoJSON.geojson')
    location = Location('Boston', 'MA', 'USA', 42.366151, -71.019357)
    model, loc = Model.from_geojson(geo_fp, location=location)

    # Check model non-geometry properties
    assert model.identifier == 'TestGeoJSON'
    assert model.display_name == 'TestGeoJSON'

    # Check model buildings (features)
    assert len(model.buildings) == 3, len(model.buildings)

    # Check the first building
    bldg1 = [bldg for bldg in model.buildings
             if bldg.identifier == 'ResidenceBuilding'][0]

    # Check properties
    assert bldg1.identifier == 'ResidenceBuilding'
    assert bldg1.display_name == 'ResidenceBuilding'
    assert 600.0 == pytest.approx(bldg1.floor_area, abs=1e-5)
    assert 200.0 == pytest.approx(bldg1.footprint_area, abs=1e-5)
    assert bldg1.story_count == 3
    assert bldg1.unique_stories[0].floor_to_floor_height == pytest.approx(3.0, abs=1e-10)

    # Check the second building
    bldg2 = [bldg for bldg in model.buildings
             if bldg.identifier == 'RetailBuildingBig'][0]

    # Check properties
    assert bldg2.identifier == 'RetailBuildingBig'
    assert bldg2.display_name == 'RetailBuildingBig'
    assert 200.0 == pytest.approx(bldg2.floor_area, abs=1e-5)
    assert 200.0 == pytest.approx(bldg2.footprint_area, abs=1e-5)
    assert bldg2.story_count == 1
    assert bldg2.unique_stories[0].floor_to_floor_height == pytest.approx(3.0, abs=1e-10)

    # Check the third building
    bldg3 = [bldg for bldg in model.buildings
             if bldg.identifier == 'OfficeBuilding'][0]

    # Check properties
    assert bldg3.identifier == 'OfficeBuilding'
    assert bldg3.display_name == 'OfficeBuilding'
    assert 1625.0 == pytest.approx(bldg3.floor_area, abs=1e-5)
    assert 325.0 == pytest.approx(bldg3.footprint_area, abs=1e-5)
    assert bldg3.story_count == 5
    assert bldg3.unique_stories[0].floor_to_floor_height == pytest.approx(3.0, abs=1e-10)


def test_from_geojson_units_test():
    """Test the Model from_geojson method with non-meter units."""

    # Load test geojson
    geojson_folder = os.path.join(os.getcwd(), 'tests', 'geojson')
    geo_fp = os.path.join(geojson_folder, 'TestGeoJSON.geojson')
    location = Location('Boston', 'MA', 'USA', 42.366151, -71.019357)

    model, loc = Model.from_geojson(geo_fp, location=location, units='Feet')

    # Check the first building
    bldg1 = [bldg for bldg in model.buildings
             if bldg.identifier == 'ResidenceBuilding'][0]

    # Check properties
    assert bldg1.identifier == 'ResidenceBuilding'
    assert bldg1.display_name == 'ResidenceBuilding'

    # Check if area is in feet square
    m2ft = 1 / hb_model.Model.conversion_factor_to_meters('Feet')
    sm2sft = m2ft * m2ft
    assert (600.0 * sm2sft) == pytest.approx(bldg1.floor_area, abs=1e-5)
    assert (200.0 * sm2sft) == pytest.approx(bldg1.footprint_area, abs=1e-5)
    assert bldg1.story_count == 3

    # Check story
    assert bldg1.story_count == 3
    assert len(bldg1.unique_stories) == 1
    for story in bldg1.unique_stories:
        assert (3.0) == pytest.approx(story.floor_to_floor_height, abs=1e-10)


def test_from_geojson_coordinates_simple_location():
    """Test the Model coordinates from_geojson method with different location inputs.
    """

    # Test 1: The location is equal to the point (0, 0) in model space.

    # Construct Model
    pts_1 = (Point3D(50, 50, 0), Point3D(60, 50, 0), Point3D(60, 60, 0), Point3D(50, 60, 0))
    pts_2 = (Point3D(60, 50, 0), Point3D(70, 50, 0), Point3D(70, 60, 0), Point3D(60, 60, 0))
    room2d_1 = Room2D('Residence1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Residence2', Face3D(pts_2), 3)
    story = Story('ResidenceFloor', [room2d_1, room2d_2])
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.multiplier = 3
    test_building = Building('ResidenceBuilding', [story])

    # Convert to geojson. Location defines the origin of the model space.
    test_model = Model('TestGeoJSON_coords1', [test_building])
    location = Location('Boston', 'MA', 'USA', 42.366151, -71.019357)  # bottom-left
    geojson_folder = './tests/geojson/'
    test_model.to_geojson(location, folder=geojson_folder)
    geo_fp = os.path.join(geojson_folder, test_model.identifier,
                          '{}.geojson'.format(test_model.identifier))

    # Convert back to Model. Location defines the origin.
    model, loc = Model.from_geojson(geo_fp, location=location, point=Point2D(0, 0))

    assert len(model.buildings) == 1

    # Test geometric properties of building
    bldg1 = model.buildings[0]

    # Check story height
    for story in bldg1.unique_stories:
        assert 3.0 == pytest.approx(story.floor_to_floor_height, abs=1e-10)

    assert pytest.approx(bldg1.footprint_area, test_building.footprint_area, abs=1e-10)
    vertices = bldg1.footprint()[0].vertices
    test_vertices = test_building.footprint()[0].vertices
    for point, test_point in zip(vertices, test_vertices):
        assert point.is_equivalent(test_point, 1e-5)

    # Test 2: Change the location to equal to the point (70, 60) in model space, which is
    # the top-right corner of the building footprints.

    # Construct model with a new location that defines the top-right corner in lon/lat degrees.
    location2 = Location('Boston', 'MA', 'USA', 42.366690813294774, -71.01850462247945)
    # We define the point at the top-right corner in model units.
    model, loc = Model.from_geojson(geo_fp, location=location2, point=Point2D(70, 60))

    assert len(model.buildings) == 1

    # Test geometric properties of building
    bldg1 = model.buildings[0]
    assert test_building.footprint_area == pytest.approx(bldg1.footprint_area, abs=1e-5)
    vertices = bldg1.footprint()[0].vertices
    test_vertices = test_building.footprint()[0].vertices
    for point, test_point in zip(vertices, test_vertices):
        assert point.is_equivalent(test_point, 1e-3)  # reduce precision due to conversion

    nukedir(os.path.join(geojson_folder, test_model.identifier), True)


def test_geojson_coordinates_to_face3d():
    """Test conversion of geojson nested list to face3d."""

    # Set constants
    origin_lon_lat = (-70.0, 42.0)
    convert_facs = meters_to_long_lat_factors(origin_lon_lat)
    convert_facs = (1 / convert_facs[0], 1 / convert_facs[1])

    # Test a Polygon
    geojson_polygon_coords = {'coordinates': [
        [[-70.0, 42.0],
         [-69.99997578750273, 42.0],
         [-69.99997578750273, 42.00001799339205],
         [-70.0, 42.00001799339205],
         [-70.0, 42.0]]]}

    face3d = Model._geojson_coordinates_to_face3d(
        geojson_polygon_coords['coordinates'], origin_lon_lat, convert_facs)
    poly2d = Polygon2D([Point2D(v[0], v[1]) for v in face3d.vertices])

    # Test that we get single polygon
    test_poly2d = Polygon2D(
        [Point2D(0, 0), Point2D(2, 0), Point2D(2, 2), Point2D(0, 2)])

    # Check length
    assert len(poly2d.vertices) == len(test_poly2d.vertices)

    # Check equivalence
    assert poly2d.is_equivalent(test_poly2d, 1e-5)

    # Test a Polygon w/ holes
    geojson_polygon_coords = {'coordinates': [
        [[-70.0, 42.0],
         [-69.99997578750273, 42.0],
         [-69.99997578750273, 42.00001799339205],
         [-70.0, 42.00001799339205],
         [-70.0, 42.0]],
        [[-70.0, 42.0],
         [-69.99997578750273, 42.00001799339205],
         [-70.0, 42.00001799339205],
         [-70.0, 42.0]]]}

    face3d = Model._geojson_coordinates_to_face3d(
        geojson_polygon_coords['coordinates'], origin_lon_lat, convert_facs)

    # Check if hole exists
    assert face3d.has_holes

    # Convert to polygon
    polyhole2d = Polygon2D([Point2D(v[0], v[1]) for v in face3d.holes[0]])

    # Test that we get single polygon
    test_polyhole2d = Polygon2D([Point2D(0, 0), Point2D(2, 2), Point2D(0, 2)])

    # Check length
    assert len(polyhole2d.vertices) == len(test_polyhole2d.vertices)

    # Check equivalence
    assert polyhole2d.is_equivalent(test_polyhole2d, 1e-5)


def test_bottom_left_coordinate_from_geojson():
    """Test derivation of origin from bldg geojson coordinates."""

    geojson_folder = os.path.join(os.getcwd(), 'tests', 'geojson')
    geo_fp = os.path.join(geojson_folder, 'TestGeoJSON.geojson')
    with open(geo_fp, 'r') as fp:
        data = json.load(fp)

    bldgs_data = [bldg_data for bldg_data in data['features']
                  if bldg_data['properties']['type'] == 'Building']

    lon, lat = Model._bottom_left_coordinate_from_geojson(bldgs_data)

    assert abs(lat - 42.36605353217153) < 1e-13
    assert abs(lon - -71.01947299845268) < 1e-13


def test_from_honeybee():
    """Test the from_honeybee method of Model objects."""
    room_south = Room.from_box('SouthZone', 5, 5, 3, origin=Point3D(0, 0, 0))
    room_north = Room.from_box('NorthZone', 5, 5, 3, origin=Point3D(0, 5, 0))
    room_up = Room.from_box('UpZone', 5, 5, 3, origin=Point3D(0, 5, 3))
    room_south[1].apertures_by_ratio(0.4, 0.01)
    room_south[3].apertures_by_ratio(0.4, 0.01)
    room_north[3].apertures_by_ratio(0.4, 0.01)
    Room.solve_adjacency([room_south, room_north], 0.01)

    pts = (Point3D(0, -3, 0), Point3D(0, -3, 3), Point3D(1, -3, 3), Point3D(1, -3, 0))
    shade = Shade('TestShade', Face3D(pts))

    model = hb_model.Model('Test_Building', [room_south, room_north, room_up],
                           orphaned_shades=[shade], tolerance=0.01)

    model = Model.from_honeybee(model)

    assert len(model.context_shades) == 1
    assert len(model.buildings) == 1
    bldg = model.buildings[0]

    assert bldg.identifier == 'Test_Building'
    assert len(bldg.unique_stories) == 2

    bound_cs = [b for room in bldg.unique_room_2ds for b in room.boundary_conditions
                if isinstance(b, Surface)]
    assert len(bound_cs) == 2
    model.check_missing_adjacencies()


def test_from_honeybee_methods():
    """Test the different conversion methods on the from_honeybee method."""
    hb_model_file = './tests/json/revit_sample_model.hbjson'
    model = hb_model.Model.from_file(hb_model_file)

    df_model = Model.from_honeybee(model, conversion_method='AllRoom2D')
    assert len(df_model.room_2ds) == 15
    assert len(df_model.room_3ds) == 0

    df_model = Model.from_honeybee(model, conversion_method='AllRoom3D')
    assert len(df_model.room_2ds) == 0
    assert len(df_model.room_3ds) == 15

    df_model = Model.from_honeybee(model, conversion_method='ExtrudedOnly')
    assert len(df_model.room_2ds) == 6
    assert len(df_model.room_3ds) == 9


def test_writer():
    """Test the Model writer object."""
    pts = (Point3D(50, 50, 3), Point3D(60, 50, 3), Point3D(60, 60, 3), Point3D(50, 60, 3))
    bldg = Building.from_footprint('TestBldg', [Face3D(pts)], [5, 4, 3, 3], tolerance=0.01)
    model = Model('TestModel', [bldg])

    writers = [mod for mod in dir(model.to) if not mod.startswith('_')]
    for writer in writers:
        assert callable(getattr(model.to, writer))


def test_model_dict_room_2d_subset():
    """Test the model_dict_room_2d_subset and ensure it serializes correctly."""
    model_file = './tests/json/sample_revit_model.dfjson'
    with open(model_file, 'r') as mf:
        model_dict = json.load(mf)
    filtered_model = Model.model_dict_room_2d_subset(model_dict, ['KitchenDining'])
    model = Model.from_dict(filtered_model)

    assert len(model.buildings) == 1
    assert len(model.stories) == 1
    assert len(model.room_2ds) == 1
    assert model.room_2ds[0].identifier == 'KitchenDining'
    assert len(model.context_shades) == 0


def test_model_from_dfjson_encoding():
    """Test the from_file method with a UTF-8 encoded JSON."""
    model_json = './tests/json/model_editor_encoded.dfjson'
    parsed_model = Model.from_file(model_json)
    assert isinstance(parsed_model, Model)
