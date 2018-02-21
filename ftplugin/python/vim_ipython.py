"""
Python code for ipy.vim.

This module is loaded as:
    from vim_ipython import *
in ipy.vim, which is a filetype plugin for *.py files. It will only function
when running within vim (+python[3]).
"""

import ast
import os
import sys
import time

from queue import Empty
unicode = str

# 'vim' can only be imported when running on the vim interpreter. Create NoOp
# class to allow testing of functions outside of vim.
not_in_vim = False
try:
    import vim
except ImportError:
    class NoOp(object):
        def __getattribute__(self, key):
            return lambda *args: '0'
    vim = NoOp()
    print("Uh oh! Not running inside vim! Loading anyway...")
    not_in_vim = True

#------------------------------------------------------------------------------ 
#        Define wrapper
#------------------------------------------------------------------------------
class VimVars(object):
    """Wrapper for vim.vars for converting bytes to str."""

    def get(self, name, default=None):
        var = vim.vars.get(name, default)
        if PY3 and isinstance(var, bytes):
            var = str(var, vim_encoding)
        elif not PY3 and isinstance(var, str):
            var = unicode(var, vim_encoding)
        return var

    def __getitem__(self, name):
        if name not in vim.vars:
            raise KeyError(name)
        return self.get(name)

    def __setitem__(self, name, value):
        vim.vars[name] = value

vim_vars = VimVars()

#------------------------------------------------------------------------------ 
#        Read global configuration variables
#------------------------------------------------------------------------------
PY3 = sys.version_info[0] == 3

show_execution_count = bool(int(vim.eval("g:ipy_show_execution_count")))
monitor_subchannel = bool(int(vim.eval("g:ipy_monitor_subchannel")))
run_flags = vim.eval("g:ipy_run_flags")
current_line = ""
current_stdin_prompt = {}

# get around unicode problems when interfacing with vim
vim_encoding = vim.eval('&encoding') or 'utf-8'

def vim_variable(name, default=None):
    exists = int(vim.eval("exists('%s')" % name))
    return vim.eval(name) if exists else default

# status buffer settings
status_prompt_in  = vim_variable('g:ipy_status_in',  'In [%(line)d]: ')
status_prompt_out = vim_variable('g:ipy_status_out', 'Out[%(line)d]: ')

status_prompt_colors = {
    'in_ctermfg'   : vim_variable('g:ipy_status_in_console_color',    'Green'),
    'in_guifg'     : vim_variable('g:ipy_status_in_gui_color',        'Green'),
    'out_ctermfg'  : vim_variable('g:ipy_status_out_console_color',   'Red'),
    'out_guifg'    : vim_variable('g:ipy_status_out_gui_color',       'Red'),
    'out2_ctermfg' : vim_variable('g:ipy_status_out2_console_colorG', 'Gray'),
    'out2_guifg'   : vim_variable('g:ipy_status_out2_gui_color',      'Gray'),
}

status_blank_lines = int(vim_variable('g:ipy_status_blank_lines', '1'))

# Set IP address to local machine
ip = '127.0.0.1'

# this allows us to load vim_ipython multiple times
# try:
#     km
#     kc
#     pid
# except NameError:
#     km = None
#     kc = None
#     pid = None

_install_instructions = """You *must* install IPython into the Python that
your vim is linked against. If you are seeing this message, this usually means
either (1) installing IPython using the system Python that vim is using, or
(2) recompiling Vim against the Python where you already have IPython
installed. This is only a requirement to allow Vim to speak with an IPython
instance using IPython's own machinery. It does *not* mean that the IPython
instance with which you communicate via vim-ipython needs to be running the
same version of Python.
"""

