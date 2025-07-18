# coding=utf-8
import pytest
import json
import os

from ladybug_geometry.geometry2d import Point2D, Vector2D, LineSegment2D, \
    Polyline2D, Polygon2D
from ladybug_geometry.geometry3d import Point3D, Vector3D, LineSegment3D, Plane, \
    Face3D, Polyface3D
from honeybee.boundarycondition import Outdoors, Ground, Surface
from honeybee.boundarycondition import boundary_conditions as bcs
from honeybee.facetype import AirBoundary
from honeybee.room import Room

from dragonfly.room2d import Room2D
from dragonfly.story import Story
from dragonfly.building import Building
from dragonfly.model import Model
from dragonfly.windowparameter import SimpleWindowRatio, SingleWindow, \
    RepeatingWindowRatio, DetailedWindows
from dragonfly.skylightparameter import DetailedSkylights
from dragonfly.shadingparameter import Overhang


def test_room2d_init():
    """Test the initialization of Room2D objects and basic properties."""
    pts = (Point3D(1, 1, 2), Point3D(1, 2, 2), Point3D(2, 2, 2), Point3D(2, 1, 2))
    plane = Plane(Vector3D(0, 0, 1), Point3D(0, 0, 2))
    room2d = Room2D('ZoneCLOSET920980', Face3D(pts, plane), 3)
    str(room2d)  # test the string representation

    assert room2d.identifier == 'ZoneCLOSET920980'
    assert room2d.display_name == 'ZoneCLOSET920980'
    assert isinstance(room2d.floor_geometry, Face3D)
    assert len(room2d.floor_geometry.vertices) == 4
    assert room2d.floor_geometry.vertices == tuple(reversed(pts))
    assert len(room2d) == 4
    assert room2d.floor_to_ceiling_height == 3
    assert all([isinstance(bc, Outdoors) for bc in room2d.boundary_conditions])
    assert all([glzpar is None for glzpar in room2d.window_parameters])
    assert all([shdpar is None for shdpar in room2d.shading_parameters])
    assert not room2d.is_ground_contact
    assert not room2d.is_top_exposed
    assert room2d.parent is None
    assert not room2d.has_parent
    assert all([isinstance(seg, LineSegment3D) for seg in room2d.floor_segments])
    assert all([isinstance(seg, LineSegment2D) for seg in room2d.floor_segments_2d])
    assert room2d.segment_count == 4
    assert all([isinstance(vec, Vector2D) for vec in room2d.segment_normals])
    assert room2d.floor_height == 2
    assert room2d.ceiling_height == 5
    assert room2d.volume == 3
    assert room2d.floor_area == 1
    assert room2d.exterior_wall_area == 12
    assert room2d.exterior_aperture_area == 0
    assert isinstance(room2d[0], LineSegment3D)
    assert isinstance(room2d.label_point(0.01), Point3D)
    assert room2d.zone == room2d.identifier
    room2d.zone = 'Closets'
    assert room2d.zone == 'Closets'


def test_room2d_init_with_windows():
    """Test the initialization of Room2D objects with windows."""
    pts = (Point3D(0, 0, 3), Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(0, 10, 3))
    ashrae_base = SimpleWindowRatio(0.4)
    overhang = Overhang(1)
    boundarycs = (bcs.outdoors, bcs.ground, bcs.outdoors, bcs.ground)
    window = (ashrae_base, None, ashrae_base, None)
    shading = (overhang, None, None, None)
    room2d = Room2D('SquareShoebox', Face3D(pts), 3, boundarycs, window, shading)

    assert len(room2d.floor_geometry.vertices) == 4
    assert room2d.floor_geometry.vertices == tuple(pts)
    assert len(room2d) == 4
    assert room2d.floor_to_ceiling_height == 3
    assert isinstance(room2d.boundary_conditions[0], Outdoors)
    assert isinstance(room2d.boundary_conditions[1], Ground)
    assert room2d.window_parameters[0] == ashrae_base
    assert room2d.window_parameters[1] is None
    assert room2d.shading_parameters[0] == overhang
    assert room2d.shading_parameters[1] is None

    assert room2d.floor_height == 3
    assert room2d.ceiling_height == 6
    assert room2d.volume == 300
    assert room2d.floor_area == 100
    assert room2d.exterior_wall_area == 60
    assert room2d.exterior_aperture_area == 60 * 0.4


def test_room_init_with_hole():
    """Test the initialization of Room2D with a hole."""
    bound_pts = [Point3D(0, 0), Point3D(3, 0), Point3D(3, 3), Point3D(0, 3)]
    hole_pts = [Point3D(1, 1, 0), Point3D(2, 1, 0), Point3D(2, 2, 0), Point3D(1, 2, 0)]
    face = Face3D(bound_pts, None, [hole_pts])
    room2d = Room2D('DonutRoom', face, 3)

    assert len(room2d.floor_geometry.vertices) == 10
    assert len(room2d) == 8
    assert room2d.floor_to_ceiling_height == 3
    assert all([isinstance(seg, LineSegment3D) for seg in room2d.floor_segments])
    assert all([isinstance(seg, LineSegment2D) for seg in room2d.floor_segments_2d])
    assert room2d.segment_count == 8
    assert all([isinstance(vec, Vector2D) for vec in room2d.segment_normals])
    assert room2d.floor_height == 0
    assert room2d.ceiling_height == 3
    assert room2d.volume == 24
    assert room2d.floor_area == 8
    assert room2d.exterior_wall_area == 48
    assert room2d.exterior_aperture_area == 0


def test_room2d_init_invalid():
    """Test the initialization of Room2D objects with invalid inputs."""
    pts = (Point3D(0, 0, 3), Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(0, 10, 3))
    ashrae_base = SimpleWindowRatio(0.4)
    overhang = Overhang(1)
    boundarycs = [bcs.outdoors, bcs.ground, bcs.outdoors, bcs.ground]
    window = [ashrae_base, None, ashrae_base, None]
    shading = [overhang, None, None, None]
    Room2D('SquareShoebox', Face3D(pts), 3, boundarycs, window, shading)

    old_bc = boundarycs.pop(-1)
    with pytest.raises(AssertionError):
        Room2D('SquareShoebox', Face3D(pts), 3, boundarycs, window, shading)
    boundarycs.append(old_bc)

    old_glz = window.pop(-1)
    with pytest.raises(AssertionError):
        Room2D('SquareShoebox', Face3D(pts), 3, boundarycs, window, shading)
    window.append(old_glz)

    old_shd = shading.pop(-1)
    with pytest.raises(AssertionError):
        Room2D('SquareShoebox', Face3D(pts), 3, boundarycs, window, shading)
    shading.append(old_shd)

    new_bcs = [bcs.ground, bcs.outdoors, bcs.outdoors, bcs.ground]
    with pytest.raises(AssertionError):
        Room2D('SquareShoebox', Face3D(pts), 3, new_bcs, window, shading)

    new_glz = [None, ashrae_base, ashrae_base, None]
    with pytest.raises(AssertionError):
        Room2D('SquareShoebox', Face3D(pts), 3, boundarycs, new_glz, shading)


def test_room2d_init_clockwise():
    """Test the initialization of Room2D objects with clockwise vertices."""
    pts = (Point3D(0, 10, 3), Point3D(10, 10, 3), Point3D(10, 0, 3), Point3D(0, 0, 3))
    ashrae_base = SimpleWindowRatio(0.4)
    overhang = Overhang(1)
    boundarycs = (bcs.outdoors, bcs.outdoors, bcs.ground, bcs.ground)
    window = (ashrae_base, ashrae_base, None, None)
    shading = (overhang, None, None, None)
    room2d = Room2D('TestZone', Face3D(pts), 3, boundarycs, window, shading)

    assert room2d.floor_geometry.boundary == tuple(reversed(pts))
    assert room2d.boundary_conditions == tuple(reversed(boundarycs))
    assert room2d.window_parameters == tuple(reversed(window))
    assert room2d.shading_parameters == tuple(reversed(shading))

    pts_hole = (Point3D(2, 8, 3), Point3D(8, 8, 3), Point3D(8, 2, 3), Point3D(2, 2, 3))
    boundarycs = (bcs.outdoors, bcs.outdoors, bcs.ground, bcs.ground,
                  bcs.outdoors, bcs.outdoors, bcs.ground, bcs.ground)
    window = (ashrae_base, ashrae_base, None, None, ashrae_base, ashrae_base, None, None)
    shading = (overhang, None, None, None, overhang, None, None, None)
    room2d = Room2D('TestZone', Face3D(pts, holes=[pts_hole]),
                    3, boundarycs, window, shading)

    assert room2d.floor_geometry.boundary == tuple(reversed(pts))
    assert room2d.floor_geometry.holes[0] == pts_hole
    assert room2d.boundary_conditions == \
        (bcs.ground, bcs.ground, bcs.outdoors, bcs.outdoors,
         bcs.outdoors, bcs.outdoors, bcs.ground, bcs.ground)
    assert room2d.window_parameters == \
        (None, None, ashrae_base, ashrae_base, ashrae_base, ashrae_base, None, None)
    assert room2d.shading_parameters == \
        (None, None, None, overhang, overhang, None, None, None)


