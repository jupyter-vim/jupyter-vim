"""
Jupyter <-> Vim

See: <http://jupyter-client.readthedocs.io/en/stable/api/client.html>
"""

# Standard
import re
from textwrap import dedent
from threading import Thread, Lock
from time import sleep

# Py module
from jupyter_client import KernelManager
import vim

# Local
from jupyter_util import echom, unquote_string, match_kernel_id, get_vim

try:
    from queue import Queue, Empty
except ImportError:
    from Queue import Queue, Empty

# Local
from language import list_languages


class VimMessenger():
    """Handle message to/from Vim

    Attributes
    ----------
    sync : :obj:`Sync`
        Object to support asynchronous operations.
    message_queue : :obj:`Queue`
        Asynchronous queue of messages.
    pid : int
        PID of the current vim session.
    verbose : bool
        If True, receive message id from sending function and report back to
        vim with output, silent otherwise.
    monitor_console : bool
        If True, create a new buffer in vim to display output from the kernel.
    cell_separators : list of str
        User-defined list of strings that separate code cells.
    """
    def __init__(self, sync):
        self.sync = sync
        self.message_queue = Queue()        # for async echom
        self.pid = get_vim('getpid()', -1)  # pid of current vim session

        # Define members python <- vim
        self.set_monitor_bools()
        self.set_cell_separators()

    def set_monitor_bools(self):
        """Set booleans to define if jupyter_vim monitors messages."""
        # NOTE this function is called by the @monitor_decorator in jupyter_vim
        # to ensure user options are up-to-date.
        self.verbose = bool(int(vim.vars.get('jupyter_verbose', 0)))
        self.monitor_console = bool(int(vim.vars.get('jupyter_monitor_console', 0)))

    def set_cell_separators(self):
        """Set cell separators (list of str)."""
        # NOTE this function is called from jupyter_vim.run_cell
        self.cell_separators = get_vim('g:jupyter_cell_separators', '')
        self.cell_separators = [unquote_string(x) for x in self.cell_separators]

    @staticmethod
    def get_timer_intervals():
        """Return list of user-defined timers [ms].

        Returns
        -------
        list of int
            List of timers [ms].
        """
        timer_list = get_vim('g:jupyter_timer_intervals', [0.1, 0.5, 1, 3])
        return [int(x) for x in timer_list]

    @staticmethod
    def get_meta_messages():
        """Return list of user-defined list of meta messages.

        Returns
        -------
        list of str
            List of user-defined meta messages to send before/after code.
        """
        return (get_vim('b:jupyter_exec_before', ''),
                get_vim('b:jupyter_exec_pre', ''),
                get_vim('b:jupyter_exex_post', ''),
                get_vim('b:jupyter_exec_after', '')
                )

    def is_cell_separator(self, line):
        """Return True if given `line` is a cell separator."""
        return any([bool(re.match(separation, line.strip()))
                    for separation in self.cell_separators])

    def thread_echom(self, arg, **args):
        """Wrap echo async: put message to be echoed in a queue."""
        self.message_queue.put((arg, args))

    def timer_echom(self):
        """Call echom sync on all messages in queue."""
        # Check in
        if self.message_queue.empty():
            return

        # Show user the force
        while not self.message_queue.empty():
            (arg, args) = self.message_queue.get_nowait()
            echom(arg, **args)

        # Restore peace in the galaxy
        vim.command('redraw')

    # TODO add verbose flag
    def string_hi(self):
        """Return Hi from vim string."""
        return ('\\n\\nReceived connection from vim client with pid {}'
                '\\n' + '-' * 60 + '\\n').format(self.pid)

    def thread_echom_kernel_info(self, kernel_info):
        """Echo kernel info (async).

        Parameters
        ----------
        kernel_info : str
            Information about the kernel to print in vim messages.
        """
        kernel_string = '\n    '.join([str(key) + ': ' + str(kernel_info[key])
                                       for key in kernel_info])

        # Send command so that user knows vim is connected at bottom, more readable
        self.thread_echom('Connected: {}'.format(kernel_info['id']), style='Question')

        # FIXME messages does not actually display in vim,
        #   only appears in `:messages` command.
        self.thread_echom('To:', style='Question')
        self.thread_echom(kernel_string)

