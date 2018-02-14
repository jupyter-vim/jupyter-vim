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
if !has('pythonx') " test for python2 or python3
    " exit if python is not available.
    " XXX: raise an error message here
    finish
endif

" Allow custom mappings.
if !exists('g:ipy_perform_mappings')
    let g:ipy_perform_mappings = 0
endif

" Register IPython completefunc
" 'global'   -- for all of vim (default).
" 'local'    -- only for the current buffer.
" otherwise  -- don't register it at all.
"
" you can later set it using ':set completefunc=CompleteIPython', which will
" correspond to the 'global' behavior, or with ':setl ...' to get the 'local'
" behavior
if !exists('g:ipy_completefunc')
    let g:ipy_completefunc = 'local'
endif

pyx << EOF
import vim
import sys
vim_ipython_path = vim.eval("expand('<sfile>:p:h')")
sys.path.append(vim_ipython_path)
from vim_ipython import *

EOF

fun! <SID>toggle_send_on_save()
    if exists("s:ssos") && s:ssos == 0
        let s:ssos = 1
        au BufWritePost *.py :pyx run_this_file()
        echo "Autosend On"
    else
        let s:ssos = 0
        au! BufWritePost *.py
        echo "Autosend Off"
    endif
endfun

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
" au CursorHold *.*,vim-ipython :pyx if update_subchannel_msgs(): echo("vim-ipython shell updated (on idle)",'Operator')

" XXX: broken - cursor hold update for insert mode moves the cursor one
" character to the left of the last character (update_subchannel_msgs must be
" doing this)
"au CursorHoldI *.* :pyx if update_subchannel_msgs(): echo("vim-ipython shell updated (on idle)",'Operator')

" Same as above, but on regaining window focus (mostly for GUIs)
" au FocusGained *.*,vim-ipython :pyx if update_subchannel_msgs(): echo("vim-ipython shell updated (on input focus)",'Operator')

" Update vim-ipython buffer when we move the cursor there. A message is only
" displayed if vim-ipython buffer has been updated.
" au BufEnter vim-ipython :pyx if update_subchannel_msgs(): echo("vim-ipython shell updated (on buffer enter)",'Operator')

" Setup plugin mappings for the most common ways to interact with ipython.
noremap  <Plug>(IPython-RunFile)            :pyx run_this_file()<CR>
noremap  <Plug>(IPython-RunLine)            :pyx run_this_line()<CR>
noremap  <Plug>(IPython-RunLines)           :pyx run_these_lines()<CR>
noremap  <Plug>(IPython-OpenPyDoc)          :pyx get_doc_buffer()<CR>
noremap  <Plug>(IPython-UpdateShell)        :pyx if update_subchannel_msgs(force=True): echo("vim-ipython shell updated",'Operator')<CR>
noremap  <Plug>(IPython-ToggleReselect)     :pyx toggle_reselect()<CR>
"noremap  <Plug>(IPython-StartDebugging)     :pyx send('%pdb')<CR>
"noremap  <Plug>(IPython-BreakpointSet)      :pyx set_breakpoint()<CR>
"noremap  <Plug>(IPython-BreakpointClear)    :pyx clear_breakpoint()<CR>
"noremap  <Plug>(IPython-DebugThisFile)      :pyx run_this_file_pdb()<CR>
"noremap  <Plug>(IPython-BreakpointClearAll) :pyx clear_all_breaks()<CR>
noremap  <Plug>(IPython-ToggleSendOnSave)   :call <SID>toggle_send_on_save()<CR>
noremap  <Plug>(IPython-PlotClearCurrent)   :pyx run_command("plt.clf()")<CR>
noremap  <Plug>(IPython-PlotCloseAll)       :pyx run_command("plt.close('all')")<CR>
noremap  <Plug>(IPython-RunLineAsTopLevel)  :pyx dedent_run_this_line()<CR>
xnoremap <Plug>(IPython-RunLinesAsTopLevel) :pyx dedent_run_these_lines()<CR>

