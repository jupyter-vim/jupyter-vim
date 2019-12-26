"""
Feature to get a buffer with jupyter output
"""

from message_parser import parse_messages, prettify_execute_intput, \
    unquote_string, str_to_vim, vim_echom
import vim
from time import sleep

try:
    from queue import Empty
except ImportError:
    from Queue import Empty

# Global
new_lines = []
b_console = False
b_verbose = False


def update_msgs(section_info, last_cmd='', console=False, verbose=False):
    """Grab pending messages and place them inside the vim console monitor
    Param: console (boolean): should I update console
           prompt  (boolean): should I update prompt
           last_cmd (string): not used already
    """
    # Set global used by timer
    global b_console, b_verbose
    b_console = console; b_verbose = verbose

    # Open the Jupyter terminal in vim, and move cursor to it
    b_nb = vim.eval('jupyter_monitor_console#OpenJupyterTerm()')
    if -1 == b_nb:
        vim_echom('__jupyter_term__ failed to open!', 'Error')
        return

    # Create thread
    thread_intervals = (0, 100, 500, 1000)
    timer_intervals = (50, 200, 600, 1100)
    section_info.start_thread(
        target=thread_fetch_msgs,
        args=[section_info, thread_intervals])

    # Launch timers
    for sleep_ms in timer_intervals:
        vim_cmd = ('call timer_start(' + str(sleep_ms) +
                   ', "jupyter_monitor_console#UpdateConsoleBuffer")')
        vim.command(vim_cmd)


def thread_fetch_msgs(section_info, intervals):
    """Update message that timer will append to console message
    """
    global new_lines

    io_cache = []
    for sleep_ms in intervals:
        # Sleep ms
        if section_info.check_stop(): return
        sleep(sleep_ms / 1000)
        if section_info.check_stop(): return

        # Get messages
        msgs = section_info.get_msgs()
        io_new = parse_messages(section_info, msgs, vim_echom)

        # Insert code line Check not already here (check with substr 'Py [')
        do_add_cmd = section_info.cmd is not None
        do_add_cmd &= len(io_new) != 0
        do_add_cmd &= not any(section_info.lang.prompt_in[:4] in msg for msg in io_new + io_cache)
        if do_add_cmd:
            # Get cmd number from id
            try:
                reply = section_info.get_reply_msg(section_info.cmd_id)
                line_number = reply['content'].get('execution_count', 0)
            except (Empty, KeyError, TypeError):
                line_number = -1
            s = prettify_execute_intput(
                line_number, section_info.cmd, section_info.lang.prompt_in)
            io_new.insert(0, s)

        # Append just new
        new_lines += [s for s in io_new if s not in io_cache]
        # Update cache
        io_cache = list(set().union(io_cache, io_new))


def timer_write_console_msgs():
    """Write kernel <-> vim messages to console buffer"""
    global new_lines

    # Check in
    if len(new_lines) == 0: return
    if not b_console and not b_verbose: return

    # Get buffer (same indexes as vim)
    if b_console:
        b_nb = int(vim.eval('bufnr("__jupyter_term__")'))
        b = vim.buffers[b_nb]

    # Append mesage to jupyter terminal buffer
    for msg in new_lines:
        for line in msg.splitlines():
            line = unquote_string(str_to_vim(line))
            if b_console:
                b.append(line)
            if b_verbose:
                vim_echom(line)
    new_lines = []

    # Update view (moving cursor)
    if b_console:
        cur_win = vim.eval('win_getid()')
        term_win = vim.eval('bufwinid({})'.format(str(b_nb)))
        vim.command('call win_gotoid({})'.format(term_win))
        vim.command('normal! G')
        vim.command('call win_gotoid({})'.format(cur_win))
