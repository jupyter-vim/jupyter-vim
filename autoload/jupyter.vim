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

" See ~/.vim/bundle/jedi-vim/autoload/jedi.vim for initialization routine
function! s:init_python() abort
    let s:init_outcome = 0
    let init_lines = [
          \ 'import sys; import os; import vim',
          \ 'vim_path, _ = os.path.split(vim.eval("expand(''<sfile>:p:h'')"))',
          \ 'vim_pythonx_path = os.path.join(vim_path, "pythonx")',
          \ 'if vim_pythonx_path not in sys.path:',
          \ '    sys.path.append(vim_pythonx_path)',
          \ 'try:',
          \ '    import jupyter_vim',
          \ 'except Exception as exc:',
          \ '    vim.command(''let s:init_outcome = "could not import jupyter_vim:'
          \                    .'{0}: {1}"''.format(exc.__class__.__name__, exc))',
          \ 'else:',
          \ '    vim.command(''let s:init_outcome = 1'')']

    " Try running lines via python, which will set script variable
    try
        execute 'Pythonx exec('''.escape(join(init_lines, '\n'), "'").''')'
    catch
        throw printf('[jupyter-vim] s:init_python: failed to run Python for initialization: %s.', v:exception)
    endtry

    if s:init_outcome is 0
        throw '[jupyter-vim] s:init_python: failed to run Python for initialization.'
    elseif s:init_outcome isnot 1
        throw printf('[jupyter-vim] s:init_python: %s.', s:init_outcome)
    endif

    return 1
endfunction

" Public initialization routine
let s:_init_python = -1
function! jupyter#init_python() abort
    if s:_init_python == -1
        let s:_init_python = 0
        try
            let s:_init_python = s:init_python()
            let s:_init_python = 1
        catch /^jupyter/
            " Only catch errors from jupyter-vim itself here, so that for
            " unexpected Python exceptions the traceback will be shown
            echoerr 'Error: jupyter-vim failed to initialize Python: '
                        \ . v:exception . ' (in ' . v:throwpoint . ')'
            " throw v:exception
        endtry
    endif
    return s:_init_python
endfunction

"-----------------------------------------------------------------------------
"        Vim -> Jupyter Public Functions:
"-----------------------------------------------------------------------------
function! jupyter#Connect(...) abort
    " call jupyter#init_python()
    let l:kernel_file = a:0 > 0 ? a:1 : '*.json'
    Pythonx jupyter_vim.connect_to_kernel(
                \ jupyter_vim.vim2py_str(
                \     vim.current.buffer.vars['jupyter_kernel_type']),
                \ filename=vim.eval('l:kernel_file'))
endfunction

function! jupyter#CompleteConnect(ArgLead, CmdLine, CursorPos) abort
    " Pre-Declare variable <- setted from python
    let l:kernel_ids = []
    " Get kernel id from python
    Pythonx jupyter_vim.find_jupyter_kernels()
    " Filter id matching user arg
    call filter(l:kernel_ids, '-1 != match(v:val, a:ArgLead)')
    " Return list
    return l:kernel_ids
endfunction

function! jupyter#Disconnect(...) abort
    Pythonx jupyter_vim.disconnect_from_kernel()
endfunction

function! jupyter#JupyterCd(...) abort 
    " Behaves just like typical `cd`.
    let l:dirname = a:0 ? a:1 : ''
    if b:jupyter_kernel_type == 'python'
        JupyterSendCode '%cd "'.escape(l:dirname, '"').'"'
    elseif b:jupyter_kernel_type == 'julia'
        JupyterSendCode 'cd("'.escape(l:dirname, '"').'")'
    else
        echoerr 'I don''t know how to do the `cd` command in Jupyter kernel'
                \ . ' type "' . b:jupyter_kernel_type . '"'
    endif
endfunction

function! jupyter#RunFile(...) abort
    " filename is the last argument on the command line
    let l:flags = (a:0 > 1) ? join(a:000[:-2], ' ') : ''
    let l:filename = a:0 ? a:000[-1] : expand("%:p")
    if b:jupyter_kernel_type == 'python'
        Pythonx jupyter_vim.run_file_in_ipython(
                    \ flags=vim.eval('l:flags'),
                    \ filename=vim.eval('l:filename'))
    elseif b:jupyter_kernel_type == 'julia'
        if l:flags != ''
            echoerr 'RunFile in kernel type "julia" doesn''t support flags.'
                \ . ' All arguments except the last (file location) will be'
                \ . ' ignored.'
        endif
        JupyterSendCode 'include("""'.escape(l:filename, '"').'""")'
    else
        echoerr 'I don''t know how to do the `RunFile` command in Jupyter'
            \ . ' kernel type "' . b:jupyter_kernel_type . '"'
    endif
endfunction

function! jupyter#SendCell() abort
    Pythonx jupyter_vim.run_cell()
endfunction

function! jupyter#SendCode(code) abort
    " NOTE: 'run_command' gives more checks than just raw 'send'
    Pythonx jupyter_vim.run_command(vim.eval('a:code'))
endfunction

function! jupyter#SendRange() range abort
    execute a:firstline . ',' . a:lastline . 'Pythonx jupyter_vim.send_range()'
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
    if a:kill
        let l:sig='SIGKILL'
    elseif a:0 > 0
        let l:sig=a:1
        echom 'Sending signal: '.l:sig
    else
        let l:sig='SIGTERM'
    endif
    " Check signal here?
    execute 'Pythonx jupyter_vim.signal_kernel(jupyter_vim.signal.'.l:sig.')'
endfunction

function! jupyter#UpdateShell() abort
    Pythonx jupyter_vim.update_console_msgs()
endfunction

"-----------------------------------------------------------------------------
"        Operator Function:
"-----------------------------------------------------------------------------
" TODO rewrite this function as a general wrapper that accepts a function (of
" one argument) that will act on the text object, and returns an
" function that may be used as an operatorfunction. Then we don't need to
" rewrite this opfunc, just changing the line that handles 'l:cmd' every time.
function! s:opfunc(type)
    " Originally from tpope/vim-scriptease
    let sel_save = &selection
    let cb_save = &clipboard
    let reg_save = @@
    let left_save = getpos("'<")
    let right_save = getpos("'>")
    let vimode_save = visualmode()
    try
        set selection=inclusive clipboard-=unnamed clipboard-=unnamedplus
        if a:type =~ '^\d\+$'
            silent exe 'normal! ^v'.a:type.'$hy'
        elseif a:type =~# '^.$'
            silent exe "normal! `<" . a:type . "`>y"
        elseif a:type ==# 'line'
            silent exe "normal! '[V']y"
        elseif a:type ==# 'block'
            silent exe "normal! `[\<C-V>`]y"
        elseif a:type ==# 'visual'
            silent exe "normal! gvy"
        else
            silent exe "normal! `[v`]y"
        endif
        redraw
        let l:cmd = @@
    finally
        let @@ = reg_save
        let &selection = sel_save
        let &clipboard = cb_save
        exe "normal! " . vimode_save . "\<Esc>"
        call setpos("'<", left_save)
        call setpos("'>", right_save)
    endtry
    " Send the text to jupyter kernel
    call jupyter#SendCode(l:cmd)
endfunction

"-----------------------------------------------------------------------------
"        Auxiliary Functions:
"-----------------------------------------------------------------------------
function! jupyter#PythonDbstop()
    " Set a debugging breakpoint for use with pdb
    normal! Oimport pdb; pdb.set_trace()j
endfunction

function! jupyter#MakeStandardCommands()
    " Standard commands, called from each ftplugin so that we only map the
    " keys buffer-local for select filetypes.
    command! -buffer -nargs=* -complete=customlist,jupyter#CompleteConnect
          \ JupyterConnect call jupyter#Connect(<f-args>)
    command! -buffer -nargs=0    JupyterDisconnect      call jupyter#Disconnect()
    command! -buffer -nargs=1    JupyterSendCode        call jupyter#SendCode(<args>)
    command! -buffer -count      JupyterSendCount       call jupyter#SendCount(<count>)
    command! -buffer -range -bar JupyterSendRange       <line1>,<line2>call jupyter#SendRange()
    command! -buffer -nargs=0    JupyterSendCell        call jupyter#SendCell()
    command! -buffer -nargs=0    JupyterUpdateShell     call jupyter#UpdateShell()
    command! -buffer -nargs=? -complete=dir  JupyterCd  call jupyter#JupyterCd(<f-args>)
    command! -buffer -nargs=? -bang  JupyterTerminateKernel  call jupyter#TerminateKernel(<bang>0, <f-args>)
    command! -buffer -nargs=* -complete=file
                \ JupyterRunFile update | call jupyter#RunFile(<f-args>)
endfunction

function! jupyter#MapStandardKeys()
    " Standard keymaps, called from each ftplugin so that we only map the keys
    " buffer-local for select filetypes.
    nnoremap <buffer> <silent> <localleader>R       :JupyterRunFile<CR>

    " Change to directory of current file
    nnoremap <buffer> <silent> <localleader>d       :JupyterCd %:p:h<CR>

    " Send just the current line
    nnoremap <buffer> <silent> <localleader>X       :JupyterSendCell<CR>
    nnoremap <buffer> <silent> <localleader>E       :JupyterSendRange<CR>
    nmap     <buffer> <silent> <localleader>e       <Plug>JupyterRunTextObj
    vmap     <buffer> <silent> <localleader>e       <Plug>JupyterRunVisual

    nnoremap <buffer> <silent> <localleader>U       :JupyterUpdateShell<CR>
endfunction

" NOTE: Generally unused except for communication debugging
function! jupyter#OpenJupyterTerm() abort
    " Set up console display window
    " If we're in the console display already, just go to the bottom.
    " Otherwise, create a new buffer in a split (or jump to it if open)
    let term_buf = '__jupyter_term__'
    if @% ==# term_buf
        normal! G
    else
        try
            let save_swbuf=&switchbuf
            set switchbuf=useopen
            let l:cmd = bufnr(term_buf) > 0 ? 'sbuffer' : 'new'
            execute l:cmd . ' ' . term_buf
            let &switchbuf=save_swbuf
        catch
            return 0
        endtry
    endif

    " Make sure buffer is a scratch buffer before we write to it
    setlocal bufhidden=hide buftype=nofile
    setlocal nobuflisted nonumber noswapfile
    setlocal syntax=python

    " Clear out any autocmds that trigger on Insert for the console buffer
    autocmd! InsertEnter,InsertLeave <buffer>

    " Syntax highlighting for prompt
    syn match JupyterPromptIn /^\(In \[[ 0-9]*\]:\)\|\(\s*\.\{3}:\)/
    syn match JupyterPromptOut /^Out\[[ 0-9]*\]:/
    syn match JupyterPromptOut2 /^\.\.\.* /
    syn match JupyterMagic /^\]: \zs%\w\+/

    hi JupyterPromptIn   ctermfg=Blue
    hi JupyterPromptOut  ctermfg=Red
    hi JupyterPromptOut2 ctermfg=Grey
    hi JupyterMagic      ctermfg=Magenta

    return 1
endfunction

"-----------------------------------------------------------------------------
"        Create <Plug> for user mappings
"-----------------------------------------------------------------------------
noremap <silent> <Plug>JupyterRunTextObj    :<C-u>set operatorfunc=<SID>opfunc<CR>g@
noremap <silent> <Plug>JupyterRunVisual     :<C-u>call <SID>opfunc(visualmode())<CR>

"=============================================================================
"=============================================================================
