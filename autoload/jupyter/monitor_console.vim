" NOTE: Generally unused except for communication debugging
function! jupyter#monitor_console#OpenJupyterMonitor() abort
    " Set up console display window
    " If we're in the console display already, just go to the bottom.
    " Otherwise, create a new buffer in a split (or jump to it if open)

    " Clear out any autocmds that trigger on Insert for the console buffer
    " vint: next-line -ProhibitAutocmdWithNoGroup
    autocmd! InsertEnter,InsertLeave __jupyter_monitor__
    " Can't wipeout the buffer while we are still inside the buffer
    autocmd BufWinLeave __jupyter_monitor__ python3 _jupyter_session.stop_monitor(wipeout_buffer=False)

    " Save current window
    let win_id = win_getid()
    let win_syntax = &syntax

    " TODO user provided command instead of bool if not string, not console
    let save_swbuf=&switchbuf
    set switchbuf=useopen
    let l:cmd = bufnr('__jupyter_monitor__') > 0 ? 'sbuffer' : 'new'
    execute l:cmd . ' ' . '__jupyter_monitor__'
    let &switchbuf=save_swbuf

    " Make sure buffer is a scratch buffer before we write to it
    setlocal bufhidden=hide buftype=nofile
    setlocal nobuflisted nonumber noswapfile
    execute 'setlocal syntax=' . win_syntax

    " Restore cursor at current window
    call win_gotoid(win_id)

    return bufnr('__jupyter_monitor__')
endfunction

" Timer callback to fill jupyter console buffer
function! jupyter#monitor_console#UpdateConsoleBuffer(timer) abort
    python3 if _jupyter_session.monitor: _jupyter_session.monitor.timer_write_msgs()
endfunction
