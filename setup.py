import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

with open('requirements.txt') as f:
    requirements = f.read().splitlines()

setuptools.setup(
    name="dragonfly-core",
    use_scm_version=True,
    setup_requires=['setuptools_scm'],
    author="Ladybug Tools",
    author_email="info@ladybug.tools",
    description=":dragon: dragonfly core library",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/ladybug-tools/dragonfly-core",
    packages=setuptools.find_packages(exclude=["tests"]),
    install_requires=requirements,
    extras_require={
        'cli': ['click==7.1.2', "dragonfly-schema==1.6.17;python_version>='3.6'"]
    },
    entry_points={
        "console_scripts": ["dragonfly = dragonfly.cli:main"]
    },
    classifiers=[
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: Implementation :: CPython",
        "License :: OSI Approved :: GNU Affero General Public License v3",
        "Operating System :: OS Independent"
    ],
    license="AGPL-3.0"
)