#------------------------------------------------------------------------------ 
#        Function Definitions:
#------------------------------------------------------------------------------
def connect_to_kernel():
    """ Create kernel manager from IPython existing kernel file """
    try:
        import IPython
    except ImportError:
        raise ImportError("Could not find IPython. " + _install_instructions)

    from jupyter_client import KernelManager, find_connection_file
    from traitlets.config.loader import KeyValueConfigLoader

    global km, kc, send

    # Test if connection is still alive
    connected = False
    starttime = time.time()
    attempt = 0
    while not connected and (time.time() - starttime) < 5.0:
        try:
            # Default: filename='kernel-*.json'
            cfile = find_connection_file()
        except IOError:
            vim_echo("IPython connection attempt #{:d} failed - no kernel file" \
                    .format(attempt), "Warning")
            time.sleep(1)
            continue
        attempt += 1

        # Create the kernel manager and connect a client
        km = KernelManager(connection_file=cfile)
        km.load_connection_file()
        kc = km.client()
        kc.start_channels()

        # Alias execution function (previously allowed altering "allow_stdin")
        def send(msg, **kwargs):
            return kc.execute(msg, **kwargs)

        # Ping the kernel
        send('', silent=True)
        try:
            msg = kc.get_shell_msg(timeout=1)
        except Empty:
            continue
        else:
            connected = True
            vim.command('redraw')
            # Send command so that monitor knows vim is commected 
            send('"_vim_client";_=_;__=__\n', store_history=False)
            set_pid() # Ask kernel for its PID
            vim_echo("IPython connection successful")
        finally:
            if not connected:
                kc.stop_channels()
                vim_echo("IPython connection attempt timed out", "Error")
                return

    return km

def vim_regex_escape(x):
    for old, new in (("[", "\\["), ("]", "\\]"), (":", "\\:"), (".", "\."),
                     ("*", "\\*")):
        x = x.replace(old, new)
    return x

def vim_echo(arg, style="Question"):
    """ Report arg using vim's echo command. 
    
    Keyword args:
    style -- the vim highlighting style to use
    """
    try:
        vim.command("echohl %s" % style)
        vim.command("echom \"%s\"" % arg.replace('\"','\\\"'))
        vim.command("echohl None")
    except vim.error:
        print("-- %s" % arg)

def disconnect():
    "disconnect kernel manager"
    # XXX: make a prompt here if this km owns the kernel
    pass

def get_doc(word, level=0):
    if kc is None:
        return ["Not connected to IPython, cannot query: %s" % word]
    if word.startswith('%'):  # request for magic documentation
        request = ('_doc = get_ipython().object_inspect("{0}", '
                   'detail_level={1})\n'
                   'del _doc["argspec"]').format(word, level)
        try:
            msg_id = send(request, silent=True, user_variables=['_doc'])
        except TypeError: # change in IPython 3.0+
            msg_id = send(request, silent=True, user_expressions={'_doc':'_doc'})
    else:
        msg_id = kc.inspect(word, detail_level=level)
    doc = get_doc_msg(msg_id)
    # get around unicode problems when interfacing with vim
    return [d.encode(vim_encoding) for d in doc]

import re
# from http://serverfault.com/questions/71285/in-centos-4-4-how-can-i-strip-escape-sequences-from-a-text-file
strip = re.compile('\x1B\[([0-9]{1,2}(;[0-9]{1,2})*)?[mK]')
def strip_color_escapes(s):
    return strip.sub('',s)

def get_doc_msg(msg_id):
    n = 13 # longest field name (empirically)
    b=[]
    try:
        m = get_child_msg(msg_id)
    except Empty:
        # timeout occurred
        return ["no reply from IPython kernel"]
    content = m['content']

    if 'evalue' in content:
        return b

    doc = None
    if 'user_variables' in content:
        doc = content['user_variables']['_doc']
    elif 'user_expressions' in content:
        doc = content['user_expressions']['_doc']
    if doc:
        content = ast.literal_eval(doc['data']['text/plain'])

    if not content['found']:
        return b

    # IPython 3.0+ the documentation message is encoding by the kernel
    if 'data' in content:
        try:
            text = content['data']['text/plain']
            for line in text.split('\n'):
                b.append(strip_color_escapes(line).rstrip())
                if 'signature: ' in b[-1].lower() and b[-1].endswith(')'):
                    left, _, right = b[-1].partition(': ')
                    b[-1] = '{0}: `{1}`'.format(left, right)
            return b
        except KeyError:    # no text/plain key
            return b

    for field in ['type_name','base_class','string_form','namespace',
            'file','length','definition','source','docstring']:
        c = content.get(field,None)
        if c:
            if field in ['definition']:
                c = '`%s`' % strip_color_escapes(c).rstrip()
            s = field.replace('_',' ').title()+':'
            s = s.ljust(n)
            if c.find('\n')==-1:
                b.append(s+c)
            else:
                b.append(s)
                b.extend(c.splitlines())
    return b

