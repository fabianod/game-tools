"""Command line utility for creating and manipulating PAK files

Supported Games:
    - QUAKE
"""

__version__ = '1.0.0'

import argparse
import os
import sys

from quake import pak


class ResolvePathAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        if isinstance(values, list):
            fullpath = [os.path.expanduser(v) for v in values]
        else:
            fullpath = os.path.expanduser(values)

        setattr(namespace, self.dest, fullpath)


class Parser(argparse.ArgumentParser):
    """Simple wrapper class to provide help on error"""
    def error(self, message):
        sys.stderr.write('error: %s\n' % message)
        self.print_help()
        sys.exit(1)


if __name__ == '__main__':
    parser = Parser(prog='pak',
                    description='Default action is to add or replace pak files '
                                'entries from list.\nIf list is omitted, pak will '
                                'use stdin.',
                    epilog='example: pak {0} {1} => adds {1} to {0}'.format('tex.pak', 'image.png'))

    parser.add_argument('file',
                        metavar='file.pak',
                        action=ResolvePathAction,
                        help='pak file to ')

    parser.add_argument('list',
                        nargs='*',
                        action=ResolvePathAction,
                        default=[t.strip('\n') for t in sys.stdin] if not sys.stdin.isatty() else None)

    parser.add_argument('-q',
                        dest='quiet',
                        action='store_true',
                        help='quiet mode')

    parser.add_argument('-v', '--version',
                        dest='version',
                        action='version',
                        help=argparse.SUPPRESS,
                        version='{} version {}'.format(parser.prog, __version__))

    args = parser.parse_args()

    if not args.list:
        parser.error('the following arguments are required: list')

    dir = os.path.dirname(args.file) or '.'
    if not os.path.exists(dir):
        os.makedirs(dir)

    filemode = 'a'
    if not os.path.isfile(args.file):
        filemode = 'w'

    with pak.PakFile(args.file, filemode) as pak_file:
        if not args.quiet:
            print('Archive: %s' % os.path.basename(args.file))

        # Process input files
        for file in args.list:
            # Walk directories
            if os.path.isdir(file):
                for root, dirs, files in os.walk(file):
                    for name in [f for f in files if not f.startswith('.')]:
                        fullpath = os.path.join(root, name)
                        relpath = os.path.relpath(fullpath, os.getcwd())

                        if not args.quiet:
                            print('  adding: %s' % relpath)

                        pak_file.write(relpath)

            else:
                relpath = os.path.relpath(file, os.getcwd())

                if not args.quiet:
                    print('  adding: %s' % relpath)

                pak_file.write(relpath)

    sys.exit(0)
