[![Build Status](https://travis-ci.org/ladybug-tools/dragonfly.svg?branch=master)](https://travis-ci.org/ladybug-tools/dragonfly)
[![Coverage Status](https://coveralls.io/repos/github/ladybug-tools/dragonfly/badge.svg?branch=master)](https://coveralls.io/github/ladybug-tools/dragonfly)

[![Python 2.7](https://img.shields.io/badge/python-2.7-green.svg)](https://www.python.org/downloads/release/python-270/) [![Python 3.6](https://img.shields.io/badge/python-3.6-blue.svg)](https://www.python.org/downloads/release/python-360/)

# dragonfly-core

![Screenshot](https://github.com/chriswmackey/Dragonfly/blob/master/dragonfly.png)

Dragonfly is collection of libraries to model and analyze urban climate, energy use, and daylight.
It extends the capabilites of [honeybee-core](https://github.com/ladybug-tools/honeybee-core) for the urban scale.

## Installation
```console
pip install dragonfly-core
```

## QuickStart
```python
import dragonfly

```

## [API Documentation](http://ladybug-tools.github.io/dragonfly/docs)

## Local Development
1. Clone this repo locally
```console
git clone git@github.com:ladybug-tools/dragonfly-core.git

# or

git clone https://github.com/ladybug-tools/dragonfly-core.git
```
2. Install dependencies:
```console
cd dragonfly
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
