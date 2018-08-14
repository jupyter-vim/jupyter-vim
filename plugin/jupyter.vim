"=============================================================================
"     File: jupyter.vim
"  Created: 02/28/2018, 11:10
"   Author: Bernie Roesler
"
"  Description: Set up autocmds and config variables for jupyter-vim plugin
"
"=============================================================================

if !has('pythonx') || &cp
    finish
endif

"-----------------------------------------------------------------------------
"        Configuration: {{{
"-----------------------------------------------------------------------------
" TODO rewrite as dictionary w/ loop so it's easy to add more
if !exists("g:jupyter_auto_connect")
    let g:jupyter_auto_connect = 0
endif

if !exists("g:jupyter_mapkeys")
    let g:jupyter_mapkeys = 1
endif

" Debugging flags:
if !exists('g:jupyter_monitor_console')
    let g:jupyter_monitor_console = 0
endif

if !exists('g:jupyter_verbose')
    let g:jupyter_verbose = 0
endif

"}}}----------------------------------------------------------------------------
"       Connect to Jupyter Kernel  {{{
"-------------------------------------------------------------------------------
" XXX SLOW AS $@#!... need to figure out how to fork the connection process so
" vim still fires up quickly even if we forget to have a kernel running, or it
" can't connect for some reason.
if g:jupyter_auto_connect
    " Add other filetypes here for other kernels!!
    augroup JConnect
        autocmd!
        autocmd FileType python JupyterConnect
    augroup END
endif
"=============================================================================
"=============================================================================