def test_room2d_init_from_polygon():
    """Test the initialization of Room2D objects from a Polygon2D."""
    pts = (Point2D(0, 0), Point2D(10, 0), Point2D(10, 10), Point2D(0, 10))
    polygon = Polygon2D(pts)
    ashrae_base = SimpleWindowRatio(0.4)
    overhang = Overhang(1)
    boundarycs = (bcs.outdoors, bcs.ground, bcs.outdoors, bcs.ground)
    window = (ashrae_base, None, ashrae_base, None)
    shading = (overhang, None, None, None)
    room2d = Room2D.from_polygon('SquareShoebox', polygon, 3, 3,
                                 boundarycs, window, shading)

    assert len(room2d.floor_geometry.vertices) == 4
    assert len(room2d) == 4
    assert room2d.floor_to_ceiling_height == 3
    assert isinstance(room2d.boundary_conditions[0], Outdoors)
    assert isinstance(room2d.boundary_conditions[1], Ground)
    assert room2d.window_parameters[0] == ashrae_base
    assert room2d.window_parameters[1] is None
    assert room2d.shading_parameters[0] == overhang
    assert room2d.shading_parameters[1] is None

    assert room2d.floor_height == 3
    assert room2d.ceiling_height == 6
    assert room2d.volume == 300
    assert room2d.floor_area == 100
    assert room2d.exterior_wall_area == 60
    assert room2d.exterior_aperture_area == 60 * 0.4


def test_room2d_init_from_polygon_clockwise():
    """Test the initialization of Room2D objects from a clockwise Polygon2D."""
    pts_3d = (Point3D(0, 10, 3), Point3D(10, 10, 3), Point3D(10, 0, 3), Point3D(0, 0, 3))
    pts = (Point2D(0, 10), Point2D(10, 10), Point2D(10, 0), Point2D(0, 0))
    polygon = Polygon2D(pts)
    ashrae_base = SimpleWindowRatio(0.4)
    overhang = Overhang(1)
    boundarycs = (bcs.outdoors, bcs.outdoors, bcs.ground, bcs.ground)
    window = (ashrae_base, ashrae_base, None, None)
    shading = (overhang, None, None, None)
    room2d = Room2D.from_polygon('SquareShoebox', polygon, 3, 3,
                                 boundarycs, window, shading)

    assert room2d.floor_geometry.boundary == tuple(reversed(pts_3d))
    assert room2d.boundary_conditions == tuple(reversed(boundarycs))
    assert room2d.window_parameters == tuple(reversed(window))
    assert room2d.shading_parameters == tuple(reversed(shading))


def test_room2d_init_from_vertices():
    """Test the initialization of Room2D objects from 2D vertices."""
    pts = (Point2D(0, 0), Point2D(10, 0), Point2D(10, 10), Point2D(0, 10))
    ashrae_base = SimpleWindowRatio(0.4)
    overhang = Overhang(1)
    boundarycs = (bcs.outdoors, bcs.ground, bcs.outdoors, bcs.ground)
    window = (ashrae_base, None, ashrae_base, None)
    shading = (overhang, None, None, None)
    room2d = Room2D.from_vertices('SquareShoebox', pts, 3, 3,
                                  boundarycs, window, shading)

    assert len(room2d.floor_geometry.vertices) == 4
    assert len(room2d) == 4
    assert room2d.floor_to_ceiling_height == 3
    assert isinstance(room2d.boundary_conditions[0], Outdoors)
    assert isinstance(room2d.boundary_conditions[1], Ground)
    assert room2d.window_parameters[0] == ashrae_base
    assert room2d.window_parameters[1] is None
    assert room2d.shading_parameters[0] == overhang
    assert room2d.shading_parameters[1] is None

    assert room2d.floor_height == 3
    assert room2d.ceiling_height == 6
    assert room2d.volume == 300
    assert room2d.floor_area == 100
    assert room2d.exterior_wall_area == 60
    assert room2d.exterior_aperture_area == 60 * 0.4


def test_room2d_segment_orientations():
    """Test the Room2D segment_orientations method."""
    pts = (Point3D(1, 1, 2), Point3D(1, 2, 2), Point3D(2, 2, 2), Point3D(2, 1, 2))
    plane = Plane(Vector3D(0, 0, 1), Point3D(0, 0, 2))
    room2d = Room2D('ZoneCLOSET920980', Face3D(pts, plane), 3)

    assert room2d.segment_normals[0] == Vector2D(1, 0)
    assert room2d.segment_normals[1] == Vector2D(0, 1)
    assert room2d.segment_normals[2] == Vector2D(-1, 0)
    assert room2d.segment_normals[3] == Vector2D(0, -1)

    orientations = room2d.segment_orientations()
    assert orientations[0] == pytest.approx(90, rel=1e-3)
    assert orientations[1] == pytest.approx(0, rel=1e-3)
    assert orientations[2] == pytest.approx(270, rel=1e-3)
    assert orientations[3] == pytest.approx(180, rel=1e-3)


def test_room2d_overlap_area():
    """Test the Room2D overlap_area method."""
    pts_1 = (Point3D(0, 0, 3), Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(0, 10, 3))
    pts_2 = (Point3D(20, 20, 3), Point3D(30, 20, 3), Point3D(30, 30, 3), Point3D(20, 30, 3))
    pts_3 = (Point3D(10, 10, 3), Point3D(20, 10, 3), Point3D(20, 20, 3), Point3D(10, 20, 3))
    pts_4 = (Point3D(5, 5, 3), Point3D(15, 5, 3), Point3D(15, 15, 3), Point3D(5, 15, 3))
    pts_5 = (Point3D(5, 5, 0), Point3D(15, 5, 0), Point3D(15, 15, 0), Point3D(5, 15, 0))
    room_1 = Room2D('SquareShoebox1', Face3D(pts_1), 3)
    room_2 = Room2D('SquareShoebox2', Face3D(pts_2), 3)
    room_3 = Room2D('SquareShoebox3', Face3D(pts_3), 3)
    room_4 = Room2D('SquareShoebox4', Face3D(pts_4), 3)
    room_5 = Room2D('SquareShoebox5', Face3D(pts_5), 3)

    assert room_1.overlap_area(room_2) == 0
    assert room_1.overlap_area(room_3) == 0
    assert room_1.overlap_area(room_4) == pytest.approx(25.0, rel=1e-3)
    assert room_1.overlap_area(room_5) == 0


def test_room2d_set_outdoor_window_shading_parameters():
    """Test the Room2D set_outdoor_window_parameters method."""
    pts = (Point3D(0, 0, 3), Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(0, 10, 3))
    boundarycs = (bcs.outdoors, bcs.ground, bcs.outdoors, bcs.ground)
    room2d = Room2D('SquareShoebox', Face3D(pts), 3, boundarycs)
    ashrae_base = SimpleWindowRatio(0.4)
    overhang = Overhang(1)
    room2d.set_outdoor_window_parameters(ashrae_base)
    room2d.set_outdoor_shading_parameters(overhang)

    assert len(room2d.floor_geometry.vertices) == 4
    assert room2d.floor_geometry.vertices == tuple(pts)
    assert len(room2d) == 4
    assert room2d.floor_to_ceiling_height == 3
    assert isinstance(room2d.boundary_conditions[0], Outdoors)
    assert isinstance(room2d.boundary_conditions[1], Ground)
    assert room2d.window_parameters[0] == ashrae_base
    assert room2d.window_parameters[1] is None
    assert room2d.shading_parameters[0] == overhang
    assert room2d.shading_parameters[1] is None

    assert room2d.floor_height == 3
    assert room2d.ceiling_height == 6
    assert room2d.volume == 300
    assert room2d.floor_area == 100
    assert room2d.exterior_wall_area == 60
    assert room2d.exterior_aperture_area == 60 * 0.4


