#=============================================================================
#    File: pythonx/jupyter_vim.py
# Created: 07/28/11 22:14:58
#  Author: Paul Ivanov (http://pirsquared.org)
#  Updated: [11/13/2017] Marijn van Vliet
#  Updated: [02/14/2018, 12:31] Bernie Roesler
#
# Description:
"""
Python code for ftplugin/python/jupyter.vim.
"""
#=============================================================================

from __future__ import print_function
import os
import re
import signal
import sys

import textwrap
from queue import Empty

_install_instructions = """You *must* install IPython into the Python that
your vim is linked against. If you are seeing this message, this usually means
either (1) installing IPython using the system Python that vim is using, or
(2) recompiling Vim against the Python where you already have IPython
installed. This is only a requirement to allow Vim to speak with an IPython
instance using IPython's own machinery. It does *not* mean that the IPython
instance with which you communicate via vim-ipython needs to be running the
same version of Python.
"""

try:
    import IPython
except ImportError:
    raise ImportError("Could not find kernel. " + _install_instructions)

try:
    import vim
except ImportError:
    raise ImportError('vim module only available within vim!')

#------------------------------------------------------------------------------
#        Read global configuration variables
#------------------------------------------------------------------------------
is_py3 = sys.version_info[0] >= 3
if is_py3:
    unicode = str

prompt_in  = 'In [{line:d}]: '
prompt_out = 'Out[{line:d}]: '

# General message command
def vim_echom(arg, style="None"):
    """
    Report string `arg` using vim's echomessage command.

    Keyword args:
    style -- the vim highlighting style to use
    """
    try:
        vim.command("echohl {}".format(style))
        vim.command("echom \"{}\"".format(arg.replace('\"', '\\\"')))
        vim.command("echohl None")
    except vim.error:
        print("-- {}".format(arg))

#------------------------------------------------------------------------------
#        Check Connection:
#------------------------------------------------------------------------------
def check_connection():
    """Check that we have a client connected to the kernel."""
    return kc.hb_channel.is_beating() if kc else False

# if module has not yet been imported, define global kernel manager, client and
# kernel pid. Otherwise, just check that we're connected to a kernel.
if all([x in globals() for x in ('kc', 'pid', 'send')]):
    if not check_connection():
        vim_echom('WARNING: Not connected to IPython!' + \
                  ' Run :JupyterConnect to find the kernel', style='WarningMsg')
else:
    kc = None
    pid = None
    send = None

#------------------------------------------------------------------------------
#        Utilities
#------------------------------------------------------------------------------
# Define wrapper for encoding
# get around unicode problems when interfacing with vim
vim_encoding = vim.eval('&encoding') or 'utf-8'

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
        # support is pretty bad. don't ask how I came up with this... It just
        # works...
        # It seems to be related to that bug: http://bugs.python.org/issue5876
        if unicode is str:
            s = self
        else:
            s = self.encode('UTF-8')
        return '"%s"' % s.replace('\\', '\\\\').replace('"', r'\"')

def set_pid():
    """Explicitly ask the ipython kernel for its pid."""
    the_pid = -1
    code = 'import os; _pid = os.getpid()'
    msg_id = send(code, silent=True, user_expressions={'_pid':'_pid'})

    # wait to get message back from kernel
    try:
        reply = get_reply_msg(msg_id)
    except Empty:
        vim_echom("no reply from IPython kernel", "WarningMsg")
        return -1

    try:
        the_pid = int(reply['content']['user_expressions']\
                        ['_pid']['data']['text/plain'])
    except KeyError:
        vim_echom("Could not get PID information, kernel not running Python?")

    return the_pid

def is_cell_separator(line):
    """ Determine whether a given line is a cell separator """
    # TODO allow users to define their own cell separators
    cell_sep = ('##', '#%%', '# %%', '# <codecell>')
    return line.startswith(cell_sep)

# from <http://serverfault.com/questions/71285/\
# in-centos-4-4-how-can-i-strip-escape-sequences-from-a-text-file>
strip = re.compile(r'\x1B\[([0-9]{1,2}(;[0-9]{1,2})*)?[mK]')
def strip_color_escapes(s):
    """Remove ANSI color escape sequences from a string."""
    return strip.sub('', s)

