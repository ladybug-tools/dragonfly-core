# coding=utf-8
import pytest
import math
import json

from ladybug_geometry.geometry2d import Point2D, LineSegment2D, Polygon2D
from ladybug_geometry.geometry3d import Vector3D, Point3D, Plane, Face3D, LineSegment3D

from dragonfly.roof import RoofSpecification


def test_roof_init():
    """Test the initialization of RoofSpecification objects and basic properties."""
    pts_1 = (Point3D(0, 0, 0), Point3D(10, 0, 0), Point3D(10, 5, 5), Point3D(0, 5, 5))
    pts_2 = (Point3D(0, 5, 5), Point3D(10, 5, 5), Point3D(10, 10, 0), Point3D(0, 10, 0))
    pts_3 = (Point3D(0, 0, 0), Point3D(10, 0, 0), Point3D(10, -5, 0), Point3D(0, -5, 0))
    roof = RoofSpecification([Face3D(pts_1), Face3D(pts_2), Face3D(pts_3)])
    str(roof)  # test the string representation

    assert isinstance(roof.geometry[0], Face3D)
    assert isinstance(roof[0], Face3D)
    assert len(roof) == 3
    assert len(roof[0]) == 4
    assert roof.parent is None
    assert not roof.has_parent
    assert all([isinstance(poly, Polygon2D) for poly in roof.boundary_geometry_2d])
    assert all([isinstance(pln, Plane) for pln in roof.planes])
    assert isinstance(roof.min, Point2D)
    assert isinstance(roof.max, Point2D)
    assert roof.min_height == pytest.approx(0.0, abs=1e-3)
    assert roof.max_height == pytest.approx(5.0, abs=1e-3)

    assert roof.center_heights[0] == pytest.approx(2.5, abs=1e-3)
    assert roof.center_heights[1] == pytest.approx(2.5, abs=1e-3)
    assert roof.center_heights[2] == pytest.approx(0.0, abs=1e-3)

    assert roof.azimuths[0] == pytest.approx(180.0, abs=1e-3)
    assert roof.azimuths[1] == pytest.approx(0.0, abs=1e-3)
    assert roof.azimuths[2] == pytest.approx(0.0, abs=1e-3)

    assert roof.tilts[0] == pytest.approx(45.0, abs=1e-3)
    assert roof.tilts[1] == pytest.approx(45.0, abs=1e-3)
    assert roof.tilts[2] == pytest.approx(0.0, abs=1e-3)


def test_resolved_geometry():
    """Test the RoofSpecification resolved_geometry method."""
    pts_1 = (Point3D(0, 0, 0), Point3D(10, 0, 0), Point3D(10, 7, 7), Point3D(0, 7, 7))
    pts_2 = (Point3D(0, 5, 5), Point3D(10, 5, 5), Point3D(10, 10, 0), Point3D(0, 10, 0))
    pts_3 = (Point3D(0, 0, 0), Point3D(10, 0, 0), Point3D(10, -5, 0), Point3D(0, -5, 0))
    roof = RoofSpecification([Face3D(pts_1), Face3D(pts_2), Face3D(pts_3)])

    assert roof.overlap_count(0.01) == 1
    res_geo = roof.resolved_geometry(0.01)
    roof = RoofSpecification(res_geo)
    assert roof.overlap_count(0.01) == 0

    assert res_geo[0].area == pytest.approx(10.0 * math.sqrt(50), abs=1e-3)
    assert res_geo[1].area == pytest.approx(10.0 * math.sqrt(50), abs=1e-3)
    assert res_geo[2].area == pytest.approx(50.0, abs=1e-3)

    assert res_geo[0].center.z == pytest.approx(2.5, abs=1e-3)
    assert res_geo[1].center.z == pytest.approx(2.5, abs=1e-3)
    assert res_geo[2].center.z == pytest.approx(0.0, abs=1e-3)


