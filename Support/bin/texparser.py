import sys
import re
import os.path
import os
import tmprefs
from struct import *


def percent_escape(str):
	return re.sub('[\x80-\xff /&]', lambda x: '%%%02X' % unpack('B', x.group(0))[0], str)

def make_link(file, line):
	return 'txmt://open?url=file:%2F%2F' + percent_escape(file) + '&amp;line=' + line

def shell_quote(string):
	return '"' + re.sub(r'([`$\\"])', r'\\\1', string) + '"'


class TexParser(object):
    """Master Class for Parsing Tex Typsetting Streams"""
    def __init__(self, input_stream, verbose):
        super(TexParser, self).__init__()
        self.input_stream = input_stream
        self.patterns = []
        self.done = False
        self.verbose = verbose
        self.numErrs = 0
        self.numWarns = 0
        self.isFatal = False
        self.fileStack = []  #TODO: long term - can improve currentFile handling by keeping track of (xxx and )

    def getRewrappedLine(self):
        """Sometimes TeX breaks up lines with hard linebreaks.  This is annoying.
           Even more annoying is that it sometime does not break line, for two distinct 
           warnings. This function attempts to return a single statement."""
        statement = ""
        while True:
            line = self.input_stream.readline()
            if not line:
                if statement: 
                    return statement
                else:
                    return ""
            statement += line.rstrip("\n")
            if len(line) != 80: # including line break
                break
        return statement+"\n"
    
    def parseStream(self):
        """Process the input_stream one line at a time, matching against
           each pattern in the patterns dictionary.  If a pattern matches
           call the corresponding method in the dictionary.  The dictionary
           is organized with patterns as the keys and methods as the values."""
        line = self.getRewrappedLine()
        while line and not self.done:
            line = line.rstrip("\n")
            foundMatch = False
            

            # process matching patterns until we find one
            for pat,fun in self.patterns:
                myMatch = pat.match(line)
                if myMatch:
                    fun(myMatch,line)
                    sys.stdout.flush()
                    foundMatch = True
                    break
            if self.verbose and not foundMatch:
                print line
            
            line = self.getRewrappedLine()
        if self.done == False:
            self.badRun()
        return self.isFatal, self.numErrs, self.numWarns

    def info(self,m,line):
        print '<p class="info">'
        print line
        print '</p>'

    def error(self,m,line):
        print '<p class="error">'
        print line
        print '</p>'
        self.numErrs += 1
        
    def warning(self,m,line):
        print '<p class="warning">'
        print line
        print '</p>'
        self.numWarns += 1

    def warn2(self,m,line):
        print '<p class="fmtWarning">'
        print line
        print '</p>'
        
    def fatal(self,m,line):
        print '<p class="error">'
        print line
        print '</p>'
        self.isFatal = True

    def badRun(self):
        """docstring for finishRun"""
        pass
        
class BibTexParser(TexParser):
    """Parse and format Error Messages from bibtex"""
    def __init__(self, btex, verbose):
        super(BibTexParser, self).__init__(btex,verbose)
        self.patterns += [ 
            (re.compile("Warning--I didn't find a database entry") , self.warning),
            (re.compile(r'I found no \\\w+ command') , self.error),
            (re.compile(r"I couldn't open style file"), self.error),
            (re.compile('This is BibTeX') , self.info),
            (re.compile('The style') , self.info),            
            (re.compile('Database') , self.info),                        
            (re.compile('---') , self.finishRun)
        ]
    
    def finishRun(self,m,line):
        self.done = True
        print '</div>'

