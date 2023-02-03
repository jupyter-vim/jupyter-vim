"""
Jupyter <-> Vim

See: <http://jupyter-client.readthedocs.io/en/stable/api/client.html>
"""

# Standard
import asyncio
import collections
from textwrap import dedent
from threading import Thread, Lock
from queue import Empty, Queue
import sys

# Py module
from jupyter_client import AsyncKernelManager, find_connection_file

# Local
from jupyter_util import echom, unquote_string, match_kernel_id, get_vim
from language import list_languages, get_language

# Process local
import vim


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
            'cfile' : str, filename of the connection file, i.e. `kernel-123.json`.
            'pid' : int, the pid of the kernel process.
            'cwd' : str, the current working directory of the kernel.
            'hostname' : str, the hostname of the kernel.
    """
    def __init__(self):
        self.km_client = None      # KernelManager client
        self.background_thread = None
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        self.loop = asyncio.new_event_loop()
        self.kernel_info = dict()  # Kernel information
        self.lang = get_language('')
        self.kernel_lock = Lock()

        # Producers and consumers of each channel
        self.producers = dict()
        self.consumers = dict()

        # Message scheduled to be displayed using echom.
        self.echom_queue = Queue()

    def connect(self, kernel_type, filename='kernel-*.json'):
        """Connect to the kernel.

        Launches a background thread to deal with future communication with the
        kernel in an async manner.

        Parameters
        ----------
        kernel_type : str
            The type of kernel, i.e. `python`.
        filename : str
            Filename of the kernel connection file.
        """
        self.kernel_info['kernel_type'] = kernel_type
        self.kernel_info['cfile_user'] = filename
        self.lang = get_language(kernel_type)

        if not self.loop.is_running():
            self.background_thread = Thread(target=self.loop.run_forever, daemon=True)
            self.background_thread.start()

        # Attempt to connect to the kernel. Since we run async functions in the
        # thead we created above, we must make sure to always schedule them in
        # a thread-safe manner.
        asyncio.run_coroutine_threadsafe(self._async_connect(filename), self.loop)

        # Start timer that periodically checks for echom messages to display
        timer_interval = get_vim('g:jupyter_timer_interval', 500)
        vim.command(f'call timer_start({timer_interval}, "jupyter#UpdateEchom")')

    async def _async_connect(self, filename):
        """The async part of the connection to the kernel.

        Parameters
        ----------
        filename : str
            Filename of the kernel connection file.
        """
        connection_file = find_connection_file(filename)
        kernel_manager = AsyncKernelManager(connection_file=connection_file)

        kernel_manager.load_connection_file()
        self.km_client = kernel_manager.client()
        self.km_client.start_channels()

        for channel in ['shell', 'iopub', 'control']:
            self.producers[channel] = self.loop.create_task(
                self._listen_to_channel(channel))

        await self.get_kernel_info()
        self.thread_echom(
            f'Connected to {self.kernel_info["kernel_type"]} kernel on '
            f'{self.kernel_info["hostname"]}:{self.kernel_info["cwd"]}',
            style='Question'
        )

    def disconnect(self):
        """Disconnect silently from kernel and close channels."""
        if self.km_client:
            self.km_client.stop_channels()
            self.km_client = None
        self.loop.call_soon_threadsafe(lambda: [task.cancel() for task in asyncio.all_tasks(self.loop.stop)])
        self.loop.call_soon_threadsafe(self.loop.stop)
        if self.background_thread and self.background_thread.is_alive():
            self.background_thread.join(1)
            self.background_thread = None
        self.kernel_info = dict()
        self.lang = get_language('')
        echom('Disconnected.', style='Directory')


    async def _listen_to_channel(self, channel):
        """Listen to a kernel channel and notify any consumers of messages.

        Parameters
        ----------
        channel : 'shell' | 'iopub' | 'control'
            The channel to listen on.
        """
        while True:
            if channel == 'shell':
                msg = await self.km_client.shell_channel.get_msg()
            elif channel == 'iopub':
                msg = await self.km_client.iopub_channel.get_msg()
            elif channel == 'control':
                msg = await self.km_client.control_channel.get_msg()
            else:
                raise ValueError(f'Unknown channel: {channel}')

            if channel in self.consumers:
                waiting = self.consumers[channel]
                while len(waiting) > 0:
                    future = waiting.pop()
                    # Futures can be done if a previous session has been
                    # cancelled or has errored out.
                    if not future.done():
                        future.set_result(msg)

    def thread_send_msg(self, channel, msg):
        """Threadsafe sending of messages to the kernel."""
        with self.kernel_lock:
            if channel == 'iopub':
                self.km_client.iopub_channel.send(msg)
            elif channel == 'control':
                self.km_client.control_channel.send(msg)
            elif channel == 'shell':
                self.km_client.shell_channel.send(msg)
            else:
                raise ValueError('Invalid channel.')

    async def get_next_msg(self, channel):
        """Listen to a channel for the next incoming message.

        This returns a Future that is then awaited on. As soon as a message
        arrives, the Future will have its result set.

        This works concurrently: multiple calls to get_next_msg will result in
        multiple futures that will trigger on the same message.

        Parameters
        ----------
        channel : 'shell' | 'iopub' | 'control'
            The channel to listen on.

        Returns
        -------
        asyncio.Future
            A future that will trigger when the message arrives. The result of
            the future will be set to the contents of the message.
        """
        consumer_list = self.consumers.get(channel, collections.deque())
        future = self.loop.create_future()
        consumer_list.append(future)
        self.consumers[channel] = consumer_list
        return await future

    async def get_reply(self, msg_id, channel):
        """Get kernel reply from sent client message with msg_id (async).

        Parameters
        ----------
        msg_id : int
            The message id obtained when sending the message.
        channel : 'shell' | 'iopub' | 'control'
            The channel to listen on.

        Returns
        -------
        dict
            Message response.
        """
        while True:
            msg = await self.get_next_msg(channel)
            if msg['parent_header']['msg_id'] == msg_id:
                return msg

    def check_connection(self):
        """Check that we have a client connected to the kernel.

        Returns
        -------
        bool
            True if client is connected, False if not.
        """
        return self.km_client.hb_channel.is_beating() if self.km_client else False

    async def get_pending_msgs(self):
        """Get pending message pool.

        Returns
        -------
        list of :obj:`msg`
            List of messages waiting on the `iopub_channel`.
        """
        msgs = list()
        try:
            msgs = await self.km_client.iopub_channel.get_msgs()
        except (Empty, TypeError, KeyError, IndexError, ValueError):
            pass
        return msgs

    def execute(self, code, ismeta=False, **kwargs):
        """Execute some code on the kernel.

        Parameters
        ----------
        code : str
            The programming code to execute on the kernel.
        ismeta : bool, default=False
            Whether the before/pre/post/after content should be used or not.
        **kwargs : dict

        Returns
        -------
        msg_id
            Id of the message. Useful for obtaining a reponse.
        """
        # Pre
        if not ismeta:
            before = get_vim('b:jupyter_exec_before', '')
            pre = get_vim('b:jupyter_exec_pre', '')
            post = get_vim('b:jupyter_exec_post', '')
            after = get_vim('b:jupyter_exec_after', '')

            # Craft new message
            if before:
                self.execute(before, ismeta=True)
            code = pre + code + post

        # Dedent the code so we don't get odd indentation errors.
        code = dedent(code)

        # Actually send execute_request
        with self.kernel_lock:
            msg_id = self.km_client.execute(code, **kwargs)

        # Send after unless it is blank
        if not ismeta and after:
            self.km_client.execute(after)

        return msg_id

    async def execute_and_get_reply(self, code):
        """Execute code on the kernel and get back variable _res

        .. note:: Only used by get_kernel_info (internal) => send with ismeta.

        Returns
        -------
        str
            Unquoted string of the message reply.
        """
        # Send message
        msg_id = self.execute(code, ismeta=True, silent=True, user_expressions={'_res': '_res'})
        reply = await self.get_reply(msg_id, 'shell')

        # Get _res from user expression
        res = reply.get('content', {}).get('user_expressions', {}) \
                   .get('_res', {}).get('data', {}).get('text/plain', -1)

        # Try again parse messages
        if res == -1:
            line_number = reply.get('content', {}).get('execution_count', -1)
            msgs = await self.get_pending_msgs()
            res = parse_iopub_for_reply(msgs, line_number)

        # Rest in peace
        return unquote_string(res)

    async def get_kernel_info(self):
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
            self.thread_echom(
                ('I don''t know how to get infos for a Jupyter kernel of type '
                 f'"{self.kernel_info["kernel_type"]}"'),
                stlye='WarningMsg'
            )

        # Fill kernel_info
        self.kernel_info.update({
            'connection_file': self.kernel_info['cfile_user'],
            'id': match_kernel_id(self.kernel_info['cfile_user']),
            # Get from kernel info
            'pid': await self.execute_and_get_reply(self.lang.pid),  # PID of kernel
            'cwd': await self.execute_and_get_reply(self.lang.cwd),
            'hostname': await self.execute_and_get_reply(self.lang.hostname),
        })

        # Return
        return self.kernel_info

    def thread_echom(self, arg, **args):
        """Schedule message for displaying with echom."""
        self.echom_queue.put((arg, args))

    def timer_echom(self):
        """Call echom sync on all messages in queue."""
        empty = self.echom_queue.empty()
        while not self.echom_queue.empty():
            (arg, args) = self.echom_queue.get_nowait()
            echom(arg, **args)
        if not empty:
            vim.command('redraw')
        timer_interval = get_vim('g:jupyter_timer_interval', 500)
        vim.command(f'call timer_start({timer_interval}, "jupyter#UpdateEchom")')


# -----------------------------------------------------------------------------
#        Parsers
# -----------------------------------------------------------------------------
def parse_iopub_for_reply(msgs, line_number):
    """Get kernel response from message pool.

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

        i_count = int(content.get('execution_count', 0))
        if not i_count:
            continue
        if line_number not in (-1, i_count):
            continue

        msg_type = msg.get('header', {}).get('msg_type', '')
        if msg_type not in ('execute_result', 'stream'):
            continue

        res = content.get('data', {}).get('text/plain', -1)
        res = res if res != -1 else content.get('text', -1)
        break
    return res
