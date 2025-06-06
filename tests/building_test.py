# coding=utf-8
import pytest

from dragonfly.building import Building
from dragonfly.story import Story
from dragonfly.room2d import Room2D
from dragonfly.roof import RoofSpecification
from dragonfly.windowparameter import SimpleWindowRatio
from dragonfly.shadingparameter import Overhang

from honeybee.model import Model
from honeybee.room import Room
from honeybee.boundarycondition import Outdoors, Surface, Ground
from honeybee.boundarycondition import boundary_conditions as bcs

from ladybug_geometry.geometry3d.pointvector import Point3D, Vector3D
from ladybug_geometry.geometry3d.plane import Plane
from ladybug_geometry.geometry3d.face import Face3D


def test_building_init():
    """Test the initialization of Building objects and basic properties."""
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
    building = Building('Office_Building_1234', [story])
    building.display_name = 'Office Building'

    str(building)  # test the string representation
    assert building.identifier == 'Office_Building_1234'
    assert building.display_name == 'Office Building'
    assert len(building.unique_stories) == len(building.unique_stories_above_ground) == 1
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
    assert building.story_count == building.story_count_above_ground == 4
    assert building.height_from_first_floor == building.height_above_ground == 12
    assert building.footprint_area == 100 * 4
    assert building.floor_area == 100 * 4 * 4
    assert building.exterior_wall_area == 60 * 4 * 4
    assert building.exterior_aperture_area == 60 * 4 * 4 * 0.4
    assert building.volume == 100 * 3 * 4 * 4

    building.convert_multipliers_to_stories()
    assert len(building.unique_stories) == len(building.unique_stories_above_ground) == 4
    assert len(building.unique_room_2ds) == 16


def test_building_init_from_footprint():
    """Test the initialization of Building objects from_footprint."""
    pts_1 = (Point3D(0, 0, 0), Point3D(0, 10, 0), Point3D(10, 10, 0), Point3D(10, 0, 0))
    pts_2 = (Point3D(0, 10, 0), Point3D(0, 20, 0), Point3D(10, 20, 0), Point3D(10, 10, 0))
    building = Building.from_footprint('Office_Tower', [Face3D(pts_1), Face3D(pts_2)],
                                       [5, 4, 4, 3, 3, 3, 3, 3])
    building.set_outdoor_window_parameters(SimpleWindowRatio(0.4))

    assert building.identifier == 'Office_Tower'
    assert building.display_name == 'Office_Tower'
    assert len(building.unique_stories) == 3
    assert len(building.all_stories()) == 8
    assert len(building.unique_room_2ds) == 6
    assert len(building.all_room_2ds()) == 16


def test_building_init_from_footprint_offset():
    """Test Building objects from_footprint with a core/perimater offset."""
    pts_1 = (Point3D(10, 10, 0), Point3D(10, 20, 0), Point3D(20, 20, 0), Point3D(20, 10, 0))
    building = Building.from_footprint(
        'Office_Tower', [Face3D(pts_1)], [5, 4, 4, 3, 3, 3, 3, 3],
        perimeter_offset=3)
    building.set_outdoor_window_parameters(SimpleWindowRatio(0.4))

    assert building.identifier == 'Office_Tower'
    assert building.display_name == 'Office_Tower'
    assert len(building.unique_stories) == 3
    assert len(building.all_stories()) == 8
    assert len(building.unique_room_2ds) == 3 * 5
    assert len(building.all_room_2ds()) == 8 * 5


def test_building_init_from_all_story_geometry():
    """Test the initialization of Building objects from_all_story_geometry."""
    pts_1 = (Point3D(0, 0, 0), Point3D(0, 10, 0), Point3D(10, 10, 0), Point3D(10, 0, 0))
    pts_2 = (Point3D(0, 0, 4), Point3D(0, 10, 4), Point3D(10, 10, 4), Point3D(10, 0, 4))
    pts_3 = (Point3D(0, 0, 8), Point3D(0, 10, 8), Point3D(5, 10, 8), Point3D(5, 0, 8))
    pts_4 = (Point3D(0, 0, 11), Point3D(0, 10, 11), Point3D(5, 10, 11), Point3D(5, 0, 11))
    story_geo = [[Face3D(pts_1)], [Face3D(pts_2)], [Face3D(pts_3)], [Face3D(pts_4)]]
    building = Building.from_all_story_geometry(
        'Office_Tower', story_geo, [4, 4, 3, 3], tolerance=0.01)
    building.set_outdoor_window_parameters(SimpleWindowRatio(0.4))

    assert building.identifier == 'Office_Tower'
    assert building.display_name == 'Office_Tower'
    assert len(building.unique_stories) == 2
    assert len(building.all_stories()) == 4
    assert len(building.unique_room_2ds) == 2
    assert len(building.all_room_2ds()) == 4


