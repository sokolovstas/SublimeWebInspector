#!/bin/bash

rsync -a --del -i --exclude='.git'  ~/Web\ Inspector/ ~/Library/Application\ Support/Sublime\ Text\ 3/Packages/Web\ Inspector

