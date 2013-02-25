# Sublime Web Inpsector (SWI)

Sublime Web Inspector works on top of WebInspectorProtocol. All information is displayed in console and text files. You can click on objects from console or stack trace to evaluate them. You can click on file name to goto file and line instantly. All clickable zone have borders to simply vizualize them.

All feature request and bugs you can add to https://github.com/sokolovstas/SublimeWebInspector/issues

*Thanks XDebug Authors for inspiration*

## Instalation
Do in your Packages folder:
```git clone git://github.com/sokolovstas/SublimeWebInspector.git Web\ Inpsector``` 

I prepare plugin to Package Manager after some testing

## Features

- Breakpoints for project stored in user settings with absolute paths.
- Console.
- Debugger steps and breakpoints.
- Stack trace.
- You can see object properties and values in console and stack trace.

## Commands

All commands you can find in "Sublime Web Inspector" command. And here a complete list:

### Command for controlling debugger
- swi\_debug\_resume
- swi\_debug\_step\_into
- swi\_debug\_step\_out
- swi\_debug\_step\_over

### Breakpoints
- swi\_debug\_breakpoint

### Page
- swi\_debug\_reload

### Start-stop
- swi\_debug\_start
- swi\_debug\_stop

### Utils
- swi\_debug\_start\_chrome

## Settings

In settings you can change layouts for debugger, some color and path to Google Chrome

## PS
*Close Google Chrome befor run it in remote debugger mode.*
