"=============================================================================
"    File: ftplugin/python/jupyter_vim.vim
" Created: 07/28/11 22:14:58
"  Author: Paul Ivanov (http://pirsquared.org)
"  Updated: [11/13/2017] William Van Vliet
"  Updated: [02/14/2018, 12:31] Bernie Roesler
"
" Description: Vim integration with Jupyter Console
"
" A two-way integration between Vim and Jupyter Console and QtConsole.
"
" Using this plugin, you can send lines or whole files for IPython to execute,
" and also get back object introspection and word completions in Vim, like
" what you get with: object?<enter>, or object.<tab> in IPython
"
" This version of vim-ipython has been tested on the following:
" $ ipython --version           # 6.1.0
" $ jupyter --version           # 4.3.0
" $ jupyter console --version   # 5.2.0
" $ jupyter qtconsole --version # 4.3.1
" $ jupyter notebook --version  # 5.0.0
"
"=============================================================================

" if exists("b:loaded_jupyter") || !has('pythonx') || &cp || !has('channel')
if !has('pythonx') || !has('job') || &cp
    finish
endif

if !jupyter#init_python()
    finish
endif

"----------------------------------------------------------------------------- 
"        Configuration: {{{
"-----------------------------------------------------------------------------
" TODO set defaults via dictionary + loop like in jedi-vim
if !exists("g:jupyter_mapkeys")
    let g:jupyter_mapkeys = 1
endif

if !exists("g:jupyter_auto_connect")
    let g:jupyter_auto_connect = 1
endif

" flags for Jupyter's run file magic
if !exists('g:ipython_run_flags')
    let g:ipython_run_flags = ''
endif

if !exists('g:ipy_monitor_subchannel')
    let g:ipy_monitor_subchannel = 0
endif

"}}}-------------------------------------------------------------------------- 
"        Autocmds: {{{
"-----------------------------------------------------------------------------
augroup vim-ipython
    autocmd!
    au FileType python Jupyter
    " TODO mode this autocmd to an async process that only reports back
    " important things like tracebacks, and sends all else to the console 
    " au CursorHold *.*,vim-ipython :pythonx 
    "             \ if jupyter_vim.update_subchannel_msgs(): 
    "             \   jupyter_vim.vim_echo("vim-ipython shell updated (on idle)",'Operator')
augroup END

"}}}-------------------------------------------------------------------------- 
"        Commands: {{{
"-----------------------------------------------------------------------------
" TODO lookup <Plug> usage vs just defining a command
"   - a little nicer to define commands so user does not necessarily need
"   a keymap
"   - cleaner to use <Plug> and not have so many commands created
"
command! -buffer -nargs=0 JupyterConnect    call jupyter#Connect()
command! -buffer -nargs=* -complete=file JupyterRunFile 
            \ update | call jupyter#RunFile(<f-args>)
command! -buffer -nargs=0 -complete=file JupyterImportThisFile
            \ update | call jupyter#RunFile('-n', expand("%:p"))

" command! -buffer -nargs=* JupyterInterrupt         :pythonx jupyter_vim.interrupt_kernel_hack("<args>")
" command! -buffer -nargs=0 JupyterTerminate         :pythonx jupyter_vim.terminate_kernel_hack()

"}}}-------------------------------------------------------------------------- 
"        Key Mappings: {{{
"-----------------------------------------------------------------------------
" Setup plugin mappings for the most common ways to interact with ipython.
" noremap  <Plug>Jupyter-ImportFile         :update<CR>:pythonx jupyter_vim.run_this_file('-n')<CR>
noremap  <Plug>Jupyter-RunLine            :pythonx jupyter_vim.run_this_line()<CR>
noremap  <Plug>Jupyter-RunCell            :pythonx jupyter_vim.run_this_cell()<CR>
noremap  <Plug>Jupyter-RunLines           :pythonx jupyter_vim.run_these_lines()<CR>
xnoremap <Plug>Jupyter-RunLinesAsTopLevel :pythonx jupyter_vim.dedent_run_these_lines()<CR>
noremap  <Plug>Jupyter-UpdateShell        :pythonx if jupyter_vim.update_subchannel_msgs(force=True): jupyter_vim.vim_echo("vim-ipython shell updated",'Operator')<CR>
"noremap  <Plug>Jupyter-StartDebugging     :pythonx send('%pdb')<CR>
"noremap  <Plug>Jupyter-BreakpointSet      :pythonx set_breakpoint()<CR>
"noremap  <Plug>Jupyter-BreakpointClear    :pythonx clear_breakpoint()<CR>
"noremap  <Plug>Jupyter-DebugThisFile      :pythonx run_this_file_pdb()<CR>
"noremap  <Plug>Jupyter-BreakpointClearAll :pythonx clear_all_breaks()<CR>
noremap  <Plug>Jupyter-RunLineAsTopLevel  :pythonx jupyter_vim.dedent_run_this_line()<CR>

noremap  <Plug>Jupyter-PlotClearCurrent   :pythonx jupyter_vim.run_command("plt.clf()")<CR>
noremap  <Plug>Jupyter-PlotCloseAll       :pythonx jupyter_vim.run_command("plt.close('all')")<CR>

if g:jupyter_mapkeys
    nnoremap <buffer> <silent> <localleader>R       :JupyterRunFile<CR>
    nnoremap <buffer> <silent> <localleader>I       :JupyterImportThisFile<CR>

    nmap <buffer> <silent> <localleader>e            <Plug>JupyterRunTextObj
    vmap <buffer> <silent> <localleader>e            <Plug>JupyterRunVisual

    map  <buffer> <silent> <S-F5>         <Plug>Jupyter-RunLine
    map  <buffer> <silent> <F6>           <Plug>Jupyter-RunTextObj
    map  <buffer> <silent> <F9>           <Plug>Jupyter-RunLines
    map  <buffer> <silent> <M-r>          <Plug>Jupyter-UpdateShell

    " Debugging maps (not yet implemented)
    "map  <buffer> <silent> <C-F6>         <Plug>Jupyter-StartDebugging
    "map  <buffer> <silent> <F6>           <Plug>Jupyter-BreakpointSet
    "map  <buffer> <silent> <S-F6>         <Plug>Jupyter-BreakpointClear
    "map  <buffer> <silent> <F7>           <Plug>Jupyter-DebugThisFile
    "map  <buffer> <silent> <S-F7>         <Plug>Jupyter-BreakpointClearAll

    " nnoremap <buffer> <C-c> :<C-u>JupyterInterrupt<CR>
endif

"}}}---------------------------------------------------------------------------- 
" TODO move to vim-ipython/plugin/jupyter.vim
"       Connect to Jupyter Kernel  {{{
"-------------------------------------------------------------------------------
if g:jupyter_auto_connect
    " General idea: open a channel to the python kernel with vim, use a callback
    " function to determine what to do with the information
    " let s:script_path = fnameescape(expand('<sfile>:p:h:h:h'))
    " let g:logjob = job_start("python " . s:script_path . "/monitor.py", 
    "             \ {'out_io': 'buffer', 'out_name': 'dummy'})
endif
"}}}

let b:loaded_jupyter = 1
"=============================================================================
"=============================================================================
