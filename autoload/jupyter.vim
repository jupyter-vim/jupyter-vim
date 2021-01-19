"=============================================================================
"     File: autoload/jupyter.vim
"  Created: 02/21/2018, 22:24
"   Author: Bernie Roesler
"
"  Description: Autoload vim functions for use in jupyter-vim plugin
"
"=============================================================================
"        Python Initialization:
"-----------------------------------------------------------------------------
" Neovim doesn't have the pythonx command, so we define a new command Pythonx
" that works for both vim and neovim.
if has('pythonx')
    command! -range -nargs=+ Pythonx <line1>,<line2>pythonx <args>
elseif has('python3')
    command! -range -nargs=+ Pythonx <line1>,<line2>python3 <args>
elseif has('python')
    command! -range -nargs=+ Pythonx <line1>,<line2>python <args>
endif

" Define Pyeval: python str -> vim variable
function! Pyevalx(str) abort
    if has('pythonx')
        return pyxeval(a:str)
    elseif has('python3')
        return py3eval(a:str)
    elseif has('python')
        return pyeval(a:str)
    endif
endfunction

" See ~/.vim/bundle/jedi-vim/autoload/jedi.vim for initialization routine
function! s:init_python() abort
    let s:init_outcome = 0
    let init_lines = [
          \ '# Add path',
          \ 'import os; import sys; import vim',
          \ 'vim_path, _ = os.path.split(vim.eval("expand(''<sfile>:p:h'')"))',
          \ 'vim_pythonx_path = os.path.join(vim_path, "pythonx")',
          \ 'if vim_pythonx_path not in sys.path:',
          \ '    sys.path.append(vim_pythonx_path)',
          \ '',
          \ '# Import',
          \ 'try:',
          \ '    from jupyter_vim import JupyterVimSession',
          \ '    _jupyter_session = JupyterVimSession()',
          \
          \ '    # For direct calls',
          \ '    from jupyter_util import str_to_py, find_jupyter_kernel_ids, find_signals',
          \ 'except Exception as exc:',
          \ '    vim.bindeval("s:")["init_outcome"] = ("could not import jupyter_vim <- {0}: {1}".format(exc.__class__.__name__, exc))',
          \ 'else:',
          \ '    vim.command("let s:init_outcome = 1")'
          \ ]

    " Try running lines via python, which will set script variable
    try
        execute 'Pythonx exec('''.escape(join(init_lines, '\n'), "'").''')'
    catch
        throw printf('[jupyter-vim] s:init_python: failed to run Python for initialization: %s', v:exception)
    endtry

    if s:init_outcome isnot 1
        throw printf('[jupyter-vim] s:init_python: s:init_outcome = %s', s:init_outcome)
    endif

    return 1
endfunction

" Public initialization routine
let s:_init_python = -1
function! jupyter#init_python() abort
    " Check in
    if s:_init_python != -1 | return s:_init_python | endif
    let s:_init_python = 0
    try
        let s:_init_python = s:init_python()
        let s:_init_python = 1
    catch /^\[jupyter-vim\]/
        " Only catch errors from jupyter-vim itself here, so that for
        " unexpected Python exceptions the traceback will be shown
        echohl Error
        echomsg 'Error: jupyter-vim failed to initialize Python: '
        echohl WarningMsg
        for line in split(v:exception, "\n")
            echomsg '  ' . line
        endfor
        echomsg '(in ' . v:throwpoint . ')'
        echohl None
        " throw v:exception
    endtry
    return s:_init_python
endfunction

" Do not initialize python until this autoload script is called for
" a compatible filetype (usually via jupyter#Connect).
call jupyter#init_python()

"-----------------------------------------------------------------------------
"        Vim -> Jupyter Public Functions:
"-----------------------------------------------------------------------------

function! jupyter#Connect(...) abort
    let l:kernel_file = a:0 > 0 ? a:1 : '*.json'
    Pythonx _jupyter_session.connect_to_kernel(
                \ str_to_py(vim.current.buffer.vars['jupyter_kernel_type']),
                \ filename=vim.eval('l:kernel_file'))
endfunction

function! jupyter#CompleteConnect(ArgLead, CmdLine, CursorPos) abort
    " Get kernel id from python
    let l:kernel_ids = Pyevalx('find_jupyter_kernel_ids()')
    " Filter id matching user arg
    call filter(l:kernel_ids, '-1 != match(v:val, a:ArgLead)')
    " Return list
    return l:kernel_ids
endfunction

function! jupyter#Disconnect(...) abort
    Pythonx _jupyter_session.disconnect_from_kernel()
endfunction

function! jupyter#JupyterCd(...) abort 
    " Behaves just like typical `cd`.
    let l:dirname = a:0 ? a:1 : "$HOME"
    " Helpers:
    " " . -> vim cwd
    if l:dirname ==# '.' | let l:dirname = getcwd() | endif
    " " % -> %:p
    if l:dirname ==# expand('%') | let l:dirname = '%:p:h' | endif
    " Expand (to get %)
    let l:dirname = expand(l:dirname)
    let l:dirname = escape(l:dirname, '"')
    Pythonx _jupyter_session.change_directory(vim.eval('l:dirname'))
endfunction

function! jupyter#RunFile(...) abort
    " filename is the last argument on the command line
    let l:flags = (a:0 > 1) ? join(a:000[:-2], ' ') : ''
    let l:filename = a:0 ? a:000[-1] : expand('%:p')
    Pythonx _jupyter_session.run_file(
                \ flags=vim.eval('l:flags'),
                \ filename=vim.eval('l:filename'))
endfunction

function! jupyter#SendCell() abort
    Pythonx _jupyter_session.run_cell()
endfunction

function! jupyter#SendCode(code) abort
    " NOTE: 'run_command' gives more checks than just raw 'send'
    Pythonx _jupyter_session.run_command(vim.eval('a:code'))
endfunction

function! jupyter#SendRange() range abort
    execute a:firstline . ',' . a:lastline . 'Pythonx _jupyter_session.send_range()'
endfunction

function! jupyter#SendCount(count) abort
    " TODO move this function to pure(ish) python like SendRange
    let sel_save = &selection
    let cb_save = &clipboard
    let reg_save = @@
    try
        set selection=inclusive clipboard-=unnamed clipboard-=unnamedplus
        silent execute 'normal! ' . a:count . 'yy'
        let l:cmd = @@
    finally
        let @@ = reg_save
        let &selection = sel_save
        let &clipboard = cb_save
    endtry
    call jupyter#SendCode(l:cmd)
endfunction

function! jupyter#TerminateKernel(kill, ...) abort
    if a:kill && !has('win32') && !has('win64')
        let l:sig='SIGKILL'
    elseif a:0 > 0
        let l:sig=a:1
        echom 'Sending signal: '.l:sig
    else
        let l:sig='SIGTERM'
    endif
    execute 'Pythonx _jupyter_session.signal_kernel("'.l:sig.'")'
endfunction

function! jupyter#CompleteTerminateKernel(ArgLead, CmdLine, CursorPos) abort
    " Get signals from Python
    let l:signals = Pyevalx('find_signals()')
    " Filter signal with user arg
    call filter(l:signals, '-1 != match(v:val, a:ArgLead)')
    " Return list
    return l:signals
endfunction

function! jupyter#UpdateMonitor() abort
    let g:jupyter_monitor_console = 1
    Pythonx _jupyter_session.update_monitor_msgs()
endfunction


"-----------------------------------------------------------------------------
"        Auxiliary Functions:
"-----------------------------------------------------------------------------

function! jupyter#PythonDbstop() abort
    " Set a debugging breakpoint for use with pdb
    normal! Oimport pdb; pdb.set_trace()
    normal! j
endfunction

" Timer callback to fill jupyter console buffer
function! jupyter#UpdateEchom(timer) abort
    Pythonx _jupyter_session.vim_client.timer_echom()
endfunction

"=============================================================================
"=============================================================================
