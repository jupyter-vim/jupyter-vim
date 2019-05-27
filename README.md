# Jupyter-Vim

A vim plugin for developing code on a Jupyter notebook without leaving the
terminal.  Currently Python and Julia kernels are supported, and more languages
are on the way.

## Installation

If you don't have a preferred installation method, I recommend
installing [pathogen.vim](https://github.com/tpope/vim-pathogen), and
then run:

```bash
    $ cd ~/.vim/bundle
    $ git clone https://github.com/broesler/jupyter-vim.git
```

Once help tags have been generated, you can view the manual with
`:help jupyter-vim`.

In order for this plugin to work, **you must have Jupyter installed** in the
Python environment that vim's `pythonx` command uses.  If either:

* you use a Python environment manager such as `virtualenv`, and thus need
  Jupyter to be present no matter which environment is loaded from the shell
  you open vim from, or
* you only use one Python environment but you don't want to install Jupyter
  system-wide for whatever reason,

then the easiest way to meet the Jupyter requirement is to configure vim to
load a designated virtualenv at startup.  This is just to allow vim to call the
Jupyter client; you can run your Jupyter server in whatever Python environment
you want.  From vim, run

```vim
    :pythonx import sys; print(sys.version)
```

This will tell you whether `pythonx` is using Python 2 or Python 3.  (Or, see
`:help python_x` if you'd like to tweak your `pythonx` settings.)  Create a
virtualenv with that python version, for example

```bash
    $ virtualenv -p /usr/bin/python2.7 /path/to/my/new/vim_virtualenv
```

or

```bash
    $ virtualenv -p /usr/bin/python3 /path/to/my/new/vim_virtualenv
```

and then install Jupyter in that environment:

```bash
    $ source /path/to/my/new/vim_virtualenv
    $ pip install jupyter
```

Finally, tell vim to load this virtualenv at startup by adding these lines to
your vimrc:

```vim
    " Always use the same virtualenv for vim, regardless of what Python
    " environment is loaded in the shell from which vim is launched
    let g:vim_virtualenv_path = '/path/to/my/new/vim_virtualenv'
    if exists('g:vim_virtualenv_path')
        pythonx import os; import vim
        pythonx activate_this = os.path.join(vim.eval('g:vim_virtualenv_path'), 'bin/activate_this.py')
        pythonx with open(activate_this) as f: exec(f.read(), {'__file__': activate_this})
    endif
```

## Quickstart
To begin:

```bash
	$ jupyter qtconsole &  # open a jupyter console window
	$ vim <your_script>.py
```

In vim: `:JupyterConnect`

Then, use `:JupyterRunFile`, or `:[range]JupyterSendRange` to execute lines of
code!

## Info
Once I fell in love with Vim, I couldn't bear having to jump back and forth
between the ipython/jupyter console and editor anymore. I modeled this simple
interface off of the ideas in
[vim-ipython](https://github.com/ivanov/vim-ipython), but have pared down many
of the features, like the replication of the Jupyter console in a vim buffer,
to make the plugin much more 'lightweight'.

Still a work in progress!

### CONTRIBUTING

Please feel free to contact me at [bernard.roesler@gmail.com](mailto:bernard.roesler@gmail.com), with the subject line: "[jupyter-vim]: Contributing".

### CREDITS
I owe significant thanks to the original developer of this plugin: 
[Paul Ivanov](https://github.com/ivanov), as well as 
[Marijn van Vliet](https://github.com/wmvanvliet).
It is far easier to update something that already works well than to forge
a new path from scratch.

