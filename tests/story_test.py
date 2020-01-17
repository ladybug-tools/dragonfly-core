# coding=utf-8
import pytest

from dragonfly.story import Story
from dragonfly.room2d import Room2D
from dragonfly.windowparameter import SimpleWindowRatio
from dragonfly.shadingparameter import Overhang

from honeybee.model import Model
from honeybee.boundarycondition import Outdoors, Surface

from ladybug_geometry.geometry3d.pointvector import Point3D, Vector3D
from ladybug_geometry.geometry3d.line import LineSegment3D
from ladybug_geometry.geometry3d.plane import Plane
from ladybug_geometry.geometry3d.face import Face3D
from ladybug_geometry.geometry3d.polyface import Polyface3D


def test_story_init():
    """Test the initalization of Story objects and basic properties."""
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

    str(story)  # test the string representation
    assert story.name == 'OfficeFloor'
    assert story.display_name == 'Office Floor'
    assert len(story.room_2ds) == 4
    for room in story.room_2ds:
        assert isinstance(room, Room2D)
        assert room.has_parent
    assert story.floor_to_floor_height == 3
    assert story.multiplier == 1
    assert story.parent is None
    assert not story.has_parent
    assert story.floor_height == 3
    assert story.volume == 100 * 3 * 4
    assert story.floor_area == 400
    assert story.exterior_wall_area == 60 * 4
    assert story.exterior_aperture_area == 60 * 4 * 0.4


