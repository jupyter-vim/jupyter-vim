"""
Jupyter language interface for vim client:

To add a language, please fill all the field.
If it is hard, just put '-1', it will never complain.
See cpp's way to run a file (defer work to python)
"""

# Export only: see at end
__all__ = ['list_languages', 'get_language']


class Language:
    """Language Base"""
    prompt_in = 'In [{:d}]: '
    prompt_out = 'Out[{:d}]: '
    print_string = 'print("{}")'
    run_file = '-1'
    cd = 'cd "{}"'
    pid = '-1'
    cwd = '-1'
    hostname = '-1'


class Bash(Language):
    prompt_in = 'Sh [{:d}]: '
    print_string = 'echo -e "{}"'
    run_file = 'source "{}"'
    cd = 'cd "{}"'
    pid = '_res=$$; echo $_res;'
    cwd = '_res=$(pwd); echo $_res;'
    hostname = '_res=$(hostname); echo $_res;'


class Cpp(Language):
    """Note :Pid is the first to run, so make import there
    I don't want to implement include so let it to -1,
        then python send file content
    """
    prompt_in = 'C++[{:d}]: '
    prompt_out = 'Out[{:d}]: '
    print_string = 'printf("%s", "{}");'
    run_file = '-1'
    cd = 'chdir("{}");'
    pid = """
        #include <unistd.h>
        #include <stdio.h>
        #include <limits.h>
        int _res_pid = getpid();
        printf("%d", _res_pid);
        """
    cwd = 'printf("%s", get_current_dir_name();'
    hostname = ('char _res_hostname[HOST_NAME_MAX];'
                ' gethostname(_res_hostname, HOST_NAME_MAX);'
                ' printf("%s", _res_hostname);')


class Java(Language):
    prompt_in = 'Ja [{:d}]: '
    print_string = 'System.out.println("{}");'
    run_file = """ // Import
        import java.nio.file.Files;
        import java.nio.file.Paths;
        import jdk.jshell.JShell;
        import jdk.jshell.SnippetEvent;
        // Slurp file
        String _res_file = "{}";
        String _res_content = Files.readString(Paths.get(_res_file));
        // Eval
        JShell _res_shell = JShell.create();
        List<SnippetEvent> _res_event = _res_shell.eval(_res_content);
        // Message
        System.out.printf("\\n\\n<-- Run status: %s <- \\"%s\\"\\n",
            _res_event.get(0).status(), _res_file);
        System.out.println(
            "------------------------------------------------------------");
    """
    cd = 'System.setProperty("user.dir", "{}");'
    pid = 'String _res = String.valueOf(ProcessHandle.current().pid()); _res;'
    cwd = ('String _res = new File(System.getProperty("user.dir"))'
           '.getAbsoluteFile().getPath(); _res;')
    hostname = 'String _res = InetAddress.getLocalHost().getHostName(); _res;'


class Javascript(Language):
    prompt_in = 'Js [{:d}]: '
    print_string = 'console.log("{}");'
    run_file = 'eval("" + require("fs").readFileSync("{}"));'
    cd = 'require("process").chdir("{}");'
    pid = '_res = require("process").pid;'
    cwd = '_res = require("process").cwd();'
    hostname = '_res = require("os").userInfo().username;'


class Julia(Language):
    prompt_in = 'Jl [{:d}]: '
    print_string = 'println("{}")'
    run_file = 'include("{}")'
    cd = 'cd "{}"'
    pid = '_res = getpid()'
    cwd = '_res = pwd()'
    hostname = '_res = gethostname()'


class Perl(Language):
    prompt_in = 'Pl [{:d}]: '
    print_string = 'print("{}")'
    run_file = 'my $_res = "{}"; $_res =~ s/\\.[^.]+$//; do $_res;'
    cd = 'chdir("{}")'
    pid = '$_res = $$'
    cwd = 'use Cwd; $_res = getcwd();'
    hostname = 'use Sys::Hostname qw/hostname/; $_res = hostname();'


class Python(Language):
    prompt_in = 'Py [{:d}]: '
    print_string = 'print("{}")'
    run_file = '%run "{}"'
    cd = '%cd "{}"'
    pid = 'import os; _res = os.getpid()'
    cwd = 'import os; _res = os.getcwd()'
    hostname = 'import socket; _res = socket.gethostname()'


class Ruby(Language):
    prompt_in = 'Rb [{:d}]: '
    print_string = 'print("{}")'
    run_file = 'load "{}"'
    cd = '_res = Dir.chdir "{}"'
    pid = '_res = Process.pid'
    cwd = '_res = Dir.pwd'
    hostname = '_res = Socket.gethostname'


# Dict: kernel_type -> class
language_dict = {
    'default': Language,
    'bash': Bash,
    'cpp': Cpp,
    'java': Java,
    'javascript': Javascript,
    'julia': Julia,
    'perl': Perl,
    'python': Python,
    'ruby': Ruby,
}


def list_languages():
    """List coding languages implemented by module"""
    return language_dict.keys()


def get_language(kernel_type):
    """Get language class
    Assert that language is in language_list (checked by caller)
    But still, let's return something
    """
    if kernel_type not in list_languages():
        return Language
    return language_dict[kernel_type]
