
import threading 
import sublime

def assert_main_thread():
    global main_thread
    assert threading.current_thread().ident == main_thread.ident, "not on main thread"

main_thread = threading.current_thread()

def get_setting(key, default = None):
    s = sublime.load_settings("swi.sublime-settings")
    if s and s.has(key):
        return s.get(key)
    else:
    	return default