class LaTexParser(TexParser):
    """Parse Output From Latex"""
    def __init__(self, input_stream, verbose, fileName):
        super(LaTexParser, self).__init__(input_stream,verbose)
        self.suffix = fileName[fileName.rfind('.')+1:]
        self.currentFile = fileName
        self.patterns += [
            #(re.compile('^This is') , self.info),
            (re.compile('^Document Class') , self.info),
            (re.compile('.*?\((\.\/[^\)]*?\.(tex|'+self.suffix+')( |$))') , self.detectNewFile),
            (re.compile('.*\<use (.*?)\>') , self.detectInclude),
            (re.compile('^Output written') , self.info),
            (re.compile('LaTeX Warning:.*?input line (\d+)(\.|$)') , self.handleWarning),
            (re.compile('LaTeX Warning:.*') , self.warning),
            (re.compile('^([^:]*):(\d+):\s+(pdfTeX warning.*)') , self.handleFileLineWarning),            
            (re.compile('.*pdfTeX warning.*') , self.warning),            
            (re.compile('LaTeX Font Warning:.*') , self.warning),            
            (re.compile('Overfull.*wide') , self.warn2),
            (re.compile('Underfull.*badness') , self.warn2),                        
            (re.compile('^([\.\/\w\x7f-\xff\- ]+(?:\.sty|\.tex|\.'+self.suffix+')):(\d+):\s+(.*)') , self.myHandleError),
            (re.compile('([^:]*):(\d+): LaTeX Error:(.*)') , self.handleError),
            (re.compile('([^:]*):(\d+): (Emergency stop)') , self.handleError),
            (re.compile('Runaway argument') , self.pdfLatexError),            
            (re.compile('Transcript written on (.*)\.$') , self.finishRun),
            (re.compile('^Error: pdflatex') , self.pdfLatexError),
            (re.compile('\!.*') , self.myHandleOldStyleErrors),
            (re.compile('^\s+==>') , self.fatal)
        ]
        self.blankLine = re.compile(r'^\s*$')        

    def parseStream(self):
        """Process the input_stream one line at a time, matching against
           each pattern in the patterns dictionary.  If a pattern matches
           call the corresponding method in the dictionary.  The dictionary
           is organized with patterns as the keys and methods as the values."""
        line = self.getRewrappedLine()
        waitForNextLine = False
        lastLine = ""
        lastMatch = ""
        while line and not self.done:
            line = line.rstrip("\n")
            foundMatch = False
            
            if waitForNextLine:
                waitForNextLine = False
                lastFun(lastMatch,lastLine, line)
                sys.stdout.flush()
                foundMatch = True
            # process matching patterns until we find one
            for pat,fun in self.patterns:
                myMatch = pat.match(line)
                if myMatch:
                    if fun == self.myHandleError or fun == self.myHandleOldStyleErrors:
                        lastFun = fun
                        lastMatch = myMatch
                        lastLine = line
                        waitForNextLine = True
                    else:
                        fun(myMatch,line)
                        sys.stdout.flush()
                        foundMatch = True
                    break
            if self.verbose and not foundMatch:
                print line
            
            line = self.getRewrappedLine()
        if self.done == False:
            self.badRun()
        return self.isFatal, self.numErrs, self.numWarns
    
    def detectNewFile(self,m,line):
        self.currentFile = m.group(1).rstrip()
        print "<h4>Processing: " + self.currentFile + "</h4>"

    def detectInclude(self,m,line):
        print "<ul><li>Including: " + m.group(1)
        print "</li></ul>"

    def handleWarning(self,m,line):
        print '<p class="warning"><a href="' + make_link(os.path.join(os.getcwd(),self.currentFile), m.group(1)) + '">'+line+"</a></p>"
        self.numWarns += 1
    
    def handleFileLineWarning(self,m,line):
        """Display warning. match m should contain file, line, warning message"""
        print '<p class="warning"><a href="' + make_link(os.path.join(os.getcwd(), m.group(1)),m.group(2)) + '">' + m.group(3) + "</a></p>"
        self.numWarns += 1
    
    def handleError(self,m,line):
        print '<p class="error">'
        print 'Latex Error: <a  href="' + make_link(os.path.join(os.getcwd(),m.group(1)),m.group(2)) +  '">' + m.group(1)+":"+m.group(2) + '</a> '+m.group(3)+'</p>'
        self.numErrs += 1
    
    def myHandleError(self,m,line,nextline):
        print '<p class="error">'
        
        line = m.group(3)
        if re.search('Undefined control sequence', line):
            match = re.search(r'\\\w+$',nextline)
            if match:
                line = "Undefined control sequence: " + match.group(0)
        if nextline and not len(nextline.strip()) > 0:
            line = line + ': ' + nextline
            
        # Verschiebung nach oben war notwendig als es noch das fixierte Banner gab
        #print '<a name="error%d" style="position:relative; top:-75px;">&nbsp;</a><a href="#error%d" style="text-decoration:none;">Latex Error:</a>' % (self.numErrs, self.numErrs + 1)
        print '<a href="#error%d" style="text-decoration:none;">Error Latex:</a><a name="error%d"  style="position:relative; top:-10px;">&nbsp;</a>' % (self.numErrs + 1, self.numErrs)
        print ' <a id="errorlink%d"' % self.numErrs
        file = re.sub("\./","",m.group(1))
        link = re.sub("%2F","/",make_link(os.path.join(os.getcwd(),file),m.group(2)))
        print 'href="' + link +  '">' + m.group(1)+":"+m.group(2) + '</a> '+ line +'</p>'
        self.numErrs += 1
    
        
    def finishRun(self,m,line):
        logFile = m.group(1).strip('"')
        print '<p>  Complete transcript is in '
        print '<a href="' + make_link(os.path.join(os.getcwd(),logFile),'1') +  '">' + logFile + '</a>'
        print '</p>'
        self.done = True

    def handleOldStyleErrors(self,m,line):
        if re.search('[Ee]rror', line):
            print '<p class="error">'
            print line
            print '</p>'
            self.numErrs += 1
        else:
            print '<p class="warning">'
            print line
            print '</p>'
            self.numWarns += 1
        
    def myHandleOldStyleErrors(self,m,line,nextline):
        if re.search('Undefined control sequence', line):
            match = re.search(r'\\\w+$',nextline)
            if match:
                nextline = ' ' + match.group(0)
        if nextline and not len(nextline.strip()) > 0:
            nextline = ': ' + nextline
            
        print '<p class="error">'
        print '<a href="#error%d" style="text-decoration:none;">Error Latex:</a><a name="error%d"  style="position:relative; top:-10px;">&nbsp;</a>' % (self.numErrs + 1, self.numErrs)
        print '<a id="errorlink%d"' % self.numErrs
        #print 'href="' + make_link(os.path.join(os.getcwd(),m.group(1)),m.group(2)) +  '">' + m.group(1)+":"+m.group(2) + '</a> '+m.group(3) + nextline +'</p>'
        #print line
        print 'href="#error0">' + line + '</a>' + nextline
