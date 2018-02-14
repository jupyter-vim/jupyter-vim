"=============================================================================
"    File: ftplugin/python/ipy.vim
" Created: 07/28/11 22:14:58
"  Author: Paul Ivanov (http://pirsquared.org)
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

"=============================================================================

" TODO move to docs
"----------------------------------------------------------------------------- 
"        Quickstart Guide: {{{
"-----------------------------------------------------------------------------
" Start `jupyter qtconsole`, `jupyter console`, or `jupyter notebook` and open
" a notebook using a separate terminal window, tmux pane, or your web browser.
" Source this file, which provides the IPython command:
"
"   :source ipy.vim
"   :IPython
"
"}}}

" if exists("g:loaded_ipy") || !has('pythonx') || &cp || version < 800
if !has('pythonx') || &cp || version < 800
    finish
endif

"----------------------------------------------------------------------------- 
"        Configuration {{{
"-----------------------------------------------------------------------------
" Allow custom mappings
if !exists('g:ipy_mapkeys')
    let g:ipy_mapkeys = 0
endif

" Register IPython completefunc
" 'global'   -- for all of vim.
" 'local'    -- only for the current buffer (default).
" otherwise  -- don't register it at all.
"
" you can later set it using ':set completefunc=CompleteIPython', which will
" correspond to the 'global' behavior, or with ':setl ...' to get the 'local'
" behavior
"
if !exists('g:ipy_completefunc')
    let g:ipy_completefunc = 'local'
endif

" Import python functions
pythonx << EOF
import vim
import sys
vim_ipython_path = vim.eval("expand('<sfile>:p:h')")
sys.path.append(vim_ipython_path)
from vim_ipython import *
EOF

fun! <SID>toggle_send_on_save()
    if exists("s:ssos") && s:ssos == 0
        let s:ssos = 1
        au BufWritePost *.py :pythonx run_this_file()
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
" au CursorHold *.*,vim-ipython :pythonx if update_subchannel_msgs(): echo("vim-ipython shell updated (on idle)",'Operator')

" XXX: broken - cursor hold update for insert mode moves the cursor one
" character to the left of the last character (update_subchannel_msgs must be
" doing this)
"au CursorHoldI *.* :pythonx if update_subchannel_msgs(): echo("vim-ipython shell updated (on idle)",'Operator')

" Same as above, but on regaining window focus (mostly for GUIs)
" au FocusGained *.*,vim-ipython :pythonx if update_subchannel_msgs(): echo("vim-ipython shell updated (on input focus)",'Operator')

" Update vim-ipython buffer when we move the cursor there. A message is only
" displayed if vim-ipython buffer has been updated.
" au BufEnter vim-ipython :pythonx if update_subchannel_msgs(): echo("vim-ipython shell updated (on buffer enter)",'Operator')

" Setup plugin mappings for the most common ways to interact with ipython.
noremap  <Plug>IPython-RunFile            :pythonx run_this_file()<CR>
noremap  <Plug>IPython-RunLine            :pythonx run_this_line()<CR>
noremap  <Plug>IPython-RunLines           :pythonx run_these_lines()<CR>
noremap  <Plug>IPython-OpenPyDoc          :pythonx get_doc_buffer()<CR>
noremap  <Plug>IPython-UpdateShell        :pythonx if update_subchannel_msgs(force=True): echo("vim-ipython shell updated",'Operator')<CR>
noremap  <Plug>IPython-ToggleReselect     :pythonx toggle_reselect()<CR>
"noremap  <Plug>IPython-StartDebugging     :pythonx send('%pdb')<CR>
"noremap  <Plug>IPython-BreakpointSet      :pythonx set_breakpoint()<CR>
"noremap  <Plug>IPython-BreakpointClear    :pythonx clear_breakpoint()<CR>
"noremap  <Plug>IPython-DebugThisFile      :pythonx run_this_file_pdb()<CR>
"noremap  <Plug>IPython-BreakpointClearAll :pythonx clear_all_breaks()<CR>
noremap  <Plug>IPython-ToggleSendOnSave   :call <SID>toggle_send_on_save()<CR>
noremap  <Plug>IPython-PlotClearCurrent   :pythonx run_command("plt.clf()")<CR>
noremap  <Plug>IPython-PlotCloseAll       :pythonx run_command("plt.close('all')")<CR>
noremap  <Plug>IPython-RunLineAsTopLevel  :pythonx dedent_run_this_line()<CR>
xnoremap <Plug>IPython-RunLinesAsTopLevel :pythonx dedent_run_these_lines()<CR>

