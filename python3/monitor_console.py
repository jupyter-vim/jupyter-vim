"""
Feature to get a buffer with jupyter output
"""

# Standard
import asyncio
from queue import Queue

# Local
from jupyter_util import echom, unquote_string, str_to_vim, get_vim

# Process local
import vim


class Monitor():
    """Jupyter kernel monitor buffer and message line"""
    def __init__(self, kernel_client):
        self.kernel_client = kernel_client
        self.cmd = None
        self.cmd_id = None
        self.cmd_count = 0
        self.line_queue = Queue()

        ## Open the Jupyter terminal in vim, and move cursor to it
        if -1 == vim.eval('jupyter#monitor_console#OpenJupyterMonitor()'):
            echom('__jupyter_monitor__ failed to open!', 'Error')
            return

        # Launch timer that will update the buffer
        timer_interval = get_vim('g:jupyter_timer_interval', 500)
        vim.command(f'call timer_start({timer_interval}, "jupyter#monitor_console#UpdateConsoleBuffer")')

        for channel in ['shell', 'iopub', 'control']:
            asyncio.run_coroutine_threadsafe(self.monitor(channel), kernel_client.loop)

    async def monitor(self, channel):
        """Start monitoring a channel.

        Parameters
        ----------
        channel : 'shell' | 'iopub' | 'control'
            The channel to monitor.
        """
        while not self.kernel_client.loop.is_closed():
            msg = await self.kernel_client.get_next_msg(channel)
            self.line_queue.put(f'[{channel}] {msg["header"]["msg_type"]}: {msg["content"]}')

    def timer_write_msgs(self):
        """Write kernel <-> vim messages to monitor buffer"""
        timer_interval = get_vim('g:jupyter_timer_interval', 500)
        vim.command(f'call timer_start({timer_interval}, "jupyter#monitor_console#UpdateConsoleBuffer")')

        # Check in
        if self.line_queue.empty():
            return

        # Get buffer (same indexes as vim)
        b_nb = int(vim.eval('bufnr("__jupyter_monitor__")'))
        buf = vim.buffers[b_nb]

        cur_win = vim.eval('win_getid()')
        term_win = vim.eval('bufwinid({})'.format(str(b_nb)))
        vim.command('call win_gotoid({})'.format(term_win))

        # Append mesage to jupyter terminal buffer
        while not self.line_queue.empty():
            msg = self.line_queue.get_nowait()
            for line in msg.splitlines():
                line = unquote_string(str_to_vim(line))
                buf.append(line)

        vim.command('normal! G')
        vim.command('call win_gotoid({})'.format(cur_win))
