from dragonfly.context import ContextShade

from honeybee.shade import Shade

from ladybug_geometry.geometry2d import Point2D, LineSegment2D
from ladybug_geometry.geometry3d import Point3D, Vector3D, Plane, Face3D, \
    Mesh3D, Polyface3D

import pytest


def test_context_shade_init():
    """Test the initialization of ContextShade objects."""
    tree_canopy_geo1 = Face3D.from_regular_polygon(6, 6, Plane(o=Point3D(5, -10, 6)))
    tree_canopy_geo2 = Face3D.from_regular_polygon(6, 2, Plane(o=Point3D(-5, -10, 3)))
    tree_canopy = ContextShade('Tree_Canopy', [tree_canopy_geo1, tree_canopy_geo2])
    str(tree_canopy)  # test the string representation

    assert tree_canopy.identifier == 'Tree_Canopy'
    assert tree_canopy.display_name == 'Tree_Canopy'
    assert len(tree_canopy) == len(tree_canopy.geometry) == 2
    for geo in tree_canopy:
        assert isinstance(geo, Face3D)
    assert len(tree_canopy[0].vertices) == 6


def test_context_shade_min_max():
    """Test the min and max properties of ContextShade objects."""
    awning_geo1 = Face3D.from_rectangle(6, 6, Plane(o=Point3D(5, -10, 6)))
    awning_geo2 = Face3D.from_rectangle(2, 2, Plane(o=Point3D(-5, -10, 3)))
    awning_canopy = ContextShade('Awning_Canopy', [awning_geo1, awning_geo2])

    assert awning_canopy.area == 40
    assert awning_canopy.min == Point2D(-5, -10)
    assert awning_canopy.max == Point2D(11, -4)


def test_move():
    """Test the ContextShade move method."""
    pts_1 = (Point3D(0, 2, 3), Point3D(2, 2, 3), Point3D(2, 0, 3), Point3D(0, 0, 3))
    plane_1 = Plane(Vector3D(0, 0, 1), Point3D(0, 0, 0))
    awning_canopy = ContextShade('Awning_Canopy', [Face3D(pts_1, plane_1)])

    vec_1 = Vector3D(2, 2, 2)
    new_a = awning_canopy.duplicate()
    new_a.move(vec_1)
    assert new_a[0][0] == Point3D(2, 2, 5)
    assert new_a[0][1] == Point3D(4, 2, 5)
    assert new_a[0][2] == Point3D(4, 4, 5)
    assert new_a[0][3] == Point3D(2, 4, 5)
    assert awning_canopy.area == new_a.area


def test_scale():
    """Test the ContextShade scale method."""
    pts = (Point3D(1, 1, 2), Point3D(2, 1, 2), Point3D(2, 2, 2), Point3D(1, 2, 2))
    plane_1 = Plane(Vector3D(0, 0, 1), Point3D(0, 0, 0))
    awning_canopy = ContextShade('Awning_Canopy', [Face3D(pts, plane_1)])

    new_a = awning_canopy.duplicate()
    new_a.scale(2)
    assert new_a[0][0] == Point3D(2, 2, 4)
    assert new_a[0][1] == Point3D(4, 2, 4)
    assert new_a[0][2] == Point3D(4, 4, 4)
    assert new_a[0][3] == Point3D(2, 4, 4)
    assert new_a.area == awning_canopy.area * 2 ** 2


def test_rotate_xy():
    """Test the ContextShade rotate_xy method."""
    pts = (Point3D(1, 1, 2), Point3D(2, 1, 2), Point3D(2, 2, 2), Point3D(1, 2, 2))
    plane = Plane(Vector3D(0, 0, 1), Point3D(0, 0, 2))
    awning_canopy = ContextShade('Awning_Canopy', [Face3D(pts, plane)])
    origin_1 = Point3D(1, 1, 0)

    test_1 = awning_canopy.duplicate()
    test_1.rotate_xy(180, origin_1)
    assert test_1[0][0].x == pytest.approx(1, rel=1e-3)
    assert test_1[0][0].y == pytest.approx(1, rel=1e-3)
    assert test_1[0][0].z == pytest.approx(2, rel=1e-3)
    assert test_1[0][2].x == pytest.approx(0, rel=1e-3)
    assert test_1[0][2].y == pytest.approx(0, rel=1e-3)
    assert test_1[0][2].z == pytest.approx(2, rel=1e-3)


def test_reflect():
    """Test the ContextShade reflect method."""
    pts = (Point3D(1, 1, 2), Point3D(2, 1, 2), Point3D(2, 2, 2), Point3D(1, 2, 2))
    plane = Plane(Vector3D(0, 0, 1), Point3D(0, 0, 2))
    awning_canopy = ContextShade('Awning_Canopy', [Face3D(pts, plane)])

    origin_1 = Point3D(1, 0, 2)
    normal_1 = Vector3D(1, 0, 0)
    plane_1 = Plane(normal_1, origin_1)

    test_1 = awning_canopy.duplicate()
    test_1.reflect(plane_1)
    assert test_1[0][-1].x == pytest.approx(1, rel=1e-3)
    assert test_1[0][-1].y == pytest.approx(1, rel=1e-3)
    assert test_1[0][-1].z == pytest.approx(2, rel=1e-3)
    assert test_1[0][1].x == pytest.approx(0, rel=1e-3)
    assert test_1[0][1].y == pytest.approx(2, rel=1e-3)
    assert test_1[0][1].z == pytest.approx(2, rel=1e-3)


