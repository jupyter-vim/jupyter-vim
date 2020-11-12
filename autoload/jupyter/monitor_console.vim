" NOTE: Generally unused except for communication debugging
function! jupyter#monitor_console#OpenJupyterTerm() abort
    " Set up console display window
    " If we're in the console display already, just go to the bottom.
    " Otherwise, create a new buffer in a split (or jump to it if open)
    " If exists already: leave
    let buf_nr = bufnr('__jupyter_term__')
    if -1 != buf_nr
        return buf_nr
    endif

    " Clear out any autocmds that trigger on Insert for the console buffer
    " vint: next-line -ProhibitAutocmdWithNoGroup
    autocmd! InsertEnter,InsertLeave __jupyter_term__

    " Save current window
    let win_id = win_getid()
    let win_syntax = &syntax

    " Create a buffer
    " TODO user provided command instead of bool if not string, not console
    let save_swbuf=&switchbuf
    set switchbuf=useopen
    let l:cmd = bufnr('__jupyter_term__') > 0 ? 'sbuffer' : 'new'
    execute l:cmd . ' ' . '__jupyter_term__'
    let &switchbuf=save_swbuf

    " Make sure buffer is a scratch buffer before we write to it
    setlocal bufhidden=hide buftype=nofile
    setlocal nobuflisted nonumber noswapfile
    execute 'setlocal syntax=' . win_syntax

    " Syntax highlighting for prompt
    syn match JupyterPromptIn /^\(\w\w \[[ 0-9]*\]:\)\|\(\s*\.\{3}:\)/
    syn match JupyterPromptOut /^Out\[[ 0-9]*\]:/
    syn match JupyterPromptOut2 /^\.\.\.* /
    syn match JupyterPromptStdOut /^St\?dOu\?t\? \?\[[ 0-9]*\]:/
    syn match JupyterPromptStdOut2 /^ *\.\.\.< /
    syn match JupyterPromptStdErr /^St\?dEr\?r\? \?\[[ 0-9]*\]:/
    syn match JupyterPromptStdErr2 /^ *\.\.\.x /
    syn match JupyterMagic /^\]: \zs%\w\+/

    hi JupyterPromptIn          ctermfg=Green
    hi JupyterPromptOut         ctermfg=Red
    hi JupyterPromptOut2        ctermfg=Grey
    hi JupyterPromptStdOut      ctermfg=Blue
    hi JupyterPromptStdOut2     ctermfg=Cyan
    hi JupyterPromptStdErr      ctermfg=Red
    hi JupyterPromptStdErr2     ctermfg=DarkRed
    hi JupyterMagic             ctermfg=Magenta

    " Restore cursor at current window
    call win_gotoid(win_id)

    return bufnr('__jupyter_term__')
endfunction


" Timer callback to fill jupyter console buffer
function! jupyter#monitor_console#UpdateConsoleBuffer(timer) abort
    Pythonx _jupyter_session.monitor.timer_write_console_msgs()
endfunction