def test_roof_find_gaps():
    """Test the RoofSpecification.find_gaps method."""
    pts_1 = (Point3D(0, 0, 0), Point3D(10, 0, 0), Point3D(10, 5, 5), Point3D(0, 5, 5))
    pts_2 = (Point3D(0, 5, 5), Point3D(10, 5, 5), Point3D(10, 10, 0), Point3D(0, 10, 0))
    pts_3 = (Point3D(0, 0, 0), Point3D(10, -0, 0), Point3D(10, -5, 0), Point3D(0, -5, 0))
    pts_4 = (Point3D(0, -0.05, 0), Point3D(10, 0, 0), Point3D(10, -5, 0), Point3D(0, -5, 0))
    pts_5 = (Point3D(0, -0.05, 0), Point3D(10, -0.05, 0), Point3D(10, -5, 0), Point3D(0, -5, 0))

    roof1 = RoofSpecification([Face3D(pts_1), Face3D(pts_2), Face3D(pts_3)])
    assert len(roof1.find_gaps(0.1)) == 0

    roof2 = RoofSpecification([Face3D(pts_1), Face3D(pts_2), Face3D(pts_4)])
    assert len(roof2.find_gaps(0.1)) == 2

    roof3 = RoofSpecification([Face3D(pts_1), Face3D(pts_2), Face3D(pts_5)])
    assert len(roof3.find_gaps(0.1)) == 4


def test_move():
    """Test the RoofSpecification move method."""
    pts_1 = (Point3D(0, 2, 0), Point3D(2, 2, 0), Point3D(2, 0, 0), Point3D(0, 0, 0))
    roof = RoofSpecification([Face3D(pts_1)])

    vec_1 = Vector3D(2, 2, 2)
    new_r = roof.duplicate()
    new_r.move(vec_1)
    assert new_r.geometry[0][0] == Point3D(2, 4, 2)
    assert new_r.geometry[0][1] == Point3D(4, 4, 2)
    assert new_r.geometry[0][2] == Point3D(4, 2, 2)
    assert new_r.geometry[0][3] == Point3D(2, 2, 2)


def test_scale():
    """Test the RoofSpecification scale method."""
    pts = (Point3D(1, 1, 2), Point3D(2, 1, 2), Point3D(2, 2, 2), Point3D(1, 2, 2))
    roof = RoofSpecification([Face3D(pts)])

    new_r = roof.duplicate()
    new_r.scale(2)
    assert new_r.geometry[0][0] == Point3D(2, 2, 4)
    assert new_r.geometry[0][1] == Point3D(4, 2, 4)
    assert new_r.geometry[0][2] == Point3D(4, 4, 4)
    assert new_r.geometry[0][3] == Point3D(2, 4, 4)
    assert new_r.geometry[0].area == roof.geometry[0].area * 2 ** 2


def test_rotate_xy():
    """Test the RoofSpecification rotate_xy method."""
    pts = (Point3D(1, 1, 2), Point3D(2, 1, 2), Point3D(2, 2, 2), Point3D(1, 2, 2))
    roof = RoofSpecification([Face3D(pts)])
    origin_1 = Point3D(1, 1, 0)

    test_1 = roof.duplicate()
    test_1.rotate_xy(180, origin_1)
    assert test_1.geometry[0][0].x == pytest.approx(1, rel=1e-3)
    assert test_1.geometry[0][0].y == pytest.approx(1, rel=1e-3)
    assert test_1.geometry[0][0].z == pytest.approx(2, rel=1e-3)
    assert test_1.geometry[0][2].x == pytest.approx(0, rel=1e-3)
    assert test_1.geometry[0][2].y == pytest.approx(0, rel=1e-3)
    assert test_1.geometry[0][2].z == pytest.approx(2, rel=1e-3)

    test_2 = roof.duplicate()
    test_2.rotate_xy(90, origin_1)
    assert test_2.geometry[0][0].x == pytest.approx(1, rel=1e-3)
    assert test_2.geometry[0][0].y == pytest.approx(1, rel=1e-3)
    assert test_2.geometry[0][0].z == pytest.approx(2, rel=1e-3)
    assert test_2.geometry[0][2].x == pytest.approx(0, rel=1e-3)
    assert test_2.geometry[0][2].y == pytest.approx(2, rel=1e-3)
    assert test_2.geometry[0][2].z == pytest.approx(2, rel=1e-3)


