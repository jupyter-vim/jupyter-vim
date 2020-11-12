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
    # pylint: disable=unused-import
    import jupyter   # noqa
except ImportError as e:
    raise ImportError("Could not import jupyter.\n(The original ImportError: {})\n{}"
                      .format(e, __doc__))

try:
    import vim
except ImportError as e:
    raise ImportError('vim module only available within vim! The original ImportError: ' + str(e))

# Standard
import functools
from os import kill, remove
from os.path import splitext
from platform import system
import signal

from jupyter_client import find_connection_file

# Local
from jupyter_util import str_to_py, echom, is_integer
from language import get_language
from message_parser import VimMessenger, JupyterMessenger, Sync
from monitor_console import Monitor, monitor_decorator


# TODO
#   * Rename `Monitor` -> 'JupyterMonitor`
#   * Rename `Sync` -> 'JupyterSync`
#   * docstrings!!
class JupyterVimSession():
    """Object containing jupyter <-> vim session info.

    This object is created in lieu of individual functions so that a single vim
    session can connect to multiple Jupyter kernels at once. Each connection
    gets a new JupyterVimSession object.

    Attributes
    ----------
    sync : :obj:`Sync`
        Object to support asynchronous operations.
    kernel_client : :obj:`JupyterMessenger`
        Object to handle primitive messaging between vim and the jupyter kernel.
    vim_client : :obj:`VimMessenger`
        Object to handle messaging between python and vim.
    monitor : :obj:`Monitor`
        Jupyter kernel monitor buffer and message line.
    lang : :obj:`Language`
        User-defined Language object corresponding to desired kernel type.
    """
    def __init__(self):
        self.sync = Sync()
        self.kernel_client = JupyterMessenger(self.sync)
        self.vim_client = VimMessenger(self.sync)
        self.monitor = Monitor(self)
        self.lang = get_language('')

    def if_connected(fct):
        """Decorator, fail if not connected."""
        # pylint: disable=no-self-argument, not-callable, no-member
        @functools.wraps(fct)
        def wrapper(self, *args, **kwargs):
            if not self.kernel_client.check_connection_or_warn():
                echom(f"Pythonx _jupyter_session.{fct.__name__}() needs a connected client",
                      style='Error')
                return None
            return fct(self, *args, **kwargs)
        return wrapper

    def connect_to_kernel(self, kernel_type, filename=''):
        """Establish a connection with the specified kernel type.

        .. note:: vim command `:JupyterConnect`

        Parameters
        ----------
        kernel_type : str
            Type of kernel, i.e. `python3` with which to connect.
        filename : str, optional, default=''
            Specific kernel connection filename, i.e.
                ``$(jupyter --runtime)/kernel-123.json``
        """
        self.kernel_client.kernel_info['kernel_type'] = kernel_type
        self.kernel_client.kernel_info['cfile_user'] = filename
        self.lang = get_language(kernel_type)

        # Create thread
        self.sync.start_thread(target=self.thread_connect_to_kernel)

        # Launch timers: update echom
        for sleep_ms in self.vim_client.get_timer_intervals():
            vim_cmd = ('let timer = timer_start(' + str(sleep_ms) +
                       ', "jupyter#UpdateEchom")')
            vim.command(vim_cmd)

    @if_connected
    def disconnect_from_kernel(self):
        """Disconnect from the kernel client (Sync).

        .. note:: vim command `:JupyterDisconnect`.
        """
        self.kernel_client.disconnnect()
        echom(f"Disconnected: {self.kernel_client.kernel_info['id']}", style='Directory')

    @if_connected
    def signal_kernel(self, sig=signal.SIGTERM):
        """Send a signal to the remote kernel via the kill command.

        This command side steps the non-functional jupyter interrupt.
        Only works on posix.

        .. note:: vim command `:JupyterTerminateKernel`

        Parameters
        ----------
        sig : :obj:`signal`, optional, default=signal.SIGTERM
            Signal to send to the kernel.
        """
        # Clause: valid signal
        if isinstance(sig, str):
            try:
                sig = getattr(signal, sig)
            except Exception as e:
                echom(f"Cannot send signal {sig} on this OS: {e}", style='Error')
                return

        # Clause: valid pid
        pid = self.kernel_client.kernel_info['pid']
        if not is_integer(pid):
            echom(f"Cannot kill kernel: pid is not a number {pid}", style='Error')
            return
        pid = int(pid)
        if pid < 1:
            echom(f"Cannot kill kernel: unknown pid retrieved {pid}", style='Error')
            return

        # Kill process
        try:
            kill(pid, int(sig))
            echom("kill pid {p:d} with signal #{v:d}, {n:s}"
                  .format(p=pid, v=sig.value, n=sig.name), style='WarningMsg')
        except ProcessLookupError:
            echom(("pid {p:d} does not exist! " +
                   "Kernel may have been terminated by outside process")
                  .format(p=pid, style='Error'))
        except OSError as err:
            echom("signal #{v:d}, {n:s} failed to kill pid {p:d}"
                  .format(v=sig.value, n=sig.name, p=pid), style='Error')
            raise err

        # Delete connection file
        sig_list = [signal.SIGTERM]
        if system() != 'Windows':
            sig_list.append(signal.SIGKILL)
        if sig in sig_list:
            try:
                remove(self.kernel_client.cfile)
            except OSError:
                pass

    @if_connected
    def run_file(self, flags='', filename=''):
        """Run an entire file in the kernel.

        .. note:: vim command `:JupyterRunFile`.

        Parameters
        ----------
        flags : str, optional, default=''
            Flags to pass with language-specific `run` command.
        filename : str, optional, default=''
            Specific filename to run.
        """
        # Special cpython cases
        if self.kernel_client.kernel_info['kernel_type'] == 'python':
            return self.run_file_in_ipython(flags=flags, filename=filename)

        # Message warning to user
        if flags != '':
            echom('RunFile in other kernel than "python" doesn\'t support flags.'
                  ' All arguments except the file location will be ignored.',
                  style='Error')

        # Get command and read file if not implemented
        cmd_run = self.lang.run_file.format(filename)
        if cmd_run == '-1':
            with open(filename, 'r') as file_run:
                cmd_run = file_run.read()

        # Run it
        return self.run_command(cmd_run)

    # -----------------------------------------------------------------------------
    #        Thread Functions: vim function forbidden here:
    #            could lead to segmentation fault
    # -----------------------------------------------------------------------------
    def thread_connect_to_kernel(self):
        """Create kernel manager from existing connection file (Async)."""
        if self.sync.check_stop():
            return

        # Check if connection is alive
        connected = self.kernel_client.check_connection()

        # Try to connect
        MAX_ATTEMPTS = 3
        for attempt in range(MAX_ATTEMPTS):
            # NOTE if user tries to :JupyterConnect <new_pid>, this check will ignore
            # the requested new pid.
            if connected:
                break
            # Check if thread want to return
            if self.sync.check_stop():
                return

            # Find connection file
            try:
                self.kernel_client.cfile = find_connection_file(
                    filename=self.kernel_client.kernel_info['cfile_user'])
            except IOError:
                self.vim_client.thread_echom(
                    "kernel connection attempt {:d}/{:d} failed - no kernel file"
                    .format(attempt, MAX_ATTEMPTS), style="Error")
                continue

            # Connect
            connected = self.kernel_client.create_kernel_manager()

        # Early return if failed
        if not connected:
            self.kernel_client.disconnnect()
            self.vim_client.thread_echom('kernel connection attempt timed out', style='Error')
            return

        # Pre-message the user
        self.vim_client.thread_echom('Connected! ', style='Question')

        # Collect and echom kernel info
        self.vim_client.thread_echom_kernel_info(self.kernel_client.get_kernel_info(self.lang))

        # TODO only if verbose
        # Print vim connected -> client
        # cmd_hi = self.lang.print_string.format(self.vim_client.string_hi())
        # self.kernel_client.send(cmd_hi)

    # -----------------------------------------------------------------------------
    #        Communicate with Kernel
    # -----------------------------------------------------------------------------
    @if_connected
    def update_monitor_msgs(self):
        """Update monitor buffer if present"""
        self.monitor.update_msgs()

    @if_connected
    @monitor_decorator
    def change_directory(self, directory):
        """Change current working directory in kernel.

        .. note:: vim command `:JupyterCd`.

        Parameters
        ----------
        directory : str
            Directory into which to change.
        """
        msg = self.lang.cd.format(directory)
        msg_id = self.kernel_client.send(msg)

        # Print cwd
        try:
            cwd = self.kernel_client.send_code_and_get_reply(self.lang.cwd)
            echom('CWD: ', style='Question')
            vim.command("echon \"{}\"".format(cwd))
        except Exception:
            pass

        # Return to decorators
        return (msg, msg_id)

    @if_connected
    @monitor_decorator
    def run_command(self, cmd):
        """Send a single command to the kernel.

        .. note:: vim command `:JupyterSendCode`.

        Parameters
        ----------
        cmd : str
            Lines of code to send to the kernel.
        """
        self.kernel_client.update_meta_messages()
        msg_id = self.kernel_client.send(cmd)
        return (cmd, msg_id)

    @if_connected
    @monitor_decorator
    def run_file_in_ipython(self, flags='', filename=''):
        """Run a given python file using ipython's %run magic.

        .. note:: vim command `:JupyterRunFile`.

        Parameters
        ----------
        flags : str, optional, default=''
            Flags to pass with language-specific `run` command.
        filename : str, optional, default=''
            Specific filename to run.
        """
        ext = splitext(filename)[-1][1:]
        if ext in ('pxd', 'pxi', 'pyx', 'pyxbld'):
            run_cmd = '%run_cython'
            params = str_to_py(vim.vars.get('cython_run_flags', ''))
        else:
            run_cmd = '%run'
            params = flags or str_to_py(vim.current.buffer.vars['ipython_run_flags'])
        cmd = '{run_cmd} {params} "{filename}"'.format(
            run_cmd=run_cmd, params=params, filename=filename)
        msg_id = self.run_command(cmd)
        return (cmd, msg_id)

    @if_connected
    @monitor_decorator
    def send_range(self):
        """Send a range of lines from the current vim buffer to the kernel.

        .. note:: vim command `:JupyterSendRange`.
        """
        rang = vim.current.range
        lines = "\n".join(vim.current.buffer[rang.start:rang.end+1])
        msg_id = self.run_command(lines)
        prompt = "range {:d}-{:d} ".format(rang.start+1, rang.end+1)
        return (prompt, msg_id)

    @if_connected
    @monitor_decorator
    def run_cell(self):
        """Run all the code between two cell separators.

        .. note:: vim command `:JupyterSendCell`.
        """
        # Get line and buffer and cellseparators
        cur_buf = vim.current.buffer
        cur_line = vim.current.window.cursor[0] - 1
        self.vim_client.set_cell_separators()

        # Search upwards for cell separator
        upper_bound = cur_line
        while upper_bound > 0 and not self.vim_client.is_cell_separator(cur_buf[upper_bound]):
            upper_bound -= 1

        # Skip past the first cell separator if it exists
        if self.vim_client.is_cell_separator(cur_buf[upper_bound]):
            upper_bound += 1

        # Search downwards for cell separator
        lower_bound = min(upper_bound+1, len(cur_buf)-1)

        while lower_bound < len(cur_buf)-1 and \
                not self.vim_client.is_cell_separator(cur_buf[lower_bound]):
            lower_bound += 1

        # Move before the last cell separator if it exists
        if self.vim_client.is_cell_separator(cur_buf[lower_bound]):
            lower_bound -= 1

        # Make sure bounds are within buffer limits
        upper_bound = max(0, min(upper_bound, len(cur_buf)-1))
        lower_bound = max(0, min(lower_bound, len(cur_buf)-1))

        # Make sure of proper ordering of bounds
        lower_bound = max(upper_bound, lower_bound)

        # Execute cell
        lines = "\n".join(cur_buf[upper_bound:lower_bound+1])
        msg_id = self.run_command(lines)
        prompt = "execute lines {:d}-{:d} ".format(upper_bound+1, lower_bound+1)
        return (prompt, msg_id)