if g:ipy_mapkeys
    map  <buffer> <silent> <F5>           <Plug>IPython-RunFile
    map  <buffer> <silent> <S-F5>         <Plug>IPython-RunLine
    map  <buffer> <silent> <F9>           <Plug>IPython-RunLines
    map  <buffer> <silent> <LocalLeader>d <Plug>IPython-OpenPyDoc
    map  <buffer> <silent> <LocalLeader>s <Plug>IPython-UpdateShell
    map  <buffer> <silent> <S-F9>         <Plug>IPython-ToggleReselect
    "map  <buffer> <silent> <C-F6>         <Plug>IPython-StartDebugging
    "map  <buffer> <silent> <F6>           <Plug>IPython-BreakpointSet
    "map  <buffer> <silent> <S-F6>         <Plug>IPython-BreakpointClear
    "map  <buffer> <silent> <F7>           <Plug>IPython-DebugThisFile
    "map  <buffer> <silent> <S-F7>         <Plug>IPython-BreakpointClearAll
    imap <buffer>          <C-F5>         <C-o><Plug>IPython-RunFile
    imap <buffer>          <S-F5>         <C-o><Plug>IPython-RunLines
    imap <buffer> <silent> <F5>           <C-o><Plug>IPython-RunFile
    map  <buffer>          <C-F5>         <Plug>IPython-ToggleSendOnSave
    "" Example of how to quickly clear the current plot with a keystroke
    "map  <buffer> <silent> <F12>          <Plug>IPython-PlotClearCurrent
    "" Example of how to quickly close all figures with a keystroke
    "map  <buffer> <silent> <F11>          <Plug>IPython-PlotCloseAll

    "pi custom
    map  <buffer> <silent> <C-Return>     <Plug>IPython-RunFile
    map  <buffer> <silent> <C-s>          <Plug>IPython-RunLine
    imap <buffer> <silent> <C-s>          <C-o><Plug>IPython-RunLine
    map  <buffer> <silent> <M-s>          <Plug>IPython-RunLineAsTopLevel
    xmap <buffer> <silent> <C-S>          <Plug>IPython-RunLines
    xmap <buffer> <silent> <M-s>          <Plug>IPython-RunLinesAsTopLevel

    noremap  <buffer> <silent> <M-c>      I#<ESC>
    xnoremap <buffer> <silent> <M-c>      I#<ESC>
    noremap  <buffer> <silent> <M-C>      :s/^\([ \t]*\)#/\1/<CR>
    xnoremap <buffer> <silent> <M-C>      :s/^\([ \t]*\)#/\1/<CR>
endif

command! -nargs=* IPython :pythonx km_from_string("<args>")
command! -nargs=0 IPythonClipboard :pythonx km_from_string(vim.eval('@+'))
command! -nargs=0 IPythonXSelection :pythonx km_from_string(vim.eval('@*'))
command! -nargs=* IPythonNew :pythonx new_ipy("<args>")
command! -nargs=* IPythonInterrupt :pythonx interrupt_kernel_hack("<args>")
command! -nargs=0 IPythonTerminate :pythonx terminate_kernel_hack()

function! IPythonBalloonExpr()
pythonx << endpython
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
        pythonx << endpython
current_line = vim.current.line
endpython
        return start
      else
        " find months matching with "a:base"
        let res = []
        pythonx << endpython
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

let g:loaded_ipy = 1
"=============================================================================
"=============================================================================
