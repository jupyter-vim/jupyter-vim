"=============================================================================
"     File: plugin/jupyter.vim
"  Created: 02/28/2018, 11:10
"   Author: Bernie Roesler
"
"  Description: Set up autocmds and config variables for jupyter-vim plugin
"
"=============================================================================

if exists("g:loaded_jupyter_vim") || !has('pythonx') || &cp
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

augroup JupyterVimInit
    " By default, guess the kernel language based on the filetype. The user
    " can override this guess on a per-buffer basis.
    autocmd BufEnter * let b:jupyter_kernel_type = get({
        \ 'python': 'python',
        \ 'julia': 'julia',
        \ }, &filetype, 'none')
augroup END

"}}}----------------------------------------------------------------------------
"       Connect to Jupyter Kernel  {{{
"-------------------------------------------------------------------------------
" XXX SLOW AS $@#!... need to figure out how to fork the connection process so
" vim still fires up quickly even if we forget to have a kernel running, or it
" can't connect for some reason.
if g:jupyter_auto_connect
    augroup JConnect
        autocmd!
        autocmd FileType julia,python JupyterConnect
    augroup END
endif

"}}}--------------------------------------------------------------------------
"        Commands: {{{
"-----------------------------------------------------------------------------
command! -nargs=0    JupyterConnect         call jupyter#Connect()
command! -nargs=1    JupyterSendCode        call jupyter#SendCode(<args>)
command! -count      JupyterSendCount       call jupyter#SendCount(<count>)
command! -range -bar JupyterSendRange       <line1>,<line2>call jupyter#SendRange()
command! -nargs=0    JupyterSendCell        call jupyter#SendCell()
command! -nargs=0    JupyterUpdateShell     call jupyter#UpdateShell()
command! -nargs=? -complete=dir  JupyterCd  call jupyter#JupyterCd(<f-args>)
command! -nargs=? -bang  JupyterTerminateKernel  call jupyter#TerminateKernel(<bang>0, <f-args>)

command! -nargs=* -complete=file
            \ JupyterRunFile update | call jupyter#RunFile(<f-args>)
"}}}

let g:loaded_jupyter_vim = 1
"=============================================================================
"=============================================================================