def get_doc_buffer(level=0, word=None):
    # empty string in case vim.eval return None
    vim.command("let isk_save = &isk") # save iskeyword list
    vim.command("let &isk = '@,48-57,_,192-255,.'")
    word = word or vim.eval('expand("<cword>")')
    vim.command("let &isk = isk_save") # restore iskeyword list
    doc = get_doc(word, level)
    if len(doc) ==0:
        vim_echo(repr(word)+" not found","Error")
        return
    # documentation buffer name is same as the query made to ipython
    vim.command('new '+word.lstrip('%'))
    vim.command('setlocal modifiable noro')
    # doc window quick quit keys: 'q' and 'escape'
    vim.command('nnoremap <buffer> q :q<CR>')
    # shortcuts to change filetype/syntax
    vim.command('nnoremap <buffer> m :<C-u>setfiletype man<CR>')
    vim.command('nnoremap <buffer> p :<C-u>setfiletype python<CR>')
    vim.command('nnoremap <buffer> r :<C-u>setfiletype rst<CR>')
    # Known issue: to enable the use of arrow keys inside the terminal when
    # viewing the documentation, comment out the next line
    # vim.command('nnoremap <buffer> <Esc> :q<CR>')
    # and uncomment this line (which will work if you have a timoutlen set)
    #vim.command('nnoremap <buffer> <Esc><Esc> :q<CR>')
    b = vim.current.buffer
    b[:] = None
    b[:] = doc
    vim.command('setlocal nomodified bufhidden=wipe nomodifiable readonly nospell')
    #vim.command('setlocal previewwindow nomodifiable nomodified ro')
    #vim.command('set previewheight=%d'%len(b))# go to previous window
    vim.command('resize %d'%len(b))
    #vim.command('pcl')
    #vim.command('pedit doc')
    #vim.command('normal! ') # go to previous window
    if level == 0:
        # highlight python code within rst
        vim.command(r'unlet! b:current_syntax')
        vim.command(r'syn include @rstPythonScript syntax/python.vim')
        # 4 spaces
        vim.command(r'syn region rstPythonRegion start=/^\v {4}/ end=/\v^( {4}|\n)@!/ contains=@rstPythonScript')
        # >>> python code -> (doctests)
        vim.command(r'syn region rstPythonRegion matchgroup=pythonDoctest start=/^>>>\s*/ end=/\n/ contains=@rstPythonScript')
        vim.command(r'set syntax=rst')
    else:
        # use Python syntax highlighting
        vim.command('setlocal syntax=python')

def vim_ipython_is_open():
    """
    Helper function to let us know if the vim-ipython shell is currently
    visible
    """
    for w in vim.windows:
        if w.buffer.name is not None and w.buffer.name.endswith("vim-ipython"):
            return True
    return False

