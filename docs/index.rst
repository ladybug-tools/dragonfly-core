Welcome to Dragonfly's documentation!
=========================================

.. image:: http://www.ladybug.tools/assets/img/dragonfly.png

Dragonfly is a collection of Python libraries to create representations of buildings
following `dragonfly-schema <https://github.com/ladybug-tools/dragonfly-schema/wiki>`_.
It abstracts the capabilities of `honeybee-core <https://github.com/ladybug-tools/honeybee-core/>`_
to make it easier to construct models on the urban scale.


Installation
============

To install the core library use ``pip install -U dragonfly-core``.

To check if the Dragonfly command line interface is installed correctly use ``dragonfly viz`` and you
should get a ``viiiiiiiiiiiiizzzzzzzzz!`` back in response!


Documentation
=============

This document includes `Dragonfly API documentation <#dragonfly>`_ and 
`Dragonfly Command Line Interface <#id1>`_ documentation for ``dragonfly core`` and does
not include the documentation for dragonfly extensions. For each extension refer to
extension's documentation page.

Here are a number of popular Dragonfly extensions:

- `dragonfly-energy <https://ladybug.tools/dragonfly-energy/docs>`_


.. toctree::
   :maxdepth: 2
   :caption: Contents:

.. include:: modules.rst
.. include:: cli.rst


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
