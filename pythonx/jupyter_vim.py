##############################################################################
#    File: pythonx/jupyter_vim.py
# Created: 07/28/11 22:14:58
#  Author: Paul Ivanov (http://pirsquared.org)
#  Updated: [11/13/2017] Marijn van Vliet
#  Updated: [02/14/2018, 12:31] Bernie Roesler
#  Updated: [15/12/2019] Tinmarino
#
# Description:
# Python code for ftplugin/python/jupyter.vim.
##############################################################################

from language import list_languages, get_language
from os import kill, listdir
from os.path import join, splitext, isfile
from signal import SIGTERM
from sys import version_info
from threading import Thread
from textwrap import dedent
import re

try:
    from queue import Empty
except ImportError:
    from Queue import Empty

_install_instructions = """You *must* install the jupyter package into the
Python that your vim is linked against. If you are seeing this message, this
usually means either:
    (1) configuring vim to automatically load a virtualenv that has Jupyter
        installed and whose Python interpreter is the same version that your
        vim is compiled against
    (2) installing Jupyter using the system Python that vim is using, or
    (3) recompiling Vim against the Python where you already have Jupyter
        installed.
This is only a requirement to allow Vim to speak with a Jupyter kernel using
Jupyter's own machinery. It does *not* mean that the Jupyter instance with
which you communicate via jupyter-vim needs to be running the same version of
Python.
"""

try:
    import jupyter   # noqa
except ImportError as e:
    raise ImportError("Could not find kernel. " + _install_instructions, e)

try:
    import vim
except ImportError as e:
    raise ImportError('vim module only available within vim!', e)

# -----------------------------------------------------------------------------
#        Read global configuration variables
# -----------------------------------------------------------------------------
is_py3 = version_info[0] >= 3
if is_py3:
    unicode = str


