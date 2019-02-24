" TODO(bzinberg): Can we factor out the common parts between this an
" ftplugin/python/jupyter.vim?  (Not sure how to do this in vimscript while
" respecting python imports)

if exists("b:loaded_jupyter_julia")
    finish
endif

if !jupyter#init_python()
    finish
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

"}}}--------------------------------------------------------------------------
"        Key Mappings: {{{
"-----------------------------------------------------------------------------
if g:jupyter_mapkeys
    " Change to directory of current file
    nnoremap <buffer> <silent> <localleader>d       :JupyterCd %:p:h<CR>

    " Send just the current line
    nnoremap <buffer> <silent> <localleader>X       :JupyterSendCell<CR>
    nnoremap <buffer> <silent> <localleader>E       :JupyterSendRange<CR>
    nmap     <buffer> <silent> <localleader>e       <Plug>JupyterRunTextObj
    vmap     <buffer> <silent> <localleader>e       <Plug>JupyterRunVisual

    nnoremap <buffer> <silent> <localleader>U       :JupyterUpdateShell<CR>

endif
"}}}

let b:loaded_jupyter_julia = 1
"=============================================================================
"=============================================================================
