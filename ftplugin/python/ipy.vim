" Vim integration with IPython 0.11+
"
" A two-way integration between Vim and IPython.
"
" Using this plugin, you can send lines or whole files for IPython to execute,
" and also get back object introspection and word completions in Vim, like
" what you get with: object?<enter> object.<tab> in IPython
"
" -----------------
" Quickstart Guide:
" -----------------
" Start `ipython qtconsole`, `ipython console`, or  `ipython notebook` and
" open a notebook using you web browser.  Source this file, which provides new
" IPython command
"
"   :source ipy.vim
"   :IPython
"
" written by Paul Ivanov (http://pirsquared.org)
"
if !has('python')
    " exit if python is not available.
    " XXX: raise an error message here
    finish
endif

" Allow custom mappings.
if !exists('g:ipy_perform_mappings')
    let g:ipy_perform_mappings = 1
endif

if !exists('g:ipython_dictionary_completion')
    let g:ipython_dictionary_completion = 0
endif
if !exists('g:ipython_greedy_matching')
    let g:ipython_greedy_matching = 0
endif

" Use -i with %run magic by default
if !exists('g:ipython_run_flags')
    let g:ipython_run_flags = '-i'
endif

" Automatically run :IPython in python files after running :IPython the first
" time
if !exists('g:ipy_autostart')
    let g:ipy_autostart = 1
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

python << EOF
import vim
import sys
import re
vim_ipython_path = vim.eval("expand('<sfile>:h')")
sys.path.append(vim_ipython_path)
from vim_ipython import *
EOF

fun! <SID>toggle_send_on_save()
    if exists("s:ssos") && s:ssos == 0
        let s:ssos = 1
        au BufWritePost *.py :py run_this_file()
        echo "Autosend On"
    else
        let s:ssos = 0
        au! BufWritePost *.py
        echo "Autosend Off"
    endif
endfun

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
    au CursorHold *.*,vim-ipython :python if update_subchannel_msgs(): echo("vim-ipython shell updated (on idle)",'Operator')

    " XXX: broken - cursor hold update for insert mode moves the cursor one
    " character to the left of the last character (update_subchannel_msgs must be
    " doing this)
    "au CursorHoldI *.* :python if update_subchannel_msgs(): echo("vim-ipython shell updated (on idle)",'Operator')

    " Same as above, but on regaining window focus (mostly for GUIs)
    au FocusGained *.*,vim-ipython :python if update_subchannel_msgs(): echo("vim-ipython shell updated (on input focus)",'Operator')

    " Update vim-ipython buffer when we move the cursor there. A message is only
    " displayed if vim-ipython buffer has been updated.
    au BufEnter vim-ipython :python if update_subchannel_msgs(): echo("vim-ipython shell updated (on buffer enter)",'Operator')
augroup END

" Setup plugin mappings for the most common ways to interact with ipython.
noremap  <Plug>(IPython-RunFile)            :update<CR>:python run_this_file()<CR>
noremap  <Plug>(IPython-RunLine)            :python run_this_line()<CR>
noremap  <Plug>(IPython-RunLines)           :python run_these_lines()<CR>
noremap  <Plug>(IPython-OpenPyDoc)          :python get_doc_buffer()<CR>
noremap  <Plug>(IPython-UpdateShell)        :python if update_subchannel_msgs(force=True): echo("vim-ipython shell updated",'Operator')<CR>
noremap  <Plug>(IPython-ToggleReselect)     :python toggle_reselect()<CR>
"noremap  <Plug>(IPython-StartDebugging)     :python send('%pdb')<CR>
"noremap  <Plug>(IPython-BreakpointSet)      :python set_breakpoint()<CR>
"noremap  <Plug>(IPython-BreakpointClear)    :python clear_breakpoint()<CR>
"noremap  <Plug>(IPython-DebugThisFile)      :python run_this_file_pdb()<CR>
"noremap  <Plug>(IPython-BreakpointClearAll) :python clear_all_breaks()<CR>
noremap  <Plug>(IPython-ToggleSendOnSave)   :call <SID>toggle_send_on_save()<CR>
noremap  <Plug>(IPython-PlotClearCurrent)   :python run_command("plt.clf()")<CR>
noremap  <Plug>(IPython-PlotCloseAll)       :python run_command("plt.close('all')")<CR>
noremap  <Plug>(IPython-RunLineAsTopLevel)  :python dedent_run_this_line()<CR>
xnoremap <Plug>(IPython-RunLinesAsTopLevel) :python dedent_run_these_lines()<CR>

function! s:DoMappings()
    let b:did_ipython = 1
    if g:ipy_perform_mappings != 0
       if &buftype == ''
        map  <buffer> <silent> <F5>           <Plug>(IPython-RunFile)
       endif
        " map  <buffer> <silent> <S-F5>         <Plug>(IPython-RunLine)
        map  <buffer> <silent> <F9>           <Plug>(IPython-RunLines)
        map  <buffer> <silent> ,d             <Plug>(IPython-OpenPyDoc)
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
        imap <buffer> <silent> <Leader>x         <Esc><Plug>(IPython-RunLine)
        map  <buffer> <silent> <M-S>             <Plug>(IPython-RunLineAsTopLevel)
        xmap <buffer> <silent> <Leader>x         <Plug>(IPython-RunLinesAsTopLevel)
        xmap <buffer> <silent> <M-S>             <Plug>(IPython-RunLines)
        map  <buffer> <silent> <Leader><Leader>x <Plug>(IPython-RunCell)

        " noremap  <buffer> <silent> <M-c>      I#<ESC>
        " xnoremap <buffer> <silent> <M-c>      I#<ESC>
        " noremap  <buffer> <silent> <M-C>      :s/^\([ \t]*\)#/\1/<CR>
        " xnoremap <buffer> <silent> <M-C>      :s/^\([ \t]*\)#/\1/<CR>

        nnoremap <buffer> <C-c> :<C-u>IPythonInterrupt<CR>
        inoremap <buffer> <Leader>K <Esc>:<C-u>call <SID>GetDocBuffer()<CR>
    endif

    augroup vim_ipython_autostart
        autocmd!
        autocmd BufEnter,BufNewFile *.py,--Python-- if g:ipy_autostart && !exists('b:did_ipython')
            \ | call s:DoMappings() | endif
        autocmd FileType python if g:ipy_autostart && !exists('b:did_ipython')
            \ | call s:DoMappings() | endif
    augroup END

    setlocal omnifunc=CompleteIPython
