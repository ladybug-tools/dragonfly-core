# coding=utf-8
import pytest

from dragonfly.model import Model
from dragonfly.building import Building
from dragonfly.story import Story
from dragonfly.room2d import Room2D
from dragonfly.context import ContextShade
from dragonfly.windowparameter import SimpleWindowRatio
from dragonfly.shadingparameter import Overhang

import honeybee.model as hb_model
from honeybee.boundarycondition import Outdoors, Surface

from ladybug_geometry.geometry2d.pointvector import Point2D, Vector2D
from ladybug_geometry.geometry3d.pointvector import Point3D, Vector3D
from ladybug_geometry.geometry3d.plane import Plane
from ladybug_geometry.geometry3d.face import Face3D


def test_model_init():
    """Test the initalization of Model objects and basic properties."""
    pts_1 = (Point3D(0, 0, 3), Point3D(0, 10, 3), Point3D(10, 10, 3), Point3D(10, 0, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(20, 10, 3), Point3D(20, 0, 3))
    pts_3 = (Point3D(0, 10, 3), Point3D(0, 20, 3), Point3D(10, 20, 3), Point3D(10, 10, 3))
    pts_4 = (Point3D(10, 10, 3), Point3D(10, 20, 3), Point3D(20, 20, 3), Point3D(20, 10, 3))
    room2d_1 = Room2D('Office 1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office 2', Face3D(pts_2), 3)
    room2d_3 = Room2D('Office 3', Face3D(pts_3), 3)
    room2d_4 = Room2D('Office 4', Face3D(pts_4), 3)
    story = Story('Office Floor', [room2d_1, room2d_2, room2d_3, room2d_4])
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.multiplier = 4
    building = Building('Office Building', [story])

    tree_canopy_geo1 = Face3D.from_regular_polygon(6, 6, Plane(o=Point3D(5, -10, 6)))
    tree_canopy_geo2 = Face3D.from_regular_polygon(6, 2, Plane(o=Point3D(-5, -10, 3)))
    tree_canopy = ContextShade('Tree Canopy', [tree_canopy_geo1, tree_canopy_geo2])

    model = Model('New Development', [building], [tree_canopy])
    str(model)  # test the string representation of the object

    assert model.name == 'NewDevelopment'
    assert model.display_name == 'New Development'
    assert model.north_angle == 0
    assert model.north_vector == Vector2D(0, 1)
    assert model.units == 'Meters'
    assert model.tolerance == 0
    assert model.angle_tolerance == 0
    assert len(model.buildings) == 1
    assert isinstance(model.buildings[0], Building)
    assert len(model.context_shades) == 1
    assert isinstance(model.context_shades[0], ContextShade)
    assert model.min.x == pytest.approx(-6.73, rel=1e-2)
    assert model.min.y == pytest.approx(-16, rel=1e-2)
    assert model.max == Point2D(20, 20)


def test_model_properties_setability():
    """Test the setting of properties on the Model."""
    pts_1 = (Point3D(0, 0, 3), Point3D(0, 10, 3), Point3D(10, 10, 3), Point3D(10, 0, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(20, 10, 3), Point3D(20, 0, 3))
    pts_3 = (Point3D(0, 10, 3), Point3D(0, 20, 3), Point3D(10, 20, 3), Point3D(10, 10, 3))
    pts_4 = (Point3D(10, 10, 3), Point3D(10, 20, 3), Point3D(20, 20, 3), Point3D(20, 10, 3))
    room2d_1 = Room2D('Office 1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office 2', Face3D(pts_2), 3)
    room2d_3 = Room2D('Office 3', Face3D(pts_3), 3)
    room2d_4 = Room2D('Office 4', Face3D(pts_4), 3)
    story = Story('Office Floor', [room2d_1, room2d_2, room2d_3, room2d_4])
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.multiplier = 4
    building = Building('Office Building', [story])

    model = Model('New Development', [building])

    model.name = 'TestBuilding'
    assert model.name == 'TestBuilding'
    model.north_angle = 20
    assert model.north_angle == 20
    model.units = 'Feet'
    assert model.units == 'Feet'
    model.tolerance = 0.01
    assert model.tolerance == 0.01
    model.angle_tolerance = 0.01
    assert model.angle_tolerance == 0.01


def test_model_add_objects():
    """Test the addition of objects to a Model and getting objects by name."""
    pts_1 = (Point3D(0, 0, 3), Point3D(0, 10, 3), Point3D(10, 10, 3), Point3D(10, 0, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(20, 10, 3), Point3D(20, 0, 3))
    pts_3 = (Point3D(0, 20, 3), Point3D(0, 30, 3), Point3D(10, 30, 3), Point3D(10, 20, 3))
    pts_4 = (Point3D(10, 20, 3), Point3D(10, 30, 3), Point3D(20, 30, 3), Point3D(20, 20, 3))
    room2d_1 = Room2D('Office 1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office 2', Face3D(pts_2), 3)
    room2d_3 = Room2D('Office 3', Face3D(pts_3), 3)
    room2d_4 = Room2D('Office 4', Face3D(pts_4), 3)
    story_1 = Story('Office Floor 1', [room2d_1, room2d_2])
    story_2 = Story('Office Floor 2', [room2d_3, room2d_4])
    story_1.solve_room_2d_adjacency(0.01)
    story_1.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story_1.multiplier = 4
    story_2.solve_room_2d_adjacency(0.01)
    story_2.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story_2.multiplier = 2
    building_1 = Building('Office Building 1', [story_1])
    building_2 = Building('Office Building 2', [story_2])

    tree_canopy_geo1 = Face3D.from_regular_polygon(6, 6, Plane(o=Point3D(5, -10, 6)))
    tree_canopy_geo2 = Face3D.from_regular_polygon(6, 2, Plane(o=Point3D(-5, -10, 3)))
    tree_canopy_1 = ContextShade('Tree Canopy 1', [tree_canopy_geo1])
    tree_canopy_2 = ContextShade('Tree Canopy 2', [tree_canopy_geo2])

    model = Model('New Development', [building_1], [tree_canopy_1], 15)
    assert len(model.buildings) == 1
    assert len(model.context_shades) == 1
    assert model.north_angle == 15
    with pytest.raises(AssertionError):
        model.add_building(tree_canopy_2)
    model.add_building(building_2)
    assert len(model.buildings) == 2
    with pytest.raises(AssertionError):
        model.add_context_shade(building_2)
    model.add_context_shade(tree_canopy_2)
    assert len(model.context_shades) == 2

    assert len(model.buildings_by_name(['OfficeBuilding1'])) == 1
    with pytest.raises(ValueError):
        model.buildings_by_name(['NotABuilding'])
    assert len(model.context_shade_by_name(['TreeCanopy1'])) == 1
    with pytest.raises(ValueError):
        model.context_shade_by_name(['NotAShade'])


def test_model_add_model():
    """Test the addition of one Model to another."""
    pts_1 = (Point3D(0, 0, 3), Point3D(0, 10, 3), Point3D(10, 10, 3), Point3D(10, 0, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(20, 10, 3), Point3D(20, 0, 3))
    pts_3 = (Point3D(0, 20, 3), Point3D(0, 30, 3), Point3D(10, 30, 3), Point3D(10, 20, 3))
    pts_4 = (Point3D(10, 20, 3), Point3D(10, 30, 3), Point3D(20, 30, 3), Point3D(20, 20, 3))
    room2d_1 = Room2D('Office 1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office 2', Face3D(pts_2), 3)
    room2d_3 = Room2D('Office 3', Face3D(pts_3), 3)
    room2d_4 = Room2D('Office 4', Face3D(pts_4), 3)
    story_1 = Story('Office Floor 1', [room2d_1, room2d_2])
    story_2 = Story('Office Floor 2', [room2d_3, room2d_4])
    story_1.solve_room_2d_adjacency(0.01)
    story_1.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story_1.multiplier = 4
    story_2.solve_room_2d_adjacency(0.01)
    story_2.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story_2.multiplier = 2
    building_1 = Building('Office Building 1', [story_1])
    building_2 = Building('Office Building 2', [story_2])

    tree_canopy_geo1 = Face3D.from_regular_polygon(6, 6, Plane(o=Point3D(5, -10, 6)))
    tree_canopy_geo2 = Face3D.from_regular_polygon(6, 2, Plane(o=Point3D(-5, -10, 3)))
    tree_canopy_1 = ContextShade('Tree Canopy 1', [tree_canopy_geo1])
    tree_canopy_2 = ContextShade('Tree Canopy 2', [tree_canopy_geo2])

    model_1 = Model('New Development 1', [building_1], [tree_canopy_1], 15)
    model_2 = Model('New Development 2', [building_2], [tree_canopy_2], 15)

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


def test_move():
    """Test the Model move method."""
    pts_1 = (Point3D(0, 0, 3), Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(0, 10, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(20, 0, 3), Point3D(20, 10, 3), Point3D(10, 10, 3))
    room2d_1 = Room2D('Office 1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office 2', Face3D(pts_2), 3)
    story = Story('Office Floor', [room2d_1, room2d_2])
    story.solve_room_2d_adjacency(0.01)
    story.multiplier = 4
    building = Building('Office Building', [story])
    awning_geo1 = Face3D.from_rectangle(6, 6, Plane(o=Point3D(5, -10, 6)))
    awning_geo2 = Face3D.from_rectangle(2, 2, Plane(o=Point3D(-5, -10, 3)))
    awning_canopy_1 = ContextShade('Awning Canopy 1', [awning_geo1])
    awning_canopy_2 = ContextShade('Awning Canopy 2', [awning_geo2])

    model = Model('New Development', [building], [awning_canopy_1, awning_canopy_2])

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
    room2d_1 = Room2D('Office 1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office 2', Face3D(pts_2), 3)
    story = Story('Office Floor', [room2d_1, room2d_2])
    story.solve_room_2d_adjacency(0.01)
    story.multiplier = 4
    building = Building('Office Building', [story])
    awning_geo1 = Face3D.from_rectangle(6, 6, Plane(o=Point3D(5, -10, 6)))
    awning_geo2 = Face3D.from_rectangle(2, 2, Plane(o=Point3D(-5, -10, 3)))
    awning_canopy_1 = ContextShade('Awning Canopy 1', [awning_geo1])
    awning_canopy_2 = ContextShade('Awning Canopy 2', [awning_geo2])

    model = Model('New Development', [building], [awning_canopy_1, awning_canopy_2])

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
    room2d_1 = Room2D('Office 1', Face3D(pts_1), 96)
    room2d_2 = Room2D('Office 2', Face3D(pts_2), 96)
    story = Story('Office Floor', [room2d_1, room2d_2])
    story.solve_room_2d_adjacency(0.01)
    story.multiplier = 4
    building = Building('Office Building', [story])
    model = Model('New Development', [building], units='Inches')

    inches_conversion = hb_model.Model.conversion_factor_to_meters('Inches')
    model.convert_to_units('Meters')

    assert room2d_1.floor_area == pytest.approx(120 * 120 * (inches_conversion ** 2), rel=1e-3)
    assert room2d_1.volume == pytest.approx(120 * 120 * 96 * (inches_conversion ** 3), rel=1e-3)
    assert model.units == 'Meters'


def test_rotate_xy():
    """Test the Model rotate_xy method."""
    pts = (Point3D(1, 1, 2), Point3D(2, 1, 2), Point3D(2, 2, 2), Point3D(1, 2, 2))
    plane = Plane(Vector3D(0, 0, 1), Point3D(0, 0, 2))
    room = Room2D('Square Shoebox', Face3D(pts, plane), 3)
    story = Story('Office Floor', [room])
    story.multiplier = 4
    building = Building('Office Building', [story])
    pts = (Point3D(1, 1, 2), Point3D(2, 1, 2), Point3D(2, 2, 2), Point3D(1, 2, 2))
    plane_1 = Plane(Vector3D(0, 0, 1), Point3D(0, 0, 0))
    awning_canopy = ContextShade('Awning Canopy', [Face3D(pts, plane_1)])

    model = Model('New Development', [building], [awning_canopy])

    origin_1 = Point3D(1, 1, 0)
    test_1 = model.duplicate()
    test_1.rotate_xy(180, origin_1)
    assert test_1.buildings[0].unique_stories[0].room_2ds[0].floor_geometry[0].x == pytest.approx(1, rel=1e-3)
    assert test_1.buildings[0].unique_stories[0].room_2ds[0].floor_geometry[0].y == pytest.approx(1, rel=1e-3)
    assert test_1.buildings[0].unique_stories[0].room_2ds[0].floor_geometry[0].z == pytest.approx(2, rel=1e-3)
    assert test_1.buildings[0].unique_stories[0].room_2ds[0].floor_geometry[2].x == pytest.approx(0, rel=1e-3)
    assert test_1.buildings[0].unique_stories[0].room_2ds[0].floor_geometry[2].y == pytest.approx(0, rel=1e-3)
    assert test_1.buildings[0].unique_stories[0].room_2ds[0].floor_geometry[2].z == pytest.approx(2, rel=1e-3)

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
    room = Room2D('Square Shoebox', Face3D(pts, plane), 3)
    story = Story('Office Floor', [room])
    story.multiplier = 4
    building = Building('Office Building', [story])
    pts = (Point3D(1, 1, 2), Point3D(2, 1, 2), Point3D(2, 2, 2), Point3D(1, 2, 2))
    plane = Plane(Vector3D(0, 0, 1), Point3D(0, 0, 2))
    awning_canopy = ContextShade('Awning Canopy', [Face3D(pts, plane)])

    model = Model('New Development', [building], [awning_canopy])

    origin_1 = Point3D(1, 0, 2)
    normal_1 = Vector3D(1, 0, 0)
    plane_1 = Plane(normal_1, origin_1)

    test_1 = model.duplicate()
    test_1.reflect(plane_1)
    assert test_1.buildings[0].unique_stories[0].room_2ds[0].floor_geometry[-1].x == pytest.approx(1, rel=1e-3)
    assert test_1.buildings[0].unique_stories[0].room_2ds[0].floor_geometry[-1].y == pytest.approx(1, rel=1e-3)
    assert test_1.buildings[0].unique_stories[0].room_2ds[0].floor_geometry[-1].z == pytest.approx(2, rel=1e-3)
    assert test_1.buildings[0].unique_stories[0].room_2ds[0].floor_geometry[1].x == pytest.approx(0, rel=1e-3)
    assert test_1.buildings[0].unique_stories[0].room_2ds[0].floor_geometry[1].y == pytest.approx(2, rel=1e-3)
    assert test_1.buildings[0].unique_stories[0].room_2ds[0].floor_geometry[1].z == pytest.approx(2, rel=1e-3)

    assert test_1.context_shades[0][0][-1].x == pytest.approx(1, rel=1e-3)
    assert test_1.context_shades[0][0][-1].y == pytest.approx(1, rel=1e-3)
    assert test_1.context_shades[0][0][-1].z == pytest.approx(2, rel=1e-3)
    assert test_1.context_shades[0][0][1].x == pytest.approx(0, rel=1e-3)
    assert test_1.context_shades[0][0][1].y == pytest.approx(2, rel=1e-3)
    assert test_1.context_shades[0][0][1].z == pytest.approx(2, rel=1e-3)


def test_check_duplicate_names():
    """Test check_duplicate_building_names and check_duplicate_context_shade_names."""
    pts_1 = (Point3D(0, 0, 3), Point3D(0, 10, 3), Point3D(10, 10, 3), Point3D(10, 0, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(20, 10, 3), Point3D(20, 0, 3))
    pts_3 = (Point3D(0, 20, 3), Point3D(0, 30, 3), Point3D(10, 30, 3), Point3D(10, 20, 3))
    pts_4 = (Point3D(10, 20, 3), Point3D(10, 30, 3), Point3D(20, 30, 3), Point3D(20, 20, 3))
    room2d_1 = Room2D('Office 1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office 2', Face3D(pts_2), 3)
    room2d_3 = Room2D('Office 3', Face3D(pts_3), 3)
    room2d_4 = Room2D('Office 4', Face3D(pts_4), 3)
    story_1 = Story('Office Floor 1', [room2d_1, room2d_2])
    story_2 = Story('Office Floor 2', [room2d_3, room2d_4])
    story_1.solve_room_2d_adjacency(0.01)
    story_1.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story_1.multiplier = 4
    story_2.solve_room_2d_adjacency(0.01)
    story_2.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story_2.multiplier = 2
    building_1 = Building('Office Building', [story_1])
    building_2 = Building('Office Building', [story_2])

    tree_canopy_geo1 = Face3D.from_regular_polygon(6, 6, Plane(o=Point3D(5, -10, 6)))
    tree_canopy_geo2 = Face3D.from_regular_polygon(6, 2, Plane(o=Point3D(-5, -10, 3)))
    tree_canopy_1 = ContextShade('Tree Canopy', [tree_canopy_geo1])
    tree_canopy_2 = ContextShade('Tree Canopy', [tree_canopy_geo2])

    model_1 = Model('New Development 1', [building_1], [tree_canopy_1], 15)
    model_2 = Model('New Development 2', [building_2], [tree_canopy_2], 15)

    assert model_1.check_duplicate_building_names(False)
    assert model_1.check_duplicate_context_shade_names(False)
    
    model_1.add_model(model_2)
    
    assert not model_1.check_duplicate_building_names(False)
    with pytest.raises(ValueError):
        model_1.check_duplicate_building_names(True)
    assert not model_1.check_duplicate_context_shade_names(False)
    with pytest.raises(ValueError):
        model_1.check_duplicate_context_shade_names(True)


def test_to_honeybee():
    """Test the to_honeybee method."""
    pts_1 = (Point3D(0, 0, 3), Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(0, 10, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(20, 0, 3), Point3D(20, 10, 3), Point3D(10, 10, 3))
    pts_3 = (Point3D(0, 20, 3), Point3D(20, 20, 3), Point3D(20, 30, 3), Point3D(0, 30, 3))
    room2d_1 = Room2D('Office 1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office 2', Face3D(pts_2), 3)
    room2d_3 = Room2D('Office 3', Face3D(pts_3), 3)
    story_big = Story('Office Floor Big', [room2d_3])
    story = Story('Office Floor', [room2d_1, room2d_2])
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.multiplier = 4
    building = Building('Office Building', [story])
    story_big.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story_big.multiplier = 4
    building_big = Building('Office Building Big', [story_big])
    
    tree_canopy_geo1 = Face3D.from_regular_polygon(6, 6, Plane(o=Point3D(5, -10, 6)))
    tree_canopy_geo2 = Face3D.from_regular_polygon(6, 2, Plane(o=Point3D(-5, -10, 3)))
    tree_canopy = ContextShade('Tree Canopy', [tree_canopy_geo1, tree_canopy_geo2])

    model = Model('New Development', [building, building_big], [tree_canopy])

    hb_models = model.to_honeybee('District', None, False, 0.01)
    assert len(hb_models) == 1
    assert isinstance(hb_models[0], hb_model.Model)
    assert len(hb_models[0].rooms) == 12
    assert len(hb_models[0].rooms[-1]) == 6
    assert hb_models[0].rooms[-1].volume == 600
    assert hb_models[0].rooms[-1].floor_area == 200
    assert hb_models[0].rooms[-1].exterior_wall_area == 180
    assert len(hb_models[0].orphaned_shades) == 2


def test_to_honeybee_multiple_models():
    """Test to_honeybee with multiple honeybee models."""
    pts_1 = (Point3D(0, 0, 3), Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(0, 10, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(20, 0, 3), Point3D(20, 10, 3), Point3D(10, 10, 3))
    pts_3 = (Point3D(0, 20, 3), Point3D(20, 20, 3), Point3D(20, 30, 3), Point3D(0, 30, 3))
    room2d_1 = Room2D('Office 1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office 2', Face3D(pts_2), 3)
    room2d_3 = Room2D('Office 3', Face3D(pts_3), 3)
    story_big = Story('Office Floor Big', [room2d_3])
    story = Story('Office Floor', [room2d_1, room2d_2])
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.multiplier = 4
    building = Building('Office Building', [story])
    story_big.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story_big.multiplier = 4
    building_big = Building('Office Building Big', [story_big])

    tree_canopy_geo1 = Face3D.from_regular_polygon(6, 6, Plane(o=Point3D(5, -10, 6)))
    tree_canopy_geo2 = Face3D.from_regular_polygon(6, 2, Plane(o=Point3D(-5, -10, 3)))
    tree_canopy = ContextShade('Tree Canopy', [tree_canopy_geo1, tree_canopy_geo2])

    model = Model('New Development', [building, building_big], [tree_canopy])

    hb_models = model.to_honeybee('Building', 10, False, 0.01)
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


def test_to_dict():
    """Test the Model to_dict method."""
    pts_1 = (Point3D(0, 0, 3), Point3D(0, 10, 3), Point3D(10, 10, 3), Point3D(10, 0, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(20, 10, 3), Point3D(20, 0, 3))
    pts_3 = (Point3D(0, 10, 3), Point3D(0, 20, 3), Point3D(10, 20, 3), Point3D(10, 10, 3))
    pts_4 = (Point3D(10, 10, 3), Point3D(10, 20, 3), Point3D(20, 20, 3), Point3D(20, 10, 3))
    room2d_1 = Room2D('Office 1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office 2', Face3D(pts_2), 3)
    room2d_3 = Room2D('Office 3', Face3D(pts_3), 3)
    room2d_4 = Room2D('Office 4', Face3D(pts_4), 3)
    story = Story('Office Floor', [room2d_1, room2d_2, room2d_3, room2d_4])
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.multiplier = 4
    building = Building('Office Building', [story])

    tree_canopy_geo1 = Face3D.from_regular_polygon(6, 6, Plane(o=Point3D(5, -10, 6)))
    tree_canopy_geo2 = Face3D.from_regular_polygon(6, 2, Plane(o=Point3D(-5, -10, 3)))
    tree_canopy = ContextShade('Tree Canopy', [tree_canopy_geo1, tree_canopy_geo2])

    model = Model('New Development', [building], [tree_canopy])
    model.north_angle = 15

    model_dict = model.to_dict()
    assert model_dict['type'] == 'Model'
    assert model_dict['name'] == 'NewDevelopment'
    assert model_dict['display_name'] == 'New Development'
    assert 'buildings' in model_dict
    assert len(model_dict['buildings']) == 1
    assert 'context_shades' in model_dict
    assert len(model_dict['context_shades']) == 1
    assert 'north_angle' in model_dict
    assert model_dict['north_angle'] == 15
    assert 'properties' in model_dict
    assert model_dict['properties']['type'] == 'ModelProperties'


def test_to_from_dict_methods():
    """Test the to/from dict methods."""
    pts_1 = (Point3D(0, 0, 3), Point3D(0, 10, 3), Point3D(10, 10, 3), Point3D(10, 0, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(20, 10, 3), Point3D(20, 0, 3))
    pts_3 = (Point3D(0, 10, 3), Point3D(0, 20, 3), Point3D(10, 20, 3), Point3D(10, 10, 3))
    pts_4 = (Point3D(10, 10, 3), Point3D(10, 20, 3), Point3D(20, 20, 3), Point3D(20, 10, 3))
    room2d_1 = Room2D('Office 1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office 2', Face3D(pts_2), 3)
    room2d_3 = Room2D('Office 3', Face3D(pts_3), 3)
    room2d_4 = Room2D('Office 4', Face3D(pts_4), 3)
    story = Story('Office Floor', [room2d_1, room2d_2, room2d_3, room2d_4])
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.multiplier = 4
    building = Building('Office Building', [story])

    tree_canopy_geo1 = Face3D.from_regular_polygon(6, 6, Plane(o=Point3D(5, -10, 6)))
    tree_canopy_geo2 = Face3D.from_regular_polygon(6, 2, Plane(o=Point3D(-5, -10, 3)))
    tree_canopy = ContextShade('Tree Canopy', [tree_canopy_geo1, tree_canopy_geo2])

    model = Model('New Development', [building], [tree_canopy])
    model.north_angle = 15

    model_dict = model.to_dict()
    new_model = Model.from_dict(model_dict)
    assert model_dict == new_model.to_dict()
