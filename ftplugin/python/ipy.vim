"=============================================================================
"    File: ftplugin/python/ipy.vim
" Created: 07/28/11 22:14:58
"  Author: Paul Ivanov (http://pirsquared.org)
"  Updated: [11/13/2017] William Van Vliet
"  Updated: [02/14/2018, 12:31] Bernie Roesler
"
" Description: Vim integration with IPython 6.1.0+
"
" A two-way integration between Vim and IPython (now Jupyter Console, etc.).
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
"       Compatibility check {{{
"-----------------------------------------------------------------------------
" if exists("g:loaded_ipy") || !has('pythonx') || &cp || version < 800
if !has('pythonx') || &cp || version < 800
    finish
endif

"}}}-------------------------------------------------------------------------- 
"        Configuration: {{{
"-----------------------------------------------------------------------------
" Allow custom mappings.
if !exists('g:ipy_perform_mappings')
    let g:ipy_perform_mappings = 1
endif

" flags to for IPython's run file magic
if !exists('g:ipython_run_flags')
    let g:ipython_run_flags = ''
endif

" Automatically run :IPython in python files
if !exists('g:ipy_autostart')
    let g:ipy_autostart = 1
endif

" update vim-ipython 'shell' on every send?
if !exists('g:ipy_monitor_subchannel')
       let g:ipy_monitor_subchannel = 0
endif


"}}}-------------------------------------------------------------------------- 
"        Execute Python Code: {{{
"-----------------------------------------------------------------------------
pythonx << endpython
import vim
import sys
import itertools as it
vim_ipython_path = vim.eval("expand('<sfile>:h')")
sys.path.append(vim_ipython_path)
from vim_ipython import *
endpython

"}}}-------------------------------------------------------------------------- 
"        Autocmds: {{{
"-----------------------------------------------------------------------------
augroup vim-ipython
    autocmd!
    au FileType python IPython
    " TODO mode this autocmd to an async process that only reports back
    " important things like tracebacks, and sends all else to the console 
    " au CursorHold *.*,vim-ipython :pythonx if update_subchannel_msgs(): vim_echo("vim-ipython shell updated (on idle)",'Operator')
augroup END

"}}}-------------------------------------------------------------------------- 
"        Key Mappings: {{{
"-----------------------------------------------------------------------------
" Setup plugin mappings for the most common ways to interact with ipython.
noremap  <Plug>IPython-RunFile            :update<CR>:pythonx run_this_file()<CR>
noremap  <Plug>IPython-ImportFile         :update<CR>:pythonx run_this_file('-n')<CR>
noremap  <Plug>IPython-RunLine            :pythonx run_this_line()<CR>
noremap  <Plug>IPython-RunCell            :pythonx run_this_cell()<CR>
noremap  <Plug>IPython-RunLines           :pythonx run_these_lines()<CR>
xnoremap <Plug>IPython-RunLinesAsTopLevel :pythonx dedent_run_these_lines()<CR>
noremap  <Plug>IPython-OpenPyDoc          :pythonx get_doc_buffer()<CR>
noremap  <Plug>IPython-UpdateShell        :pythonx if update_subchannel_msgs(force=True): echo("vim-ipython shell updated",'Operator')<CR>
"noremap  <Plug>IPython-StartDebugging     :pythonx send('%pdb')<CR>
"noremap  <Plug>IPython-BreakpointSet      :pythonx set_breakpoint()<CR>
"noremap  <Plug>IPython-BreakpointClear    :pythonx clear_breakpoint()<CR>
"noremap  <Plug>IPython-DebugThisFile      :pythonx run_this_file_pdb()<CR>
"noremap  <Plug>IPython-BreakpointClearAll :pythonx clear_all_breaks()<CR>
noremap  <Plug>IPython-PlotClearCurrent   :pythonx run_command("plt.clf()")<CR>
noremap  <Plug>IPython-PlotCloseAll       :pythonx run_command("plt.close('all')")<CR>
noremap  <Plug>IPython-RunLineAsTopLevel  :pythonx dedent_run_this_line()<CR>
noremap  <Plug>IPython-RunTextObj         :<C-u>set opfunc=<SID>opfunc<CR>g@