def update_subchannel_msgs(debug=False, force=False):
    """
    Grab any pending messages and place them inside the vim-ipython shell.
    This function will do nothing if the vim-ipython shell is not visible,
    unless force=True argument is passed.
    """
    if kc is None or (not vim_ipython_is_open() and not force):
        return False
    msgs = kc.iopub_channel.get_msgs()
    msgs += kc.stdin_channel.get_msgs()

    # Check if cursor is in 'vim-ipython' console window.
    startedin_vimipython = vim.eval('@%')=='vim-ipython'
    if not startedin_vimipython:
        # switch to preview window
        vim.command(
            "try"
            "|silent! wincmd P"
            "|catch /^Vim\%((\a\+)\)\=:E441/"
            "|silent pedit +set\ ma vim-ipython"
            "|silent! wincmd P"
            "|endtry")
        # if the current window is called 'vim-ipython'
        if vim.eval('@%')=='vim-ipython':
            # set the preview window height to the current height
            vim.command("set pvh=" + vim.eval('winheight(0)'))
        else:
            # close preview window, it was something other than 'vim-ipython'
            vim.command("pcl")
            vim.command("silent pedit +set\ ma vim-ipython")
            vim.command("wincmd P") #switch to preview window
            # subchannel window quick quit key 'q'
            vim.command('nnoremap <buffer> q :q<CR>')
            vim.command("set bufhidden=hide buftype=nofile ft=python")
            vim.command("setlocal nobuflisted") # don't come up in buffer lists
            vim.command("setlocal nonumber") # no line numbers, we have in/out nums
            vim.command("setlocal noswapfile") # no swap file (so no complaints cross-instance)
            # make shift-enter and control-enter in insert mode behave same as in ipython notebook
            # shift-enter send the current line, control-enter send the line
            # but keeps it around for further editing.
            vim.command("inoremap <buffer> <s-Enter> <esc>dd:python run_command('''<C-r>\"''')<CR>i")
            # pkddA: paste, go up one line which is blank after run_command,
            # delete it, and then back to insert mode
            vim.command("inoremap <buffer> <c-Enter> <esc>dd:python run_command('''<C-r>\"''')<CR>pkddA")
            # ctrl-C gets sent to the IPython process as a signal on POSIX
            vim.command("noremap <buffer>  :IPythonInterrupt<cr>")

    #syntax highlighting for python prompt
    # QtConsole In[] is blue, but I prefer the oldschool green
    # since it makes the vim-ipython 'shell' look like the holidays!
    colors = status_prompt_colors
    vim.command("hi IPyPromptIn ctermfg=%s guifg=%s" % (colors['in_ctermfg'], colors['in_guifg']))
    vim.command("hi IPyPromptOut ctermfg=%s guifg=%s" % (colors['out_ctermfg'], colors['out_guifg']))
    vim.command("hi IPyPromptOut2 ctermfg=%s guifg=%s" % (colors['out2_ctermfg'], colors['out2_guifg']))
    in_expression = vim_regex_escape(status_prompt_in % {'line': 999}).replace('999', '[ 0-9]*')
    vim.command("syn match IPyPromptIn /^%s/" % in_expression)
    out_expression = vim_regex_escape(status_prompt_out % {'line': 999}).replace('999', '[ 0-9]*')
    vim.command("syn match IPyPromptOut /^%s/" % out_expression)
    vim.command("syn match IPyPromptOut2 /^\\.\\.\\.* /")

    global current_stdin_prompt
    b = vim.current.buffer
    update_occured = False
    for m in msgs:
        # if we received a message it means the kernel is not waiting for input
        vim.command('autocmd! InsertEnter <buffer>')
        current_stdin_prompt.clear()
        s = ''
        if 'msg_type' not in m['header']:
            # debug information
            #echo('skipping a message on sub_channel','WarningMsg')
            #echo(str(m))
            continue
        header = m['header']['msg_type']
        if header == 'status':
            continue
        elif header == 'stream':
            # TODO: alllow for distinguishing between stdout and stderr (using
            # custom syntax markers in the vim-ipython buffer perhaps), or by
            # also echoing the message to the status bar
            try:
                s = strip_color_escapes(m['content']['data'])
            except KeyError:    # changed in IPython 3.0.0
                s = strip_color_escapes(m['content']['text'])
        elif header == 'pyout' or header == 'execute_result':
            s = status_prompt_out % {'line': m['content']['execution_count']}
            s += m['content']['data']['text/plain']
        elif header == 'display_data':
            # TODO: handle other display data types (HMTL? images?)
            s += m['content']['data']['text/plain']
        elif header == 'pyin' or header == 'execute_input':
            # TODO: the next line allows us to resend a line to ipython if
            # %doctest_mode is on. In the future, IPython will send the
            # execution_count on subchannel, so this will need to be updated
            # once that happens
            line_number = m['content'].get('execution_count', 0)
            prompt = status_prompt_in % {'line': line_number}
            s = prompt
            # add a continuation line (with trailing spaces if the prompt has them)
            dots = '.' * len(prompt.rstrip())
            dots += prompt[len(prompt.rstrip()):]
            s += m['content']['code'].rstrip().replace('\n', '\n' + dots)
        elif header == 'pyerr' or header == 'error':
            c = m['content']
            s = "\n".join(map(strip_color_escapes,c['traceback']))
        elif header == 'input_request':
            current_stdin_prompt['prompt'] = m['content']['prompt']
            current_stdin_prompt['is_password'] = m['content']['password']
            current_stdin_prompt['parent_msg_id'] = m['parent_header']['msg_id']
            s += m['content']['prompt']
            vim_echo('Awaiting input. call :IPythonInput to reply')

        if s.find('\n') == -1:
            # somewhat ugly unicode workaround from
            # http://vim.1045645.n5.nabble.com/Limitations-of-vim-python-interface-with-respect-to-character-encodings-td1223881.html
            if isinstance(s,unicode):
                s=s.encode(vim_encoding)
            b.append(s)
        else:
            try:
                b.append(s.splitlines())
            except:
                b.append([l.encode(vim_encoding) for l in s.splitlines()])
        update_occured = True
    # make a newline so we can just start typing there
    if status_blank_lines and not current_stdin_prompt:
        if b[-1] != '':
            b.append([''])
    if update_occured or force:
        vim.command('normal! G') # go to the end of the file
        if current_stdin_prompt:
            vim.command('normal! $') # also go to the end of the line

    nwindows = len(vim.windows)
    currentwin = int(vim.eval('winnr()'))
    previouswin = int(vim.eval('winnr("#")'))
    if len(vim.windows) > nwindows:
        pwin = int(vim.current.window.number)
        if pwin <= previouswin:
            previouswin += 1
        if pwin <= currentwin:
            currentwin += 1
    vim.command(str(previouswin) + 'wincmd w')
    vim.command(str(currentwin) + 'wincmd w')
    return update_occured

