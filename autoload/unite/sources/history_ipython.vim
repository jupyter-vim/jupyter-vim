if exists('g:loaded_history_ipython')
  finish
endif
let g:loaded_history_ipython = 1

let s:save_cpo = &cpo
set cpo&vim

function! unite#sources#history_ipython#define()
  return s:source
endfunction

let s:source = {
    \ 'name' : 'history/ipython',
    \ 'description' : 'candidates from IPython history',
    \ 'action_table' : {},
    \ 'hooks' : {},
    \ 'default_action' : 'send',
    \ 'default_kind' : 'word',
    \ 'syntax' : 'uniteSource__Python',
    \ 'max_candidates' : 100,
    \}

function! s:source.hooks.on_syntax(args, context)
  let save_current_syntax = get(b:, 'current_syntax', '')
  unlet! b:current_syntax

  try
    silent! syntax include @Python syntax/python.vim
    syntax region uniteSource__IPythonPython
        \ start=' ' end='$' contains=@Python containedin=uniteSource__IPython
    let &l:iskeyword = substitute(&l:iskeyword, ',!$\|!,', '', '')
  finally
    let b:current_syntax = save_current_syntax
  endtry
endfunction

function! s:source.hooks.on_init(args, context)
  if !exists('*IPythonHistory')
    call unite#print_source_error(
          \ 'IPythonHistory() does not exist', s:source.name)
    return
  endif

  let args = unite#helper#parse_source_args(a:args)
  let a:context.source__session = get(a:context, 'source__session', -1)
  if a:context.source__session == -1
    let a:context.source__session = get(args, 0, -1)
  endif
  let a:context.source__input = a:context.input
  if a:context.source__input == '' || a:context.unite__is_restart
    let a:context.source__input = unite#util#input('Pattern: ',
        \ a:context.source__input,
        \ 'customlist,IPythonCmdComplete')
  endif

  call unite#print_source_message('Pattern: '
      \ . a:context.source__input, s:source.name)
endfunction

function! s:source.gather_candidates(args, context)
  if !exists('*IPythonHistory')
    return []
  endif

  return map(IPythonHistory(a:context.source__input,
      \                     a:context.source__session), '{
      \ "word" : v:val.code,
      \ "abbr" : printf("'''''' %d/%d '''''' %s", v:val.session, v:val.line,
      \   v:val.code =~ "\n" ?
      \     "\n" . join(split(v:val.code, "\n")[:50], "\n") : v:val.code),
      \ "is_multiline" : 1,
      \ "source__session" : v:val.session,
      \ "source__line" : v:val.line,
      \ "source__context" : a:context,
      \ "action__regtype" : "V",
      \ }')
endfunction

let s:source.action_table.send = {
    \ 'description' : 'run in IPython',
    \ 'is_selectable' : 1,
    \ }
function! s:source.action_table.send.func(candidates)
  for candidate in a:candidates
    let g:ipy_input = candidate.word
    Python2or3 run_ipy_input()
    silent! unlet g:ipy_input
  endfor
endfunction

let s:source.action_table.session = {
    \ 'description' : "get history for candidate's session",
    \ 'is_quit' : 0,
    \ 'is_invalidate_cache' : 1,
    \ }
function! s:source.action_table.session.func(candidate)
  let context = a:candidate.source__context
  let context.source__input = unite#util#input('Pattern: ',
      \ context.source__input,
      \ 'customlist,IPythonCmdComplete')
  let context.source__session = a:candidate.source__session
endfunction

let s:source.action_table.session_info = {
    \ 'description' : "print information about a session",
    \ 'is_quit' : 0,
    \ }
function! s:source.action_table.session_info.func(candidate)
  let store_history = get(g:, 'ipython_store_history', 1)
  try
    let g:ipython_store_history = 0
    let session_info = [
        \ "from IPython import get_ipython",
        \ "def _session_info(session=0):",
        \ "    def date(d):",
        \ "        return d.strftime('%a %d%b%Y %T')",
        \ "    session_id, start, end, cmds, remark = " .
        \ "        get_ipython().history_manager.get_session_info(session)",
        \ "    val = 'start: {0}'.format(date(start))",
        \ "    if end:",
        \ "        val += '; end: {0}; {1} commands'.format(date(end), cmds)",
        \ "    return val",
        \ ]
    let g:ipy_input = join(session_info, "\n")
    silent Python2or3 run_ipy_input(silent=True)
    let g:ipy_input = printf('_session_info(%d)', a:candidate.source__session)
    silent! unlet g:ipy_result
    Python2or3 eval_ipy_input('g:ipy_result')
    echomsg printf('session %d: %s',
        \          a:candidate.source__session, g:ipy_result)
  finally
    let g:ipython_store_history = store_history
  endtry
endfunction

let s:source.action_table.macro = {
    \ 'description' : 'create IPython macro',
    \ 'is_selectable' : 1,
    \ }
function! s:source.action_table.macro.func(candidates)
  let g:ipy_input = printf('%%macro %s %s',
      \ unite#util#input('Macro name: '),
      \ join(map(a:candidates,
      \ 'printf("%s/%s", v:val.source__session, v:val.source__line)'))
      \ )
  Python2or3 run_ipy_input()
  silent! unlet g:ipy_input
endfunction

let s:source.action_table.yank = {
    \ 'description' : 'yank candidates',
    \ 'is_selectable' : 1,
    \ 'is_quit' : 1,
    \ }
function! s:source.action_table.yank.func(candidates)
  if len(a:candidates) == 1 && a:candidates[0].word !~ "\n"
    let text = a:candidates[0].word
    let mode = 'v'
  else
    let text = join(map(copy(a:candidates), 'v:val.word'), "\n\n")
    let mode = 'V'
  endif
  call setreg('"', text, mode)
  if has('clipboard')
    if &clipboard =~# '\<unnamed\>'
      call setreg('*', text, mode)
    endif
    if &clipboard =~# '\<unnamedplus\>'
      call setreg('+', text, mode)
    endif
  endif

  echohl Question | echo 'Yanked:' | echohl Normal
  echo text
endfunction

let s:source.action_table.append = {
    \ 'description' : 'append candidates',
    \ 'is_selectable' : 1,
    \ }
function! s:source.action_table.append.func(candidates)
  put = join(map(copy(a:candidates), 'v:val.word'), \"\n\n\")
endfunction

let s:source.action_table.insert = {
    \ 'description' : 'insert candidates',
    \ 'is_selectable' : 1,
    \ }
function! s:source.action_table.insert.func(candidates)
  put! = join(map(copy(a:candidates), 'v:val.word'), \"\n\n\")
endfunction

let &cpo = s:save_cpo
unlet s:save_cpo

" vim:set et ts=2 sts=2 sw=2:
