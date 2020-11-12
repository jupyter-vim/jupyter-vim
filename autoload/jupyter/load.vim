function! jupyter#load#MakeStandardCommands() abort
    " Standard commands, called from each ftplugin so that we only map the
    " keys buffer-local for select filetypes.
    command! -buffer -nargs=* -complete=customlist,jupyter#CompleteConnect
        \ JupyterConnect call jupyter#Connect(<f-args>)
    command! -buffer -nargs=0    JupyterDisconnect      call jupyter#Disconnect()
    command! -buffer -nargs=1    JupyterSendCode        call jupyter#SendCode(<args>)
    command! -buffer -count      JupyterSendCount       call jupyter#SendCount(<count>)
    command! -buffer -range -bar JupyterSendRange       <line1>,<line2>call jupyter#SendRange()
    command! -buffer -nargs=0    JupyterSendCell        call jupyter#SendCell()
    command! -buffer -nargs=0    JupyterUpdateMonitor   call jupyter#UpdateMonitor()
    command! -buffer -nargs=? -complete=dir  JupyterCd  call jupyter#JupyterCd(<f-args>)
    command! -buffer -nargs=? -bang -complete=customlist,jupyter#CompleteTerminateKernel
        \ JupyterTerminateKernel  call jupyter#TerminateKernel(<bang>0, <f-args>)
    command! -buffer -nargs=* -complete=file
        \ JupyterRunFile update | call jupyter#RunFile(<f-args>)
endfunction


function! jupyter#load#MapStandardKeys() abort
    " Standard keymaps, called from each ftplugin so that we only map the keys
    " buffer-local for select filetypes.
    nnoremap <buffer> <silent> <localleader>R    :JupyterRunFile<CR>

    " Change to directory of current file
    nnoremap <buffer> <silent> <localleader>d    :JupyterCd %:p:h<CR>

    " Send just the current line
    nnoremap <buffer> <silent> <localleader>X    :JupyterSendCell<CR>
    nnoremap <buffer> <silent> <localleader>E    :JupyterSendRange<CR>

    " Send the text to jupyter kernel
    nmap <buffer> <silent> <localleader>e        <Plug>JupyterRunTextObj
    vmap <buffer> <silent> <localleader>e        <Plug>JupyterRunVisual

    nnoremap <buffer> <silent> <localleader>U    :JupyterUpdateShell<CR>
endfunction

" Create <Plug> for user mappings
noremap <silent> <Plug>JupyterRunTextObj    :<C-u>set operatorfunc=<SID>opfunc_run_code<CR>g@
noremap <silent> <Plug>JupyterRunVisual     :<C-u>call <SID>opfunc_run_code(visualmode())<CR>gv

"-----------------------------------------------------------------------------
"        Operator Function:
"-----------------------------------------------------------------------------

" Factory: callback(text) -> operator_function
function! s:get_opfunc(callback) abort
    " Define the function
    function! s:res_opfunc(type) abort closure
        " From tpope/vim-scriptease
        let saved = [&selection, &clipboard, @@]
        try
            set selection=inclusive clipboard-=unnamed clipboard-=unnamedplus
            " Invoked from visual mode (V, v, ^V)
            if a:type =~# '^.$'
                silent exe 'norm! `<' . a:type . '`>y'
            " Invoked from operator pending (line, block or visual)
            else
                silent exe 'norm! `[' . get({'l': 'V', 'b': '\<C-V>'}, a:type[0], 'v') . '`]y'
            endif
            redraw
            let l:text = @@
        finally
            let [&selection, &clipboard, @@] = saved
        endtry

        " Call callback
        call a:callback(l:text)
    endfunction

    " Return the closure
    return funcref('s:res_opfunc')
endfunction


" Operator function to run selected|operator text
function! s:opfunc_run_code(type)
    call s:get_opfunc(function('jupyter#SendCode'))(a:type)
endfunction
