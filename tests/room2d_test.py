# coding=utf-8
import pytest
import json

from dragonfly.room2d import Room2D
from dragonfly.story import Story
from dragonfly.windowparameter import SimpleWindowRatio, SingleWindow, DetailedWindows
from dragonfly.shadingparameter import Overhang

from honeybee.boundarycondition import Outdoors, Ground, Surface
from honeybee.boundarycondition import boundary_conditions as bcs
from honeybee.facetype import AirBoundary
from honeybee.room import Room

from ladybug_geometry.geometry2d.pointvector import Point2D, Vector2D
from ladybug_geometry.geometry2d.line import LineSegment2D
from ladybug_geometry.geometry2d.polygon import Polygon2D
from ladybug_geometry.geometry3d.pointvector import Point3D, Vector3D
from ladybug_geometry.geometry3d.line import LineSegment3D
from ladybug_geometry.geometry3d.plane import Plane
from ladybug_geometry.geometry3d.face import Face3D
from ladybug_geometry.geometry3d.polyface import Polyface3D


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
        Room2D.solve_adjacency([room2d_1, room2d_3], 0.01)


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


def test_honeybee_ceiling_plenum():
    """Test the add_plenum functionality in the to_honeybee method with ceiling."""

    # Simple 10 x 10 room
    tol = 0.01
    pts1 = (Point3D(0, 0, 0), Point3D(10, 0, 0), Point3D(10, 10, 0), Point3D(0, 10, 0))
    pts2 = (Point3D(10, 0, 0), Point3D(20, 0, 0), Point3D(20, 10, 0), Point3D(10, 10, 0))

    # Two rooms with different heights
    room2d_3m = Room2D('R1-3m', floor_geometry=Face3D(pts1), floor_to_ceiling_height=3,
                       is_ground_contact=True, is_top_exposed=True)
    room2d_2m = Room2D('R2-2m', floor_geometry=Face3D(pts2), floor_to_ceiling_height=2,
                       is_ground_contact=True, is_top_exposed=True)

    # Check raise exception when no Story is set
    with pytest.raises(AttributeError):
        _ = room2d_2m.duplicate().to_honeybee(tolerance=tol, add_plenum=True)

    # Intersection at:
    #   ((10, 0, 0), (10, 10, 0)) # room2d_3m adj idx @ 1
    #   ((10, 10, 0), (10, 0, 0)) # room2d_2m adj idx @ 3

    story = Story('S1', [room2d_3m, room2d_2m], floor_to_floor_height=3.0)
    story.solve_room_2d_adjacency(0.01)

    # Check default ceiling condition w/o plenum for 2m
    _hb_room_2m, _ = room2d_2m.duplicate().to_honeybee(tolerance=tol, add_plenum=False)
    assert isinstance(_hb_room_2m[-1].boundary_condition, Outdoors)

    # Make HB room w/ plenum for 2m
    hb_room_2m, _ = room2d_2m.to_honeybee(tolerance=tol, add_plenum=True)
    assert isinstance(hb_room_2m[0][-1].boundary_condition, Surface)
    assert len(hb_room_2m) == 2

    plenum_2m = hb_room_2m[1]
    assert len(plenum_2m[:]) == 6

    for i, face in enumerate(plenum_2m.faces):
        if face.identifier == 'R2-2m_ceiling_plenum..Face0':
            assert isinstance(face.boundary_condition, Surface)
        elif face.identifier == 'R2-2m_ceiling_plenum..Face1':
            assert isinstance(face.boundary_condition, Outdoors)
        elif face.identifier == 'R2-2m_ceiling_plenum..Face2':
            assert isinstance(face.boundary_condition, Outdoors)
        elif face.identifier == 'R2-2m_ceiling_plenum..Face3':
            assert isinstance(face.boundary_condition, Outdoors)
        elif face.identifier == 'R2-2m_ceiling_plenum..Face4':
            assert _is_adiabatic(face.boundary_condition)
        elif face.identifier == 'R2-2m_ceiling_plenum..Face5':
            assert isinstance(face.boundary_condition, Outdoors)  # Roof exposed outdoors
        else:
            assert False

    # Check height of plenum
    test_vert_face = (Point3D(10, 0, 2), Point3D(20, 0, 2),
                      Point3D(20, 0, 3), Point3D(10, 0, 3))
    for test_vert, vert in zip(test_vert_face, plenum_2m[1].vertices):
        assert test_vert.is_equivalent(vert, tol)

    # Make HB room w/ plenum for 3m, no plenum produced
    hb_rooms_3m, _ = room2d_3m.to_honeybee(tolerance=tol, add_plenum=True)
    assert len(hb_rooms_3m) == 1
    assert isinstance(hb_rooms_3m[0][-1].boundary_condition, Outdoors)