#        print line + nextline
        print '</p>'
        self.numErrs += 1

        
    def pdfLatexError(self,m,line):
        """docstring for pdfLatexError"""
        print '<p class="error">'
        #print '<a href="#error%d" style="text-decoration:none;">Error pdfLatex:</a><a name="error%d"  style="position:relative; top:-10px;">&nbsp;</a>' % (self.numErrs + 1, self.numErrs)
        print line
        line = self.input_stream.readline()
        if line and re.match('^ ==> Fatal error occurred', line):  
            print line.rstrip("\n")
            print '</p>'
            self.isFatal = True
        else:
            if line:
                print '<pre>    '+ line.rstrip("\n") + '</pre>'
            print '</p>'    
        #self.numErrs += 1 # Nicht mitzaehlen. Da diese Fehler keinen Link haben, funktioniert sonst der Pfeil-Button nicht.
        sys.stdout.flush()
    
    def badRun(self):
        """docstring for finishRun"""
        print '<p class="error">A fatal error occured, log file is in '
        logFile = os.path.basename(os.getenv('TM_FILEPATH'))
        logFile = logFile.replace(self.suffix,'log')
        print '<a href="' + make_link(os.path.join(os.getcwd(),logFile),'1') +  '">' + logFile + '</a>'        
        print '</p>'

        