#------------------------------------------------------------------------------
#        Major Function Definitions:
#------------------------------------------------------------------------------
def connect_to_kernel():
    """Create kernel manager from existing connection file."""
    from jupyter_client import KernelManager, find_connection_file

    global kc, pid, send

    # Test if connection is alive
    connected = check_connection()
    attempt = 0
    max_attempts = 3
    while not connected and attempt < max_attempts:
        attempt += 1
        try:
            cfile = find_connection_file()  # default filename='kernel-*.json'
        except IOError:
            vim_echom("kernel connection attempt {:d} failed - no kernel file"\
                      .format(attempt), style="Error")
            continue

        # Create the kernel manager and connect a client
        # See: <http://jupyter-client.readthedocs.io/en/stable/api/client.html>
        km = KernelManager(connection_file=cfile)
        km.load_connection_file()
        kc = km.client()
        kc.start_channels()

        # Alias execute function
        def _send(msg, **kwargs):
            """Send a message to the kernel client."""
            # Include dedent of msg so we don't get odd indentation errors.
            return kc.execute(textwrap.dedent(msg), **kwargs)
        send = _send

        # Ping the kernel
        kc.kernel_info()
        try:
            reply = kc.get_shell_msg(timeout=1)
        except Empty:
            continue
        else:
            connected = True

    if connected:
        # Send command so that monitor knows vim is commected
        # send('"_vim_client"', store_history=False)
        pid = set_pid() # Ask kernel for its PID
        vim_echom('kernel connection successful! pid = {}'.format(pid),
                  style='Question')
    else:
        kc.stop_channels()
        vim_echom('kernel connection attempt timed out', style='Error')

def disconnect_from_kernel():
    """Disconnect kernel client."""
    kc.stop_channels()
    vim_echom("Client disconnected from kernel with pid = {}".format(pid))

def update_console_msgs():
    """Grab pending messages and place them inside the vim console monitor."""
    # Save which window we're in
    cur_win = vim.eval('win_getid()')

    # Open the ipython terminal in vim, and move cursor to it
    is_console_open = vim.eval('jupyter#OpenJupyterTerm()')
    if not is_console_open:
        vim_echom('__jupyter_term__ failed to open!', 'Error')
        return

    # Append the I/O to the console buffer
    io_pub = handle_messages()
    b = vim.current.buffer
    for msg in io_pub:
        b.append([PythonToVimStr(l) for l in msg.splitlines()])
    vim.command('normal! G')

    # Move cursor back to original window
    vim.command(':call win_gotoid({})'.format(cur_win))

def handle_messages():
    """
    Message handler for Jupyter protocol.

    Takes all messages on the I/O Public channel, including stdout, stderr,
    etc. and returns a list of the formatted strings of their content.

    See also: <http://jupyter-client.readthedocs.io/en/stable/messaging.html>
    """
    io_pub = []
    msgs = kc.iopub_channel.get_msgs(block=False)
    for msg in msgs:
        s = ''
        if 'msg_type' not in msg['header']:
            continue
        msg_type = msg['header']['msg_type']
        if msg_type == 'status':
            continue
        elif msg_type == 'stream':
            # TODO: alllow for distinguishing between stdout and stderr (using
            # custom syntax markers in the vim-ipython buffer perhaps), or by
            # also echoing the message to the status bar
            s = strip_color_escapes(msg['content']['text'])
        elif msg_type == 'display_data':
            s += msg['content']['data']['text/plain']
        elif msg_type == 'pyin' or msg_type == 'execute_input':
            line_number = msg['content'].get('execution_count', 0)
            prompt = prompt_in.format(line=line_number)
            s = prompt
            # add continuation line, if necessary
            dots = (' ' * (len(prompt.rstrip()) - 4)) + '...: '
            s += msg['content']['code'].rstrip().replace('\n', '\n' + dots)
        elif msg_type == 'pyout' or msg_type == 'execute_result':
            s = prompt_out.format(line=msg['content']['execution_count'])
            s += msg['content']['data']['text/plain']
        elif msg_type == 'pyerr' or msg_type == 'error':
            s = "\n".join(map(strip_color_escapes, msg['content']['traceback']))
        elif msg_type == 'input_request':
            vim_echom('python input not supported in vim.', 'Error')
            continue # unsure what to do here... maybe just return False?
        else:
            vim_echom("Message type {} unrecognized!".format(msg_type))
            continue

        # List all messages
        io_pub.append(s)

    return io_pub