def test_reflect():
    """Test the RoofSpecification reflect method."""
    pts = (Point3D(1, 1, 2), Point3D(2, 1, 2), Point3D(2, 2, 2), Point3D(1, 2, 2))
    roof = RoofSpecification([Face3D(pts)])

    origin_1 = Point3D(1, 0, 2)
    origin_2 = Point3D(0, 0, 2)
    normal_1 = Vector3D(1, 0, 0)
    normal_2 = Vector3D(-1, -1, 0).normalize()
    plane_1 = Plane(normal_1, origin_1)
    plane_2 = Plane(normal_2, origin_2)
    plane_3 = Plane(normal_2, origin_1)

    test_1 = roof.duplicate()
    test_1.reflect(plane_1)
    assert test_1.geometry[0][-1].x == pytest.approx(1, rel=1e-3)
    assert test_1.geometry[0][-1].y == pytest.approx(1, rel=1e-3)
    assert test_1.geometry[0][-1].z == pytest.approx(2, rel=1e-3)
    assert test_1.geometry[0][1].x == pytest.approx(0, rel=1e-3)
    assert test_1.geometry[0][1].y == pytest.approx(2, rel=1e-3)
    assert test_1.geometry[0][1].z == pytest.approx(2, rel=1e-3)

    test_1 = roof.duplicate()
    test_1.reflect(plane_2)
    assert test_1.geometry[0][-1].x == pytest.approx(-1, rel=1e-3)
    assert test_1.geometry[0][-1].y == pytest.approx(-1, rel=1e-3)
    assert test_1.geometry[0][-1].z == pytest.approx(2, rel=1e-3)
    assert test_1.geometry[0][1].x == pytest.approx(-2, rel=1e-3)
    assert test_1.geometry[0][1].y == pytest.approx(-2, rel=1e-3)
    assert test_1.geometry[0][1].z == pytest.approx(2, rel=1e-3)

    test_2 = roof.duplicate()
    test_2.reflect(plane_3)
    assert test_2.geometry[0][-1].x == pytest.approx(0, rel=1e-3)
    assert test_2.geometry[0][-1].y == pytest.approx(0, rel=1e-3)
    assert test_2.geometry[0][-1].z == pytest.approx(2, rel=1e-3)
    assert test_2.geometry[0][1].x == pytest.approx(-1, rel=1e-3)
    assert test_2.geometry[0][1].y == pytest.approx(-1, rel=1e-3)
    assert test_2.geometry[0][1].z == pytest.approx(2, rel=1e-3)