def test_building_init_from_all_story_geometry_offset():
    """Test Building objects from_all_story_geometry with a core/perimater offset."""
    pts_1 = (Point3D(0, 0, 0), Point3D(0, 10, 0), Point3D(10, 10, 0), Point3D(10, 0, 0))
    pts_2 = (Point3D(0, 0, 4), Point3D(0, 10, 4), Point3D(10, 10, 4), Point3D(10, 0, 4))
    pts_3 = (Point3D(0, 0, 8), Point3D(0, 10, 8), Point3D(5, 10, 8), Point3D(5, 0, 8))
    pts_4 = (Point3D(0, 0, 11), Point3D(0, 10, 11), Point3D(5, 10, 11), Point3D(5, 0, 11))
    story_geo = [[Face3D(pts_1)], [Face3D(pts_2)], [Face3D(pts_3)], [Face3D(pts_4)]]
    building = Building.from_all_story_geometry(
        'Office_Tower', story_geo, [4, 4, 3, 3], perimeter_offset=3, tolerance=0.01)
    building.set_outdoor_window_parameters(SimpleWindowRatio(0.4))

    assert building.identifier == 'Office_Tower'
    assert building.display_name == 'Office_Tower'
    assert len(building.unique_stories) == 2
    assert len(building.all_stories()) == 4
    assert len(building.unique_room_2ds) == 9
    assert len(building.all_room_2ds()) == 2 * 5 + 2 * 4


def test_building_init_from_all_story_geometry_edge_case_1():
    """Test Building objects from_all_story_geometry with an edge case."""
    polygon_verts = [[
        (107.3941737837053, -123.90058332855111, -7.3412644496784196e-07),
        (102.62848174575154, -111.31680648528064, -7.3412644496784196e-07),
        (108.11529717809981, -109.23890066739676, -7.3412644496784196e-07),
        (113.71137779135827, -107.11949406422913, -7.3412644496784196e-07),
        (124.32037644785611, -103.10169465481637, -7.3412644496784196e-07),
        (124.67352580740192, -104.03386144134423, -7.3412644496784196e-07),
        (136.00758020471866, -99.741399951079885, -7.3412644496784196e-07),
        (142.10780771023394, -97.431092335497723, -7.3412644496784196e-07),
        (146.5203533213477, -109.08239760629957, -7.3412644496784196e-07),
        (140.60948597825234, -111.32104468525282, -7.3412644496784196e-07),
        (129.05060543500056, -115.69859773284709, -7.3412644496784196e-07),
        (118.30852718352381, -119.76693650194935, -7.3412644496784196e-07),
        (112.78555819528032, -121.85868640512085, -7.3412644496784196e-07)
    ]]
    face = Face3D.from_array(polygon_verts)
    story_geo = [[face], [face], [face], [face]]
    building = Building.from_all_story_geometry(
        'Office_Tower', story_geo, [4.0, 4.0, 4.0, 4.7642257402299624],
        perimeter_offset=5.0, tolerance=0.01)
    assert len(building.unique_stories) == 2
    assert len(building.unique_room_2ds) == 14


def test_building_init_from_all_story_geometry_edge_case_2():
    """Test Building objects from_all_story_geometry with another edge case."""
    polygon_verts = [[
        (7.9267071033662715, 81.146691398793536, -7.3412650181126082e-07),
        (27.970712187994433, 88.171049675350162, -7.341265004301267e-07),
        (35.957768158530882, 66.542573700967381, -7.3412650041210438e-07),
        (15.779534964130475, 59.365500395894841, -7.3412649469936309e-07)
    ]]
    face = Face3D.from_array(polygon_verts)
    story_geo = [[face]]
    building = Building.from_all_story_geometry(
        'Office_Tower', story_geo, [5.0000565240740116],
        perimeter_offset=3.0, tolerance=0.01)
    assert len(building.unique_stories) == 1
    assert len(building.unique_room_2ds) == 5


def test_building_footprint_simple():
    """Test the building footprint method with simple geometry."""
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

    footprint = building.footprint(0.01)
    assert len(footprint) == 1
    assert isinstance(footprint[0], Face3D)
    assert footprint[0].holes is None
    assert len(footprint[0].vertices) == 8
    assert footprint[0].min == Point3D(0, 0, 3)
    assert footprint[0].max == Point3D(20, 20, 3)


def test_building_basement():
    """Test the initialization of Building objects and the setting of a basement."""
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
    story.multiplier = 4
    building = Building('Office_Building_1234', [story])
    building.display_name = 'Office Building'

    building.separate_top_bottom_floors()  # this should yield 3 story objects
    building.unique_stories[0].make_underground()  # make the first floor a basement
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))  # windows on top floors

    assert not building.unique_stories[0].is_above_ground
    assert building.height == 15
    assert building.story_count == 4
    assert building.story_count_above_ground == 3
    assert building.height_from_first_floor == 12
    assert building.height_above_ground == 9
    assert building.exterior_wall_area == 60 * 4 * 3


def test_building_footprint_courtyard():
    """Test the building footprint method with courtyard geometry."""
    pts_1 = (Point3D(0, 0, 3), Point3D(0, 5, 3), Point3D(15, 5, 3), Point3D(15, 0, 3))
    pts_2 = (Point3D(15, 0, 3), Point3D(15, 15, 3), Point3D(20, 15, 3), Point3D(20, 0, 3))
    pts_3 = (Point3D(0, 5, 3), Point3D(0, 20, 3), Point3D(5, 20, 3), Point3D(5, 5, 3))
    pts_4 = (Point3D(5, 15, 3), Point3D(5, 20, 3), Point3D(20, 20, 3), Point3D(20, 15, 3))
    room2d_1 = Room2D('Office1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office2', Face3D(pts_2), 3)
    room2d_3 = Room2D('Office3', Face3D(pts_3), 3)
    room2d_4 = Room2D('Office4', Face3D(pts_4), 3)
    int_rms = Room2D.intersect_adjacency([room2d_1, room2d_2, room2d_3, room2d_4], 0.01)
    story = Story('Office_Floor', int_rms)
    story.rotate_xy(5, Point3D(0, 0, 0))
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.multiplier = 4
    building = Building('Office_Building', [story])

    footprint = building.footprint(0.01)
    assert len(footprint) == 1
    assert isinstance(footprint[0], Face3D)
    assert len(footprint[0].boundary) == 8
    assert len(footprint[0].holes) == 1
    assert len(footprint[0].holes[0]) == 4


