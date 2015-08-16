robocopy "%userprofile%/repos/web inspector" "%appdata%/sublime text 3/packages/web inspector" /s /xd .git* /xf .git* /xf *st3* /mir
attrib +r "%appdata%/sublime text 3/packages/web inspector/*py"