def test_roof_align():
    """Test the RoofSpecification.align objects and basic properties."""
    pts_1 = (Point3D(0, 0, 0), Point3D(10, 0, 0), Point3D(10, 5, 5), Point3D(0, 5, 5))
    pts_2 = (Point3D(0, 5, 5), Point3D(10, 5, 5), Point3D(10, 10, 0), Point3D(0, 10, 0))
    roof = RoofSpecification([Face3D(pts_1), Face3D(pts_2)])

    align_seg_1 = LineSegment2D.from_end_points(Point2D(12, 10), Point2D(12, 0))
    test_1 = roof.duplicate()
    test_1.align(align_seg_1, 3.0, tolerance=0.01)
    assert test_1.geometry[0][1].x == pytest.approx(12, rel=1e-3)
    assert test_1.geometry[0][1].y == pytest.approx(0, rel=1e-3)
    assert test_1.geometry[0][1].z == pytest.approx(0, rel=1e-3)
    assert test_1.geometry[0][2].x == pytest.approx(12, rel=1e-3)
    assert test_1.geometry[0][2].y == pytest.approx(5, rel=1e-3)
    assert test_1.geometry[0][2].z == pytest.approx(5, rel=1e-3)
    assert test_1.geometry[1][1].x == pytest.approx(12, rel=1e-3)
    assert test_1.geometry[1][1].y == pytest.approx(5, rel=1e-3)
    assert test_1.geometry[1][1].z == pytest.approx(5, rel=1e-3)
    assert test_1.geometry[1][2].x == pytest.approx(12, rel=1e-3)
    assert test_1.geometry[1][2].y == pytest.approx(10, rel=1e-3)
    assert test_1.geometry[1][2].z == pytest.approx(0, rel=1e-3)

    align_seg_2 = LineSegment2D.from_end_points(Point2D(10, 10), Point2D(14, 0))
    test_2 = roof.duplicate()
    test_2.align(align_seg_2, 4.5, tolerance=0.01)
    assert test_2.geometry[0][1].x == pytest.approx(14, rel=1e-3)
    assert test_2.geometry[0][1].y == pytest.approx(0, rel=1e-3)
    assert test_2.geometry[0][1].z == pytest.approx(0, rel=1e-3)
    assert test_2.geometry[0][2].x == pytest.approx(12, rel=1e-3)
    assert test_2.geometry[0][2].y == pytest.approx(5, rel=1e-3)
    assert test_2.geometry[0][2].z == pytest.approx(5, rel=1e-3)
    assert test_2.geometry[1][1].x == pytest.approx(12, rel=1e-3)
    assert test_2.geometry[1][1].y == pytest.approx(5, rel=1e-3)
    assert test_2.geometry[1][1].z == pytest.approx(5, rel=1e-3)
    assert test_2.geometry[1][2].x == pytest.approx(10, rel=1e-3)
    assert test_2.geometry[1][2].y == pytest.approx(10, rel=1e-3)
    assert test_2.geometry[1][2].z == pytest.approx(0, rel=1e-3)