def test_building_footprint_disconnect():
    """Test the building footprint method with disconnected geometry."""
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
    story = Story('Office_Floor', int_rms)
    story.rotate_xy(5, Point3D(0, 0, 0))
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.multiplier = 4
    building = Building('Office_Building', [story])

    footprint = building.footprint(0.01)
    assert len(footprint) == 2
    assert isinstance(footprint[0], Face3D)
    assert len(footprint[0].boundary) == 8
    assert len(footprint[0].holes) == 1
    assert len(footprint[0].holes[0]) == 4
    assert isinstance(footprint[1], Face3D)
    assert len(footprint[1].boundary) == 4


def test_make_basement_stories():
    """Test the Building make_basement_stories method."""
    pts_1 = (Point3D(0, 0, 0), Point3D(0, 10, 0), Point3D(10, 10, 0), Point3D(10, 0, 0))
    pts_2 = (Point3D(10, 0, 0), Point3D(10, 10, 0), Point3D(20, 10, 0), Point3D(20, 0, 0))
    pts_3 = (Point3D(0, 10, 0), Point3D(0, 20, 0), Point3D(10, 20, 0), Point3D(10, 10, 0))
    pts_4 = (Point3D(10, 10, 0), Point3D(10, 20, 0), Point3D(20, 20, 0), Point3D(20, 10, 0))
    room2d_1 = Room2D('Office1', Face3D(pts_1), 3.5)
    room2d_2 = Room2D('Office2', Face3D(pts_2), 3.5)
    room2d_3 = Room2D('Office3', Face3D(pts_3), 3.5)
    room2d_4 = Room2D('Office4', Face3D(pts_4), 3.5)
    story = Story('Office_Floor', [room2d_1, room2d_2, room2d_3, room2d_4])
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.multiplier = 4
    building = Building('Office_Building_1234', [story])
    building = Building('Office_Building_1234', building.all_stories())
    building.unique_stories[0].room_2ds = [room2d_1.duplicate(), room2d_2.duplicate()]
    building.unique_stories[0].solve_room_2d_adjacency(0.01)

    building.make_basement_stories(2, True, 0.01)
    for room_2d in building.unique_stories[0].room_2ds:
        assert room_2d.is_ground_contact
        for bc in room_2d.boundary_conditions:
            assert isinstance(bc, (Ground, Surface))
    for room_2d in building.unique_stories[1].room_2ds:
        for bc in room_2d.boundary_conditions:
            assert isinstance(bc, (Ground, Surface))


def test_building_separate_room_2d_plenums():
    """Test the Building separate_room_2d_plenums method."""
    pts_1 = (Point3D(0, 0, 0), Point3D(0, 10, 0), Point3D(10, 10, 0), Point3D(10, 0, 0))
    pts_2 = (Point3D(10, 0, 0), Point3D(10, 10, 0), Point3D(20, 10, 0), Point3D(20, 0, 0))
    pts_3 = (Point3D(0, 10, 0), Point3D(0, 20, 0), Point3D(10, 20, 0), Point3D(10, 10, 0))
    pts_4 = (Point3D(10, 10, 0), Point3D(10, 20, 0), Point3D(20, 20, 0), Point3D(20, 10, 0))
    room2d_1 = Room2D('Office1', Face3D(pts_1), 3.5)
    room2d_2 = Room2D('Office2', Face3D(pts_2), 3.5)
    room2d_3 = Room2D('Office3', Face3D(pts_3), 3.5)
    room2d_4 = Room2D('Office4', Face3D(pts_4), 3.5)
    story = Story('Office_Floor', [room2d_1, room2d_2, room2d_3, room2d_4])
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.multiplier = 4
    building = Building('Office_Building_1234', [story])
    building = Building('Office_Building_1234', building.all_stories())
    r_pts_1 = (Point3D(0, 0, 15), Point3D(0, 20, 15), Point3D(10, 20, 20), Point3D(10, 0, 20))
    r_pts_2 = (Point3D(10, 0, 20), Point3D(10, 20, 20), Point3D(20, 20, 15), Point3D(20, 0, 15))
    building.unique_stories[-1].roof = \
        RoofSpecification([Face3D(r_pts_1), Face3D(r_pts_2)])
    for room in building.unique_stories[0]:
        room.is_ground_contact = True
    for room in building.unique_stories[-1]:
        room.is_top_exposed = True
    assert len(building.unique_room_2ds) == 16
    assert len(building.unique_stories) == 4

    building_dup = building.duplicate()
    room_ids = [room.identifier for room in building_dup.unique_room_2ds]
    plenums = building_dup.separate_room_2d_plenums(room_ids, 3.0)
    assert len(plenums) == 16
    srf_bcs = [bc for room in plenums for bc in room.boundary_conditions
               if isinstance(bc, Surface)]
    assert len(srf_bcs) == 32
    assert len(building_dup.unique_room_2ds) == 32
    assert len(building_dup.unique_stories) == 8
    for story in building_dup.unique_stories:
        story.check_missing_adjacencies(False) == ''

    building_dup = building.duplicate()
    room_ids = room_ids[:2]
    plenums = building_dup.separate_room_2d_plenums(room_ids, 3.0)
    assert len(plenums) == 2
    srf_bcs = [bc for room in plenums for bc in room.boundary_conditions
               if isinstance(bc, Surface)]
    assert len(srf_bcs) == 2
    assert len(building_dup.unique_room_2ds) == 18
    assert len(building_dup.unique_stories) == 5
    for story in building_dup.unique_stories:
        story.check_missing_adjacencies(False) == ''

    building_dup = building.duplicate()
    room_ids = [room.identifier for room in building_dup.unique_room_2ds]
    plenums = building_dup.separate_room_2d_plenums(room_ids, 3.0, True)
    assert len(plenums) == 16
    assert len(building_dup.unique_room_2ds) == 32
    assert len(building_dup.unique_stories) == 8


