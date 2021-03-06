#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import configparser  # backported configparser from python3
import collections

# from http://stackoverflow.com/questions/13921323/handling-duplicate-keys-with-configparser
# TODO: the errors raised do not exist
class ConfigParserMultiOpt(configparser.RawConfigParser):
    """ConfigParser allowing duplicate keys. Values are stored in a list"""

    def __init__(self):
        configparser.RawConfigParser.__init__(self, empty_lines_in_values=False, strict=False)

    def _read(self, fp, fpname):
        """Parse a sectioned configuration file.

        Each section in a configuration file contains a header, indicated by
        a name in square brackets (`[]'), plus key/value options, indicated by
        `name' and `value' delimited with a specific substring (`=' or `:' by
        default).

        Values can span multiple lines, as long as they are indented deeper
        than the first line of the value. Depending on the parser's mode, blank
        lines may be treated as parts of multiline values or ignored.

        Configuration files may include comments, prefixed by specific
        characters (`#' and `;' by default). Comments may appear on their own
        in an otherwise empty line or may be entered in lines holding values or
        section names.
        """
        elements_added = set()
        cursect = None                        # None, or a dictionary
        sectname = None
        optname = None
        lineno = 0
        indent_level = 0
        e = None                              # None, or an exception
        for lineno, line in enumerate(fp, start=1):
            comment_start = None
            # strip inline comments
            for prefix in self._inline_comment_prefixes:
                index = line.find(prefix)
                if index == 0 or (index > 0 and line[index-1].isspace()):
                    comment_start = index
                    break
            # strip full line comments
            for prefix in self._comment_prefixes:
                if line.strip().startswith(prefix):
                    comment_start = 0
                    break
            value = line[:comment_start].strip()
            if not value:
                if self._empty_lines_in_values:
                    # add empty line to the value, but only if there was no
                    # comment on the line
                    if (comment_start is None and
                                cursect is not None and
                            optname and
                                cursect[optname] is not None):
                        cursect[optname].append('') # newlines added at join
                else:
                    # empty line marks end of value
                    indent_level = sys.maxsize
                continue
            # continuation line?
            first_nonspace = self.NONSPACECRE.search(line)
            cur_indent_level = first_nonspace.start() if first_nonspace else 0
            if (cursect is not None and optname and
                        cur_indent_level > indent_level):
                cursect[optname].append(value)
            # a section header or option header?
            else:
                indent_level = cur_indent_level
                # is it a section header?
                mo = self.SECTCRE.match(value)
                if mo:
                    sectname = mo.group('header')
                    if sectname in self._sections:
                        if self._strict and sectname in elements_added:
                            raise DuplicateSectionError(sectname, fpname,
                                                        lineno)
                        cursect = self._sections[sectname]
                        elements_added.add(sectname)
                    elif sectname == self.default_section:
                        cursect = self._defaults
                    else:
                        cursect = self._dict()
                        self._sections[sectname] = cursect
                        self._proxies[sectname] = configparser.SectionProxy(self, sectname)
                        elements_added.add(sectname)
                    # So sections can't start with a continuation line
                    optname = None
                # no section header in the file?
                elif cursect is None:
                    raise MissingSectionHeaderError(fpname, lineno, line)
                # an option line?
                else:
                    mo = self._optcre.match(value)
                    if mo:
                        optname, vi, optval = mo.group('option', 'vi', 'value')
                        if not optname:
                            e = self._handle_error(e, fpname, lineno, line)
                        optname = self.optionxform(optname.rstrip())
                        if (self._strict and
                                    (sectname, optname) in elements_added):
                            raise configparser.DuplicateOptionError(sectname, optname, fpname, lineno)
                        elements_added.add((sectname, optname))
                        # This check is fine because the OPTCRE cannot
                        # match if it would set optval to None
                        if optval is not None:
                            optval = optval.strip()
                            # Check if this optname already exists
                            if (optname in cursect) and (cursect[optname] is not None):
                                # If it does, convert it to a tuple if it isn't already one
                                if not isinstance(cursect[optname], tuple):
                                    cursect[optname] = tuple(cursect[optname])
                                cursect[optname] = cursect[optname] + tuple([optval])
                            else:
                                cursect[optname] = [optval]
                        else:
                            # valueless option handling
                            cursect[optname] = None
                    else:
                        # a non-fatal parsing error occurred. set up the
                        # exception but keep going. the exception will be
                        # raised at the end of the file and will contain a
                        # list of all bogus lines
                        e = self._handle_error(e, fpname, lineno, line)
        # if any parsing errors occurred, raise an exception
        if e:
            raise e
        self._join_multiline_values()



def get_section_values(section, config):
    config_dict = {}
    for parser in section:
        # print '{0}'.format(parser)
        method_dict = collections.OrderedDict()
        for method in config.options(parser):
            # print '\t{0}'.format(method)
            options = config.get(parser, method)
            method_dict[str(method)] = []
            # our modified ConfigParser returns duplicates as tuples, let's break them out
            option_list = []
            if type(options) == tuple:
                for option in options:
                    # print '\t\t{0}'.format(option)
                    option_list.append(str(option))
            else:
                # print '\t\t{0}'.format(options)
                option_list.append(str(options))
            method_dict[str(method)] = option_list
        config_dict[str(parser)] = method_dict
    return config_dict


def get_config():
    config = ConfigParserMultiOpt()
    config.read('/export/home/sysjgm/pythonProjects/enrichment2.0/jared.conf')
    sections =  config.sections()

    reserved_sections = ['default', 'all']  # we don't want these to be included with our subparsers

    default = [parser for parser in sections if parser == 'default']
    all_events = [parser for parser in sections if parser == 'all']
    subparsers = [parser for parser in sections if parser not in reserved_sections]

    default_dict = get_section_values(default, config)
    all_events_dict = get_section_values(all_events, config)
    subparsers_dict = get_section_values(subparsers, config)

    return [default_dict, all_events_dict, subparsers_dict]
