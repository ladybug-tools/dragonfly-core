"""Utilities to interpret parameters for subdividing building masses."""
from __future__ import division


def interpret_floor_height_subdivide(floor_to_floor_heights, max_height,
                                     first_floor_height=0):
    """Interpret a list of instructions for subdividing a building mass into floors.

    Args:
        floor_to_floor_heights: An array of floor-to-floor height instructions
            that describe how a building mass should be divided into floors.
            The array should run from bottom floor to top floor.
            Each item in the array can be either a single number for the
            floor-to-floor height or a text string that codes for how many
            floors of each height should be generated.  For example, inputting
            "2@4" will make two floors with a height of 4 units. Simply inputting
            "@3" will make all floors at 3 units.  Putting in sequential arrays
            of these text strings will divide up floors accordingly.  For example,
            the list ["1@5", "2@4", "@3"]  will make a ground floor of 5 units,
            two floors above that at 4 units and all remaining floors at 3 units.
        max_height: The maximum height of the building, noting the z-value
            above which no new floor heights should be generated.
        first_floor_height: The z-value of the first floor.

    Returns:
        A tuple with two elements

        -   floor_heights -- An array of float values for the floor heights, which
            can be used to generate planes that subdivide a building mass.

        -   interpreted_f2f -- An array of float values noting the distance between
            each floor. Note that, unlike the input floor_to_floor_heights,
            this array always has float values and is the same length as the
            floor_heights.
    """
    # generate the list of height float values
    floor_heights = [first_floor_height]
    interpreted_f2f = []
    for height in floor_to_floor_heights:
        try:  # single number for the floor
            flr_h = float(height)
            flr_count = 1
        except (TypeError, ValueError):  # instructions for generating floors
            flr_h = float(height.split('@')[1])
            try:
                flr_count = int(height.split('@')[0])
            except ValueError:  # no number of floors to generate (ie. '@3')
                flr_count = int((max_height - floor_heights[-1]) / flr_h)

        if flr_h != 0:
            for _ in range(flr_count):
                floor_heights.append(floor_heights[-1] + flr_h)
                interpreted_f2f.append(flr_h)

    # check to be sure no heights are above the max height
    if floor_heights[-1] >= max_height:
        floor_heights = [hgt for hgt in floor_heights if hgt < max_height]
        interpreted_f2f = [interpreted_f2f[i] for i in range(len(floor_heights))]

    # remove last height if the difference between it and max height is too small
    if len(floor_heights) != 1 and \
            max_height - floor_heights[-1] < interpreted_f2f[-1] - 1e-9:
        del floor_heights[-1]
        del interpreted_f2f[-1]
        interpreted_f2f.append(max_height - floor_heights[-1])
    elif len(interpreted_f2f) < len(floor_heights):
        interpreted_f2f.append(max_height - floor_heights[-1])

    return floor_heights, interpreted_f2f


def interpret_core_perimeter_subdivide(perimeter_depths, floor_count):
    """Interpret a list of instructions for subdividing a building mass into floors.

    Args:
        perimeter_depths: An array of perimeter depth instructions that describe
            how a building floors should be divided into core/perimeter Rooms.
            The array should run from bottom floor to top floor.
            Each item in the array can be either a single number for the perimeter
            depth or a text string that codes for over how many floors a given
            perimeter depth should be applies.  For example, inputting
            "2@4" will offset the first 2 floors 4 units. Simply inputting
            "@3" will make all floors offset at 3 units.  Putting in sequential arrays
            of these text strings will offset floors accordingly.  For example,
            the list ["1@5", "2@4", "@3"]  will offset the ground floor at 5 units,
            two floors above that at 4 units and all remaining floors at 3 units.
        floor_count: An integer for the number of floors within the building. The
            array output from this function will have a length equal to this number.

    Returns:
        An array of float values for perimeter depths, which can be used to offset
        perimeters over a building's stories.
    """
    # generate the list of depth float values
    interpreted_depths = []
    for depth in perimeter_depths:
        try:  # single number for the floor
            flr_d = float(depth)
            flr_count = 1
        except (TypeError, ValueError):  # instructions for generating depths
            flr_d = float(depth.split('@')[1])
            try:
                flr_count = int(depth.split('@')[0])
            except ValueError:  # no number of depths to generate (ie. '@3')
                flr_count = int(floor_count - len(interpreted_depths))

        for _ in range(flr_count):
            interpreted_depths.append(flr_d)

    # check to be sure the length of the list is correct
    if len(interpreted_depths) > floor_count:  # cut the list short
        interpreted_depths = [interpreted_depths[i] for i in range(floor_count)]
    elif len(interpreted_depths) < floor_count:  # repeat last floor
        interpreted_depths.extend([interpreted_depths[-1] for i in
                                   range(floor_count - len(interpreted_depths))])

    return interpreted_depths
