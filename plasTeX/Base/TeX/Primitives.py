#!/usr/bin/env python

import codecs
from plasTeX.Tokenizer import Token, EscapeSequence
from plasTeX import Command, Environment, CountCommand
from plasTeX import IgnoreCommand, sourceChildren
from plasTeX.Logging import getLogger
from plasTeX.DOM import Node
import plasTeX

log = getLogger()
status = getLogger('status')
deflog = getLogger('parse.definitions')
envlog = getLogger('parse.environments')
mathshiftlog = getLogger('parse.mathshift')

class relax(Command):
    pass

class protect(Command):
    pass

class global_(Command):
    macroName = 'global'

class par(Command):
    """ Paragraph """
    level = Command.PAR_LEVEL

    def invoke(self, tex):
        status.dot()

    @property
    def source(self): 
        if self.hasChildNodes():
            return '%s\n\n' % sourceChildren(self)
        return '\n\n'

    def digest(self, tokens):
        status.dot()

    @property
    def isElementContentWhitespace(self):
        if not self.hasChildNodes():
            return True
        return False

class BoxCommand(Command):
    """ Base class for box-type commands """
    args = 'self'
    mathMode = False
    def parse(self, tex):
        MathShift.inEnv.append(None)
        Command.parse(self, tex) 
        MathShift.inEnv.pop()
        return self.attributes

class hbox(BoxCommand): pass
class vbox(BoxCommand): pass

class MathShift(Command):
    """ 
    The '$' character in TeX

    This macro detects whether this is a '$' or '$$' grouping.  If 
    it is the former, a 'math' environment is invoked.  If it is 
    the latter, a 'displaymath' environment is invoked.

    """
    macroName = 'active::$'
    inEnv = []

    def invoke(self, tex):
        """
        This gets a bit tricky because we need to keep track of both 
        our beginning and ending.  We also have to take into 
        account \mbox{}es.

        """
        inEnv = type(self).inEnv
        math = self.ownerDocument.createElement('math')
        displaymath = self.ownerDocument.createElement('displaymath')

        # See if this is the end of the environment
        if inEnv and inEnv[-1] is not None:
            env = inEnv.pop()
            if type(env) is type(displaymath):
                for t in tex.itertokens():
                    break
                displaymath.macroMode = Command.MODE_END
                self.ownerDocument.context.pop(displaymath)
                return [displaymath]
            else:
                math.macroMode = Command.MODE_END
                self.ownerDocument.context.pop(math)
                return [math]

        for t in tex.itertokens():
            if t.catcode == Token.CC_MATHSHIFT:
                inEnv.append(displaymath)
            else:
                inEnv.append(math)
                tex.pushToken(t)
            break

        current = inEnv[-1]
        mathshiftlog.debug('%s (%s)' % (current.tagName, id(current)))
        self.ownerDocument.context.push(current)

        return [current]

class AlignmentChar(Command):
    """ The '&' character in TeX """
    macroName = 'active::&'

class SuperScript(Command):
    """ The '^' character in TeX """
    macroName = 'active::^'
    args = 'self'
    def invoke(self, tex):
        # If we're not in math mode, just treat this as a normal character
        if not self.ownerDocument.context.isMathMode:
            return tex.textTokens('^')
        Command.parse(self, tex)

class SubScript(Command):
    """ The '_' character in TeX """
    macroName = 'active::_'
    args = 'self'
    def invoke(self, tex):
        # If we're not in math mode, just treat this as a normal character
        if not self.ownerDocument.context.isMathMode:
            return tex.textTokens('_')
        Command.parse(self, tex)

class DefCommand(Command):
    """ TeX's \\def command """
    local = True
    args = 'name:Tok args:Args definition:nox'
    def invoke(self, tex):
        self.parse(tex)
        a = self.attributes
        deflog.debug('def %s %s %s', a['name'], a['args'], a['definition'])
        self.ownerDocument.context.newdef(a['name'], a['args'], a['definition'], local=self.local)

class def_(DefCommand): 
    macroName = 'def'

class edef(DefCommand):
    local = True

class xdef(DefCommand):
    local = False

class gdef(DefCommand):
    local = False

class IfCommand(Command):
    pass

class if_(IfCommand): 
    """ \\if """
    args = 'a:Tok b:Tok'
    macroName = 'if'
    """ Test if character codes agree """
    def invoke(self, tex):
        self.parse(tex)
        a = self.attributes
        return tex.readIfContent(a['a'] == a['b'])

class else_(Command):
    macroName = 'else'

