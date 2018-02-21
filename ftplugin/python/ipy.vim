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
if has('python3') && get(g:, 'pymode_python', '') !=# 'python'
  pythonx PY3 = True
else
  pythonx PY3 = False
endif

" Allow custom mappings.
if !exists('g:ipy_perform_mappings')
    let g:ipy_perform_mappings = 1
endif

" Enable cell folding
if !exists('g:ipy_cell_folding')
    let g:ipy_cell_folding = 0
endif

if !exists('g:ipython_dictionary_completion')
    let g:ipython_dictionary_completion = 0
endif

if !exists('g:ipython_greedy_matching')
    let g:ipython_greedy_matching = 0
endif

if !exists('g:ipython_run_flags')
    let g:ipython_run_flags = ''
endif

" Automatically run :IPython in python files
if !exists('g:ipy_autostart')
    let g:ipy_autostart = 1
endif

if !exists('g:ipython_history_len')
  let g:ipython_history_len = 100
endif

if !exists('g:ipython_history_raw')
  let g:ipython_history_raw = 1
endif

if !exists('g:ipython_history_unique')
  let g:ipython_history_unique = 1
endif

if !exists('g:ipython_history_timeout')
  let g:ipython_history_timeout = 2
endif

" Register IPython completefunc
" 'global'   -- for all of vim (default).
" 'local'    -- only for the current buffer.
" 'omni'     -- set omnifunc for current buffer.
" otherwise  -- don't register it at all.
"
" you can later set it using ':set completefunc=CompleteIPython', which will
" correspond to the 'global' behavior, or with ':setl ...' to get the 'local'
" behavior
if !exists('g:ipy_completefunc')
    let g:ipy_completefunc = 'omni'
endif

" reselect lines after sending from Visual mode
if !exists('g:ipy_reselect')
       let g:ipy_reselect = 0
endif

" wait to get numbers for In[43]: feedback?
if !exists('g:ipy_show_execution_count')
       let g:ipy_show_execution_count = 1
endif

" update vim-ipython 'shell' on every send?
if !exists('g:ipy_monitor_subchannel')
       let g:ipy_monitor_subchannel = 0
endif

" flags to for IPython's run magic when using <F5>
if !exists('g:ipy_run_flags')
       let g:ipy_run_flags = ''
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
    " Update the vim-ipython shell when the cursor is not moving.
    " You can change how quickly this happens after you stop moving the cursor by
    " setting 'updatetime' (in milliseconds). For example, to have this event
    " trigger after 1 second:
    "
    "       :set updatetime 1000
    "
    " NOTE: This will only be triggered once, after the first 'updatetime'
    " milliseconds, *not* every 'updatetime' milliseconds. see :help CursorHold
    " for more info.
    "
    " TODO: Make this easily configurable on the fly, so that an introspection
    " buffer we may have opened up doesn't get closed just because of an idle
    " event (i.e. user pressed \d and then left the buffer that popped up, but
    " expects it to stay there).
    au CursorHold *.*,vim-ipython :pythonx if update_subchannel_msgs(): vim_echo("vim-ipython shell updated (on idle)",'Operator')

    " Update vim-ipython buffer when we move the cursor there. A message is only
    " displayed if vim-ipython buffer has been updated.
    au BufEnter vim-ipython :pythonx if update_subchannel_msgs(): vim_echo("vim-ipython shell updated (on buffer enter)",'Operator')
augroup END

"}}}-------------------------------------------------------------------------- 
"        Key Mappings: {{{
"-----------------------------------------------------------------------------
" Setup plugin mappings for the most common ways to interact with ipython.
noremap  <Plug>(IPython-RunFile)            :update<CR>:pythonx run_this_file()<CR>
noremap  <Plug>(IPython-ImportFile)         :update<CR>:pythonx run_this_file('-n')<CR>
noremap  <Plug>(IPython-RunLine)            :pythonx run_this_line()<CR>
noremap  <Plug>(IPython-RunCell)            :pythonx run_this_cell()<CR>
noremap  <Plug>(IPython-RunLines)           :pythonx run_these_lines()<CR>
xnoremap <Plug>(IPython-RunLinesAsTopLevel) :pythonx dedent_run_these_lines()<CR>
noremap  <Plug>(IPython-OpenPyDoc)          :pythonx get_doc_buffer()<CR>
noremap  <Plug>(IPython-UpdateShell)        :pythonx if update_subchannel_msgs(force=True): echo("vim-ipython shell updated",'Operator')<CR>
noremap  <Plug>(IPython-ToggleReselect)     :pythonx toggle_reselect()<CR>
"noremap  <Plug>(IPython-StartDebugging)     :pythonx send('%pdb')<CR>
"noremap  <Plug>(IPython-BreakpointSet)      :pythonx set_breakpoint()<CR>
"noremap  <Plug>(IPython-BreakpointClear)    :pythonx clear_breakpoint()<CR>
"noremap  <Plug>(IPython-DebugThisFile)      :pythonx run_this_file_pdb()<CR>
"noremap  <Plug>(IPython-BreakpointClearAll) :pythonx clear_all_breaks()<CR>
noremap  <Plug>(IPython-PlotClearCurrent)   :pythonx run_command("plt.clf()")<CR>
noremap  <Plug>(IPython-PlotCloseAll)       :pythonx run_command("plt.close('all')")<CR>
noremap  <Plug>(IPython-RunLineAsTopLevel)  :pythonx dedent_run_this_line()<CR>
noremap  <Plug>(IPython-RunTextObj)         :<C-u>set opfunc=<SID>opfunc<CR>g@
noremap  <Plug>(IPython-RunParagraph)       :<C-u>set opfunc=<SID>opfunc<CR>g@ap