# General message command
def vim_echom(arg, style="None", cmd='echom'):
    """
    Report string `arg` using vim's echomessage command.

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


# -----------------------------------------------------------------------------
#        Check Connection:
# -----------------------------------------------------------------------------
def check_connection():
    """Check that we have a client connected to the kernel."""
    return kc.hb_channel.is_beating() if kc else False


def warn_no_connection():
    vim_echom('WARNING: Not connected to Jupyter!'
              '\nRun :JupyterConnect to find the kernel', style='WarningMsg')


# if module has not yet been imported, define global kernel manager, client and
# kernel pid. Otherwise, just check that we're connected to a kernel.
if all([x in globals() for x in ('kc', 'pid', 'cfile', 'lang', 'cmd', 'cmd_id')]):
    if not check_connection():
        warn_no_connection()
else:
    kc = None
    pid = None
    cfile = None
    lang = None
    cmd = None
    cmd_id = None


# -----------------------------------------------------------------------------
#        Utilities
# -----------------------------------------------------------------------------
# Define wrapper for encoding
# get around unicode problems when interfacing with vim
vim_encoding = vim.eval('&encoding') or 'utf-8'
# from <http://serverfault.com/questions/71285/\
# in-centos-4-4-how-can-i-strip-escape-sequences-from-a-text-file>
strip = re.compile(r'\x1B\[([0-9]{1,2}(;[0-9]{1,2})*)?[mK]')


def vim2py_str(var):
    """Convert to proper encoding."""
    if is_py3 and isinstance(var, bytes):
        var = str(var, vim_encoding)
    elif not is_py3 and isinstance(var, str):
        var = unicode(var, vim_encoding)
    return var


# Taken from jedi-vim/pythonx/jedi_vim.py
# <https://github.com/davidhalter/jedi-vim>
class PythonToVimStr(unicode):
    """ Vim has a different string implementation of single quotes """
    __slots__ = []

    def __new__(cls, obj, encoding='UTF-8'):
        if not (is_py3 or isinstance(obj, unicode)):
            obj = unicode.__new__(cls, obj, encoding)

        # Vim cannot deal with zero bytes:
        obj = obj.replace('\0', '\\0')
        return unicode.__new__(cls, obj)

    def __repr__(self):
        # this is totally stupid and makes no sense but vim/python unicode
        # support is pretty bad. Don't ask how I came up with this... It just
        # works...
        # It seems to be related to that bug: http://bugs.python.org/issue5876
        if unicode is str:
            s = self
        else:
            s = self.encode('UTF-8')
        return '"{:s}"'.format(s.replace('\\', '\\\\').replace('"', r'\"'))


def get_res_from_code_string(code):
    """Helper: Get variable _res from code string (setting _res)"""
    res = None

    # Send message
    msg_id = send(code, silent=False, user_expressions={'_res': '_res'})

    # Wait to get message back from kernel (1 sec)
    try:
        reply = get_reply_msg(msg_id)
    except Empty: pass

    # Parse response
    try:
        # Requires the fix for https://github.com/JuliaLang/IJulia.jl/issues/815
        res = reply['content']['user_expressions']['_res']['data']['text/plain']
    except KeyError: pass

    # If bad luck, try again, cross your finger
    # Explain: some kernel (iperl) do not discriminate when clien ask user_expressions.
    # But still they give a printable output
    if None is res:
        # Parse all execute
        msgs = kc.iopub_channel.get_msgs()
        for msg in msgs:
            try:
                # Get the result of execution
                if msg['header']['msg_type'] not in ('execute_result', 'stream'):
                    continue
                content = msg['content']
                if 'data' in content:
                    res = content['data']['text/plain']
                else:
                    # Jupyter bash style ...
                    res = content['text']
                break
            except (KeyError): pass

    # Game over
    if None is res:
        res = -1
        vim_echom("no reply from jupyter kernel", "WarningMsg")

    # Convert
    res = unquote_string(res)
    if re.match(r'[-+]?\d+$', res) is not None:
        res = int(res)

    # Rest in peace
    return res


def unquote_string(string):
    """Unquote some text/plain response from kernel"""
    res = str(string)
    for quote in ("'", '"'):
        res = res.rstrip(quote).lstrip(quote)
    return res


def get_kernel_info(kernel_type):
    """Explicitly ask the jupyter kernel for its pid
    Returns: dict with 'kernel_type', 'pid', 'cwd', 'hostname'
    """
    global pid, lang

    # Check in
    if kernel_type not in list_languages():
        vim_echom('I don''t know how to get infos for a Jupyter kernel of'
                  ' type "{}"'.format(kernel_type), 'WarningMsg')

    # Get language
    lang = get_language(kernel_type)

    # Set kernel type
    res = {'kernel_type': kernel_type}

    # Get full connection file
    res['connection_file'] = cfile

    # Get kernel id
    res['id'] = shorten_filename(cfile)

    # Get pid
    try: res['pid'] = get_res_from_code_string(lang.pid)
    except Exception: res['pid'] = -1
    pid = res['pid']

    # Get cwd
    try: res['cwd'] = get_res_from_code_string(lang.cwd)
    except Exception: res['cwd'] = 'unknown'

    # Get hostname
    try: res['hostname'] = get_res_from_code_string(lang.hostname)
    except Exception: res['hostname'] = 'unknown'

    # Print vim connected
    vim_pid = vim.eval('getpid()')
    hi_string = '\\n\\n'
    hi_string += 'Received connection from vim client with pid ' + vim_pid
    hi_string += '\\n' + '-' * 60 + '\\n'
    get_res_from_code_string(lang.print_string.format(hi_string))

    # Return
    return res


def is_cell_separator(line):
    """ Determine whether a given line is a cell separator """
    # TODO allow users to define their own cell separators
    cell_sep = ('##', '#%%', '# %%', '# <codecell>')
    return line.startswith(cell_sep)


def strip_color_escapes(s):
    """Remove ANSI color escape sequences from a string."""
    return strip.sub('', s)


def shorten_filename(runtime_file):
    if runtime_file is None: return ''
    r_cfile = r'.*kernel-([0-9a-fA-F]*)[0-9a-fA-F\-]*.json'
    return re.sub(r_cfile, r'\1', runtime_file)


def find_jupyter_kernels():
    """Find opened kernels
    Returns: List of string (intifiable)
    """
    from jupyter_core.paths import jupyter_runtime_dir

    # Get all kernel json files
    jupyter_path = jupyter_runtime_dir()
    runtime_files = []
    for file_path in listdir(jupyter_path):
        full_path = join(jupyter_path, file_path)
        file_ext = splitext(file_path)[1]
        if (isfile(full_path) and '.json' == file_ext):
            runtime_files.append(file_path)

    # Get all the kernel ids
    kernel_ids = []
    for runtime_file in runtime_files:
        kernel_id = shorten_filename(runtime_file)
        if runtime_file.startswith('nbserver'): continue
        kernel_ids.append(kernel_id)

    # Set vim variable -> vim caller
    vim.command('let l:kernel_ids=' + str(kernel_ids))


# Alias execute function
def send(msg, **kwargs):
    """Send a message to the kernel client."""
    global cmd, cmd_id
    if kc is None:
        vim_echom('kernel failed sending message, client not created'
                  '\ndid you run :JupyterConnect ?'
                  '\n msg to be sent : {}'.format(msg), style="Error")
        return -1

    # Include dedent of msg so we don't get odd indentation errors.
    cmd = dedent(msg)
    cmd_id = kc.execute(cmd, **kwargs)

    return cmd_id


# -----------------------------------------------------------------------------
#        Major Function Definitions:
# -----------------------------------------------------------------------------
def connect_to_kernel(kernel_type, filename=''):
    # Create thread
    thread = Thread(target=thread_connect_to_kernel,
                    args=(kernel_type, filename))
    thread.start()


def thread_connect_to_kernel(kernel_type, filename=''):
    """Create kernel manager from existing connection file."""
    from jupyter_client import KernelManager, find_connection_file

    global kc, cfile

    # Test if connection is alive
    connected = check_connection()
    attempt = 0
    max_attempts = 3
    while not connected and attempt < max_attempts:
        attempt += 1
        try:
            cfile = find_connection_file(filename=filename)
        except IOError:
            vim_echom("kernel connection attempt {:d}/{:d} failed - no kernel file"
                      .format(attempt, max_attempts), style="Error")
            continue

        # Create the kernel manager and connect a client
        # See: <http://jupyter-client.readthedocs.io/en/stable/api/client.html>
        km = KernelManager(connection_file=cfile)
        km.load_connection_file()
        kc = km.client()
        kc.start_channels()

        # Ping the kernel
        kc.kernel_info()
        try:
            kc.get_shell_msg(timeout=1)
        except Empty:
            continue
        else:
            connected = True

    if connected:
        # Collect kernel info
        kernel_info = get_kernel_info(kernel_type)

        # More info (anyway screen is redrawn)
        #  # Prettify output: appearance rules
        from pprint import PrettyPrinter
        pp = PrettyPrinter(indent=4, width=vim.eval('&columns'))
        kernel_string = pp.pformat(kernel_info)[4:-1]

        # # Echo message
        vim_echom('To: ', style='Question')
        vim_echom(kernel_string.replace('\"', '\\\"'), cmd='echom')

        # Send command so that user knows vim is connected at bottom, more
        # readable
        vim_echom('Connected: {}'.format(shorten_filename(cfile)), style='Question')

    else:
        if None is not kc: kc.stop_channels()
        vim_echom('kernel connection attempt timed out', style='Error')


def disconnect_from_kernel():
    """Disconnect kernel client."""
    if None is not kc: kc.stop_channels()
    vim_echom("Disconnected: {}".format(shorten_filename(cfile)), style='Directory')


def update_console_msgs():
    """Grab pending messages and place them inside the vim console monitor."""
    # Open the Jupyter terminal in vim, and move cursor to it
    is_console_open = vim.eval('jupyter#OpenJupyterTerm()')
    if not is_console_open:
        vim_echom('__jupyter_term__ failed to open!', 'Error')
        return

    # Get buffer (same indexes as vim)
    b_nb = int(vim.eval('bufnr("__jupyter_term__")'))
    b = vim.buffers[b_nb]

    # Append the I/O to the console buffer
    io_pub = handle_messages()

    # Insert code line Check not already here (check with substr 'Py [')
    if cmd is not None and not any(lang.prompt_in[:4] in msg for msg in io_pub):
        # Get cmd number from id (TODO mutualize)
        try:
            reply = get_reply_msg(cmd_id)
            cmd_nb = reply['content']['execution_count']
        except Empty:
            cmd_nb = -1
        io_pub.insert(0, lang.prompt_in.format(cmd_nb) + cmd)

    # Append mesage to jupyter terminal buffer
    for msg in io_pub:
        b.append([PythonToVimStr(line) for line in msg.splitlines()])


def handle_messages():
    """
    Message handler for Jupyter protocol.

    Takes all messages on the I/O Public channel, including stdout, stderr,
    etc. and returns a list of the formatted strings of their content.

    See also: <http://jupyter-client.readthedocs.io/en/stable/messaging.html>
    """
    io_pub = []
    msgs = kc.iopub_channel.get_msgs()
    for msg in msgs:
        s = ''
        if 'msg_type' not in msg['header']:
            continue
        msg_type = msg['header']['msg_type']
        if msg_type == 'status':
            continue
        elif msg_type == 'stream':
            # TODO: allow for distinguishing between stdout and stderr (using
            # custom syntax markers in the vim-jupyter buffer perhaps), or by
            # also echoing the message to the status bar
            s = strip_color_escapes(msg['content']['text'])
        elif msg_type == 'display_data':
            s += msg['content']['data']['text/plain']
        elif msg_type == 'pyin' or msg_type == 'execute_input':
            line_number = msg['content'].get('execution_count', 0)
            prompt = lang.prompt_in.format(line_number)
            s = prompt
            # add continuation line, if necessary
            dots = (' ' * (len(prompt.rstrip()) - 4)) + '...: '
            s += msg['content']['code'].rstrip().replace('\n', '\n' + dots)
        elif msg_type == 'pyout' or msg_type == 'execute_result':
            s = lang.prompt_out.format(msg['content']['execution_count'])
            s += msg['content']['data']['text/plain']
        elif msg_type == 'pyerr' or msg_type == 'error':
            s = "\n".join(map(strip_color_escapes, msg['content']['traceback']))
        elif msg_type == 'input_request':
            vim_echom('python input not supported in vim.', 'Error')
            continue  # unsure what to do here... maybe just return False?
        else:
            vim_echom("Message type {} unrecognized!".format(msg_type))
            continue

        # List all messages
        io_pub.append(s)

    return io_pub


# -----------------------------------------------------------------------------
#        Communicate with Kernel
# -----------------------------------------------------------------------------
def get_reply_msg(msg_id):
    """Get kernel reply from sent client message with msg_id."""
    # TODO handle 'is_complete' requests?
    # <http://jupyter-client.readthedocs.io/en/stable/messaging.html#code-completeness>
    while True:
        try:
            m = kc.get_shell_msg(block=False, timeout=1)
        except Empty:
            continue
        if m['parent_header']['msg_id'] == msg_id:
            return m


def print_prompt(prompt, msg_id=None):
    """Print In[] or In[56] style messages on Vim's display line."""
    if msg_id:
        # wait to get message back from kernel
        try:
            reply = get_reply_msg(msg_id)
            count = reply['content']['execution_count']
            vim_echom(lang.prompt_in.format(count) + str(prompt))
        except Empty:
            # if the kernel is waiting for input it's normal to get no reply
            if not kc.stdin_channel.msg_ready():
                vim_echom(lang.prompt_in.format(-1)
                          + '{} (no reply from Jupyter kernel)'.format(prompt))
    else:
        vim_echom("In[]: {}".format(prompt))


