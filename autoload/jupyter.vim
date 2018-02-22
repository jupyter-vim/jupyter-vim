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
"=============================================================================
"=============================================================================
