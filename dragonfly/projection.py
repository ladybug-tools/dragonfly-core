"""Utilities for converting X,Y coordinates in meters to longitude, latitude."""
from __future__ import division

import math

def meters_to_long_lat_factors(origin_lon_lat=(0, 0)):
    """Get conversion factors for translating meters to longitude, latitude.

    The resulting factors should obey the WSG84 assumptions for the radius of
    the earth at the equator relative to the poles.

    Args:
        origin_long_lat: An array of two numbers in degrees. The first value
            represents the longitude of the scene origin in degrees (between -180
            and +180). The second value represents latitude of the scene origin
            in degrees (between -90 and +90). Default: (0, 0).

    Returns:
        A tuple with two values:

        meters_to_lon -- conversion factor for changing meters to degrees longitude.

        meters_to_lat -- conversion factor for changing meters to degrees latitude.
    """
    # constants of the WSG84 system
    equator_rad = 6378137.0  # radius of the earth at the equator (meters)
    pole_rad = 6356752.314  # radius of the earth at the poles (meters)

    # convert everything to radians
    lon, lat = math.radians(origin_lon_lat[0]), math.radians(origin_lon_lat[1])

    # compute the conversion values
    d = math.sqrt(
        (equator_rad ** 2 * math.sin(lat) ** 2) + (pole_rad ** 2 * math.cos(lat) ** 2))
    r = (equator_rad * pole_rad) / d  # radius of the earth at the latitude
    meters_to_lat = (math.pi * r * 2) / 360  # meters in one degree of latitude
    meters_to_lon = meters_to_lat * math.cos(lat)  # meters in one degree of longitude

    return meters_to_lon, meters_to_lat


def polygon_to_lon_lat(polygon, origin_lon_lat=(0, 0), conversion_factors=None):
    """Get an array of (longitude, latitude) from a ladybug_geometry Polygon2D in meters.

    The resulting coordinates should obey the WSG84 assumptions for the radius of
    the earth at the equator relative to the poles.
    Note that this function uses a simple formula and some distortion is possible
    when translating polygons several kilometers long.

    Args:
        polygon: An array of (X, Y) values for coordinates in meters.
        origin_lon_lat: An array of two numbers in degrees. The first value
            represents the longitude of the scene origin in degrees (between -180
            and +180). The second value represents latitude of the scene origin
            in degrees (between -90 and +90). Note that the "scene origin" is the
            (0, 0) coordinate in the 2D space of the input polygon. Default: (0, 0).
        conversion_factors: A tuple with two values used to translate between
            meters and longitude, latitude. If None, these values will be automatically
            calculated from the origin_lon_lat using the meters_to_long_lat_factors
            method.

    Returns:
        A nested array with each sub-array having 2 values for the
        (longitude, latitude) of each polygon vertex.
    """
    # unpack or autocalculate the conversion factors
    if not conversion_factors:
        meters_to_lon, meters_to_lat = meters_to_long_lat_factors(origin_lon_lat)
    else:
        meters_to_lon, meters_to_lat = conversion_factors

    # get the longitude, latitude values for the polygon
    return [(origin_lon_lat[0] + pt[0] / meters_to_lon,
             origin_lon_lat[1] + pt[1] / meters_to_lat) for pt in polygon]


def lon_lat_to_polygon(polygon_lon_lat_coords, origin_lon_lat=(0, 0),
                       conversion_factors=None):
    """Convert an array of (longitude, latitude) coordinates to (X, Y) coordinates in meters.

    The resulting coordinates will obey the WSG84 assumptions for the radius of
    the earth at the equator relative to the poles.
    Note that this function uses a simple formula and some distortion is possible
    when translating polygons several kilometers long.

    Args:
        polygon_lon_lat_coords: A nested array with each sub-array having 2 values for
            the (longitude, latitude) of a polygon boundary.
        origin_lon_lat: An array of two numbers in degrees. The first value
            represents the longitude of the scene origin in degrees (between -180
            and +180). The second value represents latitude of the scene origin
            in degrees (between -90 and +90). Note that the "scene origin" is the
            (0, 0) coordinate in the 2D space of the input polygon. Default: (0, 0).
        conversion_factors: A tuple with two values used to translate between
            longitude, latitude and meters. If None, these values will be automatically
            calculated from the origin_lon_lat using the inverse of the
            factors computed from the meters_to_long_lat_factors method.
    Returns:
        An array of (X, Y) values for the boundary coordinates in meters.
    """

    # Unpack or autocalculate the conversion factors
    if not conversion_factors:
        meters_to_lon, meters_to_lat = meters_to_long_lat_factors(origin_lon_lat)
        lon_to_meters, lat_to_meters = 1.0 / meters_to_lon, 1.0 / meters_to_lat
    else:
        lon_to_meters, lat_to_meters = conversion_factors

    # Get the (X, Y) values for the boundary in meters
    return [((pt[0] - origin_lon_lat[0]) / lon_to_meters,
             (pt[1] - origin_lon_lat[1]) / lat_to_meters)
            for pt in polygon_lon_lat_coords]


def origin_long_lat_from_location(location, point):
    """Get the (longitude, latitude) of the scene origin from a location and a point.

    Args:
        location: A ladybug Location object possessing longitude and latitude data.
        point: A ladybug_geometry Point2D for where the location object exists
            within the space of a scene. The coordinates of this point are expected
            to be in meters.

    Returns:
        An array of two numbers in degrees. The first value represents the longitude
        of the scene origin in degrees (between -180 and +180). The second value
        represents latitude of the scene origin in degrees (between -90 and +90).
    """
    meters_to_lon, meters_to_lat = meters_to_long_lat_factors(
        (location.longitude, location.latitude))
    return location.longitude - point.x / meters_to_lon, \
        location.latitude - point.y / meters_to_lat