# Decorator for all sending commands
def with_console(f):
    """
    Decorator for sending messages to the kernel. Conditionally monitor
    the kernel replies, as well as messages from other clients.
    """
    def wrapper(*args, **kwargs):
        if not check_connection():
            warn_no_connection()
            return
        monitor_console = bool(int(vim.vars.get('jupyter_monitor_console', 0)))
        f(*args, **kwargs)
        if monitor_console:
            update_console_msgs()
    return wrapper


# Include verbose output to vim command line
def with_verbose(f):
    """
    Decorator to receive message id from sending function, and report back to
    vim with output.
    """
    def wrapper(*args, **kwargs):
        verbose = bool(int(vim.vars.get('jupyter_verbose', 0)))
        (prompt, msg_id) = f(*args, **kwargs)
        if verbose:
            print_prompt(prompt, msg_id=msg_id)
    return wrapper


def change_directory(directory):
    """CD: Change (current working) to directory
    Note: @with_verbose + send make perl bug. TODO restore that
    """
    # Cd
    get_res_from_code_string(lang.cd.format(directory))

    # TODO set cd to a buffer var ?
    # Print cwd
    try:
        cwd = get_res_from_code_string(lang.cwd)
        vim_echom('CWD: ', style='Question')
        vim.command("echon \"{}\"".format(cwd))
    except Exception: pass


