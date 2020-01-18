# coding=utf-8
import pytest

from dragonfly.room2d import Room2D
from dragonfly.windowparameter import SimpleWindowRatio, SingleWindow
from dragonfly.shadingparameter import Overhang

from honeybee.boundarycondition import Outdoors, Ground, Surface
from honeybee.boundarycondition import boundary_conditions as bcs

from ladybug_geometry.geometry2d.pointvector import Point2D, Vector2D
from ladybug_geometry.geometry2d.line import LineSegment2D
from ladybug_geometry.geometry2d.polygon import Polygon2D
from ladybug_geometry.geometry3d.pointvector import Point3D, Vector3D
from ladybug_geometry.geometry3d.line import LineSegment3D
from ladybug_geometry.geometry3d.plane import Plane
from ladybug_geometry.geometry3d.face import Face3D
from ladybug_geometry.geometry3d.polyface import Polyface3D


def test_room2d_init():
    """Test the initalization of Room2D objects and basic properties."""
    pts = (Point3D(1, 1, 2), Point3D(1, 2, 2), Point3D(2, 2, 2), Point3D(2, 1, 2))
    plane = Plane(Vector3D(0, 0, 1), Point3D(0, 0, 2))
    room2d = Room2D('Zone: CLOSET [920980]', Face3D(pts, plane), 3)
    str(room2d)  # test the string representation

    assert room2d.name == 'ZoneCLOSET920980'
    assert room2d.display_name == 'Zone: CLOSET [920980]'
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
    """Test the initalization of Room2D objects with windows."""
    pts = (Point3D(0, 0, 3), Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(0, 10, 3))
    ashrae_base = SimpleWindowRatio(0.4)
    overhang = Overhang(1)
    boundarycs = (bcs.outdoors, bcs.ground, bcs.outdoors, bcs.ground)
    window = (ashrae_base, None, ashrae_base, None)
    shading = (overhang, None, None, None)
    room2d = Room2D('Square Shoebox', Face3D(pts), 3, boundarycs, window, shading)

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
    """Test the initalization of Room2D with a hole."""
    bound_pts = [Point3D(0, 0), Point3D(3, 0), Point3D(3, 3), Point3D(0, 3)]
    hole_pts = [Point3D(1, 1, 0), Point3D(2, 1, 0), Point3D(2, 2, 0), Point3D(1, 2, 0)]
    face = Face3D(bound_pts, None, [hole_pts])
    room2d = Room2D('Donut Room', face, 3)

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
    """Test the initalization of Room2D objects with invalid inputs."""
    pts = (Point3D(0, 0, 3), Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(0, 10, 3))
    ashrae_base = SimpleWindowRatio(0.4)
    overhang = Overhang(1)
    boundarycs = [bcs.outdoors, bcs.ground, bcs.outdoors, bcs.ground]
    window = [ashrae_base, None, ashrae_base, None]
    shading = [overhang, None, None, None]
    Room2D('Square Shoebox', Face3D(pts), 3, boundarycs, window, shading)

    old_bc = boundarycs.pop(-1)
    with pytest.raises(AssertionError):
        Room2D('Square Shoebox', Face3D(pts), 3, boundarycs, window, shading)
    boundarycs.append(old_bc)

    old_glz = window.pop(-1)
    with pytest.raises(AssertionError):
        Room2D('Square Shoebox', Face3D(pts), 3, boundarycs, window, shading)
    window.append(old_glz)

    old_shd = shading.pop(-1)
    with pytest.raises(AssertionError):
        Room2D('Square Shoebox', Face3D(pts), 3, boundarycs, window, shading)
    shading.append(old_shd)

    new_bcs = [bcs.ground, bcs.outdoors, bcs.outdoors, bcs.ground]
    with pytest.raises(AssertionError):
        Room2D('Square Shoebox', Face3D(pts), 3, new_bcs, window, shading)

    new_glz = [None, ashrae_base, ashrae_base, None]
    with pytest.raises(AssertionError):
        Room2D('Square Shoebox', Face3D(pts), 3, boundarycs, new_glz, shading)


