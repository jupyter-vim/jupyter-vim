# Jupyter-Vim

A vim plugin for developing python code without leaving the terminal.

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