def test_check_collisions_between_stories():
    """Test the Building check_collisions_between_stories method."""
    pts_1 = (Point3D(0, 0, 0), Point3D(0, 10, 0), Point3D(10, 10, 0), Point3D(10, 0, 0))
    pts_2 = (Point3D(10, 0, 0), Point3D(10, 10, 0), Point3D(20, 10, 0), Point3D(20, 0, 0))
    pts_3 = (Point3D(0, 10, 0), Point3D(0, 20, 0), Point3D(10, 20, 0), Point3D(10, 10, 0))
    pts_4 = (Point3D(10, 10, 0), Point3D(10, 20, 0), Point3D(20, 20, 0), Point3D(20, 10, 0))
    room2d_1 = Room2D('Office1', Face3D(pts_1), 3.5)
    room2d_2 = Room2D('Office2', Face3D(pts_2), 3.5)
    room2d_3 = Room2D('Office3', Face3D(pts_3), 3.5)
    room2d_4 = Room2D('Office4', Face3D(pts_4), 3.5)
    story = Story('Office_Floor', [room2d_1, room2d_2, room2d_3, room2d_4])
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.multiplier = 4
    building = Building('Office_Building_1234', [story])
    building = Building('Office_Building_1234', building.all_stories())
    for room in building.unique_stories[0]:
        room.is_ground_contact = True
    for room in building.unique_stories[-1]:
        room.is_top_exposed = True

    assert building.check_collisions_between_stories(raise_exception=False) == ''

    building.unique_stories[0].room_2ds[0].floor_to_ceiling_height = 4
    assert building.check_collisions_between_stories(raise_exception=False) != ''

    building.unique_stories[0].room_2ds[0].floor_to_ceiling_height = 3.5
    building.unique_stories[1].room_2ds[0].move(Vector3D(0, 0, -0.5))
    assert building.check_collisions_between_stories(raise_exception=False) != ''


def test_honeybee_ceiling_plenum():
    """Test the Room2D.ceiling_plenum_depth translation to honeybee."""
    # simple 10 x 10 rooms
    pts1 = (Point3D(0, 0, 0), Point3D(10, 0, 0), Point3D(10, 10, 0), Point3D(0, 10, 0))
    pts2 = (Point3D(10, 0, 0), Point3D(20, 0, 0), Point3D(20, 10, 0), Point3D(10, 10, 0))

    # two rooms with different plenum depths
    room2d_full = Room2D(
        'R1-full', floor_geometry=Face3D(pts1), floor_to_ceiling_height=4,
        is_ground_contact=True, is_top_exposed=True)
    room2d_plenum = Room2D(
        'R2-plenum', floor_geometry=Face3D(pts2), floor_to_ceiling_height=4,
        is_ground_contact=True, is_top_exposed=True)
    room2d_plenum.ceiling_plenum_depth = 1

    story = Story('S1', [room2d_full, room2d_plenum])
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.multiplier = 4
    building = Building('Office_Building_1234', [story])

    # check the ceiling condition w/o plenum
    no_plenum_model = building.to_honeybee(tolerance=0.01, exclude_plenums=True)
    no_plenum_rooms = no_plenum_model.rooms
    assert len(no_plenum_rooms) == 2
    assert no_plenum_rooms[0].volume == pytest.approx(400, rel=1e-3)
    assert no_plenum_rooms[1].volume == pytest.approx(400, rel=1e-3)

    # check the ceiling condition with plenum
    assert room2d_plenum.check_plenum_depths(0.01, False) == ''
    plenum_model = building.to_honeybee(tolerance=0.01)
    plenum_rooms = plenum_model.rooms
    assert len(plenum_rooms) == 3
    assert plenum_rooms[0].volume == pytest.approx(400, rel=1e-3)
    assert plenum_rooms[1].volume == pytest.approx(300, rel=1e-3)
    assert plenum_rooms[2].volume == pytest.approx(100, rel=1e-3)

    plenum = plenum_rooms[-1]
    assert len(plenum[:]) == 6
    for face in plenum.faces:
        if face.identifier == 'R2-plenum_Ceiling_Plenum..Face0':
            assert isinstance(face.boundary_condition, Surface)
        elif face.identifier == 'R2-plenum_Ceiling_Plenum..Face1':
            assert isinstance(face.boundary_condition, Outdoors)
        elif face.identifier == 'R2-plenum_Ceiling_Plenum..Face2':
            assert isinstance(face.boundary_condition, Outdoors)
        elif face.identifier == 'R2-plenum_Ceiling_Plenum..Face3':
            assert isinstance(face.boundary_condition, Outdoors)
        elif face.identifier == 'R2-plenum_Ceiling_Plenum..Face4':
            assert _is_interior(face.boundary_condition)
        elif face.identifier == 'R2-plenum_Ceiling_Plenum..Face5':
            assert isinstance(face.boundary_condition, Outdoors)  # Roof exposed outdoors
        else:
            assert False

    # check that no plenum is produced when room does not have_ceiling
    room2d_plenum.has_ceiling = False
    assert room2d_plenum.check_plenum_depths(0.01, False) != ''
    no_plenum_model = building.to_honeybee(tolerance=0.01)
    no_plenum_rooms = no_plenum_model.rooms
    assert len(no_plenum_rooms) == 2
    assert no_plenum_rooms[0].volume == pytest.approx(400, rel=1e-3)
    assert no_plenum_rooms[1].volume == pytest.approx(400, rel=1e-3)