@with_console
@with_verbose
def run_command(cmd):
    """Send a single command to the kernel."""
    msg_id = send(cmd)
    return (cmd, msg_id)


@with_console
@with_verbose
def run_file_in_ipython(flags='', filename=''):
    """Run a given python file using ipython's %run magic."""
    ext = splitext(filename)[-1][1:]
    if ext in ('pxd', 'pxi', 'pyx', 'pyxbld'):
        run_cmd = '%run_cython'
        params = vim2py_str(vim.vars.get('cython_run_flags', ''))
    else:
        run_cmd = '%run'
        params = flags or vim2py_str(vim.current.buffer.vars['ipython_run_flags'])
    cmd = '{run_cmd} {params} "{filename}"'.format(
        run_cmd=run_cmd, params=params, filename=filename)
    msg_id = send(cmd)
    return (cmd, msg_id)


@with_console
@with_verbose
def send_range():
    """Send a range of lines from the current vim buffer to the kernel."""
    r = vim.current.range
    lines = "\n".join(vim.current.buffer[r.start:r.end+1])
    msg_id = send(lines)
    prompt = "range {:d}-{:d} ".format(r.start+1, r.end+1)
    return (prompt, msg_id)


@with_console
@with_verbose
def run_cell():
    """Run all the code between two cell separators"""
    cur_buf = vim.current.buffer
    (cur_line, cur_col) = vim.current.window.cursor
    cur_line -= 1

    # Search upwards for cell separator
    upper_bound = cur_line
    while upper_bound > 0 and not is_cell_separator(cur_buf[upper_bound]):
        upper_bound -= 1

    # Skip past the first cell separator if it exists
    if is_cell_separator(cur_buf[upper_bound]):
        upper_bound += 1

    # Search downwards for cell separator
    lower_bound = min(upper_bound+1, len(cur_buf)-1)

    while lower_bound < len(cur_buf)-1 and \
            not is_cell_separator(cur_buf[lower_bound]):
        lower_bound += 1

    # Move before the last cell separator if it exists
    if is_cell_separator(cur_buf[lower_bound]):
        lower_bound -= 1

    # Make sure bounds are within buffer limits
    upper_bound = max(0, min(upper_bound, len(cur_buf)-1))
    lower_bound = max(0, min(lower_bound, len(cur_buf)-1))

    # Make sure of proper ordering of bounds
    lower_bound = max(upper_bound, lower_bound)

    # Execute cell
    lines = "\n".join(cur_buf[upper_bound:lower_bound+1])
    msg_id = send(lines)
    prompt = "execute lines {:d}-{:d} ".format(upper_bound+1, lower_bound+1)
    return (prompt, msg_id)