def get_child_msg(msg_id):
    while True:
        m = kc.get_shell_msg(timeout=1)
        if m['parent_header']['msg_id'] == msg_id:
            return m

def print_prompt(prompt,msg_id=None):
    """Print In[] or In[42] style messages"""
    global show_execution_count
    if show_execution_count and msg_id:
        # wait to get message back from kernel
        try:
            child = get_child_msg(msg_id)
            count = child['content']['execution_count']
            vim_echo("In[%d]: %s" %(count,prompt))
        except Empty:
            # if the kernel it's waiting for input it's normal to get no reply
            if not kc.stdin_channel.msg_ready():
                vim_echo("In[]: %s (no reply from IPython kernel)" % prompt)
    else:
        vim_echo("In[]: %s" % prompt)

def with_subchannel(f,*args,**kwargs):
    """ Conditionally monitor subchannel. """
    def f_with_update(*args, **kwargs):
        try:
            f(*args,**kwargs)
            if monitor_subchannel:
                update_subchannel_msgs(force=True)
        except AttributeError: #if kc is None
            vim_echo("not connected to IPython", 'Error')
    return f_with_update

@with_subchannel
def run_this_file(flags=''):
    ext = os.path.splitext(vim.current.buffer.name)[-1][1:]
    if ext in ('pxd', 'pxi', 'pyx', 'pyxbld'):
        cmd = ' '.join(filter(None, (
            '%run_cython',
            vim_vars.get('cython_run_flags', ''),
            repr(vim.current.buffer.name))))
    else:
        cmd = '%%run %s %s' % (flags or vim_vars['ipython_run_flags'],
                               repr(vim.current.buffer.name))
    msg_id = send(cmd)
    print_prompt(cmd, msg_id)

@with_subchannel
def run_ipy_input(**kwargs):
    lines = vim_vars['ipy_input']
    if lines.strip().endswith('?'):
        return get_doc_buffer(level=1 if lines.strip().endswith('??') else 0,
                              word=lines.strip().rstrip('?'))
    msg_id = send(lines, **kwargs)
    lines = lines.replace('\n', u'\xac')
    print_prompt(lines[:(int(vim.options['columns']) - 22)], msg_id)

@with_subchannel
def run_this_line(dedent=False):
    line = vim.current.line
    if dedent:
        line = line.lstrip()
    if line.rstrip().endswith('?'):
        # intercept question mark queries -- move to the word just before the
        # question mark and call the get_doc_buffer on it
        w = vim.current.window
        original_pos =  w.cursor
        new_pos = (original_pos[0], vim.current.line.index('?')-1)
        w.cursor = new_pos
        if line.rstrip().endswith('??'):
            # double question mark should display source
            # XXX: it's not clear what level=2 is for, level=1 is sufficient
            # to get the code -- follow up with IPython team on this
            get_doc_buffer(1)
        else:
            get_doc_buffer()
        # leave insert mode, so we're in command mode
        vim.command('stopi')
        w.cursor = original_pos
        return
    msg_id = send(line)
    print_prompt(line, msg_id)