def test_honeybee_floor_plenum():
    """Test the Room2D.floor_plenum_depth translation to honeybee."""
    # simple 10 x 10 rooms
    pts1 = (Point3D(0, 0, 0), Point3D(10, 0, 0), Point3D(10, 10, 0), Point3D(0, 10, 0))
    pts2 = (Point3D(10, 0, 0), Point3D(20, 0, 0), Point3D(20, 10, 0), Point3D(10, 10, 0))

    # Two rooms with different plenum depths
    room2d_full = Room2D(
        'R1-full', floor_geometry=Face3D(pts1), floor_to_ceiling_height=4,
        is_ground_contact=True, is_top_exposed=True)
    room2d_plenum = Room2D(
        'R2-plenum', floor_geometry=Face3D(pts2), floor_to_ceiling_height=4,
        is_ground_contact=True, is_top_exposed=True)
    room2d_plenum.floor_plenum_depth = 1

    story = Story('S1', [room2d_full, room2d_plenum])
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.multiplier = 4
    building = Building('Office_Building_1234', [story])

    # check the floor condition w/o plenum
    no_plenum_model = building.to_honeybee(tolerance=0.01, exclude_plenums=True)
    no_plenum_rooms = no_plenum_model.rooms
    assert len(no_plenum_rooms) == 2
    assert no_plenum_rooms[0].volume == pytest.approx(400, rel=1e-3)
    assert no_plenum_rooms[1].volume == pytest.approx(400, rel=1e-3)

    # check the floor condition with plenum
    assert room2d_plenum.check_plenum_depths(0.01, False) == ''
    plenum_model = building.to_honeybee(tolerance=0.01)
    plenum_rooms = plenum_model.rooms
    assert len(plenum_rooms) == 3
    assert plenum_rooms[0].volume == pytest.approx(100, rel=1e-3)
    assert plenum_rooms[1].volume == pytest.approx(400, rel=1e-3)
    assert plenum_rooms[2].volume == pytest.approx(300, rel=1e-3)

    plenum = plenum_rooms[0]
    assert len(plenum[:]) == 6
    for face in plenum.faces:
        if face.identifier == 'R2-plenum_Floor_Plenum..Face0':
            assert isinstance(face.boundary_condition, Ground)
        elif face.identifier == 'R2-plenum_Floor_Plenum..Face1':
            assert isinstance(face.boundary_condition, Outdoors)
        elif face.identifier == 'R2-plenum_Floor_Plenum..Face2':
            assert isinstance(face.boundary_condition, Outdoors)
        elif face.identifier == 'R2-plenum_Floor_Plenum..Face3':
            assert isinstance(face.boundary_condition, Outdoors)
        elif face.identifier == 'R2-plenum_Floor_Plenum..Face4':
            assert _is_interior(face.boundary_condition)
        elif face.identifier == 'R2-plenum_Floor_Plenum..Face5':
            assert isinstance(face.boundary_condition, Surface)
        else:
            assert False

    # check that no plenum is produced when room does not have_floor
    room2d_plenum.has_floor = False
    assert room2d_plenum.check_plenum_depths(0.01, False) != ''
    no_plenum_model = building.to_honeybee(tolerance=0.01)
    no_plenum_rooms = no_plenum_model.rooms
    assert len(no_plenum_rooms) == 2
    assert no_plenum_rooms[0].volume == pytest.approx(400, rel=1e-3)
    assert no_plenum_rooms[1].volume == pytest.approx(400, rel=1e-3)