class JupyterMessenger():
    """Handle primitive messages to/from jupyter kernel.

    Attributes
    ----------
    km_client : :obj:`KernelManager` client
        Object to handle connections with the kernel.
        See: <http://jupyter-client.readthedocs.io/en/stable/api/client.html>
    kernel_info : dict
        Information about the kernel itself.
        dict with keys:
            'kernel_type' : str, the type of kernel, i.e. `python`.
            'pid' : int, the pid of the kernel process.
            'cwd' : str, the current working directory of the kernel.
            'hostname' : str, the hostname of the kernel.
    cfile : str
        Filename of the connection file, i.e. `kernel-123.json`.
    sync : :obj:`Sync`
        Object to support asynchronous operations.
    meta_messages : list of str
        User-defined meta messages to send before/after code.
    """
    def __init__(self, sync):
        self.km_client = None      # KernelManager client
        self.kernel_info = dict()  # Kernel information
        self.cfile = ''            # Connection file
        self.sync = sync           # Sync object
        self.meta_messages = VimMessenger.get_meta_messages()

    def create_kernel_manager(self):
        """Create the kernel manager and connect a client.

        Returns
        -------
        bool
            True if client connects successfully, False on failure.
        """
        # Get client
        kernel_manager = KernelManager(connection_file=self.cfile)
        # The json may be badly encoding especially if autoconnecting
        try:
            kernel_manager.load_connection_file()
        except Exception:
            return False
        self.km_client = kernel_manager.client()

        # Open channel
        self.km_client.start_channels()

        # Ping the kernel
        self.km_client.kernel_info()
        try:
            self.km_client.get_shell_msg(timeout=1)
            return True
        except Empty:
            return False

    def disconnnect(self):
        """Disconnect silently from kernel and close channels."""
        if self.km_client is None:
            return
        self.km_client.stop_channels()
        self.km_client = None

    def update_meta_messages(self):
        """Sync: reread vim meta vars."""
        self.meta_messages = VimMessenger.get_meta_messages()

    def check_connection(self):
        """Check that we have a client connected to the kernel.

        Returns
        -------
        bool
            True if client is connected, False if not.
        """
        return self.km_client.hb_channel.is_beating() if self.km_client else False

    def check_connection_or_warn(self):
        """Echo warning if not connected.
        Returns
        -------
        bool
            True if client is connected, False if not.
        """
        if self.check_connection():
            return True
        echom('WARNING: Not connected to Jupyter!'
              '\nRun :JupyterConnect to find the kernel', style='WarningMsg')
        return False

    def get_pending_msgs(self):
        """Get pending message pool.

        Returns
        -------
        list of :obj:`msg`
            List of messages waiting on the `iopub_channel`.
        """
        msgs = list()
        try:
            self.sync.msg_lock.acquire()
            msgs = self.km_client.iopub_channel.get_msgs()
        except (Empty, TypeError, KeyError, IndexError, ValueError):
            pass
        finally:
            self.sync.msg_lock.release()
        return msgs

    def get_reply_msg(self, msg_id):
        """Get kernel reply from sent client message with msg_id (async).

        This function can block 3 sec, so call in a thread.

        Returns
        -------
        dict
            Message response.
        """
        # TODO handle 'is_complete' requests?
        # <http://jupyter-client.readthedocs.io/en/stable/messaging.html#code-completeness>
        # Declare default
        reply = dict()
        for _ in range(3):
            # Check
            if self.sync.stop:
                return dict()

            # Get
            self.sync.msg_lock.acquire()
            try:
                reply = self.km_client.get_shell_msg(block=True, timeout=1) or {}
            except (Empty, TypeError, KeyError, IndexError, ValueError):
                pass
            finally:
                self.sync.msg_lock.release()

            # Stop
            if reply.get('parent_header', {}).get('msg_id', -1) == msg_id:
                break

        return reply

    def send(self, msg, ismeta=False, **kwargs):
        """Send a message to the kernel client.

        .. note:: Async: crossroad <- run_command
                  Global: -> cmd, cmd_id

        Returns
        -------
        int
            Command id.
        """
        if not self.check_connection_or_warn():
            return -1

        # Pre
        if not ismeta:
            bef, pre, post, aft = self.meta_messages
            # Send before unless it is blank
            if bef:
                self.send(bef, ismeta=True)
            # Craft new message
            msg = pre + msg + post

        # Include dedent of msg so we don't get odd indentation errors.
        cmd = dedent(msg)

        # Actually send execute_request
        cmd_id = self.km_client.execute(cmd, **kwargs)

        # Send after unless it is blank
        if not ismeta and aft:
            self.send(aft, ismeta=True)

        return cmd_id

    def get_kernel_info(self, language):
        """Explicitly ask the jupyter kernel for its pid

        .. note:: Thread: <- cfile
                          <- vim_pid
                          -> lang
                          -> kernel_pid
        Returns
        -------
        dict
            dict with keys: {'kernel_type', 'pid', 'cwd', 'hostname'}
        """
        # Check in
        if self.kernel_info['kernel_type'] not in list_languages():
            echom('I don''t know how to get infos for a Jupyter kernel of type "{}"'
                  .format(self.kernel_info['kernel_type']), 'WarningMsg')

        # Fill kernel_info
        self.kernel_info.update({
            'connection_file': self.cfile,
            'id': match_kernel_id(self.cfile),  # int id of cfile
            # Get from kernel info
            'pid': self.send_code_and_get_reply(language.pid),  # PID of kernel
            'cwd': self.send_code_and_get_reply(language.cwd),
            'hostname': self.send_code_and_get_reply(language.hostname),
            })

        # Return
        return self.kernel_info

    def send_code_and_get_reply(self, code):
        """Get variable _res from code string.

        .. note:: Only used by get_kernel_info (internal) => send with ismeta.

        Returns
        -------
        str
            Unquoted string of the message reply.
        """
        # Send message
        msg_id = self.send(code, ismeta=True, silent=True, user_expressions={'_res': '_res'})

        # Wait to get message back from kernel (1 sec)
        reply = self.get_reply_msg(msg_id)

        # Get _res from user expression
        res = reply.get('content', {}).get('user_expressions', {}) \
                   .get('_res', {}).get('data', {}).get('text/plain', -1)

        # Try again parse messages
        if res == -1:
            line_number = reply.get('content', {}).get('execution_count', -1)
            msgs = self.get_pending_msgs()
            res = parse_iopub_for_reply(msgs, line_number)

        # Rest in peace
        return unquote_string(res)


