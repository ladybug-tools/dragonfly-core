"""
Command Line Interface (CLI) entry point for dragonfly and dragonfly extensions.

Use this file only to add commands related to dragonfly-core. For adding extra commands
from each extention see below.

Dragonfly is using click (https://click.palletsprojects.com/en/7.x/) for creating the CLI.
You can extend the command line interface from inside each extention by following these
steps:

1. Create a ``cli`` folder in your extension.
2. Import the ``main`` function from this ``dragonfly.cli``.
3. Add your commands and command groups to main using add_command method.
4. Add ``import [your-extention].cli`` to ``__init__.py`` file to the commands are added
   to the cli when the module is loaded.

Good practice is to group all your extention commands in a command group named after
the extension. This will make the commands organized under extension namespace. For
instance commands for `dragonfly-energy` will be called like ``dragonfly energy [energy-command]``.


.. code-block:: python

    import click
    from dragonfly.cli import main

    @click.group()
    def energy():
        pass

    # add commands to energy group
    @energy.command('to-idf')
    # ...
    def to_idf():
        pass

    # finally add the newly created commands to dragonfly cli
    main.add_command(energy)

    # do not forget to import this module in __init__.py otherwise it will not be added
    # to dragonfly commands.

Note:
    For extension with several commands you can use a folder structure instead of a single
    file.
"""
import click

from dragonfly.cli.validate import validate
from dragonfly.cli.translate import translate
from dragonfly.cli.edit import edit


@click.group()
@click.version_option()
def main():
    pass


@main.command('viz')
def viz():
    """Check if dragonfly is flying!"""
    click.echo('viiiiiiiiiiiiizzzzzzzzz!')


main.add_command(validate)
main.add_command(translate)
main.add_command(edit)


if __name__ == "__main__":
    main()