def test_room2d_check_window_parameters_valid():
    """Test the Room2D check_window_parameters_valid method."""
    pts = (Point3D(0, 0, 3), Point3D(5, 0, 3), Point3D(5, 10, 3), Point3D(0, 10, 3))
    room2d = Room2D('SquareShoebox', Face3D(pts), 3)

    sky_pts = (Point2D(0.5, 5), Point2D(3, 5), Point2D(3, 8), Point2D(0.5, 8))
    sky_par = DetailedSkylights([Polygon2D(sky_pts)])
    room2d.skylight_parameters = sky_par
    assert room2d.check_window_parameters_valid(raise_exception=False) == ''

    sky_pts = (Point2D(0.5, 5), Point2D(3, 5), Point2D(0.5, 8), Point2D(3, 8))
    sky_par = DetailedSkylights([Polygon2D(sky_pts)])
    room2d.skylight_parameters = sky_par
    assert room2d.check_window_parameters_valid(raise_exception=False) != ''

    sky_pts = (Point2D(-2.5, 5), Point2D(2.5, 5), Point2D(2.5, 12), Point2D(-2.5, 12))
    sky_par = DetailedSkylights([Polygon2D(sky_pts)])
    room2d.skylight_parameters = sky_par
    assert room2d.check_window_parameters_valid(raise_exception=False) != ''


def test_room2d_offset_windows():
    """Test the initialization of Room2D objects with windows."""
    pts = (Point3D(0, 0, 3), Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(0, 10, 3))
    ashrae_base = RepeatingWindowRatio(0.4, 2.0, 0.8, 3.0)
    boundarycs = (bcs.outdoors, bcs.ground, bcs.outdoors, bcs.ground)
    window = (ashrae_base, None, ashrae_base, None)
    room2d = Room2D('SquareShoebox', Face3D(pts), 3, boundarycs, window)
    room2d.to_detailed_windows()

    sky_pts = (Point2D(2.5, 2.5), Point2D(7.5, 2.5), Point2D(7.5, 7.5), Point2D(2.5, 7.5))
    sky_par = DetailedSkylights([Polygon2D(sky_pts)])
    room2d.skylight_parameters = sky_par
    room2d.is_top_exposed = True

    assert room2d.exterior_window_area / room2d.exterior_wall_area == \
        pytest.approx(0.4, rel=1e-3)
    room2d.offset_windows(0.2, 0.01)
    assert room2d.exterior_window_area / room2d.exterior_wall_area > 0.4

    assert room2d.skylight_area / room2d.floor_area == \
        pytest.approx(0.25, rel=1e-3)
    room2d.offset_skylights(0.25, 0.01)
    assert room2d.skylight_area / room2d.floor_area > 0.25


def test_room2d_offset_skylights_from_edges():
    """Test the Room2D offset_skylights_from_edges method."""
    pts = (Point3D(0, 0, 3), Point3D(5, 0, 3), Point3D(5, 10, 3), Point3D(0, 10, 3))
    room2d = Room2D('SquareShoebox', Face3D(pts), 3)
    sky_pts = (Point2D(-2.5, 5), Point2D(2.5, 5), Point2D(2.5, 12), Point2D(-2.5, 12))
    sky_par = DetailedSkylights([Polygon2D(sky_pts)])
    room2d.skylight_parameters = sky_par
    assert room2d.check_window_parameters_valid(raise_exception=False) != ''

    room2d.offset_skylights_from_edges(0.05, 0.01)
    assert room2d.check_window_parameters_valid(raise_exception=False) == ''
    for pt in room2d.skylight_parameters[0].vertices:
        if pt.x == pytest.approx(0.05, rel=1e-2) and pt.y == pytest.approx(9.95, rel=1e-2):
            break
    else:
        raise ValueError('offset_skylights_from_edges failed.')


def test_room2d_remove_duplicate_vertices():
    """Test the Room2D remove_duplicate_vertices method."""
    pts = (Point3D(0, 0, 3), Point3D(10, 0, 3), Point3D(10, 0, 3.001),
           Point3D(10, 10, 3), Point3D(0, 10, 3))
    ashrae_base = SimpleWindowRatio(0.4)
    overhang = Overhang(1)
    boundarycs = (bcs.outdoors, bcs.ground, bcs.ground, bcs.outdoors, bcs.ground)
    window = (ashrae_base, None, None, ashrae_base, None)
    shading = (overhang, None, None, None, None)
    room2d = Room2D('SquareShoebox', Face3D(pts), 3, boundarycs, window, shading)

    assert len(room2d.boundary_conditions) == 5
    assert len(room2d.window_parameters) == 5
    assert len(room2d.shading_parameters) == 5

    remove_i = room2d.remove_duplicate_vertices(0.01)

    assert len(room2d.boundary_conditions) == 4
    assert len(room2d.window_parameters) == 4
    assert len(room2d.shading_parameters) == 4
    assert len(remove_i) == 1

    pts = (Point3D(0, 0, 3), Point3D(10, 0, 3),
           Point3D(10, 10, 3), Point3D(0, 10, 3), Point3D(0, 0.0001, 3))
    ashrae_base = SimpleWindowRatio(0.4)
    overhang = Overhang(1)
    boundarycs = (bcs.outdoors, bcs.ground, bcs.outdoors, bcs.ground, bcs.outdoors)
    window = (ashrae_base, None, ashrae_base, None, ashrae_base)
    shading = (overhang, None, None, None, overhang)
    room2d = Room2D('SquareShoebox', Face3D(pts), 3, boundarycs, window, shading)

    assert len(room2d.boundary_conditions) == 5
    assert len(room2d.window_parameters) == 5
    assert len(room2d.shading_parameters) == 5

    remove_i = room2d.remove_duplicate_vertices(0.01)

    assert len(room2d.boundary_conditions) == 4
    assert len(room2d.window_parameters) == 4
    assert len(room2d.shading_parameters) == 4
    assert len(remove_i) == 1


def test_room2d_update_floor_geometry_remove():
    """Test the Room2D update_floor_geometry method while removing segments."""
    pts = (Point3D(0, 0, 3), Point3D(5, 0, 3), Point3D(10, 0, 3),
           Point3D(10, 10, 3), Point3D(0, 10, 3))
    orig_geo = Face3D(pts)
    win_pts = (Point2D(0.5, 0.5), Point2D(4, 0.5), Point2D(4, 2.5), Point2D(0.5, 2.5))
    detailed_window = DetailedWindows((Polygon2D(win_pts),))
    boundarycs = (bcs.outdoors, bcs.outdoors, bcs.ground, bcs.outdoors, bcs.ground)
    window = (detailed_window, detailed_window, None, detailed_window, None)
    room2d = Room2D('SquareShoebox', orig_geo, 3, boundarycs, window)

    new_geo = Face3D(
        (Point3D(0, 0, 3), Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(0, 10, 3)),
        plane=room2d.floor_geometry.plane
    )
    edit_code = 'KXKKK'

    room2d.update_floor_geometry(new_geo, edit_code)
    assert len(room2d.boundary_conditions) == 4
    assert len(room2d.window_parameters) == 4
    assert len(room2d.window_parameters[0]) == 2

    window_alt = (None, detailed_window, None, detailed_window, None)
    room2d = Room2D('SquareShoebox', orig_geo, 3, boundarycs, window_alt)
    room2d.update_floor_geometry(new_geo, edit_code)
    assert len(room2d.boundary_conditions) == 4
    assert len(room2d.window_parameters) == 4
    assert len(room2d.window_parameters[0]) == 1


def test_room2d_update_floor_geometry_add():
    """Test the Room2D update_floor_geometry method while adding segments."""
    pts = (Point3D(0, 0, 3), Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(0, 10, 3))

    orig_geo = Face3D(pts)
    win_pts = (Point2D(0.5, 0.5), Point2D(9.5, 0.5), Point2D(9.5, 2.5), Point2D(0.5, 2.5))
    detailed_window = DetailedWindows((Polygon2D(win_pts),))
    boundarycs = (bcs.outdoors, bcs.ground, bcs.outdoors, bcs.ground)
    window = (detailed_window, None, detailed_window, None)
    room2d = Room2D('SquareShoebox', orig_geo, 3, boundarycs, window)

    new_geo = Face3D(
        (Point3D(0, 0, 3), Point3D(5, 0, 3), Point3D(10, 0, 3),
         Point3D(10, 10, 3), Point3D(0, 10, 3)),
        plane=room2d.floor_geometry.plane
    )
    edit_code = 'KAKKK'

    room2d.update_floor_geometry(new_geo, edit_code)
    assert len(room2d.boundary_conditions) == 5
    assert len(room2d.window_parameters) == 5
    assert len(room2d.window_parameters[0]) == 1
    assert len(room2d.window_parameters[1]) == 1

    room2d = Room2D('SquareShoebox', orig_geo, 3, boundarycs, window)
    new_geo = Face3D(
        (Point3D(0, 0, 3), Point3D(3, 0, 3), Point3D(6, 0, 3), Point3D(10, 0, 3),
         Point3D(10, 10, 3), Point3D(0, 10, 3)),
        plane=room2d.floor_geometry.plane
    )
    edit_code = 'KAAKKK'
    room2d.update_floor_geometry(new_geo, edit_code)
    assert len(room2d.boundary_conditions) == 6
    assert len(room2d.window_parameters) == 6
    assert len(room2d.window_parameters[0]) == 1
    assert len(room2d.window_parameters[1]) == 1
    assert len(room2d.window_parameters[2]) == 1


