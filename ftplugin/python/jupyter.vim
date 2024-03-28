"=============================================================================
"     File: ftplugin/python/jupyter.vim
"  Created: 2019-03-03 16:37
"   Author: Bernie Roesler
"
"  Description: Python-specific settings, commands and mappings
"
"=============================================================================

" User-specified flags for IPython's run file magic can be set per-buffer
let b:ipython_run_flags = ''

" Highlight jupyter cells (lines beginning with ##) such that it is easier to
" see them
if g:jupyter_highlight_cells
    fun! SetCellHighlighting()
        for cell_separator in g:jupyter_cell_separators
            let regex_cell= "^" . cell_separator . "\\([^#]\\|$\\).*$"
            let match_cmd = "syntax match JupyterCell \"" . regex_cell . "\"" 
            let highlight_cmd = "highlight JupyterCell ctermfg=255 guifg=#eeeeee ctermbg=022 guibg=#005f00 cterm=bold gui=bold"
            if !hlexists('JupyterCell')
                execute highlight_cmd
            endif
            execute match_cmd
        endfor
    endfu
    exe 'augroup jupyter_highlight_cell_' . bufnr()
    exe '  au!'
    exe '  autocmd BufEnter <buffer> call SetCellHighlighting()'
    exe 'augroup END'
endif

"}}}--------------------------------------------------------------------------
"        Commands: {{{
"-----------------------------------------------------------------------------
command! -buffer -nargs=?
            \ PythonImportThisFile update | call jupyter#RunFile('-n', expand("%:p"))

" Debugging commands
command! -nargs=0   PythonSetBreak  call jupyter#PythonDbstop()
command! -nargs=0   PythonStartDebugger  call jupyter#PythonStartDebugger()

"}}}--------------------------------------------------------------------------
"        Key Mappings: {{{
"-----------------------------------------------------------------------------
if exists('g:jupyter_mapkeys') && g:jupyter_mapkeys
    " Run the current file
    nnoremap <buffer> <silent> <localleader>I :PythonImportThisFile<CR>

    " Debugging maps
    nnoremap <buffer> <silent> <localleader>b :PythonSetBreak<CR>
    nnoremap <buffer> <silent> <localleader>d :PythonStartDebugger<CR>
endif
"}}}

"=============================================================================
"=============================================================================
