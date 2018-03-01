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

if !jupyter#init_python()
    finish
endif

"-----------------------------------------------------------------------------
"        Configuration: {{{
"-----------------------------------------------------------------------------
if !exists("g:jupyter_auto_connect")
    let g:jupyter_auto_connect = 1
endif

if !exists("g:jupyter_mapkeys")
    let g:jupyter_mapkeys = 1
endif

if !exists('g:ipy_monitor_subchannel')
    let g:ipy_monitor_subchannel = 1
endif

"}}}----------------------------------------------------------------------------
"       Connect to Jupyter Kernel  {{{
"-------------------------------------------------------------------------------
if g:jupyter_auto_connect
    " Add other filetypes here for other kernels!!
    augroup JConnect
        autocmd!
        autocmd FileType python JupyterConnect

        " TODO create a BufClose command to check if we're the last python
        " file and close the connection
    augroup END
endif
"=============================================================================
"=============================================================================
