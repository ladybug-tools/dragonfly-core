# coding: utf-8
"""A series of utility functions that are useful across several dragonfly extensions."""
from __future__ import division


def model_extension_dicts(data, extension_key, building_ext_dicts, story_ext_dicts,
                          room2d_ext_dicts, context_shade_ext_dicts):
    """Get all Model property dictionaries of an extension organized by geometry type.

    Note that the order in which dictionaries appear in the output lists is the
    same order as the geometry objects appear when requested from the model.
    For example, the shade_ext_dicts align with the model.shades.

    Args:
        data: A dictionary representation of an entire honeybee-core Model.
        extension_key: Text for the key of the extension (eg. "energy", "radiance").

    Returns:
        A tuple with four elements

        -   building_ext_dicts: A list of Building extension property dictionaries that
            align with the serialized model.buildings.

        -   story_ext_dicts: A list of Story extension property dictionaries that
            align with the serialized model.stories.

        -   room2d_ext_dicts: A list of Room2D extension property dictionaries that
            align with the serialized model.rooms.

        -   context_shade_ext_dicts: A list of ContextShade extension property
            dictionaries that align with the serialized model.context_shades.
    """
    assert data['type'] == 'Model', \
        'Expected Model dictionary. Got {}.'.format(data['type'])

    # loop through the model dictionary using the same logic that the
    # model does when you request buildings, stories, room_2ds, and context_shades.
    if 'buildings' in data:
        building_extension_dicts(data['buildings'], extension_key, building_ext_dicts,
                                 story_ext_dicts, room2d_ext_dicts)
    if 'context_shades' in data:
        context_shade_extension_dicts(data['context_shades'], extension_key,
                                      context_shade_ext_dicts)

    return building_ext_dicts, story_ext_dicts, room2d_ext_dicts, context_shade_ext_dicts


def building_extension_dicts(building_list, extension_key, building_ext_dicts,
                             story_ext_dicts, room2d_ext_dicts):
    """Get all Building property dictionaires of an extension organized by geometry type.

    Args:
        building_list: A list of Building dictionaries.
        extension_key: Text for the key of the extension (eg. "energy", "radiance").

    Returns:
        A tuple with three elements

        -   building_ext_dicts: A list with the Building extension property dictionaries.

        -   story_ext_dicts: A list with Story extension property dictionaries.

        -   room2d_ext_dicts: A list with Room2D extension property dictionaries.
    """
    for bldg_dict in building_list:
        try:
            building_ext_dicts.append(bldg_dict['properties'][extension_key])
        except KeyError:
            building_ext_dicts.append(None)
        story_extension_dicts(bldg_dict['unique_stories'], extension_key,
                              story_ext_dicts, room2d_ext_dicts)
    return building_ext_dicts, story_ext_dicts, room2d_ext_dicts


def story_extension_dicts(story_list, extension_key, story_ext_dicts,
                          room2d_ext_dicts):
    """Get all Building property dictionaires of an extension organized by geometry type.

    Args:
        building_list: A list of Building dictionaries.
        extension_key: Text for the key of the extension (eg. "energy", "radiance").

    Returns:
        A tuple with two elements

        -   story_ext_dicts: A list with Story extension property dictionaries.

        -   room2d_ext_dicts: A list with Room2D extension property dictionaries.
    """
    for story_dict in story_list:
        try:
            story_ext_dicts.append(story_dict['properties'][extension_key])
        except KeyError:
            story_ext_dicts.append(None)
        room2d_extension_dicts(story_dict['room_2ds'], extension_key,
                               room2d_ext_dicts)
    return story_ext_dicts, room2d_ext_dicts


def room2d_extension_dicts(room2d_list, extension_key, room2d_ext_dicts):
    """Get all Room2D property dictionaires of an extension.

    Args:
        room2d_list: A list of Room2D dictionaries.
        extension_key: Text for the key of the extension (eg. "energy", "radiance").

    Returns:
        room2d_ext_dict -- A list with Room2D extension property dictionaries.
    """
    for room_dict in room2d_list:
        try:
            room2d_ext_dicts.append(room_dict['properties'][extension_key])
        except KeyError:
            room2d_ext_dicts.append(None)
    return room2d_ext_dicts


def context_shade_extension_dicts(context_shade_list, extension_key,
                                  context_shade_ext_dicts):
    """Get all ContextShade property dictionaires of an extension.

    Args:
        context_shade_list: A list of ContextShade dictionaries.
        extension_key: Text for the key of the extension (eg. "energy", "radiance").

    Returns:
        context_shade_ext_dicts -- A list with ContextShade extension property
        dictionaries.
    """
    for shd_dict in context_shade_list:
        try:
            context_shade_ext_dicts.append(shd_dict['properties'][extension_key])
        except KeyError:
            context_shade_ext_dicts.append(None)
    return context_shade_ext_dicts
