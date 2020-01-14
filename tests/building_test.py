# coding=utf-8
import pytest

from dragonfly.building import Building
from dragonfly.story import Story
from dragonfly.room2d import Room2D
from dragonfly.windowparameter import SimpleWindowRatio
from dragonfly.shadingparameter import Overhang

from honeybee.model import Model
from honeybee.boundarycondition import Outdoors, Surface

from ladybug_geometry.geometry3d.pointvector import Point3D, Vector3D
from ladybug_geometry.geometry3d.plane import Plane
from ladybug_geometry.geometry3d.face import Face3D


def test_building_init():
    """Test the initalization of Building objects and basic properties."""
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

    str(building)  # test the string representation
    assert building.name == 'OfficeBuilding'
    assert building.display_name == 'Office Building'
    assert len(building.unique_stories) == 1
    assert len(building.all_stories()) == 4
    assert len(building.unique_room_2ds) == 4
    assert len(building.all_room_2ds()) == 16
    for story in building.unique_stories:
        assert isinstance(story, Story)
        assert story.has_parent
    for story in building.all_stories():
        assert isinstance(story, Story)
        assert story.has_parent
    for room in building.unique_room_2ds:
        assert isinstance(room, Room2D)
        assert room.has_parent
    for room in building.all_room_2ds():
        assert isinstance(room, Room2D)
        assert room.has_parent
    assert building.height == 15
    assert building.height_from_first_floor == 12
    assert building.volume == 100 * 3 * 4 * 4
    assert building.floor_area == 100 * 4 * 4
    assert building.exterior_wall_area == 60 * 4 * 4
    assert building.exterior_aperture_area == 60 * 4 * 4 * 0.4


def test_building_init_from_footprint():
    """Test the initalization of Building objects from_footprint."""
    pts_1 = (Point3D(0, 0, 0), Point3D(0, 10, 0), Point3D(10, 10, 0), Point3D(10, 0, 0))
    pts_2 = (Point3D(0, 10, 0), Point3D(0, 20, 0), Point3D(10, 20, 0), Point3D(10, 10, 0))
    building = Building.from_footprint('Office Tower', [Face3D(pts_1), Face3D(pts_2)],
                                       [5, 4, 4, 3, 3, 3, 3, 3])
    building.set_outdoor_window_parameters(SimpleWindowRatio(0.4))

    assert building.name == 'OfficeTower'
    assert building.display_name == 'Office Tower'
    assert len(building.unique_stories) == 3
    assert len(building.all_stories()) == 8
    assert len(building.unique_room_2ds) == 6
    assert len(building.all_room_2ds()) == 16


def test_building_init_from_all_story_geometry():
    """Test the initalization of Building objects from_all_story_geometry."""
    pts_1 = (Point3D(0, 0, 0), Point3D(0, 10, 0), Point3D(10, 10, 0), Point3D(10, 0, 0))
    pts_2 = (Point3D(0, 0, 4), Point3D(0, 10, 4), Point3D(10, 10, 4), Point3D(10, 0, 4))
    pts_3 = (Point3D(0, 0, 8), Point3D(0, 10, 8), Point3D(5, 10, 8), Point3D(5, 0, 8))
    pts_4 = (Point3D(0, 0, 11), Point3D(0, 10, 11), Point3D(5, 10, 11), Point3D(5, 0, 11))
    story_geo = [[Face3D(pts_1)], [Face3D(pts_2)], [Face3D(pts_3)], [Face3D(pts_4)]]
    building = Building.from_all_story_geometry(
        'Office Tower', story_geo, [4, 4, 3, 3], 0.01)
    building.set_outdoor_window_parameters(SimpleWindowRatio(0.4))

    print(Building._is_story_equivalent(story_geo[0][0], story_geo[1][0], 0.1))

    assert building.name == 'OfficeTower'
    assert building.display_name == 'Office Tower'
    assert len(building.unique_stories) == 2
    assert len(building.all_stories()) == 4
    assert len(building.unique_room_2ds) == 2
    assert len(building.all_room_2ds()) == 4


def test_building_shade_representation():
    """Test the Building shade_representation method."""
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
    story.multiplier = 4
    building = Building('Office Building', [story])

    shade_rep = building.shade_representation(0.01)
    assert len(shade_rep) == 8
    shd_area = sum([shd.area for shd in shade_rep])
    assert shd_area == building.exterior_wall_area


