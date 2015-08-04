
# this contains all globals that are used by 
# modules that are imported in more than one place.
#
# if there is a circle of imports then globals
# can be multiply instantiated, once initially,
# then again when the file is cyclically imported
#
# but if the global is factored into config.py
# and config.py imports nothing itself,
# only one instance of the global will exist.
buffers  = {}
