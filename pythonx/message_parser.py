"""
Jupyter <-> Vim
String Utility functions:
    1/ Helper (unquote_string)
    2/ Formater / Parser (parse_messages)
"""

# Standard
import re
from sys import version_info
from os import listdir
from os.path import isfile, join, splitext
from textwrap import dedent

from threading import Thread, Lock
from time import sleep

from jupyter_client import KernelManager, find_connection_file
import vim

try:
    from queue import Queue, Empty
except ImportError:
    from Queue import Queue, Empty

# Local
from language import list_languages


class VimMessenger:
    """Handle message to/from Vim"""
    def __init__(self, sync):
        # Message queue: for async echom
        self.message_queue = Queue()
        # Pid of current vim section
        self.pid = vim.eval('getpid()')

        # Define members python <- vim
        self.set_cell_separators()
        self.set_monitor_bools()

        # Sync object
        self.sync = sync

    def set_monitor_bools(self):
        """Set boolean defining if jupyter-vim.py must monitor it messages"""
        # Verbose: receive message id from sending function
        # and report back to vim with output.
        self.verbose = bool(int(vim.vars.get('jupyter_verbose', 0)))
        # Monitor: the kernel replies, as well as messages from other clients.
        self.monitor_console = bool(int(vim.vars.get('jupyter_monitor_console', 0)))

    def set_cell_separators(self):
        """Set cell separators list<regex> from vim globals to python object
        Once to avoid mutliple call at parsing file
        """
        self.cell_separators = vim.eval('g:jupyter_cell_separators')
        self.cell_separators = list(map(unquote_string, self.cell_separators))

    @staticmethod
    def get_timer_intervals():
        """Return list<int> timers in ms user defined"""
        timer_list = vim.eval('g:jupyter_timer_intervals')
        return list(map(int, timer_list))

    def is_cell_separator(self, line):
        """ Determine whether a given line is a cell separator """
        return any([bool(re.match(separation, line)) for separation in self.cell_separators])

    def thread_echom(self, arg, **args):
        """Wrap echo async: put message to be echo in a queue """
        self.message_queue.put((arg, args))

    def timer_echom(self):
        """Call echom sync: all messages in queue"""
        # Check in
        if self.message_queue.empty(): return

        # Show user the force
        while not self.message_queue.empty():
            (arg, args) = self.message_queue.get_nowait()
            echom(arg, **args)

        # Restore peace in the galaxy
        vim.command('redraw')

    def string_hi(self):
        """Return Hi froom vim string"""
        return ('\\n\\nReceived connection from vim client with pid {}'
                '\\n' + '-' * 60 + '\\n').format(self.pid)

    def thread_echom_kernel_info(self, kernel_info):
        """Echo kernel info (async)
        Prettify output: appearance rules
        """
        kernel_string = ""
        for key in kernel_info:
            kernel_string += "\n    " + str(key) + ': ' + str(kernel_info[key])

        # # Echo message
        self.thread_echom('To:', style='Question')
        self.thread_echom(kernel_string)

        # Send command so that user knows vim is connected at bottom, more readable
        self.thread_echom('Connected: {}'.format(kernel_info['id']), style='Question')


