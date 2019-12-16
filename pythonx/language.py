"""
Jupyter language interface for vim client:
"""

# Export only: see at end
__all__ = ['list_languages', 'get_language']


class Language:
    """Language Base"""
    prompt_in = 'In [{line:d}]: '
    prompt_out = 'Out[{line:d}]: '
    print_string = 'print("{}")'
    pid = -1
    cwd = '"unknown"'
    hostname = '"unknown"'


class Javascript(Language):
    prompt_in = 'Js [{line:d}]: '
    print_string = 'console.log("{}")'
    pid = 'var process = require("process"); _res = process.pid;'
    cwd = 'var os = require("os"); _res = os.userInfo().username;'
    hostname = 'var process = require("process"); _res = process.cwd();'


class Julia(Language):
    prompt_in = 'Jl [{line:d}]: '
    print_string = 'println("{}")'
    pid = '_res = getpid()'
    cwd = '_res = pwd()'
    hostname = '_res = gethostname()'


class Perl(Language):
    prompt_in = 'Pl [{line:d}]: '
    print_string = 'print("{}")'
    pid = '$_res = $$'
    cwd = 'use Cwd; $_res = getcwd();'
    hostname = 'use Sys::Hostname qw/hostname/; $_res = hostname();'


class Python(Language):
    prompt_in = 'Py [{line:d}]: '
    print_string = 'print("{}")'
    pid = 'import os; _res = os.getpid()'
    cwd = 'import os; _res = os.getcwd()'
    hostname = 'import socket; _res = socket.gethostname()'


# Dict: kernel_type -> class
language_dict = {
    'javascript': Javascript,
    'julia': Julia,
    'perl': Perl,
    'python': Python,
}


def list_languages():
    return language_dict.keys()


def get_language(kernel_type):
    """Get language class
    Assert that language is in language_list (checked by caller)
    But still, let's return something
    """
    if kernel_type not in list_languages():
        return Language
    return language_dict[kernel_type]
