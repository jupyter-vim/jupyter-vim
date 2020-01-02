"""
Feature to get a buffer with jupyter output
"""

from message_parser import parse_messages, prettify_execute_intput, \
    unquote_string, str_to_vim, echom, warn_no_connection
import vim
from time import sleep

try:
    from queue import Empty
except ImportError:
    from Queue import Empty

SI = None


def set_monitor_section_info(section_info):
    """Set global section info"""
    # pylint: disable=global-statement
    global SI; SI = section_info


def monitorable(fct):
    """Decorator to monitor messages"""
    def wrapper(*args, **kwargs):
        # Check
        if not SI.client.check_connection():
            warn_no_connection()
            return

        # Call
        fct(*args, **kwargs)

        # Clause
        SI.vim.set_monitor_bools()
        if not SI.vim.verbose and not SI.vim.monitor_console: return

        # Launch update threads
        update_msgs()
    return wrapper


def update_msgs():
    """Launch pending messages grabbers (Sync but not for long)
    Param: console (boolean): should I update console
           prompt  (boolean): should I update prompt
           last_cmd (string): not used already

    """
    # Open the Jupyter terminal in vim, and move cursor to it
    b_nb = vim.eval('jupyter_monitor_console#OpenJupyterTerm()')
    if -1 == b_nb:
        echom('__jupyter_term__ failed to open!', 'Error')
        return

    # Define time: thread (additive) sleep and timer wait
    # TODO get as user parameter
    timer_intervals = (100, 200, 400, 800, 1500, 3000, 10000)
    thread_intervals = [50]
    for i in range(len(timer_intervals)-1):
        thread_intervals.append(timer_intervals[i+1] - timer_intervals[i] - 50)

    # Create thread
    SI.sync.start_thread(
        target=thread_fetch_msgs,
        args=[thread_intervals])

    # Launch timers
    for sleep_ms in timer_intervals:
        vim_cmd = ('call timer_start(' + str(sleep_ms) +
                   ', "jupyter_monitor_console#UpdateConsoleBuffer")')
        vim.command(vim_cmd)


def thread_fetch_msgs(intervals):
    """Update message that timer will append to console message
    """
    io_cache = []
    for sleep_ms in intervals:
        # Sleep ms
        if SI.sync.check_stop(): return
        sleep(sleep_ms / 1000)
        if SI.sync.check_stop(): return

        # Get messages
        SI.sync.msg_lock.acquire()
        msgs = SI.client.get_pending_msgs()
        SI.sync.msg_lock.release()
        io_new = parse_messages(SI, msgs)

        # Insert code line Check not already here (check with substr 'Py [')
        do_add_cmd = SI.cmd is not None
        do_add_cmd &= len(io_new) != 0
        do_add_cmd &= not any(SI.lang.prompt_in[:4] in msg for msg in io_new + io_cache)
        if do_add_cmd:
            # Get cmd number from id
            try:
                SI.sync.msg_lock.acquire()
                reply = SI.client.get_reply_msg(SI.cmd_id)
                SI.sync.msg_lock.release()
                line_number = reply['content'].get('execution_count', 0)
            except (Empty, KeyError, TypeError):
                line_number = -1
            s = prettify_execute_intput(
                line_number, SI.cmd, SI.lang.prompt_in)
            io_new.insert(0, s)

        # Append just new
        _ = [SI.sync.line_queue.put(s) for s in io_new if s not in io_cache]
        # Update cache
        io_cache = list(set().union(io_cache, io_new))


def timer_write_console_msgs():
    """Write kernel <-> vim messages to console buffer"""
    # Check in
    if SI.sync.line_queue.empty(): return
    if not SI.vim.monitor_console and not SI.vim.verbose: return

    # Get buffer (same indexes as vim)
    if SI.vim.monitor_console:
        b_nb = int(vim.eval('bufnr("__jupyter_term__")'))
        b = vim.buffers[b_nb]

    # Append mesage to jupyter terminal buffer
    while not SI.sync.line_queue.empty():
        msg = SI.sync.line_queue.get_nowait()
        for line in msg.splitlines():
            line = unquote_string(str_to_vim(line))
            if SI.vim.monitor_console:
                b.append(line)
            if SI.vim.verbose:
                echom(line)

    # Update view (moving cursor)
    if SI.vim.monitor_console:
        cur_win = vim.eval('win_getid()')
        term_win = vim.eval('bufwinid({})'.format(str(b_nb)))
        vim.command('call win_gotoid({})'.format(term_win))
        vim.command('normal! G')
        vim.command('call win_gotoid({})'.format(cur_win))