function! s:DoMappings()
    " let b:did_ipython = 1
    if g:ipy_perform_mappings
       if &buftype == ''
        map  <buffer> <silent> <F5>           <Plug>(IPython-RunFile)
        map  <buffer> <silent> g<F5>          <Plug>(IPython-ImportFile)
       endif
        " map  <buffer> <silent> <S-F5>         <Plug>(IPython-RunLine)
        map  <buffer> <silent> <F6>           <Plug>(IPython-RunTextObj)
        map  <buffer> <silent> <F9>           <Plug>(IPython-RunLines)
        "map  <buffer> <silent> ,d             <Plug>(IPython-OpenPyDoc)
        map  <buffer> <silent> <M-r>          <Plug>(IPython-UpdateShell)
        map  <buffer> <silent> <S-F9>         <Plug>(IPython-ToggleReselect)
        "map  <buffer> <silent> <C-F6>         <Plug>(IPython-StartDebugging)
        "map  <buffer> <silent> <F6>           <Plug>(IPython-BreakpointSet)
        "map  <buffer> <silent> <S-F6>         <Plug>(IPython-BreakpointClear)
        "map  <buffer> <silent> <F7>           <Plug>(IPython-DebugThisFile)
        "map  <buffer> <silent> <S-F7>         <Plug>(IPython-BreakpointClearAll)
        imap <buffer>          <C-F5>         <C-o><Plug>(IPython-RunFile)
        imap <buffer>          <S-F5>         <C-o><Plug>(IPython-RunLines)
        " imap <buffer> <silent> <F5>           <C-o><Plug>(IPython-RunFile)
        map  <buffer>          <C-F5>         <Plug>(IPython-ToggleSendOnSave)
        "" Example of how to quickly clear the current plot with a keystroke
        "map  <buffer> <silent> <F12>          <Plug>(IPython-PlotClearCurrent)
        "" Example of how to quickly close all figures with a keystroke
        "map  <buffer> <silent> <F11>          <Plug>(IPython-PlotCloseAll)

        "pi custom
        map  <buffer> <silent> <C-Return>        <Plug>(IPython-RunFile)
        " map  <buffer> <silent> <Leader>x         <Plug>(IPython-RunLine)
        " imap <buffer> <silent> <Leader>x         <Esc><Plug>(IPython-RunLine)
        map  <buffer> <silent> <M-S>             <Plug>(IPython-RunLineAsTopLevel)
        "xmap <buffer> <silent> <Leader>x         <Plug>(IPython-RunLinesAsTopLevel)
        xmap <buffer> <silent> <M-S>             <Plug>(IPython-RunLines)
        map  <buffer> <silent> <Leader><Leader>x <Plug>(IPython-RunCell)

        nnoremap <buffer> <C-c> :<C-u>IPythonInterrupt<CR>
        inoremap <buffer> <Leader>K <Esc>:<C-u>call <SID>GetDocBuffer()<CR>
    endif

    augroup vim_ipython_autostart
        autocmd!
        "&& !exists('b:did_ipython')
        autocmd BufEnter,BufNewFile *.py,--Python-- if g:ipy_autostart | call s:DoMappings() | endif
        autocmd FileType python if g:ipy_autostart | call s:DoMappings() | endif
    augroup END

    setlocal omnifunc=CompleteIPython
endfunction

"}}}-------------------------------------------------------------------------- 
"        Commands: {{{
"-----------------------------------------------------------------------------
command! -nargs=* IPython :call <SID>DoMappings()|:pythonx km_from_string("<args>")
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

function! IPythonBalloonExpr()
pythonx << endpython
word = vim.eval('v:beval_text')
reply = get_doc(word)
vim.command("let l:doc = %s"% reply)
endpython
return l:doc
endfunction

if g:ipython_greedy_matching
    let s:split_pattern = "[^= \r\n*().@-]"
else
    let s:split_pattern = '\k\|\.'
endif

pythonx << endpython
def process_matches(matches, metadata, result):
    if PY3:
        completions = matches
    else:
        completions = [s.encode(vim_encoding) for s in matches]
    if vim.vars['ipython_dictionary_completion'] and not vim.vars['ipython_greedy_matching']:
        for char in '\'"':
            if any(c.endswith(char + ']') for c in completions):
                completions = [c for c in completions if c.endswith(char + ']')]
                break
    try:
        completions, metadata = zip(*sorted(zip(completions, metadata),
                                            key=lambda x: x[0].lstrip('%').lower()))
    except ValueError:
        pass
    for c, m in zip(completions, metadata):
        result.clear()
        result['word'] = c
        # vim can't handle null bytes in Python strings
        for k, v in m.items():
          result[k] = v.replace('\0', '^@')
        vim.command('call add(res, {%s})' % ','.join(
            '"{k}": pyxeval("r[\'{k}\']")'.format(k=k)
            for k in result))