class WatchDocumentParser(LaTexParser):
    """Parse Output From Latex"""
    def __init__(self, input_stream, verbose, fileName):
        super(WatchDocumentParser, self).__init__(input_stream,verbose,fileName)
        self.suffix = fileName[fileName.rfind('.')+1:]
        self.currentFile = fileName
        self.patterns = [
            #(re.compile('^This is') , self.info),
            #(re.compile('^Document Class') , self.info),
            ####(re.compile('.*?\((\.\/[^\)]*?\.(tex|'+self.suffix+')( |$))') , self.detectNewFile),
            ####(re.compile('.*\<use (.*?)\>') , self.detectInclude),
            #(re.compile('^Output written') , self.info),
            #(re.compile('LaTeX Warning:.*?input line (\d+)(\.|$)') , self.handleWarning),
            #(re.compile('LaTeX Warning:.*') , self.warning),
            #(re.compile('^([^:]*):(\d+):\s+(pdfTeX warning.*)') , self.handleFileLineWarning),            
            #(re.compile('.*pdfTeX warning.*') , self.warning),            
            #(re.compile('LaTeX Font Warning:.*') , self.warning),            
            #(re.compile('Overfull.*wide') , self.warn2),
            #(re.compile('Underfull.*badness') , self.warn2),                        
            (re.compile('^([\.\/\w\x7f-\xff\- ]+(?:\.sty|\.tex|\.'+self.suffix+')):(\d+):\s+(.*)') , self.myHandleError),
            (re.compile('([^:]*):(\d+): LaTeX Error:(.*)') , self.handleError),
            (re.compile('([^:]*):(\d+): (Emergency stop)') , self.handleError),
            (re.compile('Runaway argument') , self.pdfLatexError),            
            #(re.compile('Transcript written on (.*)\.$') , self.finishRun),
            (re.compile('Output written on (.*)\.$') , self.finishRun),
            (re.compile('^Error: pdflatex') , self.pdfLatexError),
            (re.compile('\!.*') , self.myHandleOldStyleErrors),
            (re.compile('^\s+==>') , self.fatal)
        ]
        self.blankLine = re.compile(r'^\s*$')  
        #print '<div id="watchdocument">'
        
        
    def myHandleError(self,m,line,nextline):
        print '<p class="error">'
        line = m.group(3)
        if re.search('Undefined control sequence', line):
            match = re.search(r'\\\w+$',nextline)
            if match:
                line = "Undefined control sequence: " + match.group(0)
        if nextline and not len(nextline.strip()) > 0:
            line = line + ': ' + nextline
        
        # Verschiebung nach oben war notwendig als es noch das fixierte Banner gab
        #print '<a name="error%d" style="position:relative; top:-75px;">&nbsp;</a><a href="#error%d" style="text-decoration:none;">Latex Error:</a>' % (self.numErrs, self.numErrs + 1)
        print '<a href="#error%d" style="text-decoration:none;">Error Latex:</a><a name="error%d"  style="position:relative; top:-10px;">&nbsp;</a>' % (self.numErrs + 1, self.numErrs)
        print ' <a id="errorlink%d"' % self.numErrs
        file =re.sub("\.?(\w+)\.(?:ini|tex)","\\1.tex", m.group(1))
        file = re.sub("\./","",file)
        #print 'href="' + make_link(os.path.join(os.getcwd(),file),m.group(2)) +  '">' + file+":"+m.group(2) + ':</a> '+m.group(3)+ nextline + '</p>'
        link = re.sub("%2F","/",make_link(os.path.join(os.getcwd(),file),m.group(2)))
#        link = "txmt://open?url=file:///Users/drkuehl/Dropbox/Doktorarbeit/TsoReordered/Thesis/level2b.tex"
        print 'href="' + link +  '">' + file+":"+m.group(2) + ':</a> '+ line + '</p>'
        #print 'href="' + make_link(os.path.join(os.getcwd(),m.group(1)),m.group(2)) +  '">' + m.group(1)+":"+m.group(2) + '</a> '+m.group(3) + nextline +'</p>'
        self.numErrs += 1
    
    def badRun(self): # Tritt auf wenn nur die Preambel compiliert wird
        """docstring for finishRun"""
        #print '<p class="error">A fatal error occured, log file is in '
        #logFile = os.path.basename(os.getenv('TM_FILEPATH'))
        #logFile = logFile.replace(self.suffix,'log')
        #print '<a href="' + make_link(os.path.join(os.getcwd(),logFile),'1') +  '">' + logFile + '</a>'        
        #print '</p>'
        self.summary()
        #print '</div>' # watchdocument errors
    
    def summary(self):
        print('<script>'
                'function firstError() {' 
                    'if (document.getElementById("errorlink0")) document.location.href = "#error0";'
                    'else {'
                        'document.location.href = "#errorsummary";' 
                        '(elem=document.getElementById("fastfinder")).parentNode.removeChild(elem);}};' 
                'var i = 0;' 
                'function nextError() {' 
                    'document.location.href = "#error"+i;' 
                    'if (link=document.getElementById("errorlink"+i)) document.location = link.getAttribute("href");' 
                    'else {(elem=document.getElementById("fastfinder")).parentNode.removeChild(elem);'
                        'document.location.href = "#errorsummary"}' 
                    'i = i+1;  }'
                'document.addEventListener("DOMContentLoaded", firstError, false);'
            '</script>')
        print '<div id="fastfinder" style="background-color:transparent;"><form><input type="button" id="nexterror" style="text-decoration:none;" onClick="nextError();" value=">>"></form></div>'
        print "<p class='info'>Found <a name=\"errorsummary\" href=\"#error0\">" + str(self.numErrs) + "</a> errors.</p>"
        print '</div>' # watchdocument errors
        #print "<!--"
        
        
    
    def finishRun(self,m,line):
        print '<p class="info">'
        print line
        print '</p>'
        self.done = True
        self.summary()


