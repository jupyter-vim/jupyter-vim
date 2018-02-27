"=============================================================================
"     File: autoload/jupyter.vim
"  Created: 02/21/2018, 22:24
"   Author: Bernie Roesler
"
"  Description: Autoload vim functions for use in jupyter-vim plugin
"
"=============================================================================

"----------------------------------------------------------------------------- 
"        Default Setings: {{{
"-----------------------------------------------------------------------------

"}}}-------------------------------------------------------------------------- 
"        Python Initialization: {{{
"-----------------------------------------------------------------------------
" See ~/.vim/bundle/jedi-vim/autoload/jedi.vim for initialization routine
function! s:init_python() abort
    let s:init_outcome = 0
    let init_lines = [
          \ 'import vim',
          \ 'try:',
          \ '    import jupyter_vim',
          \ 'except Exception as exc:',
          \ '    vim.command(''let s:init_outcome = "could not import jupyter_vim: {0}: {1}"''.format(exc.__class__.__name__, exc))',
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
"}}}

"----------------------------------------------------------------------------- 
"        Vim -> Python Functions:
"-----------------------------------------------------------------------------
function! jupyter#Connect() abort
    pythonx jupyter_vim.connect_to_kernel()
endfunction

function! jupyter#RunFile(...) abort
    " filename is the last argument on the command line
    let l:flags = (a:0 > 1) ? join(a:000[:-2], ' ') : ''
    let l:filename = a:0 ? a:000[-1] : expand("%:p")
    " not the prettiest way to do kwargs... but it works.
    execute "pythonx jupyter_vim.run_file(flags='" . l:flags
                \ . "', filename='" . l:filename . "')"
endfunction

"----------------------------------------------------------------------------- 
"        Operator Function: {{{
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
    " Send the text to ipython
    pythonx jupyter_vim.send(textwrap.dedent(vim.eval('l:cmd')))
endfunction
"}}}
"
"----------------------------------------------------------------------------- 
"        Create <Plug> for user mappings
"-----------------------------------------------------------------------------
noremap <silent> <Plug>JupyterRunTextObj    :<C-u>set operatorfunc=<SID>opfunc<CR>g@
noremap <silent> <Plug>JupyterRunVisual     :<C-u>call <SID>opfunc(visualmode())<CR>

"=============================================================================
"=============================================================================
