# Sublime Web Inspector

__Adds a basic Javascript Console and Debugger to Sublime Text.__ 

This means you can stay in Sublime, in your code, while debugging your Javascript on the page.

Because of the nature of Sublime, all information is presented as text, however this turns out to work well enough. You can click on objects from console or stack trace to evaluate them. You can also click on a file name to goto the file and line. All clickable zones have borders to appear like buttons.

There are enough features that you can do basic diagnostics of your Javascript without leaving your editor for your browser tools.

To use against:

* __Chrome__ -- just works
* __Internet Explorer 11__ -- start up IE, then start the [IE Diagnostics Adapter](https://github.com/Microsoft/IEDiagnosticsAdapter/releases). Web Inspector should detect it and offer to Start Debugging. Soon, Web Inspector will detect IE and offer to launch it as well. Note that you cannot use the Chrome tools and Web Inspector at the same time, but you /can/ use the Internet Explorer F12 tools (perhaps for the DOM explorer) and Web Inspector (for debugging) at the same time.

## Future plans

* Add a basic __DOM explorer__ including trace styles.
* Add support for __Source Maps__ (for debugging Typescript, Coffeescript, etc)
* Better support for __Internet Explorer__ (for now, via the [IE Diagnostics Adapter](https://github.com/Microsoft/IEDiagnosticsAdapter/releases)) including potentially working against both at once. 
* Live source editing support
* More console and debugger features

Please help us prioritize. You can add feature requests or bugs to the [Issues List](https://github.com/sokolovstas/SublimeWebInspector/issues) here.

## Installation
Make sure the [Sublime Package Manager is installed](https://packagecontrol.io/installation) in Sublime.
Run "Package Control: Install Package" command and choose "Web Inspector"

## Getting started
- Open your web site root with "Open Folder" in Sublime. (This will allow Web Inspector to map a file on disk to a file in the browser.)
- If your target is Chrome, make sure any existing instances are closed.
- Press CTRL+SHIFT+R and select "Start Google Chrome with remote debug port 9222". (If CTRL+SHIFT+R didn't work, do CTRL+SHIFT+P and choose Web Inspector.)
- After starting Chrome navigate to your site. (Or, set this in Web Inspector settings, see below.)
- Go to Sublime press CTRL+SHIFT+R and select "Start debugging" and select your tab in the list provided.

## Features
- Breakpoints are persisted.
- Colorized console.
- Debugger steps and hits breakpoints.
- Stack trace.
- You can see object properties and values in console and scopes, and expand them.
- Evaluate arbitrary selected expressions.

### Controlling debugger
- Web Inspector>Pause execution (or F8 to toggle)
- Web Inspector>Resume execution (or F8 or F5)
- Web Inspector>Step into (or F11)
- Web Inspector>Step out (or Shift+F11)
- Web Inspector>Step over (or F10)
- Web Inspector>Evaluate selection (if paused on call frame)

### Breakpoints
- Web Inspector>Toggle breakpoints

### Page
- Web Inspector>Reload connected page

### Start-stop
- Web Inspector>Start debugging (.. and then choose your page)
- Web Inspector>Stop debugging

  You may stop and start debugging without restarting your browser.

### Utils
- Web Inspector>Start Chrome: Start Google Chrome
- Web Inspector>Show File Mapping

## Settings
You can change layouts for the debugger, color options, and path to Google Chrome in settings. See [list of settings here](https://github.com/sokolovstas/SublimeWebInspector/wiki/User-Settings).

By default, after "Start Chrome" you must navigate to your site. To do this automatically, add a setting like this to your user settings for the plugin:

"chrome_url": "http://localhost/your/site"

## Stats
[Download graph](https://packagecontrol.io/packages/Web%20Inspector)

*Thanks XDebug Authors for inspiration*