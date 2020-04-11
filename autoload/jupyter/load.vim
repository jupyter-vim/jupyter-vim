function! jupyter#load#MakeStandardCommands() abort
    " Standard commands, called from each ftplugin so that we only map the
    " keys buffer-local for select filetypes.
    command! -buffer -nargs=* -complete=customlist,jupyter#CompleteConnect
        \ JConnect call jupyter#Connect(<f-args>)
    command! -buffer -nargs=0    JDisconnect      call jupyter#Disconnect()
    command! -buffer -nargs=1    JSendCode        call jupyter#SendCode(<args>)
    command! -buffer -count      JSendCount       call jupyter#SendCount(<count>)
    command! -buffer -range -bar JSendRange       <line1>,<line2>call jupyter#SendRange()
    command! -buffer -nargs=0    JSendCell        call jupyter#SendCell()
    command! -buffer -nargs=0    JUpdateMonitor   call jupyter#UpdateMonitor()
    command! -buffer -nargs=? -complete=dir  JCd  call jupyter#JupyterCd(<f-args>)
    command! -buffer -nargs=? -bang -complete=customlist,jupyter#CompleteTerminateKernel
        \ JupyterTerminateKernel  call jupyter#TerminateKernel(<bang>0, <f-args>)
    command! -buffer -nargs=* -complete=file
        \ JRunFile update | call jupyter#RunFile(<f-args>)
endfunction


function! jupyter#load#MapStandardKeys() abort
    " Standard keymaps, called from each ftplugin so that we only map the keys
    " buffer-local for select filetypes.
    nnoremap <buffer> <silent> <localleader>R    :JRunFile<CR>

    " Change to directory of current file
    nnoremap <buffer> <silent> <localleader>d    :JCd %:p:h<CR>

    " Send just the current line
    nnoremap <buffer> <silent> <localleader>X    :JSendCell<CR>
    nnoremap <buffer> <silent> <localleader>E    :JSendRange<CR>

    " Send the text to jupyter kernel
    nmap <buffer> <silent> <localleader>e        <Plug>JupyterRunTextObj
    vmap <buffer> <silent> <localleader>e        <Plug>JupyterRunVisual

    nnoremap <buffer> <silent> <localleader>U    :JUpdateShell<CR>
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
