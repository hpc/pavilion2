####################################################################
#
#  Disclaimer and Notice of Copyright
#  ==================================
#
#  Copyright (c) 2015, Los Alamos National Security, LLC
#  All rights reserved.
#
#  Copyright 2015. Los Alamos National Security, LLC.
#  This software was produced under U.S. Government contract
#  DE-AC52-06NA25396 for Los Alamos National Laboratory (LANL),
#  which is operated by Los Alamos National Security, LLC for
#  the U.S. Department of Energy. The U.S. Government has rights
#  to use, reproduce, and distribute this software.  NEITHER
#  THE GOVERNMENT NOR LOS ALAMOS NATIONAL SECURITY, LLC MAKES
#  ANY WARRANTY, EXPRESS OR IMPLIED, OR ASSUMES ANY LIABILITY
#  FOR THE USE OF THIS SOFTWARE.  If software is modified to
#  produce derivative works, such modified software should be
#  clearly marked, so as not to confuse it with the version
#  available from LANL.
#
#  Additionally, redistribution and use in source and binary
#  forms, with or without modification, are permitted provided
#  that the following conditions are met:
#  -  Redistributions of source code must retain the
#     above copyright notice, this list of conditions
#     and the following disclaimer.
#  -  Redistributions in binary form must reproduce the
#     above copyright notice, this list of conditions
#     and the following disclaimer in the documentation
#     and/or other materials provided with the distribution.
#  -  Neither the name of Los Alamos National Security, LLC,
#     Los Alamos National Laboratory, LANL, the U.S. Government,
#     nor the names of its contributors may be used to endorse
#     or promote products derived from this software without
#     specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY LOS ALAMOS NATIONAL SECURITY, LLC
#  AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,
#  INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
#  MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
#  IN NO EVENT SHALL LOS ALAMOS NATIONAL SECURITY, LLC OR CONTRIBUTORS
#  BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY,
#  OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
#  PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA,
#  OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
#  THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR
#  TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT
#  OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY
#  OF SUCH DAMAGE.
#
#  ###################################################################

# The module file contains the functions and classes needed for parsing
# strings and performing variable insertion in pavilion configurations.
#
# While we don't use a context free grammer for parsing, it is convenient for
# describing the format:

# # pav strings can contain variable references, escapes, or sub strings.
# PAV_STR  -> TEXT | TEXT VAR PAV_STR | TEXT ESC PAV_STR | TEXT SUB_STR PAV_STR
# # Text is anything that doesn't start an escape, sub string, or variable reference
# # It may also be an empty string.
# TEXT     -> [^\{[]*
# # Variable references are a bracket surrounded variable name. These can consist
# # of a var_set name, variable name, variable index, and sub-variable name. All but the
# # variable name are optional.
# VAR      -> {VAR_KEY}
# VAR_KEY  -> VAR_BASE | VAR_BASE.VAR_IDX | VAR_BASE.VAR_ID | VAR_BASE.VAR_IDX.VAR_ID
# VAR_BASE -> VAR_ID | VAR_ID.VAR_ID
# VAR_ID   -> [a-z][a-z0-9_-]+
# VAR_IDX  -> [0-9]+
# #
# ESCAPE   -> \.
# # A substring is a pav string surrounded by squared brackets. It's used to
# # denote an area that can be copied as a unit when used with multi-valued variables.
# SUB_STR  -> [PAV_STR] | [PAV_STR:SEP]
# SEP      -> .

import re
import variables


class ScanError(ValueError):
    """Error scanning and tokenizing a Pav string."""
    def __init__(self, message, error_start, error_end):
        self.message = message
        self.error_start = error_start
        self.error_end = error_end


class ParseError(ScanError):
    """Error parsing the Pav string tokens"""


class ResolveError(ValueError):
    """Error resolving string variables."""


def parse(string):
    tokens = tokenize(string)

    print('tokenized:', tokens)

    return PavString(tokens)


TEXT_END_RE = re.compile(r'\[|\\|{|}|(:.)?\]')