function! s:DoMappings()
    if g:ipy_perform_mappings
       if &buftype == ''
        map  <buffer> <silent> <F5>           <Plug>IPython-RunFile
        map  <buffer> <silent> g<F5>          <Plug>IPython-ImportFile
       endif
        " map  <buffer> <silent> <S-F5>         <Plug>IPython-RunLine
        map  <buffer> <silent> <F6>           <Plug>IPython-RunTextObj
        map  <buffer> <silent> <F9>           <Plug>IPython-RunLines
        "map  <buffer> <silent> ,d             <Plug>IPython-OpenPyDoc
        map  <buffer> <silent> <M-r>          <Plug>IPython-UpdateShell
        map  <buffer> <silent> <S-F9>         <Plug>IPython-ToggleReselect
        "map  <buffer> <silent> <C-F6>         <Plug>IPython-StartDebugging
        "map  <buffer> <silent> <F6>           <Plug>IPython-BreakpointSet
        "map  <buffer> <silent> <S-F6>         <Plug>IPython-BreakpointClear
        "map  <buffer> <silent> <F7>           <Plug>IPython-DebugThisFile
        "map  <buffer> <silent> <S-F7>         <Plug>IPython-BreakpointClearAll
        imap <buffer>          <C-F5>         <C-o><Plug>IPython-RunFile
        imap <buffer>          <S-F5>         <C-o><Plug>IPython-RunLines
        " imap <buffer> <silent> <F5>           <C-o><Plug>IPython-RunFile

        "pi custom
        map  <buffer> <silent> <C-Return>        <Plug>IPython-RunFile
        map  <buffer> <silent> <M-S>             <Plug>IPython-RunLineAsTopLevel
        xmap <buffer> <silent> <M-S>             <Plug>IPython-RunLines
        map  <buffer> <silent> <Leader><Leader>x <Plug>IPython-RunCell

        " nnoremap <buffer> <C-c> :<C-u>IPythonInterrupt<CR>
        " inoremap <buffer> <Leader>K <Esc>:<C-u>call <SID>GetDocBuffer()<CR>
    endif

    augroup vim_ipython_autostart
        autocmd!
        autocmd BufEnter,BufNewFile *.py if g:ipy_autostart | call s:DoMappings() | endif
        autocmd FileType python if g:ipy_autostart | call s:DoMappings() | endif
    augroup END
endfunction

"}}}-------------------------------------------------------------------------- 
"        Commands: {{{
"-----------------------------------------------------------------------------
command! -nargs=0 IPython :call <SID>DoMappings()|:pythonx connect_to_kernel()
command! -nargs=* IPythonInterrupt :pythonx interrupt_kernel_hack("<args>")
command! -nargs=0 IPythonTerminate :pythonx terminate_kernel_hack()
command! -nargs=0 -bang IPythonInput :pythonx InputPrompt(force='<bang>')
command! -nargs=0 -bang IPythonInputSecret :pythonx InputPrompt(force='<bang>', hide_input=True)

"}}}-------------------------------------------------------------------------- 
"        Functions: {{{
"-----------------------------------------------------------------------------
function! s:GetDocBuffer()
    python get_doc_buffer()
    nnoremap <buffer> <silent> gi ZQ:undojoin<bar>startinsert!<CR>
    nnoremap <buffer> <silent> q ZQ:undojoin<bar>startinsert!<CR>
    nnoremap <buffer> <silent> ` <C-w>p:if winheight(0)<30<bar>res 30<bar>endif<bar>undojoin<bar>startinsert!<CR>
endfunction

function! s:opfunc(type)
  " Originally from tpope/vim-scriptease
  let sel_save = &selection
  let cb_save = &clipboard
  let reg_save = @@
  let left_save = getpos("'<")
  let right_save = getpos("'>")
  let vimode_save = visualmode()
  try
    set selection=inclusive clipboard-=unnamed clipboard-=unnamedplus
    if a:type =~ '^\d\+$'
      silent exe 'normal! ^v'.a:type.'$hy'
    elseif a:type =~# '^.$'
      silent exe "normal! `<" . a:type . "`>y"
    elseif a:type ==# 'line'
      silent exe "normal! '[V']y"
    elseif a:type ==# 'block'
      silent exe "normal! `[\<C-V>`]y"
    elseif a:type ==# 'visual'
      silent exe "normal! gvy"
    else
      silent exe "normal! `[v`]y"
    endif
    redraw
    let l:cmd = @@
  finally
    let @@ = reg_save
    let &selection = sel_save
    let &clipboard = cb_save
    exe "normal! " . vimode_save . "\<Esc>"
    call setpos("'<", left_save)
    call setpos("'>", right_save)
  endtry
pythonx << EOF
import textwrap
import vim
run_command(textwrap.dedent(vim.eval('l:cmd')))
EOF
endfunction
"}}}

let g:loaded_ipy = 1
"=============================================================================
"=============================================================================