def test_roof_pull_to_segments():
    """Test the RoofSpecification.pull_to_segments objects and basic properties."""
    pts_1 = (Point3D(0, 0, 0), Point3D(10, 0, 0), Point3D(10, 5, 5), Point3D(0, 5, 5))
    pts_2 = (Point3D(0, 5, 5), Point3D(10, 5, 5), Point3D(10, 10, 0), Point3D(0, 10, 0))
    roof = RoofSpecification([Face3D(pts_1), Face3D(pts_2)])

    align_seg_1 = LineSegment2D.from_end_points(Point2D(12, 10), Point2D(12, 0))
    test_1 = roof.duplicate()
    test_1.pull_to_segments([align_seg_1], 3.0, snap_vertices=False, tolerance=0.01)
    assert test_1.geometry[0][1].x == pytest.approx(12, rel=1e-3)
    assert test_1.geometry[0][1].y == pytest.approx(0, rel=1e-3)
    assert test_1.geometry[0][1].z == pytest.approx(0, rel=1e-3)
    assert test_1.geometry[0][2].x == pytest.approx(12, rel=1e-3)
    assert test_1.geometry[0][2].y == pytest.approx(5, rel=1e-3)
    assert test_1.geometry[0][2].z == pytest.approx(5, rel=1e-3)
    assert test_1.geometry[1][1].x == pytest.approx(12, rel=1e-3)
    assert test_1.geometry[1][1].y == pytest.approx(5, rel=1e-3)
    assert test_1.geometry[1][1].z == pytest.approx(5, rel=1e-3)
    assert test_1.geometry[1][2].x == pytest.approx(12, rel=1e-3)
    assert test_1.geometry[1][2].y == pytest.approx(10, rel=1e-3)
    assert test_1.geometry[1][2].z == pytest.approx(0, rel=1e-3)

    align_seg_2 = LineSegment2D.from_end_points(Point2D(10, 10), Point2D(14, 0))
    test_2 = roof.duplicate()
    test_2.pull_to_segments([align_seg_2], 4.5, snap_vertices=False, tolerance=0.01)
    assert test_2.geometry[0][1].x == pytest.approx(14, rel=1e-3)
    assert test_2.geometry[0][1].y == pytest.approx(0, rel=1e-3)
    assert test_2.geometry[0][1].z == pytest.approx(0, rel=1e-3)
    assert test_2.geometry[0][2].x == pytest.approx(12, rel=1e-3)
    assert test_2.geometry[0][2].y == pytest.approx(5, rel=1e-3)
    assert test_2.geometry[0][2].z == pytest.approx(5, rel=1e-3)
    assert test_2.geometry[1][1].x == pytest.approx(12, rel=1e-3)
    assert test_2.geometry[1][1].y == pytest.approx(5, rel=1e-3)
    assert test_2.geometry[1][1].z == pytest.approx(5, rel=1e-3)
    assert test_2.geometry[1][2].x == pytest.approx(10, rel=1e-3)
    assert test_2.geometry[1][2].y == pytest.approx(10, rel=1e-3)
    assert test_2.geometry[1][2].z == pytest.approx(0, rel=1e-3)

    pts_3 = (Point3D(0, 0, 0), Point3D(10, 0, 0), Point3D(10, -5, 0), Point3D(0, -5, 0))
    test_3 = RoofSpecification([Face3D(pts_1), Face3D(pts_2), Face3D(pts_3)])
    test_3.pull_to_segments([align_seg_2], 4.5, snap_vertices=False,
                            selected_indices=[0, 1], tolerance=0.01)
    assert test_2.geometry[0][1].x == pytest.approx(14, rel=1e-3)
    assert test_2.geometry[0][1].y == pytest.approx(0, rel=1e-3)
    assert test_2.geometry[0][1].z == pytest.approx(0, rel=1e-3)
    assert test_2.geometry[0][2].x == pytest.approx(12, rel=1e-3)
    assert test_2.geometry[0][2].y == pytest.approx(5, rel=1e-3)
    assert test_2.geometry[0][2].z == pytest.approx(5, rel=1e-3)
    assert test_2.geometry[1][1].x == pytest.approx(12, rel=1e-3)
    assert test_2.geometry[1][1].y == pytest.approx(5, rel=1e-3)
    assert test_2.geometry[1][1].z == pytest.approx(5, rel=1e-3)
    assert test_2.geometry[1][2].x == pytest.approx(10, rel=1e-3)
    assert test_2.geometry[1][2].y == pytest.approx(10, rel=1e-3)
    assert test_2.geometry[1][2].z == pytest.approx(0, rel=1e-3)


def test_subtract_roofs():
    """Test the RoofSpecification subtract_roofs method."""
    pts_1 = (Point3D(0, 0, 0), Point3D(10, 0, 0), Point3D(10, 7, 7), Point3D(0, 7, 7))
    pts_2 = (Point3D(0, 5, 5), Point3D(10, 5, 5), Point3D(10, 10, 0), Point3D(0, 10, 0))
    pts_3 = (Point3D(0, 0, 0), Point3D(10, 0, 0), Point3D(10, -5, 0), Point3D(0, -5, 0))
    roof = RoofSpecification([Face3D(pts_1), Face3D(pts_2), Face3D(pts_3)])

    assert roof.overlap_count(0.01) == 1
    roof.subtract_roofs(1, [0, 2], 0.01)
    assert roof.overlap_count(0.01) == 0

    res_geo = roof.geometry

    assert res_geo[0].area == pytest.approx(10.0 * math.sqrt(49 * 2), abs=1e-3)
    assert res_geo[1].area == pytest.approx(10.0 * math.sqrt(9 * 2), abs=1e-3)
    assert res_geo[2].area == pytest.approx(50.0, abs=1e-3)

    assert res_geo[0].center.z == pytest.approx(3.5, abs=1e-3)
    assert res_geo[1].center.z == pytest.approx(1.5, abs=1e-3)
    assert res_geo[2].center.z == pytest.approx(0.0, abs=1e-3)