def test_honeybee_floor_plenum():
    """Test the add_plenum functionality in the to_honeybee method with floor."""

    # Simple 10 x 10 room
    tol = 0.01
    pts1 = (Point3D(0, 0, 1), Point3D(10, 0, 1), Point3D(10, 10, 1), Point3D(0, 10, 1))
    pts2 = (Point3D(10, 0, 1.5), Point3D(20, 0, 1.5), Point3D(20, 10, 1.5),
            Point3D(10, 10, 1.5))

    # Two rooms with different floor heights
    room2d_1m = Room2D('R1-1m', floor_geometry=Face3D(pts1), floor_to_ceiling_height=3,
                       is_ground_contact=True, is_top_exposed=True)
    room2d_5m = Room2D('R2-5m', floor_geometry=Face3D(pts2), floor_to_ceiling_height=3,
                       is_ground_contact=False, is_top_exposed=True)

    story = Story('S1', [room2d_1m, room2d_5m], floor_to_floor_height=3.0)
    story.solve_room_2d_adjacency(0.01)

    # Check story floor height is minimum of room floor heights
    assert story.floor_height == pytest.approx(1, abs=1e-10)

    # Check default floor condition w/o plenum
    _hb_room_5m, _ = room2d_5m.duplicate().to_honeybee(tolerance=tol, add_plenum=False)
    assert isinstance(_hb_room_5m[-1].boundary_condition, Outdoors)
    assert _is_adiabatic(_hb_room_5m[0].boundary_condition)

    # Make HB room w/ plenum for 2m
    hb_room_5m, _ = room2d_5m.to_honeybee(tolerance=tol, add_plenum=True)
    assert len(hb_room_5m) == 2

    plenum_5m = hb_room_5m[-1]
    assert len(plenum_5m[:]) == 6

    for i, face in enumerate(plenum_5m.faces):
        if face.identifier == 'R2-5m_floor_plenum..Face0':
            assert _is_adiabatic(face.boundary_condition)
        elif face.identifier == 'R2-5m_floor_plenum..Face1':
            assert isinstance(face.boundary_condition, Outdoors)
        elif face.identifier == 'R2-5m_floor_plenum..Face2':
            assert isinstance(face.boundary_condition, Outdoors)
        elif face.identifier == 'R2-5m_floor_plenum..Face3':
            assert isinstance(face.boundary_condition, Outdoors)
        elif face.identifier == 'R2-5m_floor_plenum..Face4':
            assert _is_adiabatic(face.boundary_condition)
        elif face.identifier == 'R2-5m_floor_plenum..Face5':
            assert isinstance(face.boundary_condition, Surface)
        else:
            assert False

    # Check height of plenum
    test_vert_face = (Point3D(10, 0, 1), Point3D(20, 0, 1),
                      Point3D(20, 0, 1.5), Point3D(10, 0, 1.5))
    for test_vert, vert in zip(test_vert_face, plenum_5m[1].vertices):
        assert test_vert.is_equivalent(vert, tol)

    # Make HB room w/ plenum for 1m floor height, no plenum produced
    hb_rooms_1m, _ = room2d_1m.to_honeybee(tolerance=tol, add_plenum=True)
    assert len(hb_rooms_1m) == 1
    assert isinstance(hb_rooms_1m[0][0].boundary_condition, Ground)


def test_honeybee_ceiling_and_floor_plenum():
    """Test the add_plenum in the to_honeybee method with ceiling and floor."""

    # Simple 10 x 10 room
    tol = 0.01
    pts1 = (Point3D(0, 0, 1), Point3D(10, 0, 1), Point3D(10, 10, 1), Point3D(0, 10, 1))
    pts2 = (Point3D(10, 0, 1.5), Point3D(20, 0, 1.5), Point3D(20, 10, 1.5),
            Point3D(10, 10, 1.5))

    # Two rooms that require plenums

    # floor_plenum: 0m, ceiling_plenum: 1m
    room2d_1m = Room2D('R1-1m', floor_geometry=Face3D(pts1), floor_to_ceiling_height=3,
                       is_ground_contact=True, is_top_exposed=False)
    # floor_plenum: 0.5m, ceiling_plenum: 1m
    room2d_5m = Room2D('R2-5m', floor_geometry=Face3D(pts2), floor_to_ceiling_height=3,
                       is_ground_contact=False, is_top_exposed=False)

    story = Story('S1', [room2d_1m, room2d_5m], floor_to_floor_height=4.0)
    story.solve_room_2d_adjacency(tol)

    # Make HB room w/ just ceiling plenum
    hb_rooms_1m, _ = room2d_1m.to_honeybee(tolerance=tol, add_plenum=True)
    assert len(hb_rooms_1m) == 2

    # Make HB room w/ both
    hb_rooms_5m, _ = room2d_5m.to_honeybee(tolerance=tol, add_plenum=True)
    assert len(hb_rooms_5m) == 3

    hb_room_5m, ceil_plenum_5m, floor_plenum_5m = hb_rooms_5m

    # Check names
    assert hb_room_5m.identifier == 'R2-5m'
    assert ceil_plenum_5m.identifier == 'R2-5m_ceiling_plenum'
    assert floor_plenum_5m.identifier == 'R2-5m_floor_plenum'

    # Check height of floor_plenum
    test_vert_face = (Point3D(10, 0, 1), Point3D(20, 0, 1),
                      Point3D(20, 0, 1.5), Point3D(10, 0, 1.5))
    for test_vert, vert in zip(test_vert_face, floor_plenum_5m[1].vertices):
        assert test_vert.is_equivalent(vert, tol)

    # Check height of ceil_plenum
    test_vert_face = (Point3D(10, 0, 4.5), Point3D(20, 0, 4.5),
                      Point3D(20, 0, 5.0), Point3D(10, 0, 5.0))
    for test_vert, vert in zip(test_vert_face, ceil_plenum_5m[1].vertices):
        assert test_vert.is_equivalent(vert, tol)


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

    room_dict = room.to_dict()
    new_room = Room2D.from_dict(room_dict)
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
        (bcs.outdoors, bcs.ground, bcs.outdoors, bcs.outdoors)
    assert room2d.window_parameters[0] is None
    assert room2d.window_parameters[1] is None
    assert room2d.window_parameters[2] is None
    assert isinstance(room2d.window_parameters[3], DetailedWindows)
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
