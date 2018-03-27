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

" Public initialization routine
let s:_init_python = -1
function! jupyter#init_python() abort 
    if s:_init_python == -1
        try
            let s:_init_python = s:init_python()
        catch
            let s:_init_python = 0
            echoerr 'Error: jupyter-vim failed to initialize Python: '
                        \ . v:exception . ' (in ' . v:throwpoint . ')'
        endtry
    endif
    return s:_init_python
endfunction

"----------------------------------------------------------------------------- 
"        Vim -> Python Public Functions: 
"-----------------------------------------------------------------------------
function! jupyter#Connect() abort 
    pythonx jupyter_vim.connect_to_kernel()
endfunction

function! jupyter#JupyterCd(...) abort 
    " Behaves just like typical `cd`
    let l:dirname = a:0 ? a:1 : ''
    JupyterSendCode '%cd '.l:dirname
endfunction

function! jupyter#RunFile(...) abort 
    " filename is the last argument on the command line
    let l:flags = (a:0 > 1) ? join(a:000[:-2], ' ') : ''
    let l:filename = a:0 ? a:000[-1] : expand("%:p")
    pythonx jupyter_vim.run_file(flags=vim.eval('l:flags'),
                               \ filename=vim.eval('l:filename'))
endfunction

function! jupyter#SendCell() abort 
    pythonx jupyter_vim.run_cell()
endfunction

function! jupyter#SendCode(code) abort 
    " NOTE: 'run_command' gives more checks than just raw 'send'
    pythonx jupyter_vim.run_command(vim.eval('a:code'))
endfunction

function! jupyter#SendRange() range abort 
    execute a:firstline . ',' . a:lastline . 'pythonx jupyter_vim.send_range()'
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