def test_room2d_update_floor_geometry_holes():
    """Test the Room2D update_floor_geometry method while adding segments."""
    bpts = (Point3D(0, 0, 3), Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(0, 10, 3))
    hpts = (Point3D(4, 4, 3), Point3D(6, 4, 3), Point3D(6, 6, 3), Point3D(4, 6, 3))
    orig_geo = Face3D(bpts, holes=[hpts])
    win_pts = (Point2D(0.5, 0.5), Point2D(1.5, 0.5), Point2D(1.5, 2.5), Point2D(0.5, 2.5))
    detailed_window = DetailedWindows((Polygon2D(win_pts),))
    boundarycs = (bcs.outdoors, bcs.ground, bcs.outdoors, bcs.ground,
                  bcs.outdoors, bcs.outdoors, bcs.outdoors, bcs.outdoors)
    window = (detailed_window, None, detailed_window, None,
              detailed_window, detailed_window, detailed_window, detailed_window)
    room2d = Room2D('DonutShoebox', orig_geo, 3, boundarycs, window)

    new_geo = Face3D(
        (Point3D(0, 0, 3), Point3D(5, 0, 3), Point3D(10, 0, 3),
         Point3D(10, 10, 3), Point3D(0, 10, 3)),
        holes=((Point3D(4, 4, 3), Point3D(5, 4, 3), Point3D(6, 4, 3),
                Point3D(6, 6, 3), Point3D(4, 6, 3)),),
        plane=room2d.floor_geometry.plane
    )
    edit_code = 'KAKKKKAKKK'

    room2d.update_floor_geometry(new_geo, edit_code)
    assert len(room2d.boundary_conditions) == 10
    assert len(room2d.window_parameters) == 10
    assert len(room2d.window_parameters[5]) == 1
    assert len(room2d.window_parameters[6]) == 1


def test_generate_grid():
    """Test the generate_grid method."""
    pts = (Point3D(0, 0, 3), Point3D(5, 0, 3), Point3D(5, 10, 3), Point3D(0, 10, 3))
    room = Room2D('SquareShoebox', Face3D(pts), 3)
    mesh_grid = room.generate_grid(1)
    assert len(mesh_grid.faces) == 50
    mesh_grid = room.generate_grid(0.5)
    assert len(mesh_grid.faces) == 200


def test_room2d_set_boundary_condition():
    """Test the Room2D set_boundary_condition method."""
    pts = (Point3D(0, 0, 3), Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(0, 10, 3))
    room2d = Room2D('SquareShoebox', Face3D(pts), 3)
    room2d.set_boundary_condition(1, bcs.ground)
    assert isinstance(room2d.boundary_conditions[1], Ground)

    room2d.set_outdoor_window_parameters(SimpleWindowRatio(0.4))
    assert room2d.window_parameters[1] is None
    with pytest.raises(AssertionError):
        room2d.set_boundary_condition(3, bcs.ground)


def test_move():
    """Test the Room2D move method."""
    pts_1 = (Point3D(0, 2, 0), Point3D(2, 2, 0), Point3D(2, 0, 0), Point3D(0, 0, 0))
    plane_1 = Plane(Vector3D(0, 0, 1), Point3D(0, 0, 0))
    room = Room2D('SquareShoebox', Face3D(pts_1, plane_1), 3)

    vec_1 = Vector3D(2, 2, 2)
    new_r = room.duplicate()
    new_r.move(vec_1)
    assert new_r.floor_geometry[0] == Point3D(2, 2, 2)
    assert new_r.floor_geometry[1] == Point3D(4, 2, 2)
    assert new_r.floor_geometry[2] == Point3D(4, 4, 2)
    assert new_r.floor_geometry[3] == Point3D(2, 4, 2)
    assert room.floor_area == new_r.floor_area
    assert room.volume == new_r.volume


def test_scale():
    """Test the Room2D scale method."""
    pts = (Point3D(1, 1, 2), Point3D(2, 1, 2), Point3D(2, 2, 2), Point3D(1, 2, 2))
    plane_1 = Plane(Vector3D(0, 0, 1), Point3D(0, 0, 0))
    room = Room2D('SquareShoebox', Face3D(pts, plane_1), 3)
    room.set_outdoor_window_parameters(SingleWindow(1, 1, 1))
    room.set_outdoor_shading_parameters(Overhang(1))

    new_r = room.duplicate()
    new_r.scale(2)
    assert new_r.floor_geometry[0] == Point3D(2, 2, 4)
    assert new_r.floor_geometry[1] == Point3D(4, 2, 4)
    assert new_r.floor_geometry[2] == Point3D(4, 4, 4)
    assert new_r.floor_geometry[3] == Point3D(2, 4, 4)
    assert new_r.floor_area == room.floor_area * 2 ** 2
    assert new_r.volume == room.volume * 2 ** 3
    assert new_r.window_parameters[0].width == 2
    assert new_r.window_parameters[0].height == 2
    assert new_r.window_parameters[0].sill_height == 2
    assert new_r.shading_parameters[0].depth == 2


def test_rotate_xy():
    """Test the Room2D rotate_xy method."""
    pts = (Point3D(1, 1, 2), Point3D(2, 1, 2), Point3D(2, 2, 2), Point3D(1, 2, 2))
    plane = Plane(Vector3D(0, 0, 1), Point3D(0, 0, 2))
    room = Room2D('SquareShoebox', Face3D(pts, plane), 3)
    origin_1 = Point3D(1, 1, 0)

    test_1 = room.duplicate()
    test_1.rotate_xy(180, origin_1)
    assert test_1.floor_geometry[0].x == pytest.approx(1, rel=1e-3)
    assert test_1.floor_geometry[0].y == pytest.approx(1, rel=1e-3)
    assert test_1.floor_geometry[0].z == pytest.approx(2, rel=1e-3)
    assert test_1.floor_geometry[2].x == pytest.approx(0, rel=1e-3)
    assert test_1.floor_geometry[2].y == pytest.approx(0, rel=1e-3)
    assert test_1.floor_geometry[2].z == pytest.approx(2, rel=1e-3)

    test_2 = room.duplicate()
    test_2.rotate_xy(90, origin_1)
    assert test_2.floor_geometry[0].x == pytest.approx(1, rel=1e-3)
    assert test_2.floor_geometry[0].y == pytest.approx(1, rel=1e-3)
    assert test_2.floor_geometry[0].z == pytest.approx(2, rel=1e-3)
    assert test_2.floor_geometry[2].x == pytest.approx(0, rel=1e-3)
    assert test_2.floor_geometry[2].y == pytest.approx(2, rel=1e-3)
    assert test_2.floor_geometry[2].z == pytest.approx(2, rel=1e-3)