def test_honeybee_ceiling_and_floor_plenum():
    """Test the the translation of both plenum depths to honeybee."""
    # simple 10 x 10 rooms
    pts1 = (Point3D(0, 0, 0), Point3D(10, 0, 0), Point3D(10, 10, 0), Point3D(0, 10, 0))
    pts2 = (Point3D(10, 0, 0), Point3D(20, 0, 0), Point3D(20, 10, 0), Point3D(10, 10, 0))

    # Two rooms with different floor heights
    room2d_full = Room2D(
        'R1-full', floor_geometry=Face3D(pts1), floor_to_ceiling_height=4,
        is_ground_contact=True, is_top_exposed=True)
    room2d_plenum = Room2D(
        'R2-plenum', floor_geometry=Face3D(pts2), floor_to_ceiling_height=4,
        is_ground_contact=True, is_top_exposed=True)
    room2d_plenum.ceiling_plenum_depth = 0.5
    room2d_plenum.floor_plenum_depth = 0.5

    story = Story('S1', [room2d_full, room2d_plenum])
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.multiplier = 4
    building = Building('Office_Building_1234', [story])

    # check the floor condition w/o plenum
    no_plenum_model = building.to_honeybee(tolerance=0.01, exclude_plenums=True)
    no_plenum_rooms = no_plenum_model.rooms
    assert len(no_plenum_rooms) == 2
    assert no_plenum_rooms[0].volume == pytest.approx(400, rel=1e-3)
    assert no_plenum_rooms[1].volume == pytest.approx(400, rel=1e-3)

    # check the floor condition with plenum
    plenum_model = building.to_honeybee(tolerance=0.01)
    plenum_rooms = plenum_model.rooms
    assert len(plenum_rooms) == 4
    assert plenum_rooms[0].volume == pytest.approx(50, rel=1e-3)
    assert plenum_rooms[1].volume == pytest.approx(400, rel=1e-3)
    assert plenum_rooms[2].volume == pytest.approx(300, rel=1e-3)
    assert plenum_rooms[3].volume == pytest.approx(50, rel=1e-3)

    plenum = plenum_rooms[0]
    assert len(plenum[:]) == 6
    for face in plenum.faces:
        if face.identifier == 'R2-plenum_Floor_Plenum..Face0':
            assert isinstance(face.boundary_condition, Ground)
        elif face.identifier == 'R2-plenum_Floor_Plenum..Face1':
            assert isinstance(face.boundary_condition, Outdoors)
        elif face.identifier == 'R2-plenum_Floor_Plenum..Face2':
            assert isinstance(face.boundary_condition, Outdoors)
        elif face.identifier == 'R2-plenum_Floor_Plenum..Face3':
            assert isinstance(face.boundary_condition, Outdoors)
        elif face.identifier == 'R2-plenum_Floor_Plenum..Face4':
            assert _is_interior(face.boundary_condition)
        elif face.identifier == 'R2-plenum_Floor_Plenum..Face5':
            assert isinstance(face.boundary_condition, Surface)
        else:
            assert False

    plenum = plenum_rooms[-1]
    assert len(plenum[:]) == 6
    for face in plenum.faces:
        if face.identifier == 'R2-plenum_Ceiling_Plenum..Face0':
            assert isinstance(face.boundary_condition, Surface)
        elif face.identifier == 'R2-plenum_Ceiling_Plenum..Face1':
            assert isinstance(face.boundary_condition, Outdoors)
        elif face.identifier == 'R2-plenum_Ceiling_Plenum..Face2':
            assert isinstance(face.boundary_condition, Outdoors)
        elif face.identifier == 'R2-plenum_Ceiling_Plenum..Face3':
            assert isinstance(face.boundary_condition, Outdoors)
        elif face.identifier == 'R2-plenum_Ceiling_Plenum..Face4':
            assert _is_interior(face.boundary_condition)
        elif face.identifier == 'R2-plenum_Ceiling_Plenum..Face5':
            assert isinstance(face.boundary_condition, Outdoors)  # Roof exposed outdoors
        else:
            assert False

    # check that no plenum is produced when room does not have_floor
    room2d_plenum.has_floor = False
    room2d_plenum.has_ceiling = False
    no_plenum_model = building.to_honeybee(tolerance=0.01)
    no_plenum_rooms = no_plenum_model.rooms
    assert len(no_plenum_rooms) == 2
    assert no_plenum_rooms[0].volume == pytest.approx(400, rel=1e-3)
    assert no_plenum_rooms[1].volume == pytest.approx(400, rel=1e-3)


def test_building_shade_representation():
    """Test the Building shade_representation method."""
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
    story.multiplier = 4
    building = Building('Office_Building', [story])

    shade_rep = building.shade_representation(tolerance=0.01)
    assert len(shade_rep) == 8
    shd_area = sum([shd.area for shd in shade_rep])
    assert shd_area == building.exterior_wall_area


def test_building_window_shading_parameters():
    """Test the Building set_outdoor_window_parameters method."""
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
    story.multiplier = 4
    building = Building('Office_Building', [story])

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
    assert len(set(story.identifier for story in building.unique_stories)) == 3
    assert len(building.all_stories()) == 4
    assert len(building.unique_room_2ds) == 12


