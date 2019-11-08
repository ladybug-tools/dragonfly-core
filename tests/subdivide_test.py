# coding=utf-8
from dragonfly.subdivide import interpret_floor_height_subdivide, \
    interpret_core_perimeter_subdivide


def test_interpret_floor_height_subdivide():
    """Test the interpret_floor_height_subdivide method."""
    test_1 = [5]
    test_2 = [5, 3]
    test_3 = [5, "@3"]
    test_4 = ["2@4"]
    test_5 = ["@3"]
    test_6 = ["1@5", "2@4", "@3"]

    assert interpret_floor_height_subdivide(test_1, 5)[0] == [0]
    assert interpret_floor_height_subdivide(test_1, 15)[0] == [0, 5]
    assert interpret_floor_height_subdivide(test_2, 15)[0] == [0, 5, 8]
    assert interpret_floor_height_subdivide(test_3, 17)[0] == [0, 5, 8, 11, 14]
    assert interpret_floor_height_subdivide(test_4, 17)[0] == [0, 4, 8]
    assert interpret_floor_height_subdivide(test_5, 15)[0] == [0, 3, 6, 9, 12]
    assert interpret_floor_height_subdivide(test_6, 25)[0] == [0, 5, 9, 13, 16, 19, 22]

    assert interpret_floor_height_subdivide(test_1, 5)[1] == [5]
    assert interpret_floor_height_subdivide(test_1, 15)[1] == [5, 10]
    assert interpret_floor_height_subdivide(test_2, 15)[1] == [5, 3, 7]
    assert interpret_floor_height_subdivide(test_3, 17)[1] == [5, 3, 3, 3, 3]
    assert interpret_floor_height_subdivide(test_4, 17)[1] == [4, 4, 9]
    assert interpret_floor_height_subdivide(test_5, 15)[1] == [3, 3, 3, 3, 3]
    assert interpret_floor_height_subdivide(test_6, 25)[1] == [5, 4, 4, 3, 3, 3, 3]


def test_interpret_floor_height_subdivide_odd_last_floor():
    """Test the interpret_floor_height_subdivide method with a short last floor."""
    test = ["1@5", "2@4", "@3"]

    assert interpret_floor_height_subdivide(test, 23)[0] == [0, 5, 9, 13, 16, 19]
    assert interpret_floor_height_subdivide(test, 23)[1] == [5, 4, 4, 3, 3, 4]


def test_interpret_core_perimeter_subdivide():
    """Test the interpret_core_perimeter_subdivide method."""
    test_1 = [5]
    test_2 = [5, 3]
    test_3 = [5, "@3"]
    test_4 = ["2@4"]
    test_5 = ["@3"]
    test_6 = ["1@5", "2@4", "@3"]

    assert interpret_core_perimeter_subdivide(test_1, 1) == [5]
    assert interpret_core_perimeter_subdivide(test_1, 2) == [5, 5]
    assert interpret_core_perimeter_subdivide(test_2, 3) == [5, 3, 3]
    assert interpret_core_perimeter_subdivide(test_3, 5) == [5, 3, 3, 3, 3]
    assert interpret_core_perimeter_subdivide(test_4, 2) == [4, 4]
    assert interpret_core_perimeter_subdivide(test_5, 3) == [3, 3, 3]
    assert interpret_core_perimeter_subdivide(test_6, 8) == [5, 4, 4, 3, 3, 3, 3, 3]