def test_reflect():
    """Test the Room2D reflect method."""
    pts = (Point3D(1, 1, 2), Point3D(2, 1, 2), Point3D(2, 2, 2), Point3D(1, 2, 2))
    plane = Plane(Vector3D(0, 0, 1), Point3D(0, 0, 2))
    room = Room2D('SquareShoebox', Face3D(pts, plane), 3)

    origin_1 = Point3D(1, 0, 2)
    origin_2 = Point3D(0, 0, 2)
    normal_1 = Vector3D(1, 0, 0)
    normal_2 = Vector3D(-1, -1, 0).normalize()
    plane_1 = Plane(normal_1, origin_1)
    plane_2 = Plane(normal_2, origin_2)
    plane_3 = Plane(normal_2, origin_1)

    test_1 = room.duplicate()
    test_1.reflect(plane_1)
    assert test_1.floor_geometry[-1].x == pytest.approx(1, rel=1e-3)
    assert test_1.floor_geometry[-1].y == pytest.approx(1, rel=1e-3)
    assert test_1.floor_geometry[-1].z == pytest.approx(2, rel=1e-3)
    assert test_1.floor_geometry[1].x == pytest.approx(0, rel=1e-3)
    assert test_1.floor_geometry[1].y == pytest.approx(2, rel=1e-3)
    assert test_1.floor_geometry[1].z == pytest.approx(2, rel=1e-3)

    test_1 = room.duplicate()
    test_1.reflect(plane_2)
    assert test_1.floor_geometry[-1].x == pytest.approx(-1, rel=1e-3)
    assert test_1.floor_geometry[-1].y == pytest.approx(-1, rel=1e-3)
    assert test_1.floor_geometry[-1].z == pytest.approx(2, rel=1e-3)
    assert test_1.floor_geometry[1].x == pytest.approx(-2, rel=1e-3)
    assert test_1.floor_geometry[1].y == pytest.approx(-2, rel=1e-3)
    assert test_1.floor_geometry[1].z == pytest.approx(2, rel=1e-3)

    test_2 = room.duplicate()
    test_2.reflect(plane_3)
    assert test_2.floor_geometry[-1].x == pytest.approx(0, rel=1e-3)
    assert test_2.floor_geometry[-1].y == pytest.approx(0, rel=1e-3)
    assert test_2.floor_geometry[-1].z == pytest.approx(2, rel=1e-3)
    assert test_2.floor_geometry[1].x == pytest.approx(-1, rel=1e-3)
    assert test_2.floor_geometry[1].y == pytest.approx(-1, rel=1e-3)
    assert test_2.floor_geometry[1].z == pytest.approx(2, rel=1e-3)


def test_room2d_remove_colinear_vertices():
    """Test the Room2D remove_colinear_vertices method."""
    pts = (Point3D(0, 0, 3), Point3D(5, 0, 3), Point3D(10, 0, 3), Point3D(10, 10, 3),
           Point3D(0, 10, 3))
    room2d = Room2D('SquareShoebox', Face3D(pts), 3)

    assert len(room2d) == 5
    new_room = room2d.remove_colinear_vertices(0.01)
    assert len(new_room) == 4
    assert len(new_room.boundary_conditions) == 4
    assert len(new_room.window_parameters) == 4
    assert len(new_room.shading_parameters) == 4


def test_room2d_remove_short_segments():
    """Test the Room2D remove_short_segments method."""
    test_json = './tests/json/short_seg_room2ds.json'
    with open(test_json) as json_file:
        data = json.load(json_file)
    room1, room2, room3, room4, room5, room6 = [Room2D.from_dict(rd) for rd in data]

    new_room1 = room1.remove_short_segments(7)
    assert len(room1) == 6
    assert len(new_room1) == 4

    new_room2 = room2.remove_short_segments(7)
    assert len(room2) == 6
    assert len(new_room2) == 4

    new_room3 = room3.remove_short_segments(7)
    assert len(room3) == 10
    assert len(new_room3) == 6

    new_room4 = room4.remove_short_segments(7)
    assert len(room4) == 9
    assert len(new_room4) == 5

    new_room5 = room5.remove_short_segments(0.1)
    assert len(room5) == 15
    assert len(new_room5) == 15

    new_room6 = room6.remove_short_segments(0.2)
    assert len(room6) == 10
    assert len(new_room6) == 8


def test_snap_to_points():
    """Test the snap_to_points method."""
    pts_1 = (Point3D(0, 0, 3), Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(0, 10, 3))
    snap_points = (Point2D(10.5, 0), Point2D(10.5, 10.5))
    room1 = Room2D('SquareShoebox1', Face3D(list(reversed(pts_1))), 3)
    distance = 1.0

    room2 = room1.duplicate()
    room2.snap_to_points(snap_points, distance)
    assert room2.floor_area > room1.floor_area
    assert room2.floor_geometry[1].x == pytest.approx(10.5, abs=1e-3)
    assert room2.floor_geometry[1].y == pytest.approx(0, abs=1e-3)
    assert room2.floor_geometry[2].x == pytest.approx(10.5, abs=1e-3)
    assert room2.floor_geometry[2].y == pytest.approx(10.5, abs=1e-3)


def test_room2d_align():
    """Test the Room2D align method."""
    # set up the inputs
    align_distance = 0.6  # distance in model units where vertices will be aligned
    model_file = './tests/json/Level03.dfjson'
    line_file = './tests/json/line_rays.json'

    # load the line geometries, Dragonfly Room2Ds, and get the model tolerance
    with open(line_file) as json_file:
        line_data = json.load(json_file)
    input_lines = [LineSegment2D.from_dict(ld) for ld in line_data]
    model = Model.from_dfjson(model_file)
    tolerance = model.tolerance
    rooms = model.room_2ds

    # loop through the rooms and align them to each line
    updated_rooms, removed_rooms = [], []
    for room in rooms:
        # perform the alignment operation
        for line in input_lines:
            room.align(line, align_distance)
        # remove duplicate vertices from the result
        try:  # catch all degeneracy in the process
            room.remove_duplicate_vertices(tolerance)
            max_dim = max((room.max.x - room.min.x, room.max.y - room.min.y))
            if room.floor_geometry.area < max_dim * tolerance:
                removed_rooms.append(room)
            else:
                room.remove_degenerate_holes(tolerance)
                updated_rooms.append(room)
        except ValueError:  # degenerate room found!
            removed_rooms.append(room)

    # write out the updated rooms as a new Model
    new_model_file = './tests/json/Level03_Updated.dfjson'
    new_story = Story('New_Story', updated_rooms)
    new_building = Building('New_Building', [new_story])
    new_model = Model('New_Model', [new_building])
    new_model.to_dfjson(os.path.split(new_model_file)[1], os.path.split(new_model_file)[0])
    os.remove(new_model_file)


def test_coordinate_room_2d_vertices():
    """Test the coordinate_room_2d_vertices method."""
    pts_1 = (Point3D(0, 0, 3), Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(0, 10, 3))
    pts_2 = (Point3D(10.5, 0, 3), Point3D(20, 0, 3), Point3D(20, 10, 3),
             Point3D(10.5, 10, 3), Point3D(10, 5, 3))
    room1 = Room2D('SquareShoebox1', Face3D(list(reversed(pts_1))), 3)
    room2 = Room2D('SquareShoebox2', Face3D(list(reversed(pts_2))), 3)

    distance = 0.6
    new_room = room1.duplicate()
    new_room.pull_to_room_2d(room2, distance, True)
    new_room.coordinate_room_2d_vertices(room2, distance, 0.01)
    assert len(new_room.floor_geometry.vertices) == 5
    assert room1.floor_area == pytest.approx(100, abs=1e-3)
    assert new_room.floor_area == pytest.approx(102.5, abs=1e-3)

    pts_3 = (Point3D(10.5, 0, 3), Point3D(20, 0, 3), Point3D(20, 10, 3),
             Point3D(10.5, 10, 3), Point3D(10, 5, 3), Point3D(10, 2, 3))
    room1 = Room2D('SquareShoebox1', Face3D(pts_1), 3)
    room3 = Room2D('SquareShoebox3', Face3D(pts_3), 3)
    new_room = room1.duplicate()
    new_room.pull_to_room_2d(room3, distance, True)
    new_room.coordinate_room_2d_vertices(room3, distance, 0.01)
    assert len(new_room.floor_geometry.vertices) == 6
    assert new_room.floor_area == pytest.approx(101.75, abs=1e-3)


def test_pull_to_room_2d():
    """Test the pull_to_room_2d method."""
    pts_1 = (Point3D(0, 0, 3), Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(0, 10, 3))
    pts_2 = (Point3D(10.5, -0.5, 3), Point3D(20, 0, 3), Point3D(20, 9.5, 3),
             Point3D(10.5, 9.5, 3))
    room1 = Room2D('SquareShoebox1', Face3D(list(reversed(pts_1))), 3)
    room2 = Room2D('SquareShoebox2', Face3D(list(reversed(pts_2))), 3)

    distance = 0.8
    new_room = room1.duplicate()
    new_room.pull_to_room_2d(room2, distance, True, False, 0.01)
    assert new_room.floor_geometry[1].x == pytest.approx(10.5, abs=1e-3)
    assert new_room.floor_geometry[1].y == pytest.approx(-0.5, abs=1e-3)
    assert new_room.floor_geometry[2].x == pytest.approx(10.5, abs=1e-3)
    assert new_room.floor_geometry[2].y == pytest.approx(9.5, abs=1e-3)

    new_room = room1.duplicate()
    new_room.pull_to_room_2d(room2, distance, True, True, 0.01)
    assert new_room.floor_geometry[1].x == pytest.approx(10.5, abs=1e-3)
    assert new_room.floor_geometry[1].y == pytest.approx(0.0, abs=1e-3)
    assert new_room.floor_geometry[2].x == pytest.approx(10.5, abs=1e-3)
    assert new_room.floor_geometry[2].y == pytest.approx(10.0, abs=1e-3)

    new_room = room1.duplicate()
    new_room.pull_to_segments(room2.floor_segments_2d, distance, True, False, 0.01)
    assert new_room.floor_geometry[1].x == pytest.approx(10.5, abs=1e-3)
    assert new_room.floor_geometry[1].y == pytest.approx(-0.5, abs=1e-3)
    assert new_room.floor_geometry[2].x == pytest.approx(10.5, abs=1e-3)
    assert new_room.floor_geometry[2].y == pytest.approx(9.5, abs=1e-3)

    new_room = room1.duplicate()
    new_room.pull_to_segments(room2.floor_segments_2d, distance, True, True, 0.01)
    assert new_room.floor_geometry[1].x == pytest.approx(10.5, abs=1e-3)
    assert new_room.floor_geometry[1].y == pytest.approx(0.0, abs=1e-3)
    assert new_room.floor_geometry[2].x == pytest.approx(10.5, abs=1e-3)
    assert new_room.floor_geometry[2].y == pytest.approx(10.0, abs=1e-3)


