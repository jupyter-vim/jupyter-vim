"""
Utility functions for use with jupyter_vim module.
"""

from pathlib import Path
import re
import signal
from sys import version_info

from jupyter_core.paths import jupyter_runtime_dir

import vim


def is_integer(s):
    """Check if string represents an integer."""
    s = str(s)
    if s[0] in ('-', '+'):
        return s[1:].isdigit()
    return s.isdigit()


def echom(arg, style='None'):
    """Report `arg` using vim's :echomessage command.

    Parameters
    ----------
    arg : str
        message to print
    style : str, optional, default='None'
        vim highlighting style of message
    """
    try:
        vim.command(f"echohl {style}")
        messages = arg.split('\n')
        for msg in messages:
            vim.command("echom \"{}\"".format(msg.replace('\"', '\\\"')))
        vim.command("echohl None")
    except vim.error:
        print(f"-- {arg}")


def get_vim(name, default=None):
    """Try to get vim `name` otherwise `default`.

    .. note:: The built-in `vim.vars['name']` dictionary only contains `g:` and
        `v:` variables, not `b:`, `l:`, or `s:` variables.

    Parameters
    ----------
    name : str
        Name of vim variable to evaluate.
    default : :obj:, optional, default=None
        Value to return if vim variable `name` does not exist.

    Returns
    -------
    str
        The value of the vim variable, or `default`.
    """
    try:
        return vim.eval(name)
    except vim.error:
        return default


def str_to_py(obj):
    """Encode Python object `obj` as python string.

    Parameters
    ----------
    obj : :obj:
        Python object to be encoded (typically a str or int).

    Returns
    -------
    str
        An encoded python string.
    """
    is_py3 = version_info[0] >= 3
    encoding = vim.eval('&encoding') or 'utf-8'
    if is_py3 and isinstance(obj, bytes):
        obj = str(obj, encoding)
    elif not is_py3 and isinstance(obj, str):
        # pylint: disable=undefined-variable
        obj = unicode(obj, encoding)  # noqa: E0602
    return obj


def str_to_vim(obj):
    """Encode Python object `obj` as vim string.

    Parameters
    ----------
    obj : :obj:
        Object to be encoded.

    Returns
    -------
    str
        Double-quoted string.
    """
    # Encode
    is_py3 = version_info[0] >= 3
    if is_py3:
        if not isinstance(obj, bytes):
            obj = obj.encode()
        obj = str(obj, 'utf-8')
    else:
        # pylint: disable=undefined-variable
        obj = unicode(obj, 'utf-8')  # noqa: E0602

    # Vim cannot deal with zero bytes:
    obj = obj.replace('\0', '\\0')

    # Escape
    obj.replace('\\', '\\\\').replace('"', r'\"')

    # Return double-quoted string
    return f'"{obj:s}"'


def unquote_string(s):
    """Remove single and double quotes from beginning and end of `s`."""
    if isinstance(s, bytes):
        s = s.decode()
    if not isinstance(s, str):
        s = str(s)
    for quote in ("'", '"'):
        s = s.rstrip(quote).lstrip(quote)
    return s


def strip_color_escapes(s):
    """Remove ANSI color escape sequences from a string."""
    re_strip_ansi = re.compile(r'\x1B\[([0-9]{1,2}(;[0-9]{1,2})*)?[mK]')
    return re_strip_ansi.sub('', s)


def prettify_execute_intput(line_number, cmd, prompt_in):
    """Add additional formatting around a multiline command.

    Parameters
    ----------
    line_number : int or str
        Starting line number of input command.
    cmd : str
        The command to be executed.
    prompt_in : str
        The leader prompt string.

    Returns
    -------
    str
        Input command with additional formatting.
    """
    prompt = prompt_in.format(line_number)
    # Add continuation line, if necessary
    dots = (' ' * (len(prompt.rstrip()) - 4)) + '...: '
    return prompt + cmd.rstrip().replace('\n', '\n' + dots)


def match_kernel_id(fpath):
    """Get kernel id from file path: 'kernel-24536.json' -> '24536'.

    Parameters
    ----------
    fpath : :obj:`pathlib.Path` or str
        Filename (or full path) from which to find kernel id.

    Returns
    -------
    str
        Kernel id as a string.
    """
    m = re.search(r'kernel-(.+)\.json', str(fpath))
    return m[1] if m else None


def find_jupyter_kernel_ids():
    """Find opened kernel json files.

    .. note:: called by vim command completion.

    Returns
    -------
    list(str)
        List of strings of kernel ids.
    """
    # TODO Get type of kernel (python, julia, etc.)
    runtime_files = Path(jupyter_runtime_dir()).glob('kernel*.json')
    return [match_kernel_id(fpath) for fpath in runtime_files]


def find_signals():
    """Find avalaible signal string in OS.

    .. note:: called by vim command completion.

    Returns
    -------
    list(str)
        List of strings of signal names, i.e. SIGTERM.
    """
    signals = [v for v, k in signal.__dict__.items()
               if v.startswith('SIG') and not v.startswith('SIG_')]
    return sorted(signals)
