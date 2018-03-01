"=============================================================================
"    File: ftplugin/python/jupyter_vim.vim
" Created: 07/28/11 22:14:58
"  Author: Paul Ivanov (http://pirsquared.org)
"  Updated: [02/14/2018, 12:31] Bernie Roesler
"
" Description: Vim integration with Jupyter [Qt]Console running ipython
"=============================================================================

" if exists("b:loaded_jupyter")
"     finish
" endif

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
" TODO lookup <Plug> usage vs just defining a command
"   - a little nicer to define commands so user does not necessarily need
"   a keymap
"   - cleaner to use <Plug> and not have so many commands created

command! -buffer -nargs=0    JupyterConnect         call jupyter#Connect()
command! -buffer -nargs=1    JupyterSendCode        call jupyter#SendCode(<args>)
command! -buffer -count      JupyterSendCount       call jupyter#SendCount(<count>)
command! -buffer -range -bar JupyterSendRange       <line1>,<line2>call jupyter#SendRange()

command! -buffer -nargs=0    JupyterUpdateShell     call jupyter#UpdateShell()
command! -buffer -nargs=0    JupyterKillKernel      call jupyter#KillKernel()
command! -buffer -nargs=0    JupyterTerminateKernel call jupyter#TerminateKernel()

command! -buffer -nargs=* -complete=file JupyterRunFile
            \ update | call jupyter#RunFile(<f-args>)
command! -buffer -nargs=0 -complete=file JupyterImportThisFile
            \ update | call jupyter#RunFile('-n', expand("%:p"))

"}}}--------------------------------------------------------------------------
"        Key Mappings: {{{
"-----------------------------------------------------------------------------
" Setup plugin mappings for the most common ways to interact with ipython.
noremap  <Plug>Jupyter-RunCell            :pythonx jupyter_vim.run_this_cell()<CR>

"noremap  <Plug>Jupyter-StartDebugging     :pythonx send('%pdb')<CR>
"noremap  <Plug>Jupyter-BreakpointSet      :pythonx set_breakpoint()<CR>
"noremap  <Plug>Jupyter-BreakpointClear    :pythonx clear_breakpoint()<CR>
"noremap  <Plug>Jupyter-DebugThisFile      :pythonx run_this_file_pdb()<CR>
"noremap  <Plug>Jupyter-BreakpointClearAll :pythonx clear_all_breaks()<CR>

" noremap  <Plug>Jupyter-PlotClearCurrent   :pythonx jupyter_vim.run_command("plt.clf()")<CR>
" noremap  <Plug>Jupyter-PlotCloseAll       :pythonx jupyter_vim.run_command("plt.close('all')")<CR>

if g:jupyter_mapkeys
    nnoremap <buffer> <silent> <localleader>R       :JupyterRunFile<CR>
    nnoremap <buffer> <silent> <localleader>I       :JupyterImportThisFile<CR>

    " Send just the current line
    nnoremap <buffer> <silent> <localleader>E           :JupyterSendRange<CR>
    nmap     <buffer> <silent> <localleader>e           <Plug>JupyterRunTextObj
    vmap     <buffer> <silent> <localleader>e           <Plug>JupyterRunVisual

    nnoremap <buffer> <silent> <localleader>U           :JupyterUpdateShell<CR>
    " nnoremap <buffer> <silent> <localleader><C-c>       :JupyterTerminateKernel<CR>

    " Debugging maps (not yet implemented)
    "map  <buffer> <silent> <C-F6>         <Plug>Jupyter-StartDebugging
    "map  <buffer> <silent> <F6>           <Plug>Jupyter-BreakpointSet
    "map  <buffer> <silent> <S-F6>         <Plug>Jupyter-BreakpointClear
    "map  <buffer> <silent> <F7>           <Plug>Jupyter-DebugThisFile
    "map  <buffer> <silent> <S-F7>         <Plug>Jupyter-BreakpointClearAll

endif
"}}}

let b:loaded_jupyter = 1
"=============================================================================
"=============================================================================
