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
from textwrap import dedent
from threading import Thread
from time import sleep
import re

try:
    from queue import Empty, Queue
except ImportError:
    from Queue import Empty, Queue

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


# -----------------------------------------------------------------------------
#        Check Connection:
# -----------------------------------------------------------------------------
def check_connection():
    """Check that we have a client connected to the kernel."""
    return SI.km_client.hb_channel.is_beating() if SI.km_client else False


def warn_no_connection():
    """Echo warning: not connected"""
    vim_echom('WARNING: Not connected to Jupyter!'
              '\nRun :JupyterConnect to find the kernel', style='WarningMsg')


class SectionInfo():
    """Info relative to the jupyter <-> vim current section
    The only global object is of this class
    """
    def __init__(self):
        # KernelManager client
        self.km_client = None
        # Pid of the kernel
        self.kernel_pid = None
        # Pid of current vim section executing me
        self.vim_pid = vim.eval('getpid()')
        # Number of column of vim section
        # # will be setted at last sync moment
        self.vim_column = 80
        # Connection file
        self.cfile = None
        # Language static class of the kernel (python || java || ...)
        # # implemented in ./language.py
        self.lang = get_language('default')
        # Last command sent and it's id
        self.cmd = None
        self.cmd_id = None
        # Last received messages
        self.io_pub = []

        # Thread running
        self.thread = None
        # Should the current thread stop (cleanly)
        self.stop = False
        # Message queue
        self.message_queue = Queue()


# if module has not yet been imported, define global kernel manager, client and
# kernel pid. Otherwise, just check that we're connected to a kernel.
if 'SI' in globals():
    if not check_connection():
        warn_no_connection()
else:
    SI = SectionInfo()


# -----------------------------------------------------------------------------
#        Utilities
# -----------------------------------------------------------------------------
# Define wrapper for encoding
# get around unicode problems when interfacing with vim
vim_encoding = vim.eval('&encoding') or 'utf-8'
# from <http://serverfault.com/questions/71285/\
# in-centos-4-4-how-can-i-strip-escape-sequences-from-a-text-file>
strip = re.compile(r'\x1B\[([0-9]{1,2}(;[0-9]{1,2})*)?[mK]')


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


def get_res_from_iopub(line_number):
    """Try again to get kernel response
    Param: line_number: the message number of the corresponding code
    """
    res = None
    # Parse all execute
    msgs = SI.km_client.iopub_channel.get_msgs()
    for msg in msgs:
        try:
            # Get the result of execution
            # 1 content
            content = msg.get('content', False)
            if not content: continue

            # 2 execution _count
            ec = int(content.get('execution_count', 0))
            if not ec: continue
            if line_number not in (-1, ec): continue

            # 3 message type
            if msg['header']['msg_type'] not in ('execute_result', 'stream'): continue

            # 4 text
            if 'data' in content:
                res = content['data']['text/plain']
            else:
                # Jupyter bash style ...
                res = content['text']
            break
        except KeyError: pass
    return res


