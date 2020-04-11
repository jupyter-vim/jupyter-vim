"""
Utility functions for use with jupyter_vim module.
"""
import os
from pathlib import Path
import re
import signal
from sys import version_info

import vim

from jupyter_core.paths import jupyter_runtime_dir


def is_integer(s):
    """Check if string represent an interger"""
    s = str(s)
    if s[0] in ('-', '+'):
        return s[1:].isdigit()
    return s.isdigit()


def echom(arg, style="None", cmd='echom'):
    """Report string `arg` using vim's echomessage command.

    Keyword args:
    style -- the vim highlighting style to use
    """
    try:
        vim.command("echohl {}".format(style))
        messages = arg.split('\n')
        for msg in messages:
            vim.command(cmd + " \"{}\"".format(msg.replace('\"', '\\\"')))
        vim.command("echohl None")
    except vim.error:
        print("-- {}".format(arg))


def vim_var(name, default):
    """Try to get vim (name) otherwise (default)"""
    try: 
        return vim.eval(name)
    except: 
        return default


def str_to_py(var):
    """Convert: Vim -> Py"""
    is_py3 = version_info[0] >= 3
    encoding = vim.eval('&encoding') or 'utf-8'
    if is_py3 and isinstance(var, bytes):
        var = str(var, encoding)
    elif not is_py3 and isinstance(var, str):
        # pylint: disable=undefined-variable
        var = unicode(var, encoding)  # noqa: E0602
    return var


def str_to_vim(obj):
    """Convert: Py -> Vim
    Independant of vim's version
    """
    # Encode
    if version_info[0] < 3:
        # pylint: disable=undefined-variable
        obj = unicode(obj, 'utf-8')  # noqa: E0602
    else:
        if not isinstance(obj, bytes):
            obj = obj.encode()
        obj = str(obj, 'utf-8')

    # Vim cannot deal with zero bytes:
    obj = obj.replace('\0', '\\0')

    # Escape
    obj.replace('\\', '\\\\').replace('"', r'\"')

    return '"{:s}"'.format(obj)


def unquote_string(string):
    """Unquote some text/plain response from kernel"""
    if isinstance(string, bytes):
        string = string.decode()
    if not isinstance(string, str):
        string = str(string)
    for quote in ("'", '"'):
        string = string.rstrip(quote).lstrip(quote)
    return string


def strip_color_escapes(s):
    """Remove ANSI color escape sequences from a string."""
    re_strip_ansi = re.compile(r'\x1B\[([0-9]{1,2}(;[0-9]{1,2})*)?[mK]')
    return re_strip_ansi.sub('', s)


def prettify_execute_intput(line_number, cmd, prompt_in):
    """Also used with my own input (as iperl does not send it back)"""
    prompt = prompt_in.format(line_number)
    # Add continuation line, if necessary
    dots = (' ' * (len(prompt.rstrip()) - 4)) + '...: '
    return prompt + cmd.rstrip().replace('\n', '\n' + dots)


def match_kernel_id(fpath):
    """Get kernel id from filename: 'kernel-24536.json' -> '24536'"""
    m = re.search(r'kernel-(.+)\.json', str(fpath))
    return m[1] if m else None


def find_jupyter_kernel_ids():
    """Find opened kernels
    Called: <- vim completion method
    Returns: List of string
    """
    # TODO Get type of kernel (python, julia, etc.)
    runtime_files = Path(jupyter_runtime_dir()).glob('kernel*.json')
    return [match_kernel_id(fpath) for fpath in runtime_files]


def find_signals():
    """Find avalaible signal string in OS
    Called: <- vim completion method
    Returns: List of string
    """
    signals = [v for v, k in signal.__dict__.items()
               if v.startswith('SIG') and not v.startswith('SIG_')]
    signals.sort()
    return signals