class fi(Command): 
    pass
        
class ifnum(IfCommand):
    """ Compare two integers """
    args = 'a:Number rel:Tok b:Number'
    def invoke(self, tex):
        self.parse(tex)
        attrs = self.attributes
        relation = attrs['rel']
        a, b = attrs['a'], attrs['b']
        if relation == '<':
            return tex.readIfContent(a < b)
        elif relation == '>':
            return tex.readIfContent(a > b)
        elif relation == '=':
            return tex.readIfContent(a == b)
        raise ValueError, '"%s" is not a valid relation' % relation

class ifdim(IfCommand):
    """ Compare two dimensions """
    args = 'a:Dimen rel:Tok b:Dimen'
    def invoke(self, tex):
        self.parse(tex)
        attrs = self.attributes
        relation = attrs['rel']
        a, b = attrs['a'], attrs['b']
        if relation == '<':
            return tex.readIfContent(a < b)
        elif relation == '>':
            return tex.readIfContent(a > b)
        elif relation == '=':
            return tex.readIfContent(a == b)
        raise ValueError, '"%s" is not a valid relation' % relation

class ifodd(IfCommand):
    """ Test for odd integer """   
    args = 'value:Number'
    def invoke(self, tex):
        self.parse(tex)
        return tex.readIfContent(not(not(self.attributes['value'] % 2)))

class ifeven(IfCommand):
    """ Test for even integer """
    args = 'value:Number'
    def invoke(self, tex):
        self.parse(tex)
        return tex.readIfContent(not(self.attributes['value'] % 2))

class ifvmode(IfCommand):
    """ Test for vertical mode """
    def invoke(self, tex):
        self.parse(tex)
        return tex.readIfContent(False)

class ifhmode(IfCommand):
    """ Test for horizontal mode """
    def invoke(self, tex):
        self.parse(tex)
        return tex.readIfContent(True)

class ifmmode(IfCommand):
    """ Test for math mode """
    def invoke(self, tex):
        self.parse(tex)
        return tex.readIfContent(self.ownerDocument.context.isMathMode)

class ifinner(IfCommand):
    """ Test for internal mode """
    def invoke(self, tex):
        return tex.readIfContent(False)

class ifcat(IfCommand):
    """ Test if category codes agree """
    args = 'a:Tok b:Tok'
    def invoke(self, tex):
        self.parse(tex)
        a = self.attributes
        return tex.readIfContent(a['a'].catcode == a['b'].catcode)

class ifx(IfCommand):
    """ Test if tokens agree """
    args = 'a:XTok b:XTok'
    def invoke(self, tex):
        self.parse(tex)
        a = self.attributes
        return tex.readIfContent(a['a'] == a['b'])

class ifvoid(IfCommand):
    """ Test a box register """
    args = 'value:Number'
    def invoke(self, tex):
        self.parse(tex)
        return tex.readIfContent(False)

class ifhbox(IfCommand):
    """ Test a box register """
    args = 'value:Number'
    def invoke(self, tex):
        self.parse(tex)
        return tex.readIfContent(False)

class ifvbox(IfCommand):
    """ Test a box register """
    args = 'value:Number'
    def invoke(self, tex):
        self.parse(tex)
        return tex.readIfContent(False)

class ifeof(IfCommand):
    """ Test for end of file """
    args = 'value:Number'
    def invoke(self, tex):
        self.parse(tex)
        return tex.readIfContent(False)

class iftrue(IfCommand):
    """ Always true """
    def invoke(self, tex):
        self.parse(tex)
        return tex.readIfContent(True)

class ifplastex(iftrue): pass
class plastexfalse(Command): pass
class plastextrue(Command): pass

class ifhtml(iftrue): pass
class htmlfalse(Command): pass
class htmltrue(Command): pass

class iffalse(IfCommand):
    """ Always false """
    def invoke(self, tex):
        return tex.readIfContent(False)

class ifpdf(iffalse): pass
class pdffalse(Command): pass
class pdftrue(Command): pass
#class pdfoutput(Command): pass

class ifcase(IfCommand):
    """ Cases """
    args = 'value:Number'
    def invoke(self, tex):
        return tex.readIfContent(self.parse(tex)['value'])


class let(Command):
    """ \\let """
    args = 'name:Tok = value:Tok'
    def invoke(self, tex):
        a = self.parse(tex)
        self.ownerDocument.context.let(a['name'], a['value'])

class char(Command):
    """ \\char """
    args = 'char:Number'
    def invoke(self, tex):
        return tex.textTokens(chr(self.parse(tex)['char']))

