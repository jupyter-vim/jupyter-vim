"=============================================================================
"    File: ftplugin/python/jupyter_vim.vim
" Created: 07/28/11 22:14:58
"  Author: Paul Ivanov (http://pirsquared.org)
"  Updated: [02/14/2018, 12:31] Bernie Roesler
"
" Description: Vim integration with Jupyter [Qt]Console running ipython
"=============================================================================

if exists("b:loaded_jupyter")
    finish
endif

if !jupyter#init_python()
    finish
endif

"-----------------------------------------------------------------------------
"        Configuration: {{{
"-----------------------------------------------------------------------------
" flags for Jupyter's run file magic
if !exists('b:ipython_run_flags')
    let b:ipython_run_flags = ''
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
            \ JupyterImportThisFile update | call jupyter#RunFile('-n', expand("%:p"))

" Debugging commands
command! -buffer -nargs=0   PythonSetBreak  call jupyter#PythonDbstop()

"}}}--------------------------------------------------------------------------
"        Key Mappings: {{{
"-----------------------------------------------------------------------------
if g:jupyter_mapkeys
    nnoremap <buffer> <silent> <localleader>R       :JupyterRunFile<CR>
    nnoremap <buffer> <silent> <localleader>I       :JupyterImportThisFile<CR>

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

let b:loaded_jupyter = 1
"=============================================================================
"=============================================================================