def test_subtract_room_2ds():
    """Test the Room2D subtract_room_2ds method."""
    f_pts = (Point3D(0, 0, 2), Point3D(2, 0, 2), Point3D(2, 2, 2), Point3D(0, 2, 2))
    room2d = Room2D('SquareShoebox1', Face3D(f_pts), 3)
    ashrae_base = SimpleWindowRatio(0.4)
    room2d.window_parameters = [ashrae_base] * 4
    room2d.to_rectangular_windows()

    sub_pts = (Point3D(1, -1, 2), Point3D(1, 1, 2), Point3D(3, 1, 2), Point3D(3, -1, 2))
    sub_room2d = Room2D('SquareShoebox2', Face3D(sub_pts), 3)
    new_room = room2d.subtract_room_2ds([sub_room2d], 0.01)
    assert len(new_room) == 1
    assert len(new_room[0].floor_geometry) == 6
    assert new_room[0].floor_area == pytest.approx(room2d.floor_area * 0.75, rel=1e-2)
    assert new_room[0].exterior_aperture_area == \
        pytest.approx(room2d.exterior_aperture_area * 0.75, rel=1e-2)

    sub_pts = (Point3D(0.5, 0.5, 1), Point3D(1.5, 0.5, 1), Point3D(1.5, 1.5, 1),
               Point3D(0.5, 1.5, 1))
    sub_room2d = Room2D('SquareShoebox2', Face3D(sub_pts), 3)
    new_room = room2d.subtract_room_2ds([sub_room2d], 0.01)
    assert len(new_room) == 1
    assert len(new_room[0].floor_geometry) == 10
    assert new_room[0].floor_area == pytest.approx(room2d.floor_area * 0.75, rel=1e-2)
    assert new_room[0].exterior_aperture_area == \
        pytest.approx(room2d.exterior_aperture_area, rel=1e-2)


def test_split_with_line():
    """Test the Room2D split_with_line method."""
    f_pts = (Point3D(0, 0, 2), Point3D(2, 0, 2), Point3D(2, 2, 2), Point3D(0, 2, 2))
    room2d = Room2D('SquareShoebox1', Face3D(f_pts), 3)
    ashrae_base = SimpleWindowRatio(0.4)
    room2d.window_parameters = [ashrae_base] * 4
    room2d.to_detailed_windows()

    l_pts = (Point2D(1, -1), Point2D(1, 3))
    line = LineSegment2D.from_end_points(*l_pts)
    int_result = room2d.split_with_line(line, 0.01)
    assert len(int_result) == 2
    assert len(int_result[0].floor_geometry) == 4
    assert len(int_result[1].floor_geometry) == 4
    assert int_result[0].floor_area == pytest.approx(room2d.floor_area / 2, rel=1e-2)
    assert int_result[1].floor_area == pytest.approx(room2d.floor_area / 2, rel=1e-2)
    assert sum(r.exterior_aperture_area for r in int_result) == \
        pytest.approx(room2d.exterior_aperture_area, rel=1e-2)
    assert int_result[0].exterior_aperture_area == \
        pytest.approx(room2d.exterior_aperture_area / 2, rel=1e-2)

    l_pts = (Point2D(1, 0), Point2D(1, 2))
    line = LineSegment2D.from_end_points(*l_pts)
    int_result = room2d.split_with_line(line, 0.01)
    assert len(int_result) == 2
    assert len(int_result[0].floor_geometry) == 4
    assert len(int_result[1].floor_geometry) == 4
    assert int_result[0].floor_area == pytest.approx(room2d.floor_area / 2, rel=1e-2)
    assert int_result[1].floor_area == pytest.approx(room2d.floor_area / 2, rel=1e-2)
    assert sum(r.exterior_aperture_area for r in int_result) == \
        pytest.approx(room2d.exterior_aperture_area, rel=1e-2)
    assert int_result[0].exterior_aperture_area == \
        pytest.approx(room2d.exterior_aperture_area / 2, rel=1e-2)

    l_pts = (Point2D(1, 0), Point2D(1, 1))
    line = LineSegment2D.from_end_points(*l_pts)
    int_result = room2d.split_with_line(line, 0.01)
    assert len(int_result) == 1
    assert int_result[0] is room2d

    l_pts = (Point2D(-1, -1), Point2D(3, 3))
    line = LineSegment2D.from_end_points(*l_pts)
    int_result = room2d.split_with_line(line, 0.01)
    assert len(int_result) == 2
    assert len(int_result[0].floor_geometry) == 3
    assert len(int_result[1].floor_geometry) == 3
    assert int_result[0].floor_area == pytest.approx(room2d.floor_area / 2, rel=1e-2)
    assert int_result[1].floor_area == pytest.approx(room2d.floor_area / 2, rel=1e-2)
    assert sum(r.exterior_aperture_area for r in int_result) == \
        pytest.approx(room2d.exterior_aperture_area, rel=1e-2)
    assert int_result[0].exterior_aperture_area == \
        pytest.approx(room2d.exterior_aperture_area / 2, rel=1e-2)


def test_split_with_line_extreme_coordinate():
    """Test the Room2D split_with_line method with extreme coordinate values."""
    f_pts = (Point3D(0, 0, 2), Point3D(2, 0, 2), Point3D(2, 2, 2), Point3D(0, 2, 2))
    room2d = Room2D('SquareShoebox1', Face3D(f_pts), 3)
    ashrae_base = SimpleWindowRatio(0.4)
    room2d.window_parameters = [ashrae_base] * 4
    room2d.to_detailed_windows()

    l_pts = (Point2D(1, -99999), Point2D(1, 99999))
    line = LineSegment2D.from_end_points(*l_pts)
    int_result = room2d.split_with_line(line, 0.01)
    assert len(int_result) == 2


def test_split_with_polyline():
    """Test the Room2D split_with_polyline method."""
    f_pts = (Point3D(0, 0, 2), Point3D(2, 0, 2), Point3D(2, 2, 2), Point3D(0, 2, 2))
    room2d = Room2D('SquareShoebox1', Face3D(f_pts), 3)
    ashrae_base = SimpleWindowRatio(0.4)
    room2d.window_parameters = [ashrae_base] * 4
    room2d.to_detailed_windows()

    pl_pts = (Point2D(1, -1), Point2D(1, 1), Point2D(3, 1))
    line = Polyline2D(pl_pts)
    int_result = room2d.split_with_polyline(line, 0.01)
    assert len(int_result) == 2
    assert len(int_result[0].floor_geometry) == 6
    assert len(int_result[1].floor_geometry) == 4
    assert int_result[0].floor_area == pytest.approx(room2d.floor_area * 0.75, rel=1e-2)
    assert int_result[1].floor_area == pytest.approx(room2d.floor_area * 0.25, rel=1e-2)
    assert sum(r.exterior_aperture_area for r in int_result) == \
        pytest.approx(room2d.exterior_aperture_area, rel=1e-2)

    pl_pts = (Point2D(1, -1), Point2D(1, 1), Point2D(1.5, 1))
    line = Polyline2D(pl_pts)
    int_result = room2d.split_with_polyline(line, 0.01)
    assert len(int_result) == 1
    assert int_result[0] is room2d