class chardef(Command):
    args = 'command:cs = num:Number'
    def invoke(self, tex):
        a = self.parse(tex)
        self.ownerDocument.context.chardef(a['command'], a['num'])
      
class NameDef(Command):
    macroName = '@namedef'
    args = 'name:str value:nox'

class makeatletter(Command):
    def invoke(self, tex):
        self.ownerDocument.context.catcode('@', Token.CC_LETTER)

class everypar(Command):
    args = 'tokens:nox'

class catcode(Command):
    """ \\catcode """
    args = 'char:Number = code:Number'
    def invoke(self, tex):
        a = self.parse(tex)
        self.ownerDocument.context.catcode(chr(a['char']), a['code'])
    def source(self):
        return '\\catcode`\%s=%s' % (chr(self.attributes['char']), 
                                     self.attributes['code'])
    source = property(source)

class csname(Command):
    """ \\csname """
    def invoke(self, tex):
        name = []
        for t in tex:
            if t.nodeType == Command.ELEMENT_NODE and t.nodeName == 'endcsname':
                break
            name.append(t)
        return [EscapeSequence(''.join(name))]

class endcsname(Command): 
    """ \\endcsname """
    pass

class input(Command):
    """ \\input """
    args = 'name:str'
    def invoke(self, tex):
        a = self.parse(tex)
        try: 
            path = tex.kpsewhich(a['name'])

            status.info(' ( %s ' % path)
            encoding = self.config['files']['input-encoding']
            tex.input(codecs.open(path, 'r', encoding, 'replace'))
            status.info(' ) ')

        except (OSError, IOError), msg:
            log.warning(msg)
            status.info(' ) ')

class endinput(Command):
    def invoke(self, tex):
        tex.endInput()

class include(input):
    """ \\include """

class showthe(Command):
    args = 'arg:cs'
    def invoke(self, tex):
        log.info(self.ownerDocument.createElement(self.parse(tex)['arg']).the())


class active(CountCommand):
    value = CountCommand.new(13)

class advance(Command):
    def invoke(self, tex):
        tex.readArgument(type='Number')
        tex.readKeyword(['by'])
        tex.readArgument(type='Number')

class leavevmode(Command): pass

class kern(Command): pass

class hrule(Command): pass

class jobname(Command):
    def invoke(self, tex):
        self.unicode = tex.jobname

class long(Command): pass

class undefined(Command): pass

class undefined_(Command):
    macroName = '@undefined'

class vobeyspaces_(Command):
    macroName = '@vobeyspaces'

class noligs_(Command):
    macroName = '@noligs'

class expandafter(Command):
    def invoke(self, tex):
        nexttok = None
        for tok in tex.itertokens():
            nextok = tok
            break
        for tok in tex:
            aftertok = tok
            break
        tex.pushToken(aftertok)
        tex.pushToken(nexttok)
        return []

class vskip(Command):
    args = 'size:Dimen'

class hskip(Command):
    args = 'size:Dimen'

class openout(Command):
    args = 'arg:cs = value:any'
    def invoke(self, tex):
        result = Command.invoke(self, tex)
#       a = self.attributes
#       self.ownerDocument.context.newwrite(a['arg'].nodeName, 
#                                           a['value'].textContent)
        return result

class closeout(Command):
    args = 'arg:cs'
    def invoke(self, tex):
        result = Command.invoke(self, tex)
#       a = self.attributes
#       self.ownerDocument.context.writes[a['arg'].nodeName].close()
        return result

class write(Command):
    args = 'arg:cs text:nox'
    def invoke(self, tex):
        result = Command.invoke(self, tex)
#       a = self.attributes
#       self.ownerDocument.context.writes[a['arg'].nodeName].write(self.attributes['text']+'\n')
        return result

class protected_write(write):
    nodeName = 'protected@write'

class hfil(Command):
    pass

class over(Command):
    def digest(self, tokens):
        nodes = self.parentNode.childNodes
        self.attributes['numer'] = self.ownerDocument.createDocumentFragment()
        while nodes:
            self.attributes['numer'].insert(0, nodes.pop())
        self.attributes['denom'] = self.ownerDocument.createDocumentFragment()
        for item in tokens:
            if item.level < self.level:
                tokens.push(item)
                break
            if item.nodeType == Node.ELEMENT_NODE:
                item.parentNode = self
                item.digest(tokens)
            if isinstance(item, plasTeX.Base.egroup):
                tokens.push(item)
                
                break
            self.attributes['denom'].appendChild(item)
            