#------------------------------------------------------------------------------
#        Communicate with Kernel
#------------------------------------------------------------------------------
def get_reply_msg(msg_id):
    """Get kernel reply from sent client message with msg_id."""
    # TODO handle 'is_complete' requests?
    # <http://jupyter-client.readthedocs.io/en/stable/messaging.html#code-completeness>
    while True:
        try:
            # TODO try block=False
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
            vim_echom("In[{:d}]: {:s}".format(count, prompt))
        except Empty:
            # if the kernel is waiting for input it's normal to get no reply
            if not kc.stdin_channel.msg_ready():
                vim_echom("In[]: {} (no reply from IPython kernel)"\
                          .format(prompt))
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
            vim_echom('WARNING: Not connected to IPython!', 'WarningMsg')
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

@with_console
@with_verbose
def run_command(cmd):
    """Send a single command to the kernel."""
    msg_id = send(cmd)
    return (cmd, msg_id)

@with_console
@with_verbose
def run_file(flags='', filename=''):
    """Run a given python file using ipython's %run magic."""
    ext = os.path.splitext(filename)[-1][1:]
    if ext in ('pxd', 'pxi', 'pyx', 'pyxbld'):
        cmd = ' '.join(filter(None, (
            '%run_cython',
            vim2py_str(vim.vars.get('cython_run_flags', '')),
            repr(filename))))
    else:
        b = vim.current.buffer
        cmd = '%run {} {}'.format((flags or vim2py_str(b.vars['ipython_run_flags'])),
                                  repr(filename))
    msg_id = send(cmd)
    return (cmd, msg_id)

@with_console
@with_verbose
def send_range():
    """Send a range of lines from the current vim buffer to the kernel."""
    r = vim.current.range
    lines = "\n".join(vim.current.buffer[r.start:r.end+1])
    msg_id = send(lines)
    prompt = "range %d-%d "% (r.start+1, r.end+1)
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

def signal_kernel(sig=signal.SIGTERM):
    """
    Use kill command to send a signal to the remote kernel. This side steps the
    (non-functional) ipython interrupt mechanisms.
    Only works on posix.
    """
    try:
        os.kill(pid, int(sig))
        vim_echom("kill pid {p:d} with signal #{v:d}, {n:s}"\
                  .format(p=pid, v=sig.value, n=sig.name), style='WarningMsg')
    except ProcessLookupError:
        vim_echom(("pid {p:d} does not exist! " +
                   "Kernel may have been terminated by outside process")\
                  .format(p=pid), style='Error')
    except OSError as e:
        vim_echom("signal #{v:d}, {n:s} failed to kill pid {p:d}"\
                  .format(v=sig.value, n=sig.name, p=pid), style='Error')
        raise e

#def set_breakpoint():
#    send("__IP.InteractiveTB.pdb.set_break('%s',%d)" % (vim.current.buffer.name,
#                                                        vim.current.window.cursor[0]))
#    print("set breakpoint in %s:%d"% (vim.current.buffer.name,
#                                      vim.current.window.cursor[0]))
#
#def clear_breakpoint():
#    send("__IP.InteractiveTB.pdb.clear_break('%s',%d)" % (vim.current.buffer.name,
#                                                          vim.current.window.cursor[0]))
#    print("clearing breakpoint in %s:%d" % (vim.current.buffer.name,
#                                            vim.current.window.cursor[0]))
#
#def clear_all_breakpoints():
#    send("__IP.InteractiveTB.pdb.clear_all_breaks()");
#    print("clearing all breakpoints")
#
#def run_this_file_pdb():
#    send(' __IP.InteractiveTB.pdb.run(\'execfile("%s")\')' % (vim.current.buffer.name,))
#    #send('run -d %s' % (vim.current.buffer.name,))
#    echo("In[]: run -d %s (using pdb)" % vim.current.buffer.name)


#==============================================================================
#==============================================================================
