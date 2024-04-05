[![Build Status](https://travis-ci.com/ladybug-tools/dragonfly-core.svg?branch=master)](https://travis-ci.com/ladybug-tools/dragonfly-core)
[![Coverage Status](https://coveralls.io/repos/github/ladybug-tools/dragonfly-core/badge.svg?branch=master)](https://coveralls.io/github/ladybug-tools/dragonfly-core)

[![Python 3.10](https://img.shields.io/badge/python-3.10-orange.svg)](https://www.python.org/downloads/release/python-3100/) [![Python 3.7](https://img.shields.io/badge/python-3.7-blue.svg)](https://www.python.org/downloads/release/python-370/) [![Python 2.7](https://img.shields.io/badge/python-2.7-green.svg)](https://www.python.org/downloads/release/python-270/) [![IronPython](https://img.shields.io/badge/ironpython-2.7-red.svg)](https://github.com/IronLanguages/ironpython2/releases/tag/ipy-2.7.8/)

# dragonfly-core

![Screenshot](https://github.com/chriswmackey/Dragonfly/blob/master/dragonfly.png)

Dragonfly is a collection of Python libraries to create representations of buildings
following [dragonfly-schema](https://github.com/ladybug-tools/dragonfly-schema/wiki).
It abstracts the capabilities of [honeybee-core](https://github.com/ladybug-tools/honeybee-core/)
to make it easier to construct and edit large models.

This repository is the core repository that provides dragonfly's common functionalities.
To extend these functionalities you should install available Dragonfly extensions or write
your own.

Here are a number of frequently used extensions for Dragonfly:
- [dragonfly-energy](https://github.com/ladybug-tools/dragonfly-energy): Adds Energy simulation to Dragonfly.

## Installation

`pip install -U dragonfly-core`

To check if Dragonfly command line interface is installed correctly use `dragonfly viz` and you
should get a `viiiiiiiiiiiiizzzzzzzzz!` back in response!

## [API Documentation](https://www.ladybug.tools/dragonfly-core/docs/)

## Local Development
1. Clone this repo locally
```console
git clone git@github.com:ladybug-tools/dragonfly-core.git

# or

git clone https://github.com/ladybug-tools/dragonfly-core.git
```
2. Install dependencies:
```console
cd dragonfly-core
pip install -r dev-requirements.txt
pip install -r requirements.txt
```

3. Run Tests:
```console
python -m pytests tests/
```

4. Generate Documentation:
```console
sphinx-apidoc -f -e -d 4 -o ./docs ./dragonfly
sphinx-build -b html ./docs ./docs/_build/docs
```
