# Jupyter-Vim

A vim plugin for developing python code without leaving the terminal.

## Installation

If you don't have a preferred installation method, I recommend
installing [pathogen.vim](https://github.com/tpope/vim-pathogen), and
then run:

```bash
    $ cd ~/.vim/bundle
    $ git clone https://github.com/jupyter-vim/jupyter-vim.git
```

Make sure that the python installation that Vim is using has jupyter installed.
One way to do this is to 
```vim
   if has('nvim')
       let g:python3_host_prog = '/path/to/python/bin/python3'
   else
       set pyxversion=3

       " OSX
       set pythonthreedll=/Library/Frameworks/Python.framework/Versions/3.6/Python

       " Windows
       set pythonthreedll=python37.dll
       set pythontheehome=C:\Python37
   endif
```

Once help tags have been generated, you can view the manual with
`:help jupyter-vim`.

## Quickstart
First, we need to configure the jupyter console and qtconsole clients to
display output from other clients. 

The config files can be found in in `~/.jupyter`, if they don't exist yet you
can generate them with:

```bash
$ jupyter console --generate-config
$ jupyter qtconsole --generate-config
```

Now you need to uncomment and change the following config options to `True`.

For qtconsole:

```python
c.ConsoleWidget.include_other_output = True
```

For console:

```python
c.ZMQTerminalInteractiveShell.include_other_output = True
```

To begin a session:

```bash
$ jupyter qtconsole &  # open a jupyter console window
$ vim <your_script>.py
```

In vim: `:JupyterConnect`

Then, use `:JupyterRunFile`, or `:[range]JupyterSendRange` to execute lines of
code!

Code will be sent and executed as expected in qtconsole, however the
jupyter console will still not update but shows the result after you press
enter.

## Info
Once we fell in love with Vim, we couldn't bear having to jump back and forth
between the ipython/jupyter console and editor anymore. We modeled this simple
interface off of the ideas in
[vim-ipython](https://github.com/ivanov/vim-ipython), but have pared down many
of the features, like the replication of the Jupyter console in a vim buffer,
to make the plugin much more 'lightweight'.

Still a work in progress!

## Troubleshooting

Make sure that you are running Vim 8 or higher with Python 3 support

### CONTRIBUTING

Please feel free to raise issues and pull requests on
[the github repository](https://github.com/jupyter-vim/jupyter-vim).

### CREDITS
We owe significant thanks to the original developer of this plugin: 
[Paul Ivanov](https://github.com/ivanov).
It is far easier to update something that already works well than to forge
a new path from scratch.

