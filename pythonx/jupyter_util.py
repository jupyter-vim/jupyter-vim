from sys import version_info
from os import listdir
from os.path import isfile, join
import signal
import re

import vim

def is_integer(s):
    """Check if string represent an interger"""
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


def shorten_filename(runtime_file):
    """Shorten connection filename kernel-24536.json -> 24536"""
    r_cfile = r'.*kernel-([^\-]*).*\.json'
    return re.sub(r_cfile, r'\1', runtime_file)


def hex_sort(stg):
    """Sort hex strings"""
    try: res = int('0x' + stg, 16)
    except ValueError: res = 0
    return res


def find_jupyter_kernels():
    """Find opened kernels
    Called: <- vim completion method
    Returns: List of string
    """
    # Get jupyter runtime root dir
    from jupyter_core.paths import jupyter_runtime_dir
    jupyter_path = jupyter_runtime_dir()

    # Get all kernel json files
    runtime_files = [fpath for fpath in listdir(jupyter_path)
                     if isfile(join(jupyter_path, fpath))
                     and re.match(r'.*\.json', fpath)]

    # Get all the kernel ids
    kernel_ids = [shorten_filename(fpath) for fpath in runtime_files
                  if not fpath.startswith('nbserver')]

    # Sort
    kernel_ids.sort(key=hex_sort, reverse=True)

    # Return -> vim caller
    return kernel_ids


def find_signals():
    """Find avalaible signal string in OS
    Called: <- vim completion method
    Returns: List of string
    """
    signals = [v for v, k in signal.__dict__.items()
               if v.startswith('SIG') and not v.startswith('SIG_')]
    signals.sort()
    return signals

# -----------------------------------------------------------------------------
#        Parsers
# -----------------------------------------------------------------------------

def parse_iopub_for_reply(msgs, line_number):
    """Get kernel response from message pool (Async)
    Param: line_number: the message number of the corresponding code
    Use: some kernel (iperl) do not discriminate when clien ask user_expressions.
        But still they give a printable output
    """
    res = -1

    # Parse all execute
    for msg in msgs:
        # Get the result of execution
        # 1 content
        content = msg.get('content', False)
        if not content: continue

        # 2 execution _count
        ec = int(content.get('execution_count', 0))
        if not ec: continue
        if line_number not in (-1, ec): continue

        # 3 message type
        msg_type = msg.get('header', {}).get('msg_type', '')
        if msg_type not in ('execute_result', 'stream'): continue

        # 4 text
        res = content.get('data', {}).get('text/plain', -1)
        res = res if res != -1 else content.get('text', -1)  # Jupyter bash style ...
        break
    return res


def parse_messages(section_info, msgs):
    """Message handler for Jupyter protocol (Async)

    Takes all messages on the I/O Public channel, including stdout, stderr,
    etc.
    Returns: a list of the formatted strings of their content.

    See also: <http://jupyter-client.readthedocs.io/en/stable/messaging.html>
    """
    # pylint: disable=too-many-branches
    # TODO section_info is not perfectly async
    # TODO remove complexity
    res = []
    for msg in msgs:
        s = ''
        default_count = section_info.monitor.cmd_count
        if 'msg_type' not in msg['header']:
            continue
        msg_type = msg['header']['msg_type']

        if msg_type == 'status':
            # I don't care status (idle or busy)
            continue

        if msg_type == 'stream':
            # Get data
            text = strip_color_escapes(msg['content']['text'])
            line_number = msg['content'].get('execution_count', default_count)
            # Set prompt
            if msg['content'].get('name', 'stdout') == 'stderr':
                prompt = 'Err[{:d}]: '.format(line_number)
                dots = (' ' * (len(prompt.rstrip()) - 4)) + '...x '
            else:
                prompt = 'Out[{:d}]: '.format(line_number)
                dots = (' ' * (len(prompt.rstrip()) - 4)) + '...< '
            s = prompt
            # Add continuation line, if necessary
            s += text.rstrip().replace('\n', '\n' + dots)
            # Set cmd_count: if it changed
            if line_number != default_count:
                section_info.monitor.set_cmd_count(line_number)

        elif msg_type == 'display_data':
            s += msg['content']['data']['text/plain']

        elif msg_type in ('execute_input', 'pyin'):
            line_number = msg['content'].get('execution_count', default_count)
            cmd = msg['content']['code']
            s = prettify_execute_intput(line_number, cmd, section_info.lang.prompt_in)
            # Set cmd_count: if it changed
            if line_number != default_count:
                section_info.monitor.set_cmd_count(line_number)

        elif msg_type in ('execute_result', 'pyout'):
            # Get the output
            line_number = msg['content'].get('execution_count', default_count)
            s = section_info.lang.prompt_out.format(line_number)
            s += msg['content']['data']['text/plain']
            # Set cmd_count: if it changed
            if line_number != default_count:
                section_info.monitor.set_cmd_count(line_number)

        elif msg_type in ('error', 'pyerr'):
            s = "\n".join(map(strip_color_escapes, msg['content']['traceback']))

        elif msg_type == 'input_request':
            section_info.vim.thread_echom('python input not supported in vim.', style='Error')
            continue  # unsure what to do here... maybe just return False?

        else:
            section_info.vim.thread_echom("Message type {} unrecognized!".format(msg_type))
            continue

        # List all messages
        res.append(s)

    return res
