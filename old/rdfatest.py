#!/usr/bin/env python
# encoding: utf-8
"""
untitled.py

Created by Martin Hepp on 2009-10-27.
Copyright (c) 2009 Universität der Bundeswehr. All rights reserved.
"""

import sys
import os
from rdflib.syntax.parsers.RDFaParser import RDFaParser
from rdflib.Graph import Graph
import pyRdfa
from pyRdfa import processURI, Options

#uri = 'http://www.ebusiness-unibw.org/wiki/GoodRelationsRDFaInMediaWikiProduct'
#uri2 = "http://www.heppnetz.de/"
uri = 'http://www.hepp.de/'

g = Graph()
rdfa = processURI(uri, outputFormat='rdf/xml', form={'lax':False})
print rdfa

g.parse("http://www.heppnetz.de/", format="rdfa")
print len(g)

for statement in g:
	print statement
#rdflib.syntax.parsers.RDFaParser


