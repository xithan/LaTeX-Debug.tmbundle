### LaTeX-Debug.tmbundle

This is a bundle for Textmate containg the two commands "Watch document" and "Typeset &amp; View" from Textmate's 
LaTeX bundle. I made some changes to make it easier to track down LaTeX errors. 
It's honestly a bunch of dirty hacks and the output crys for cosmetic improvements but it's functional and, in my opinion, very useful,
especially if you use "Watch document" a lot.

### Added features

I replaced the (not very helpful) error message dialog, that "Watch document" used to show when something went wrong,
with the HTML window with explicit error messages that "Typeset &amp; View" uses.

I added the following features to the HTML output:
- The "Undefined control sequence" error message includes the name of the unknown command.
- There is a fixed button in the upper right hand corner. If pressed the error message window scrolls to the first error
and the LaTeX document jumps to the line with the error. If pressed again the next error is displayed.
- The header is no longer fixed so there is more space for error messages.
- In each error message a klick on "Error Latex:" scrolls the window to the next error (useful if you get long lists of warnings in between)
- The total number of errors at the bottom is a link to the first error.
