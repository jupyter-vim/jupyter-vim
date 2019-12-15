"=============================================================================
"     File: plugin/jupyter.vim
"  Created: 02/28/2018, 11:10
"   Author: Bernie Roesler
"
"  Description: Set up autocmds and config variables for jupyter-vim plugin
"
"  Filetypes: python, julia
"=============================================================================

if exists('g:loaded_jupyter_vim') || !(has('pythonx') || has('python') || has('python3')) || &compatible
    finish
endif

if !jupyter#init_python()
    finish
endif

"-----------------------------------------------------------------------------
"        Configuration: {{{
"-----------------------------------------------------------------------------
let s:default_settings = {
    \ 'shortmess': 0,
    \ 'auto_connect': 0,
    \ 'mapkeys': 1,
    \ 'monitor_console': 0,
    \ 'verbose': 0
\ }

for [s:key, s:val] in items(s:default_settings)
    if !exists('g:jupyter_' . s:key)
        execute 'let g:jupyter_' . s:key . ' = ' . s:val
    endif
endfor



augroup JupyterVimInit
    " By default, guess the kernel language based on the filetype. The user
    " can override this guess on a per-buffer basis.
    autocmd!
    autocmd BufEnter * let b:jupyter_kernel_type = get({
        \ 'python': 'python',
        \ 'julia': 'julia',
        \ }, &filetype, 'none')

    autocmd FileType julia,python call jupyter#MakeStandardCommands()
    autocmd FileType julia,python if g:jupyter_mapkeys |
                \ call jupyter#MapStandardKeys() |
                \ endif
augroup END

"}}}----------------------------------------------------------------------------
"       Connect to Jupyter Kernel  {{{
"-------------------------------------------------------------------------------
" XXX SLOW AS $@#!... need to figure out how to fork the connection process so
" vim still fires up quickly even if we forget to have a kernel running, or it
" can't connect for some reason.
if g:jupyter_auto_connect
    augroup JConnect
        autocmd!
        autocmd FileType julia,python JupyterConnect
    augroup END
endif

let g:loaded_jupyter_vim = 1
"=============================================================================
"=============================================================================