class Sync():
    """Synchronization (not so) primitives, for safe thread support.

    Attributes
    ----------
    thread : :obj:`Thread` or None
        The running thread.
    stop : bool
        True if thread should not be stopped, False otherwise.
    line_queue : :obj:`Queue`
        Queue of lines of code to echo to the kernel.
    msg_lock : :obj:`Lock`
        lock to retrieve messages one thread at a time.
    """
    def __init__(self):
        self.thread = None
        self.stop = False
        self.line_queue = Queue()
        self.msg_lock = Lock()

    def check_stop(self):
        """Check and reset stop value.

        Returns
        -------
        bool
            Last value of `self.stop`.
        """
        last = self.stop
        if self.stop:
            self.stop = False
        return last

    def stop_thread(self):
        """Stop current thread."""
        if self.thread is None:
            return
        if not self.thread.is_alive():
            self.thread = None
            return

        # Wait 1 sec max
        self.stop = True
        for _ in range(100):
            if not self.stop:
                sleep(0.010)
        self.thread = None
        return

    def start_thread(self, target=None, args=None):
        """Stop last / Create new / Start thread.

        Parameters
        ----------
        target : callable, optional, default=None
            Callable object to which `args` will be passed.
        args : list, optional, default=None
        """
        if args is None:
            args = list()
        self.stop_thread()
        self.thread = Thread(target=target, args=args, daemon=True)
        self.thread.start()


# -----------------------------------------------------------------------------
#        Parsers
# -----------------------------------------------------------------------------
def parse_iopub_for_reply(msgs, line_number):
    """Get kernel response from message pool (Async).

    .. note:: some kernel (iperl) do not discriminate when client asks for
              `user_expressions`. But still they give a printable output.

    Parameters
    ----------
    msgs : list
        List of messages to parse.
    line_number : int
        The message number of the corresponding code.

    Returns
    -------
    str
        The kernel response to the messages.
    """
    res = -1

    # Parse all execute
    for msg in msgs:
        # Get the result of execution
        content = msg.get('content', False)
        if not content:
            continue

        ec = int(content.get('execution_count', 0))
        if not ec:
            continue
        if line_number not in (-1, ec):
            continue

        msg_type = msg.get('header', {}).get('msg_type', '')
        if msg_type not in ('execute_result', 'stream'):
            continue

        res = content.get('data', {}).get('text/plain', -1)
        res = res if res != -1 else content.get('text', -1)
        break
    return res
