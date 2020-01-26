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
    raise ImportError("Could not find kernel. " + __doc__, e)

try:
    import vim
except ImportError as e:
    raise ImportError('vim module only available within vim!', e)

# Standard
from os import kill, remove
from os.path import splitext
from platform import system
from signal import SIGTERM
if system() != 'Windows':
    from signal import SIGKILL

# Local
from monitor_console import Monitor, monitor_decorator
from message_parser import VimMessenger, JupyterMessenger, Sync, \
    str_to_py, echom
from language import get_language


class JupyterVimSession():
    """Info relative to the jupyter <-> vim current section"""
    def __init__(self):
        self.sync = Sync()
        self.client = JupyterMessenger(self.sync)
        self.vim = VimMessenger(self.sync)
        self.monitor = Monitor(self)
        self.lang = get_language('')


    def connect_to_kernel(self, kernel_type, filename=''):
        """:JupyterConnect"""
        # Set what can
        self.client.kernel_info['kernel_type'] = kernel_type
        self.client.kernel_info['cfile_user'] = filename
        self.lang = get_language(kernel_type)

        # Create thread
        self.sync.start_thread(target=self.thread_connect_to_kernel)

        # Launch timers: update echom
        for sleep_ms in self.vim.get_timer_intervals():
            vim_cmd = ('let timer = timer_start(' + str(sleep_ms) +
                       ', "jupyter#UpdateEchom")')
            vim.command(vim_cmd)


    def disconnect_from_kernel(self):
        """:JupyterDisconnect kernel client (Sync)"""
        self.client.disconnnect()
        echom("Disconnected: {}".format(self.client.kernel_info['id']), style='Directory')


    def signal_kernel(self, sig=SIGTERM):
        """:JupyterTerminateKernel
        Use kill command to send a signal to the remote kernel.
        This side steps the (non-functional) jupyter interrupt mechanisms.
        Only works on posix.
        """
        # Kill process
        try:
            # Check if valid pid
            if self.client.kernel_info['pid'] < 1:
                echom("Cannot kill kernel: unknown pid", style='Error')
            else:
                kill(self.client.kernel_info['pid'], int(sig))
                echom("kill pid {p:d} with signal #{v:d}, {n:s}"
                      .format(p=self.client.kernel_info['pid'],
                              v=sig.value, n=sig.name), style='WarningMsg')
        except ProcessLookupError:
            echom(("pid {p:d} does not exist! " +
                   "Kernel may have been terminated by outside process")
                  .format(p=self.client.kernel_info['pid']), style='Error')
        except OSError as err:
            echom("signal #{v:d}, {n:s} failed to kill pid {p:d}"
                  .format(v=sig.value, n=sig.name, p=self.client.kernel_info['pid']), style='Error')
            raise err

        # Delete connection file
        sig_list = [SIGTERM]
        if system() != 'Windows': sig_list.append(SIGKILL)
        if sig in sig_list:
            try:
                remove(self.client.cfile)
            except OSError:
                pass


    def run_file(self, flags='', filename=''):
        """:JupyterRunFile"""
        # Special cpython cases
        if self.client.kernel_info['kernel_type'] == 'python':
            return self.run_file_in_ipython(flags=flags, filename=filename)

        # Message warning to user
        if flags != '':
            echom('RunFile in other kernel than "python" doesn\'t support flags.'
                  ' All arguments except the last (file location) will be ignored.',
                  style='Error')

        # Get command and slurp file if not implemented
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
        """Create kernel manager from existing connection file (Async)"""
        if self.sync.check_stop(): return

        # Check if connection is alive
        connected = self.client.check_connection()

        # Try to connect
        for attempt in range(3):
            if connected: break
            # Check if thread want to return
            if self.sync.check_stop(): return

            # Find connection file
            try: self.client.find_cfile(self.client.kernel_info['cfile_user'])
            except IOError:
                self.vim.thread_echom(
                    "kernel connection attempt {:d}/3 failed - no kernel file"
                    .format(attempt), style="Error")
                continue

            # Connect
            connected = self.client.create_kernel_manager()

        # Early return if failed
        if not connected:
            self.client.disconnnect()
            self.vim.thread_echom('kernel connection attempt timed out', style='Error')
            return

        # Pre-message the user
        self.vim.thread_echom('Connected! ', style='Question')

        # Collect and echom kernel info
        self.vim.thread_echom_kernel_info(self.client.get_kernel_info(self.lang))

        # Print vim connected -> client
        cmd_hi = self.lang.print_string.format(self.vim.string_hi())
        self.client.send(cmd_hi)


    # -----------------------------------------------------------------------------
    #        Communicate with Kernel
    # -----------------------------------------------------------------------------
    @monitor_decorator
    def change_directory(self, directory):
        """CD: Change (current working) to directory
        """
        # Cd
        msg = self.lang.cd.format(directory)
        msg_id = self.client.send(msg)

        # Print cwd
        try:
            cwd = self.client.send_code_and_get_reply(self.lang.cwd)
            echom('CWD: ', style='Question')
            vim.command("echon \"{}\"".format(cwd))
        except Exception: pass

        # Return to decorators
        return (msg, msg_id)


    @monitor_decorator
    def run_command(self, cmd):
        """Send a single command to the kernel."""
        msg_id = self.client.send(cmd)
        return (cmd, msg_id)


    @monitor_decorator
    def run_file_in_ipython(self, flags='', filename=''):
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
        msg_id = self.client.send(cmd)
        return (cmd, msg_id)


    @monitor_decorator
    def send_range(self):
        """Send a range of lines from the current vim buffer to the kernel."""
        rang = vim.current.range
        lines = "\n".join(vim.current.buffer[rang.start:rang.end+1])
        msg_id = self.client.send(lines)
        prompt = "range {:d}-{:d} ".format(rang.start+1, rang.end+1)
        return (prompt, msg_id)


    @monitor_decorator
    def run_cell(self):
        """Run all the code between two cell separators"""
        # Get line and buffer and cellseparators
        cur_buf = vim.current.buffer
        cur_line = vim.current.window.cursor[0] - 1
        self.vim.set_cell_separators()

        # Search upwards for cell separator
        upper_bound = cur_line
        while upper_bound > 0 and not self.vim.is_cell_separator(cur_buf[upper_bound]):
            upper_bound -= 1

        # Skip past the first cell separator if it exists
        if self.vim.is_cell_separator(cur_buf[upper_bound]):
            upper_bound += 1

        # Search downwards for cell separator
        lower_bound = min(upper_bound+1, len(cur_buf)-1)

        while lower_bound < len(cur_buf)-1 and \
                not self.vim.is_cell_separator(cur_buf[lower_bound]):
            lower_bound += 1

        # Move before the last cell separator if it exists
        if self.vim.is_cell_separator(cur_buf[lower_bound]):
            lower_bound -= 1

        # Make sure bounds are within buffer limits
        upper_bound = max(0, min(upper_bound, len(cur_buf)-1))
        lower_bound = max(0, min(lower_bound, len(cur_buf)-1))

        # Make sure of proper ordering of bounds
        lower_bound = max(upper_bound, lower_bound)

        # Execute cell
        lines = "\n".join(cur_buf[upper_bound:lower_bound+1])
        msg_id = self.client.send(lines)
        prompt = "execute lines {:d}-{:d} ".format(upper_bound+1, lower_bound+1)
        return (prompt, msg_id)