@with_subchannel
def run_command(cmd):
    msg_id = send(cmd)
    print_prompt(cmd, msg_id)

@with_subchannel
def run_these_lines(dedent=False):
    r = vim.current.range
    if dedent:
        lines = list(vim.current.buffer[r.start:r.end+1])
        nonempty_lines = [x for x in lines if x.strip()]
        if not nonempty_lines:
            return
        first_nonempty = nonempty_lines[0]
        leading = len(first_nonempty) - len(first_nonempty.lstrip())
        lines = "\n".join(x[leading:] for x in lines)
    else:
        lines = "\n".join(vim.current.buffer[r.start:r.end+1])
    msg_id = send(lines + "\n")
    #alternative way of doing this in more recent versions of ipython
    #but %paste only works on the local machine
    #vim.command("\"*yy")
    #send("'%paste')")

    #vim lines start with 1
    #print("lines %d-%d sent to ipython"% (r.start+1,r.end+1))
    prompt = "lines %d-%d "% (r.start+1,r.end+1)
    print_prompt(prompt,msg_id)

@with_subchannel
def InputPrompt(force=False, hide_input=False):
    msgs = kc.stdin_channel.get_msgs()
    for m in msgs:
        global current_stdin_prompt
        if 'msg_type' not in m['header']:
            continue
        current_stdin_prompt.clear()
        header = m['header']['msg_type']
        if header == 'input_request':
            current_stdin_prompt['prompt'] = m['content']['prompt']
            current_stdin_prompt['is_password'] = m['content']['password']
            current_stdin_prompt['parent_msg_id'] = m['parent_header']['msg_id']

    if not hide_input:
        hide_input = current_stdin_prompt.get('is_password', False)
    # If there is a pending input or we are forcing the input prompt
    if (current_stdin_prompt or force) and kc:
        # save the current prompt, ask for input and restore the prompt
        vim.command('call inputsave()')
        input_call = (
            "try"
            "|let user_input = {input_command}('{prompt}')"
            "|catch /^Vim:Interrupt$/"
            "|silent! unlet user_input"
            "|endtry"
            ).format(input_command='inputsecret' if hide_input else 'input',
                     prompt=current_stdin_prompt.get('prompt', ''))
        vim.command(input_call)
        vim.command('call inputrestore()')

        # if the user replied to the input request
        if vim.eval('exists("user_input")'):
            reply = vim.eval('user_input')
            vim.command("silent! unlet user_input")
            # write the reply to the vim-ipython buffer if it's not a password
            if not hide_input and vim_ipython_is_open():

                currentwin = int(vim.eval('winnr()'))
                previouswin = int(vim.eval('winnr("#")'))
                vim.command(
                    "try"
                    "|silent! wincmd P"
                    "|catch /^Vim\%((\a\+)\)\=:E441/"
                    "|endtry")

                if vim.eval('@%')=='vim-ipython':
                    b = vim.current.buffer
                    last_line = b[-1]
                    del b[-1]
                    b.append((last_line+reply).splitlines())
                    vim.command(str(previouswin) + 'wincmd w')
                    vim.command(str(currentwin) + 'wincmd w')

            kc.input(reply)
            if current_stdin_prompt:
                try:
                    child = get_child_msg(current_stdin_prompt['parent_msg_id'])
                except Empty:
                    pass

            current_stdin_prompt.clear()
            return True
    else:
        if not current_stdin_prompt:
            vim_echo('no input request detected')
        if not kc:
            vim_echo('not connected to IPython')
        return False


def set_pid():
    """
    Explicitly ask the ipython kernel for its pid
    """
    global pid
    code = 'import os as _os; _pid = _os.getpid()'
    msg_id = send(code, silent=True, user_expressions={'_pid':'_pid'})

    # wait to get message back from kernel
    try:
        child = get_child_msg(msg_id)
    except Empty:
        vim_echo("no reply from IPython kernel")
        return
    try:
        pid = int(child['content']['user_expressions']\
                        ['_pid']['data']['text/plain'])
    except KeyError:
        vim_echo("Could not get PID information, kernel not running Python?")
    return pid