class ParseLatexMk(TexParser):
    """docstring for ParseLatexMk"""
    def __init__(self, input_stream, verbose,filename):
        super(ParseLatexMk, self).__init__(input_stream,verbose)
        self.fileName = filename
        self.patterns += [
            (re.compile('This is (pdfTeX|latex2e|latex|XeTeX)') , self.startLatex),
            (re.compile('This is BibTeX') , self.startBibtex),
            (re.compile('^Latexmk: All targets \(.*?\) are up-to-date') , self.finishRun),
            (re.compile('This is makeindex') , self.startBibtex),
            (re.compile('^Latexmk') , self.ltxmk),
            (re.compile('Run number') , self.newRun)
        ]
        self.numRuns = 0
    
    def startBibtex(self,m,line):
        print '<div class="bibtex">'
        print '<h3>' + line[:-1] + '</h3>'
        bp = BibTexParser(self.input_stream,self.verbose)
        f,e,w = bp.parseStream()
        self.numErrs += e
        self.numWarns += w

    def startLatex(self,m,line):
        print '<div class="latex">'
        print '<hr>'
        print '<h3>' + line[:-1] + '</h3>'
        bp = LaTexParser(self.input_stream,self.verbose,self.fileName)
        f,e,w = bp.parseStream()
        self.numErrs += e
        self.numWarns += w

    def newRun(self,m,line):
        if self.numRuns > 0:
            print '<hr />'
            print '<p>', self.numErrs, 'Errors', self.numWarns, 'Warnings', 'in this run.', '</p>'
        self.numWarns = 0
        self.numErrs = 0
        self.numRuns += 1

    def finishRun(self,m,line):
        self.ltxmk(m,line)
        self.done = True

    def ltxmk(self,m,line):
        print '<p class="ltxmk">%s</p>'%line

class ChkTeXParser(TexParser):
    """Parse the output from chktex"""
    def __init__(self, input_stream, verbose, filename):
        super(ChkTeXParser, self).__init__(input_stream,verbose)
        self.fileName = filename
        self.patterns += [
            (re.compile('^ChkTeX') , self.info),
            (re.compile('Warning \d+ in (.*.tex) line (\d+):(.*)') , self.handleWarning),
            (re.compile('Error \d+ in (.*.tex) line (\d+):(.*)') , self.handleError),
        ]
        self.numRuns = 0

    def handleWarning(self,m,line):
        """Display warning. match m should contain file, line, warning message"""
        print '<p class="warning">Warning: <a href="' + make_link(os.path.join(os.getcwd(), m.group(1)),m.group(2)) + '">' + m.group(1)+ ": "+m.group(2)+":</a>"+m.group(3)+"</p>"
        warnDetail = self.input_stream.readline()
        if len(warnDetail) > 2:
            print '<pre>',warnDetail[:-1]
            print self.input_stream.readline()[:-1], '</pre>'
        self.numWarns += 1

    def handleError(self,m,line):
        print '<p class="error">'
        print 'Error: <a  href="' + make_link(os.path.join(os.getcwd(),m.group(1)),m.group(2)) +  '">' + m.group(1)+":"+m.group(2) + ':</a> '+m.group(3)+'</p>'
        print '<pre>', self.input_stream.readline()[:-1]
        print self.input_stream.readline()[:-1], '</pre>'
        self.numErrs += 1

if __name__ == '__main__':
    # test
    #stream = open('../tex/test.log')
    stream = open(sys.argv[1])
    lp = WatchDocumentParser(stream,False,sys.argv[2])
    f,e,w = lp.parseStream()
    #exit(5)
    