endpython

fun! CompleteIPython(findstart, base)
    if a:findstart
        " return immediately for imports
        if getline('.')[:col('.')-1] =~#
            \ '\v^\s*(from\s+\w+(\.\w+)*\s+import\s+(\w+,\s+)*|import\s+)'
            let line = getline('.')
            let s:start = col('.') - 1
            while s:start && line[s:start - 1] =~ '[._[:alnum:]]'
                let s:start -= 1
            endwhile
            pythonx current_line = vim.current.line
            return s:start
        endif
        " locate the start of the word
        let line = split(getline('.')[:col('.')-1], '\zs')
        let s:start = col('.') - 1
        if s:start == 0 || (len(line) == s:start &&
            \ line[s:start-2] !~ s:split_pattern &&
            \ !(g:ipython_greedy_matching && s:start >= 2
            \   && line[s:start-3] =~ '\k') &&
            \ join(line[s:start-3:s:start-2], '') !=# '].')
            let s:start = -1
            return s:start
        endif
        let s:start = strchars(getline('.')[:col('.')-1]) - 1
        let bracket_level = 0
        while s:start > 0 && (line[s:start-1] =~ s:split_pattern
            \ || (g:ipython_greedy_matching && line[s:start-1] == '.'
            \     && s:start >= 2 && line[s:start-2] =~ '\k')
            \ || (g:ipython_greedy_matching && line[s:start-1] == '-'
            \     && s:start >= 2 && line[s:start-2] == '[')
            \ || join(line[s:start-2:s:start-1], '') ==# '].')
            if g:ipython_greedy_matching && line[s:start-1] == '['
                if (s:start == 1 || line[s:start-2] !~ '\k\|\]')
                    \ || bracket_level > 0
                    break
                endif
                let bracket_level += 1
            elseif g:ipython_greedy_matching && line[s:start-1] == ']'
                let bracket_level -= 1
            endif
            let s:start -= 1
        endwhile
        pythonx current_line = vim.current.line
        return s:start + len(join(line[: s:start], '')) -
            \ len(getline('.')[: s:start])
    else
        " find months matching with "a:base"
        let res = []
        if s:start == -1 | return [] | endif
        " don't complete numeric literals
        if a:base =~? '\v^[-+]?\d*\.?\d+(e[-+]?\d+)?\.$' | return [] | endif
        " don't complete incomplete string literals
        if a:base =~? '\v^(([^''].*)?['']|([^"].*)?["])\.$' | return [] | endif
        let start = s:start
        pythonx << endpython
base = vim.eval("a:base")
try:
    matches, metadata = ipy_complete(base, current_line, int(vim.eval('start')) + len(base))
except IOError:
    if vim.eval('exists("*jedi#completions")') == '1':
        vim.command('setlocal omnifunc=jedi#completions')
    else:
        vim.command('setlocal omnifunc=')
    vim.command('return []')
r = dict()  # result object to let vim access namespace while in a function
process_matches(matches, metadata, r)
endpython
        return res
    endif
endfun

" Custom folding function to fold cells
function! FoldByCell(lnum)
    let pattern = '\v^\s*(##|' . escape('# <codecell>', '<>') . '|# %%).*$'
    if getline(a:lnum) =~? pattern
        return '>1'
    elseif getline(a:lnum+1) =~? pattern
        return '<1'
    else
        return '='
    endif
endfunction

function! EnableFoldByCell()
	setlocal foldmethod=expr
	setlocal foldexpr=FoldByCell(v:lnum)
endfunction

if g:ipy_cell_folding != 0
    call EnableFoldByCell()
endif

function! IPythonCmdComplete(arglead, cmdline, cursorpos, ...)
  let res = []
pythonx << endpython
arglead = vim.eval('a:arglead')
if ' ' in arglead and not (arglead.strip().startswith('from ') or
                           arglead.strip().startswith('import ')):
    start = arglead.split()[-1]
else:
    start = arglead

try:
    matches, metadata = ipy_complete(start,
                                     vim.eval('a:cmdline'),
                                     int(vim.eval('a:cursorpos')))
except IOError:
    vim.command('return []')

if ' ' in arglead:
    arglead = arglead.rpartition(' ')[0]
    matches = ['%s %s' % (arglead, m) for m in matches]
if int(vim.eval('a:0')):
    r = dict()
    process_matches(matches, metadata, r)
endpython
  if a:0
    return res
  else
    return pyxeval('matches')
  endif
endfunction

function! GreedyCompleteIPython(findstart, base)
  if a:findstart
    let line = getline('.')
    let start = col('.') - 1
    while start && line[start - 1] =~ '\S'
      let start -= 1
    endwhile
    return start
  else
    return IPythonCmdComplete(a:base, a:base, len(a:base), 1)
  endif
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