class JupyterMessenger:
    """Handle primitive messages to / from jupyter kernel
    Alias client
    """
    def __init__(self, sync):
        # KernelManager client
        self.km_client = None
        # Kernel information
        self.kernel_info = {}
        # Connection file
        self.cfile = ''
        # Sync object
        self.sync = sync

    def create_kernel_manager(self):
        """Create the kernel manager and connect a client
        See: <http://jupyter-client.readthedocs.io/en/stable/api/client.html>
        """
        # Get client
        kernel_manager = KernelManager(connection_file=self.cfile)
        kernel_manager.load_connection_file()
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
        """Disconnect (silently from kernel): close channels"""
        if self.km_client is None: return
        self.km_client.stop_channels()
        self.km_client = None

    def check_connection(self):
        """Check that we have a client connected to the kernel."""
        return self.km_client.hb_channel.is_beating() if self.km_client else False

    def check_connection_or_warn(self):
        """Echo warning: if not connected"""
        if self.check_connection(): return True
        echom('WARNING: Not connected to Jupyter!'
              '\nRun :JupyterConnect to find the kernel', style='WarningMsg')
        return False

    def get_pending_msgs(self):
        """Get pending message pool"""
        msgs = []
        try:
            self.sync.msg_lock.acquire()
            msgs = self.km_client.iopub_channel.get_msgs()
        except (Empty, TypeError, KeyError, IndexError, ValueError): pass
        finally:
            self.sync.msg_lock.release()
        return msgs

    def get_reply_msg(self, msg_id):
        """Get kernel reply from sent client message with msg_id (async)
        I can block 3 sec, so call me in a thread
        """
        # TODO handle 'is_complete' requests?
        # <http://jupyter-client.readthedocs.io/en/stable/messaging.html#code-completeness>
        # Declare default
        reply = {}
        for _ in range(3):
            # Check
            if self.sync.stop: return {}

            # Get
            self.sync.msg_lock.acquire()
            try:
                reply = self.km_client.get_shell_msg(block=True, timeout=1) or {}
            except (Empty, TypeError, KeyError, IndexError, ValueError): pass
            finally:
                self.sync.msg_lock.release()

            # Stop
            if reply.get('parent_header', {}).get('msg_id', -1) == msg_id: break

        return reply

    def find_cfile(self, user_cfile):
        """Find connection file from argument"""
        self.cfile = find_connection_file(filename=user_cfile)
        return self.cfile

    def send(self, msg, **kwargs):
        """Send a message to the kernel client
        Global: -> cmd, cmd_id
        """
        if not self.check_connection_or_warn(): return -1

        # Include dedent of msg so we don't get odd indentation errors.
        cmd = dedent(msg)
        cmd_id = self.km_client.execute(cmd, **kwargs)

        return cmd_id

    def get_kernel_info(self, language):
        """Explicitly ask the jupyter kernel for its pid
        Thread: <- cfile
                <- vim_pid
                -> lang
                -> kernel_pid
        Returns: dict with 'kernel_type', 'pid', 'cwd', 'hostname'
        """
        # Check in
        if self.kernel_info['kernel_type'] not in list_languages():
            echom('I don''t know how to get infos for a Jupyter kernel of type "{}"'
                  .format(self.kernel_info['kernel_type']), 'WarningMsg')

        # Fill kernel_info
        self.kernel_info.update({
            'connection_file': self.cfile,
            'id': shorten_filename(self.cfile),  # Id of cfile (reduced)
            # Get from kernel info
            'pid': self.send_code_and_get_reply(language.pid),  # PID of kernel
            'cwd': self.send_code_and_get_reply(language.cwd),
            'hostname': self.send_code_and_get_reply(language.hostname),
            })

        # Return
        return self.kernel_info

    def send_code_and_get_reply(self, code):
        """Helper: Get variable _res from code string (setting _res)"""
        # Send message
        msg_id = self.send(code, silent=False, user_expressions={'_res': '_res'})

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


class Sync:
    """Sync primitive"""
    def __init__(self):
        # Thread running
        self.thread = None
        # Should the current thread stop (cleanly)
        self.stop = False
        # Queue for line to echom
        self.line_queue = Queue()
        # Lock to retrieve messages one thread at a time
        self.msg_lock = Lock()

    def check_stop(self):
        """Check and reset stop value"""
        last = self.stop
        if self.stop: self.stop = False
        return last

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
#        Helpers
# -----------------------------------------------------------------------------


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
                     and splitext(fpath)[1] == '.json']

    # Get all the kernel ids
    kernel_ids = [shorten_filename(fpath) for fpath in runtime_files
                  if not fpath.startswith('nbserver')]

    # Sort
    kernel_ids.sort(key=hex_sort, reverse=True)

    # Return -> vim caller
    return kernel_ids


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
        res = res or content.get('text', '')  # Jupyter bash style ...
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
                prompt = 'SdE[{:d}]: '.format(line_number)
                dots = (' ' * (len(prompt.rstrip()) - 4)) + '...x '
            else:
                prompt = 'SdO[{:d}]: '.format(line_number)
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
