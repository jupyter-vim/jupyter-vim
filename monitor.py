#!~/anaconda3/bin/python3
#=============================================================================
#     File: ~/.vim/bundle/jupyter-vim/monitor.py
#  Updated: 02/20/2018, 15:48
#   Author: Bernie Roesler
#
#  Description: Monitor for Jupyter console commands run in vim.
#
#  This code is no longer part of the user-facing functionality of jupyter-vim,
#  so will not be maintained.
#
#=============================================================================
# TODO implement: if __name__ == "__main__" to run while loop. Move loop and
# tty-setting code to functions that are called as main

"""
Monitor for Jupyter console commands run from Vim.

Usage:
    $ jupyter kernel # or `jupyter console`
    $ python monitor.py
    $ vim my_script.py
    :Jupyter
"""

import os
import sys
import six
import traceback

from jupyter_client import KernelManager, find_connection_file
from queue import Empty

try:
    from pygments import highlight
except ImportError:
    highlight = lambda code, *args: code
else:
    from pygments.lexers import PythonLexer, Python3Lexer
    from pygments.formatters import TerminalFormatter
    formatter = TerminalFormatter()
    lexer = Python3Lexer() if six.PY3 else PythonLexer()

colors = {k: i for i, k in enumerate([
    'black', 'red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'white'])}

#------------------------------------------------------------------------------
#        Function definitions
#------------------------------------------------------------------------------
def colorize(string, color, bold=False, bright=False):
    if isinstance(color, str):
        code = ''.join(('\033[', str(colors[color] + (90 if bright else 30))))
    else:
        code = '\033[38;5;%d' % color
    return ''.join((code, ';1' if bold else '', 'm', string, '\033[0m'))

#------------------------------------------------------------------------------
#        Class definition
#------------------------------------------------------------------------------
class IPythonMonitor(object):
    """
    Class to keep track of the ipython kernel.
    Track clients, and messages published on iopub_channel
    """

    def __init__(self):
        self.clients = set()
        self.execution_count_id = None
        self.last_msg_type = None  # Only set when text written to stdout
        self.last_execution_count = 0

    def listen(self, socket):
        """ Listen for mesages on the kernel socket once connected. """
        while socket.recv():
            for msg in kc.iopub_channel.get_msgs():
                # See this URL for descriptions of all message types:
                # <http://jupyter-client.readthedocs.io/en/stable/messaging.html>
                msg_type = msg['msg_type']
                print(msg_type)

                if msg_type == 'shutdown_reply':
                    print("Shutting down monitor")
                    sys.exit(0)

                # UUID of the client sending the message
                client = msg['parent_header'].get('session', '')

                # Check for the message from vim :IPython command to add vim as
                # an acceptable client
                if (client and msg_type in ('execute_input', 'pyin') and
                        msg['content']['code'].strip("\n") == '"_vim_client"'):
                    self.clients.add(client)
                    print("Added vim as client")
                    continue

                # If vim has sent the message to the kernel,
                # Handle the message with an IPythonMonitor function
                # if client in self.clients:
                #     getattr(self, msg_type, self.other)(msg)
                #     sys.stdout.flush()

                # Handle all messages from all clients
                getattr(self, msg_type, self.other)(msg)
                sys.stdout.flush()

    def clear_output(self, msg):
        if self.last_msg_type in ('execute_input', 'pyin'):
            print('\n')
        print('\033[2K\r', file=sys.stdout, end='')

    def display_data(self, msg):
        sys.stdout.write('\n')
        self.pyout(msg, prompt=False)

    def print_prompt(self, start='In', color=28, num_color=46, count_offset=0):
        count = str(self.last_execution_count + count_offset)
        sys.stdout.write(colorize(start.rstrip() + ' [', color))
        sys.stdout.write(colorize(count, num_color, bold=True))
        sys.stdout.write(colorize(']: ', color))
        return '%s [%s]: ' % (start.strip(), count)

    def pyerr(self, msg):
        for line in msg['content']['traceback']:
            sys.stdout.write('\n' + line)
        if self.last_msg_type not in ('execute_input', 'pyin'):
            self.print_prompt('\nIn')
        self.last_msg_type = msg['msg_type']

    def pyin(self, msg):
        self.last_execution_count = msg['content']['execution_count']
        sys.stdout.write('\r')
        dots = ' ' * (len(self.print_prompt().rstrip()) - 1) + ': '
        code = highlight(msg['content']['code'], lexer, formatter)
        output = code.rstrip().replace('\n', '\n' + colorize(dots, 28))
        sys.stdout.write(output)
        self.execution_count_id = msg['parent_header']['msg_id']
        self.last_msg_type = msg['msg_type']

    def pyout(self, msg, prompt=True, spaces=''):
        if 'execution_count' in msg['content']:
            self.last_execution_count = msg['content']['execution_count']
            self.execution_count_id = msg['parent_header']['msg_id']
        output = msg['content']['data']['text/plain']
        if prompt:
            self.print_prompt('\nOut', 196, 196)
            sys.stdout.write(('\n' if '\n' in output else '') + output)
        else:
            sys.stdout.write(output)
        self.last_msg_type = msg['msg_type']

    def status(self, msg):
        if (msg['content']['execution_state'] == 'idle' and
                msg['parent_header']['msg_id'] == self.execution_count_id):
            self.print_prompt('\nIn', count_offset=1)
            self.execution_count_id = None

    def stream(self, msg):
        if self.last_msg_type not in ('pyerr', 'error', 'stream'):
            sys.stdout.write('\n')
        # Use of 'data' or 'text' depends on message type
        try:
            data = msg['content']['data']
        except KeyError:
            data = msg['content']['text']
        sys.stdout.write(colorize(data, 'cyan', bright=True))
        self.last_msg_type = msg['msg_type']

    def other(self, msg):
        print('msg_type = %s' % str(msg['msg_type']))
        print('msg = %s' % str(msg))

    # Alias some functions to attributes (IPython names changed)
    execute_input = pyin
    execute_result = pyout
    error = pyerr


#------------------------------------------------------------------------------
#       Connect to the kernel
#------------------------------------------------------------------------------
# TODO move this loop to __init__ of IPythonMonitor??
connected = False
while not connected:
    try:
        # Default: filename='kernel-*.json'
        filename = find_connection_file()
    except IOError:
        continue

    # Create the kernel manager and connect a client
    km = KernelManager(connection_file=filename)
    km.load_connection_file()
    kc = km.client()
    kc.start_channels()

    # Ping the kernel
    msg_id = kc.kernel_info()
    try:
        reply = kc.get_shell_msg(timeout=1)
    except Empty:
        continue
    except Exception:
        traceback.print_exc()
    except KeyboardInterrupt:   # <C-c> or kill -SIGINT?
        sys.exit(0)
    else:
        connected = True
        # Set the socket on which to listen for messages
        socket = km.connect_iopub()
        print('IPython monitor connected successfully!')
    finally:
        if not connected:
            kc.stop_channels()


#------------------------------------------------------------------------------
#       Set stdout to desired tty
#------------------------------------------------------------------------------
term = ''
if len(sys.argv) > 1:
    # Set stdout to arbitrary file descriptor given as script argument
    #   $ python monitor.py '/dev/ttys003' &
    term = open(sys.argv[1], 'w')
    sys.stdout = term
else:
    term = os.ttyname(1)  # use monitor's terminal
    # # Set stdout to terminal in which kernel is running
    # msg_id = kc.execute('import os as _os; _tty = _os.ttyname(1)', silent=True,
    #         user_expressions=dict(_tty='_tty'))
    # while True:
    #     try:
    #         msg = kc.shell_channel.get_msg(timeout=1.0)
    #         if msg['parent_header']['msg_id'] == msg_id:
    #             term = ast.literal_eval(msg['content']['user_expressions']
    #                     ['_tty']['data']['text/plain'])
    #             # print("setting sys.stdout to term: {}".format(term))
    #             sys.stdout = open(term, 'w+')
    #             break
    #     except Empty:
    #         continue

# def print_msg_type(msg):
#     msg_type = msg['header']['msg_type']
#     print('[iopub]: msg_type = {}'.format(msg_type))

#------------------------------------------------------------------------------
#        Create and run the monitor
#------------------------------------------------------------------------------
monitor = IPythonMonitor()
monitor.listen(socket)

#==============================================================================
#==============================================================================