def test_building_window_shading_parameters():
    """Test the Building set_outdoor_window_parameters method."""
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
    story.multiplier = 4
    building = Building('Office Building', [story])
    building.auto_assign_top_bottom_floors()

    assert building.exterior_aperture_area == 0
    assert building.unique_room_2ds[0].window_parameters[2] is None
    ashrae_base = SimpleWindowRatio(0.4)
    story.set_outdoor_window_parameters(ashrae_base)
    assert building.exterior_aperture_area == 60 * 4 * 4 * 0.4
    assert building.unique_room_2ds[0].window_parameters[2] == ashrae_base

    assert building.unique_room_2ds[0].shading_parameters[2] is None
    overhang = Overhang(1)
    story.set_outdoor_shading_parameters(overhang)
    assert building.unique_room_2ds[0].shading_parameters[2] == overhang

    assert len(building.unique_stories) == 1
    assert len(building.all_stories()) == 4
    assert len(building.unique_room_2ds) == 4
    building.separate_top_bottom_floors()
    assert len(building.unique_stories) == 3
    assert len(set(story.name for story in building.unique_stories)) == 3
    assert len(building.all_stories()) == 4
    assert len(building.unique_room_2ds) == 12


def test_move():
    """Test the Building move method."""
    pts_1 = (Point3D(0, 0, 3), Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(0, 10, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(20, 0, 3), Point3D(20, 10, 3), Point3D(10, 10, 3))
    room2d_1 = Room2D('Office 1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office 2', Face3D(pts_2), 3)
    story = Story('Office Floor', [room2d_1, room2d_2])
    story.solve_room_2d_adjacency(0.01)
    story.multiplier = 4
    building = Building('Office Building', [story])

    vec_1 = Vector3D(2, 2, 2)
    new_b = building.duplicate()
    building.move(vec_1)
    assert building.unique_stories[0].room_2ds[0].floor_geometry[0] == Point3D(2, 2, 5)
    assert building.unique_stories[0].room_2ds[0].floor_geometry[1] == Point3D(12, 2, 5)
    assert building.unique_stories[0].room_2ds[0].floor_geometry[2] == Point3D(12, 12, 5)
    assert building.unique_stories[0].room_2ds[0].floor_geometry[3] == Point3D(2, 12, 5)
    assert building.unique_stories[0].room_2ds[1].floor_geometry[0] == Point3D(12, 2, 5)
    assert building.unique_stories[0].room_2ds[1].floor_geometry[1] == Point3D(22, 2, 5)
    assert building.unique_stories[0].room_2ds[1].floor_geometry[2] == Point3D(22, 12, 5)
    assert building.unique_stories[0].room_2ds[1].floor_geometry[3] == Point3D(12, 12, 5)
    assert building.floor_area == new_b.floor_area
    assert building.volume == new_b.volume
    assert building.height_from_first_floor == new_b.height_from_first_floor
    assert building.height == 17


def test_scale():
    """Test the Building scale method."""
    pts_1 = (Point3D(0, 0, 3), Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(0, 10, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(20, 0, 3), Point3D(20, 10, 3), Point3D(10, 10, 3))
    room2d_1 = Room2D('Office 1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office 2', Face3D(pts_2), 3)
    story = Story('Office Floor', [room2d_1, room2d_2])
    story.solve_room_2d_adjacency(0.01)
    story.multiplier = 4
    building = Building('Office Building', [story])

    new_b = building.duplicate()
    new_b.scale(2)
    assert new_b.unique_stories[0].room_2ds[0].floor_geometry[0] == Point3D(0, 0, 6)
    assert new_b.unique_stories[0].room_2ds[0].floor_geometry[1] == Point3D(20, 0, 6)
    assert new_b.unique_stories[0].room_2ds[0].floor_geometry[2] == Point3D(20, 20, 6)
    assert new_b.unique_stories[0].room_2ds[0].floor_geometry[3] == Point3D(0, 20, 6)
    assert new_b.unique_stories[0].room_2ds[1].floor_geometry[0] == Point3D(20, 0, 6)
    assert new_b.unique_stories[0].room_2ds[1].floor_geometry[1] == Point3D(40, 0, 6)
    assert new_b.unique_stories[0].room_2ds[1].floor_geometry[2] == Point3D(40, 20, 6)
    assert new_b.unique_stories[0].room_2ds[1].floor_geometry[3] == Point3D(20, 20, 6)
    assert new_b.floor_area == building.floor_area * 2 ** 2
    assert new_b.volume == building.volume * 2 ** 3
    assert new_b.height_from_first_floor == building.height_from_first_floor * 2
    assert new_b.height == 30


def test_rotate_xy():
    """Test the Building rotate_xy method."""
    pts = (Point3D(1, 1, 2), Point3D(2, 1, 2), Point3D(2, 2, 2), Point3D(1, 2, 2))
    plane = Plane(Vector3D(0, 0, 1), Point3D(0, 0, 2))
    room = Room2D('Square Shoebox', Face3D(pts, plane), 3)
    story = Story('Office Floor', [room])
    story.multiplier = 4
    building = Building('Office Building', [story])
    origin_1 = Point3D(1, 1, 0)

    test_1 = building.duplicate()
    test_1.rotate_xy(180, origin_1)
    assert test_1.unique_stories[0].room_2ds[0].floor_geometry[0].x == pytest.approx(1, rel=1e-3)
    assert test_1.unique_stories[0].room_2ds[0].floor_geometry[0].y == pytest.approx(1, rel=1e-3)
    assert test_1.unique_stories[0].room_2ds[0].floor_geometry[0].z == pytest.approx(2, rel=1e-3)
    assert test_1.unique_stories[0].room_2ds[0].floor_geometry[2].x == pytest.approx(0, rel=1e-3)
    assert test_1.unique_stories[0].room_2ds[0].floor_geometry[2].y == pytest.approx(0, rel=1e-3)
    assert test_1.unique_stories[0].room_2ds[0].floor_geometry[2].z == pytest.approx(2, rel=1e-3)

    test_2 = building.duplicate()
    test_2.rotate_xy(90, origin_1)
    assert test_2.unique_stories[0].room_2ds[0].floor_geometry[0].x == pytest.approx(1, rel=1e-3)
    assert test_2.unique_stories[0].room_2ds[0].floor_geometry[0].y == pytest.approx(1, rel=1e-3)
    assert test_2.unique_stories[0].room_2ds[0].floor_geometry[0].z == pytest.approx(2, rel=1e-3)
    assert test_2.unique_stories[0].room_2ds[0].floor_geometry[2].x == pytest.approx(0, rel=1e-3)
    assert test_2.unique_stories[0].room_2ds[0].floor_geometry[2].y == pytest.approx(2, rel=1e-3)
    assert test_2.unique_stories[0].room_2ds[0].floor_geometry[2].z == pytest.approx(2, rel=1e-3)

    assert building.floor_area == test_1.floor_area
    assert building.volume == test_1.volume
    assert building.height_from_first_floor == test_1.height_from_first_floor
    assert building.height == 14


def test_reflect():
    """Test the Building reflect method."""
    pts = (Point3D(1, 1, 2), Point3D(2, 1, 2), Point3D(2, 2, 2), Point3D(1, 2, 2))
    plane = Plane(Vector3D(0, 0, 1), Point3D(0, 0, 2))
    room = Room2D('Square Shoebox', Face3D(pts, plane), 3)
    story = Story('Office Floor', [room])
    story.multiplier = 4
    building = Building('Office Building', [story])

    origin_1 = Point3D(1, 0, 2)
    normal_1 = Vector3D(1, 0, 0)
    plane_1 = Plane(normal_1, origin_1)

    test_1 = building.duplicate()
    test_1.reflect(plane_1)
    assert test_1.unique_stories[0].room_2ds[0].floor_geometry[-1].x == pytest.approx(1, rel=1e-3)
    assert test_1.unique_stories[0].room_2ds[0].floor_geometry[-1].y == pytest.approx(1, rel=1e-3)
    assert test_1.unique_stories[0].room_2ds[0].floor_geometry[-1].z == pytest.approx(2, rel=1e-3)
    assert test_1.unique_stories[0].room_2ds[0].floor_geometry[1].x == pytest.approx(0, rel=1e-3)
    assert test_1.unique_stories[0].room_2ds[0].floor_geometry[1].y == pytest.approx(2, rel=1e-3)
    assert test_1.unique_stories[0].room_2ds[0].floor_geometry[1].z == pytest.approx(2, rel=1e-3)


def test_to_honeybee():
    """Test the to_honeybee method."""
    pts_1 = (Point3D(0, 0, 3), Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(0, 10, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(20, 0, 3), Point3D(20, 10, 3), Point3D(10, 10, 3))
    room2d_1 = Room2D('Office 1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office 2', Face3D(pts_2), 3)
    story = Story('Office Floor', [room2d_1, room2d_2])
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.multiplier = 4
    building = Building('Office Building', [story])

    hb_model = building.to_honeybee(False, 0.01)
    assert isinstance(hb_model, Model)
    assert len(hb_model.rooms) == 8
    assert len(hb_model.rooms[0]) == 6
    assert hb_model.rooms[0].volume == 300
    assert hb_model.rooms[0].floor_area == 100
    assert hb_model.rooms[0].exterior_wall_area == 90
    assert hb_model.rooms[0].exterior_aperture_area == pytest.approx(90 * 0.4, rel=1e-3)
    assert hb_model.rooms[0].average_floor_height == 3
    assert hb_model.rooms[0].check_solid(0.01, 1)

    assert isinstance(hb_model.rooms[0][1].boundary_condition, Outdoors)
    assert isinstance(hb_model.rooms[0][2].boundary_condition, Surface)
    assert hb_model.rooms[0][2].boundary_condition.boundary_condition_object == \
        hb_model.rooms[1][4].name
    assert len(hb_model.rooms[0][1].apertures) == 1
    assert len(hb_model.rooms[0][2].apertures) == 0

    assert hb_model.check_duplicate_room_names()
    assert hb_model.check_duplicate_face_names()
    assert hb_model.check_duplicate_sub_face_names()
    assert hb_model.check_missing_adjacencies()

    hb_model = building.to_honeybee(True, 0.01)
    assert len(hb_model.rooms) == 2
    for room in hb_model.rooms:
        assert room.multiplier == 4

    assert hb_model.check_duplicate_room_names()
    assert hb_model.check_duplicate_face_names()
    assert hb_model.check_duplicate_sub_face_names()
    assert hb_model.check_missing_adjacencies()


def test_buildings_to_honeybee():
    """Test the buildings_to_honeybee method."""
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

    hb_model = Building.buildings_to_honeybee([building, building_big], False, 0.01)
    assert isinstance(hb_model, Model)
    assert len(hb_model.rooms) == 12
    assert len(hb_model.rooms[-1]) == 6
    assert hb_model.rooms[-1].volume == 600
    assert hb_model.rooms[-1].floor_area == 200
    assert hb_model.rooms[-1].exterior_wall_area == 180

    hb_model = Building.buildings_to_honeybee([building, building_big], True, 0.01)
    assert isinstance(hb_model, Model)
    assert len(hb_model.rooms) == 3
    for room in hb_model.rooms:
        assert room.multiplier == 4


def test_buildings_to_honeybee_self_shade():
    """Test the buildings_to_honeybee_self_shade method."""
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

    hb_models = Building.buildings_to_honeybee_self_shade(
        [building, building_big], None, None, False, 0.01)
    assert len(hb_models) == 2
    assert isinstance(hb_models[0], Model)
    assert len(hb_models[0].orphaned_shades) == 4
    assert isinstance(hb_models[-1], Model)
    assert len(hb_models[-1].rooms) == 4
    assert len(hb_models[-1].rooms[-1]) == 6
    assert hb_models[-1].rooms[-1].volume == 600
    assert hb_models[-1].rooms[-1].floor_area == 200
    assert hb_models[-1].rooms[-1].exterior_wall_area == 180

    hb_models = Building.buildings_to_honeybee_self_shade(
        [building, building_big], None, 5, True, 0.01)
    assert len(hb_models) == 2
    assert isinstance(hb_models[0], Model)
    assert len(hb_models[0].orphaned_shades) == 0
    assert len(hb_models[0].rooms) == 2
    for room in hb_models[0].rooms:
        assert room.multiplier == 4


def test_to_dict():
    """Test the Building to_dict method."""
    pts_1 = (Point3D(0, 0, 2), Point3D(10, 0, 2), Point3D(10, 10, 2), Point3D(0, 10, 2))
    pts_2 = (Point3D(10, 0, 3), Point3D(20, 0, 3), Point3D(20, 10, 3), Point3D(10, 10, 3))
    room2d_1 = Room2D('Office 1', Face3D(pts_1), 5)
    room2d_2 = Room2D('Office 2', Face3D(pts_2), 3)
    story = Story('Office Floor', [room2d_1, room2d_2])
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.set_outdoor_shading_parameters(Overhang(1))
    story.multiplier = 4
    building = Building('Office Building', [story])
    building.auto_assign_top_bottom_floors()
    building.separate_top_bottom_floors()

    bd = building.to_dict()
    assert bd['type'] == 'Building'
    assert bd['name'] == 'OfficeBuilding'
    assert bd['display_name'] == 'Office Building'
    assert 'unique_stories' in bd
    assert len(bd['unique_stories']) == 3
    assert 'properties' in bd
    assert bd['properties']['type'] == 'BuildingProperties'


def test_to_from_dict():
    """Test the to/from dict of Story objects."""
    pts_1 = (Point3D(0, 0, 2), Point3D(10, 0, 2), Point3D(10, 10, 2), Point3D(0, 10, 2))
    pts_2 = (Point3D(10, 0, 3), Point3D(20, 0, 3), Point3D(20, 10, 3), Point3D(10, 10, 3))
    room2d_1 = Room2D('Office 1', Face3D(pts_1), 5)
    room2d_2 = Room2D('Office 2', Face3D(pts_2), 3)
    story = Story('Office Floor', [room2d_1, room2d_2])
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.set_outdoor_shading_parameters(Overhang(1))
    story.multiplier = 4
    building = Building('Office Building', [story])
    building.auto_assign_top_bottom_floors()
    building.separate_top_bottom_floors()

    building_dict = building.to_dict()
    new_building = Building.from_dict(building_dict)
    assert isinstance(new_building, Building)
    assert new_building.to_dict() == building_dict