def test_room2d_init_clockwise():
    """Test the initalization of Room2D objects with clockwise vertices."""
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
    room2d = Room2D('TestZone', Face3D(pts, holes=[pts_hole]), 3, boundarycs, window, shading)

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
    """Test the initalization of Room2D objects from a Polygon2D."""
    pts = (Point2D(0, 0), Point2D(10, 0), Point2D(10, 10), Point2D(0, 10))
    polygon = Polygon2D(pts)
    ashrae_base = SimpleWindowRatio(0.4)
    overhang = Overhang(1)
    boundarycs = (bcs.outdoors, bcs.ground, bcs.outdoors, bcs.ground)
    window = (ashrae_base, None, ashrae_base, None)
    shading = (overhang, None, None, None)
    room2d = Room2D.from_polygon('Square Shoebox', polygon, 3, 3,
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
    """Test the initalization of Room2D objects from a clockwise Polygon2D."""
    pts_3d = (Point3D(0, 10, 3), Point3D(10, 10, 3), Point3D(10, 0, 3), Point3D(0, 0, 3))
    pts = (Point2D(0, 10), Point2D(10, 10), Point2D(10, 0), Point2D(0, 0))
    polygon = Polygon2D(pts)
    ashrae_base = SimpleWindowRatio(0.4)
    overhang = Overhang(1)
    boundarycs = (bcs.outdoors, bcs.outdoors, bcs.ground, bcs.ground)
    window = (ashrae_base, ashrae_base, None, None)
    shading = (overhang, None, None, None)
    room2d = Room2D.from_polygon('Square Shoebox', polygon, 3, 3,
                                 boundarycs, window, shading)

    assert room2d.floor_geometry.boundary == tuple(reversed(pts_3d))
    assert room2d.boundary_conditions == tuple(reversed(boundarycs))
    assert room2d.window_parameters == tuple(reversed(window))
    assert room2d.shading_parameters == tuple(reversed(shading))


def test_room2d_init_from_vertices():
    """Test the initalization of Room2D objects from 2D vertices."""
    pts = (Point2D(0, 0), Point2D(10, 0), Point2D(10, 10), Point2D(0, 10))
    ashrae_base = SimpleWindowRatio(0.4)
    overhang = Overhang(1)
    boundarycs = (bcs.outdoors, bcs.ground, bcs.outdoors, bcs.ground)
    window = (ashrae_base, None, ashrae_base, None)
    shading = (overhang, None, None, None)
    room2d = Room2D.from_vertices('Square Shoebox', pts, 3, 3,
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
    room2d = Room2D('Zone: CLOSET [920980]', Face3D(pts, plane), 3)

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
    room2d = Room2D('Square Shoebox', Face3D(pts), 3, boundarycs)
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


def test_generate_grid():
    """Test the generate_grid method."""
    pts = (Point3D(0, 0, 3), Point3D(5, 0, 3), Point3D(5, 10, 3), Point3D(0, 10, 3))
    room = Room2D('Square Shoebox', Face3D(pts), 3)
    mesh_grid = room.generate_grid(1)
    assert len(mesh_grid.faces) == 50
    mesh_grid = room.generate_grid(0.5)
    assert len(mesh_grid.faces) == 200


def test_move():
    """Test the Room2D move method."""
    pts_1 = (Point3D(0, 2, 0), Point3D(2, 2, 0), Point3D(2, 0, 0), Point3D(0, 0, 0))
    plane_1 = Plane(Vector3D(0, 0, 1), Point3D(0, 0, 0))
    room = Room2D('Square Shoebox', Face3D(pts_1, plane_1), 3)

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
    room = Room2D('Square Shoebox', Face3D(pts, plane_1), 3)
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
    room = Room2D('Square Shoebox', Face3D(pts, plane), 3)
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
    room = Room2D('Square Shoebox', Face3D(pts, plane), 3)

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


def test_room2d_solve_adjacency():
    """Test the Room2D solve_adjacency method."""
    pts_1 = (Point3D(0, 0, 3), Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(0, 10, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(20, 0, 3), Point3D(20, 10, 3), Point3D(10, 10, 3))
    room2d_1 = Room2D('Square Shoebox 1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Square Shoebox 2', Face3D(pts_2), 3)
    Room2D.solve_adjacency([room2d_1, room2d_2], 0.01)

    assert isinstance(room2d_1.boundary_conditions[1], Surface)
    assert isinstance(room2d_2.boundary_conditions[3], Surface)
    assert room2d_1.boundary_conditions[1].boundary_condition_object == \
        '{}..Face4'.format(room2d_2.name)
    assert room2d_2.boundary_conditions[3].boundary_condition_object == \
        '{}..Face2'.format(room2d_1.name)


def test_solve_adjacency_aperture():
    """Test the Room2D solve_adjacency method with an interior aperture."""
    pts_1 = (Point3D(0, 0, 3), Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(0, 10, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(20, 0, 3), Point3D(20, 10, 3), Point3D(10, 10, 3))
    ashrae_base = SimpleWindowRatio(0.4)
    window_1 = (None, ashrae_base, None, None)
    window_2 = (None, None, None, ashrae_base)
    window_3 = (None, None, None, None)
    room2d_1 = Room2D('Square Shoebox 1', Face3D(pts_1), 3, None, window_1)
    room2d_2 = Room2D('Square Shoebox 2', Face3D(pts_2), 3, None, window_2)
    room2d_3 = Room2D('Square Shoebox 3', Face3D(pts_2), 3, None, window_3)
    Room2D.solve_adjacency([room2d_1, room2d_2], 0.01)

    assert room2d_1.boundary_conditions[1].boundary_condition_object == \
        '{}..Face4'.format(room2d_2.name)
    assert room2d_2.boundary_conditions[3].boundary_condition_object == \
        '{}..Face2'.format(room2d_1.name)

    with pytest.raises(AssertionError):
        Room2D.solve_adjacency([room2d_1, room2d_3], 0.01)


def test_room2d_intersect_adjacency():
    """Test the Room2D intersect_adjacency method."""
    pts_1 = (Point3D(0, 0, 3), Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(0, 10, 3))
    pts_2 = (Point3D(10, 5, 2), Point3D(20, 5, 2), Point3D(20, 15, 2), Point3D(10, 15, 2))
    room2d_1 = Room2D('Square Shoebox 1', Face3D(pts_1), 3)
    room2d_2 = Room2D('Square Shoebox 2', Face3D(pts_2), 3)
    room2d_1, room2d_2 = Room2D.intersect_adjacency([room2d_1, room2d_2], 0.01)

    assert len(room2d_1) == 5
    assert len(room2d_2) == 5

    Room2D.solve_adjacency([room2d_1, room2d_2], 0.01)

    assert isinstance(room2d_1.boundary_conditions[2], Surface)
    assert isinstance(room2d_2.boundary_conditions[4], Surface)
    assert room2d_1.boundary_conditions[2].boundary_condition_object == \
        '{}..Face5'.format(room2d_2.name)
    assert room2d_2.boundary_conditions[4].boundary_condition_object == \
        '{}..Face3'.format(room2d_1.name)


def test_to_honeybee():
    """Test the to_honeybee method."""
    pts = (Point3D(0, 0, 3), Point3D(5, 0, 3), Point3D(5, 10, 3), Point3D(0, 10, 3))
    ashrae_base = SimpleWindowRatio(0.5)
    overhang = Overhang(1)
    boundarycs = (bcs.outdoors, bcs.ground, bcs.outdoors, bcs.ground)
    window = (ashrae_base, None, ashrae_base, None)
    shading = (overhang, None, None, None)
    room2d = Room2D('Zone: SHOE_BOX [920980]', Face3D(pts), 3, boundarycs, window, shading)
    room = room2d.to_honeybee(1, 0.1)

    assert room.name == 'ZoneSHOE_BOX920980'
    assert room.display_name == 'Zone: SHOE_BOX [920980]'
    assert isinstance(room.geometry, Polyface3D)
    assert len(room.geometry.vertices) == 8
    assert len(room) == 6
    assert room.volume == 150
    assert room.floor_area == 50
    assert room.exterior_wall_area == 30
    assert room.exterior_aperture_area == 15
    assert room.average_floor_height == 3
    assert room.check_solid(0.01, 1)
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
    room = Room2D('Shoe Box Zone', Face3D(pts), 3, boundarycs, window, shading, True, False)

    rd = room.to_dict()
    assert rd['type'] == 'Room2D'
    assert rd['name'] == 'ShoeBoxZone'
    assert rd['display_name'] == 'Shoe Box Zone'
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

    room_2 = Room2D('Shoe Box Zone', Face3D(pts), 3)
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
    room = Room2D('Shoe Box Zone', Face3D(pts), 3, boundarycs, window, shading, True)

    room_dict = room.to_dict()
    new_room = Room2D.from_dict(room_dict)
    assert isinstance(new_room, Room2D)
    assert new_room.to_dict() == room_dict
