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

augroup JupyterVimInit
    " User-specified flags for IPython's run file magic can be set per-buffer
    " (affects Python kernels only)
    autocmd BufEnter * let b:ipython_run_flags = ''
    " By default, guess the kernel language based on the filetype, according
    " to the mapping below.  The user can override this guess on a per-buffer
    " basis.
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
        autocmd FileType python JupyterConnect
        autocmd FileType julia JupyterConnect
    augroup END
endif

"}}}--------------------------------------------------------------------------
"        Commands: {{{
"-----------------------------------------------------------------------------
command! -buffer -nargs=0    JupyterConnect         call jupyter#Connect()
command! -buffer -nargs=1    JupyterSendCode        call jupyter#SendCode(<args>)
command! -buffer -count      JupyterSendCount       call jupyter#SendCount(<count>)
command! -buffer -range -bar JupyterSendRange       <line1>,<line2>call jupyter#SendRange()
command! -buffer -nargs=0    JupyterSendCell        call jupyter#SendCell()
command! -buffer -nargs=0    JupyterUpdateShell     call jupyter#UpdateShell()
command! -buffer -nargs=? -complete=dir  JupyterCd  call jupyter#JupyterCd(<f-args>)
command! -buffer -nargs=? -bang  JupyterTerminateKernel  call jupyter#TerminateKernel(<bang>0, <f-args>)

command! -buffer -nargs=* -complete=file
            \ JupyterRunFile update | call jupyter#RunFile(<f-args>)
command! -buffer -nargs=0 -complete=file
            \ PythonImportThisFile update | call jupyter#PythonImportThisFile()

" Debugging commands
command! -buffer -nargs=0   PythonSetBreak  call jupyter#PythonDbstop()

"}}}--------------------------------------------------------------------------
"        Key Mappings: {{{
"-----------------------------------------------------------------------------
if g:jupyter_mapkeys
    nnoremap <buffer> <silent> <localleader>R       :JupyterRunFile<CR>
    nnoremap <buffer> <silent> <localleader>I       :PythonImportThisFile<CR>

    " Change to directory of current file
    nnoremap <buffer> <silent> <localleader>d       :JupyterCd %:p:h<CR>

    " Send just the current line
    nnoremap <buffer> <silent> <localleader>X       :JupyterSendCell<CR>
    nnoremap <buffer> <silent> <localleader>E       :JupyterSendRange<CR>
    nmap     <buffer> <silent> <localleader>e       <Plug>JupyterRunTextObj
    vmap     <buffer> <silent> <localleader>e       <Plug>JupyterRunVisual

    nnoremap <buffer> <silent> <localleader>U       :JupyterUpdateShell<CR>

    " Debugging maps
    nnoremap <buffer> <silent> <localleader>b       :PythonSetBreak<CR>

endif
"}}}

"=============================================================================
"=============================================================================