def test_story_floor_geometry():
    """Test the Story floor_geometry methods."""
    pts_1 = (Point3D(0, 0, 3), Point3D(0, 10, 3), Point3D(10, 10, 3), Point3D(10, 0, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(20, 10, 3), Point3D(20, 0, 3))
    pts_3 = (Point3D(0, 10, 3), Point3D(0, 20, 3), Point3D(10, 20, 3), Point3D(10, 10, 3))
    pts_4 = (Point3D(10, 10, 3), Point3D(10, 20, 3), Point3D(20, 20, 3), Point3D(20, 10, 3))
    room2d_1 = Room2D('Office 1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office 2', Face3D(pts_2), 3)
    room2d_3 = Room2D('Office 3', Face3D(pts_3), 3)
    room2d_4 = Room2D('Office 4', Face3D(pts_4), 3)
    story = Story('Office Floor', [room2d_1, room2d_2, room2d_3, room2d_4])

    floor_geo = story.floor_geometry(0.01)
    outline_segs = story.outline_segments(0.01)

    assert isinstance(floor_geo, Polyface3D)
    assert floor_geo.area == story.floor_area
    assert len(outline_segs) == 8
    assert all([isinstance(seg, LineSegment3D) for seg in outline_segs])


def test_story_add_rooms():
    """Test the Story add_rooms methods."""
    pts_1 = (Point3D(0, 0, 3), Point3D(0, 10, 3), Point3D(10, 10, 3), Point3D(10, 0, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(20, 10, 3), Point3D(20, 0, 3))
    pts_3 = (Point3D(0, 10, 3), Point3D(0, 20, 3), Point3D(10, 20, 3), Point3D(10, 10, 3))
    pts_4 = (Point3D(10, 10, 3), Point3D(10, 20, 3), Point3D(20, 20, 3), Point3D(20, 10, 3))
    room2d_1 = Room2D('Office 1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office 2', Face3D(pts_2), 3)
    room2d_3 = Room2D('Office 3', Face3D(pts_3), 3)
    room2d_4 = Room2D('Office 4', Face3D(pts_4), 3)
    story = Story('Office Floor', [room2d_1])

    assert story.floor_area == 100
    assert isinstance(story.room_by_name('Office1'), Room2D) 
    with pytest.raises(ValueError):
        story.room_by_name('Office2')
    story.add_room_2d(room2d_2)
    assert story.floor_area == 200
    assert isinstance(story.room_by_name('Office2'), Room2D)
    with pytest.raises(ValueError):
        story.room_by_name('Office3')
    story.add_room_2ds([room2d_3, room2d_4])
    assert story.floor_area == 400
    assert isinstance(story.room_by_name('Office3'), Room2D)


def test_room2d_set_outdoor_window_shading_parameters():
    """Test the Story set_outdoor_window_parameters method."""
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

    ashrae_base = SimpleWindowRatio(0.4)
    overhang = Overhang(1)
    story.set_outdoor_window_parameters(ashrae_base)
    story.set_outdoor_shading_parameters(overhang)

    assert story.room_2ds[0].window_parameters[1] is None
    assert story.room_2ds[0].window_parameters[2] == ashrae_base
    assert story.room_2ds[0].shading_parameters[1] is None
    assert story.room_2ds[0].shading_parameters[2] == overhang

    assert story.exterior_wall_area == 60 * 4
    assert story.exterior_aperture_area == 60 * 4 * 0.4


def test_generate_grid():
    """Test the generate_grid method."""
    pts_1 = (Point3D(0, 0, 3), Point3D(0, 10, 3), Point3D(10, 10, 3), Point3D(10, 0, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(20, 10, 3), Point3D(20, 0, 3))
    room2d_1 = Room2D('Office 1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office 2', Face3D(pts_2), 3)
    story = Story('Office Floor', [room2d_1, room2d_2])

    mesh_grid = story.generate_grid(1)
    assert len(mesh_grid) == 2
    assert len(mesh_grid[0].faces) == 100

    mesh_grid = story.generate_grid(0.5)
    assert len(mesh_grid[0].faces) == 400


def test_move():
    """Test the Story move method."""
    pts_1 = (Point3D(0, 0, 3), Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(0, 10, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(20, 0, 3), Point3D(20, 10, 3), Point3D(10, 10, 3))
    room2d_1 = Room2D('Office 1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office 2', Face3D(pts_2), 3)
    story = Story('Office Floor', [room2d_1, room2d_2])

    vec_1 = Vector3D(2, 2, 2)
    new_s = story.duplicate()
    story.move(vec_1)
    assert story.room_2ds[0].floor_geometry[0] == Point3D(2, 2, 5)
    assert story.room_2ds[0].floor_geometry[1] == Point3D(12, 2, 5)
    assert story.room_2ds[0].floor_geometry[2] == Point3D(12, 12, 5)
    assert story.room_2ds[0].floor_geometry[3] == Point3D(2, 12, 5)
    assert story.room_2ds[1].floor_geometry[0] == Point3D(12, 2, 5)
    assert story.room_2ds[1].floor_geometry[1] == Point3D(22, 2, 5)
    assert story.room_2ds[1].floor_geometry[2] == Point3D(22, 12, 5)
    assert story.room_2ds[1].floor_geometry[3] == Point3D(12, 12, 5)
    assert story.floor_area == new_s.floor_area
    assert story.volume == new_s.volume


def test_scale():
    """Test the Room2D scale method."""
    pts_1 = (Point3D(0, 0, 3), Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(0, 10, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(20, 0, 3), Point3D(20, 10, 3), Point3D(10, 10, 3))
    room2d_1 = Room2D('Office 1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office 2', Face3D(pts_2), 3)
    story = Story('Office Floor', [room2d_1, room2d_2])

    new_s = story.duplicate()
    new_s.scale(2)
    assert new_s.room_2ds[0].floor_geometry[0] == Point3D(0, 0, 6)
    assert new_s.room_2ds[0].floor_geometry[1] == Point3D(20, 0, 6)
    assert new_s.room_2ds[0].floor_geometry[2] == Point3D(20, 20, 6)
    assert new_s.room_2ds[0].floor_geometry[3] == Point3D(0, 20, 6)
    assert new_s.room_2ds[1].floor_geometry[0] == Point3D(20, 0, 6)
    assert new_s.room_2ds[1].floor_geometry[1] == Point3D(40, 0, 6)
    assert new_s.room_2ds[1].floor_geometry[2] == Point3D(40, 20, 6)
    assert new_s.room_2ds[1].floor_geometry[3] == Point3D(20, 20, 6)
    assert new_s.floor_area == story.floor_area * 2 ** 2
    assert new_s.volume == story.volume * 2 ** 3


def test_rotate_xy():
    """Test the Story rotate_xy method."""
    pts = (Point3D(1, 1, 2), Point3D(2, 1, 2), Point3D(2, 2, 2), Point3D(1, 2, 2))
    plane = Plane(Vector3D(0, 0, 1), Point3D(0, 0, 2))
    room = Room2D('Square Shoebox', Face3D(pts, plane), 3)
    story = Story('Office Floor', [room])
    origin_1 = Point3D(1, 1, 0)

    test_1 = story.duplicate()
    test_1.rotate_xy(180, origin_1)
    assert test_1.room_2ds[0].floor_geometry[0].x == pytest.approx(1, rel=1e-3)
    assert test_1.room_2ds[0].floor_geometry[0].y == pytest.approx(1, rel=1e-3)
    assert test_1.room_2ds[0].floor_geometry[0].z == pytest.approx(2, rel=1e-3)
    assert test_1.room_2ds[0].floor_geometry[2].x == pytest.approx(0, rel=1e-3)
    assert test_1.room_2ds[0].floor_geometry[2].y == pytest.approx(0, rel=1e-3)
    assert test_1.room_2ds[0].floor_geometry[2].z == pytest.approx(2, rel=1e-3)

    test_2 = story.duplicate()
    test_2.rotate_xy(90, origin_1)
    assert test_2.room_2ds[0].floor_geometry[0].x == pytest.approx(1, rel=1e-3)
    assert test_2.room_2ds[0].floor_geometry[0].y == pytest.approx(1, rel=1e-3)
    assert test_2.room_2ds[0].floor_geometry[0].z == pytest.approx(2, rel=1e-3)
    assert test_2.room_2ds[0].floor_geometry[2].x == pytest.approx(0, rel=1e-3)
    assert test_2.room_2ds[0].floor_geometry[2].y == pytest.approx(2, rel=1e-3)
    assert test_2.room_2ds[0].floor_geometry[2].z == pytest.approx(2, rel=1e-3)


def test_reflect():
    """Test the Story reflect method."""
    pts = (Point3D(1, 1, 2), Point3D(2, 1, 2), Point3D(2, 2, 2), Point3D(1, 2, 2))
    plane = Plane(Vector3D(0, 0, 1), Point3D(0, 0, 2))
    room = Room2D('Square Shoebox', Face3D(pts, plane), 3)
    story = Story('Office Floor', [room])

    origin_1 = Point3D(1, 0, 2)
    normal_1 = Vector3D(1, 0, 0)
    plane_1 = Plane(normal_1, origin_1)

    test_1 = story.duplicate()
    test_1.reflect(plane_1)
    assert test_1.room_2ds[0].floor_geometry[-1].x == pytest.approx(1, rel=1e-3)
    assert test_1.room_2ds[0].floor_geometry[-1].y == pytest.approx(1, rel=1e-3)
    assert test_1.room_2ds[0].floor_geometry[-1].z == pytest.approx(2, rel=1e-3)
    assert test_1.room_2ds[0].floor_geometry[1].x == pytest.approx(0, rel=1e-3)
    assert test_1.room_2ds[0].floor_geometry[1].y == pytest.approx(2, rel=1e-3)
    assert test_1.room_2ds[0].floor_geometry[1].z == pytest.approx(2, rel=1e-3)


def test_to_honeybee():
    """Test the to_honeybee method."""
    pts_1 = (Point3D(0, 0, 3), Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(0, 10, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(20, 0, 3), Point3D(20, 10, 3), Point3D(10, 10, 3))
    room2d_1 = Room2D('Office 1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office 2', Face3D(pts_2), 3)
    story = Story('Office Floor', [room2d_1, room2d_2])
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))

    hb_model = story.to_honeybee(0.01)
    assert isinstance(hb_model, Model)
    assert len(hb_model.rooms) == 2
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


def test_to_honeybee_different_heights():
    """Test the to_honeybee method with different floor and ceiling heights."""
    pts_1 = (Point3D(0, 0, 2), Point3D(10, 0, 2), Point3D(10, 10, 2), Point3D(0, 10, 2))
    pts_2 = (Point3D(10, 0, 3), Point3D(20, 0, 3), Point3D(20, 10, 3), Point3D(10, 10, 3))
    room2d_1 = Room2D('Office 1', Face3D(pts_1), 5)
    room2d_2 = Room2D('Office 2', Face3D(pts_2), 3)
    story = Story('Office Floor', [room2d_1, room2d_2])
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))

    hb_model = story.to_honeybee(True, 0.01)
    assert isinstance(hb_model, Model)
    assert len(hb_model.rooms) == 2
    assert len(hb_model.rooms[0]) == 8
    assert hb_model.rooms[0].volume == 500
    assert hb_model.rooms[0].floor_area == 100
    assert hb_model.rooms[0].exterior_wall_area >= 150
    assert hb_model.rooms[0].exterior_aperture_area == pytest.approx(150 * 0.4, rel=1e-3)
    assert hb_model.rooms[0].average_floor_height == 2
    assert hb_model.rooms[0].check_solid(0.01, 1)

    assert isinstance(hb_model.rooms[0][1].boundary_condition, Outdoors)
    assert not isinstance(hb_model.rooms[0][2].boundary_condition, Surface)  # bottom
    assert isinstance(hb_model.rooms[0][3].boundary_condition, Surface)  # middle
    assert not isinstance(hb_model.rooms[0][4].boundary_condition, Surface)  # top


def test_to_dict():
    """Test the Story to_dict method."""
    pts_1 = (Point3D(0, 0, 2), Point3D(10, 0, 2), Point3D(10, 10, 2), Point3D(0, 10, 2))
    pts_2 = (Point3D(10, 0, 3), Point3D(20, 0, 3), Point3D(20, 10, 3), Point3D(10, 10, 3))
    room2d_1 = Room2D('Office 1', Face3D(pts_1), 5)
    room2d_2 = Room2D('Office 2', Face3D(pts_2), 3)
    story = Story('Office Floor', [room2d_1, room2d_2])
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.set_outdoor_shading_parameters(Overhang(1))

    sd = story.to_dict()
    assert sd['type'] == 'Story'
    assert sd['name'] == 'OfficeFloor'
    assert sd['display_name'] == 'Office Floor'
    assert 'room_2ds' in sd
    assert len(sd['room_2ds']) == 2
    assert sd['floor_to_floor_height'] == 5
    assert sd['multiplier'] == 1
    assert 'properties' in sd
    assert sd['properties']['type'] == 'StoryProperties'


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

    story_dict = story.to_dict()
    new_story = Story.from_dict(story_dict)
    assert isinstance(new_story, Story)
    assert new_story.to_dict() == story_dict