endfunction

function! s:GetDocBuffer()
    python get_doc_buffer()
    nnoremap <buffer> <silent> gi ZQ:undojoin<bar>startinsert!<CR>
    nnoremap <buffer> <silent> q ZQ:undojoin<bar>startinsert!<CR>
    nnoremap <buffer> <silent> ` <C-w>p:if winheight(0)<30<bar>res 30<bar>endif<bar>undojoin<bar>startinsert!<CR>
endfunction

command! -nargs=* IPython :call <SID>DoMappings()|:py km_from_string("<args>")
command! -nargs=0 IPythonClipboard :py km_from_string(vim.eval('@+'))
command! -nargs=0 IPythonXSelection :py km_from_string(vim.eval('@*'))
command! -nargs=* IPythonNew :py new_ipy("<args>")
command! -nargs=* IPythonInterrupt :py interrupt_kernel_hack("<args>")
command! -nargs=0 IPythonTerminate :py terminate_kernel_hack()

function! IPythonBalloonExpr()
python << endpython
word = vim.eval('v:beval_text')
reply = get_doc(word)
vim.command("let l:doc = %s"% reply)
endpython
return l:doc
endfunction

if g:ipython_greedy_matching
    let s:split_pattern = "[^= \r\n().-@]"
else
    let s:split_pattern = '\k\|\.'
endif

fun! CompleteIPython(findstart, base)
      if a:findstart
        " locate the start of the word
        let line = getline('.')[:col('.')-1]
        let s:start = col('.') - 1
        if line[s:start-1] !~ s:split_pattern &&
            \ !(g:ipython_greedy_matching && s:start >= 2
            \   && line[s:start-2] =~ '\k') &&
            \ line[s:start-2:s:start-1] !=# '].'
            if line =~# '\v^\s*from\s+\w+\s+import\s+(\w+,\s+)*'
                python << endpython
current_line = vim.current.line
endpython
                return col('.') - 1
            else
                return -1
            endif
        endif
        while s:start > 0 && (line[s:start-1] =~ s:split_pattern
            \ || (g:ipython_greedy_matching && line[s:start-1] == '.'
            \     && s:start >= 2 && line[s:start-2] =~ '\k')
            \ || line[s:start-2:s:start-1] ==# '].')
          if g:ipython_greedy_matching && line[s:start-1] == '[' &&
              \ (s:start == 1 || line[s:start-2] !~ '\k\|\]')
              break
          endif
          let s:start -= 1
        endwhile
        python << endpython
current_line = vim.current.line
endpython
        return s:start
      else
        " find months matching with "a:base"
        let res = []
        python << endpython
base = vim.eval("a:base")
matches, metadata = ipy_complete(base, current_line, int(vim.eval('s:start')) + len(base))
# we need to be careful with unicode, because we can have unicode
# completions for filenames (for the %run magic, for example). So the next
# line will fail on those:
#completions= [str(u) for u in matches]
# because str() won't work for non-ascii characters
# and we also have problems with unicode in vim, hence the following:
completions = [s.encode(vim_encoding) for s in matches]
metadata = [s.encode(vim_encoding) for s in metadata]
if vim.vars['ipython_dictionary_completion'] and not vim.vars['ipython_greedy_matching']:
    for c in completions:
        if c.endswith("']"):
            completions = filter(lambda c: c.endswith("']"), completions)
            break
        elif c.endswith('"]'):
            completions = filter(lambda c: c.endswith('"]'), completions)
            break
## Additionally, we have no good way of communicating lists to vim, so we have
## to turn in into one long string, which can be problematic if e.g. the
## completions contain quotes. The next line will not work if some filenames
## contain quotes - but if that's the case, the user's just asking for
## it, right?
#completions = '["'+ '", "'.join(completions)+'"]'
#vim.command("let completions = %s" % completions)
## An alternative for the above, which will insert matches one at a time, so
## if there's a problem with turning a match into a string, it'll just not
## include the problematic match, instead of not including anything. There's a
## bit more indirection here, but I think it's worth it
try:
    completions, metadata = zip(*sorted(zip(completions, metadata), key=lambda x: x[0].lower()))
except ValueError:
    pass
for c, m in zip(completions, metadata):
    if 'CALLSIG' in m:
        split = m.partition('CALLSIG')
        vim.command('call add(res, {"word": pyeval("c"), "menu": pyeval("split[0]"), "info": pyeval("split[-1]")})')
    else:
        vim.command('call add(res, {"word": pyeval("c"), "menu": pyeval("m")})')
endpython
        "call extend(res,completions) 
        return res
      endif
    endfun