def eval_ipy_input(var=None):
    ipy_input = vim_vars['ipy_input']
    if not ipy_input:
        return
    if ipy_input.startswith(('%', '!', '$')):
        msg_id = send('', silent=True,
                      user_expressions={'_expr': ipy_input})
    else:
        msg_id = send('from __future__ import division; '
                      '_expr = %s' % ipy_input, silent=True,
                      user_expressions={'_expr': '_expr'})
    try:
        child = get_child_msg(msg_id)
    except Empty:
        vim_echo("no reply from IPython kernel")
        return
    result = child['content']['user_expressions']
    try:
        text = result['_expr']['data']['text/plain']
        if not PY3 and isinstance(text, str):
            text = unicode(text, vim_encoding)
        if var:
            try:
                from cStringIO import StringIO
            except ImportError:
                from io import StringIO
            from tokenize import STRING, generate_tokens
            if next(generate_tokens(StringIO(text).readline))[0] == STRING:
                from ast import parse
                vim_vars[var.replace('g:', '')] = parse(text).body[0].value.s
            else:
                vim.command('let %s = "%s"' % (
                    var, text.replace('\\', '\\\\').replace('"', '\\"')))
        else:
            vim.command('call setreg(\'"\', "%s")' %
                        text.replace('\\', '\\\\').replace('"', '\\"'))
    except KeyError:
        try:
            try:
                vim_echo('{ename}: {evalue}'.format(**child['content']))
            except KeyError:
                vim_echo('{ename}: {evalue}'.format(**result['_expr']))
        except Exception:
            vim_echo('Unknown error occurred')
    else:
        if not var:
            vim.command('let @+ = @"')
            vim.command('let @* = @"')


def terminate_kernel_hack():
    "Send SIGTERM to our the IPython kernel"
    import signal
    interrupt_kernel_hack(signal.SIGTERM)

def interrupt_kernel_hack(signal_to_send=None):
    """
    Sends the interrupt signal to the remote kernel.  This side steps the
    (non-functional) ipython interrupt mechanisms.
    Only works on posix.
    """
    global pid
    import signal
    import os
    if pid is None:
        # Avoid errors if we couldn't get pid originally,
        # by trying to obtain it now
        pid = set_pid()

        if pid is None:
            vim_echo("cannot get kernel PID, Ctrl-C will not be supported")
            return
    if not signal_to_send:
        signal_to_send = signal.SIGINT

    vim_echo("KeyboardInterrupt (sent to ipython: pid " +
        "%i with signal %s)" % (pid, signal_to_send),"Operator")
    try:
        os.kill(pid, int(signal_to_send))
    except OSError:
        vim_echo("unable to kill pid %d" % pid)
        pid = None

def dedent_run_this_line():
    run_this_line(True)

def dedent_run_these_lines():
    run_these_lines(True)

def is_cell_separator(line):
    '''Determines whether a given line is a cell separator'''
    cell_sep = ['##', '#%%%%', '# <codecell>']
    for sep in cell_sep:
        if line.strip().startswith(sep):
            return True
    return False

@with_subchannel
def run_this_cell():
    '''Runs all the code in between two cell separators'''
    cur_buf = vim.current.buffer
    (cur_line, cur_col) = vim.current.window.cursor
    cur_line -= 1

    # Search upwards for cell separator
    upper_bound = cur_line
    while upper_bound > 0 and not is_cell_separator(cur_buf[upper_bound]):
        upper_bound -= 1

    # Skip past the first cell separator if it exists
    if is_cell_separator(cur_buf[upper_bound]):
        upper_bound += 1

    # Search downwards for cell separator
    lower_bound = min(upper_bound+1, len(cur_buf)-1)

    while lower_bound < len(cur_buf)-1 and not is_cell_separator(cur_buf[lower_bound]):
        lower_bound += 1

    # Move before the last cell separator if it exists
    if is_cell_separator(cur_buf[lower_bound]):
        lower_bound -= 1

    # Make sure bounds are within buffer limits
    upper_bound = max(0, min(upper_bound, len(cur_buf)-1))
    lower_bound = max(0, min(lower_bound, len(cur_buf)-1))

    # Make sure of proper ordering of bounds
    lower_bound = max(upper_bound, lower_bound)

    # Calculate minimum indentation level of entire cell
    shiftwidth = vim.eval('&shiftwidth')
    count = lambda x: int(vim.eval('indent(%d)/%s' % (x,shiftwidth)))

    min_indent = count(upper_bound+1)
    for i in range(upper_bound+1, lower_bound):
        indent = count(i)
        if indent < min_indent:
            min_indent = indent

    # Perform dedent
    if min_indent > 0:
        vim.command('%d,%d%s' % (upper_bound+1, lower_bound+1, '<'*min_indent))

    # Execute cell
    lines = "\n".join(cur_buf[upper_bound:lower_bound+1])
    msg_id = send(lines)
    prompt = "lines %d-%d "% (upper_bound+1,lower_bound+1)
    print_prompt(prompt, msg_id)

    # Re-indent
    if min_indent > 0:
        vim.command("silent undo")

