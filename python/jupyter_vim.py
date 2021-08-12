##############################################################################
#    File: pythonx/jupyter_vim.py
# Created: 07/28/11 22:14:58
#  Author: Paul Ivanov (http://pirsquared.org)
#  Updated: [11/13/2017] Marijn van Vliet
#  Updated: [02/14/2018, 12:31] Bernie Roesler
#  Updated: [15/12/2019] Tinmarino
#  Updated: [02/08/2021] Marijn van Vliet
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
except ImportError as e_import:
    raise ImportError("Could not import jupyter.\n(The original ImportError: {})\n{}"
                      .format(e_import, __doc__)) from e_import

try:
    import vim
except ImportError as e_import:
    raise ImportError('vim module only available within vim! The original ImportError: ' +
                      str(e_import)) from e_import


# Standard
import functools
from os import kill, remove
from os.path import splitext
from platform import system
import signal
import re

# Local
from jupyter_util import str_to_py, echom, is_integer, unquote_string, get_vim
from jupyter_messenger import JupyterMessenger
from monitor_console import Monitor
from debugger import DAPProxy


class JupyterVimSession():
    """Object containing jupyter <-> vim session info.

    This object is created in lieu of individual functions so that a single vim
    session can connect to multiple Jupyter kernels at once. Each connection
    gets a new JupyterVimSession object.

    Attributes
    ----------
    kernel_client : :obj:`JupyterMessenger`
        Object to handle primitive messaging between vim and the jupyter kernel.
    """
    def __init__(self):
        self.kernel_client = JupyterMessenger()
        self.dap_proxy = DAPProxy(self.kernel_client)
        self.monitor = None

    def if_connected(fct):
        """Decorator, fail if not connected."""
        # pylint: disable=no-self-argument, not-callable, no-member
        @functools.wraps(fct)
        def wrapper(self, *args, **kwargs):
            if not self.kernel_client.check_connection():
                echom(f'python3 _jupyter_session.{fct.__name__}() needs a connected client. ',
                      style='Error')
                return None
            return fct(self, *args, **kwargs)
        return wrapper

    def connect_to_kernel(self, kernel_type, filename='kernel-*.json'):
        """Establish a connection with the specified kernel type.

        .. note:: vim command `:JupyterConnect`

        Parameters
        ----------
        kernel_type : str
            Type of kernel, i.e. `python3` with which to connect.
        filename : str, optional, default='kernel-*.json'
            Specific kernel connection filename, i.e.
                ``$(jupyter --runtime)/kernel-123.json``
        """
        if self.kernel_client.check_connection():
            echom('Already connected to a kernel. Use :JupyterDisconnect to disconnect.', style='Error')
            return
        self.kernel_client.connect(kernel_type, filename)
        self.dap_proxy.start()

    def disconnect_from_kernel(self):
        """Disconnect from the kernel client if connected.

        Even when not connected, this function ensures the background thread
        and event loop are shut down.

        .. note:: vim command `:JupyterDisconnect`.
        """
        self.kernel_client.disconnect()

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
            except (AttributeError, NameError) as err:
                echom(f"Cannot send signal {sig} on this OS: {err}", style='Error')
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
                remove(self.kernel_client.kernel_info['cfile_user'])
            except OSError:
                pass

    @if_connected
    def start_monitor(self):
        self.monitor = Monitor(self.kernel_client)

    def stop_monitor(self, wipeout_buffer=True):
        if not self.monitor:
            return
        self.monitor = None
        if wipeout_buffer:
            vim.command('bwipeout __jupyter_monitor__')

    def start_debugger(self, vimspector_session):
        vimspector_session._StartWithConfiguration(
            configuration={
                'adapter': 'multi-session',
                'configuration': {'request': 'attach'},
                'breakpoints': {
                    'exception': {
                        'caught': 'N',
                        'raised': 'N',
                        'uncaught': 'Y'
                    }
                },
            },
            adapter={'host': 'localhost', 'port': '9000'}
        )
        
    # -----------------------------------------------------------------------------
    #        Communicate with Kernel
    # -----------------------------------------------------------------------------
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
        cmd = self.kernel_client.lang.run_file.format(filename)
        if cmd == '-1':
            with open(filename, 'r') as file_run:
                cmd = file_run.read()

        # Run it
        return self.kernel_client.execute(cmd)

    @if_connected
    def change_directory(self, directory):
        """Change current working directory in kernel.

        .. note:: vim command `:JupyterCd`.

        Parameters
        ----------
        directory : str
            Directory into which to change.
        """
        msg = self.kernel_client.lang.cd.format(directory)
        msg_id = self.kernel_client.execute(msg)
        echom('CWD: ', style='Question')
        vim.command("echon \"{}\"".format(directory))
        return (msg, msg_id)

    @if_connected
    def run_command(self, cmd):
        """Send a single command to the kernel.

        .. note:: vim command `:JupyterSendCode`.

        Parameters
        ----------
        cmd : str
            Lines of code to send to the kernel.
        """
        msg_id = self.kernel_client.send(cmd)
        return (cmd, msg_id)

    @if_connected
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
        msg_id = self.kernel_client.execute(cmd)
        return (cmd, msg_id)

    @if_connected
    def send_range(self):
        """Send a range of lines from the current vim buffer to the kernel.

        .. note:: vim command `:JupyterSendRange`.
        """
        rang = vim.current.range
        lines = "\n".join(vim.current.buffer[rang.start:rang.end+1])
        msg_id = self.kernel_client.execute(lines)
        prompt = "range {:d}-{:d} ".format(rang.start+1, rang.end+1)
        return (prompt, msg_id)

    @if_connected
    def run_cell(self):
        """Run all the code between two cell separators.

        .. note:: vim command `:JupyterSendCell`.
        """
        # Get line and buffer and cellseparators
        cur_buf = vim.current.buffer
        cur_line = vim.current.window.cursor[0] - 1

        cell_separators = get_vim('g:jupyter_cell_separators', '')
        cell_separators = [unquote_string(x) for x in cell_separators]

        def is_cell_separator(line):
            """Check if given line is a cell separator."""
            for separation in cell_separators:
                if re.match(separation, line):
                    return True
            return False

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
        msg_id = self.kernel_client.execute(lines)
        prompt = "execute lines {:d}-{:d} ".format(upper_bound+1, lower_bound+1)
        return (prompt, msg_id)