if g:ipy_perform_mappings != 0
    map  <buffer> <silent> <F5>           <Plug>(IPython-RunFile)
    map  <buffer> <silent> <S-F5>         <Plug>(IPython-RunLine)
    map  <buffer> <silent> <F9>           <Plug>(IPython-RunLines)
    map  <buffer> <silent> <LocalLeader>d <Plug>(IPython-OpenPyDoc)
    map  <buffer> <silent> <LocalLeader>s <Plug>(IPython-UpdateShell)
    map  <buffer> <silent> <S-F9>         <Plug>(IPython-ToggleReselect)
    "map  <buffer> <silent> <C-F6>         <Plug>(IPython-StartDebugging)
    "map  <buffer> <silent> <F6>           <Plug>(IPython-BreakpointSet)
    "map  <buffer> <silent> <S-F6>         <Plug>(IPython-BreakpointClear)
    "map  <buffer> <silent> <F7>           <Plug>(IPython-DebugThisFile)
    "map  <buffer> <silent> <S-F7>         <Plug>(IPython-BreakpointClearAll)
    imap <buffer>          <C-F5>         <C-o><Plug>(IPython-RunFile)
    imap <buffer>          <S-F5>         <C-o><Plug>(IPython-RunLines)
    imap <buffer> <silent> <F5>           <C-o><Plug>(IPython-RunFile)
    map  <buffer>          <C-F5>         <Plug>(IPython-ToggleSendOnSave)
    "" Example of how to quickly clear the current plot with a keystroke
    "map  <buffer> <silent> <F12>          <Plug>(IPython-PlotClearCurrent)
    "" Example of how to quickly close all figures with a keystroke
    "map  <buffer> <silent> <F11>          <Plug>(IPython-PlotCloseAll)

    "pi custom
    map  <buffer> <silent> <C-Return>     <Plug>(IPython-RunFile)
    map  <buffer> <silent> <C-s>          <Plug>(IPython-RunLine)
    imap <buffer> <silent> <C-s>          <C-o><Plug>(IPython-RunLine)
    map  <buffer> <silent> <M-s>          <Plug>(IPython-RunLineAsTopLevel)
    xmap <buffer> <silent> <C-S>          <Plug>(IPython-RunLines)
    xmap <buffer> <silent> <M-s>          <Plug>(IPython-RunLinesAsTopLevel)

    noremap  <buffer> <silent> <M-c>      I#<ESC>
    xnoremap <buffer> <silent> <M-c>      I#<ESC>
    noremap  <buffer> <silent> <M-C>      :s/^\([ \t]*\)#/\1/<CR>
    xnoremap <buffer> <silent> <M-C>      :s/^\([ \t]*\)#/\1/<CR>
endif

command! -nargs=* IPython :pyx km_from_string("<args>")
command! -nargs=0 IPythonClipboard :pyx km_from_string(vim.eval('@+'))
command! -nargs=0 IPythonXSelection :pyx km_from_string(vim.eval('@*'))
command! -nargs=* IPythonNew :pyx new_ipy("<args>")
command! -nargs=* IPythonInterrupt :pyx interrupt_kernel_hack("<args>")
command! -nargs=0 IPythonTerminate :pyx terminate_kernel_hack()

function! IPythonBalloonExpr()
pyx << endpython
word = vim.eval('v:beval_text')
reply = get_doc(word)
vim.command("let l:doc = %s"% reply)
endpython
return l:doc
endfunction

fun! CompleteIPython(findstart, base)
      if a:findstart
        " locate the start of the word
        let line = getline('.')
        let start = col('.') - 1
        while start > 0 && line[start-1] =~ '\k\|\.' "keyword
          let start -= 1
        endwhile
        echo start
        pyx << endpython
current_line = vim.current.line
endpython
        return start
      else
        " find months matching with "a:base"
        let res = []
        pyx << endpython
base = vim.eval("a:base")
findstart = vim.eval("a:findstart")
matches = ipy_complete(base, current_line, vim.eval("col('.')"))
# we need to be careful with unicode, because we can have unicode
# completions for filenames (for the %run magic, for example). So the next
# line will fail on those:
#completions= [str(u) for u in matches]
# because str() won't work for non-ascii characters
# and we also have problems with unicode in vim, hence the following:
completions = [s.encode(vim_encoding) for s in matches]
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
for c in completions:
    vim.command('call add(res,"'+c+'")')
endpython
        "call extend(res,completions) 
        return res
      endif
    endfun