#def set_this_line():
#    # not sure if there's a way to do this, since we have multiple clients
#    send("get_ipython().shell.set_next_input(\'%s\')" % vim.current.line.replace("\'","\\\'"))
#    #print("line \'%s\' set at ipython prompt"% vim.current.line)
#    echo("line \'%s\' set at ipython prompt"% vim.current.line,'Statement')


#def set_breakpoint():
#    send("__IP.InteractiveTB.pdb.set_break('%s',%d)" % (vim.current.buffer.name,
#                                                        vim.current.window.cursor[0]))
#    print("set breakpoint in %s:%d"% (vim.current.buffer.name,
#                                      vim.current.window.cursor[0]))
#
#def clear_breakpoint():
#    send("__IP.InteractiveTB.pdb.clear_break('%s',%d)" % (vim.current.buffer.name,
#                                                          vim.current.window.cursor[0]))
#    print("clearing breakpoint in %s:%d" % (vim.current.buffer.name,
#                                            vim.current.window.cursor[0]))
#
#def clear_all_breakpoints():
#    send("__IP.InteractiveTB.pdb.clear_all_breaks()");
#    print("clearing all breakpoints")
#
#def run_this_file_pdb():
#    send(' __IP.InteractiveTB.pdb.run(\'execfile("%s")\')' % (vim.current.buffer.name,))
#    #send('run -d %s' % (vim.current.buffer.name,))
#    echo("In[]: run -d %s (using pdb)" % vim.current.buffer.name)

def get_history(n, pattern=None, unique=True):
    msg_id = kc.history(
        hist_access_type='search' if pattern else 'tail',
        pattern=pattern, n=n, unique=unique,
        raw=vim_vars.get('ipython_history_raw', True))
    try:
        child = get_child_msg(
            msg_id, timeout=float(vim_vars.get('ipython_history_timeout', 2)))
        results = [(session, line, code.encode(vim_encoding))
                   for session, line, code in child['content']['history']]
    except Empty:
        vim_echo("no reply from IPython kernel")
        return []
    if unique:
        results.extend(get_session_history(pattern=pattern))
    return results

def get_session_history(session=None, pattern=None):
    from ast import literal_eval
    from fnmatch import fnmatch
    msg_id = send('', silent=True, user_expressions={
        '_hist': '[h for h in get_ipython().history_manager.get_range('
        '%s, raw=%s)]'
        % (str(session) if session else
           'get_ipython().history_manager.session_number',
           vim_vars.get('ipython_history_raw', 'True')),
        '_session': 'get_ipython().history_manager.session_number',
    })
    try:
        child = get_child_msg(
            msg_id, timeout=float(vim_vars.get('ipython_history_timeout', 2)))
        hist = child['content']['user_expressions']['_hist']
        session = child['content']['user_expressions']['_session']
        session = int(session['data']['text/plain'].encode(vim_encoding))
        hist = literal_eval(hist['data']['text/plain'])
        return [(s if s > 0 else session, l, c.encode(vim_encoding))
                for s, l, c in hist if fnmatch(c, pattern or '*')]
    except Empty:
        vim_echo("no reply from IPython kernel")
        return []
    except KeyError:
        return []


if not_in_vim:
    print('done.')

#=============================================================================
#=============================================================================
