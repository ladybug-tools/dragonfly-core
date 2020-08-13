# coding=utf-8
"""Utilities to convertint any dictionary to Python objects.

Note that importing this module will import almost all modules within the
library in order to be able to re-serialize almost any dictionary produced
from the library.
"""
from dragonfly.model import Model
from dragonfly.building import Building
from dragonfly.story import Story
from dragonfly.room2d import Room2D
from dragonfly.context import ContextShade
import dragonfly.windowparameter as dfw
import dragonfly.shadingparameter as dfs

import honeybee.boundarycondition as hbc


def dict_to_object(dragonfly_dict, raise_exception=True):
    """Re-serialize a dictionary of almost any object within dragonfly.

    This includes any Model, Building, Story, Room2D, WindowParameter,
    ShadingParameter, and boundary conditions.

    Args:
        dragonfly_dict: A dictionary of any Dragonfly object. Note
            that this should be a non-abridged dictionary to be valid.
        raise_exception: Boolean to note whether an excpetion should be raised
            if the object is not identified as a part of dragonfly.
            Default: True.

    Returns:
        A Python object derived from the input dragonfly_dict.
    """
    try:  # get the type key from the dictionary
        obj_type = dragonfly_dict['type']
    except KeyError:
        raise ValueError('Dragonfly dictionary lacks required "type" key.')

    if obj_type == 'Model':
        return Model.from_dict(dragonfly_dict)
    elif obj_type == 'Building':
        return Building.from_dict(dragonfly_dict)
    elif obj_type == 'Story':
        return Story.from_dict(dragonfly_dict)
    elif obj_type == 'Room2D':
        return Room2D.from_dict(dragonfly_dict)
    elif obj_type == 'ContextShade':
        return ContextShade.from_dict(dragonfly_dict)
    elif hasattr(dfw, obj_type):
        win_class = getattr(dfw, obj_type)
        return win_class.from_dict(dragonfly_dict)
    elif hasattr(dfs, obj_type):
        shd_class = getattr(dfs, obj_type)
        return shd_class.from_dict(dragonfly_dict)
    elif hasattr(hbc, obj_type):
        bc_class = getattr(hbc, obj_type)
        return bc_class.from_dict(dragonfly_dict)
    elif raise_exception:
        raise ValueError('{} is not a recognized dragonfly object'.format(obj_type))