def signal_kernel(sig=SIGTERM):
    """
    Use kill command to send a signal to the remote kernel. This side steps the
    (non-functional) jupyter interrupt mechanisms.
    Only works on posix.
    """
    try:
        kill(pid, int(sig))
        vim_echom("kill pid {p:d} with signal #{v:d}, {n:s}"
                  .format(p=pid, v=sig.value, n=sig.name), style='WarningMsg')
    except ProcessLookupError:
        vim_echom(("pid {p:d} does not exist! " +
                   "Kernel may have been terminated by outside process")
                  .format(p=pid), style='Error')
    except OSError as e:
        vim_echom("signal #{v:d}, {n:s} failed to kill pid {p:d}"
                  .format(v=sig.value, n=sig.name, p=pid), style='Error')
        raise e


# def set_breakpoint():
#     send("__IP.InteractiveTB.pdb.set_break('%s',%d)" % (vim.current.buffer.name,
#                                                         vim.current.window.cursor[0]))
#     print("set breakpoint in %s:%d"% (vim.current.buffer.name,
#                                       vim.current.window.cursor[0]))
#
# def clear_breakpoint():
#     send("__IP.InteractiveTB.pdb.clear_break('%s',%d)" % (vim.current.buffer.name,
#                                                           vim.current.window.cursor[0]))
#     print("clearing breakpoint in %s:%d" % (vim.current.buffer.name,
#                                             vim.current.window.cursor[0]))
#
# def clear_all_breakpoints():
#     send("__IP.InteractiveTB.pdb.clear_all_breaks()");
#     print("clearing all breakpoints")
#
# def run_this_file_pdb():
#     send(' __IP.InteractiveTB.pdb.run(\'execfile("%s")\')' % (vim.current.buffer.name,))
#     #send('run -d %s' % (vim.current.buffer.name,))
#     echo("In[]: run -d %s (using pdb)" % vim.current.buffer.name)