def get_res_from_code_string(code):
    """Helper: Get variable _res from code string (setting _res)"""
    res = None

    # Send message
    msg_id = send(code, silent=False, user_expressions={'_res': '_res'})

    # Wait to get message back from kernel (1 sec)
    try:
        reply = get_reply_msg(msg_id)
        line_number = reply['content'].get('execution_count', -1)
    except (Empty, KeyError, TypeError):
        line_number = -1

    # Parse response
    try:
        # Requires the fix for https://github.com/JuliaLang/IJulia.jl/issues/815
        res = reply['content']['user_expressions']['_res']['data']['text/plain']
    except (TypeError, KeyError): pass

    # If bad luck, try again, cross your finger
    # Explain: some kernel (iperl) do not discriminate when clien ask user_expressions.
    # But still they give a printable output
    if None is res: get_res_from_code_string(line_number)

    # Game over
    if None is res: res = -1

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
    Thread: <- cfile
            <- vim_pid
            -> lang
            -> kernel_pid
    Returns: dict with 'kernel_type', 'pid', 'cwd', 'hostname'
    """
    global SI

    # Check in
    if kernel_type not in list_languages():
        vim_echom('I don''t know how to get infos for a Jupyter kernel of'
                  ' type "{}"'.format(kernel_type), 'WarningMsg')

    # Get language
    SI.lang = get_language(kernel_type)

    # Set kernel type
    res = {'kernel_type': kernel_type}

    # Get full connection file
    res['connection_file'] = SI.cfile

    # Get kernel id
    res['id'] = shorten_filename(SI.cfile)

    # Get pid
    try: res['pid'] = get_res_from_code_string(SI.lang.pid)
    except Exception: res['pid'] = -1
    SI.kernel_pid = res['pid']

    # Get cwd
    try: res['cwd'] = get_res_from_code_string(SI.lang.cwd)
    except Exception: res['cwd'] = 'unknown'

    # Get hostname
    try: res['hostname'] = get_res_from_code_string(SI.lang.hostname)
    except Exception: res['hostname'] = 'unknown'

    # Print vim connected
    hi_string = '\\n\\n'
    hi_string += 'Received connection from vim client with pid ' + SI.vim_pid
    hi_string += '\\n' + '-' * 60 + '\\n'
    get_res_from_code_string(SI.lang.print_string.format(hi_string))

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
    """Shorten connection filename kernel-24536.json -> 24536"""
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
        if (isfile(full_path) and file_ext == '.json'):
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
    """Send a message to the kernel client
    Global: -> cmd, cmd_id
    """
    global SI
    if SI.km_client is None:
        vim_echom('kernel failed sending message, client not created'
                  '\ndid you run :JupyterConnect ?'
                  '\n msg to be sent : {}'.format(msg), style="Error")
        return -1

    # Include dedent of msg so we don't get odd indentation errors.
    SI.cmd = dedent(msg)
    SI.cmd_id = SI.km_client.execute(SI.cmd, **kwargs)

    return SI.cmd_id


def stop_thread():
    """Stop current thread <- SI.thread"""
    global SI
    if SI.thread is None: return
    if not SI.thread.isAlive(): SI.thread = None; return

    # Wait 1 sec max
    SI.stop = True
    for _ in range(100):
        if not SI.stop: sleep(0.010)
    SI.thread = None
    return


# -----------------------------------------------------------------------------
#        Major Function Definitions:
# -----------------------------------------------------------------------------
def connect_to_kernel(kernel_type, filename=''):
    """JupyterConnect"""
    global SI

    # Get number of column (used for pretty printing)
    SI.vim_column = vim.eval('&columns')

    # Create thread
    stop_thread()
    SI.thread = Thread(target=thread_connect_to_kernel,
                       args=(kernel_type, filename))
    SI.thread.start()

    # Launch timers: update echom
    for sleep_ms in (500, 1000, 1500, 2000, 3000):
        vim_cmd = ('let timer = timer_start(' + str(sleep_ms) +
                   ', "jupyter#UpdateEchom")')
        vim.command(vim_cmd)


def disconnect_from_kernel():
    """Disconnect kernel client."""
    if None is not SI.km_client: SI.km_client.stop_channels()
    vim_echom("Disconnected: {}".format(shorten_filename(SI.cfile)), style='Directory')


def update_console_msgs():
    """Grab pending messages and place them inside the vim console monitor."""
    global SI

    # Open the Jupyter terminal in vim, and move cursor to it
    b_nb = vim.eval('jupyter#OpenJupyterTerm()')
    if -1 == b_nb:
        vim_echom('__jupyter_term__ failed to open!', 'Error')
        return

    # Create thread
    thread_intervals = (10, 100)
    timer_intervals = (100, 400)
    stop_thread()
    SI.thread = Thread(target=thread_update_console_msgs, args=[thread_intervals])
    SI.thread.start()

    # Launch timers
    for sleep_ms in timer_intervals:
        vim_cmd = ('let timer = timer_start(' + str(sleep_ms) +
                   ', "jupyter#UpdateConsoleBuffer")')
        vim.command(vim_cmd)


def prettify_execute_intput(line_number, cmd):
    """Also used with my own input (as iperl does not send it back)"""
    prompt = SI.lang.prompt_in.format(line_number)
    s = prompt
    # add continuation line, if necessary
    dots = (' ' * (len(prompt.rstrip()) - 4)) + '...: '
    s += cmd.rstrip().replace('\n', '\n' + dots)
    return s


def handle_messages():
    """
    Message handler for Jupyter protocol.

    Takes all messages on the I/O Public channel, including stdout, stderr,
    etc.
    Returns: a list of the formatted strings of their content.

    See also: <http://jupyter-client.readthedocs.io/en/stable/messaging.html>
    """
    res = []
    msgs = SI.km_client.iopub_channel.get_msgs()
    for msg in msgs:
        s = ''
        if 'msg_type' not in msg['header']:
            continue
        msg_type = msg['header']['msg_type']

        if msg_type == 'status':
            # I don't care status (idle or busy)
            continue

        if msg_type == 'stream':
            # Get data
            text = strip_color_escapes(msg['content']['text'])
            line_number = msg['content'].get('execution_count', 0)
            # Set prompt
            if msg['content'].get('name', 'stdout') == 'stderr':
                prompt = 'StdErr [{:d}]: '.format(line_number)
                dots = (' ' * (len(prompt.rstrip()) - 4)) + '...x '
            else:
                prompt = 'StdOut [{:d}]: '.format(line_number)
                dots = (' ' * (len(prompt.rstrip()) - 4)) + '...< '
            s = prompt
            # Add continuation line, if necessary
            s += text.rstrip().replace('\n', '\n' + dots)

        elif msg_type == 'display_data':
            s += msg['content']['data']['text/plain']

        elif msg_type in ('execute_input', 'pyin'):
            line_number = msg['content'].get('execution_count', 0)
            cmd = msg['content']['code']
            s = prettify_execute_intput(line_number, cmd)

        elif msg_type in ('execute_result', 'pyout'):
            # Get the output
            s = SI.lang.prompt_out.format(msg['content']['execution_count'])
            s += msg['content']['data']['text/plain']

        elif msg_type in ('error', 'pyerr'):
            s = "\n".join(map(strip_color_escapes, msg['content']['traceback']))

        elif msg_type == 'input_request':
            vim_echom('python input not supported in vim.', 'Error')
            continue  # unsure what to do here... maybe just return False?

        else:
            vim_echom("Message type {} unrecognized!".format(msg_type))
            continue

        # List all messages
        res.append(s)

    return res


# -----------------------------------------------------------------------------
#        Thread Functions: vim function forbidden here:
#            could lead to segmentation fault
# -----------------------------------------------------------------------------
def thread_connect_to_kernel(kernel_type, filename=''):
    """Create kernel manager from existing connection file.
    Thread: <- stop
            -> cfile
    """
    from jupyter_client import KernelManager, find_connection_file
    global SI

    if SI.stop: SI.stop = False; return

    # Test if connection is alive
    connected = check_connection()
    attempt = 0
    max_attempts = 3
    while not connected and attempt < max_attempts:
        if SI.stop: SI.stop = False; return

        attempt += 1
        try:
            SI.cfile = find_connection_file(filename=filename)
        except IOError:
            thread_queue_message(
                "kernel connection attempt {:d}/{:d} failed - no kernel file"
                .format(attempt, max_attempts), style="Error")
            continue

        # Create the kernel manager and connect a client
        # See: <http://jupyter-client.readthedocs.io/en/stable/api/client.html>
        km = KernelManager(connection_file=SI.cfile)
        km.load_connection_file()
        SI.km_client = km.client()
        SI.km_client.start_channels()

        # Ping the kernel
        SI.km_client.kernel_info()
        try:
            SI.km_client.get_shell_msg(timeout=1)
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
        pp = PrettyPrinter(indent=4, width=SI.vim_column)
        kernel_string = pp.pformat(kernel_info)[4:-1]

        # # Echo message
        thread_queue_message('To: ', style='Question')
        thread_queue_message(kernel_string.replace('\"', '\\\"'), cmd='echom')

        # Send command so that user knows vim is connected at bottom, more readable
        thread_queue_message('Connected: {}'.format(shorten_filename(SI.cfile)), style='Question')

    else:
        if None is not SI.km_client: SI.km_client.stop_channels()
        thread_queue_message('kernel connection attempt timed out', style='Error')


def thread_update_console_msgs(intervals):
    """Update message that timer will append to console message
    Thread: <- stop
            -> io_pub
    """
    global SI

    io_cache = []
    for sleep_ms in intervals:
        if SI.stop: SI.stop = False; return
        # Get messages
        io_new = handle_messages()

        # Insert code line Check not already here (check with substr 'Py [')
        do_add_cmd = SI.cmd is not None
        do_add_cmd &= len(io_new) != 0
        do_add_cmd &= not any(SI.lang.prompt_in[:4] in msg for msg in io_new + io_cache)
        if do_add_cmd:
            # Get cmd number from id
            try:
                reply = get_reply_msg(SI.cmd_id)
                line_number = reply['content'].get('execution_count', 0)
            except(Empty, KeyError, TypeError):
                line_number = -1
            s = prettify_execute_intput(line_number, SI.cmd)
            io_new.insert(0, s)

        # Append just new
        SI.io_pub = [s for s in io_new if s not in io_cache]
        # Update cache
        io_cache = list(set().union(io_cache, io_new))

        # Sleep ms
        if SI.stop: SI.stop = False; return
        sleep(sleep_ms / 1000)


def thread_queue_message(arg, **args):
    """Wrap echo async: put message to be echo in a queue
    Thread: -> message_queue
    """
    SI.message_queue.put((arg, args))


def timer_echom_queue():
    """Call echom sync: all messages in queue"""
    # Check in
    if SI.message_queue.empty(): return

    # Show user the force
    while not SI.message_queue.empty():
        (arg, args) = SI.message_queue.get_nowait()
        vim_echom(arg, **args)

    # Restore peace in the galaxy
    vim.command('redraw')


def timer_write_console_msgs(b_nb):
    """Write kernel <-> vim messages to console buffer"""
    global SI

    # Check in
    if len(SI.io_pub) == 0: return

    # Get buffer (same indexes as vim)
    b = vim.buffers[b_nb]

    # Append mesage to jupyter terminal buffer
    for msg in SI.io_pub:
        b.append([PythonToVimStr(line) for line in msg.splitlines()])
    SI.io_pub = []

    # # Update view (moving cursor)
    cur_win = vim.eval('win_getid()')
    term_win = vim.eval('bufwinid({})'.format(str(b_nb)))
    vim.command('call win_gotoid({})'.format(term_win))
    vim.command('normal! G')
    vim.command('call win_gotoid({})'.format(cur_win))


# -----------------------------------------------------------------------------
#        Communicate with Kernel
# -----------------------------------------------------------------------------
def get_reply_msg(msg_id):
    """Get kernel reply from sent client message with msg_id.
    I can block 3 sec, so call me in a thread
    """
    # TODO handle 'is_complete' requests?
    # <http://jupyter-client.readthedocs.io/en/stable/messaging.html#code-completeness>
    for _ in range(3):
        try:
            reply = SI.km_client.get_shell_msg(block=True, timeout=1)
        except Empty:
            continue
        if reply['parent_header']['msg_id'] == msg_id:
            return reply
    return None


def print_prompt(prompt, msg_id=None):
    """Print In[] or In[56] style messages on Vim's display line."""
    if msg_id:
        # wait to get message back from kernel
        try:
            reply = get_reply_msg(msg_id)
            count = reply['content']['execution_count']
            vim_echom(SI.lang.prompt_in.format(count) + str(prompt))
        except Empty:
            # if the kernel is waiting for input it's normal to get no reply
            if not SI.km_client.stdin_channel.msg_ready():
                vim_echom(SI.lang.prompt_in.format(-1)
                          + '{} (no reply from Jupyter kernel)'.format(prompt))
    else:
        vim_echom("In[]: {}".format(prompt))


