# Sublime Web Inspector

__Adds a basic Javascript Console and Debugger to Sublime Text.__ 

This means you can stay in Sublime, in your code, while debugging your Javascript on the page.

![Screenshot](https://github.com/sokolovstas/SublimeWebInspector/raw/master/overview.png)

Because of the nature of Sublime, all information is presented as text, however this turns out to work well enough. You can click on objects from console or stack trace to evaluate them. You can also click on a file name to goto the file and line. All clickable zones have borders to appear like buttons. Because it supports Source Maps, you can step in your originally authored code, such as Coffeescript or Typescript.

This package aims to keep you in Sublime a little more, and jump to your browser tools a little less. The philosophy is, if you can find a simple error using Sublime, you're already where you need to be to fix it. For anything more complicated, drop into the browser tools in the normal way.

To use against:

* __Chrome__ -- just works
* __Internet Explorer 11__ -- start up IE, then start the [IE Diagnostics Adapter](https://github.com/Microsoft/IEDiagnosticsAdapter/releases). Web Inspector should detect it and offer to Start Debugging. Soon, Web Inspector will detect IE and offer to launch it as well. Note that you cannot use the Chrome tools and Web Inspector at the same time, but you /can/ use the Internet Explorer F12 tools (perhaps for the DOM explorer) and Web Inspector (for debugging) at the same time.
* __Edge__ -- start up Edge, then start the [Edge Diagnostics Adapter](https://github.com/Microsoft/edge-diagnostics-adaptor/releases). Web Inspector should detect it and offer to Start Debugging. Soon, Web Inspector will detect Edge and offer to launch it as well

# Features
- Debugger stepping and breakpoints.
- Console with colorized messages.
- Navigable stack trace.
- Inspect and expand objects.
- Evaluate expressions.
- Step directly through your originally authored code, such as Typescript, if source maps are available

## Future plans

* Support for styles editing, making it easy to see which styles in your CSS files are in use, and edit them in place. 
* Better support for Internet Explorer (for now, via the [IE Diagnostics Adapter](https://github.com/Microsoft/IEDiagnosticsAdapter/releases)) including potentially working against both browsers at once. 
* Support for live editing of your Javascript and CSS

Please help us prioritize. We would welcome collaboration. You can add feature requests or bugs to the [Issues List](https://github.com/sokolovstas/SublimeWebInspector/issues) here.

## Installation
* Make sure the [Sublime Package Manager is installed](https://packagecontrol.io/installation) in Sublime.
* Run "Package Control: Install Package" command and choose "Web Inspector"

## Getting started
- Open your web site root with "Open Folder" in Sublime. (This will allow Web Inspector to map a file on disk to a file in the browser.)
- If your target is Chrome, make sure any existing instances are closed.
- Press CTRL+SHIFT+R (⌘ + SHIFT + R) and select "Start Google Chrome with remote debug port 9222". (If CTRL+SHIFT+R didn't work, do CTRL+SHIFT+P and choose Web Inspector. Also, check the Sublime console for error messages.)
- After starting Chrome navigate to your site. (Or, set "chrome_url" in Web Inspector settings, see below.)
- Go to Sublime press CTRL+SHIFT+R and select "Start debugging" and select your tab in the list provided. It will select it automatically if there is only one open.

#### If it won't get past "Start Google Chrome"
If Chrome was already open when Sublime launches it with the debugger flag, Chrome won't open the port, so the debugger can't attach. Close all instances of Chrome and try again. 
 
### Controlling debugger
CTRL+SHIFT+R (⌘ + SHIFT + R) and:
- Pause execution (or F8 to toggle)
- Resume execution (or F8 or F5)
- Step into (or F11)
- Step out (or Shift+F11)
- Step over (or F10)
- Evaluate selection (if paused on call frame)

### Breakpoints
CTRL+SHIFT+R (⌘ + SHIFT + R) and Toggle breakpoints

Breakpoints toggled when not debugging should bind when you start debugging. Breakpoints are persisted between sessions in your user settings.

### Page
CTRL+SHIFT+R (⌘ + SHIFT + R) and Reload page

### Start-stop
CTRL+SHIFT+R (⌘ + SHIFT + R) and:
- Start debugging (may offer a choice of page)
- Stop debugging

  You may stop and start debugging without restarting your browser.

#### If Web Inspector won't bind breakpoints
Currently Web Inspector requires that you have access to the Javascript file -- it can't yet retrieve the Javascript from the browser, as browser tools do. To find the local file, Web Inspector will recurse within any folders you have opened, and any files you have opened. Web Inspector will then match up files in that folder with URLs the browser tells it about. Sometimes it is helpful to press CTRL+SHIFT+R and choose "Dump Mappings" to see if it did this successfully. Also, try setting "debug_mode": "true" in your web inspector settings, and restarting debugging. This will dump detailed information to the Sublime Console (Ctrl-`) showing where it's looked.

#### If Web Inspector can't resolve original sources
To debug original sources, Web Inspector must find a 

         //# sourceMappingURL=

comment at the end of the JavaScript file. That comment must contain a relative path to a local source map file. The source map must in turn have path(s) to original source files. As above, set "debug_mode": "true" and restart to get details about the search for source maps and authored files dumped to the Sublime Console (Ctrl-`).  

## Settings
You can change layouts for the debugger, color options, and path to Google Chrome in settings. See [list of settings here](https://github.com/sokolovstas/SublimeWebInspector/wiki/User-Settings).

By default, after "Start Chrome" you must navigate to your site. To do this automatically, add a setting like this to your user settings for the plugin:

	"chrome_url": "http://localhost/your/site"

## Pre-Release
To receive pre-release versions, instead of blessed versions, add Web Inspector to your install_prereleases section of your Package Control user settings, for example:

	"install_prereleases":
	[
	"Web Inspector"
	]

## Stats
[Download graph](https://packagecontrol.io/packages/Web%20Inspector)

*Thanks XDebug Authors for inspiration*
