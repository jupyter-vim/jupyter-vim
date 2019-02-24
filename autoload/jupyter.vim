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
" See ~/.vim/bundle/jedi-vim/autoload/jedi.vim for initialization routine
function! s:init_python() abort 
    let s:init_outcome = 0
    let init_lines = [
          \ 'import vim',
          \ 'try:',
          \ '    import jupyter_vim',
          \ 'except Exception as exc:',
          \ '    vim.command(''let s:init_outcome = "could not import jupyter_vim:'
          \                    .'{0}: {1}"''.format(exc.__class__.__name__, exc))',
          \ 'else:',
          \ '    vim.command(''let s:init_outcome = 1'')']

    " Try running lines via python, which will set script variable
    try
        execute 'pythonx exec('''.escape(join(init_lines, '\n'), "'").''')'
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

" Runs s:init_python if it hasn't already been run.  This routine can be
" called at the beginning of every routine that expects init_python to have
" already been run.
let s:_init_python_retstatus = -1
function! s:init_python_once() abort
    if s:_init_python_retstatus == -1
        try
            echo 'Initializing Jupyter client...'
            let s:_init_python_retstatus = s:init_python()
            echo 'Jupyter client initialized.'
        catch
            let s:_init_python_retstatus = 0
            throw v:exception
        endtry
    endif
    return s:_init_python_retstatus
endfunction

" Public initialization routine.  Same as `s:init_python_once` but prints
" error instead of throwing.
function! jupyter#init_python() abort
    try
        call s:init_python_once()
    catch
        echoerr 'Error: jupyter-vim failed to initialize Python: '
                    \ . v:exception . ' (in ' . v:throwpoint . ')'
    endtry
    return s:_init_python_retstatus
endfunction

"----------------------------------------------------------------------------- 
"        Vim -> Jupyter Public Functions: 
"-----------------------------------------------------------------------------
function! jupyter#Connect() abort 
    call s:init_python_once()
    pythonx jupyter_vim.connect_to_kernel(
                \ vim.current.buffer.vars['jupyter_kernel_type'])
endfunction

function! jupyter#JupyterCd(...) abort 
    call s:init_python_once()
    " Behaves just like typical `cd`.  Different kernel types have different
    " syntaxes for this command.
    let l:dirname = a:0 ? a:1 : ''
    if b:jupyter_kernel_type == 'python'
        JupyterSendCode '%cd """'.escape(l:dirname, '"').'"""'
    elseif b:jupyter_kernel_type == 'julia'
        JupyterSendCode 'cd("""'.escape(l:dirname, '"').'""")'
    else
        echoerr 'I don''t know how to do the `cd` command in Jupyter kernel'
                    \ . ' type "' . b:jupyter_kernel_type . '"'
    endif
endfunction

function! jupyter#RunFile(...) abort 
    call s:init_python_once()
    " filename is the last argument on the command line
    let l:flags = (a:0 > 1) ? join(a:000[:-2], ' ') : ''
    let l:filename = a:0 ? a:000[-1] : expand("%:p")
    if b:jupyter_kernel_type == 'python'
        pythonx jupyter_vim.run_file_in_ipython(
                    \ flags=vim.eval('l:flags'),
                    \ filename=vim.eval('l:filename'))
    elseif b:jupyter_kernel_type == 'julia'
        if l:flags != ''
            echoerr 'RunFile in kernel type "julia" doesn''t support flags.'
                \ . ' All arguments except the last (file location) will be'
                \ . ' ignored.'
        endif
        JupyterSendCode 'include("""'.escape(l:filename, '"').'"""")'
    else
        echoerr 'I don''t know how to do the `RunFile` command in Jupyter'
            \ . ' kernel type "' . b:jupyter_kernel_type . '"'
    endif
endfunction

function! jupyter#SendCell() abort 
    call s:init_python_once()
    pythonx jupyter_vim.run_cell()
endfunction

function! jupyter#SendCode(code) abort 
    call s:init_python_once()
    " NOTE: 'run_command' gives more checks than just raw 'send'
    pythonx jupyter_vim.run_command(vim.eval('a:code'))
endfunction

function! jupyter#SendRange() range abort 
    call s:init_python_once()
    execute a:firstline . ',' . a:lastline . 'pythonx jupyter_vim.send_range()'
endfunction

function! jupyter#SendCount(count) abort 
    call s:init_python_once()
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
    call s:init_python_once()
    if a:kill
        let l:sig='SIGKILL'
    elseif a:0 > 0
        let l:sig=a:1
        echom 'Sending signal: '.l:sig
    else
        let l:sig='SIGTERM'
    endif
    " Check signal here?
    execute 'pythonx jupyter_vim.signal_kernel(jupyter_vim.signal.'.l:sig.')'
endfunction

function! jupyter#UpdateShell() abort 
    pythonx jupyter_vim.update_console_msgs()
endfunction

"----------------------------------------------------------------------------- 
"        Operator Function: 
"-----------------------------------------------------------------------------
" TODO rewrite this function as a general wrapper that accepts a function (of
" one argument) that will act on the text object, and returns an
" function that may be used as an operatorfunction. Then we don't need to
" rewrite this opfunc, just changing the line that handles 'l:cmd' every time.
function! s:opfunc(type)
    call s:init_python_once()
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
    if b:jupyter_kernel_type != 'python'
        echoerr 'Jupyter kernel is not in Python, are you sure you want to'
                \ . 'insert a Python breakpoint?'
    endif
    " Set a debugging breakpoint for use with pdb
    normal! Oimport pdb; pdb.set_trace()j
endfunction

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
