# Sublime Web Inspector (SWI)

Sublime Web Inspector works on top of WebInspectorProtocol. All information is displayed in console and text files. 
You can click on objects from console or stack trace to evaluate them. You can also click on a file name to 
goto the file and line instantly. All clickable zones have borders to simply vizualize them.

You can add feature requests or bugs to https://github.com/sokolovstas/SublimeWebInspector/issues

*Thanks XDebug Authors for inspiration*

## Installation
Execute the following command in your Sublime Packages folder:
```git clone git://github.com/sokolovstas/SublimeWebInspector.git Web\ Inspector``` 

*I will prepare a plugin to Package Manager after additional testing*

## Features

- Breakpoints for project stored in user settings with absolute paths.
- Console.
- Debugger steps and breakpoints.
- Stack trace.
- You can see object properties and values in console and stack trace.

## Commands

You can find all commands in the "Sublime Web Inspector" namespace. Here is a complete list:

### Command for controlling debugger
- swi\_debug\_resume: Resume from pause
- swi\_debug\_step\_into: Step into debugger
- swi\_debug\_step\_out: Step out debugger
- swi\_debug\_step\_over: Step over debugger
- swi\_debug\_evaluate: Evaluate selection (if paused on call frame)

### Breakpoints
- swi\_debug\_breakpoint: Add remove breakpoints

### Page
- swi\_debug\_reload: Reload connected page

### Start-stop
- swi\_debug\_start: Start debugger
- swi\_debug\_stop: Stop debugger

### Utils
- swi\_debug\_start\_chrome: Start Google Chrome
- swi\_show\_file\_mapping: Show mapping local file to url

## Settings

You can change layouts for the debugger, color options, and path to Google Chrome in settings.

## Additional Notes
*Close Google Chrome before you run it in remote debugger mode.*