def tokenize(string):
    tokens = [TextToken('', 0, 0)]

    pos = 0

    while pos < len(string):

        # Grab everything that isn't a special char.
        match = TEXT_END_RE.search(string, pos)
        if match is None:
            # The text went to the end of the string.
            tokens.append(TextToken(string[pos:], pos, len(string)))
            break
        else:
            # Grab the text we found, even if it's empty.
            end = match.start()
            if end != pos:
                tokens.append(TextToken(string[pos:end], pos, end))
            pos = end

        end_str = match.group()
        print(pos, end, end_str)

        # Process the non-text token (in most cases) that follows.
        if end_str == '[':
            tokens.append(SubStringStartToken(pos, pos+1))
            pos += 1
        elif end_str.endswith(']'):

            if len(end_str) == 3:
                separator = end_str[1]
            else:
                separator = ''

            tokens.append(SubStringEndToken(pos, pos+1, separator))
            pos += len(end_str)

        elif end_str == '{':
            var_end = string.find('}', pos)
            if var_end == -1:
                error_end = string.find(' ', pos)
                if error_end == -1:
                    error_end = len(string)
                raise ScanError("Variable escape missing closing bracket '}'", pos - 1, error_end)

            var_name = string[pos+1:var_end]

            # Use the variable manager to parse the key and check for validity.
            try:
                variables.VariableSetManager.parse_key(var_name)
            except KeyError as err:
                raise ScanError("Invalid variable name '{}': {}."
                                .format(var_name, err), pos, var_end)

            tokens.append(VariableToken(var_name, pos, var_end))
            pos = var_end + 1

        elif end_str == '}':
            raise ScanError("Extra variable close bracket '}'", pos, pos + 1)
        elif end_str == '\\':
            if pos + 1 >= len(string):
                raise ScanError("Escape character '\\' at end of string.", pos, pos + 1)
            tokens.append(TextToken(string[pos + 1], pos, pos+2))
            pos += 2
        else:
            print(end_str)
            raise ScanError("Unknown scanning error at character {}.".format(end_str), pos, pos + 1)

    return tokens


class Token(object):
    def __init__(self, start, end):
        """Scan the string starting at pos to find the end of this token. Save the matching
        part, start and end. These type of token may be empty.
        :param int start:
        :param int end:
        """

        self.start = start
        self.end = end
        self.next_token = None

    def resolve(self, var_man):
        """Resolve any variables in this token using the variable manager.
        :param var_man: A variable manager with the needed variables.
        :return: The resolved string.
        """

        raise NotImplementedError

    def __repr__(self):
        return "{}".format(self.__class__.__name__)


