# coding=utf-8
import pytest

from dragonfly.story import Story
from dragonfly.room2d import Room2D
from dragonfly.windowparameter import SimpleWindowRatio
from dragonfly.shadingparameter import Overhang

from honeybee.room import Room
from honeybee.boundarycondition import Outdoors, Surface

from ladybug_geometry.geometry3d.pointvector import Point3D, Vector3D
from ladybug_geometry.geometry3d.line import LineSegment3D
from ladybug_geometry.geometry3d.plane import Plane
from ladybug_geometry.geometry3d.face import Face3D
from ladybug_geometry.geometry3d.polyface import Polyface3D


def test_story_init():
    """Test the initialization of Story objects and basic properties."""
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

    str(story)  # test the string representation
    assert story.identifier == 'OfficeFloor'
    assert story.display_name == 'OfficeFloor'
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
    assert story.is_above_ground


def test_story_floor_geometry():
    """Test the Story floor_geometry methods."""
    pts_1 = (Point3D(0, 0, 3), Point3D(0, 10, 3), Point3D(10, 10, 3), Point3D(10, 0, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(20, 10, 3), Point3D(20, 0, 3))
    pts_3 = (Point3D(0, 10, 3), Point3D(0, 20, 3), Point3D(10, 20, 3), Point3D(10, 10, 3))
    pts_4 = (Point3D(10, 10, 3), Point3D(10, 20, 3), Point3D(20, 20, 3), Point3D(20, 10, 3))
    room2d_1 = Room2D('Office1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office2', Face3D(pts_2), 3)
    room2d_3 = Room2D('Office3', Face3D(pts_3), 3)
    room2d_4 = Room2D('Office4', Face3D(pts_4), 3)
    story = Story('OfficeFloor', [room2d_1, room2d_2, room2d_3, room2d_4])

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
    room2d_1 = Room2D('Office1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office2', Face3D(pts_2), 3)
    room2d_3 = Room2D('Office3', Face3D(pts_3), 3)
    room2d_4 = Room2D('Office4', Face3D(pts_4), 3)
    story = Story('OfficeFloor', [room2d_1])

    assert story.floor_area == 100
    assert isinstance(story.room_by_identifier('Office1'), Room2D) 
    with pytest.raises(ValueError):
        story.room_by_identifier('Office2')
    story.add_room_2d(room2d_2)
    assert story.floor_area == 200
    assert isinstance(story.room_by_identifier('Office2'), Room2D)
    with pytest.raises(ValueError):
        story.room_by_identifier('Office3')
    story.add_room_2ds([room2d_3, room2d_4])
    assert story.floor_area == 400
    assert isinstance(story.room_by_identifier('Office3'), Room2D)


def test_story_set_outdoor_window_shading_parameters():
    """Test the Story set_outdoor_window_parameters method."""
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


def test_story_make_underground():
    """Test the Story make_underground method."""
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

    assert all(not room.is_ground_contact for room in story.room_2ds)
    assert all(not room.is_top_exposed for room in story.room_2ds)
    assert story.is_above_ground

    story.set_ground_contact(True)
    assert all(room.is_ground_contact for room in story.room_2ds)

    story.set_top_exposed(True)
    assert all(room.is_top_exposed for room in story.room_2ds)

    story.make_underground()
    assert not story.is_above_ground


def test_generate_grid():
    """Test the generate_grid method."""
    pts_1 = (Point3D(0, 0, 3), Point3D(0, 10, 3), Point3D(10, 10, 3), Point3D(10, 0, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(20, 10, 3), Point3D(20, 0, 3))
    room2d_1 = Room2D('Office1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office2', Face3D(pts_2), 3)
    story = Story('OfficeFloor', [room2d_1, room2d_2])

    mesh_grid = story.generate_grid(1)
    assert len(mesh_grid) == 2
    assert len(mesh_grid[0].faces) == 100

    mesh_grid = story.generate_grid(0.5)
    assert len(mesh_grid[0].faces) == 400


def test_move():
    """Test the Story move method."""
    pts_1 = (Point3D(0, 0, 3), Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(0, 10, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(20, 0, 3), Point3D(20, 10, 3), Point3D(10, 10, 3))
    room2d_1 = Room2D('Office1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office2', Face3D(pts_2), 3)
    story = Story('OfficeFloor', [room2d_1, room2d_2])

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
    room2d_1 = Room2D('Office1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office2', Face3D(pts_2), 3)
    story = Story('OfficeFloor', [room2d_1, room2d_2])

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
    room = Room2D('SquareShoebox', Face3D(pts, plane), 3)
    story = Story('OfficeFloor', [room])
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
    room = Room2D('SquareShoebox', Face3D(pts, plane), 3)
    story = Story('OfficeFloor', [room])

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
    room2d_1 = Room2D('Office1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office2', Face3D(pts_2), 3)
    story = Story('OfficeFloor', [room2d_1, room2d_2])
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))

    rooms = story.to_honeybee(0.01)
    assert len(rooms) == 2
    assert len(rooms[0]) == 6
    assert rooms[0].story == story.identifier
    assert rooms[0].multiplier == story.multiplier
    assert rooms[0].volume == 300
    assert rooms[0].floor_area == 100
    assert rooms[0].exterior_wall_area == 90
    assert rooms[0].exterior_aperture_area == pytest.approx(90 * 0.4, rel=1e-3)
    assert rooms[0].average_floor_height == 3
    assert rooms[0].check_solid(0.01, 1) == ''

    assert isinstance(rooms[0][1].boundary_condition, Outdoors)
    assert isinstance(rooms[0][2].boundary_condition, Surface)
    assert rooms[0][2].boundary_condition.boundary_condition_object == \
        rooms[1][4].identifier
    assert len(rooms[0][1].apertures) == 1
    assert len(rooms[0][2].apertures) == 0


def test_to_honeybee_different_heights():
    """Test the to_honeybee method with different floor and ceiling heights."""
    pts_1 = (Point3D(0, 0, 2), Point3D(10, 0, 2), Point3D(10, 10, 2), Point3D(0, 10, 2))
    pts_2 = (Point3D(10, 0, 3), Point3D(20, 0, 3), Point3D(20, 10, 3), Point3D(10, 10, 3))
    room2d_1 = Room2D('Office1', Face3D(pts_1), 5)
    room2d_2 = Room2D('Office2', Face3D(pts_2), 3)
    story = Story('OfficeFloor', [room2d_1, room2d_2])
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.solve_room_2d_adjacency(0.01)

    rooms = story.to_honeybee(True, tolerance=0.01)
    assert len(rooms) == 2
    assert len(rooms[0]) == 8
    assert rooms[0].volume == 500
    assert rooms[0].floor_area == 100
    assert rooms[0].exterior_wall_area >= 150
    assert rooms[0].exterior_aperture_area == pytest.approx(150 * 0.4, rel=1e-3)
    assert rooms[0].average_floor_height == 2
    assert rooms[0].check_solid(0.01, 1) == ''

    assert isinstance(rooms[0][1].boundary_condition, Outdoors)
    assert not isinstance(rooms[0][2].boundary_condition, Surface)  # bottom
    assert isinstance(rooms[0][3].boundary_condition, Surface)  # middle
    assert not isinstance(rooms[0][4].boundary_condition, Surface)  # top

    assert len(rooms[0][3].apertures) == 1
    assert len(rooms[1][4].apertures) == 1
    rm1_ap = rooms[0][3].apertures[0]
    rm2_ap = rooms[1][4].apertures[0]
    assert isinstance(rm1_ap.boundary_condition, Surface)
    assert isinstance(rm2_ap.boundary_condition, Surface)
    assert rm1_ap.area == pytest.approx(rm2_ap.area, rel=1e-3)


def test_to_dict():
    """Test the Story to_dict method."""
    pts_1 = (Point3D(0, 0, 2), Point3D(10, 0, 2), Point3D(10, 10, 2), Point3D(0, 10, 2))
    pts_2 = (Point3D(10, 0, 3), Point3D(20, 0, 3), Point3D(20, 10, 3), Point3D(10, 10, 3))
    room2d_1 = Room2D('Office1', Face3D(pts_1), 5)
    room2d_2 = Room2D('Office2', Face3D(pts_2), 3)
    story = Story('OfficeFloor', [room2d_1, room2d_2])
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.set_outdoor_shading_parameters(Overhang(1))

    sd = story.to_dict()
    assert sd['type'] == 'Story'
    assert sd['identifier'] == 'OfficeFloor'
    assert sd['display_name'] == 'OfficeFloor'
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
    room2d_1 = Room2D('Office1', Face3D(pts_1), 5)
    room2d_2 = Room2D('Office2', Face3D(pts_2), 3)
    story = Story('OfficeFloor', [room2d_1, room2d_2])
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.set_outdoor_shading_parameters(Overhang(1))

    story_dict = story.to_dict()
    new_story = Story.from_dict(story_dict)
    assert isinstance(new_story, Story)
    assert new_story.to_dict() == story_dict


def test_from_dict_reversed_surface_bcs():
    """Test the from_dict of Story objects with reversed Surface boundary conditions."""
    pts_1 = (Point3D(0, 0, 2), Point3D(10, 0, 2), Point3D(10, 10, 2), Point3D(0, 10, 2))
    pts_2 = (Point3D(10, 0, 3), Point3D(20, 0, 3), Point3D(20, 10, 3), Point3D(10, 10, 3))
    room2d_1 = Room2D('Office1', Face3D(pts_1), 5)
    room2d_2 = Room2D('Office2', Face3D(pts_2), 3)
    story = Story('OfficeFloor', [room2d_1, room2d_2])
    story.solve_room_2d_adjacency(0.01)
    story_dict_original = story.to_dict()

    # reverse the order of vertices in one of the rooms
    story_dict = story.to_dict()
    room2 = story_dict['room_2ds'][1]
    room2['floor_boundary'] = list(reversed(room2['floor_boundary']))
    room2['boundary_conditions'] = list(reversed(room2['boundary_conditions']))
    room1_bc = story_dict['room_2ds'][0]['boundary_conditions'][1]
    room1_bc['boundary_condition_objects'] = ('Office2..Face1', 'Office2')

    new_story = Story.from_dict(story_dict)
    assert new_story.to_dict() == story_dict_original

    # reverse the order of vertices in both of the rooms
    room1 = story_dict['room_2ds'][0]
    room1['floor_boundary'] = list(reversed(room1['floor_boundary']))
    room1['boundary_conditions'] = list(reversed(room1['boundary_conditions']))
    room2_bc = story_dict['room_2ds'][1]['boundary_conditions'][0]
    room2_bc['boundary_condition_objects'] = ('Office1..Face3', 'Office1')

    new_story = Story.from_dict(story_dict)
    assert new_story.to_dict() == story_dict_original


def test_from_honeybee():
    """Test the from_honeybee method of Story objects."""
    room_south = Room.from_box('Zone1', 5, 5, 3, origin=Point3D(0, 0, 0))
    room_north = Room.from_box('Zone2', 5, 5, 3, origin=Point3D(0, 5, 0))
    room_south[3].apertures_by_ratio(0.4, 0.01)
    Room.solve_adjacency([room_south, room_north], 0.01)

    df_story = Story.from_honeybee('Test_Story', [room_south, room_north], 0.01)
    bound_cs = [b for room in df_story.room_2ds for b in room.boundary_conditions
                if isinstance(b, Surface)]
    assert len(bound_cs) == 2
    assert bound_cs[0].boundary_condition_objects == ('Zone2..Face4', 'Zone2')
    assert bound_cs[1].boundary_condition_objects == ('Zone1..Face2', 'Zone1')


def test_writer():
    """Test the Story writer object."""
    pts_1 = (Point3D(0, 0, 2), Point3D(10, 0, 2), Point3D(10, 10, 2), Point3D(0, 10, 2))
    room2d_1 = Room2D('Office1', Face3D(pts_1), 5)
    story = Story('OfficeFloor', [room2d_1])

    writers = [mod for mod in dir(story.to) if not mod.startswith('_')]
    for writer in writers:
        assert callable(getattr(story.to, writer))
