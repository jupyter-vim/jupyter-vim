"=============================================================================
"     File: ftplugin/python/jupyter.vim
"  Created: 2019-03-03 16:37
"   Author: Bernie Roesler
"
"  Description: Python-specific settings, commands and mappings
"
"=============================================================================

" User-specified flags for IPython's run file magic can be set per-buffer
let b:ipython_run_flags = ''

"}}}--------------------------------------------------------------------------
"        Commands: {{{
"-----------------------------------------------------------------------------
command! -buffer -nargs=0 -complete=file
            \ PythonImportThisFile update | call jupyter#RunFile('-n', expand("%:p"))

" Debugging commands
command! -nargs=0   PythonSetBreak  call jupyter#PythonDbstop()

"}}}--------------------------------------------------------------------------
"        Key Mappings: {{{
"-----------------------------------------------------------------------------
if exists('g:jupyter_mapkeys') && g:jupyter_mapkeys
    " Run the current file
    nnoremap <buffer> <silent> <localleader>I :PythonImportThisFile<CR>

    " Debugging maps
    nnoremap <buffer> <silent> <localleader>b :PythonSetBreak<CR>
endif
"}}}

"=============================================================================
"=============================================================================