def test_move():
    """Test the Building move method."""
    pts_1 = (Point3D(0, 0, 3), Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(0, 10, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(20, 0, 3), Point3D(20, 10, 3), Point3D(10, 10, 3))
    room2d_1 = Room2D('Office_1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office_2', Face3D(pts_2), 3)
    story = Story('Office_Floor', [room2d_1, room2d_2])
    story.solve_room_2d_adjacency(0.01)
    story.multiplier = 4
    building = Building('Office_Building', [story])

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
    room2d_1 = Room2D('Office1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office2', Face3D(pts_2), 3)
    story = Story('Office_Floor', [room2d_1, room2d_2])
    story.solve_room_2d_adjacency(0.01)
    story.multiplier = 4
    building = Building('Office_Building', [story])

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
    room = Room2D('Square_Shoebox', Face3D(pts, plane), 3)
    story = Story('Office_Floor', [room])
    story.multiplier = 4
    building = Building('Office_Building', [story])
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

    assert building.floor_area == pytest.approx(test_1.floor_area, rel=1e-3)
    assert building.volume == pytest.approx(test_1.volume, rel=1e-3)
    assert building.height_from_first_floor == \
        pytest.approx(test_1.height_from_first_floor, rel=1e-3)
    assert building.height == 14


def test_reflect():
    """Test the Building reflect method."""
    pts = (Point3D(1, 1, 2), Point3D(2, 1, 2), Point3D(2, 2, 2), Point3D(1, 2, 2))
    plane = Plane(Vector3D(0, 0, 1), Point3D(0, 0, 2))
    room = Room2D('Square_Shoebox', Face3D(pts, plane), 3)
    story = Story('Office_Floor', [room])
    story.multiplier = 4
    building = Building('Office_Building', [story])

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
    room2d_1 = Room2D('Office1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office2', Face3D(pts_2), 3)
    story = Story('Office_Floor', [room2d_1, room2d_2])
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.multiplier = 4
    building = Building('Office_Building', [story])

    hb_model = building.to_honeybee(False, 0.01)
    assert isinstance(hb_model, Model)
    assert len(hb_model.rooms) == 8
    assert len(hb_model.rooms[0]) == 6
    assert hb_model.rooms[0].volume == 300
    assert hb_model.rooms[0].floor_area == 100
    assert hb_model.rooms[0].exterior_wall_area == 90
    assert hb_model.rooms[0].exterior_aperture_area == pytest.approx(90 * 0.4, rel=1e-3)
    assert hb_model.rooms[0].average_floor_height == 3
    assert hb_model.rooms[0].check_solid(0.01, 1) == ''

    assert isinstance(hb_model.rooms[0][1].boundary_condition, Outdoors)
    assert isinstance(hb_model.rooms[0][2].boundary_condition, Surface)
    assert hb_model.rooms[0][2].boundary_condition.boundary_condition_object == \
        hb_model.rooms[1][4].identifier
    assert len(hb_model.rooms[0][1].apertures) == 1
    assert len(hb_model.rooms[0][2].apertures) == 0

    assert hb_model.check_duplicate_room_identifiers() == ''
    assert hb_model.check_duplicate_face_identifiers() == ''
    assert hb_model.check_duplicate_sub_face_identifiers() == ''
    assert hb_model.check_missing_adjacencies() == ''

    hb_model = building.to_honeybee(True, 0.01)
    assert len(hb_model.rooms) == 2
    for room in hb_model.rooms:
        assert room.multiplier == 4

    assert hb_model.check_duplicate_room_identifiers() == ''
    assert hb_model.check_duplicate_face_identifiers() == ''
    assert hb_model.check_duplicate_sub_face_identifiers() == ''
    assert hb_model.check_missing_adjacencies() == ''


def test_district_to_honeybee():
    """Test the district_to_honeybee method."""
    pts_1 = (Point3D(0, 0, 3), Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(0, 10, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(20, 0, 3), Point3D(20, 10, 3), Point3D(10, 10, 3))
    pts_3 = (Point3D(0, 20, 3), Point3D(20, 20, 3), Point3D(20, 30, 3), Point3D(0, 30, 3))
    room2d_1 = Room2D('Office1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office2', Face3D(pts_2), 3)
    room2d_3 = Room2D('Office3', Face3D(pts_3), 3)
    story_big = Story('Office_Floor_Big', [room2d_3])
    story = Story('Office_Floor', [room2d_1, room2d_2])
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.multiplier = 4
    building = Building('Office_Building', [story])
    story_big.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story_big.multiplier = 4
    building_big = Building('Office_Building_Big', [story_big])

    hb_model = Building.district_to_honeybee([building, building_big], False, 0.01)
    assert isinstance(hb_model, Model)
    assert len(hb_model.rooms) == 12
    assert len(hb_model.rooms[-1]) == 6
    assert hb_model.rooms[-1].volume == 600
    assert hb_model.rooms[-1].floor_area == 200
    assert hb_model.rooms[-1].exterior_wall_area == 180

    hb_model = Building.district_to_honeybee([building, building_big], True, 0.01)
    assert isinstance(hb_model, Model)
    assert len(hb_model.rooms) == 3
    for room in hb_model.rooms:
        assert room.multiplier == 4


def test_buildings_to_honeybee():
    """Test the buildings_to_honeybee method."""
    pts_1 = (Point3D(0, 0, 3), Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(0, 10, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(20, 0, 3), Point3D(20, 10, 3), Point3D(10, 10, 3))
    pts_3 = (Point3D(0, 20, 3), Point3D(20, 20, 3), Point3D(20, 30, 3), Point3D(0, 30, 3))
    room2d_1 = Room2D('Office1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Office2', Face3D(pts_2), 3)
    room2d_3 = Room2D('Office3', Face3D(pts_3), 3)
    story_big = Story('Office_Floor_Big', [room2d_3])
    story = Story('Office_Floor', [room2d_1, room2d_2])
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.multiplier = 4
    building = Building('Office_Building', [story])
    story_big.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story_big.multiplier = 4
    building_big = Building('Office_Building_Big', [story_big])

    hb_models = Building.buildings_to_honeybee(
        [building, building_big], None, None, False)
    assert len(hb_models) == 2
    assert isinstance(hb_models[0], Model)
    assert len(hb_models[0].orphaned_shades) == 4
    assert isinstance(hb_models[-1], Model)
    assert len(hb_models[-1].rooms) == 4
    assert len(hb_models[-1].rooms[-1]) == 6
    assert hb_models[-1].rooms[-1].volume == 600
    assert hb_models[-1].rooms[-1].floor_area == 200
    assert hb_models[-1].rooms[-1].exterior_wall_area == 180

    hb_models = Building.buildings_to_honeybee(
        [building, building_big], None, 5, True)
    assert len(hb_models) == 2
    assert isinstance(hb_models[0], Model)
    assert len(hb_models[0].orphaned_shades) == 0
    assert len(hb_models[0].rooms) == 2
    for room in hb_models[0].rooms:
        assert room.multiplier == 4

    hb_models = Building.buildings_to_honeybee(
        [building, building_big], cap=True)
    assert len(hb_models) == 2
    assert isinstance(hb_models[0], Model)
    assert len(hb_models[0].orphaned_shades) == 5


def test_to_dict():
    """Test the Building to_dict method."""
    pts_1 = (Point3D(0, 0, 2), Point3D(10, 0, 2), Point3D(10, 10, 2), Point3D(0, 10, 2))
    pts_2 = (Point3D(10, 0, 3), Point3D(20, 0, 3), Point3D(20, 10, 3), Point3D(10, 10, 3))
    room2d_1 = Room2D('Office1', Face3D(pts_1), 5)
    room2d_2 = Room2D('Office2', Face3D(pts_2), 3)
    story = Story('Office_Floor', [room2d_1, room2d_2])
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.set_outdoor_shading_parameters(Overhang(1))
    story.multiplier = 4
    building = Building('Office_Building', [story])
    building.separate_top_bottom_floors()

    bd = building.to_dict()
    assert bd['type'] == 'Building'
    assert bd['identifier'] == 'Office_Building'
    assert bd['display_name'] == 'Office_Building'
    assert 'unique_stories' in bd
    assert len(bd['unique_stories']) == 3
    assert 'properties' in bd
    assert bd['properties']['type'] == 'BuildingProperties'


def test_to_from_dict():
    """Test the to/from dict of Building objects."""
    pts_1 = (Point3D(0, 0, 2), Point3D(10, 0, 2), Point3D(10, 10, 2), Point3D(0, 10, 2))
    pts_2 = (Point3D(10, 0, 3), Point3D(20, 0, 3), Point3D(20, 10, 3), Point3D(10, 10, 3))
    room2d_1 = Room2D('Office1', Face3D(pts_1), 5)
    room2d_2 = Room2D('Office2', Face3D(pts_2), 3)
    story = Story('Office_Floor', [room2d_1, room2d_2])
    story.solve_room_2d_adjacency(0.01)
    story.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    story.set_outdoor_shading_parameters(Overhang(1))
    story.multiplier = 4
    building = Building('Office_Building', [story])
    building.separate_top_bottom_floors()

    building_dict = building.to_dict()
    new_building = Building.from_dict(building_dict)
    assert isinstance(new_building, Building)
    assert new_building.to_dict() == building_dict


def test_from_honeybee():
    """Test the from_honeybee method of Building objects."""
    room_south = Room.from_box('SouthZone', 5, 5, 3, origin=Point3D(0, 0, 0))
    room_north = Room.from_box('NorthZone', 5, 5, 3, origin=Point3D(0, 5, 0))
    room_up = Room.from_box('UpZone', 5, 5, 3, origin=Point3D(0, 5, 3))
    room_south[1].apertures_by_ratio(0.4, 0.01)
    room_south[3].apertures_by_ratio(0.4, 0.01)
    room_north[3].apertures_by_ratio(0.4, 0.01)
    Room.solve_adjacency([room_south, room_north], 0.01)

    model = Model('Test_Building', [room_south, room_north, room_up], tolerance=0.01)
    bldg = Building.from_honeybee(model)

    assert bldg.identifier == 'Test_Building'
    assert len(bldg.unique_stories) == 2

    bound_cs = [b for room in bldg.unique_room_2ds for b in room.boundary_conditions
                if isinstance(b, Surface)]
    assert len(bound_cs) == 2
    for story in bldg.unique_stories:
        story.check_missing_adjacencies()


def test_writer():
    """Test the Building writer object."""
    pts = (Point3D(50, 50, 3), Point3D(60, 50, 3), Point3D(60, 60, 3), Point3D(50, 60, 3))
    bldg = Building.from_footprint('TestBldg', [Face3D(pts)], [5, 4, 3, 3], tolerance=0.01)

    writers = [mod for mod in dir(bldg.to) if not mod.startswith('_')]
    for writer in writers:
        assert callable(getattr(bldg.to, writer))


def _is_interior(bc):
    """Test if adiabatic instance, or if honeybee-energy not installed,
    if using default Outdoors.
    """
    if isinstance(bc, Surface):
        return True
    try:
        return isinstance(bc, type(bcs.adiabatic))
    except AttributeError:
        return isinstance(bc, Outdoors)