def test_split_with_polygon():
    """Test the Room2D split_with_line method."""
    f_pts = (Point3D(0, 0, 2), Point3D(2, 0, 2), Point3D(2, 2, 2), Point3D(0, 2, 2))
    room2d = Room2D('SquareShoebox1', Face3D(f_pts), 3)
    ashrae_base = SimpleWindowRatio(0.4)
    room2d.window_parameters = [ashrae_base] * 4
    room2d.to_rectangular_windows()

    poly_pts = (Point2D(1, -1), Point2D(1, 1), Point2D(3, 1), Point2D(3, -1))
    polygon = Polygon2D(poly_pts)
    int_result = room2d.split_with_polygon(polygon, 0.01)
    assert len(int_result) == 2
    assert len(int_result[0].floor_geometry) == 6
    assert len(int_result[1].floor_geometry) == 4
    assert int_result[0].floor_area == pytest.approx(room2d.floor_area * 0.75, rel=1e-2)
    assert int_result[1].floor_area == pytest.approx(room2d.floor_area * 0.25, rel=1e-2)
    assert sum(r.exterior_aperture_area for r in int_result) == \
        pytest.approx(room2d.exterior_aperture_area, rel=1e-2)

    poly_pts = (Point2D(0.5, 0.5), Point2D(1.5, 0.5), Point2D(1.5, 1.5), Point2D(0.5, 1.5))
    polygon = Polygon2D(poly_pts)
    int_result = room2d.split_with_polygon(polygon, 0.01)
    assert len(int_result) == 2
    assert len(int_result[0].floor_geometry) == 10
    assert len(int_result[1].floor_geometry) == 4
    assert int_result[0].floor_area == pytest.approx(room2d.floor_area * 0.75, rel=1e-2)
    assert int_result[1].floor_area == pytest.approx(room2d.floor_area * 0.25, rel=1e-2)
    assert sum(r.exterior_aperture_area for r in int_result) == \
        pytest.approx(room2d.exterior_aperture_area, rel=1e-2)


def test_split_with_thick_line():
    """Test the Room2D split_with_line method."""
    f_pts = (Point3D(0, 0, 2), Point3D(4, 0, 2), Point3D(4, 4, 2), Point3D(0, 4, 2))
    h_pts = (Point3D(1, 1, 2), Point3D(3, 1, 2), Point3D(3, 3, 2), Point3D(1, 3, 2))
    face = Face3D(f_pts, holes=[h_pts])
    room2d = Room2D('DonutShoebox1', face, 3)
    ashrae_base = SimpleWindowRatio(0.4)
    room2d.window_parameters = [ashrae_base] * 8
    room2d.to_detailed_windows()

    l_pts = (Point2D(-1, 2), Point2D(2, 2))
    line = LineSegment2D.from_end_points(*l_pts)
    int_result = room2d.split_with_thick_line(line, 0.2, 0.01)
    assert len(int_result) == 1
    assert len(int_result[0].floor_geometry.vertices) == 12

    l_pts = (Point2D(-1, 2), Point2D(5, 2))
    line = LineSegment2D.from_end_points(*l_pts)
    int_result = room2d.split_with_thick_line(line, 0.2, 0.01)
    assert len(int_result) == 2
    assert len(int_result[0].floor_geometry.vertices) == 8


def test_split_with_thick_polyline():
    """Test the Room2D split_with_thick_polyline method."""
    f_pts = (Point3D(0, 0, 2), Point3D(4, 0, 2), Point3D(4, 4, 2), Point3D(0, 4, 2))
    h_pts = (Point3D(1, 1, 2), Point3D(3, 1, 2), Point3D(3, 3, 2), Point3D(1, 3, 2))
    face = Face3D(f_pts, holes=[h_pts])
    room2d = Room2D('DonutShoebox1', face, 3)
    ashrae_base = SimpleWindowRatio(0.4)
    room2d.window_parameters = [ashrae_base] * 8
    room2d.to_detailed_windows()

    l_pts = (Point2D(-1, 2), Point2D(2, 2), Point2D(2, 2.5))
    line = Polyline2D(l_pts)
    int_result = room2d.split_with_thick_polyline(line, 0.2, 0.01)
    assert len(int_result) == 1
    assert len(int_result[0].floor_geometry.vertices) == 12

    l_pts = (Point2D(-1, 2), Point2D(2, 2), Point2D(2, 5))
    line = Polyline2D(l_pts)
    int_result = room2d.split_with_thick_polyline(line, 0.2, 0.01)
    assert len(int_result) == 2
    assert len(int_result[0].floor_geometry.vertices) == 10 or \
        len(int_result[0].floor_geometry.vertices) == 6
    assert len(int_result[1].floor_geometry.vertices) == 10 or \
        len(int_result[1].floor_geometry.vertices) == 6


