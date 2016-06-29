robocopy "%~dp0\.." "%appdata%/sublime text 3/packages/web inspector" /s /xd .git* /xf .git* /xf *st3* /mir
attrib +r /s "%appdata%/sublime text 3/packages/web inspector/*py"