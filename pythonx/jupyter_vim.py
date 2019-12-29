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

"""
Jupyter-Vim interface, permit to send code to a jupyter kernel from a vim client

Install:
    You *must* install the jupyter package into the
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
    from queue import Empty
except ImportError:
    from Queue import Empty

try:
    # pylint: disable=unused-import
    import jupyter   # noqa
    from jupyter_client import KernelManager, find_connection_file
except ImportError as e:
    raise ImportError("Could not find kernel. " + __doc__, e)

try:
    import vim
except ImportError as e:
    raise ImportError('vim module only available within vim!', e)

# Local
from language import list_languages, get_language
from message_parser import parse_iopub_for_reply, unquote_string, str_to_py, \
    shorten_filename, vim_echom, warn_no_connection, thread_echom

# Standard
from os import kill, remove
from os.path import splitext
from platform import system
from signal import SIGTERM
if system() != 'Windows':
    from signal import SIGKILL
from textwrap import dedent
from threading import Thread
from time import sleep
import re


class SectionInfo():
    """Info relative to the jupyter <-> vim current section
    The only global object is of this class
    """
    def __init__(self):
        # Kernel
        # KernelManager client
        self.km_client = None
        # Connection file
        self.cfile = None
        # User argument to find running kernel
        self.filename_arg = ''
        # Kernel type string (or language)
        self.kernel_type = 'default'
        # Pid of the kernel
        self.kernel_pid = None
        # Language static class of the kernel (python || java || ...)
        # # implemented in ./language.py
        self.lang = get_language(self.kernel_type)
        # Last command sent and it's id
        self.cmd = None
        self.cmd_id = None
        self.cmd_count = 0

        # Vim
        # Pid of current vim section executing me
        self.vim_pid = vim.eval('getpid()')
        # Number of column of vim section
        # # will be setted at last sync moment
        self.vim_column = 80

        # Thread
        # Thread running
        self.thread = None
        # Should the current thread stop (cleanly)
        self.stop = False

    def send(self, msg, **kwargs):
        """Send a message to the kernel client
        Global: -> cmd, cmd_id
        """
        if self.km_client is None:
            vim_echom('kernel failed sending message, client not created'
                      '\ndid you run :JupyterConnect ?'
                      '\n msg to be sent : {}'.format(msg), style="Error")
            return -1

        # Include dedent of msg so we don't get odd indentation errors.
        self.cmd = dedent(msg)
        self.cmd_id = self.km_client.execute(self.cmd, **kwargs)

        return self.cmd_id


    def check_connection(self):
        """Check that we have a client connected to the kernel."""
        return self.km_client.hb_channel.is_beating() if self.km_client else False

    def check_stop(self):
        """Check and reset stop value"""
        last = self.stop
        if self.stop: self.stop = False
        return last

    def get_msgs(self):
        """Get pending message pool"""
        try:
            return self.km_client.iopub_channel.get_msgs()
        except (Empty, TypeError, KeyError, IndexError, ValueError):
            return []

    def get_reply_msg(self, msg_id):
        """Get kernel reply from sent client message with msg_id.
        I can block 3 sec, so call me in a thread
        """
        # TODO handle 'is_complete' requests?
        # <http://jupyter-client.readthedocs.io/en/stable/messaging.html#code-completeness>
        for _ in range(3):
            if self.stop: return None
            try:
                reply = self.km_client.get_shell_msg(block=True, timeout=1)
            except (Empty, TypeError, KeyError, IndexError, ValueError):
                continue
            if reply['parent_header']['msg_id'] == msg_id:
                return reply
        return None

    def get_kernel_info(self):
        """Explicitly ask the jupyter kernel for its pid
        Thread: <- cfile
                <- vim_pid
                -> lang
                -> kernel_pid
        Returns: dict with 'kernel_type', 'pid', 'cwd', 'hostname'
        """
        # Check in
        if self.kernel_type not in list_languages():
            vim_echom('I don''t know how to get infos for a Jupyter kernel of'
                      ' type "{}"'.format(self.kernel_type), 'WarningMsg')

        # Get language
        self.lang = get_language(self.kernel_type)

        # Set kernel type
        res = {'kernel_type': self.kernel_type}

        # Get full connection file
        res['connection_file'] = self.cfile

        # Get kernel id
        res['id'] = shorten_filename(self.cfile)

        # Get pid
        try: res['pid'] = self.send_code_and_get_reply(self.lang.pid)
        except Exception: res['pid'] = -1
        self.kernel_pid = res['pid']

        # Get cwd
        try: res['cwd'] = self.send_code_and_get_reply(self.lang.cwd)
        except Exception: res['cwd'] = 'unknown'

        # Get hostname
        try: res['hostname'] = self.send_code_and_get_reply(self.lang.hostname)
        except Exception: res['hostname'] = 'unknown'

        # Print vim connected
        hi_string = '\\n\\n'
        hi_string += 'Received connection from vim client with pid ' + self.vim_pid
        hi_string += '\\n' + '-' * 60 + '\\n'
        self.send_code_and_get_reply(self.lang.print_string.format(hi_string))

        # Return
        return res

    def set_from_connect_attempt(self, kernel_type, filename):
        """Set what can when user calls JupyterConnect"""
        self.kernel_type = kernel_type
        self.filename_arg = filename

    def set_vim_column(self):
        """Set vim column number <- vim"""
        self.vim_column = vim.eval('&columns')

    def set_cfile(self):
        """Set connection file from argument"""
        self.cfile = find_connection_file(filename=self.filename_arg)

    def set_cmd_count(self, num):
        """Set command count number, to record it if wanted (console buffer)"""
        self.cmd_count = num

    def connect_new_client(self):
        """Create the kernel manager and connect a client
        See: <http://jupyter-client.readthedocs.io/en/stable/api/client.html>
        """
        # Get client
        km = KernelManager(connection_file=self.cfile)
        km.load_connection_file()
        self.km_client = km.client()

        # Open channel
        self.km_client.start_channels()

        # Ping the kernel
        self.km_client.kernel_info()
        try:
            self.km_client.get_shell_msg(timeout=1)
            return True
        except Empty:
            return False

    def send_code_and_get_reply(self, code):
        """Helper: Get variable _res from code string (setting _res)"""
        res = None

        # Send message
        msg_id = self.send(code, silent=False, user_expressions={'_res': '_res'})

        # Wait to get message back from kernel (1 sec)
        try:
            reply = self.get_reply_msg(msg_id)
            line_number = reply['content'].get('execution_count', -1)
        except (Empty, KeyError, TypeError):
            line_number = -1

        # Parse response
        try:
            # Requires the fix for https://github.com/JuliaLang/IJulia.jl/issues/815
            res = reply['content']['user_expressions']['_res']['data']['text/plain']
        except (TypeError, KeyError): pass

        if None is res:
            msgs = self.get_msgs()
            parse_iopub_for_reply(msgs, line_number)

        # Game over
        if None is res: res = -1

        # Convert
        res = unquote_string(res)
        if re.match(r'[-+]?\d+$', res) is not None:
            res = int(res)

        # Rest in peace
        return res

    def stop_thread(self):
        """Stop current thread"""
        if self.thread is None: return
        if not self.thread.isAlive(): self.thread = None; return

        # Wait 1 sec max
        self.stop = True
        for _ in range(100):
            if not self.stop: sleep(0.010)
        self.thread = None
        return

    def start_thread(self, target=None, args=None):
        """Stop last / Create new / Start thread"""
        if args is None: args = []
        self.stop_thread()
        self.thread = Thread(target=target, args=args)
        self.thread.start()

# -----------------------------------------------------------------------------
#        Utilities
# -----------------------------------------------------------------------------


def is_cell_separator(line):
    """ Determine whether a given line is a cell separator """
    # TODO allow users to define their own cell separators
    cell_sep = ('##', '#%%', '# %%', '# <codecell>')
    return line.startswith(cell_sep)


# -----------------------------------------------------------------------------
#        Major Function Definitions:
# -----------------------------------------------------------------------------
# if module has not yet been imported, define global kernel manager, client and
# kernel pid. Otherwise, just check that we're connected to a kernel.
if 'SI' not in globals():
    SI = SectionInfo()
else:
    if not SI.check_connection():
        warn_no_connection()


def connect_to_kernel(kernel_type, filename=''):
    """:JupyterConnect"""
    # Set what can
    SI.set_from_connect_attempt(kernel_type, filename)

    # Get number of column (used for pretty printing)
    SI.set_vim_column()

    # Create thread
    SI.start_thread(target=thread_connect_to_kernel)

    # Launch timers: update echom
    for sleep_ms in (500, 1000, 1500, 2000, 3000):
        vim_cmd = ('let timer = timer_start(' + str(sleep_ms) +
                   ', "jupyter#UpdateEchom")')
        vim.command(vim_cmd)


def disconnect_from_kernel():
    """:JupyterDisconnect kernel client (Sync)"""
    if SI.km_client is not None: SI.km_client.stop_channels()
    vim_echom("Disconnected: {}".format(shorten_filename(SI.cfile)), style='Directory')


def signal_kernel(sig=SIGTERM):
    """:JupyterTerminateKernel
    Use kill command to send a signal to the remote kernel.
    This side steps the (non-functional) jupyter interrupt mechanisms.
    Only works on posix.
    """
    # Kill process
    try:
        # Check if valid pid
        if SI.kernel_pid < 1:
            vim_echom("Cannot kill kernel: unknown pid", style='Error')
        else:
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

    # Delete connection file
    sig_list = [SIGTERM];
    sig_list.append(SIGKILL) if system() != 'Windows' else None
    if sig in sig_list:
        try:
            remove(SI.cfile)
        except OSError:
            pass


def run_file(flags='', filename=''):
    """:JupyterRunFile"""
    # Special cpython cases
    if SI.kernel_type == 'python':
        return run_file_in_ipython(flags=flags, filename=filename)

    # Message warning to user
    if flags != '':
        vim_echom('RunFile in other kernel than "python" doesn\'t support flags.'
                  ' All arguments except the last (file location) will be ignored.',
                  style='Error')

    # Get command and slurp file if not implemented
    cmd_run = SI.lang.run_file.format(filename)
    if cmd_run == '-1':
        with open(filename, 'r') as file_run:
            cmd_run = file_run.read()

    # Run it
    return run_command(cmd_run)


# -----------------------------------------------------------------------------
#        Thread Functions: vim function forbidden here:
#            could lead to segmentation fault
# -----------------------------------------------------------------------------
def thread_connect_to_kernel():
    """Create kernel manager from existing connection file (Async)"""
    if SI.check_stop(): return

    # Test if connection is alive
    connected = SI.check_connection()
    attempt = 0
    max_attempts = 3
    while not connected and attempt < max_attempts:
        attempt += 1
        if SI.check_stop(): return

        # Get cfile
        try:
            SI.set_cfile()
        except IOError:
            thread_echom(
                "kernel connection attempt {:d}/{:d} failed - no kernel file"
                .format(attempt, max_attempts), style="Error")
            continue

        # Connect
        if SI.connect_new_client():
            connected = True

    if connected:
        # Collect kernel info
        kernel_info = SI.get_kernel_info()

        # More info (anyway screen is redrawn)
        #  # Prettify output: appearance rules
        from pprint import PrettyPrinter
        pp = PrettyPrinter(indent=4, width=SI.vim_column)
        kernel_string = pp.pformat(kernel_info)[4:-1]

        # # Echo message
        thread_echom('To: ', style='Question')
        thread_echom(kernel_string.replace('\"', '\\\"'), cmd='echom')

        # Send command so that user knows vim is connected at bottom, more readable
        thread_echom('Connected: {}'.format(shorten_filename(SI.cfile)), style='Question')

    else:
        if None is not SI.km_client: SI.km_client.stop_channels()
        thread_echom('kernel connection attempt timed out', style='Error')


# -----------------------------------------------------------------------------
#        Communicate with Kernel
# -----------------------------------------------------------------------------
def monitorable(fct):
    """Decorator to monitor messages"""
    def wrapper(*args, **kwargs):
        # Check
        if not SI.check_connection():
            warn_no_connection()
            return

        # Call
        last_cmd = fct(*args, **kwargs)[0]

        # Verbose: receive message id from sending function
        # and report back to vim with output.
        verbose = bool(int(vim.vars.get('jupyter_verbose', 0)))
        # Monitor: the kernel replies, as well as messages from other clients.
        monitor_console = bool(int(vim.vars.get('jupyter_monitor_console', 0)))
        if not verbose and not monitor_console:
            return

        # Launch update threads
        from monitor_console import update_msgs
        update_msgs(SI, last_cmd=last_cmd, verbose=verbose, console=monitor_console)
    return wrapper


@monitorable
def change_directory(directory):
    """CD: Change (current working) to directory
    """
    # Cd
    msg = SI.lang.cd.format(directory)
    msg_id = SI.send(msg)

    # Print cwd
    try:
        cwd = SI.send_code_and_get_reply(SI.lang.cwd)
        vim_echom('CWD: ', style='Question')
        vim.command("echon \"{}\"".format(cwd))
    except Exception: pass

    # Return to decorators
    return (msg, msg_id)


@monitorable
def run_command(cmd):
    """Send a single command to the kernel."""
    msg_id = SI.send(cmd)
    return (cmd, msg_id)


@monitorable
def run_file_in_ipython(flags='', filename=''):
    """Run a given python file using ipython's %run magic."""
    ext = splitext(filename)[-1][1:]
    if ext in ('pxd', 'pxi', 'pyx', 'pyxbld'):
        run_cmd = '%run_cython'
        params = str_to_py(vim.vars.get('cython_run_flags', ''))
    else:
        run_cmd = '%run'
        params = flags or str_to_py(vim.current.buffer.vars['ipython_run_flags'])
    cmd = '{run_cmd} {params} "{filename}"'.format(
        run_cmd=run_cmd, params=params, filename=filename)
    msg_id = SI.send(cmd)
    return (cmd, msg_id)


@monitorable
def send_range():
    """Send a range of lines from the current vim buffer to the kernel."""
    rang = vim.current.range
    lines = "\n".join(vim.current.buffer[rang.start:rang.end+1])
    msg_id = SI.send(lines)
    prompt = "range {:d}-{:d} ".format(rang.start+1, rang.end+1)
    return (prompt, msg_id)


@monitorable
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
    msg_id = SI.send(lines)
    prompt = "execute lines {:d}-{:d} ".format(upper_bound+1, lower_bound+1)
    return (prompt, msg_id)