def test_split_with_polygon():
    """Test the RoofSpecification split_with_polygon method."""
    pts_1 = (Point3D(0, 0, 0), Point3D(10, 0, 0), Point3D(10, 5, 5), Point3D(0, 5, 5))
    pts_2 = (Point3D(0, 5, 5), Point3D(10, 5, 5), Point3D(10, 10, 0), Point3D(0, 10, 0))
    pts_3 = (Point3D(0, 0, 0), Point3D(10, 0, 0), Point3D(10, -5, 0), Point3D(0, -5, 0))
    roof = RoofSpecification([Face3D(pts_1), Face3D(pts_2), Face3D(pts_3)])

    roof_area = sum(rg.area for rg in roof.geometry)

    split_poly = Polygon2D((Point2D(3, 3), Point2D(7, 3), Point2D(7, 7), Point2D(3, 7)))
    roof.split_with_polygon(split_poly, tolerance=0.01)

    assert len(roof) == 5
    assert sum(rg.area for rg in roof.geometry) == pytest.approx(roof_area, abs=1e-3)


def test_split_with_lines():
    """Test the RoofSpecification split_with_lines method."""
    pts = (Point3D(0., 5., 5.), Point3D(10., 5., 5.), Point3D(10., 10., 0.), Point3D(0., 10., 0.))
    face = Face3D(pts)
    split_line = LineSegment3D.from_end_points(Point3D(5., 3., 7.), Point3D(5., 12., -2.))
    face.split_with_line(split_line, 0.01)

    pts_1 = (Point3D(0, 0, 0), Point3D(10, 0, 0), Point3D(10, 5, 5), Point3D(0, 5, 5))
    pts_2 = (Point3D(0, 5, 5), Point3D(10, 5, 5), Point3D(10, 10, 0), Point3D(0, 10, 0))
    pts_3 = (Point3D(0, 0, 0), Point3D(10, 0, 0), Point3D(10, -5, 0), Point3D(0, -5, 0))
    roof = RoofSpecification([Face3D(pts_1), Face3D(pts_2), Face3D(pts_3)])

    roof_area = sum(rg.area for rg in roof.geometry)

    split_line_1 = LineSegment2D.from_end_points(Point2D(5, 3), Point2D(5, 12))
    split_line_2 = LineSegment2D.from_end_points(Point2D(-1, 3), Point2D(11, 3))
    roof.split_with_lines([split_line_1, split_line_2], tolerance=0.01)

    assert len(roof) == 6
    assert sum(rg.area for rg in roof.geometry) == pytest.approx(roof_area, abs=1e-3)


def test_split_with_line():
    """Test another case of RoofSpecification split_with_lines method."""
    in_roof = {
        "type": "RoofSpecification",
        "geometry": [
            {
                "type": "Face3D",
                "boundary": [
                    [7.0619315174376345, -3.4035939785815463, 2.2000000000000837],
                    [13.061931517437632, -3.4035939785815463, 2.2000000000000837],
                    [13.061931517437632, -15.201593978581808, 2.2000000000000837],
                    [7.0619315174376345, -15.201593978581808, 2.2000000000000837]
                ]
            }
        ]
    }
    roof = RoofSpecification.from_dict(in_roof)
    split_line_array = [[16.26167736358605, -11.045644087390255],
                        [5.753788558176589, -7.5595438697731]]
    split_line = LineSegment2D.from_array(split_line_array)

    assert len(roof.geometry) == 1
    roof.split_with_lines([split_line])
    assert len(roof.geometry) == 2


def test_endless_loop_resolved_geometry():
    """Test the resolved_geometry method with a roof causing an endless loop."""
    test_json = './tests/json/endless_roof.json'
    with open(test_json) as json_file:
        data = json.load(json_file)
    roof = RoofSpecification.from_dict(data)
    assert len(roof.resolved_geometry(0.003)) >= 5
