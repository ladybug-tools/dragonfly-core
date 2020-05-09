"""Test dictutil module."""
from dragonfly.dictutil import dict_to_object
from dragonfly.model import Model
from dragonfly.building import Building
from dragonfly.story import Story
from dragonfly.room2d import Room2D
from dragonfly.context import ContextShade
from dragonfly.windowparameter import SingleWindow, SimpleWindowRatio, \
    RepeatingWindowRatio, RepeatingWindowWidthHeight, RectangularWindows, \
    DetailedWindows
from dragonfly.shadingparameter import ExtrudedBorder, Overhang, LouversByDistance, \
    LouversByCount

from ladybug.location import Location
from ladybug_geometry.geometry2d.pointvector import Point2D, Vector2D
from ladybug_geometry.geometry2d.polygon import Polygon2D
from ladybug_geometry.geometry3d.pointvector import Point3D, Vector3D
from ladybug_geometry.geometry3d.plane import Plane
from ladybug_geometry.geometry3d.face import Face3D

import pytest


def test_dict_to_object():
    """Test the dict_to_object method with all geometry objects."""
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

    tree_canopy_geo1 = Face3D.from_regular_polygon(6, 6, Plane(o=Point3D(5, -10, 6)))
    tree_canopy_geo2 = Face3D.from_regular_polygon(6, 2, Plane(o=Point3D(-5, -10, 3)))
    tree_canopy = ContextShade('Tree_Canopy', [tree_canopy_geo1, tree_canopy_geo2])

    model = Model('New_Development', [building], [tree_canopy])

    model_dict = model.to_dict()
    room_dict = room2d_1.to_dict()
    story_dict = story.to_dict()
    building_dict = building.to_dict()

    assert isinstance(dict_to_object(model_dict), Model)
    assert isinstance(dict_to_object(room_dict), Room2D)
    assert isinstance(dict_to_object(story_dict), Story)
    assert isinstance(dict_to_object(building_dict), Building)


def test_dict_to_object_win_par():
    """Test the dict_to_object method with window parameters."""
    simple_window = SingleWindow(5, 2, 0.8)
    ashrae_base1 = SimpleWindowRatio(0.4)
    ashrae_base2 = RepeatingWindowRatio(0.4, 2, 0.8, 3)
    bod_windows = RepeatingWindowWidthHeight(2, 1.5, 0.8, 3)

    origins = (Point2D(2, 1), Point2D(5, 0.5))
    widths = (1, 3)
    heights = (1, 2)
    detailed_window1 = RectangularWindows(origins, widths, heights)

    pts_1 = (Point2D(2, 1), Point2D(3, 1), Point2D(3, 2), Point2D(2, 2))
    pts_2 = (Point2D(5, 0.5), Point2D(8, 0.5), Point2D(8, 2.5), Point2D(5, 2.5))
    detailed_window2 = DetailedWindows((Polygon2D(pts_1), Polygon2D(pts_2)))

    assert isinstance(dict_to_object(simple_window.to_dict()), SingleWindow)
    assert isinstance(dict_to_object(ashrae_base1.to_dict()), SimpleWindowRatio)
    assert isinstance(dict_to_object(ashrae_base2.to_dict()), RepeatingWindowRatio)
    assert isinstance(dict_to_object(bod_windows.to_dict()), RepeatingWindowWidthHeight)
    assert isinstance(dict_to_object(detailed_window1.to_dict()), RectangularWindows)
    assert isinstance(dict_to_object(detailed_window2.to_dict()), DetailedWindows)


def test_dict_to_object_shd_par():
    """Test the dict_to_object method with shading parameters."""
    simple_border = ExtrudedBorder(0.3)
    simple_awning = Overhang(2, 10)
    louvers1 = LouversByDistance(0.5, 0.3, 1, 30)
    louvers2 = LouversByCount(3, 0.3, 1, 30)

    assert isinstance(dict_to_object(simple_border.to_dict()), ExtrudedBorder)
    assert isinstance(dict_to_object(simple_awning.to_dict()), Overhang)
    assert isinstance(dict_to_object(louvers1.to_dict()), LouversByDistance)
    assert isinstance(dict_to_object(louvers2.to_dict()), LouversByCount)