# Decorator for all sending commands
def with_console(fct):
    """
    Decorator for sending messages to the kernel. Conditionally monitor
    the kernel replies, as well as messages from other clients.
    """
    def wrapper(*args, **kwargs):
        if not check_connection():
            warn_no_connection()
            return
        monitor_console = bool(int(vim.vars.get('jupyter_monitor_console', 0)))
        fct(*args, **kwargs)
        if monitor_console:
            update_console_msgs()
    return wrapper


# Include verbose output to vim command line
def with_verbose(fct):
    """
    Decorator to receive message id from sending function, and report back to
    vim with output.
    """
    def wrapper(*args, **kwargs):
        verbose = bool(int(vim.vars.get('jupyter_verbose', 0)))
        (prompt, msg_id) = fct(*args, **kwargs)
        if verbose:
            print_prompt(prompt, msg_id=msg_id)
    return wrapper


@with_console
@with_verbose
def change_directory(directory):
    """CD: Change (current working) to directory
    """
    # Cd
    msg = SI.lang.cd.format(directory)
    msg_id = send(msg)

    # Print cwd
    try:
        cwd = get_res_from_code_string(SI.lang.cwd)
        vim_echom('CWD: ', style='Question')
        vim.command("echon \"{}\"".format(cwd))
    except Exception: pass

    # Return to decorators
    return (msg, msg_id)


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
    rang = vim.current.range
    lines = "\n".join(vim.current.buffer[rang.start:rang.end+1])
    msg_id = send(lines)
    prompt = "range {:d}-{:d} ".format(rang.start+1, rang.end+1)
    return (prompt, msg_id)


@with_console
@with_verbose
def run_cell():
    """Run all the code between two cell separators"""
    cur_buf = vim.current.buffer
    cur_line = vim.current.window.cursor[0] - 1

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
        kill(SI.kernel_pid, int(sig))
        vim_echom("kill pid {p:d} with signal #{v:d}, {n:s}"
                  .format(p=SI.kernel_pid, v=sig.value, n=sig.name), style='WarningMsg')
    except ProcessLookupError:
        vim_echom(("pid {p:d} does not exist! " +
                   "Kernel may have been terminated by outside process")
                  .format(p=SI.kernel_pid), style='Error')
    except OSError as err:
        vim_echom("signal #{v:d}, {n:s} failed to kill pid {p:d}"
                  .format(v=sig.value, n=sig.name, p=SI.kernel_pid), style='Error')
        raise err