class PavString(Token):
    """Provides a tokenized representation of a pavilion string, including summary information
    about variables used, etc. It is itself the root token of the parse tree."""

    def __init__(self, tokens, is_substr=False):
        """
        Tokenize the given pav_string.
        :param list tokens:
        """

        super(PavString, self).__init__(0, 0)

        self.next_token = None
        self._separator = ''

        self._root = self._parse(tokens, is_substr)

    def _parse(self, tokens, is_substr):
        """Create a parse tree from the given tokens."""

        root = tokens.pop(0)
        self.start = root.start
        last_token = root

        while tokens:
            token = tokens.pop(0)

            if isinstance(token, SubStringStartToken):
                # Start a new PavString if we're dropping into a sub string.
                token = PavString(tokens)
                last_token.next_token = token
                # The we're consuming tokens from the list as we parse, so what's left is
                # what was outside the sub string.
            elif isinstance(token, SubStringEndToken):
                # This is the end of the substring. If it was followed by a space, make
                # sure to note that.
                self.end = token.end
                self._separator = token.separator
                return root
            else:
                # Add any other token to our PavString token list.
                last_token.next_token = token

            last_token = token

        # Only in the top level PavStr, which isn't a sub string, should this be reached.
        if is_substr:
            raise ParseError("""Sub string missing closing bracket ']'.""", self.start,
                             last_token.end)

        self.end = last_token.end

        return root

    @property
    def variables(self):
        token = self._root

        var_set = set()

        while token:
            if isinstance(token, VariableToken):
                var_set.add(token.var)
            elif isinstance(token, PavString):
                var_set.union(token.variables)

            token = token.next_token

        return var_set

    def get_substr_vars(self, var_man, iter_vars):
        """
        :param variables.VariableSetManager var_man:
        :param dict iter_vars:
        :return:
        """

        token = self._root

        local_iter_vars = set()

        while token:
            if isinstance(token, VariableToken):
                var_set, var, idx, subvar = var_man.resolve_key(token.var)

                if idx is None and var_man.len(var_set, var) > 1:
                    local_iter_vars.add((var_set, var))

            token = token.next_token

        return sorted(local_iter_vars)

    def resolve(self, var_man, iter_vars=None):
        """
        :param variables.VariableSetManager var_man:
        :param dict iter_vars:
        :return:
        """

        if iter_vars is None:
            iter_vars = dict()

        token = self._root

        parts = []

        while token:
            if isinstance(token, TextToken):
                print('token: ', token.text)
                parts.append(token.text)
            elif isinstance(token, VariableToken):
                print('token: ', token.var)
                var_set, var, idx, sub_var = var_man.resolve_key(token.var)

                if (var_set, var) in iter_vars and idx is None:
                    # Resolve the substr var by the given index.
                    parts.append(token.resolve(var_man, index=iter_vars[(var_set, var)]))
                else:
                    # A single valued var, or one referenced directly by index.
                    parts.append(token.resolve(var_man))

            elif isinstance(token, PavString):
                print('token: substr')
                # We have a substring to resolve.

                local_iter_vars = token.get_substr_vars(var_man, iter_vars)

                # This holds the current index for each var we're looping over.
                iter_vars = iter_vars.copy()
                # This holds the max iterations for each of those vars.
                local_iter_vars_max = dict()
                for iter_var in local_iter_vars:
                    local_iter_vars_max[iter_var] = var_man.len(*iter_var)
                    iter_vars[iter_var] = 0

                done = False

                # Now loop over all our local iter vars in sorted order (they needed to be in
                # some consistent order).
                while not done:
                    part = token.resolve(var_man, iter_vars)
                    parts.append(part)

                    # If there aren't any local iter vars, we're done now.
                    if not local_iter_vars:
                        break

                    # We're going to increment through the local, multi-valued vars in our
                    # substring. After incrementing a var index, if that index exceeds the number
                    #  of items for that var, we reset that value and increment the next local var.
                    # If we increment all the way through all the local vars, we're 'done'.
                    inc_idx = 0
                    # Grab the first var to increment the index of, and do so.
                    iter_var = local_iter_vars[inc_idx]
                    iter_vars[iter_var] += 1

                    # Keep incrementing var indexs until we hit one that isn't over it's limit.
                    # This will cycle through all index combinations.
                    while iter_vars[iter_var] >= local_iter_vars_max[iter_var]:
                        # Reset this var, and switch to the next.
                        iter_vars[iter_var] = 0
                        inc_idx += 1

                        # If there isn't a next one, we're done.
                        if inc_idx >= len(local_iter_vars):
                            done = True
                            break
                        else:
                            # Otherwise, grab the next and increment it.
                            iter_var = local_iter_vars[inc_idx]
                            iter_vars[iter_var] += 1

                    # Only add the separator between values.
                    if not done and token._separator:
                        parts.append(token._separator)

            else:
                raise ResolveError("Unknown token of type '{}' to resolve.".format(type(token)))

            token = token.next_token

        print('parts', parts)
        return ''.join(parts)


class TextToken(Token):
    """A plaintext token."""

    def __init__(self, text, start, end):
        self.text = text

        super(TextToken, self).__init__(start, end)

    def resolve(self, var_man):
        """Resolve any variables in this token using the variable manager.
        :param var_man: A variable manager with the needed variables.
        :return: The resolved string.
        """

        return self.text

    def __repr__(self):
        return "{}('{}')".format(self.__class__.__name__, self.text)


class VariableToken(Token):
    def __init__(self, var, start, end):
        super(VariableToken, self).__init__(start, end)

        self.var = var

    def resolve(self, var_man, index=None):
        """Resolve any variables in this token using the variable manager.
        :param variables.VariableSetManager var_man:
        :param int index: The index to force for this variable, when it's being iterated over.
        :return:
        """

        var_set, var, idx, subvar = var_man.resolve_key(self.var)

        if index is not None:
            idx = index

        return var_man[(var_set, var, idx, subvar)]

    def __repr__(self):
        return "{}('{}')".format(self.__class__.__name__, self.var)


class SubStringStartToken(Token):
    """The start of a sub string section."""

    def resolve(self, var_man):
        raise RuntimeError("This token should never be resolved. They should be replaced with "
                           "PavString tokens.")


class SubStringEndToken(Token):
    """The end of a sub string section."""

    def __init__(self, start, end, separator):
        super(SubStringEndToken, self).__init__(start, end)

        self.separator = separator

    def resolve(self, var_man):
        raise RuntimeError("This token should never be resolved. They should be replaced with "
                           "PavString tokens.")