def test_snap_to_grid():
    """Test the ContextShade snap_to_grid method."""
    pts1 = (Point3D(1.1, 1.1, 4), Point3D(2.1, 1.1, 4), Point3D(2.1, 2.1, 4), Point3D(1.1, 2.1, 4))
    plane = Plane(Vector3D(0, 0, 1), Point3D(0, 0, 2))
    face = Face3D(pts1, plane)
    pts2 = (Point3D(0, 0, 2), Point3D(0, 2.1, 2), Point3D(2.1, 2.1, 2),
            Point3D(2.1, 0, 2), Point3D(4.1, 0, 2))
    mesh = Mesh3D(pts2, [(0, 1, 2, 3), (2, 3, 4)])
    awning_canopy = ContextShade('Awning_Canopy', [face, mesh])
    assert not awning_canopy.is_conforming(Plane())

    awning_canopy.snap_to_grid(1.0, None)
    assert awning_canopy[0].vertices != pts1


def test_align():
    """Test the ContextShade align method."""
    shade_box = Polyface3D.from_box(2, 2, 0.5, Plane(o=Point3D(0, 0, 3)))
    awning_canopy = ContextShade('Awning_Canopy', shade_box.faces)
    assert awning_canopy.is_conforming(Plane())

    align_line = LineSegment2D.from_end_points(Point2D(2.1, -1), Point2D(2.1, 3))
    new_awning = awning_canopy.duplicate()
    new_awning.align(align_line, 0.2, 0.01)
    assert new_awning.area > awning_canopy.area


def test_to_honeybee():
    """Test the to_honeybee method."""
    tree_canopy_geo1 = Face3D.from_regular_polygon(6, 6, Plane(o=Point3D(5, -10, 6)))
    tree_canopy_geo2 = Face3D.from_regular_polygon(6, 2, Plane(o=Point3D(-5, -10, 3)))
    tree_canopy = ContextShade('Tree_Canopy', [tree_canopy_geo1, tree_canopy_geo2])
    hb_tree_canopies = tree_canopy.to_honeybee()

    assert len(hb_tree_canopies) == 2
    for shd in hb_tree_canopies:
        assert isinstance(shd, Shade)
        assert shd.identifier.startswith('Tree_Canopy')
    assert hb_tree_canopies[0].identifier != hb_tree_canopies[1].identifier
    assert tree_canopy.area == sum([shd.area for shd in hb_tree_canopies])


def test_to_dict():
    """Test the ContextShade to_dict method."""
    tree_canopy_geo1 = Face3D.from_regular_polygon(6, 6, Plane(o=Point3D(5, -10, 6)))
    tree_canopy_geo2 = Face3D.from_regular_polygon(6, 2, Plane(o=Point3D(-5, -10, 3)))
    tree_canopy = ContextShade('Tree_Canopy', [tree_canopy_geo1, tree_canopy_geo2])

    sd = tree_canopy.to_dict()
    assert sd['type'] == 'ContextShade'
    assert sd['identifier'] == 'Tree_Canopy'
    assert sd['display_name'] == 'Tree_Canopy'
    assert len(sd['geometry']) == 2


def test_to_from_dict():
    """Test the to/from dict of ContextShade objects."""
    tree_canopy_geo1 = Face3D.from_regular_polygon(6, 6, Plane(o=Point3D(5, -10, 6)))
    tree_canopy_geo2 = Face3D.from_regular_polygon(6, 2, Plane(o=Point3D(-5, -10, 3)))
    tree_canopy = ContextShade('Tree_Canopy', [tree_canopy_geo1, tree_canopy_geo2])

    context_dict = tree_canopy.to_dict()
    new_context = ContextShade.from_dict(context_dict)
    assert isinstance(new_context, ContextShade)
    assert new_context.to_dict() == context_dict


def test_from_dict_invalid():
    """Test the from dict of ContextShade objects with invalid dictionaries."""
    pts1 = (Point3D(1.1, 1.1, 4), Point3D(2.1, 1.1, 4), Point3D(2.1, 2.1, 4),
            Point3D(1.1, 2.1, 4))
    plane = Plane(Vector3D(0, 0, 1), Point3D(0, 0, 2))
    face = Face3D(pts1, plane)
    pts2 = (Point3D(0, 0, 2), Point3D(0, 2.1, 2), Point3D(2.1, 2.1, 2),
            Point3D(2.1, 0, 2), Point3D(4.1, 0, 2))
    mesh = Mesh3D(pts2, [(0, 1, 2, 3), (2, 3, 4)])
    awning_canopy = ContextShade('Awning_Canopy', [face, mesh])

    context_dict = awning_canopy.to_dict()
    new_context = ContextShade.from_dict(context_dict)
    assert isinstance(new_context, ContextShade)
    assert new_context.to_dict() == context_dict
    assert len(new_context.geometry) == 2

    context_dict['geometry'][1]['faces'] = []
    new_context = ContextShade.from_dict(context_dict)
    assert len(new_context.geometry) == 1

    context_dict['geometry'][0]['boundary'] = [pts1[0].to_array(), pts1[1].to_array()]
    with pytest.raises(ValueError):
        new_context = ContextShade.from_dict(context_dict)


def test_writer():
    """Test the Building writer object."""
    tree_canopy_geo1 = Face3D.from_regular_polygon(6, 6, Plane(o=Point3D(5, -10, 6)))
    tree_canopy_geo2 = Face3D.from_regular_polygon(6, 2, Plane(o=Point3D(-5, -10, 3)))
    tree_canopy = ContextShade('Tree_Canopy', [tree_canopy_geo1, tree_canopy_geo2])

    writers = [mod for mod in dir(tree_canopy.to) if not mod.startswith('_')]
    for writer in writers:
        assert callable(getattr(tree_canopy.to, writer))
