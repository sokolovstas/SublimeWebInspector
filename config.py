
# this contains all globals that are used by 
# modules that are imported in more than one place.
# if modules X and Y both import Z, then
# two instances of any global in Z will
# exist, causing subtle problems.
#
# but if the global is factored into config.py
# and config.py is only imported by Z,
# only one instance of the global will exist.
buffers  = {}