def test_room2d_solve_adjacency():
    """Test the Room2D solve_adjacency method."""
    pts_1 = (Point3D(0, 0, 3), Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(0, 10, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(20, 0, 3),
             Point3D(20, 10, 3), Point3D(10, 10, 3))
    room2d_1 = Room2D('SquareShoebox1', Face3D(pts_1), 3)
    room2d_2 = Room2D('SquareShoebox2', Face3D(pts_2), 3)
    Room2D.solve_adjacency([room2d_1, room2d_2], 0.01)

    assert isinstance(room2d_1.boundary_conditions[1], Surface)
    assert isinstance(room2d_2.boundary_conditions[3], Surface)
    assert room2d_1.boundary_conditions[1].boundary_condition_object == \
        '{}..Face4'.format(room2d_2.identifier)
    assert room2d_2.boundary_conditions[3].boundary_condition_object == \
        '{}..Face2'.format(room2d_1.identifier)


def test_solve_adjacency_aperture():
    """Test the Room2D solve_adjacency method with an interior aperture."""
    pts_1 = (Point3D(0, 0, 3), Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(0, 10, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(20, 0, 3),
             Point3D(20, 10, 3), Point3D(10, 10, 3))
    ashrae_base = SimpleWindowRatio(0.4)
    window_1 = (None, ashrae_base, None, None)
    window_2 = (None, None, None, ashrae_base)
    window_3 = (None, None, None, None)
    room2d_1 = Room2D('SquareShoebox1', Face3D(pts_1), 3, None, window_1)
    room2d_2 = Room2D('SquareShoebox2', Face3D(pts_2), 3, None, window_2)
    room2d_3 = Room2D('SquareShoebox3', Face3D(pts_2), 3, None, window_3)
    Room2D.solve_adjacency([room2d_1, room2d_2], 0.01)

    assert room2d_1.boundary_conditions[1].boundary_condition_object == \
        '{}..Face4'.format(room2d_2.identifier)
    assert room2d_2.boundary_conditions[3].boundary_condition_object == \
        '{}..Face2'.format(room2d_1.identifier)

    with pytest.raises(AssertionError):
        Room2D.solve_adjacency([room2d_1, room2d_3], 0.01, False)


def test_solve_adjacency_air_boundary():
    """Test the Room2D solve_adjacency method with an air boundary."""
    pts_1 = (Point3D(0, 0, 3), Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(0, 10, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(20, 0, 3),
             Point3D(20, 10, 3), Point3D(10, 10, 3))
    room2d_1 = Room2D('SquareShoebox1', Face3D(pts_1), 3)
    room2d_2 = Room2D('SquareShoebox2', Face3D(pts_2), 3)
    adj_info = Room2D.solve_adjacency([room2d_1, room2d_2], 0.01)
    for room_pair in adj_info:
        for room_adj in room_pair:
            room, wall_i = room_adj
            air_bnd = list(room.air_boundaries)
            air_bnd[wall_i] = True
            room.air_boundaries = air_bnd

    assert isinstance(room2d_1.boundary_conditions[1], Surface)
    assert isinstance(room2d_2.boundary_conditions[3], Surface)
    assert room2d_1.air_boundaries[1]
    assert room2d_2.air_boundaries[3]
    hb_room_1, hb_room_2 = room2d_1.to_honeybee()[0], room2d_2.to_honeybee()[0]
    assert isinstance(hb_room_1[2].type, AirBoundary)
    assert isinstance(hb_room_2[4].type, AirBoundary)


def test_room2d_intersect_adjacency():
    """Test the Room2D intersect_adjacency method."""
    pts_1 = (Point3D(0, 0, 3), Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(0, 10, 3))
    pts_2 = (Point3D(10, 5, 2), Point3D(20, 5, 2),
             Point3D(20, 15, 2), Point3D(10, 15, 2))
    room2d_1 = Room2D('SquareShoebox1', Face3D(pts_1), 3)
    room2d_2 = Room2D('SquareShoebox2', Face3D(pts_2), 3)
    room2d_1, room2d_2 = Room2D.intersect_adjacency([room2d_1, room2d_2], 0.01)

    assert len(room2d_1) == 5
    assert len(room2d_2) == 5

    Room2D.solve_adjacency([room2d_1, room2d_2], 0.01)

    assert isinstance(room2d_1.boundary_conditions[2], Surface)
    assert isinstance(room2d_2.boundary_conditions[4], Surface)
    assert room2d_1.boundary_conditions[2].boundary_condition_object == \
        '{}..Face5'.format(room2d_2.identifier)
    assert room2d_2.boundary_conditions[4].boundary_condition_object == \
        '{}..Face3'.format(room2d_1.identifier)


def test_group_by_adjacency():
    """Test the Room2D group_by_adjacency method."""
    pts_1 = (Point3D(0, 0, 3), Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(0, 10, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(20, 0, 3),
             Point3D(20, 10, 3), Point3D(10, 10, 3))
    pts_3 = (Point3D(10, 20, 3), Point3D(20, 20, 3),
             Point3D(20, 30, 3), Point3D(10, 30, 3))
    room2d_1 = Room2D('SquareShoebox1', Face3D(pts_1), 3)
    room2d_2 = Room2D('SquareShoebox2', Face3D(pts_2), 3)
    room2d_3 = Room2D('SquareShoebox3', Face3D(pts_3), 3)
    Room2D.solve_adjacency([room2d_1, room2d_2], 0.01)

    all_rooms = [room2d_1, room2d_2, room2d_3]

    grouped_rooms = Room2D.group_by_adjacency(all_rooms)

    assert len(grouped_rooms) == 2
    assert len(grouped_rooms[0]) == 2
    assert len(grouped_rooms[1]) == 1


def test_group_by_air_boundary_adjacency():
    """Test the Room2D group_by_air_boundary_adjacency method."""
    pts_1 = (Point3D(0, 0, 3), Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(0, 10, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(20, 0, 3),
             Point3D(20, 10, 3), Point3D(10, 10, 3))
    pts_3 = (Point3D(10, 10, 3), Point3D(20, 10, 3),
             Point3D(20, 20, 3), Point3D(10, 20, 3))
    room2d_1 = Room2D('SquareShoebox1', Face3D(pts_1), 3)
    room2d_2 = Room2D('SquareShoebox2', Face3D(pts_2), 3)
    room2d_3 = Room2D('SquareShoebox3', Face3D(pts_3), 3)
    adj_info = Room2D.solve_adjacency([room2d_1, room2d_2], 0.01)

    for room_pair in adj_info:
        for room_adj in room_pair:
            room, wall_i = room_adj
            air_bnd = list(room.air_boundaries)
            air_bnd[wall_i] = True
            room.air_boundaries = air_bnd

    all_rooms = [room2d_1, room2d_2, room2d_3]
    Room2D.solve_adjacency(all_rooms, 0.01)

    grouped_rooms = Room2D.group_by_air_boundary_adjacency(all_rooms)

    assert len(grouped_rooms) == 2
    assert len(grouped_rooms[0]) == 2
    assert len(grouped_rooms[1]) == 1


def test_to_honeybee():
    """Test the to_honeybee method."""
    pts = (Point3D(0, 0, 3), Point3D(5, 0, 3), Point3D(5, 10, 3), Point3D(0, 10, 3))
    ashrae_base = SimpleWindowRatio(0.5)
    overhang = Overhang(1)
    boundarycs = (bcs.outdoors, bcs.ground, bcs.outdoors, bcs.ground)
    window = (ashrae_base, None, ashrae_base, None)
    shading = (overhang, None, None, None)
    room2d = Room2D('ZoneSHOE_BOX920980', Face3D(pts), 3, boundarycs, window, shading)
    room, adj = room2d.to_honeybee(1, tolerance=0.1)

    assert room.identifier == 'ZoneSHOE_BOX920980'
    assert room.display_name == 'ZoneSHOE_BOX920980'
    assert isinstance(room.geometry, Polyface3D)
    assert len(room.geometry.vertices) == 8
    assert len(room) == 6
    assert room.volume == 150
    assert room.floor_area == 50
    assert room.exterior_wall_area == 30
    assert room.exterior_aperture_area == 15
    assert room.average_floor_height == 3
    assert room.check_solid(0.01, 1) == ''
    assert len(room[1].apertures) == 1
    assert len(room[2].apertures) == 0
    assert len(room[3].apertures) == 1
    assert len(room[1].outdoor_shades) == 1
    assert len(room[3].outdoor_shades) == 0


def test_to_dict():
    """Test the Room2D to_dict method."""
    pts = (Point3D(0, 0, 3), Point3D(5, 0, 3), Point3D(5, 10, 3), Point3D(0, 10, 3))
    ashrae_base = SimpleWindowRatio(0.4)
    overhang = Overhang(1)
    boundarycs = (bcs.outdoors, bcs.ground, bcs.outdoors, bcs.ground)
    window = (ashrae_base, None, ashrae_base, None)
    shading = (overhang, None, None, None)
    room = Room2D('ShoeBoxZone', Face3D(pts),
                  3, boundarycs, window, shading, True, False)

    rd = room.to_dict()
    assert rd['type'] == 'Room2D'
    assert rd['identifier'] == 'ShoeBoxZone'
    assert rd['display_name'] == 'ShoeBoxZone'
    assert 'floor_boundary' in rd
    assert len(rd['floor_boundary']) == 4
    assert 'floor_holes' not in rd
    assert rd['floor_height'] == 3
    assert rd['floor_to_ceiling_height'] == 3
    assert 'boundary_conditions' in rd
    assert len(rd['boundary_conditions']) == 4
    assert 'window_parameters' in rd
    assert len(rd['window_parameters']) == 4
    assert 'shading_parameters' in rd
    assert len(rd['shading_parameters']) == 4
    assert rd['is_ground_contact']
    assert not rd['is_top_exposed']
    assert 'properties' in rd
    assert rd['properties']['type'] == 'Room2DProperties'

    room_2 = Room2D('ShoeBoxZone', Face3D(pts), 3)
    rd = room_2.to_dict()
    assert 'boundary_conditions' in rd
    assert len(rd['boundary_conditions']) == 4
    assert 'window_parameters' not in rd
    assert 'shading_parameters' not in rd


def test_to_from_dict():
    """Test the to/from dict of Room2D objects."""
    pts = (Point3D(0, 0, 3), Point3D(5, 0, 3), Point3D(5, 10, 3), Point3D(0, 10, 3))
    ashrae_base = SimpleWindowRatio(0.4)
    overhang = Overhang(1)
    boundarycs = (bcs.outdoors, bcs.ground, bcs.outdoors, bcs.ground)
    window = (ashrae_base, None, ashrae_base, None)
    shading = (overhang, None, None, None)
    room = Room2D('ShoeBoxZone', Face3D(pts), 3, boundarycs, window, shading, True)
    room.zone = 'Closed Offices NE'

    room_dict = room.to_dict()
    new_room = Room2D.from_dict(room_dict)
    assert new_room.zone == 'Closed Offices NE'
    assert isinstance(new_room, Room2D)
    assert new_room.to_dict() == room_dict


def test_from_honeybee():
    """Test the from honeybee method."""
    room = Room.from_box('ShoeBoxZone', 5, 10, 3)
    south_face = room[3]
    south_face.apertures_by_ratio(0.5, 0.01)
    north_face = room[1]
    north_face.boundary_condition = bcs.ground

    room2d = Room2D.from_honeybee(room, 0.01)
    assert room2d.boundary_conditions == \
        (bcs.ground, bcs.outdoors, bcs.outdoors, bcs.outdoors)
    assert room2d.window_parameters[0] is None
    assert room2d.window_parameters[1] is None
    assert room2d.window_parameters[3] is None
    assert isinstance(room2d.window_parameters[2], DetailedWindows)
    assert room2d.floor_to_ceiling_height == 3.0
    assert room2d.is_ground_contact
    assert room2d.is_top_exposed


def test_writer():
    """Test the Building writer object."""
    pts_1 = (Point3D(0, 0, 2), Point3D(10, 0, 2), Point3D(10, 10, 2), Point3D(0, 10, 2))
    room2d = Room2D('Office1', Face3D(pts_1), 5)

    writers = [mod for mod in dir(room2d.to) if not mod.startswith('_')]
    for writer in writers:
        assert callable(getattr(room2d.to, writer))


def _is_adiabatic(bc):
    """Test if adiabatic instance, or if honeybee-energy not installed,
    if using default Outdoors.
    """
    try:
        return isinstance(bc, type(bcs.adiabatic))
    except AttributeError:
        return isinstance(bc, Outdoors)
