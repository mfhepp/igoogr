#!/usr/bin/env python
# encoding: utf-8
"""
main.py

iGooGr - Imagine Google was using GoodRelations

A project of the E-Business and Web Science Research Group, Universität der Bundeswehr München,
http://www.unibw.de/ebusiness/
Written by Martin Hepp, mhepp@computer.org on Oct 26-29, 2009.

Submission for the ISWC 2009 Linked Data-a-thon competition.

This software is free software under the LPGL.
"""

# TBD / Open issues
# check, why “Who sells cell phones and on which Web pages can I get more information on respective offerings?” causes error (likely strange quotation marks)
# - Order opening hours by day of week
# - Catch errors; be more tolerant to markup and network performance
# - Parallelize fetching pages in individual threads

import os
import urllib2
import urllib
import html5lib
import httpheader
from StringIO import StringIO

import wsgiref.handlers
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
import logging
from django.utils import simplejson 

from rdflib import *
from rdflib import Graph
from rdflib import RDF

URI = 'http://ajax.googleapis.com/ajax/services/search/web?v=1.0&q='
REFERER = 'http://igoogr.appspot.com/'
GRNS = "http://purl.org/goodrelations/v1#"
RDFSNS = 'http://www.w3.org/2000/01/rdf-schema#'
PYRDFA_URI = 'http://www.w3.org/2007/08/pyRdfa/extract?uri=%s&format=pretty-xml&warnings=false&parser=lax&space-preserve=false&submit=Go!&text='
ODE_URI = 'http://linkeddata.uriburner.com/ode/?uri=%s'

# FUTURE: ODE_URI = 'http://linkeddata.uriburner.com/about/html/http://linkeddata.uriburner.com/about/id/http/www.heppnetz.de/searchmonkey/company.html%01business

SIGMA_URI = 'http://sindice.com/developers/inspector/?url=%s#graph'

class Result:
	'''A class for results'''
	def __init__(self,uri="",title="",abstract="",dispuri="",price="",payments="",opening="",hasGR=False,hasRDF=False,pyrdfa="",ode ="",sigma="",format=""):
		self.uri = uri
		self.title = title
		self.abstract = abstract
		self.dispuri = dispuri
		self.price = price
		self.payments = payments
		self.opening = opening
		self.hasGR = hasGR
		self.hasRDF = hasRDF
		self.pyrdfa = pyrdfa
		self.ode = ode
		self.sigma = sigma
		self.format = format

class MainHandler(webapp.RequestHandler):
	"""
	MainHandler: Class for http://igoogr.appspot.com/
	"""
	
	def get(self):
		"""get(self)
		Handler for http GET - processes query string
		"""
		GR = Namespace(GRNS)
		RDFS = Namespace(RDFSNS)
		
		res = []
		format = ""
		
		query = self.request.get('q')
		
		# If query nonempty, fetch list of URIs	
		if query != "":
			logging.info("QUERY: %s" % query)		
			query2 = urllib.quote_plus(query)
			request = urllib2.Request(URI+query2, None, {'Referer': REFERER})
			response = urllib2.urlopen(request)

			results = simplejson.load(response)
			results = results['responseData']
			if str(results) != "":
				results = results['results']
			else:
				results = []
			# Create graph for GoodRelations, because we need the labels etc.
			grgraph = Graph()
			grgraph.parse('http://www.heppnetz.de/ontologies/goodrelations/v1.owl') 

			# For each URI: fetch page, extract RDFa, parse RDF, extract GoodRelations, translate into text
			for item in results:
				if item['url'] == 'http://igoogr.appspot.com/': # skip the igoogr main page, which can also be among the search results
					continue
					
				payments = ""
				price_info = ""
				openingspecs = ""
				hasGR = False
				hasRDF = False
				
				# check that the media type is HTML, XML or XHTML
				r = urllib.urlopen(item['url'])	
				h = r.info()
				r.close()
				h = h['Content-Type']
				html = (h.find('text/html') != -1) # the content type could also contain an encoding etc.
				xhtml = (h.find('application/xhtml+xml') != -1)
				xml = (h.find('text/xml') != -1)
				rdf = (h.find('application/rdf+xml') != -1)
								
				if (html or xhtml or xml or rdf):
					logging.info("***** PARSEABLE: %s, %s" % (item['url'], h))										
					if rdf: 					#rdf/xml will also be accepted, if served as application/rdf+xml
						g = Graph()
						g.parse(item['url'])
						format = "RDF/XML" 
						hasRDF = True
					else:
#						rdfa = pyRdfa.processURI(item['url'], outputFormat='rdf/xml', form={'lax':True})
						g = Graph()
						url_clean = urllib.unquote(item['url'])
						g.parse(url_clean, format="rdfa")
						format = "RDFa"
						if len(g) > 20: # ad-hoc threshold for meaningful triples
							hasRDF = True
						 	
					# add GoodRelations, because we need the element labels etc.
					# we reuse the same graph object instead of parsing it for each URI anew 				
					g += grgraph

					# Convert price info into string
					p = g.subjects(RDF.type, GR.UnitPriceSpecification)
					for pinfo in p:
						if price_info != "":
							price_info += ", "
						currency = g.value(pinfo,GR.hasCurrency)												
						price = g.value(pinfo,GR.hasCurrencyValue)						
						price_min = g.value(pinfo,GR.hasMinCurrencyValue)
						price_max = g.value(pinfo,GR.hasMaxCurrencyValue)
						is_list_price = g.value(pinfo,GR.isListPrice)
						
						price_type = g.value(pinfo,GR.priceType)
						# Let's ne tolerant - accept "true", "True", and boolean:True
						# This is needed because we must expect missing datatypes
						decoration = '<span style="color:red">Today'
						
						is_list_price = str(is_list_price)
						if is_list_price.lower().startswith('true'): 
							price_info += 'List Price: ' # deprecated pattern, but still used by Yahoo
							decoration = "<span>"
						price_type = str(price_type)	
						if price_type.upper().startswith('SRP'):
							price_info += 'Suggested Retail Price: ' # correct pattern
							decoration = "<span>"
																		
						# Is it a point price ?
						if price != None: 
							price_info += "%s %s %.2f"% (decoration,currency,float(price.toPython()))
							
						# Is it a price range?
						# Note that due to reasoning, a point price may be expanded to a price range with min=max
						# Thus, we have to check for the point price first
						else:
							if price_min != None:
								price_info += "%s from: %s %.2f"% (decoration,currency, float(str(price_min))) # expect bad markup
								if price_max != None:
									price_info += " to "
									price_info += "%.2f" % float(str(price_max)) # expect bad markup
							elif price_max != None:
								price_info += "%s %s %.2f or less"% (decoration,currency, float(str(price_max))) # expect bad markup
						price_info += '</span>'
														
					# Convert payment info into string
					for p_option in g.objects(None,GR.acceptedPaymentMethods):
						method = g.label(p_option)
						if len(payments)>0:
							payments += ", "
						pos = method.find(' (') 
						if pos>-1:
							method = method[:pos]
						payments += method

					# Convert Opening hour info into string
					# TBD: Order by day of week
					delimiter = ""					
					for openinghrs in g.subjects(RDF.type,GR.OpeningHoursSpecification):
						openingspecs += delimiter
						opens = g.value(openinghrs,GR.opens)
						closes = g.value(openinghrs,GR.closes)	
						daysofweek = g.objects(openinghrs,GR.hasOpeningHoursDayOfWeek)
						for day in daysofweek:
							dayname = g.label(day)
							dayname = dayname[:3]
							openingspecs += str(dayname)+", "
						openingspecs = openingspecs[:len(openingspecs)-2]	
						openingspecs +=(": "+opens[:5]+"-"+closes[:5])
						delimiter = ", "
				else:
					logging.info("***** FALSE %s, %s -- ignored" % (item['url'], h))
					
				if len(price_info)>0 or len(payments)>0 or len(openingspecs)>0:
					hasGR = True
					logging.info("==>GR>== Found GoodRelations meta-data at %s" % item['url'])
										
				if hasRDF:					
					pyrdfa = PYRDFA_URI % item['url']
					ode = ODE_URI % item['url']
					sigma = SIGMA_URI % item['url']
				else:	
					pyrdfa = ""
					ode = ""
					sigma = ""
									
				if len(price_info) == 0:			
					price_info = '<span style="color:grey;font-style:italic">No price information meta-data available. See list of <a href="http://www.ebusiness-unibw.org/wiki/GoodRelations#Applications">\
					shop software that supports price information</a> for the Web of Linked Data.</span>'
				if len(payments) == 0:
					payments='<span style="color:grey;font-style:italic">No rich meta-data available. Use the <a href="http://www.ebusiness-unibw.org/tools/goodrelations-annotator/">\
					GoodRelations Annotator</a> to create it.</span>'						
				if len(openingspecs) == 0:
					openingspecs='<span style="color:grey;font-style:italic">No rich meta-data available. Use the <a href="http://www.ebusiness-unibw.org/tools/goodrelations-annotator/">\
					GoodRelations Annotator</a> to create it.</span>'
									
				result = Result(uri=item['url'],
					title=item['title'],
					abstract=item['content'],
#					dispuri=item['visibleUrl'], # Google's visibleUrl is too short
					dispuri=item['url'][7:],
					price = price_info,
					payments=payments,
					opening=openingspecs,					
					hasGR=hasGR,
					hasRDF=hasRDF,
					pyrdfa=pyrdfa, 
					ode=ode,
					sigma=sigma,
					format=format)				
				res.append(result)
								
		template_values = {'query':query, 'results':res}

		path = os.path.join(os.path.dirname(__file__), 'index.html')
		self.response.out.write(template.render(path, template_values))
		
def main():
	application = webapp.WSGIApplication([('/', MainHandler)],
                                       debug=True)
  	wsgiref.handlers.CGIHandler().run(application)

if __name__ == '__main__':
	main()
